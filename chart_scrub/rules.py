"""Rule-based de-identification for Traditional Chinese (Taiwan) clinical text.

Design principle: **recall over precision**. Masking a few extra tokens is an
inconvenience; leaking a name or an ID is not. Every rule here is deliberately
willing to over-mask.

This module is the single source of truth for the pattern table. The browser
demo in ``docs/`` is generated from ``RULES`` by ``tools/export_rules_js.py``,
so the two never drift apart.

The rules are regex only — there is no NER model, no dictionary of real names,
and no learning component. See README "Known limitations" for what that misses.
"""

from __future__ import annotations

import re
from typing import NamedTuple

__all__ = [
    "SURNAMES",
    "TITLES",
    "RULES",
    "Rule",
    "normalize",
    "deidentify",
    "deidentify_verbose",
    "is_valid_roc_id",
    "load_rules_file",
    "audit_numbers",
]

# Common Taiwanese surnames (roughly the top 100 by population). Used together
# with title/role heuristics — a surname on its own is never masked, because
# many of them are also ordinary words (黃 yellow, 白 white, 江 river).
SURNAMES = (
    "陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏"
    "柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯田康姜白汪鄒尤巫鐘黎涂龔嚴韓"
)

# The 22 counties and cities, spelled out rather than matched as
# "any 1-4 CJK chars + 縣/市". The generic form swallows the character before
# the address (住新北市 matches 住新北 + 市), and over-masking that silently
# eats ordinary words is the kind of damage nobody notices.
#
# The pre-2010 names (臺北縣, 桃園縣, 臺中縣, 臺南縣, 高雄縣) are included on
# purpose: older patients still give their address the way it was when they
# moved in, and a history is written down the way it was spoken.
COUNTIES = (
    r"(?:臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|"
    r"新竹市|新竹縣|嘉義市|嘉義縣|苗栗縣|彰化縣|南投縣|雲林縣|屏東縣|宜蘭縣|"
    r"花蓮縣|臺東縣|台東縣|澎湖縣|金門縣|連江縣|"
    r"臺北縣|台北縣|桃園縣|臺中縣|台中縣|臺南縣|台南縣|高雄縣)"
)

# Forms of address that mark the preceding characters as a personal name.
TITLES = r"(?:先生|小姐|太太|女士|阿公|阿嬤|阿伯|阿姨|大哥|大姐|同學|老師|伯伯|奶奶|爺爺)"

# A CJK character class. Written as an explicit codepoint range so that the
# exported JavaScript behaves identically.
CJK = r"[一-鿿]"

# Full-width digits, upper-case and lower-case Latin letters. Each block sits
# exactly 0xFEE0 above its ASCII counterpart.
_FULLWIDTH = {
    cp: cp - 0xFEE0
    for start, end in ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A))
    for cp in range(start, end + 1)
}


class Rule(NamedTuple):
    """One masking rule.

    ``pattern`` is a regex source string valid in **both** Python's ``re`` and
    JavaScript's ``RegExp``. ``replacement`` uses Python backreference syntax
    (``\\1``); the JS exporter rewrites those to ``$1``. ``flags`` holds
    JavaScript flag letters (only ``m`` is used so far); the Python side maps
    them onto ``re`` flags.
    """

    name: str
    pattern: str
    replacement: str
    description: str
    flags: str = ""


_FLAG_MAP = {"m": re.M, "i": re.I, "s": re.S}


def _compile(rule: Rule) -> re.Pattern[str]:
    flags = 0  # not re.NOFLAG — that name only exists from Python 3.11
    for letter in rule.flags:
        flags |= _FLAG_MAP[letter]
    return re.compile(rule.pattern, flags)


RULES: list[Rule] = [
    Rule(
        "mrn",
        # No upper bound on the digit run: a cap of 10 would mask the first
        # ten digits of an 11-digit number and leave the tail sitting in the
        # open — a partial mask that nothing downstream can notice. A labelled
        # number is a number; eat all of it.
        #
        # Taiwanese charts carry English headers as often as Chinese ones
        # ("Chart No:", "MRN"), so the label side is bilingual. "case"/"record"
        # require an explicit No./number — bare "case 12345" is everyday prose
        # ("in case 12345 patients…"), bare "chart 12345" is not. The leading
        # \b keeps "flowchart" from donating its tail.
        r"(病歷號碼?|病歷|案號|掛號號?碼?"
        r"|\b(?:chart|medical\s+record)\s*(?:no\.?|number|#)?"
        r"|\b(?:case|record)\s*(?:no\.?|number)"
        r"|\bMRN\s*#?)"
        r"[\s:：#]*[A-Za-z]?\d{5,}",
        r"\1[病歷號]",
        "Chart/medical record number introduced by a label (病歷號 / Chart No / MRN)",
        "i",
    ),
    Rule(
        "roc_id",
        # Lower-case accepted: normalize() folds width but not case, and a
        # hand-typed a123456789 identifies exactly as well as A123456789.
        r"(?<![A-Za-z0-9])[A-Za-z]\d{9}(?!\d)",
        "[身分證號]",
        "ROC national ID and new-style resident certificate number",
    ),
    Rule(
        "arc_old",
        # Old-style resident certificate (ARC/APRC before 2021): two letters
        # followed by eight digits. Its checksum differs from the national
        # ID's, so is_valid_roc_id() does not apply to these.
        r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{8}(?!\d)",
        "[居留證號]",
        "Old-style resident certificate number (two letters + 8 digits)",
    ),
    Rule(
        "nhi_card_labelled",
        r"(健保卡號?|卡號)[\s:：#]*\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)",
        r"\1[健保卡號]",
        "NHI card number introduced by a label (健保卡號：…)",
    ),
    Rule(
        "nhi_card",
        r"(?<![A-Za-z0-9])(?:0{4}|[0-9]{4})-?[0-9]{4}-?[0-9]{4}(?=\s*(?:健保卡|卡號))",
        "[健保卡號]",
        "NHI card number when the text after it names it (…健保卡)",
    ),
    Rule(
        "passport",
        # Label-driven on purpose: a bare 8-9 digit number is more often a
        # clinical value than a passport, and the address/phone rules already
        # guard their own shapes.
        # The value needs actual digits — a letters-only word after the label
        # ("passport control") is prose, not a number.
        r"(護照(?:號碼?)?|[Pp]assport(?:\s*(?:[Nn]o\.?|[Nn]umber))?)"
        r"[\s:：#]*[A-Za-z]{0,3}\d{4,9}(?![A-Za-z0-9])",
        r"\1[護照號]",
        "Passport number introduced by a label",
    ),
    Rule(
        "mobile",
        # (?<!\d) rather than \b: CJK counts as a word character in both
        # engines, so "電話0912..." has no word boundary to anchor on.
        r"(?<!\d)09\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)",
        "[電話]",
        "Mobile phone number",
    ),
    Rule(
        "landline",
        r"(?<!\d)0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)",
        "[電話]",
        "Landline phone number",
    ),
    Rule(
        "email",
        r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[電子郵件]",
        "Email address",
    ),
    Rule(
        "birth_roc",
        r"民國\s?\d{1,3}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?[日號](?:\s?出?生)?",
        "[生日]",
        "Date of birth written in ROC calendar form",
    ),
    Rule(
        "birth_labelled",
        # 出生日期/出生年月日 are part of the label, not the value — without
        # them in the label the value class (which has no 期) never reaches
        # four characters and the whole date survives.
        #
        # English labels are anchored: bare "birth" sits in too much clinical
        # prose (birth weight, preterm birth) to be a date cue on its own.
        # The value class allows spaces but not newlines — a class with \s
        # swallowed the line break after the date and glued the next line
        # onto the label ("出生[生日]主訴").
        r"(生日|出生(?:日期|年月日)?|\bDOB\b|\bdate\s+of\s+birth|\bbirth\s?da(?:te|y))"
        r"[是為:：\s]*[\d/年月日號 \t-]{4,12}",
        r"\1[生日]",
        "Date of birth introduced by a label (生日 / DOB / date of birth)",
        "i",
    ),
    Rule(
        "address",
        COUNTIES
        + r"(?:[一-鿿]{1,3}[區鄉鎮市])?"
        + r"(?:[一-鿿0-9]{0,12}[路街道巷弄]"
        r"(?:[一二三四五六七八九十0-9]{1,3}段)?"
        # Up to three number segments: 100巷5弄3號 is one address, and
        # stopping after the first segment leaves 5弄3號 in the open.
        r"(?:[0-9之\-]{1,8}[號巷弄]){0,3}"
        r"(?:[0-9之\-]{1,6}[樓F])?)?",
        "[地址]",
        "Full address starting from one of the 22 counties/cities",
    ),
    Rule(
        "street_number",
        # A street with an actual house number, for addresses written without
        # the county. Two guards keep it from eating ordinary prose: the
        # trailing 號 is required ("沿著中山路走" survives), and the road name
        # must start after a line break, a punctuation mark, or an address cue
        # — otherwise the preceding words get swallowed into the match.
        r"(^|[，,。；;：:\s]|住址|地址|住在|居住|位於|住|在)"
        # Road names are capped at 5 characters. Longer would let the match
        # start at the beginning of the line and swallow whatever came before.
        r"[一-鿿0-9]{2,5}[路街道](?:[一二三四五六七八九十0-9]{1,3}段)?"
        r"(?:[0-9之\-]{1,8}[號巷弄]){1,3}(?:[0-9之\-]{1,6}[樓F])?",
        r"\1[地址]",
        "Street address without a county prefix, anchored on a house number",
        "m",
    ),
    Rule(
        "surname_title",
        r"[" + SURNAMES + r"]" + TITLES,
        "[稱謂]",
        "Surname followed by a form of address (陳先生, 林阿嬤)",
    ),
    Rule(
        "fullname_title",
        r"[" + SURNAMES + r"][一-鿿]{1,2}" + TITLES,
        "[姓名]",
        "Full name followed by a form of address (陳小明先生)",
    ),
    Rule(
        "relation_name",
        # Family members get named in histories all the time ("我太太林美玉說…").
        # This rule sits AFTER the title rules on purpose: "他太太黃小姐" is
        # already "他太太[稱謂]" by the time we get here, so we cannot chop the
        # 姐 off a form of address and leave "他[姓名]姐" behind.
        r"(太太|先生|老公|老婆|兒子|女兒|媽媽|爸爸|母親|父親|哥哥|姊姊|姐姐|弟弟|妹妹|"
        r"孫子|孫女|媳婦|女婿|外甥|姪子|姪女|阿姨|舅舅|叔叔)"
        r"[" + SURNAMES + r"][一-鿿]{1,2}",
        r"\1[姓名]",
        "Family relation word immediately followed by a name (我太太林美玉)",
    ),
    Rule(
        "declared_name",
        r"(我叫|我是|名字是|姓名[是為:：\s]|病人叫|他叫|她叫|叫做)\s*[一-鿿]{2,4}",
        r"\1[姓名]",
        "Name introduced by an explicit declaration",
    ),
    Rule(
        "role_name",
        r"(病人|患者|個案|案主|家屬)[" + SURNAMES + r"][一-鿿]{1,2}",
        r"\1[姓名]",
        "Role word immediately followed by a full name (病人陳小明)",
    ),
    Rule(
        "english_name",
        # Conservative: only after a name cue, so medical eponyms
        # (McMurray, Colles) are left alone. Deliberately case-SENSITIVE:
        # capitalisation is the signal that separates a name from prose.
        #
        # The name shape covers how Taiwanese charts romanise names:
        # "WANG, TA-MING", "Chen Mei-Ling" — an optional comma between
        # words and a hyphenated given name. Each continuation word must
        # start with a capital (or follow a hyphen), so "Name: Wang Ta-Ming
        # presented with…" stops before "presented".
        # The continuation excludes the words that follow a name on a chart
        # header line ("Name: WANG, TA-MING  DOB: …") — without that guard the
        # next field's label gets swallowed into the name.
        r"(name is|[Nn]ame\s*[:：]|NAME\s*[:：]|Mr\.|Mrs\.|Ms\.)\s*"
        r"[A-Z][A-Za-z]+"
        r"(?:,?\s+(?!(?:DOB|MRN|ID|No|Sex|Age|Chart|Birth|Date|Tel|Phone)\b)"
        r"[A-Z][A-Za-z]+|-[A-Za-z]+){0,3}",
        r"\1 [NAME]",
        "English/romanised personal name after an explicit cue (Name:, Mr., name is)",
    ),
]

_COMPILED: list[tuple[Rule, re.Pattern[str]]] = [(r, _compile(r)) for r in RULES]


def normalize(text: str) -> str:
    """Fold full-width digits and Latin letters to half-width.

    A national ID typed as ``Ａ１２３４５６７８９`` has to match the same rule
    as ``A123456789``. Punctuation is deliberately left alone: full NFKC would
    also rewrite Chinese full-width commas and brackets into ASCII, which
    mangles the text for no de-identification benefit.

    The browser demo folds exactly the same three ranges.
    """
    return text.translate(_FULLWIDTH)


# National ID letter values, per the household registration checksum spec.
_ROC_ID_LETTER = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}


def is_valid_roc_id(token: str) -> bool:
    """True when ``token`` passes the national ID checksum.

    **Classification only — masking must never depend on this.** A real ID
    with one digit mistyped fails the checksum, and a masking pass gated on
    validity would wave exactly that ID through. Use this to tell a genuine
    身分證 apart from a chart number that merely shares the shape, or to
    label a residue finding as a certain leak rather than a suspected one.

    Covers the national ID and the new-style (2021+) resident certificate,
    which share the algorithm. Old-style two-letter ARC numbers do not.
    """
    token = normalize(token).upper()
    if not re.fullmatch(r"[A-Z]\d{9}", token):
        return False
    letter = _ROC_ID_LETTER[token[0]]
    digits = [letter // 10, letter % 10] + [int(c) for c in token[1:]]
    weights = (1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1)
    return sum(d * w for d, w in zip(digits, weights)) % 10 == 0


def load_rules_file(path: str) -> list[Rule]:
    """Read user-supplied rules from a JSON file.

    Every hospital prints identifiers its own way — most of them without any
    label at all — and no built-in table can know that an 8-digit run in *your*
    charts is always a chart number. This file is where you write that down::

        [
          {
            "name": "my_mrn",
            "pattern": "(?<![A-Za-z0-9])\\\\d{8}(?!\\\\d)",
            "replacement": "[病歷號]",
            "description": "our charts: bare 8 digits"
          }
        ]

    ``description`` and ``flags`` are optional. Validation is strict — a rule
    that fails to compile, or a name that collides with a built-in rule or
    another entry, stops the run instead of being silently dropped: a masking
    pass that quietly loses a rule is worse than one that refuses to start.
    """
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of rule objects")
    builtin = {r.name for r in RULES}
    seen: set[str] = set()
    out: list[Rule] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: entry {i} is not an object")
        missing = {"name", "pattern", "replacement"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: entry {i} is missing {sorted(missing)}")
        name = entry["name"]
        if name in builtin:
            raise ValueError(
                f"{path}: '{name}' collides with a built-in rule — "
                f"pick another name (and --skip {name} if you mean to replace it)")
        if name in seen:
            raise ValueError(f"{path}: duplicate rule name '{name}'")
        seen.add(name)
        flags = entry.get("flags", "")
        unknown_flags = set(flags) - set(_FLAG_MAP)
        if unknown_flags:
            raise ValueError(f"{path}: '{name}' has unsupported flags {sorted(unknown_flags)}")
        rule = Rule(name, entry["pattern"], entry["replacement"],
                    entry.get("description", ""), flags)
        try:
            _compile(rule)
        except re.error as e:
            raise ValueError(f"{path}: '{name}' does not compile: {e}") from e
        out.append(rule)
    return out


def deidentify(
    text: str, *, do_normalize: bool = True, skip: frozenset[str] | set[str] = frozenset(),
    extra_rules: list[Rule] | tuple[Rule, ...] = (),
) -> str:
    """Apply every rule (minus ``skip``) and return the masked text."""
    return deidentify_verbose(
        text, do_normalize=do_normalize, skip=skip, extra_rules=extra_rules)[0]


def deidentify_verbose(
    text: str, *, do_normalize: bool = True, skip: frozenset[str] | set[str] = frozenset(),
    extra_rules: list[Rule] | tuple[Rule, ...] = (),
) -> tuple[str, dict[str, int]]:
    """Apply every rule, returning ``(masked_text, hits_per_rule)``.

    ``skip`` holds rule names to leave out — the caller decides which
    identifiers exist in their world (a clinic that never sees passport
    numbers can drop that rule). Only rules that fired appear in the count
    dict.

    ``extra_rules`` (see :func:`load_rules_file`) run **before** the built-in
    table: the caller knows their own data format better than we do, so their
    pattern gets first claim on the text — a bare chart number masked by a
    custom rule must not be half-eaten by a generic one first.
    """
    if do_normalize:
        text = normalize(text)
    counts: dict[str, int] = {}
    table = [(r, _compile(r)) for r in extra_rules] + _COMPILED
    for rule, pattern in table:
        if rule.name in skip:
            continue
        text, n = pattern.subn(rule.replacement, text)
        if n:
            counts[rule.name] = n
    return text, counts


# ------------------------------------------------------------------ audit
# What the audit looks for in *masked* output: any digit run long enough to
# be an identifier, with up to two leading letters (national ID, old ARC).
_AUDIT_RUN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{0,2}\d{5,}(?![A-Za-z0-9])")


def classify_number(token: str) -> str:
    """Best guess at what a surviving number-shaped token is.

    Classification, not judgement: the audit reports what a shape *could* be
    so a human can decide, it never decides on its own that something is safe.
    """
    if is_valid_roc_id(token):
        return "確定身分證號（檢查碼有效）"
    if re.fullmatch(r"[A-Za-z]\d{9}", token):
        return "疑似身分證號（檢查碼無效）"
    if re.fullmatch(r"[A-Za-z]{2}\d{8}", token):
        return "疑似舊式居留證號"
    if re.fullmatch(r"09\d{8}", token):
        return "疑似手機號碼"
    if re.fullmatch(r"(?:19|20)\d{6}", token):
        m, d = int(token[4:6]), int(token[6:8])
        if 1 <= m <= 12 and 1 <= d <= 31:
            return "疑似日期 YYYYMMDD（若為生日應遮蔽）"
    if re.fullmatch(r"\d{7,8}", token):
        return "7-8位數（各院病歷號常見長度）"
    return "未分類數字串"


def audit_numbers(text: str) -> list[tuple[str, int, str]]:
    """Every number-shaped token surviving in ``text``, with a shape guess.

    Run this on already-masked output. Whatever it returns is what the rules
    did NOT recognise — the working loop is: audit, decide which shapes are
    identifiers in your hospital's format, write those into a
    :func:`load_rules_file` JSON, mask again. Sorted by count so the
    systematic shapes (a chart number on every record) float to the top.
    """
    counts: dict[str, int] = {}
    for m in _AUDIT_RUN.finditer(text):
        counts[m.group()] = counts.get(m.group(), 0) + 1
    return sorted(
        ((tok, n, classify_number(tok)) for tok, n in counts.items()),
        key=lambda t: (-t[1], t[0]),
    )


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    sample = (
        "病人王大明先生，病歷號 1234567，身分證 A123456789，電話 0912-345-678，"
        "住新北市板橋區文化路一段100號5樓。我叫王大明，民國60年3月5日生，"
        "email daming@example.com。McMurray test 陽性。My name is John Smith."
    )
    masked, hits = deidentify_verbose(sample)
    print(masked)
    print(hits)
