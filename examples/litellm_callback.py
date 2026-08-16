"""Use chart-scrub as an interception layer in front of a language model.

chart-scrub was built for text you keep: de-identify a note, file it, audit it
later. This example covers the other shape — text you send. A prompt leaves for
a cloud model, an answer comes back, and nothing identifiable crosses the wire
in either direction.

Two modes, and the difference matters:

``scrub_messages``
    Stateless. The rule engine masks identifiers into markers (``[姓名]``,
    ``[病歷號]``). Nothing is stored, nothing comes back — the model's answer
    talks about ``[姓名]`` and so do you. Zero setup, zero database.

``scrub_messages_reversible`` + ``restore_reply``
    Stateful. Each patient becomes a stable alias (PT-0001), the mapping lives
    in a local SQLite file, and the reply is restored to real names before you
    read it. The conversation reads normally; the provider only ever saw
    aliases.

Before wiring the reversible mode into a server, read this twice
-----------------------------------------------------------------

The alias database is the one file that re-identifies everything. Running this
inside a gateway means that file lives wherever the gateway runs. If the
gateway is a container on somebody else's host, the mapping has left your
machine and the de-identification no longer protects anyone. Reversible mode
belongs on a workstation, next to the person reading the answers.

Restoration is also partial by design. Dates of birth became ages and generic
markers carry no way home; only aliases return. That is the whole point of the
split — the identifiers you never need back never come back.

Running this file
-----------------

    python examples/litellm_callback.py

It runs a round trip against a fake model, so it works without litellm
installed and without any network access. The ``ChartScrubGuardrail`` class at
the bottom is the litellm proxy wiring and is only defined when litellm is
importable.
"""

from __future__ import annotations

import copy
import os
import sys
from typing import Any, Callable

try:
    from chart_scrub import AliasStore, deidentify, process_record, rehydrate
except ModuleNotFoundError:  # running from a clone without `pip install -e .`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from chart_scrub import AliasStore, deidentify, process_record, rehydrate

__all__ = [
    "scrub_messages",
    "scrub_messages_reversible",
    "restore_reply",
    "round_trip",
]

# Roles whose content is user-supplied and therefore worth scrubbing. A system
# prompt you wrote yourself holds no patient data; scrubbing it anyway would
# mangle instructions that happen to look like identifiers.
_SCRUB_ROLES = ("user",)


def _map_content(
    messages: list[dict[str, Any]], fn: Callable[[str], str]
) -> list[dict[str, Any]]:
    """Apply ``fn`` to the text of every scrubbable message, copying as we go."""
    out = copy.deepcopy(messages)
    for m in out:
        if m.get("role") in _SCRUB_ROLES and isinstance(m.get("content"), str):
            m["content"] = fn(m["content"])
    return out


def scrub_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mask identifiers in place. Stateless, and not reversible."""
    return _map_content(messages, deidentify)


def scrub_messages_reversible(
    store: AliasStore, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Swap each patient for a stable alias, recording the mapping in ``store``.

    ``process_record`` is used rather than ``ingest`` because a chat turn is
    one message, not a file of records, and nothing should be written to disk
    here.
    """

    def one(text: str) -> str:
        return process_record(store, text).text

    return _map_content(messages, one)


def restore_reply(store: AliasStore, reply: str) -> tuple[str, list[str]]:
    """Turn aliases in the model's answer back into names.

    Returns ``(text, unresolved)``. Anything unresolved is left verbatim — an
    alias this database never issued is not something to guess at.
    """
    result = rehydrate(store, reply)
    return result.text, result.unknown + result.nameless


def round_trip(
    store: AliasStore,
    messages: list[dict[str, Any]],
    call_model: Callable[[list[dict[str, Any]]], str],
) -> tuple[str, list[dict[str, Any]]]:
    """Scrub, call, restore. ``call_model`` takes messages and returns text.

    Also hands back what was actually sent, so you can look at it. Reading the
    outbound payload once, with your own eyes, catches more than any test.
    """
    sent = scrub_messages_reversible(store, messages)
    restored, _ = restore_reply(store, call_model(sent))
    return restored, sent


# --------------------------------------------------------------- litellm glue
try:  # pragma: no cover - exercised only where litellm is installed
    from litellm.integrations.custom_logger import CustomLogger

    class ChartScrubGuardrail(CustomLogger):
        """A litellm proxy hook. Stateless mode, because a proxy is shared.

        Reversible mode is deliberately not offered here: a proxy serving more
        than one person would need one alias database per person, and getting
        that wrong mixes patients together. Use :func:`round_trip` from a
        workstation script when you want the names back.
        """

        async def async_pre_call_hook(
            self, user_api_key_dict, cache, data, call_type
        ):
            if isinstance(data.get("messages"), list):
                data["messages"] = scrub_messages(data["messages"])
            return data

except ImportError:  # litellm not installed — the functions above still work
    ChartScrubGuardrail = None  # type: ignore[assignment]


# --------------------------------------------------------------------- demo
def _fake_model(messages: list[dict[str, Any]]) -> str:
    """Stand-in for a provider. Echoes the alias, as a real answer would."""
    sent = messages[-1]["content"]
    alias = "PT-0001" if "PT-0001" in sent else "[病人]"
    return f"{alias} 的症狀比較像肩夾擠症候群，建議先做六週復健。"


def _demo() -> None:
    import tempfile
    import os

    note = "姓名：王大明\n病歷號碼：1234567\n出生：1971/03/05\n主訴：右肩抬不高三個月。"
    messages = [
        {"role": "system", "content": "你是復健科醫師的助理。"},
        {"role": "user", "content": note},
    ]

    print("=== 1. stateless ===")
    for m in scrub_messages(messages):
        print(f"  [{m['role']}] {m['content']!r}")

    print("\n=== 2. reversible ===")
    db = os.path.join(tempfile.mkdtemp(), "demo.db")
    with AliasStore(db) as store:
        answer, sent = round_trip(store, messages, _fake_model)
        print("  sent to the provider:")
        print(f"    {sent[-1]['content']!r}")
        print("  answer as you read it:")
        print(f"    {answer!r}")


if __name__ == "__main__":
    _demo()
