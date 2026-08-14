"""Tests for the 0.3.0 batch: new identifier rules, the checksum classifier,
per-rule skipping, the unidentified exit code, and the monotonic alias counter.
"""

import sqlite3

import pytest

from chart_scrub.cli import main
from chart_scrub.pseudonymize import detect_identity
from chart_scrub.rules import deidentify, is_valid_roc_id
from chart_scrub.store import AliasStore


# ---------------------------------------------------------------- new rules
def test_nhi_card_label_before_the_number():
    assert "1234" not in deidentify("健保卡號：1234-5678-9012")
    assert "[健保卡號]" in deidentify("健保卡號：1234-5678-9012")
    assert "[健保卡號]" in deidentify("卡號 123456789012")


def test_nhi_card_label_after_the_number_still_works():
    assert "[健保卡號]" in deidentify("0000-1234-5678 健保卡")


def test_old_style_arc_number_is_masked():
    assert deidentify("居留證 AB12345678 已核對") == "居留證 [居留證號] 已核對"


def test_lowercase_national_id_is_masked():
    assert "[身分證號]" in deidentify("身分證 a123456789")


def test_overlong_labelled_number_is_masked_whole():
    # An 11-digit value must not be split into a masked prefix and a bare tail.
    out = deidentify("病歷號 12345678901")
    assert "[病歷號]" in out
    assert not any(ch.isdigit() for ch in out)


def test_birth_date_label_variants():
    for text in ("出生日期：1971/03/05", "出生年月日：60年3月5日"):
        out = deidentify(text)
        assert "[生日]" in out, out


def test_lane_alley_address_is_masked_whole():
    out = deidentify("住台北市大安區和平東路100巷5號")
    assert out == "住[地址]"


def test_street_without_county_lane_alley():
    out = deidentify("住在文化路100巷5弄3號")
    assert "5弄" not in out and "3號" not in out


def test_passport_needs_a_label_and_digits():
    assert "[護照號]" in deidentify("護照號碼 312345678")
    # Letters-only after the label is prose, not a number.
    assert deidentify("passport control 已通過") == "passport control 已通過"


# ---------------------------------------------------------------- checksum
def test_checksum_accepts_a_valid_id():
    assert is_valid_roc_id("A123456789")
    assert is_valid_roc_id("a123456789")  # case folded
    assert is_valid_roc_id("Ａ１２３４５６７８９")  # width folded


def test_checksum_rejects_wrong_digit_and_wrong_shape():
    assert not is_valid_roc_id("A123456780")
    assert not is_valid_roc_id("1234567")
    assert not is_valid_roc_id("AB12345678")


def test_checksum_never_gates_masking():
    # A checksum-failing ID-shaped token is still masked.
    assert "[身分證號]" in deidentify("身分證 A123456780")


# ---------------------------------------------------------------- skip
def test_skip_leaves_a_rule_out():
    text = "護照號碼 312345678，電話 0912-345-678"
    out = deidentify(text, skip={"passport"})
    assert "312345678" in out
    assert "[電話]" in out


def test_cli_mask_skip(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("居留證 AB12345678", encoding="utf-8")
    assert main(["mask", str(src), "--skip", "arc_old"]) == 0
    assert "AB12345678" in capsys.readouterr().out


def test_cli_rejects_unknown_skip_name(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["mask", str(src), "--skip", "no_such_rule"])


# ---------------------------------------------------------------- exit codes
def test_ingest_returns_3_when_a_record_has_no_identity(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("主訴：右肩痛三個月，無其他不適。", encoding="utf-8")
    db = tmp_path / "a.db"
    code = main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()
    assert code == 3


def test_ingest_still_returns_0_when_identified(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("病歷號碼：1234567 姓名：王大明\n主訴：右肩痛。", encoding="utf-8")
    db = tmp_path / "a.db"
    code = main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()
    assert code == 0


# ---------------------------------------------------------------- alias store
def test_alias_numbers_are_never_reused_after_deletion(tmp_path):
    db = str(tmp_path / "a.db")
    with AliasStore(db) as store:
        store.alias_for("111111")
        assert store.alias_for("222222") == "PT-0002"
        store.con.execute("DELETE FROM aliases WHERE alias='PT-0002'")
        store.con.commit()
        # The counter has already moved past 2; the number must not come back.
        assert store.alias_for("333333") == "PT-0003"


def test_counter_seeds_from_a_pre_counter_database(tmp_path):
    db = str(tmp_path / "a.db")
    con = sqlite3.connect(db)
    con.executescript(
        """CREATE TABLE patients(mrn TEXT PRIMARY KEY, name TEXT, sex TEXT,
               birth TEXT, first_seen TEXT, last_seen TEXT, last_dx TEXT,
               visit_count INTEGER DEFAULT 0);
           CREATE TABLE aliases(alias TEXT PRIMARY KEY, mrn TEXT UNIQUE, created TEXT);
           INSERT INTO aliases VALUES('PT-0007','111111','2026-01-01');"""
    )
    con.commit()
    con.close()
    with AliasStore(db) as store:
        assert store.alias_for("222222") == "PT-0008"


def test_upsert_maintains_first_and_last_seen(tmp_path):
    db = str(tmp_path / "a.db")
    with AliasStore(db) as store:
        store.upsert_patient("111111", "王大明", None)
        first, last = store.con.execute(
            "SELECT first_seen, last_seen FROM patients WHERE mrn='111111'"
        ).fetchone()
        assert first and last


# ---------------------------------------------------------------- pipeline
def test_detect_identity_reads_the_new_birth_labels():
    _, _, birth = detect_identity("病歷號碼：1234567 出生日期：1971/03/05")
    assert birth == "1971-03-05"
