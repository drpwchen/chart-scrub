"""The pseudonymisation pipeline: real record in, alias-bearing record out.

What this adds on top of :mod:`clinic_deid.rules`:

1. **Targeted substitution.** The patient's own name and chart number are
   replaced with a stable alias (PT-0001) rather than a generic ``[姓名]``
   marker, so the same person is recognisable across visits and pronoun-free
   sentences still refer to somebody.
2. **Date of birth becomes an age**, which is what clinical reasoning actually
   needs.
3. **Other patients mentioned in passing** get their own aliases, pulled from
   the store.
4. **The rule engine runs last**, as a net under everything the targeted pass
   did not know about.
5. **A residue check** greps the output for every identifier the store knows
   about. If anything survived, the record is reported as failed.

Ordering matters: targeted substitution has to run before the generic rules,
or the rules mask the name into ``[姓名]`` and the alias can never be attached.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from .rules import SURNAMES, deidentify, normalize
from .store import AliasStore

__all__ = [
    "RecordResult",
    "age_from_birth",
    "detect_identity",
    "split_records",
    "process_record",
    "ingest",
    "residue_check",
]

# A chart number introduced by a label. Also used as a record separator.
MRN_HEAD = re.compile(r"(?:病歷號碼?|案號)[\s:：#]*([A-Z]?\d{5,10})")

# Hand-typed clinic shorthand: a national ID (1 letter + 9 digits) sitting
# right next to a Chinese name, in either order.
#
# The name side is anchored on a known surname on purpose. Accepting any 2-4
# CJK characters looks more permissive, but it reads "陪同者 A123456789 李小華"
# as the name being 陪同者 — which registers a role word as a patient and lets
# the real name through untouched, with nothing downstream to flag it.
ID_NAME = re.compile(
    r"(?:([A-Z]\d{9})[ ,，]*([" + SURNAMES + r"][一-鿿]{1,3})"
    r"|([" + SURNAMES + r"][一-鿿]{1,3})[ ,，]*([A-Z]\d{9}))"
)

NAME_LABEL = re.compile(r"姓\s*名[\s:：]*([" + SURNAMES + r"][一-鿿]{1,3})")

BIRTH_AD = re.compile(r"(?:出生|生日)[\s:：]*(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})")
BIRTH_ROC = re.compile(
    r"(?:出生|生日)[\s:：]*(?:民國)?\s*0?(\d{2,3})[/\-年](\d{1,2})[/\-月]?(\d{1,2})[日]?(?!\d)"
)
BIRTH_COMPACT = re.compile(r"(?:出生|生日)[\s:：]*(\d{7})(?!\d)")


@dataclass
class RecordResult:
    """One de-identified record and everything worth reporting about it."""

    alias: str | None
    age: int | None
    text: str
    identified: bool
    stats: dict[str, int] = field(default_factory=dict)
    leaks: list[str] = field(default_factory=list)
    path: str | None = None

    @property
    def ok(self) -> bool:
        return not self.leaks


def _id_boundary(identifier: str) -> str:
    """A pattern matching ``identifier`` only as a whole token.

    A plain string replace is wrong here, and quietly so. Chart number
    ``1234567`` is a substring of somebody else's national ID ``A123456789``,
    so replacing it blindly rewrites the middle of that ID into
    ``APT-000189``: the other person's identifier is now mangled rather than
    masked, and it no longer looks like an ID, so the residue check that
    watches for surviving IDs cannot see it either. The same collision can
    chop a phone number in half and stop the phone rule from matching what is
    left.
    """
    return r"(?<![A-Za-z0-9])" + re.escape(identifier) + r"(?![0-9])"


def age_from_birth(birth: str | None, ref: datetime.date | None = None) -> int | None:
    """Age in whole years at ``ref`` (default today), or None if unparseable."""
    try:
        b = datetime.date.fromisoformat(birth)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
    r = ref or datetime.date.today()
    return r.year - b.year - ((r.month, r.day) < (b.month, b.day))


def detect_identity(text: str) -> tuple[str | None, str | None, str | None]:
    """Pull ``(mrn, name, birth)`` out of a record. Any of them may be None."""
    mrn = name = birth = None

    m = MRN_HEAD.search(text)
    if m:
        mrn = m.group(1)

    m = NAME_LABEL.search(text)
    if m:
        name = m.group(1)

    if not mrn:
        m = ID_NAME.search(text)
        if m:
            mrn = m.group(1) or m.group(4)
            name = name or m.group(2) or m.group(3)

    m = BIRTH_AD.search(text)
    if m:
        birth = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    else:
        m = BIRTH_ROC.search(text)
        if m and int(m.group(1)) < 200:  # ROC year, not a stray 4-digit year
            birth = f"{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        else:
            m = BIRTH_COMPACT.search(text)
            if m:
                s = m.group(1)
                birth = f"{int(s[:3]) + 1911:04d}-{s[3:5]}-{s[5:]}"

    return mrn, name, birth


def _line_id(line: str) -> str | None:
    m = MRN_HEAD.search(line)
    if m:
        return m.group(1)
    m = ID_NAME.search(line)
    return (m.group(1) or m.group(4)) if m else None


def _split_on_heads(text: str) -> list[str]:
    """Cut immediately before each line that carries a labelled chart number."""
    heads = [m.start() for m in MRN_HEAD.finditer(text)]
    starts = sorted({text.rfind("\n", 0, h) + 1 for h in heads})
    if len(starts) <= 1:
        return [text.strip()] if text.strip() else []
    if starts[0] != 0:
        starts.insert(0, 0)
    return [
        text[a:b].strip()
        for a, b in zip(starts, starts[1:] + [len(text)])
        if text[a:b].strip()
    ]


def _split_on_ids(text: str) -> list[str]:
    """No chart-number labels: every line carrying ID+name starts a new patient.

    Consecutive lines with the same ID stay together; lines with no ID at all
    belong to whoever came before them.
    """
    recs: list[tuple[str | None, list[str]]] = []
    for line in text.splitlines():
        lid = _line_id(line)
        if lid and (not recs or recs[-1][0] != lid):
            recs.append((lid, [line]))
        elif recs:
            recs[-1][1].append(line)
        elif line.strip():
            recs.append((None, [line]))
    return ["\n".join(lines).strip() for _, lines in recs if "\n".join(lines).strip()]


def split_records(text: str) -> list[str]:
    """Split a pasted blob into one chunk per patient.

    Three layers, applied in order: an explicit ``---``/``===`` separator line,
    then labelled chart numbers, then the ID+name shorthand.
    """
    out: list[str] = []
    for part in re.split(r"^\s*[-=]{3,}\s*$", text, flags=re.M):
        if not part.strip():
            continue
        for chunk in _split_on_heads(part):
            if MRN_HEAD.search(chunk):
                out.append(chunk)
            else:
                out.extend(_split_on_ids(chunk))
    return out


def residue_check(store: AliasStore, body: str) -> list[str]:
    """Grep a finished record for anything that should not have survived.

    Three separate signals, because they fail in different ways:
      * a known real name or chart number appearing verbatim,
      * a 2-4 character Chinese string glued to an ``[身分證號]`` marker, which
        is what an un-masked name next to a masked ID looks like,
      * an ID-shaped token the rules did not catch at all.
    """
    leaks: list[str] = []
    for mrn, name in store.all_known():
        if name and name in body:
            leaks.append(f"姓名({store.alias_for(mrn)})")
        if mrn and mrn in body:
            leaks.append(f"病歷號({store.alias_for(mrn)})")
    if re.search(r"\[身分證號\][ ,，]*[一-鿿]{2,4}|[一-鿿]{2,4}[ ,，]*\[身分證號\]", body):
        leaks.append("疑似姓名貼著[身分證號]")
    if re.search(r"(?<![A-Za-z0-9])[A-Z]\d{9}(?!\d)", body):
        leaks.append("殘留未遮罩ID")
    return leaks


def process_record(
    store: AliasStore,
    text: str,
    mrn: str | None = None,
    name: str | None = None,
    birth: str | None = None,
    *,
    ref_date: datetime.date | None = None,
) -> RecordResult:
    """De-identify one record. The record's content never enters the result stats."""
    text = normalize(text)

    if not mrn or not name:
        d_mrn, d_name, d_birth = detect_identity(text)
        mrn = mrn or d_mrn
        name = name or d_name
        birth = birth or d_birth
    if mrn and not (name and birth):
        known_name, known_birth = store.lookup(mrn)
        name = name or known_name
        birth = birth or known_birth

    stats: dict[str, int] = {}
    if mrn:
        alias = store.alias_for(mrn)
        store.upsert_patient(mrn, name, birth)
    else:
        alias = None

    # 1) Targeted substitution — keeps the reference, drops the identity.
    tag = alias or "[病人]"
    if mrn:
        text, n = re.subn(_id_boundary(mrn), tag, text)
        stats["mrn_to_alias"] = n
    if name:
        text, n = re.subn(re.escape(name), tag, text)
        stats["name_to_alias"] = n
        if len(name) >= 3:  # given name used on its own, without the surname
            text, n2 = re.subn(re.escape(name[1:]), tag, text)
            stats["name_to_alias"] += n2

    # 2) Date of birth becomes an age.
    age = age_from_birth(birth, ref_date) if birth else None
    if birth:
        y, mo, d = birth.split("-")
        for pat in (
            rf"{y}[/\-年]0?{int(mo)}[/\-月]0?{int(d)}日?",
            rf"(?:民國)?\s?0?{int(y) - 1911}[/\-年]0?{int(mo)}[/\-月]?0?{int(d)}[日號]?(?!\d)",
        ):
            text, n = re.subn(pat, f"[{age}歲]" if age is not None else "[生日]", text)
            stats["birth_to_age"] = stats.get("birth_to_age", 0) + n

    # 3) Other patients on record who happen to be mentioned here.
    for other_mrn, other_name in store.others(mrn):
        other_alias = store.alias_for(other_mrn)
        if other_name and other_name in text:
            text = text.replace(other_name, other_alias)
            stats["other_patients"] = stats.get("other_patients", 0) + 1
        if other_mrn:
            text, n = re.subn(_id_boundary(other_mrn), other_alias, text)
            if n:
                stats["other_patients"] = stats.get("other_patients", 0) + n

    # 4) The generic net, last.
    text = deidentify(text, do_normalize=False)

    header = f"[代號 {alias or '未識別'}" + (f"，{age}歲" if age is not None else "") + "]\n"
    body = header + text

    return RecordResult(
        alias=alias,
        age=age,
        text=body,
        identified=bool(mrn),
        stats=stats,
        leaks=residue_check(store, body),
    )


def ingest(
    store: AliasStore,
    text: str,
    *,
    ref_date: datetime.date | None = None,
) -> list[RecordResult]:
    """De-identify a blob that may hold several patients.

    Two passes on purpose: every ID+name pair in the **whole** input is
    registered first, so that when record A mentions patient B in passing, B
    already has an alias to be replaced with.
    """
    text = normalize(text)
    records = split_records(text)

    pairs: list[tuple[str, str | None, str | None]] = []
    for chunk in records:
        mrn, name, birth = detect_identity(chunk)
        if mrn:
            pairs.append((mrn, name, birth))
    for m in ID_NAME.finditer(text):  # also catches people buried inside another record
        pairs.append((m.group(1) or m.group(4), m.group(2) or m.group(3), None))
    for mrn, name, birth in pairs:
        store.alias_for(mrn)
        store.upsert_patient(mrn, name, birth)

    results = [process_record(store, chunk, ref_date=ref_date) for chunk in records]

    # Second residue sweep: by now every patient in the batch is registered,
    # so a name that was still unknown during the first pass gets caught here.
    for r in results:
        r.leaks = residue_check(store, r.text)
    return results
