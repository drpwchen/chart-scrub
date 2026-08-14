# clinic-deid

[![CI](https://github.com/drpwchen/clinic-deid/actions/workflows/ci.yml/badge.svg)](https://github.com/drpwchen/clinic-deid/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

在自己的電腦上，把繁體中文臨床文字的識別資訊拿掉，再決定要不要送給雲端模型。

**[在瀏覽器裡直接試 →](https://drpwchen.github.io/clinic-deid/)**
那頁完全在你的瀏覽器裡跑，沒有任何資料上傳。

English → [README.md](README.md)

---

## 它做什麼

```
病歷號碼：1234567 姓名：王大明 出生：1971/03/05
主訴：右肩痛三個月，夜間痛醒。王大明表示上個月在李阿嬤介紹的推拿館推過。
電話 0912-345-678，住新北市板橋區文化路一段100號5樓。
```

會變成

```
[代號 PT-0001，55歲]
病歷號碼：PT-0001 姓名：PT-0001 出生：[55歲]
主訴：右肩痛三個月，夜間痛醒。PT-0001表示上個月在[稱謂]介紹的推拿館推過。
電話 [電話]，住[地址]。
```

臨床內容留著，身分不見了。同一個病人下次回診還是 `PT-0001`，所以一串紀錄讀起來
仍然是同一個人的故事；而 `PT-0001` 對回真名的那張表，只存在你本機的一個 SQLite
檔裡，不會離開這台電腦。

## 兩層

**第一層：遮罩引擎**（`clinic_deid/rules.py`）——15 條規則，處理病歷號、身分證、
電話、電子郵件、生日、地址、姓名。沒有狀態、沒有資料庫、不連網。瀏覽器 demo 跑的
就是這一層。

**第二層：假名化管線**（`clinic_deid/pseudonymize.py`）——先判斷這筆是誰的紀錄，
把那個人換成固定代號，把生日換算成年齡，順帶提到的其他病人也各自給代號，最後再把
第一層當成網子鋪在底下。跑完會拿自己知道的每一個識別資訊回頭搜自己的輸出，**只要
有東西活下來就判定失敗**。

順序是有意義的：定向抽換一定要在通用規則之前跑，否則姓名已經變成 `[姓名]`，代號就
接不上去了。

## 安裝

```bash
git clone https://github.com/drpwchen/clinic-deid
cd clinic-deid
pip install -e .
```

標準函式庫以外沒有任何相依套件。

## 怎麼用

```bash
# 只跑規則。不建資料庫，什麼都不留。
clinic-deid mask notes.txt
echo "病人陳小明，電話 0912-345-678" | clinic-deid mask -

# 完整管線。在輸入檔旁邊產出 PT-0001_<時間>.deid.txt
clinic-deid ingest today.txt

# 一次貼多個病人——用 --- 分隔、用病歷號那行、或用「身分證+姓名」的寫法都可以切
clinic-deid ingest clinic-list.txt --json

# 對已經產好的檔案重跑殘留檢查
clinic-deid verify *.deid.txt

# 只列代號和年齡，給誰看都安全
clinic-deid list

# 反查真名。會印出真實姓名——請在自己的終端機跑，不要透過 AI 助理。
clinic-deid who PT-0001
```

離開碼 `2` 代表殘留檢查沒過，**那個輸出檔不要用**。

當函式庫用：

```python
from clinic_deid import AliasStore, deidentify, ingest

deidentify("病人陳小明，電話 0912-345-678")
# '病人[姓名]，電話 [電話]'

with AliasStore("aliases.db") as store:
    for record in ingest(store, open("today.txt", encoding="utf-8").read()):
        print(record.alias, record.age, record.ok)
```

## 它抓不到什麼（這段請看兩遍）

- **沒有線索的姓名會漏。**「小明今天回診」沒有稱謂、沒有角色詞、也不是自我介紹，
  所以不會觸發。姓名被抓到的情況是：帶稱謂（`陳先生`）、跟在角色詞後面
  （`病人陳小明`）、明講（`我叫…`）、或緊鄰身分證號。
- **姓氏表只有約 100 個姓。** 罕見姓氏根本不會被當成姓名。
- **純正規表示式。** 沒有 NER 模型、沒有真實姓名字典、沒有任何會學習的東西，
  它無法理解上下文。
- **它故意會多遮。** 偶爾會誤遮醫學名詞。這個取捨是刻意的：多遮一個詞你重看一次
  就好，漏掉一個名字代價大得多。
- **就診日期會保留。** 臨床判讀通常需要。如果你要符合 HIPAA safe harbor 的日期
  規則，得自己加日期位移。
- **殘留檢查只知道資料庫裡有的東西。** 它抓得到已登記的姓名與病歷號，加上兩種漏法
  （中文姓名黏在被遮的身分證旁邊、長得像身分證卻沒被遮的字串）。從沒見過、又沒有
  任何規則命中的姓名，會安靜通過。
- **它是照一家診間的貼上格式長出來的。** 我的。下一段講這件事。

請把它當第一道網子，不是保證。輸出送出去之前，還是要有人看過。

## 每家醫院的資料都長不一樣

這裡面的格式假設——病歷號在哪一欄、生日寫民國還是西元、一次貼一個病人還是十二個
——全都是從我自己的門診流程長出來的。你的一定不一樣。

**所以請 fork 過去改成你的版本。** 最可能要動的地方：

| 想改什麼 | 改哪裡 |
| --- | --- |
| 新增或修改遮罩規則 | `clinic_deid/rules.py` 的 `RULES` |
| 讓它認得你的表頭格式 | `clinic_deid/pseudonymize.py` 的 `MRN_HEAD`、`NAME_LABEL` |
| 改變多病人怎麼切分 | `split_records()` |
| 改代號格式 | `AliasStore(prefix=...)` |
| 在輸出前多加一道檢查 | `residue_check()` |

如果你做出更好的版本，我真的很想知道——歡迎開 issue。

## 瀏覽器 demo

`docs/` 是一頁純靜態網頁，沒有 build、沒有相依套件。它的規則表是**從 Python 那份
自動產生的**：

```bash
python tools/export_rules_js.py           # 重新產生
python tools/export_rules_js.py --check   # 過期就失敗（CI 會跑這個）
```

還有一個測試會把同樣的 22 組輸入丟給兩邊的引擎，斷言輸出完全一致，所以 demo 不會
悄悄跟函式庫走鐘。

兩個引擎差異是明講處理掉的：Python 的 `\d` 會匹配全形數字而 JavaScript 不會
（所以兩邊都先把全形英數字折成半形），以及 Python 的 `\1` 反向參照要換成 `$1`。

## 測試

```bash
pip install -e ".[dev]"
pytest
```

80 條測試，其中大約三分之一是在斷言某些東西**不該**被遮——一個把全部東西都遮掉的
引擎，可以通過所有正向測試，然後完全沒用。

這套測試做過變異驗證：把幾個關鍵決定各自改回錯的做法（全文預先登記那一輪、
身分證+姓名規則的姓氏約束、跨紀錄代號抽換、地址規則的前導字守衛、編碼的 BOM 檢查），
測試都會失敗。

## 安全提醒

- `*.db` 和 `*.deid.txt` 已經在 `.gitignore` 裡，請讓它們留在那裡。
- 對照資料庫是唯一能把這一切還原的檔案，請用對待原始病歷的方式對待它。
- `clinic-deid who` 會印出真名，那就是它的用途。不要透過 AI 助理跑它，輸出也不要
  貼到任何地方。
- `ingest` 只印統計和代號、絕不印紀錄內容，所以需要別人幫忙除錯時，終端機輸出可以
  直接貼給對方看。

## 授權

MIT，見 [LICENSE](LICENSE)。

這是一個工具，**不是**法遵產品。它的輸出能不能滿足你機構的規定、你的 IRB、或個資法，
是你要自己判斷的事，不是我。
