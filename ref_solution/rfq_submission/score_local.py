"""Local stand-in for the company's score.py (which we were never sent). Usage: python score_local.py file.jsonl [-v]
Exact match per field; an example counts as fully correct only if all six fields match."""
import json, sys, time
from parse import parse_rfq
KEYS = ["category", "quantity", "unit", "gsm", "micron", "location"]
def same(a, b, k):
    if k == "location" and isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    if k == "quantity" and a is not None and b is not None:
        return abs(float(a) - float(b)) < 1e-6
    return a == b
def main(path, verbose=False):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    t0 = time.time(); field_ok = dict.fromkeys(KEYS, 0); full = 0; bad = []
    for r in rows:
        got = parse_rfq(r["text"]); exp = r["expected"]
        assert set(got) == set(KEYS), got
        oks = {k: same(got[k], exp[k], k) for k in KEYS}
        for k in KEYS: field_ok[k] += oks[k]
        if all(oks.values()): full += 1
        else: bad.append((r["text"], {k: (exp[k], got[k]) for k in KEYS if not oks[k]}))
    n = len(rows)
    print(f"{path}: {full}/{n} fully correct = {100*full/n:.1f}%   ({time.time()-t0:.2f}s)")
    print("  per field: " + "  ".join(f"{k} {100*field_ok[k]/n:.0f}%" for k in KEYS))
    if verbose or bad:
        for t, d in bad: print("  FAIL:", t, "->", d)
if __name__ == "__main__":
    main(sys.argv[1], "-v" in sys.argv)
