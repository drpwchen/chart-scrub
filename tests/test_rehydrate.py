"""Tests for the reverse direction: aliases back into names.

All fixtures are invented. No real chart number, name or note appears here.
"""

import datetime

import pytest

from chart_scrub.pseudonymize import ingest, process_record, rehydrate
from chart_scrub.store import AliasStore

REF = datetime.date(2026, 8, 14)


@pytest.fixture
def store(tmp_path):
    with AliasStore(str(tmp_path / "t.db")) as s:
        yield s


def _register(store, mrn, name, birth=None):
    """Put one patient on record and hand back their alias."""
    alias = store.alias_for(mrn)
    store.upsert_patient(mrn, name, birth)
    return alias


# ------------------------------------------------------------ round trip
def test_round_trip_restores_the_name(store):
    text = "姓名：王大明\n病歷號碼：1234567\n主訴：右肩痛三個月。"
    record = process_record(store, text, ref_date=REF)
    assert record.alias not in (None, "")
    assert "王大明" not in record.text

    back = rehydrate(store, record.text)
    assert "王大明" in back.text
    assert record.alias not in back.text
    assert back.complete


def test_restores_every_occurrence(store):
    alias = _register(store, "1234567", "王大明")
    reply = f"{alias} 的問題是肩夾擠。建議 {alias} 先做six週復健。"
    back = rehydrate(store, reply)
    assert back.text.count("王大明") == 2
    assert alias not in back.text


def test_with_chart_number(store):
    alias = _register(store, "1234567", "王大明")
    back = rehydrate(store, f"{alias}回診", with_mrn=True)
    assert back.text == "王大明（病歷號 1234567）回診"


def test_lowercase_alias_still_resolves(store):
    alias = _register(store, "1234567", "王大明")
    back = rehydrate(store, f"{alias.lower()} 回診")
    assert "王大明" in back.text


# ------------------------------------------------- the prefix collision
def test_shorter_alias_does_not_eat_the_longer_one(store):
    """PT-1 is a prefix of PT-10. One scan, not one loop.

    Replacing alias by alias in a loop rewrites PT-10 into 甲0. The four-digit
    format hides this until a store issues its 10000th alias, so the aliases
    are inserted by hand to reach the collision now rather than later.
    """
    store.con.execute("INSERT INTO aliases(alias, mrn) VALUES('PT-1','111')")
    store.con.execute("INSERT INTO aliases(alias, mrn) VALUES('PT-10','222')")
    store.con.commit()
    store.upsert_patient("111", "甲君", None)
    store.upsert_patient("222", "乙君", None)

    back = rehydrate(store, "PT-10 陪同 PT-1 前來")
    assert back.text == "乙君 陪同 甲君 前來"


def test_alias_inside_a_longer_number_is_left_alone(store):
    """PT-00011 is not PT-0001 followed by a 1.

    Guaranteed by the greedy digit run: the whole token matches, then misses
    the table. No trailing look-ahead is involved.
    """
    _register(store, "1234567", "王大明")
    back = rehydrate(store, "代號 PT-00011")
    assert "王大明" not in back.text
    assert back.unknown == ["PT-00011"]


def test_alias_glued_to_a_leading_token_is_not_matched(store):
    """The leading boundary is the guard that actually does work."""
    _register(store, "1234567", "王大明")
    back = rehydrate(store, "XPT-0001 是別的編號")
    assert back.text == "XPT-0001 是別的編號"
    assert back.resolved == {}


# ------------------------------------------------------ non-candidates
@pytest.mark.parametrize("text", ["COVID-19 病史", "L4-5 椎間盤突出", "ICD-10 編碼"])
def test_hyphenated_clinical_terms_are_not_aliases(store, text):
    _register(store, "1234567", "王大明")
    back = rehydrate(store, text)
    assert back.text == text
    assert back.unknown == []


def test_empty_store_returns_text_untouched(store):
    back = rehydrate(store, "PT-0001 回診")
    assert back.text == "PT-0001 回診"
    assert back.resolved == {}


# ------------------------------------------------------- what cannot come back
def test_unknown_alias_is_reported_not_guessed(store):
    _register(store, "1234567", "王大明")
    back = rehydrate(store, "PT-0001 與 PT-9999 同日回診")
    assert "PT-9999" in back.text          # left exactly as it was
    assert back.unknown == ["PT-9999"]
    assert not back.complete


def test_alias_without_a_name_is_reported(store):
    alias = store.alias_for("7654321")     # no upsert_patient: no name on record
    back = rehydrate(store, f"{alias} 回診")
    assert alias in back.text
    assert back.nameless == [alias]
    assert not back.complete


def test_repeated_unknown_alias_reported_once(store):
    _register(store, "1234567", "王大明")
    back = rehydrate(store, "PT-9999 與 PT-9999")
    assert back.unknown == ["PT-9999"]


def test_age_does_not_become_a_birthday_again(store):
    text = "姓名：王大明\n病歷號碼：1234567\n出生：1971/03/05\n主訴：肩痛。"
    record = process_record(store, text, ref_date=REF)
    back = rehydrate(store, record.text)
    assert "1971" not in back.text
    assert "55歲" in back.text


def test_generic_markers_stay_masked(store):
    text = "姓名：王大明\n病歷號碼：1234567\n電話：0912345678"
    record = process_record(store, text, ref_date=REF)
    back = rehydrate(store, record.text)
    assert "0912345678" not in back.text


# ------------------------------------------------------------ multi-patient
def test_two_patients_each_get_their_own_name_back(store):
    """Identity is passed in explicitly rather than split out of one blob.

    ``split_records`` cuts on the chart-number line, so a 姓名 line sitting
    above it lands in the previous chunk — a known limitation of the splitter,
    unrelated to this direction. Feeding each record separately keeps this
    test about rehydration.
    """
    a = process_record(store, "主訴：肩痛。", "1234567", "王大明", ref_date=REF)
    b = process_record(store, "主訴：膝痛。", "7654321", "李小華", ref_date=REF)
    back = rehydrate(store, a.text + "\n" + b.text)
    assert "王大明" in back.text and "李小華" in back.text
    assert back.complete


def test_ingest_output_round_trips(store):
    blob = "王大明 A123456789 主訴肩痛。\n李小華 B234567890 主訴膝痛。"
    results = ingest(store, blob, ref_date=REF)
    back = rehydrate(store, "\n".join(r.text for r in results))
    assert "王大明" in back.text and "李小華" in back.text
