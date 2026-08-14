"""The browser demo must behave exactly like the library.

Two separate checks, because they fail differently:

* ``test_generated_file_is_current`` catches "someone edited rules.py and
  forgot to regenerate" — a stale file, caught without running any JS.
* ``test_python_and_javascript_agree`` catches "the two regex engines disagree
  about this pattern" — the failure a regeneration would not fix.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from chart_scrub.rules import deidentify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tools", "js_deid_runner.mjs")

CASES = [
    "病歷號碼：1234567",
    "身分證 A123456789 已核對",
    "身分證Ａ１２３４５６７８９",
    "聯絡電話0912345678請撥",
    "市話 03-1234567",
    "寄到 daming@example.com 給我",
    "民國60年3月5日生",
    "生日：1971/03/05",
    "住新北市板橋區文化路一段100號5樓",
    "住台中市西屯區台灣大道三段99號",
    "復健科在中山路100號3樓",
    "他說沿著中山路走十分鐘就到了。",
    "陳先生今天回診",
    "王大明先生今天回診",
    "我叫林志偉",
    "病人陳小明主訴右肩痛",
    "我太太林美玉說我走路都歪一邊",
    "他太太黃小姐陪同",
    "My name is John Smith.",
    "McMurray test 陰性，Colles fracture 已癒合，Neer sign 陽性。",
    "皮膚偏黃，白血球正常，江湖傳言不足採信。",
    "ROM 0-120 度，MMT 4/5，VAS 7 分，血壓 138/86 mmHg。",
    "主訴：右肩痛（三個月），夜間痛醒。",
    "姓名：王大明\n病歷號碼：1234567\n電話：0912-345-678\n住宜蘭縣礁溪鄉中央路二段10巷5號",
]


def test_generated_file_is_current():
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "export_rules_js.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_python_and_javascript_agree():
    r = subprocess.run(
        ["node", RUNNER], input=json.dumps(CASES), capture_output=True,
        text=True, encoding="utf-8", cwd=os.path.join(ROOT, "tools"),
    )
    assert r.returncode == 0, r.stderr
    js_out = json.loads(r.stdout)
    py_out = [deidentify(c) for c in CASES]

    mismatches = [
        (case, py, js)
        for case, py, js in zip(CASES, py_out, js_out)
        if py != js
    ]
    assert not mismatches, "\n".join(
        f"input:  {c!r}\npython: {p!r}\njs:     {j!r}" for c, p, j in mismatches
    )
