# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-08-14

Findings from an external design review (Codex, gpt-5.6-luna) plus our own
pass, adjudicated and fixed together.

### Added

- **`is_valid_roc_id()` — the national ID checksum, as a classifier.** It
  tells a genuine 身分證 apart from a chart number that shares the shape, and
  the residue check uses it to grade a surviving ID-shaped token as a certain
  leak versus a suspect. **It never gates masking**: a mistyped real ID fails
  the checksum, and a masking pass that trusted it would leak exactly that ID.
  身分證檢查碼驗證，只做分類；遮罩從不依賴它。
- **Per-rule opt-out.** `--skip rule,rule` on `mask`/`ingest`, checkboxes on
  the demo page, `skip=` in the library. You know which identifiers exist in
  your world; the tool doesn't.
  每條規則可個別停用（CLI `--skip`、demo 勾選框、library `skip=`）。
- **New rules**: old-style resident certificate numbers (two letters + eight
  digits), labelled passport numbers, and NHI card numbers with the label
  *before* the number (`健保卡號：…` — previously only `… 健保卡` matched).
  新規則：舊式居留證號、護照號（帶標籤）、標籤在前的健保卡號。
- **Exit code 3**: masking ran but a record carried no recognisable identity.
  Generic rules still applied; nothing patient-specific was substituted.
  離開碼 3＝有紀錄找不到身分，通用規則有跑但沒做代號抽換。

### Fixed

- **Partial masks on overlong numbers.** A labelled 11-digit number was
  masked ten digits deep with the tail left in the open. Digit runs are now
  unbounded — a labelled number is eaten whole.
  帶標籤的超長號碼不再只遮前十碼。
- **Lower-case IDs leaked.** `a123456789` never matched; ID rules and the
  residue check now accept both cases.
  小寫身分證從頭到尾抓不到，已修。
- **`出生日期：`/`出生年月日：` labels never matched** in either the rule
  engine or the pipeline's birth parser.
  「出生日期」「出生年月日」標籤兩層都吃得到了。
- **Lane/alley addresses masked only up to the first segment** —
  `和平東路100巷5號` left `5號` in the open. Up to three segments now.
  巷弄多層地址不再遮一半。
- **Alias numbers could collide or be re-used.** `COUNT(*)+1` numbering let
  two processes collide and let a deleted row's number be re-issued to the
  next patient. A monotonic counter table (seeded from existing databases)
  now hands out each number exactly once, under a write lock.
  代號編號改用單調遞增計數表，不重號、不因刪除而重用。
- The residue check now also watches for lower-case and old-ARC-shaped
  tokens, and `first_seen`/`last_seen` are actually maintained.
  殘留檢查涵蓋小寫與舊式居留證形狀；first_seen/last_seen 開始維護。

## [0.2.0] — 2026-08-14

### Changed

- **Project renamed from `clinic-deid` to `chart-scrub`.** Repository, Python
  package (`clinic_deid` → `chart_scrub`), CLI name, default database
  directory (`~/.clinic-deid` → `~/.chart-scrub`) and the demo page URL all
  follow. GitHub redirects the old repository URL, but the old GitHub Pages
  demo URL does not redirect.
  專案改名：repo、Python 套件、CLI、預設資料庫目錄與 demo 網址全部跟著換；
  舊 repo 網址會自動轉址，舊 demo 網址不會。

### Fixed

- **Demo page: the highlighted sample button now follows your click.** The
  green highlight was hard-coded to the first sample; loading the second
  sample never moved it. Hand-editing the input clears the highlight.
  Demo 頁「載入範例」按鈕的選取顏色現在會跟著點擊移動；手動編輯輸入框會清除選取狀態。

## [0.1.0] — 2026-08-14

First public release. Extracted from a private clinic workflow, generalised,
tested, and documented.

### Added

- **Masking engine** (`chart_scrub/rules.py`): 16 regex rules covering chart
  numbers, ROC national IDs and resident certificate numbers, NHI card
  numbers, mobile and landline numbers, email addresses, dates of birth in
  both ROC and Gregorian form, addresses, and names carrying a title, a role
  word, a family relation word or an explicit declaration. Addresses accept
  the pre-2010 county names as well as the current 22.
- **Pseudonymisation pipeline** (`chart_scrub/pseudonymize.py`): stable
  `PT-NNNN` aliases per patient, date of birth converted to age, aliases for
  other patients mentioned in passing, multi-patient splitting on three
  layers (separator lines, chart-number lines, ID+name shorthand), and a
  residue check that fails the record rather than emitting it.
- **Local alias store** (`chart_scrub/store.py`): SQLite, git-ignored.
- **CLI** (`chart-scrub`): `mask`, `ingest`, `verify`, `who`, `list`.
  Exit code 2 on a failed residue check.
- **Browser demo** (`docs/`): a static page that runs the masking engine
  client-side. Its rule table is generated from the Python one by
  `tools/export_rules_js.py`, and `--check` fails CI when the two drift.
- **87 tests**, including a Python↔JavaScript parity test over 24 inputs and
  a substantial set of negative tests (medical eponyms, bare surnames,
  measurements, punctuation must all survive).
- **CI**: pytest on Ubuntu and Windows × Python 3.10 and 3.12, rule-table
  drift check, gitleaks over full history, and a guard that fails the build if
  a database or a `.deid.txt` file is ever committed.

### Documented, not fixed

- **Uniqueness is out of scope and says so.** A role only one person holds, or
  an event that made the news, identifies someone with every identifier
  removed. No rule can see that a description points at exactly one person, so
  the README, the browser demo and the launch post all state it plainly
  instead of implying the tool covers it.

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
- Targeted substitution replaced a chart number as a plain string, with no
  token boundary. Chart number `1234567` is a substring of a companion's
  national ID `A123456789`, so the ID was rewritten into `APT-000189`: mangled
  instead of masked, and no longer ID-shaped, which also blinded the residue
  check that watches for surviving IDs. The same collision can cut a phone
  number in half and stop the phone rule matching the remainder.
- The rule engine and the pipeline were coupled through a hard-coded
  `sys.path` insert into another project's directory.
