# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.6.3] — 2026-08-20

Documentation only. Corrects a mis-cited provision introduced in 0.6.2.

### Fixed

- **醫院個人資料檔案安全維護計畫實施辦法 was cited as §8 for a rule it does
  not contain.** 0.6.2 stated that §8 bars staff from taking work documents
  off-site. It does not: §8 governs the hospital's own collection scope and
  transmission ("醫院於傳輸個人資料時，應採取必要保護措施；國際傳輸電子病歷時，
  並應符合醫療機構電子病歷製作及管理辦法之規定"). The "不得攜離使用" wording
  lives in §11(4) and is bound to **handover on leaving employment**, not to
  a general prohibition during employment; §11(3) covers the in-service duty
  as custody and confidentiality undertakings. Both READMEs now cite §11(3),
  §11(4) and §15, and no longer describe the rule as a blanket ban on taking
  documents off-site. Re-checked against law.moj.gov.tw current text
  (111-09-23).

## [0.6.2] — 2026-08-17

Documentation only. A second pass over the legal section after independent
re-checking against primary sources; one of the additions changes how the
tool's own output should be described.

### Changed

- **The legal section now leads with pseudonymisation vs anonymisation.**
  The alias table is what makes cross-visit reading work, and it is also the
  key that restores identity — so under 111 年憲判字第 13 號 (reasons ¶35–36,
  personal data 「客觀上仍有還原而間接識別當事人之可能時」) the masked output
  is still personal data while you hold the table, and 個資法 still applies.
  Previously the section only covered re-identification *risk*; this is about
  the data's legal character, which is a different and more basic point.
  新增「這個工具做出來的是假名化，不是匿名化」：只要對照表在你手上，
  遮罩後的文字仍是個人資料，個資法照樣適用。
- **醫療法 §72／§103 now cited in the text**, not just linked — the duty not
  to disclose without cause, and the NT$50,000–250,000 fine that falls on the
  individual as well as the institution.
- **New source: 醫院個人資料檔案安全維護計畫實施辦法 (L0020218, 111-09-23).**
  At hospitals of 100 beds or more, staff may not take work documents
  off-site (§8) and usage/trail logs are kept at least six months (§15) —
  closer to the actual act of copying records than anything cited before.
  新增醫院個資安全維護辦法：一百床以上醫院，員工不得攜離工作文件資料。
- **電子病歷辦法 §8 added** to the outward-transfer bullet: cloud storage of
  electronic records must sit inside Taiwan absent ministry approval. It
  binds the institution, not the individual, but it is the one written
  data-localisation rule and the bullet previously rested only on a judgment
  and a non-binding guideline.
- **The MOHW generative-AI guideline is now labelled administrative guidance
  (行政指導), not a binding rule**, as the guideline itself states. Overstating
  its force is as inaccurate as understating it.
- **New closing note on pending changes**: the 2025-11-11 個資法 amendment adds
  an oversight chapter, rewrites §21 on international transfer and deletes
  §27 — the authorising provision for L0020218 — and none of it is in force
  yet. Readers should re-check before relying on the section.
  新增「正在變動」提示：個資法 2025-11-11 修正尚未施行，且刪除的第 27 條
  正是醫院個資辦法的授權依據。

## [0.6.1] — 2026-08-17

Documentation only — but the kind that decides whether the tool gets used
safely. No code changed.

### Changed

- **The README now says out loud that this is a worked example, not a
  product.** The intro tells you to treat the repo as a template: audit it
  against your own hospital's format, adjust the rules, and verify before
  trusting.
  README 開頭明說：這是範例實作，請當模板照自己醫院的格式調整。
- **New section: "Before you feed it real data".** Do not start by dumping a
  folder into `ingest` — a masking pass that misses your formats fails
  silently. The section walks the trust ladder: a fake torture sample in
  your exact format first, audit until clean, then a handful of real records
  read line by line, and only then scale — re-verifying whenever a form or
  HIS version changes.
  新增「餵真資料之前先做這些事」：先用假資料驗證遮得住，逐行讀過才放量。
- **New section: "The legal side (Taiwan)".** Masking is a technical step;
  compliance is a separate question, and Taiwan's bar is not the HIPAA
  checklist. Covers the outcome standard (個資法施行細則 §17), medical
  records as special-category data (個資法 §6), why batch-pulling records
  is off the table (電子病歷辦法 §13 audit trails, 刑法 §359), and why
  de-identification alone does not license sending data outward
  (憲判字 111-13, MOHW generative-AI guideline 2026-05) — with the local
  model → in-hospital → external-commercial-last ladder. All sources
  link to law.moj.gov.tw current versions. Not legal advice.
  新增「法律面（台灣）」：結果標準而非清單標準、特種個資、不可批次抓病歷、
  去識別化不是外送免死金牌；出處全連全國法規資料庫現行版本。

## [0.6.0] — 2026-08-17

Labels turned out to be the wrong assumption. Real pastes are SOAP notes:
English prose, identifiers dropped in bare — the national ID just written
out, the name just sitting there, the birthday with nothing in front of it.
This release masks by shape and context instead of waiting for a label.
(Bare national IDs were always shape-matched; what follows closes the name
and date gaps.)

### Added

- **`cjk_fullname` — a standalone CJK token led by a surname is a name.**
  In an English-language chart, `Patient 王大明 presented…` is what a pasted
  name looks like, and isolated CJK is rare enough that the odds favour a
  name. The `NOT_NAMES` stoplist excuses the words a doctor types in Chinese
  when the English term won't come (`c/o 高血壓`, `白血球`, `石膏`…) — grow
  it as you meet new ones. Inside continuous Chinese prose the CJK-boundary
  guards keep the rule silent: `病人說高血壓很久` and `陳舊性骨折` are never
  touched.
  新增：英文病歷裡孤立出現的姓氏開頭中文字串直接視為姓名；
  想不起英文而打的中文臨床詞由 `NOT_NAMES` 名單放行；連續中文句子不受影響。
- **`name_beside_id` — a bare name glued to a masked identifier.**
  `王大明 A123456789` carries no label and no title, but by the time the
  name rules run the ID is already `[身分證號]`, and a surname-led token
  touching that marker is as strong as name evidence gets. Both orders work,
  and the marker set covers ID, ARC, chart number, NHI card, passport,
  birthday, phone and date.
  新增：緊貼在已遮罩識別碼旁的裸姓名（兩個方向都認）。
- **`name_demographics` — a bare name followed by demographics.**
  `王大明 45歲`, `王大明，男 45歲`, `王大明 1971/03/05`. The date branch
  requires two numbers, so `高血壓 20年` is not a name; `男性/女性` breaks
  the sex branch for the same reason.
  新增：後面跟著年齡／性別／生日的裸姓名。
- **`bare_date` — full dates masked by shape, no label needed.**
  `1971/03/05`, `2020-05-03`, `113/05/06`, `19710305`, `1971年3月5日` all
  become `[日期]`. Visit dates go too — by shape nobody can tell a birthday
  from an operation date, so the rule takes the HIPAA safe-harbor trade;
  `--skip bare_date` keeps the timeline. Three guards protect clinical
  numerics: the year needs 2-4 digits (dosing `1-0-1`, MMT `4/5` never
  start a match), both separators must be the same character (electrolytes
  `140/4.0/100` fall apart), and the compact form validates month and day
  (an 8-digit chart number `20259999` is not a date).
  新增：完整日期照樣貌遮成 `[日期]`（含就診日期，可用 `--skip bare_date`
  保留時間軸）；劑量、MMT、電解質等臨床數字有三道防呆不會誤中。

Both READMEs and the demo's limitation list are rewritten to match; the demo
picked the four rules up automatically through the generated table.

## [0.5.0] — 2026-08-17

Taiwanese charts are written in English. The prose is English, the identity
block is pasted in from the HIS — sometimes under English labels, more often
with no label at all. Prompted by a reader asking about an English version:
the answer is not a translation, it is closing that gap. The label rules go
bilingual; the unlabelled case — the one that actually dominates a pasted
SOAP note — gets a discovery loop: audit what survived, write your hospital's
shapes into a rules file, mask again.

### Added

- **`--rules FILE` — your hospital's own shapes.** A JSON file of extra rules
  that runs **before** the built-in table, on `mask` and `ingest` and as
  `extra_rules=` in the library. No generic table can know that a bare
  8-digit run is always a chart number in *your* charts; this file is where
  you write that down. Validation is strict: a rule that fails to compile or
  a colliding name stops the run instead of being silently dropped.
  新增 `--rules`：把你們醫院自己的識別碼形狀寫成 JSON，跑在內建規則之前；
  規則寫錯會直接擋下，不會默默漏掉。
- **`mask --audit` — find out what to write down.** After masking, lists
  every number-shaped token that survived, with a shape guess: valid national
  ID checksum, ID shape with a bad checksum, old ARC shape, mobile shape,
  YYYYMMDD date, or 7-8 digits (the common chart-number length). The audit
  classifies, the human decides — its output is the input to your rules file.
  新增 `mask --audit`：列出遮完仍存活的數字串並猜形狀，猜測只供人裁決；
  audit 的輸出就是 `--rules` 檔的素材。
- **The browser demo runs the same loop.** An audit panel under the masked
  output lists surviving number shapes; a custom-rules box takes the same
  JSON as `--rules` (strictly validated, errors shown, never silently
  dropped); a third sample shows an English SOAP note. The audit/checksum/
  classification JS is generated from the Python source by
  `tools/export_rules_js.py` and held to it by the parity tests — same
  no-drift guarantee as the rule table.
  demo 頁同步：輸出下方有 audit 面板、自訂規則框吃與 `--rules` 相同的 JSON、
  新增英文 SOAP 範例；JS 端一樣由 Python 產生並受 parity 測試看守。
- **Bilingual labels.** `Chart No:` / `MRN` / `Case No.` join `病歷號`;
  `DOB:` / `date of birth` / `birthday` join `生日`; `Name: WANG, TA-MING` /
  `Name: Chen Mei-Ling` join `姓名` — in the masking rules **and** in
  `detect_identity()`, so an English-headered record builds its alias and
  age exactly like a Chinese one. "case"/"record" require an explicit
  No./number ("in case 123456 patients…" is prose); bare "birth" stays
  unanchored (birth weight, preterm birth); romanised names still need a cue,
  so McMurray and Osgood-Schlatter survive.
  標籤規則雙語化，`detect_identity()` 也認英文表頭——英文病歷一樣建代號、
  生日一樣轉年齡；醫學人名（eponym）不受影響。

### Fixed

- **Romanised names are no longer first-char-chopped.** The Chinese
  given-name trick (`name[1:]`) ran on every name; on "Wang Taming" it hunts
  for "ang Taming", which sits inside *another* person's "Tang Taming" and
  corrupts it. Romanised names now match case-insensitively with flexible
  comma/space instead ("WANG, TA-MING" in the header, "Wang Ta-Ming" in the
  prose, one alias).
  修正：羅馬拼音姓名不再套用中文的「去姓留名」邏輯，改用不分大小寫、
  逗號空格互通的比對。
- **A labelled birthday no longer swallows the line break.**
  `出生：1971/03/05\n主訴` used to become `出生[生日]主訴` — two lines glued
  together. The value class now stops at the newline.
  修正：生日規則不再吃掉換行，`主訴` 不會被黏到上一行。

## [0.4.0] — 2026-08-16

The pipeline learned to run backwards. Prompted by a reader who pointed at
LiteLLM + [ceil-dlp](https://github.com/dorcha-inc/ceil-dlp) and its
*whistledown* mode ([paper](https://arxiv.org/abs/2511.13319)) — reversible
masking that restores values in the model's reply. That idea was missing here,
and it is borrowed with credit.

### Added

- **`rehydrate()` — aliases back into names.** The reverse of the targeted
  substitution, for text that went out to a model and came back still talking
  about PT-0001. Reports what it could not restore rather than guessing:
  `unknown` for aliases this database never issued, `nameless` for aliases it
  issued but holds no name for. Only aliases return — a date of birth became
  an age, and an age has no way home.
  `rehydrate()` 把代號換回真名；還原不了的據實回報，不猜。
- **`chart-scrub rehydrate [FILE]`.** Prints to stdout and has no option to
  write a file, on purpose: the output is identifiable again and should not
  end up next to the de-identified corpus. `--with-chart` appends the chart
  number.
  新增 `rehydrate` 子命令，只印到 stdout、刻意不提供寫檔選項。
- **`AliasStore.alias_map()` and `AliasStore.prefixes()`** — the whole mapping
  and every prefix ever issued, in one query each, because re-identifying a
  body of text has to scan it exactly once.
- **`examples/litellm_callback.py`** — a runnable example of using chart-scrub
  as an interception layer in front of a language model, in both stateless and
  reversible modes, plus litellm proxy wiring. It runs against a fake model,
  so it works with no network and without litellm installed. CI runs it.
  新增 litellm 攔截層範例，可直接執行、CI 會跑。
- **README: "Sending text to a model"**, including an honest comparison with
  the LiteLLM + ceil-dlp route and when to prefer it.
  README 新增「把文字送給模型」一節，含與 ceil-dlp 路線的比較。

### Fixed

- **`__version__` was stuck at `0.1.0`** while `pyproject.toml` said `0.3.0`.
  Both now read `0.4.0`.
  套件版本號與 pyproject 不一致，已同步。

### Notes

- 18 new tests for the reverse direction, 6 for the example, 134 total.
  Six mutations were injected and all six were caught: dropping the
  case-insensitive flag, replacing the single scan with an alias-by-alias
  loop, dropping the leading token boundary, accepting any prefix shape,
  restoring a nameless alias as the string `None`, and reporting duplicate
  unknown aliases.
- A seventh mutation survived and led to a code change instead of a new test:
  a trailing `(?![0-9])` in the alias pattern was unreachable, because the
  greedy digit run already consumes every digit. It was removed rather than
  covered — a guard that can never fire reads as protection and is not.
  第七個變異存活，結論是那段防護本來就永遠為真，直接移除而不是補測試。

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
