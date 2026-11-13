# 其他路線

如果你的問題其實是「攔住每一個離開這台機器的 prompt」，而不是「把要留存的資料去識別化」，
那 gateway 上的 DLP 層可能比 CLI 更合適。[LiteLLM](https://github.com/BerriAI/litellm)
搭配 [ceil-dlp](https://github.com/dorcha-inc/ceil-dlp) 這類 guardrail plugin 走的就是
這條路；而 ceil-dlp 的 *whistledown* 模式——可逆遮罩、在回覆裡把值還原回去，出自
[這篇論文](https://arxiv.org/abs/2511.13319)——正是上面 `rehydrate()` 借鏡的來源。
該給的功勞要給。

兩個要權衡的差別：

- **語言。** ceil-dlp 的偵測層是英文的：spaCy `en_core_web_lg`、在 CoNLL-2003 上訓練的
  `dslim/bert-base-NER`、以及 GLiNER `gliner_multi_pii-v1`（fine-tune 過英、法、德、西、
  義、葡六種語言）。中文不在其中，而且這三個都不認識台灣的病歷號、健保卡號和身分證
  檢查碼。chart-scrub 存在的理由就是這個缺口。
- **模型 vs 規則。** NER ensemble 能推廣到正則沒預料到的寫法，但它漏掉的東西你既列不
  出來也測不到。規則剛好相反：沒人寫過的規則就漏，但同樣的輸入永遠得到同樣的輸出——
  正是這一點才讓殘留檢查和測試套件有意義。對於要歸檔、日後可能要交代的文字，這個取捨
  偏向一邊；對於正在飛的 prompt，可能偏向另一邊。

兩者不互斥。看文字之後會發生什麼事，選對應的那個。

[回到 README](../README.zh-TW.md)
