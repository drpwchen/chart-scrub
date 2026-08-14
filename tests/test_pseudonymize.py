"""Tests for the pseudonymisation pipeline.

All fixtures are invented. No real chart number, name or note appears here.
"""

import datetime

import pytest

from chart_scrub.pseudonymize import (
    age_from_birth,
    detect_identity,
    ingest,
    process_record,
    residue_check,
    split_records,
)
from chart_scrub.store import AliasStore

REF = datetime.date(2026, 8, 14)


@pytest.fixture
def store(tmp_path):
    with AliasStore(str(tmp_path / "t.db")) as s:
        yield s


# ------------------------------------------------------------ identity
def test_detect_labelled_record():
    mrn, name, birth = detect_identity("姓名：王大明\n病歷號碼：1234567\n出生：1971/03/05")
    assert (mrn, name, birth) == ("1234567", "王大明", "1971-03-05")


def test_detect_roc_birthday():
    _, _, birth = detect_identity("出生：民國60年3月5日")
    assert birth == "1971-03-05"


def test_detect_compact_roc_birthday():
    _, _, birth = detect_identity("生日：0600305")
    assert birth == "1971-03-05"


def test_detect_id_name_shorthand():
    mrn, name, _ = detect_identity("A123456789 王大明 右肩痛")
    assert (mrn, name) == ("A123456789", "王大明")


def test_detect_id_name_reversed():
    mrn, name, _ = detect_identity("王大明 A123456789 右肩痛")
    assert (mrn, name) == ("A123456789", "王大明")


def test_role_word_before_an_id_is_not_taken_as_the_name():
    # "陪同者 A123456789 李小華" must resolve to 李小華, not 陪同者.
    mrn, name, _ = detect_identity("陪同者 A123456789 李小華")
    assert (mrn, name) == ("A123456789", "李小華")


def test_age_from_birth():
    assert age_from_birth("1971-03-05", REF) == 55
    assert age_from_birth("1971-09-05", REF) == 54  # birthday not yet reached
    assert age_from_birth(None) is None
    assert age_from_birth("not-a-date") is None


# ------------------------------------------------------------ splitting
def test_split_on_separator_line():
    assert len(split_records("病歷號碼：1111111 甲\n---\n病歷號碼：2222222 乙")) == 2


def test_split_on_chart_number_lines():
    text = "病歷號碼：1111111 甲\n主訴 A\n病歷號碼：2222222 乙\n主訴 B"
    parts = split_records(text)
    assert len(parts) == 2
    assert "主訴 A" in parts[0] and "主訴 B" in parts[1]


def test_split_on_id_name_shorthand():
    text = "A123456789 王大明 右肩痛\nB234567890 李小華 下背痛"
    assert len(split_records(text)) == 2


def test_continuation_lines_stay_with_their_patient():
    text = "A123456789 王大明 右肩痛\n  夜間痛醒\nB234567890 李小華 下背痛"
    parts = split_records(text)
    assert len(parts) == 2
    assert "夜間痛醒" in parts[0]


def test_single_record_is_not_split():
    assert len(split_records("病歷號碼：1111111\n主訴：右肩痛\n理學檢查：Neer (+)")) == 1


# ------------------------------------------------------------ aliasing
def test_alias_replaces_name_and_chart_number(store):
    r = process_record(store, "病歷號碼：1234567 姓名：王大明\n王大明主訴右肩痛", ref_date=REF)
    assert r.alias == "PT-0001"
    assert "王大明" not in r.text
    assert "1234567" not in r.text
    assert "PT-0001" in r.text
    assert r.ok


def test_same_patient_keeps_the_same_alias_across_visits(store):
    first = process_record(store, "病歷號碼：1234567 姓名：王大明\n初診", ref_date=REF)
    second = process_record(store, "病歷號碼：1234567\n回診，肩膀好些", ref_date=REF)
    assert first.alias == second.alias == "PT-0001"


def test_second_patient_gets_a_second_alias(store):
    process_record(store, "病歷號碼：1111111 姓名：王大明", ref_date=REF)
    r = process_record(store, "病歷號碼：2222222 姓名：李小華", ref_date=REF)
    assert r.alias == "PT-0002"


def test_given_name_alone_is_replaced(store):
    r = process_record(store, "病歷號碼：1234567 姓名：王大明\n大明說他不想開刀", ref_date=REF)
    assert "大明" not in r.text


def test_birthday_becomes_age(store):
    r = process_record(store, "病歷號碼：1234567 姓名：王大明 出生：1971/03/05\n"
                              "1971/03/05 生", ref_date=REF)
    assert r.age == 55
    assert "1971/03/05" not in r.text
    assert "[55歲]" in r.text


def test_known_patient_is_recognised_without_repeating_the_name(store):
    process_record(store, "病歷號碼：1234567 姓名：王大明 出生：1971/03/05", ref_date=REF)
    r = process_record(store, "病歷號碼：1234567\n回診", ref_date=REF)
    assert r.age == 55  # pulled from the store, not from this record


def test_record_without_any_identifier_still_gets_masked(store):
    r = process_record(store, "陳先生主訴右肩痛，電話 0912-345-678", ref_date=REF)
    assert r.alias is None
    assert r.identified is False
    assert "0912" not in r.text
    assert "[稱謂]" in r.text


def test_content_never_enters_the_stats(store):
    r = process_record(store, "病歷號碼：1234567 姓名：王大明\n主訴：右肩痛", ref_date=REF)
    blob = repr(r.stats) + repr(r.alias) + repr(r.leaks)
    assert "右肩痛" not in blob
    assert "王大明" not in blob


def test_chart_number_inside_another_id_is_not_chopped(store):
    # 1234567 is a substring of A123456789. A plain string replace rewrites the
    # middle of that ID into APT-000189: mangled rather than masked, and no
    # longer ID-shaped, so the residue check stops seeing it too.
    text = "病歷號碼：1234567 姓名：王大明\n陪同者 A123456789 李小華"
    results = ingest(store, text, ref_date=REF)
    body = results[0].text
    assert "APT-" not in body, body
    assert "A123456789" not in body
    assert "PT-0002" in body   # the companion got their own alias, intact


def test_chart_number_inside_a_phone_number_is_not_chopped(store):
    # 234567 sitting inside 0912345678 would break the phone rule's match.
    store.alias_for("234567")
    store.upsert_patient("234567", "王大明", None)
    r = process_record(store, "病歷號碼：234567 姓名：王大明\n電話 0912345678", ref_date=REF)
    assert "[電話]" in r.text, r.text
    assert "0912" not in r.text


def test_another_patients_chart_number_is_also_token_bounded(store):
    # Same collision, different code path: the chart number being substituted
    # belongs to some OTHER patient on record (2345678), and it sits inside a
    # third party's ID (A234567890) in this record. Unbounded, that ID becomes
    # APT-000290 and the ID rule never gets to mask it.
    store.alias_for("2345678")
    store.upsert_patient("2345678", "李小華", None)
    r = process_record(store, "病歷號碼：1111111 姓名：王大明\n轉介單附 A234567890",
                       ref_date=REF)
    assert "[身分證號]" in r.text, r.text
    assert "APT-" not in r.text


# ------------------------------------------------------------ batch ingest
def test_other_patient_mentioned_in_passing_gets_their_own_alias(store):
    text = ("病歷號碼：1111111 姓名：王大明\n"
            "與李小華同住，李小華也是本科病人。\n"
            "---\n"
            "病歷號碼：2222222 姓名：李小華\n下背痛")
    results = ingest(store, text, ref_date=REF)
    assert len(results) == 2
    assert "李小華" not in results[0].text
    assert "PT-0002" in results[0].text  # referred to by their own alias
    assert all(r.ok for r in results)


def test_batch_registers_everyone_before_masking(store):
    # 李小華 appears inside 王大明's record BEFORE their own record exists.
    # A one-pass implementation leaks the name here.
    text = ("A123456789 王大明 陪同者李小華\n"
            "B234567890 李小華 下背痛")
    results = ingest(store, text, ref_date=REF)
    assert all("李小華" not in r.text for r in results)


def test_person_named_only_inside_someone_elses_record_is_registered(store):
    # This one exercises the whole-input ID+name scan specifically: the record
    # is NOT split (it carries a labelled chart number), so per-record identity
    # detection only ever sees 王大明. Without the second scan, 李小華 stays in
    # the output next to a masked ID — which is exactly what the residue
    # heuristic is there to catch.
    text = "病歷號碼：1111111 姓名：王大明\n陪同者 A123456789 李小華，與病人同住。"
    results = ingest(store, text, ref_date=REF)
    assert len(results) == 1
    assert "李小華" not in results[0].text
    assert "PT-0002" in results[0].text
    assert results[0].ok, results[0].leaks


def test_every_record_in_a_batch_is_returned(store):
    text = "\n---\n".join(f"病歷號碼：111111{i} 姓名：測試{i}" for i in range(1, 4))
    assert len(ingest(store, text, ref_date=REF)) == 3


# ------------------------------------------------------------ residue check
def test_residue_check_catches_a_known_name(store):
    store.alias_for("1234567")
    store.upsert_patient("1234567", "王大明", None)
    leaks = residue_check(store, "王大明今天回診")
    assert any("姓名" in x for x in leaks)


def test_residue_check_catches_a_known_chart_number(store):
    store.alias_for("1234567")
    store.upsert_patient("1234567", "王大明", None)
    assert any("病歷號" in x for x in residue_check(store, "chart 1234567"))


def test_residue_check_catches_an_unmasked_id(store):
    assert "殘留未遮罩ID" in residue_check(store, "身分證 A123456789")


def test_residue_check_catches_a_name_glued_to_a_masked_id(store):
    # The shape of a leak the targeted pass missed: the ID got masked by the
    # generic rules but the name beside it did not.
    assert any("疑似姓名" in x for x in residue_check(store, "[身分證號] 王大明"))


def test_clean_record_passes_the_residue_check(store):
    assert residue_check(store, "PT-0001，55歲，主訴右肩痛。") == []
