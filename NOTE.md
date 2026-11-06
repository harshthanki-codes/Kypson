# Technical Note: B2B Packaging RFQ Parser

### Approach & Assumptions
Deterministic 7-stage pipeline in Python 3.10+ standard library: text normalisation (Devanagari, stuck units), GSM/micron parsing, pattern masking (PINs, phones, dimensions, freight, rates, pack sizes), category classification, Indian-number candidate extraction (fractions, magnitudes, crore/lakh/k), domain filtering (fill weight vs capacity vs order quantity), and compiled regex gazetteer lookup with transit routing (~1 ms/msg).  
- *Assumption 1 (Option A):* Missing order quantity returns `quantity: None` and `unit: None`.  
- *Assumption 2:* Plain carton with `gsm >= 200` is classified as `mono_carton`; lower-GSM cartons remain `corrugated_box`.

### Evaluation & Scores
Evaluated with official `score.py` (SHA-256: `C3DD1FF783D61F77F79CBEF25A72ED33C939A35ECB08964D95BA5192A3A36DC7`):
- `my_tests.jsonl` (official submission set, 60 msgs): 60/60 (100.0%)
- Own test sets: `holdout.jsonl` (80 msgs): 80/80 (100.0%) | `red_team.jsonl` (150 msgs): 150/150 (100.0%) | `holdout_new.jsonl` (100 msgs): 100/100 (100.0%) | `fresh_eval100.jsonl` (100 msgs): 100/100 (100.0%) [cities.txt off: 98/100 (98.0%)] | `simulation_fresh100.jsonl` (100 msgs): 100/100 (100.0%) [cities.txt off: 100/100 (100.0%)]
- 10,000-case fuzzing: completed in 28.5s with 0 crashes and 0 contract violations.
- Unseen hidden-set expectation: on messy, unconstrained buyer traffic, honest accuracy is estimated at about **88% to 94%**.

### Three Messages My Parser Gets Wrong and Why
1. `need 2000 bopp bags 60 gsm and 500 kg stretch film 25 mic delivery to Surat`  
   *Output:* `bopp_bag`, qty 2000 pcs, gsm 60, micron 25. Single-item schema drops the second product and merges film micron into bag spec.
2. `need 500 mt stretch film 25 mic Morbi`  
   *Output:* `quantity: 500, unit: mt`. Buyers often mean linear metres, but canonicalisation maps MT to Metric Tonnes.
3. `humko char carton box chahiye Pune`  
   *Output:* `quantity: None, unit: None`. Bare Hindi numbers without magnitudes ("char", "do") are suppressed to prevent collisions with English prose ("do send quote").

### With 1,000 Labelled Examples
Train a lightweight sequence tagger using rule spans as dense features. Calibrate per-field confidence thresholds to route low-confidence RFQs to ops review, and cluster unrecognised delivery tokens.

### How I'd Know It Works With Real Buyers
Track per-field `None` rates, supplier edit deltas, and buyer drop-offs. Run in shadow mode, auditing a 2% daily sample and alerting on outlier quantities (>1 crore or <10 units).

---
**AI Assistance:** Antigravity agent (Gemini and GPT-OSS 120B) for code, tests, and refactoring; Claude (Anthropic) for planning, prompts, and a benchmark reference.  
**Personal Verification:** [User to insert personal review details]
