"""Tests for the masking engine.

Every test here is written so that removing the rule it covers makes it fail.
The negative tests matter just as much: an engine that masks everything would
pass all the positive tests and be useless.
"""

import pytest

from chart_scrub.rules import RULES, deidentify, deidentify_verbose, normalize


# ------------------------------------------------------------ identifiers
@pytest.mark.parametrize("text,gone", [
    ("病歷號碼：1234567", "1234567"),
    ("病歷號 A123456", "A123456"),
    ("案號: 987654321", "987654321"),
    ("掛號號碼 55667788", "55667788"),
])
def test_chart_numbers_are_masked(text, gone):
    assert gone not in deidentify(text)
    assert "[病歷號]" in deidentify(text)


def test_roc_id_masked_anywhere():
    assert deidentify("身分證 A123456789 已核對") == "身分證 [身分證號] 已核對"


def test_new_style_arc_number_masked():
    # Post-2021 resident certificates use a second letter-derived digit;
    # the rule must not assume the old 1/2 gender digit.
    assert "[身分證號]" in deidentify("居留證 A800000014")


def test_fullwidth_id_masked():
    assert "[身分證號]" in deidentify("身分證Ａ１２３４５６７８９")


@pytest.mark.parametrize("phone", [
    "0912-345-678", "0912345678", "0912 345 678", "03-1234567", "02-27123456",
])
def test_phone_numbers_masked(phone):
    assert "[電話]" in deidentify(f"電話{phone}")


def test_phone_masked_without_word_boundary():
    # CJK counts as a word character, so \b would never fire here.
    assert "0912" not in deidentify("聯絡電話0912345678請撥")


def test_email_masked():
    assert deidentify("寄到 daming@example.com 給我") == "寄到 [電子郵件] 給我"


# ------------------------------------------------------------------ dates
def test_roc_birthday_masked():
    assert "[生日]" in deidentify("民國60年3月5日生")


def test_labelled_birthday_masked():
    assert "1971/03/05" not in deidentify("生日：1971/03/05")


# --------------------------------------------------------------- addresses
@pytest.mark.parametrize("addr", [
    "新北市板橋區文化路一段100號5樓",
    "台中市西屯區台灣大道三段99號",
    "宜蘭縣礁溪鄉中央路二段10巷5號",
    # Pre-2010 county names: older patients give the address they moved in with.
    "台北縣板橋市文化路一段100號5樓",
    "高雄縣鳳山市中山路50號",
])
def test_addresses_masked(addr):
    out = deidentify(f"住{addr}")
    assert out == "住[地址]", out


def test_street_without_county_masked():
    assert deidentify("復健科在中山路100號3樓") == "復健科在[地址]"


def test_road_without_house_number_survives():
    # A road mentioned in passing is not an address.
    text = "他說沿著中山路走十分鐘就到了。"
    assert deidentify(text) == text


# -------------------------------------------------------------------- names
def test_surname_plus_title_masked():
    assert deidentify("陳先生今天回診") == "[稱謂]今天回診"


def test_full_name_plus_title_masked():
    assert "王大明" not in deidentify("王大明先生今天回診")


def test_declared_name_masked():
    assert "林志偉" not in deidentify("我叫林志偉")


def test_role_word_plus_name_masked():
    assert "陳小明" not in deidentify("病人陳小明主訴右肩痛")


def test_family_member_name_masked():
    assert deidentify("我太太林美玉說我走路都歪一邊") == "我太太[姓名]說我走路都歪一邊"


def test_relation_word_before_a_title_is_not_chopped():
    # "他太太黃小姐" must become "他太太[稱謂]", never "他[姓名]姐".
    assert deidentify("他太太黃小姐陪同") == "他太太[稱謂]陪同"


def test_english_name_after_cue_masked():
    assert deidentify("My name is John Smith.") == "My name is [NAME]."


# ------------------------------------------------- what must NOT be masked
def test_medical_eponyms_survive():
    text = "McMurray test 陰性，Colles fracture 已癒合，Neer sign 陽性。"
    assert deidentify(text) == text


def test_bare_surname_survives():
    # 黃 and 白 are surnames and also ordinary words. Masking a lone surname
    # would shred normal clinical prose.
    text = "皮膚偏黃，白血球正常，江湖傳言不足採信。"
    assert deidentify(text) == text


def test_clinical_measurements_survive():
    text = "ROM 0-120 度，MMT 4/5，VAS 7 分，血壓 138/86 mmHg。"
    assert deidentify(text) == text


def test_punctuation_is_not_folded():
    # NFKC would turn these into ASCII. We only fold digits and letters.
    text = "主訴：右肩痛（三個月），夜間痛醒。"
    assert deidentify(text) == text


def test_normalize_leaves_punctuation_alone():
    assert normalize("（）：，。") == "（）：，。"
    assert normalize("Ａ１ｚ") == "A1z"


# ------------------------------------------------------------- bookkeeping
def test_verbose_counts_only_rules_that_fired():
    _, hits = deidentify_verbose("電話 0912-345-678")
    assert hits == {"mobile": 1}


def test_verbose_counts_repeats():
    _, hits = deidentify_verbose("A123456789 與 B234567890")
    assert hits["roc_id"] == 2


def test_rule_names_are_unique():
    names = [r.name for r in RULES]
    assert len(names) == len(set(names))


def test_every_rule_has_a_description():
    assert all(r.description.strip() for r in RULES)
