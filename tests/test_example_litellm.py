"""The gateway example is documentation people copy, so CI runs it.

All fixtures are invented. No real chart number, name or note appears here.
"""

import importlib.util
import pathlib

import pytest

from chart_scrub.store import AliasStore

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "litellm_callback.py"


@pytest.fixture(scope="module")
def example():
    spec = importlib.util.spec_from_file_location("_example_litellm", EXAMPLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def store(tmp_path):
    with AliasStore(str(tmp_path / "t.db")) as s:
        yield s


NOTE = "姓名：王大明\n病歷號碼：1234567\n出生：1971/03/05\n主訴：右肩抬不高三個月。"
MESSAGES = [
    {"role": "system", "content": "你是復健科醫師的助理。"},
    {"role": "user", "content": NOTE},
]


def test_stateless_scrub_removes_identifiers(example):
    out = example.scrub_messages(MESSAGES)
    body = out[-1]["content"]
    assert "王大明" not in body
    assert "1234567" not in body
    assert "右肩抬不高三個月" in body      # the clinical content survives


def test_system_prompt_is_left_alone(example):
    out = example.scrub_messages(MESSAGES)
    assert out[0]["content"] == MESSAGES[0]["content"]


def test_input_messages_are_not_mutated(example):
    before = MESSAGES[-1]["content"]
    example.scrub_messages(MESSAGES)
    assert MESSAGES[-1]["content"] == before


def test_round_trip_restores_the_name(example, store):
    answer, sent = example.round_trip(store, MESSAGES, example._fake_model)
    assert "王大明" not in sent[-1]["content"]
    assert "1234567" not in sent[-1]["content"]
    assert "王大明" in answer


def test_restore_reports_an_alias_it_never_issued(example, store):
    example.scrub_messages_reversible(store, MESSAGES)
    text, unresolved = example.restore_reply(store, "PT-0001 與 PT-9999 同日回診")
    assert "王大明" in text
    assert "PT-9999" in text
    assert unresolved == ["PT-9999"]


def test_demo_runs(example, capsys):
    example._demo()
    out = capsys.readouterr().out
    assert "王大明" in out          # the reversible half worked
    assert "PT-0001" in out         # and the provider saw an alias
