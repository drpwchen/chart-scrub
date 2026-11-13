# AGENTS.md — notes for AI coding agents

chart-scrub is a local de-identification tool for Taiwanese medical charts:
a stateless masking engine (`chart_scrub/rules.py`) plus a pseudonymisation
pipeline with a reversible alias store (`chart_scrub/pseudonymize.py`,
`chart_scrub/store.py`). README.md (and README.zh-TW.md) is the user manual
and the legal reasoning; this file is what an agent must know before changing
the code or running it on someone's data.

## Hard rules

- **Never run the tool on real patient data inside an AI assistant session.**
  Its whole point is that records stay on the user's machine. `chart-scrub
  who` and `rehydrate()` print real names — they are for the user's own
  terminal only. If a user pastes a real record into the chat, say so and
  stop; do not "help" by masking it in the conversation.
- **A masking pass that misses a format fails silently.** Never report a
  record as "clean" from the exit code alone; the residue check only knows the
  shapes in the rule table and the aliases in the store. The verify-before-
  real-data ladder in README (`## Before you feed it real data`) is the
  procedure — torture sample → `mask --audit` → read every line → a handful of
  real records → scale.
- **`is_valid_roc_id()` classifies, it never gates masking.** A mistyped real
  ID fails the checksum; a rule that trusted the checksum would leak exactly
  that ID. Keep the checksum in the residue grader and out of the matchers.
- **Order in the pipeline is load-bearing**: targeted person substitution runs
  before the generic rules (otherwise the name is already `[姓名]` and no alias
  can attach), and the whole-input pre-registration pass runs before any
  per-record work. The test suite is mutation-verified against reverting these;
  do not "simplify" them away.
- **Tests that assert something is NOT masked are as important as the
  positive ones** (about a third of the suite). An engine that masks everything
  passes every positive test and is useless. New rules need a negative case.
- **`RULES` in `rules.py` is the only place a pattern is written.** The
  browser demo's `docs/rules.generated.js` is generated:
  `python tools/export_rules_js.py` after any rule change, `--check` in CI
  and `tests/test_js_parity.py` (needs `node`) fail on drift. Two engine
  differences are handled in the exporter (`\1`→`$1`, `g` flag) and one by
  normalisation (full-width digits/Latin folded to half-width on both sides).
- `*.db` and `*.deid.txt` stay in `.gitignore`. The alias database is the one
  file that undoes everything; never commit, print or upload one, including
  fixture databases built from anything but invented data.
- Legal citations in the READMEs are exact article numbers checked against the
  statute text (0.6.3 was a documentation-only release to fix a mis-cited
  section). **Re-read the article before writing a section number**; never
  paraphrase a provision from memory.
- Public repo: every change ships as CHANGELOG entry + version bump in
  `pyproject.toml` + tag + GitHub Release. Keep README.md and README.zh-TW.md
  in step — they are translations, not two documents.

## Layout

- `chart_scrub/cli.py` — `mask`, `ingest`, `check`, `list`, `who`, `rehydrate`;
  exit codes `2` = residue found, `3` = no recognisable identity.
- `chart_scrub/rules.py` — 23 bilingual label-driven rules; `--skip` and
  `--rules` (user shapes run before the built-in table).
- `chart_scrub/pseudonymize.py` — resolve subject → alias → DOB→age → other
  patients → masking net → residue check → refuse on survivors; `rehydrate()`.
- `chart_scrub/store.py` — `AliasStore` (SQLite).
- `docs/` — static browser demo, no build step, no dependencies (plus prose: `legal-taiwan*.md`, `other-routes*.md`).
- `examples/litellm_callback.py` — outbound/inbound hook example
  (`tests/test_example_litellm.py` covers it).
- `tools/export_rules_js.py`, `tools/js_deid_runner.mjs` — JS parity.

## Tests

```bash
pip install -e ".[dev]"
pytest                                   # 87 tests; JS parity skips without node
python tools/export_rules_js.py --check  # demo rule table in sync
```

Before a release also open `docs/index.html` once and run the demo's sample
through it — the parity test covers the rule table, not the page wiring.

## Maintainer notes (the author's own setup — other users can ignore)

- Release: `python ~/.claude/scripts/gh_release.py ship <repo> <version>`
  (CHANGELOG section must exist first). The repo is in the monthly OSS release
  digest (`oss_release_digest.py`).
- Torture samples for the author's own hospital formats are not in this repo
  and must never be added to it.
