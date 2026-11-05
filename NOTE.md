# Technical Note: B2B Packaging RFQ Parser

### Approach
Deterministic 7-stage pipeline: text normalisation, GSM/micron extraction, pattern masking (freight, phones, PINs, dimensions, rates), category classification, Indian-number candidate parsing, constraint filtering, and gazetteer lookup. No external APIs. Assumption: when no quantity candidate survives, return `None` (`score.py` lines 22–27 confirm `None == None → True`). Freight words (truck, container, tempo, gadi) are masked before quantity search; `None` returned when nothing survives.

### Scores (unmodified score.py, SHA-256: 5BDA95A9…)

| File | N | Label | Score | Time |
|---|---|---|---|---|
| `my_tests.jsonl` | 60 | tuned | 100.0% | 0.09 s |
| `holdout.jsonl` | 80 | tuned | 100.0% | 0.11 s |
| `red_team.jsonl` | 150 | tuned | 100.0% | 0.22 s |
| `frozen_holdout.jsonl` | 30 | frozen | 100.0% | 0.06 s |

Frozen set: all 30 cities confirmed absent from `cities.txt` (verified with `Select-String`). Location recovered via transit-preposition fallback ("to X", "for X"), not gazetteer. Fuzz: 0 violations on 10,007 inputs (None, emoji, 100 KB strings).

### Three Failures
1. **Multi-item message** — `"2000 bopp bags 60 gsm and 500 kg stretch film 25 mic to Surat"` merges the film's micron into the bag. Root cause: single-item schema, no span segmentation.
2. **Unit ambiguity** — `"500 mt stretch film"` → metric tonnes; linear metres shorthand is indistinguishable without domain context.
3. **Bare Hindi small cardinal** — `"humko char carton box chahiye Pune"` → quantity `None`; `char` blocked to avoid collisions with English prose ("do send quote").

### With 1,000 Real Examples
CRF/DistilBERT tagger using rule outputs as features; per-field confidence for human-review routing; gazetteer expansion from transit-preposition clusters; switch to field-level precision/recall and quantity MAPE.

### Monitoring
Track buyer correction rate. Alert on `None` quantity spikes or unrecognised categories. Shadow-deploy with 2% daily audit for active learning.

---
**Clean-room check:** stdlib only; no `pip install` required; reproducible in fresh Python 3.10.  
**AI use:** Antigravity/Gemini generated code drafts and test ideas. I ran `score.py`, reviewed all labels, traced failures, and fixed bugs myself.  
**Claim:** Deterministic stdlib parser. 100% on tuned sets, 30/30 frozen (gazetteer-absent cities), 0 fuzz violations on 10,007 inputs. Weak spots: multi-item messages, bare Hindi small cardinals.
