# chart-scrub

[![CI](https://github.com/drpwchen/chart-scrub/actions/workflows/ci.yml/badge.svg)](https://github.com/drpwchen/chart-scrub/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

De-identify Traditional Chinese (Taiwan) clinical text on your own machine,
before any of it reaches a cloud model.

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

**1. A masking engine** (`chart_scrub/rules.py`) — 19 regex rules for chart
numbers, national IDs, old-style resident certificate numbers, NHI card
numbers, passports, phone numbers, email, dates of birth, addresses and
names. No state, no database, no network. This is what the browser demo runs.
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

- **Names without a cue are missed.** `小明今天回診` has no title, no role word
  and no self-introduction, so nothing fires. Names are caught when they carry
  a title (`陳先生`), follow a role word (`病人陳小明`) or a family relation
  (`我太太林美玉`), are declared (`我叫…`), or sit next to a national ID.
- **The surname list holds about 100 surnames.** A rare surname is not
  recognised as a name at all.
- **Regex only.** No NER model, no dictionary of real names, nothing that
  learns. It cannot reason about context.
- **It over-masks on purpose.** A medical term occasionally gets masked. That
  trade is deliberate: masking one word too many costs you a re-read, leaking
  one name costs a great deal more.
- **Visit dates are kept.** Clinical reasoning usually needs them. If you need
  HIPAA safe-harbor date handling, you have to add date shifting yourself.
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

**So fork it and make it yours.** The parts most likely to need editing:

| What | Where |
| --- | --- |
| Add or change a masking rule | `RULES` in `chart_scrub/rules.py` |
| Recognise your record header format | `MRN_HEAD`, `NAME_LABEL` in `chart_scrub/pseudonymize.py` |
| Change how records are split apart | `split_records()` |
| Change the alias format | `AliasStore(prefix=...)` |
| Add a check before output is trusted | `residue_check()` |

If you build something better, I would genuinely like to hear about it —
open an issue.

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
