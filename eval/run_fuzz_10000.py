import json, time, random, string, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from parse import parse_rfq

CATS = {"bopp_bag","woven_sack","corrugated_box","pouch","film","mono_carton","fibc"}
KEYS = {"category","quantity","unit","gsm","micron","location"}

def check(out):
    """Return a list of contract violations for one parse_rfq output."""
    bad = []
    if not isinstance(out, dict) or set(out) != KEYS:
        return ["keys"]
    if out["category"] not in CATS: bad.append("category")
    if out["quantity"] is None:
        if out["unit"] is not None: bad.append("unit should be None when quantity is None")
    else:
        if out["unit"] not in {"pcs", "kg", "mt"}: bad.append("unit")
    q = out["quantity"]
    if q is not None and (isinstance(q, bool) or not isinstance(q, (int, float))): bad.append("quantity type")
    for k in ("gsm", "micron"):
        v = out[k]
        if v is not None and (isinstance(v, bool) or not isinstance(v, int)): bad.append(k)
    if out["location"] is not None and not isinstance(out["location"], str): bad.append("location")
    return bad

rng = random.Random(1)
chars = string.printable + "\u0966\u0967\u0968\u0939\u091c\u093e\u0930\U0001F600"
inputs = ["", " ", "\n", "x" * 100000, "\U0001F600" * 500, None, 123] + [
    "".join(rng.choice(chars) for _ in range(rng.randint(0, 200))) for _ in range(10000)]

start = time.time()
fails = 0
for s in inputs:
    try:
        v = check(parse_rfq(s))
        if v:
            fails += 1
            if fails <= 5:
                print("VIOLATION", v, repr(s)[:50])
    except Exception as e:
        fails += 1
        if fails <= 5:
            print("CRASH", e, repr(s)[:50])

dur = time.time() - start
print(f"Fuzz test: {len(inputs)} inputs in {dur:.2f}s, violations/crashes: {fails}")
