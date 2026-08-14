"""End-to-end CLI tests, including the exit code the residue check reports."""

import json
import os

import pytest

from clinic_deid.cli import main

RECORD = "病歷號碼：1234567 姓名：王大明 出生：1971/03/05\n主訴：右肩痛三個月。"


def test_mask_writes_masked_text_to_stdout(capsys, tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("電話 0912-345-678", encoding="utf-8")
    assert main(["mask", str(src)]) == 0
    out = capsys.readouterr().out
    assert "[電話]" in out
    assert "0912" not in out


def test_mask_does_not_create_a_database(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("電話 0912-345-678", encoding="utf-8")
    db = tmp_path / "nope.db"
    main(["--db", str(db), "mask", str(src)])
    capsys.readouterr()
    assert not db.exists()


def test_ingest_writes_a_deid_file(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    db = tmp_path / "a.db"
    assert main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)]) == 0

    outs = list(tmp_path.glob("PT-0001_*.deid.txt"))
    assert len(outs) == 1
    body = outs[0].read_text(encoding="utf-8")
    assert "王大明" not in body
    assert "1234567" not in body
    assert "右肩痛" in body  # clinical content survives


def test_ingest_json_output(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    main(["--db", str(tmp_path / "a.db"), "ingest", str(src),
          "--out", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["records"][0]["alias"] == "PT-0001"


def test_ingest_never_prints_patient_content(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    main(["--db", str(tmp_path / "a.db"), "ingest", str(src), "--out", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "右肩痛" not in printed
    assert "王大明" not in printed


def test_ingest_does_not_overwrite_an_existing_output(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    db = tmp_path / "a.db"
    for _ in range(2):
        src.write_text(RECORD, encoding="utf-8")
        main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()
    assert len(list(tmp_path.glob("PT-0001_*.deid.txt"))) == 2


def test_verify_fails_on_a_file_that_still_holds_an_identifier(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    db = tmp_path / "a.db"
    main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()

    bad = tmp_path / "leaked.txt"
    bad.write_text("王大明今天回診", encoding="utf-8")
    assert main(["--db", str(db), "verify", str(bad)]) == 2
    assert "FAIL" in capsys.readouterr().out


def test_verify_passes_on_a_clean_file(tmp_path, capsys):
    clean = tmp_path / "clean.txt"
    clean.write_text("PT-0001，55歲，主訴右肩痛。", encoding="utf-8")
    assert main(["--db", str(tmp_path / "a.db"), "verify", str(clean)]) == 0


def test_list_prints_aliases_without_identifiers(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    db = tmp_path / "a.db"
    main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()

    main(["--db", str(db), "list"])
    out = capsys.readouterr().out
    assert "PT-0001" in out
    assert "王大明" not in out
    assert "1234567" not in out


def test_who_resolves_an_alias(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text(RECORD, encoding="utf-8")
    db = tmp_path / "a.db"
    main(["--db", str(db), "ingest", str(src), "--out", str(tmp_path)])
    capsys.readouterr()

    assert main(["--db", str(db), "who", "pt-0001"]) == 0
    assert "王大明" in capsys.readouterr().out


def test_who_on_an_unknown_alias(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "a.db"), "who", "PT-9999"]) == 1


def test_utf16_input_is_read(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_bytes(RECORD.encode("utf-16"))
    assert main(["--db", str(tmp_path / "a.db"), "ingest", str(src),
                 "--out", str(tmp_path)]) == 0


def test_big5_input_is_read(tmp_path, capsys):
    # A Big5 file has no BOM. Decoding it as UTF-16 succeeds and yields
    # mojibake, which then matches no rule at all — so this test asserts the
    # patient was actually identified, not merely that the command exited 0.
    src = tmp_path / "in.txt"
    src.write_bytes(RECORD.encode("cp950"))
    assert main(["--db", str(tmp_path / "a.db"), "ingest", str(src),
                 "--out", str(tmp_path)]) == 0
    outs = list(tmp_path.glob("PT-0001_*.deid.txt"))
    assert len(outs) == 1, "record was not identified — check encoding detection"
    body = outs[0].read_text(encoding="utf-8")
    assert "王大明" not in body
    assert "右肩痛" in body  # proves it decoded, rather than masking garbage


def test_utf16_with_bom_is_read(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_bytes(b"\xff\xfe" + RECORD.encode("utf-16-le"))
    assert main(["--db", str(tmp_path / "a.db"), "ingest", str(src),
                 "--out", str(tmp_path)]) == 0
    outs = list(tmp_path.glob("PT-0001_*.deid.txt"))
    assert len(outs) == 1
    assert "右肩痛" in outs[0].read_text(encoding="utf-8")
