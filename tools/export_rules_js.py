#!/usr/bin/env python3
"""Generate the browser demo's rule table from the Python one.

The Python ``RULES`` list is the only place a pattern is ever written. This
script rewrites ``docs/rules.generated.js`` from it, and ``--check`` fails when
the two have drifted — which is what CI runs, so a rule change that forgets the
demo cannot be merged.

Two engine differences are handled here:
  * backreferences: Python ``\\1`` becomes JavaScript ``$1``
  * ``re.sub`` replaces every occurrence, so each RegExp gets the ``g`` flag

One difference is handled by normalising first: Python's ``\\d`` matches
full-width digits and JavaScript's does not, so both sides fold full-width
digits and Latin letters to half-width before any rule runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from chart_scrub.rules import RULES, _ROC_ID_LETTER  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "rules.generated.js")

HEADER = """// GENERATED FILE — do not edit.
// Source of truth: chart_scrub/rules.py
// Regenerate: python tools/export_rules_js.py
"""


def to_js_replacement(repl: str) -> str:
    """Python backreference syntax to JavaScript's."""
    return re.sub(r"\\(\d)", r"$\1", repl)


def render() -> str:
    entries = []
    for rule in RULES:
        entries.append(
            "  {\n"
            f"    name: {json.dumps(rule.name)},\n"
            f"    description: {json.dumps(rule.description, ensure_ascii=False)},\n"
            f"    pattern: new RegExp({json.dumps(rule.pattern, ensure_ascii=False)}, "
            f"{json.dumps('g' + rule.flags)}),\n"
            f"    replacement: {json.dumps(to_js_replacement(rule.replacement), ensure_ascii=False)},\n"
            "  },"
        )
    body = "\n".join(entries)
    letters = json.dumps(_ROC_ID_LETTER)
    return rf"""{HEADER}
export const RULES = [
{body}
];

// Mirrors chart_scrub.rules.normalize(): full-width digits and Latin letters
// fold to half-width, punctuation is left alone.
export function normalize(text) {{
  return text.replace(/[０-９Ａ-Ｚａ-ｚ]/g,
    c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
}}

// Mirrors chart_scrub.rules.deidentify_verbose(), including its `skip`
// parameter (here `disabled`, a Set of rule names to leave out) and its
// `extra_rules` (here `extra`, an array of {{name, pattern, replacement}}
// whose patterns run BEFORE the built-in table — the caller knows their own
// data format better than we do).
export function deidentify(text, {{ normalize: doNormalize = true, disabled = new Set(), extra = [] }} = {{}}) {{
  if (doNormalize) text = normalize(text);
  const hits = {{}};
  for (const rule of [...extra, ...RULES]) {{
    if (disabled.has(rule.name)) continue;
    rule.pattern.lastIndex = 0;
    const before = text;
    text = text.replace(rule.pattern, rule.replacement);
    if (text !== before) {{
      const matches = before.match(rule.pattern);
      hits[rule.name] = matches ? matches.length : 1;
    }}
  }}
  return {{ text, hits }};
}}

// Mirrors chart_scrub.rules.is_valid_roc_id(). Classification only —
// masking must never depend on this: a real ID with one digit mistyped
// fails the checksum, and a masking pass gated on validity would wave
// exactly that ID through.
const ROC_ID_LETTER = {letters};

export function isValidRocId(token) {{
  token = normalize(token).toUpperCase();
  if (!/^[A-Z]\d{{9}}$/.test(token)) return false;
  const letter = ROC_ID_LETTER[token[0]];
  const digits = [Math.floor(letter / 10), letter % 10,
                  ...token.slice(1).split('').map(Number)];
  const weights = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1];
  return digits.reduce((s, d, i) => s + d * weights[i], 0) % 10 === 0;
}}

// Mirrors chart_scrub.rules.classify_number(). The strings must stay
// byte-identical to the Python ones — the parity test compares them.
export function classifyNumber(token) {{
  if (isValidRocId(token)) return "確定身分證號（檢查碼有效）";
  if (/^[A-Za-z]\d{{9}}$/.test(token)) return "疑似身分證號（檢查碼無效）";
  if (/^[A-Za-z]{{2}}\d{{8}}$/.test(token)) return "疑似舊式居留證號";
  if (/^09\d{{8}}$/.test(token)) return "疑似手機號碼";
  if (/^(?:19|20)\d{{6}}$/.test(token)) {{
    const m = +token.slice(4, 6), d = +token.slice(6, 8);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31)
      return "疑似日期 YYYYMMDD（若為生日應遮蔽）";
  }}
  if (/^\d{{7,8}}$/.test(token)) return "7-8位數（各院病歷號常見長度）";
  return "未分類數字串";
}}

// Mirrors chart_scrub.rules.audit_numbers(): run on MASKED output, returns
// [token, count, guess] for every number-shaped survivor, most frequent
// first. Whatever comes back is what the rules did NOT recognise.
const AUDIT_RUN = /(?<![A-Za-z0-9])[A-Za-z]{{0,2}}\d{{5,}}(?![A-Za-z0-9])/g;

export function auditNumbers(text) {{
  const counts = new Map();
  for (const m of text.matchAll(AUDIT_RUN))
    counts.set(m[0], (counts.get(m[0]) || 0) + 1);
  return [...counts.entries()]
    .map(([token, n]) => [token, n, classifyNumber(token)])
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
}}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated file is out of date")
    args = ap.parse_args()

    new = render()
    path = os.path.normpath(OUT)
    if args.check:
        if not os.path.exists(path):
            print(f"{path} is missing — run python tools/export_rules_js.py")
            return 1
        with open(path, encoding="utf-8") as f:
            current = f.read()
        if current != new:
            print(f"{path} is out of date — run python tools/export_rules_js.py")
            return 1
        print(f"{path} is up to date")
        return 0

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"wrote {path} ({len(RULES)} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
