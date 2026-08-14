# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-08-14

First public release. Extracted from a private clinic workflow, generalised,
tested, and documented.

### Added

- **Masking engine** (`clinic_deid/rules.py`): 15 regex rules covering chart
  numbers, ROC national IDs and resident certificate numbers, NHI card
  numbers, mobile and landline numbers, email addresses, dates of birth in
  both ROC and Gregorian form, addresses, and names carrying a title, a role
  word or an explicit declaration.
- **Pseudonymisation pipeline** (`clinic_deid/pseudonymize.py`): stable
  `PT-NNNN` aliases per patient, date of birth converted to age, aliases for
  other patients mentioned in passing, multi-patient splitting on three
  layers (separator lines, chart-number lines, ID+name shorthand), and a
  residue check that fails the record rather than emitting it.
- **Local alias store** (`clinic_deid/store.py`): SQLite, git-ignored.
- **CLI** (`clinic-deid`): `mask`, `ingest`, `verify`, `who`, `list`.
  Exit code 2 on a failed residue check.
- **Browser demo** (`docs/`): a static page that runs the masking engine
  client-side. Its rule table is generated from the Python one by
  `tools/export_rules_js.py`, and `--check` fails CI when the two drift.
- **80 tests**, including a Python↔JavaScript parity test over 22 inputs and
  a substantial set of negative tests (medical eponyms, bare surnames,
  measurements, punctuation must all survive).
- **CI**: pytest on Ubuntu and Windows × Python 3.10 and 3.12, rule-table
  drift check, gitleaks over full history, and a guard that fails the build if
  a database or a `.deid.txt` file is ever committed.

### Fixed relative to the private original

- `ID_NAME` accepted any 2–4 CJK characters next to a national ID, so
  `陪同者 A123456789 李小華` registered **陪同者** as the patient's name and let
  the real name through untouched. The name side is now anchored on a known
  surname.
- Encoding detection tried UTF-16 on files with no byte order mark. A Big5
  file decoded as UTF-16 without raising, produced mojibake, matched no rule,
  and the pipeline reported success having de-identified nothing. UTF-16 is
  now only attempted when a BOM is present.
- The address rule matched "any 1–4 CJK characters + 縣/市", which swallowed
  the character before the address (`住新北市…` matched `住新北` + `市`). It now
  uses the explicit list of 22 counties and cities, plus a separate rule for
  street addresses written without a county — that one requires a house
  number, so `沿著中山路走` survives.
- Full-width normalisation used NFKC, which also rewrote Chinese full-width
  punctuation into ASCII. Only digits and Latin letters are folded now.
- The rule engine and the pipeline were coupled through a hard-coded
  `sys.path` insert into another project's directory.
