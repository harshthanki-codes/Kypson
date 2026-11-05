import json, time, random, string
from parse import parse_rfq

CATS = {"bopp_bag","woven_sack","corrugated_box","pouch","film","mono_carton","fibc"}
KEYS = {"category","quantity","unit","gsm","micron","location"}

def check(out):
    """Return a list of contract violations for one parse_rfq output."""
    bad = []
    if not isinstance(out, dict) or set(out) != KEYS:
        return ["keys"]
    if out["category"] not in CATS: bad.append("category")
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
fails = 0
for s in inputs:
    try:
        v = check(parse_rfq(s))
        if v:
            fails += 1; print("VIOLATION", v, repr(s)[:40])
    except Exception as e:
        fails += 1; print("RAISED", type(e).__name__, repr(s)[:40])
print(f"fuzz failures: {fails} / {len(inputs)}")
t = time.perf_counter()
for line in open("my_tests.jsonl", encoding="utf-8"):
    parse_rfq(json.loads(line)["text"])
print(f"my_tests time: {time.perf_counter()-t:.3f}s")
