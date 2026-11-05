"""Cross-evaluate MY parse.py and REF parse.py on all JSONL files.
Usage: python cross_eval.py
Never modifies any source file. Uses importlib to load both parsers cleanly.
"""
import importlib.util, json, sys, pathlib, re

ROOT   = pathlib.Path(__file__).parent
REF    = ROOT / "ref_solution" / "rfq_submission"
KEYS   = ["category", "quantity", "unit", "gsm", "micron", "location"]

# ── load MY parse_rfq ────────────────────────────────────────────────────────
spec_my = importlib.util.spec_from_file_location("my_parse", ROOT / "parse.py")
mod_my  = importlib.util.module_from_spec(spec_my); spec_my.loader.exec_module(mod_my)
my_parse = mod_my.parse_rfq

# ── load REF parse_rfq ───────────────────────────────────────────────────────
spec_ref = importlib.util.spec_from_file_location("ref_parse", REF / "parse.py")
mod_ref  = importlib.util.module_from_spec(spec_ref); spec_ref.loader.exec_module(mod_ref)
ref_parse = mod_ref.parse_rfq

# ── helpers ──────────────────────────────────────────────────────────────────
def same(a, b, k):
    if a is None and b is None:  return True
    if a is None or b is None:   return False
    if k == "location" and isinstance(a,str) and isinstance(b,str):
        return a.strip().lower() == b.strip().lower()
    if k == "quantity":
        try: return abs(float(a)-float(b)) < 1e-6
        except: return False
    return a == b

def score_one(got, exp):
    return {k: same(got[k], exp[k], k) for k in KEYS}

def load_jsonl(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def summarise(name, rows, field_ok_my, field_ok_ref, n_my, n_ref, my_full, ref_full):
    print(f"\n{'='*60}")
    print(f"FILE: {name}   ({len(rows)} examples)")
    print(f"{'='*60}")
    print(f"{'Field':<12} {'MINE':>8} {'REF':>8}")
    print(f"{'-'*30}")
    for k in KEYS:
        pm = 100*field_ok_my[k]/len(rows)
        pr = 100*field_ok_ref[k]/len(rows)
        flag = " <" if pm < pr else (" >" if pm > pr else "")
        print(f"  {k:<10} {pm:>7.1f}% {pr:>7.1f}%{flag}")
    print(f"  {'FULL':<10} {100*my_full/len(rows):>7.1f}% {100*ref_full/len(rows):>7.1f}%")

# ── datasets ─────────────────────────────────────────────────────────────────
datasets = [
    ("my_tests.jsonl",         ROOT / "my_tests.jsonl"),
    ("holdout.jsonl (mine)",   ROOT / "holdout.jsonl"),
    ("red_team.jsonl (mine)",  ROOT / "red_team.jsonl"),
    ("ref/my_tests.jsonl",     REF  / "my_tests.jsonl"),
    ("ref/holdout.jsonl",      REF  / "holdout.jsonl"),
    ("ref/redteam.jsonl",      REF  / "redteam.jsonl"),
]

disagreements = []

for label, path in datasets:
    if not path.exists():
        print(f"\nSKIP (not found): {label}")
        continue
    rows = load_jsonl(path)
    n = len(rows)
    fok_my  = dict.fromkeys(KEYS, 0)
    fok_ref = dict.fromkeys(KEYS, 0)
    full_my = full_ref = 0
    for r in rows:
        text = r["text"]
        exp  = r["expected"]
        gm   = my_parse(text)
        gr   = ref_parse(text)
        om   = score_one(gm, exp)
        or_  = score_one(gr, exp)
        for k in KEYS:
            fok_my[k]  += om[k]
            fok_ref[k] += or_[k]
        if all(om.values()): full_my  += 1
        if all(or_.values()): full_ref += 1
        # collect disagreements
        for k in KEYS:
            if om[k] != or_[k]:  # one right, one wrong
                disagreements.append({
                    "file": label, "text": text, "field": k,
                    "expected": exp[k],
                    "mine": gm[k], "ref": gr[k],
                    "mine_ok": om[k], "ref_ok": or_[k],
                })
    summarise(label, rows, fok_my, fok_ref, n, n, full_my, full_ref)

# ── disagreement table ────────────────────────────────────────────────────────
print(f"\n\n{'='*60}")
print("DISAGREEMENTS (mine vs ref, at least one is wrong)")
print(f"{'='*60}")
print(f"{'File':<22} {'Field':<10} {'Expected':<20} {'Mine':<20} {'Ref':<20} {'Who wins'}")
print("-"*110)
for d in disagreements:
    exp_s  = str(d['expected'])[:18]
    mine_s = str(d['mine'])[:18]
    ref_s  = str(d['ref'])[:18]
    winner = "MINE" if d['mine_ok'] and not d['ref_ok'] else ("REF" if d['ref_ok'] and not d['mine_ok'] else "BOTH_WRONG")
    print(f"  {d['file']:<20} {d['field']:<10} {exp_s:<20} {mine_s:<20} {ref_s:<20} {winner}")
    print(f"    text: {d['text'][:90]}")
print(f"\nTotal disagreements: {len(disagreements)}")
