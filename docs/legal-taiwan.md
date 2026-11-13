# The legal side (Taiwan)

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

[Back to README](../README.md)
