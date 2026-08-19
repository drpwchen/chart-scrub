# chart-scrub

[![CI](https://github.com/drpwchen/chart-scrub/actions/workflows/ci.yml/badge.svg)](https://github.com/drpwchen/chart-scrub/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

De-identify Traditional Chinese (Taiwan) clinical text on your own machine,
before any of it reaches a cloud model.

**This is a worked example, not a product.** The rules grew out of one
clinic's paste format — mine. Treat the repo as a template: audit it against
*your* data format, adjust the rules to what your hospital actually prints
(see [Every hospital's data looks different](#every-hospitals-data-looks-different)),
and [verify it masks before you feed it anything real](#before-you-feed-it-real-data).
Using it also does not settle the [legal side](#the-legal-side-taiwan) —
masking is a technical step, compliance is a separate question.

**[Try the rule engine in your browser →](https://drpwchen.github.io/chart-scrub/)**
Nothing is uploaded; the page runs entirely client-side.

繁體中文版說明 → [README.zh-TW.md](README.zh-TW.md)

---

## What it does

```
病歷號碼：1234567 姓名：王大明 出生：1971/03/05
主訴：右肩痛三個月，夜間痛醒。王大明表示上個月在李阿嬤介紹的推拿館推過。
電話 0912-345-678，住新北市板橋區文化路一段100號5樓。
```

becomes

```
[代號 PT-0001，55歲]
病歷號碼：PT-0001 姓名：PT-0001 出生：[55歲]
主訴：右肩痛三個月，夜間痛醒。PT-0001表示上個月在[稱謂]介紹的推拿館推過。
電話 [電話]，住[地址]。
```

The clinical content survives. The identity does not. The same patient gets the
same `PT-0001` on their next visit, so a series of records still reads as one
person's story — and the mapping from `PT-0001` back to a real name lives only
in a local SQLite file that never leaves your machine.

## Two layers

**1. A masking engine** (`chart_scrub/rules.py`) — 23 regex rules for chart
numbers, national IDs, old-style resident certificate numbers, NHI card
numbers, passports, phone numbers, email, dates of birth, addresses and
names. Taiwanese charts are written in English prose with identifiers pasted
in from the HIS, so the label-driven rules are bilingual: `病歷號` and
`Chart No:`/`MRN`, `生日` and `DOB:`, `姓名` and `Name: WANG, TA-MING` all
count. No state, no database, no network. This is what the browser demo runs.
Every rule can be switched off (`--skip rule,rule` on the CLI, checkboxes in
the demo) — you know which identifiers exist in your world, the tool doesn't.

The engine also ships `is_valid_roc_id()`, the national ID checksum.
**It classifies, it never gates masking**: a real ID with one digit mistyped
fails the checksum, and a masking pass that trusted the checksum would wave
exactly that ID through. Use it to tell a genuine national ID apart from a
chart number that shares the shape; the residue check uses it to grade a
surviving ID-shaped token as a certain leak versus a suspected one.

**2. A pseudonymisation pipeline** (`chart_scrub/pseudonymize.py`) — resolves
who the record is about, swaps that person for a stable alias, turns the date
of birth into an age, gives every other patient mentioned in passing their own
alias, then runs the masking engine as a net underneath. Finally it greps its
own output for every identifier it knows about and **refuses to pass** if
anything survived.

Order matters: the targeted substitution has to run before the generic rules,
or the name is already `[姓名]` and no alias can be attached to it.

The pipeline also runs backwards. `rehydrate()` turns aliases in a piece of
text back into the names they stand for, so a de-identified note can go out to
a model and the answer can come back readable. Only aliases return: a date of
birth became an age, and an age has no way home. See
[Sending text to a model](#sending-text-to-a-model).

## Install

```bash
git clone https://github.com/drpwchen/chart-scrub
cd chart-scrub
pip install -e .
```

No dependencies outside the standard library.

## Use

```bash
# Rules only. No database is created, nothing is stored.
chart-scrub mask notes.txt
echo "病人陳小明，電話 0912-345-678" | chart-scrub mask -

# Full pipeline. Writes PT-0001_<timestamp>.deid.txt next to the input.
chart-scrub ingest today.txt

# Several patients in one paste — split on ---, on chart-number lines,
# or on the ID+name shorthand.
chart-scrub ingest clinic-list.txt --json

# Re-run the residue check on files you already produced.
chart-scrub verify *.deid.txt

# Aliases and ages only. Safe to show anyone.
chart-scrub list

# Re-identify. Prints a real name — run it in your own terminal,
# never through an AI assistant.
chart-scrub who PT-0001

# Turn aliases in a model's reply back into names. Prints real names,
# to stdout only — same rule, your own terminal.
pbpaste | chart-scrub rehydrate -
```

Exit code `2` means the residue check failed. **Do not use that output file.**
Exit code `3` means masking ran but at least one record carried no
recognisable identity — generic rules still applied, but nothing
patient-specific was substituted. Read that record before trusting it.

As a library:

```python
from chart_scrub import AliasStore, deidentify, ingest

deidentify("病人陳小明，電話 0912-345-678")
# '病人[姓名]，電話 [電話]'

with AliasStore("aliases.db") as store:
    for record in ingest(store, open("today.txt", encoding="utf-8").read()):
        print(record.alias, record.age, record.ok)
```

## Sending text to a model

The tool was built for text you keep. This section is about text you send: a
prompt goes to a cloud model, an answer comes back, and nothing identifiable
crosses the wire either way.

Two shapes, and the difference is worth understanding before picking one.

**Stateless.** `deidentify()` masks identifiers into markers. Nothing is
stored and nothing comes back — the model's answer talks about `[姓名]`, and so
do you. No database, no setup, no way to re-identify anything afterwards.

**Reversible.** `process_record()` swaps each patient for a stable alias, and
`rehydrate()` restores the names in the reply before you read it. The
conversation reads normally; the provider only ever saw PT-0001.

```python
from chart_scrub import AliasStore, process_record, rehydrate

with AliasStore("aliases.db") as store:
    outbound = process_record(store, note).text     # PT-0001, no name, no chart no.
    reply = call_your_model(outbound)               # provider sees only the alias
    print(rehydrate(store, reply).text)             # you read a real name
```

A runnable end-to-end example, including litellm proxy wiring, is in
[`examples/litellm_callback.py`](examples/litellm_callback.py). It runs against
a fake model, so `python examples/litellm_callback.py` works with no network
and no litellm installed.

Three things to get right:

- **The alias database re-identifies everything.** Running reversible mode
  inside a gateway puts that file wherever the gateway runs. On somebody
  else's host, the mapping has left your machine and the de-identification is
  protecting no one. Reversible mode belongs on a workstation.
- **A shared proxy needs one database per person.** Getting that wrong mixes
  patients together. The example's litellm hook is stateless only, on purpose.
- **Restoration is partial by design.** Aliases come back; ages and generic
  markers do not. The identifiers you never need back never come back.

### Other routes worth knowing about

If your problem is really "intercept every prompt leaving this machine"
rather than "de-identify a corpus I am going to keep", a DLP layer at the
gateway may fit better than a CLI. [LiteLLM](https://github.com/BerriAI/litellm)
with a guardrail plugin such as
[ceil-dlp](https://github.com/dorcha-inc/ceil-dlp) covers that shape, and
ceil-dlp's *whistledown* mode — reversible masking that restores values in the
reply, from [this paper](https://arxiv.org/abs/2511.13319) — is the idea
`rehydrate()` above borrows from. Credit where it is due.

Two differences to weigh:

- **Language.** ceil-dlp's detection stack is English: spaCy `en_core_web_lg`,
  `dslim/bert-base-NER` trained on CoNLL-2003, and GLiNER
  `gliner_multi_pii-v1`, which is fine-tuned on English, French, German,
  Spanish, Italian and Portuguese. Chinese is not among them, and none of the
  three knows a Taiwanese chart number, NHI card number or national ID
  checksum. chart-scrub exists because that gap is the whole job here.
- **Model versus rule.** An NER ensemble generalises to phrasings a regex
  never anticipated, and misses in ways you cannot enumerate or test. Rules do
  the opposite: they miss what nobody wrote a rule for, but the same input
  always produces the same output, which is what makes a residue check and a
  test suite mean anything. For text you file and may have to defend later,
  that trade leans one way. For a prompt in flight, it may lean the other.

They are not mutually exclusive. Use whichever matches what happens to the
text afterwards.

## Known limitations

This is the part worth reading twice.

### The one no rule engine can fix: uniqueness

**Some people stay identifiable with every identifier removed**, and no
pattern can help you there. Two shapes of it:

- **A role only one person holds.** A title that belongs to exactly one human
  in the country identifies them completely. To the engine it is an ordinary
  noun, indistinguishable from "the patient" or "a teacher".
- **The event does the identifying.** After a disaster or a case that made the
  news, a line like "hit by a parapet during the typhoon" names somebody
  precisely while containing no name at all.

What makes these re-identifiable is not a string, it is that **the description
points at exactly one person** — and pattern matching cannot see that. Only
you can, because only you know how rare the story is. If a colleague would
recognise the case from the description alone, then de-identifying it is a
decision about what to write down, not a processing step you can delegate.

### The ordinary ones

- **Some names still need a cue.** A standalone surname-led CJK token is
  masked on its own (`Patient 王大明 presented…` — in an English chart that
  is what a pasted name looks like), and the `NOT_NAMES` stoplist excuses
  clinical words typed in Chinese (`c/o 高血壓`) — grow that list in
  `rules.py` as you meet new ones. What still needs a cue: a given name on
  its own (`小明今天回診` — 小 is not a surname), a rare surname, and a full
  name buried inside continuous Chinese prose with no title, role word,
  declaration, or identifier next to it.
- **The surname list holds about 100 surnames.** A rare surname is not
  recognised as a name at all.
- **Regex only.** No NER model, no dictionary of real names, nothing that
  learns. It cannot reason about context.
- **It over-masks on purpose.** A medical term occasionally gets masked. That
  trade is deliberate: masking one word too many costs you a re-read, leaking
  one name costs a great deal more.
- **All full dates are masked, visit dates included.** A pasted date of birth
  arrives bare, and no rule can tell it from an operation date by shape, so
  since v0.6.0 every full date becomes `[日期]` (the HIPAA safe-harbor trade).
  If your workflow needs the timeline, run with `--skip bare_date` — labelled
  and ROC-calendar birthdays are still caught by their own rules.
- **The residue check only knows what the store knows.** It catches names and
  chart numbers already on record, plus two shapes of leak (a Chinese name
  glued to a masked ID, an ID-shaped token that survived). A name it has never
  seen, in a form no rule matches, passes silently.
- **A given name that is also an ordinary word gets substituted everywhere.**
  The pipeline replaces the patient's given name on its own (王建國 → 建國), so
  a street called 建國路 comes out as `PT-0001路`. That is over-masking, not a
  leak — the safe direction — but expect the occasional mangled word.
- **Tuned to one clinic's paste format.** Mine. See below.

Use it as the first net, not as a guarantee. A human still reads the output
before it goes anywhere.

## Every hospital's data looks different

The record layouts here — where the chart number sits, whether birthdays are
written in ROC or Gregorian form, whether you paste one patient or twelve —
came out of my own outpatient workflow. Yours will differ.

**Since v0.5.0 you don't have to fork for this.** Most identifiers in a real
chart carry no label at all — a bare 8-digit run that *your* hospital always
uses as the chart number looks like any other number to a generic rule table.
The working loop:

```bash
# 1. Mask, and list every number-shaped token that survived,
#    with a guess at what each one is (ID checksum? phone shape?
#    7-8 digits, the common chart-number length?).
chart-scrub mask note.txt --audit

# 2. Whatever shape is an identifier in YOUR format, write it down:
cat > my-hospital.json <<'EOF'
[
  {
    "name": "my_mrn",
    "pattern": "(?<![A-Za-z0-9])\\d{8}(?!\\d)",
    "replacement": "[病歷號]",
    "description": "our charts: bare 8 digits"
  }
]
EOF

# 3. Mask again with your rules — they run before the built-in table.
chart-scrub mask note.txt --rules my-hospital.json --audit
```

Repeat until the audit comes back clean or everything left is genuinely not
an identifier. `ingest` takes `--rules` too, so the same file covers the full
pipeline. The [browser demo](https://drpwchen.github.io/chart-scrub/) runs
the same loop client-side: an audit panel under the output, and a custom-rules
box that takes the same JSON as `--rules`.

**For deeper changes, fork it and make it yours.** The parts most likely to
need editing:

| What | Where |
| --- | --- |
| Add or change a masking rule | `RULES` in `chart_scrub/rules.py` |
| Recognise your record header format | `MRN_HEAD`, `NAME_LABEL` in `chart_scrub/pseudonymize.py` |
| Change how records are split apart | `split_records()` |
| Change the alias format | `AliasStore(prefix=...)` |
| Add a check before output is trusted | `residue_check()` |

If you build something better, I would genuinely like to hear about it —
open an issue.

## Before you feed it real data

Do not start by dumping a folder of records into `ingest`. A masking pass
that misses your hospital's formats fails **silently** — the output looks
clean, prints statistics, and still carries identifiers no rule matched.
Earn trust in this order:

1. **Write a torture sample.** One fake record in exactly your hospital's
   format — the real header layout, your chart-number shape, a name, an ID,
   a birthday, a phone number, an address — with every identifier invented.
   Ten minutes of typing, zero risk.
2. **Mask it and read every line.** `chart-scrub mask sample.txt --audit`.
   Anything that survived and shouldn't have → write the shape into your
   `--rules` file, or fix the rule, and run again until the audit is clean.
3. **Then a handful of real records, still reading every line yourself.**
   The residue check and exit codes (`2` = residue found, `3` = record had
   no recognisable identity) are guard rails, not a replacement for your
   eyes — they only catch what the store or the shape rules know about.
4. **Only then scale up** — and keep spot-reading. A new admission form, a
   new HIS version, a colleague's different paste habit each reintroduce
   step 1.

The uniqueness problem from [Known limitations](#known-limitations) never
goes away at any step: a story only one patient can own re-identifies them
with every string masked, and only the person who knows the story can see it.

## The legal side (Taiwan)

Masking is a technical step. Whether you may collect the text, keep it, or
send it anywhere is a legal question that this tool does not answer — and in
Taiwan the bar is **not** the HIPAA checklist. Points worth knowing before
you build a workflow on this (sources verified against the current versions
on law.moj.gov.tw, 2026-08; not legal advice):

- **What this tool produces is pseudonymised, not anonymised.** The alias
  table is a feature — PT-0001 stays PT-0001 across visits, which is what
  makes "same patient, three months later" readable — and it is also the key
  that turns the output back into a named record. The Constitutional Court
  drew the line on restorability, not on field count: processed data stays
  personal data 「客觀上仍有還原而間接識別當事人之可能時」, and loses that
  character only 「於客觀上無還原識別個人之可能時」 (111 年憲判字第 13 號,
  reasons ¶35–36). So while you hold the table, the masked text is still
  personal data in your hands and 個資法 still applies to it. Masking lowers
  the risk; it does not move the data outside the statute.
- **Taiwan has no 18-item safe harbor.** The de-identification standard is
  個人資料保護法施行細則 §17 — an *outcome* standard (「無從辨識該特定個人」),
  not a checklist. Deleting all eighteen HIPAA fields does not finish the job
  here; a rare diagnosis + procedure + month + hospital can re-identify with
  every listed field gone.
- **Medical records are special-category data.** 個資法 §6 prohibits
  collecting, processing and using them in principle; the exceptions must be
  affirmatively met. The moment "using a record for care" becomes "keeping a
  pile of records as a dataset", you are in 蒐集 territory and need an
  answer to which exception applies.
- **Do not batch-pull records to feed this tool.** 醫療法 §72 forbids
  disclosing what you learn in practice without cause, and §103 puts the
  NT$50,000–250,000 fine on the individual as well as the institution.
  Hospitals must log every access and copy (醫療機構電子病歷製作及管理辦法
  §13); at hospitals of 100 beds or more, 醫院個人資料檔案安全維護計畫實施辦法
  requires custody and confidentiality undertakings from staff (§11(3)),
  requires documents held for work to be handed over — not carried off —
  when they leave (§11(4)), and keeps usage and trail logs for at least six
  months (§15). Obtaining records beyond your care relationship can reach
  刑法 §359. Same keystrokes,
  different scope: your own patient for care is authorised; accumulating
  beyond that is not, even on your own account.
- **De-identification is not a free pass outward.** The Constitutional Court
  (111 年憲判字第 13 號, the NHI database case) accepted de-identification
  only *together with* purpose limits and oversight. For institutions, cloud
  storage of electronic records must sit inside Taiwan unless the ministry
  approves otherwise (電子病歷辦法 §8) — that binds the hospital rather than
  you personally, but it tells you where the regulator stands. The MOHW
  generative-AI guideline for medical institutions (衛部醫字第 1151663164 號,
  2026-05-29) treats using real patient data in clinical workflow as
  *deployment* that should go through the institution's process, not personal
  testing; it is administrative guidance (行政指導), not a binding rule, and
  says so itself. The sensible ladder: local model first, in-hospital
  deployment second, external commercial models last and only after checking
  your hospital's own policy.

Two things are moving, so re-check before relying on this section: the
2025-11-11 amendment to 個資法 adds an administrative-oversight chapter,
rewrites §21 on international transfer and deletes §27 — the provision that
醫院個人資料檔案安全維護計畫實施辦法 is issued under — and none of it is in
force yet (the Executive Yuan has not set a date).

Sources: [個資法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0050021) ·
[施行細則](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0050022) ·
[電子病歷辦法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0020121) ·
[醫院個資安全維護辦法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0020218) ·
[醫療法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0020021) ·
[刑法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=C0000001) ·
[憲判字 111-13](https://cons.judicial.gov.tw/docdata.aspx?fid=38&id=309956) ·
[衛福部生成式 AI 指引](https://www.mohw.gov.tw/cp-18-86695-1.html)

## The browser demo

`docs/` is a single static page with no build step and no dependencies. Its
rule table is **generated from the Python one**:

```bash
python tools/export_rules_js.py           # regenerate
python tools/export_rules_js.py --check   # fail if out of date (CI runs this)
```

A test feeds the same 24 inputs to both engines and asserts identical output,
so the demo cannot quietly drift away from the library.

Two engine differences are handled explicitly: Python's `\d` matches full-width
digits and JavaScript's does not (both sides fold full-width digits and Latin
letters to half-width first), and Python's `\1` backreferences become `$1`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

87 tests. Roughly a third of them assert that something is **not** masked —
an engine that masks everything would pass every positive test and be useless.

The suite has been mutation-verified: reverting each of the load-bearing
decisions (the whole-input pre-registration pass, the surname anchor on the
ID+name pattern, the token boundary on identifier substitution, the
cross-record alias substitution, the address lead-in guard, the encoding BOM
check) makes it fail.

## Safety notes

- `*.db` and `*.deid.txt` are in `.gitignore`. Keep them there.
- The alias database is the one file that can undo all of this. Treat it the
  way you treat the source records.
- `chart-scrub who` prints a real name. That is its whole job. Do not run it
  through an assistant, and do not paste its output anywhere.
- `ingest` prints statistics and aliases only — never record content — so the
  terminal output is safe to share when you need help debugging.

## License

MIT. See [LICENSE](LICENSE).

This software is provided as-is and is **not** a compliance product. Whether
its output satisfies your institution's rules, your IRB, or the Personal Data
Protection Act is your determination to make, not mine.
