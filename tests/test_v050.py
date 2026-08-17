"""v0.5.0: English chart headers, custom rule files, and the number audit.

Taiwanese charts are written in English prose with identifiers pasted in from
the HIS — sometimes under English labels, more often with no label at all.
The label rules go bilingual here; the unlabelled case is served by
``--rules`` (your hospital's own shapes) plus ``--audit`` (find out which
shapes survived so you know what to write down).
"""

import datetime
import json

import pytest

from chart_scrub.pseudonymize import detect_identity, process_record
from chart_scrub.rules import (
    Rule,
    audit_numbers,
    classify_number,
    deidentify,
    load_rules_file,
)
from chart_scrub.store import AliasStore

REF = datetime.date(2026, 8, 17)


# ------------------------------------------------------- English labels
@pytest.mark.parametrize("text,gone", [
    ("Chart No: 12345678", "12345678"),
    ("chart no. 12345678", "12345678"),
    ("MRN 87654321", "87654321"),
    ("MRN#87654321", "87654321"),
    ("Case No: 5566778", "5566778"),
    ("Medical record number 12345678", "12345678"),
])
def test_english_chart_labels_masked(text, gone):
    out = deidentify(text)
    assert gone not in out
    assert "[病歷號]" in out


def test_flowchart_is_not_a_chart_label():
    # \b keeps "flowchart" from donating its tail as a label.
    assert deidentify("see flowchart no. 123456 in the appendix") == \
        "see flowchart no. 123456 in the appendix"


def test_bare_case_is_prose_not_a_label():
    # "case" without an explicit No./number is everyday English.
    assert deidentify("in case 123456 patients enroll") == \
        "in case 123456 patients enroll"


@pytest.mark.parametrize("text", [
    "DOB: 1971/03/05",
    "dob: 1971-03-05",
    "Date of Birth: 1971/03/05",
    "Birthday 1971/03/05",
    "birth date: 60年3月5日",
])
def test_english_birth_labels_masked(text):
    out = deidentify(text)
    assert "1971" not in out and "60年" not in out
    assert "[生日]" in out


@pytest.mark.parametrize("text", [
    "birth weight 3200g",
    "preterm birth at 34 weeks",
])
def test_bare_birth_prose_survives(text):
    assert deidentify(text) == text


def test_birth_value_stops_at_newline():
    # The value class must not swallow the line break — that glued the next
    # line onto the label ("出生[生日]主訴").
    out = deidentify("出生：1971/03/05\n主訴：頭痛")
    assert "\n" in out
    assert "主訴：頭痛" in out


@pytest.mark.parametrize("text,gone", [
    ("Name: Wang Ta-Ming", "Wang Ta-Ming"),
    ("Name: WANG, TA-MING", "WANG, TA-MING"),
    ("NAME: CHEN MEI-LING", "CHEN MEI-LING"),
])
def test_romanised_name_after_label_masked(text, gone):
    out = deidentify(text)
    assert gone not in out
    assert "[NAME]" in out


def test_name_match_stops_before_lowercase_prose():
    out = deidentify("Name: Wang Ta-Ming presented with back pain")
    assert "Wang" not in out
    assert "presented with back pain" in out


def test_eponyms_still_survive():
    text = "McMurray test positive, Osgood-Schlatter suspected"
    assert deidentify(text) == text


# ------------------------------------------ English header, full pipeline
def test_detect_identity_from_english_header():
    mrn, name, birth = detect_identity(
        "Chart No: 12345678  Name: WANG, TA-MING  DOB: 1971/03/05\n"
        "S: low back pain for 3 months"
    )
    assert mrn == "12345678"
    assert name == "WANG, TA-MING"
    assert birth == "1971-03-05"


def test_process_record_english_header(tmp_path):
    with AliasStore(str(tmp_path / "a.db")) as store:
        r = process_record(
            store,
            "Chart No: 12345678  Name: WANG, TA-MING  DOB: 1971/03/05\n"
            "Wang Ta-Ming reports numbness.",
            ref_date=REF,
        )
    assert r.identified and r.alias
    assert r.age == 55
    # Header form and prose form of the same name both become the alias.
    assert "WANG" not in r.text and "Wang" not in r.text
    assert r.text.count(r.alias) >= 2


def test_romanised_name_is_not_first_char_chopped(tmp_path):
    # The Chinese given-name trick (name[1:]) must never run on an ASCII
    # name: "Wang Taming"[1:] is "ang Taming", which sits inside the *other*
    # person's name "Tang Taming" — running it would corrupt that name into
    # "T<alias>" instead of leaving it for its own masking.
    with AliasStore(str(tmp_path / "a.db")) as store:
        r = process_record(
            store, "Name: Wang Taming\nReferred by Dr. Tang Taming.",
            mrn="12345678", ref_date=REF,
        )
    assert "Tang Taming" in r.text


# ------------------------------------------------------- custom rules
def test_extra_rules_mask_unlabelled_shapes():
    my_mrn = Rule("my_mrn", r"(?<![A-Za-z0-9])\d{8}(?!\d)", "[病歷號]",
                  "bare 8 digits are chart numbers at my hospital")
    out = deidentify("pt 20250731 seen today", extra_rules=[my_mrn])
    assert out == "pt [病歷號] seen today"


def test_extra_rules_run_before_builtins():
    # The caller's pattern gets first claim on the text.
    mine = Rule("my_id", r"[A-Za-z]\d{9}", "[院內格式]", "")
    out = deidentify("A123456789", extra_rules=[mine])
    assert out == "[院內格式]"


def test_load_rules_file_roundtrip(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps([{
        "name": "my_mrn",
        "pattern": r"(?<![A-Za-z0-9])\d{8}(?!\d)",
        "replacement": "[病歷號]",
    }]), encoding="utf-8")
    rules = load_rules_file(str(p))
    assert len(rules) == 1
    assert deidentify("no 20250731 x", extra_rules=rules) == "no [病歷號] x"


@pytest.mark.parametrize("entry,msg", [
    ({"name": "mrn", "pattern": r"\d+", "replacement": "x"}, "collides"),
    ({"name": "bad", "pattern": r"[unclosed", "replacement": "x"}, "compile"),
    ({"name": "a", "pattern": r"\d"}, "missing"),
    ({"name": "f", "pattern": r"\d", "replacement": "x", "flags": "gx"}, "flags"),
])
def test_load_rules_file_rejects_bad_entries(tmp_path, entry, msg):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        load_rules_file(str(p))


def test_load_rules_file_rejects_duplicate_names(tmp_path):
    p = tmp_path / "rules.json"
    entry = {"name": "dup", "pattern": r"\d", "replacement": "x"}
    p.write_text(json.dumps([entry, entry]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_rules_file(str(p))


# ------------------------------------------------------------- audit
def test_audit_finds_and_classifies_survivors():
    # bare_date (v0.6.0) would mask the compact date; skipping it here keeps
    # this test about the audit — a date-shaped survivor must be called out.
    masked = deidentify("身分證 A123456789 已遮，病歷號另有 20250731 和 55667788",
                        skip={"bare_date"})
    found = {tok: kind for tok, _, kind in audit_numbers(masked)}
    assert "A123456789" not in found          # masked, so not a survivor
    assert "似日期" in found["20250731"]
    assert "病歷號常見長度" in found["55667788"]


def test_audit_counts_and_sorts_by_frequency():
    out = audit_numbers("55667788 x 55667788 y 99999")
    assert out[0][0] == "55667788" and out[0][1] == 2


@pytest.mark.parametrize("token,expect", [
    ("A123456789", "確定身分證號"),      # valid checksum
    ("A123456780", "檢查碼無效"),
    ("AB12345678", "居留證號"),
    ("0912345678", "手機"),
    ("20250731", "似日期"),
    ("1234567", "病歷號常見長度"),
    ("123456789012", "未分類"),
])
def test_classify_number(token, expect):
    assert expect in classify_number(token)
