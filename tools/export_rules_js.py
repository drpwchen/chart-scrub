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

from chart_scrub.rules import RULES  # noqa: E402

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
    return f"""{HEADER}
export const RULES = [
{body}
];

// Mirrors chart_scrub.rules.normalize(): full-width digits and Latin letters
// fold to half-width, punctuation is left alone.
export function normalize(text) {{
  return text.replace(/[０-９Ａ-Ｚａ-ｚ]/g,
    c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
}}

// Mirrors chart_scrub.rules.deidentify_verbose().
export function deidentify(text, {{ normalize: doNormalize = true }} = {{}}) {{
  if (doNormalize) text = normalize(text);
  const hits = {{}};
  for (const rule of RULES) {{
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
