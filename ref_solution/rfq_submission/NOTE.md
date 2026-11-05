# NOTE: RFQ Parser

**Approach.** Plain rules, standard library only (no model, no keys, ~1 ms per message). Gsm and micron are extracted first so their numbers can't be mistaken for quantity. Every other number becomes a quantity *candidate*; I reject the ones that are really fill weight ("25 kg bags", "bags of 50 kg", "50 kg x 2000"), capacity ("1000 kg capacity", "SWL"), sizes, price/rate, phone numbers, pincodes, ply, colours or dates, then pick the best remaining one and convert lakh / hazaar / k / crore. Category uses a prioritised keyword list with typo tolerance. Location uses a list of ~900 Indian cities, states and countries, then pattern fallbacks ("deliver to X", "X me", "X 440001", last comma segment) for places not in the list.

**Score.** The company's `score.py` was not included with my copy of the brief, so I wrote `score_local.py` (exact match per field; a message counts only if all six fields are right).
- `my_tests.jsonl` (60 messages, used while building): 60/60
- `holdout.jsonl` (50, different wording and cities; I fixed bugs it exposed, so it is not fully clean): 50/50
- `redteam.jsonl` (52 harder messages written after tuning): 52/52
- Location with the city list switched off (fallback patterns only), over all 162 messages: 154/162 (95%). **This is the honest estimate for unseen cities.** Many of my test cities are in the list, so 100% on location overstates it.
- 25 unit tests also pass (contract, traps, number formats, garbage input, invariance, speed).
All three sets were written by me, so real buyer messages will score lower. I expect roughly 85-92%.

**3 messages it gets wrong (real outputs).**
1. `need bopp bags 5000 and woven sack 2000 Pune` returns only bopp_bag / 5000. The schema holds one product, so the second is dropped.
2. `bopp bags 65 gsm 40000 Nagpur Pune` returns Nagpur. Two cities and nothing says which is the delivery city, so it takes the first.
3. `film 20 mic 1 MT or 2 MT Pune` returns 1 mt. Two alternatives; it takes the first. Similarly `bags chahiye` returns woven_sack, a guess, because nothing names the product.

**With 1,000 real labelled examples.** Measure errors per field first. Keep the rules as a validator and train a small tagger (CRF or a tiny transformer) for quantity and location, with the rules as features. Learn the city list from the data, tune thresholds and the typo cutoff on a held-out split, add a confidence per field, and score precision/recall per field instead of only exact match.

**How I'd know it works with real buyers.** Track the share of None per field and quantity outliers (alert on spikes), review a small random sample by hand every day, and treat "buyer or supplier corrected the extracted field" as the live error rate. Run in shadow mode before launch, and store every correction as new labelled data.

**Tools / AI.** Claude (Anthropic) wrote the first version of parse.py, the tests and the labels. I then ran it, read the failures and checked the labels myself: *(edit this line to say truthfully what you personally did)*.
