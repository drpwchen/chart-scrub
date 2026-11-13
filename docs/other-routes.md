# Other routes worth knowing about

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

[Back to README](../README.md)
