"""v0.6.0: unlabelled identifiers in English-language charts.

Taiwanese charts are written in English; identifiers arrive pasted from the
HIS with no label at all. Three rules carry this: a standalone CJK token led
by a surname is treated as a name (with a NOT_NAMES stoplist for the words a
doctor types in Chinese when the English term won't come), a name glued to an
already-masked identifier is a name, and a full date is masked by shape alone.
"""

import pytest

from chart_scrub.rules import NOT_NAMES, deidentify


# --------------------------------------------- standalone CJK name
@pytest.mark.parametrize("text,expect", [
    ("Patient 王大明 presented with back pain", "Patient [姓名] presented with back pain"),
    ("王大明 A123456789", "[姓名] [身分證號]"),
    ("A123456789 王大明", "[身分證號] [姓名]"),
    ("s/p TKR, 王大明, follow up", "s/p TKR, [姓名], follow up"),
])
def test_standalone_cjk_name_masked(text, expect):
    assert deidentify(text) == expect


@pytest.mark.parametrize("term", ["高血壓", "白血球", "黃疸", "石膏", "張力"])
def test_not_names_stoplist_survives(term):
    text = f"c/o {term} for years"
    assert deidentify(text) == text


def test_stoplist_entry_with_cjk_neighbour_is_not_consulted():
    # 高血壓性 continues in CJK — the boundary guard, not the stoplist,
    # decides here, and nothing is masked either way.
    text = "known 高血壓性心臟病 history"
    assert deidentify(text) == text


@pytest.mark.parametrize("text", [
    "病人說高血壓很久了，陳舊性骨折未癒合",   # continuous Chinese prose
    "主訴：右肩痛三個月，夜間痛醒。",
])
def test_continuous_chinese_prose_untouched(text):
    assert deidentify(text) == text


def test_non_surname_led_cjk_survives():
    text = "c/o 頭暈 and 落枕"
    assert deidentify(text) == text


# --------------------------------------------- name beside identifier
def test_name_beside_id_inside_chinese_context():
    # Standalone boundaries fail here (CJK neighbour), adjacency carries it.
    out = deidentify("陪同者說王大明A123456789是他弟弟")
    assert "王大明" not in out and "[身分證號]" in out


def test_name_after_date_marker():
    out = deidentify("1971/03/05 王大明回診")
    assert "王大明" not in out and "[日期]" in out


# --------------------------------------------- bare dates by shape
@pytest.mark.parametrize("text,gone", [
    ("DOB 欄空白，實際是 1971/03/05", "1971/03/05"),
    ("admitted 2020-05-03", "2020-05-03"),
    ("op date 113/05/06", "113/05/06"),
    ("60.3.5 出生", "60.3.5"),
    ("key in 19710305", "19710305"),
    ("1971年3月5日", "1971年3月5日"),
])
def test_bare_dates_masked(text, gone):
    out = deidentify(text)
    assert gone not in out
    assert "[日期]" in out or "[生日]" in out


@pytest.mark.parametrize("text", [
    "BP 138/86 mmHg",
    "MMT 4/5, VAS 7",
    "Na/K/Cl 140/4.0/100",     # mixed separators — the backreference guard
    "medication 1-0-1 after meals",
    "L4-5 disc bulge, ICD-10 coded",
    "20259999 is not a date",  # month 99 fails the compact validation
])
def test_clinical_numerics_survive_date_rule(text):
    assert deidentify(text) == text


def test_labelled_birthday_still_wins_over_bare_date():
    # birth_labelled runs first, so the labelled form keeps its [生日] tag.
    out = deidentify("生日：1971/03/05")
    assert "[生日]" in out and "[日期]" not in out


def test_stoplist_has_no_duplicates():
    assert len(NOT_NAMES) == len(set(NOT_NAMES))
