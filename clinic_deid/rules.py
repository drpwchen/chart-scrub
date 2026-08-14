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
COUNTIES = (
    r"(?:臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|"
    r"新竹市|新竹縣|嘉義市|嘉義縣|苗栗縣|彰化縣|南投縣|雲林縣|屏東縣|宜蘭縣|"
    r"花蓮縣|臺東縣|台東縣|澎湖縣|金門縣|連江縣)"
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
        r"(病歷號碼?|病歷|案號|掛號號?碼?)[\s:：#]*[A-Z]?\d{5,10}",
        r"\1[病歷號]",
        "Chart/medical record number introduced by a label",
    ),
    Rule(
        "roc_id",
        r"(?<![A-Za-z0-9])[A-Z]\d{9}(?!\d)",
        "[身分證號]",
        "ROC national ID and new-style resident certificate number",
    ),
    Rule(
        "nhi_card",
        r"(?<![A-Za-z0-9])(?:0{4}|[0-9]{4})-?[0-9]{4}-?[0-9]{4}(?=\s*(?:健保卡|卡號))",
        "[健保卡號]",
        "NHI card number when the surrounding text names it",
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
        r"(生日|出生)[是為:：\s]*[\d/年月日號\s-]{4,12}",
        r"\1[生日]",
        "Date of birth introduced by a label",
    ),
    Rule(
        "address",
        COUNTIES
        + r"(?:[一-鿿]{1,3}[區鄉鎮市])?"
        + r"(?:[一-鿿0-9]{0,12}[路街道巷弄]"
        r"(?:[一二三四五六七八九十0-9]{1,3}段)?"
        r"(?:[0-9之\-]{1,8}[號巷弄])?"
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
        r"[0-9之\-]{1,8}[號巷](?:[0-9之\-]{1,6}[樓F])?",
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
        # (McMurray, Colles) are left alone.
        r"(name is|Mr\.|Mrs\.|Ms\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",
        r"\1 [NAME]",
        "English personal name after an explicit cue",
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


def deidentify(text: str, *, do_normalize: bool = True) -> str:
    """Apply every rule and return the masked text."""
    return deidentify_verbose(text, do_normalize=do_normalize)[0]


def deidentify_verbose(
    text: str, *, do_normalize: bool = True
) -> tuple[str, dict[str, int]]:
    """Apply every rule, returning ``(masked_text, hits_per_rule)``.

    Only rules that fired appear in the count dict.
    """
    if do_normalize:
        text = normalize(text)
    counts: dict[str, int] = {}
    for rule, pattern in _COMPILED:
        text, n = pattern.subn(rule.replacement, text)
        if n:
            counts[rule.name] = n
    return text, counts


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    sample = (
        "病人王大明先生，病歷號 1234567，身分證 A123456789，電話 0912-345-678，"
        "住新北市板橋區文化路一段100號5樓。我叫王大明，民國60年3月5日生，"
        "email daming@example.com。McMurray test 陽性。My name is John Smith."
    )
    masked, hits = deidentify_verbose(sample)
    print(masked)
    print(hits)
