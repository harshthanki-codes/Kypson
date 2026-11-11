"""
Ablation test: measure score and location accuracy on fresh_eval100.jsonl
and simulation_fresh100.jsonl with:
  1. cities.txt ENABLED (full 1,708-entry gazetteer)
  2. cities.txt DISABLED (fallback to embedded ~357-city list)
  3. All gazetteer DISABLED (empty gazetteer, contextual preposition/fallback only)
"""
import json, sys, os, re, importlib
from pathlib import Path

os.chdir(r"C:\Users\Admin\Desktop\Kypson")
sys.path.insert(0, r"C:\Users\Admin\Desktop\Kypson")

import parse
from score import same, FIELDS

def score_dataset(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    per_field = {f: 0 for f in FIELDS}
    all_ok = 0
    for r in rows:
        out = parse.parse_rfq(r["text"])
        ok = True
        for f in FIELDS:
            if same(f, out.get(f), r["expected"][f]):
                per_field[f] += 1
            else:
                ok = False
        all_ok += ok
    n = len(rows)
    return n, per_field, all_ok

def run_ablation(dataset_path):
    print(f"\n========================================================")
    print(f"Dataset: {dataset_path}")
    print(f"========================================================")

    # 1. Default (cities.txt enabled)
    # Ensure standard gazetteer loaded
    lookup, s_list = parse._load_gazetteer()
    parse._GAZETTEER_SET = lookup
    parse._GAZETTEER_LIST = s_list
    parse._CITY_REGEX = re.compile(r"\b(" + "|".join(re.escape(e) for e in s_list) + r")\b", re.I)

    n, pf, all_ok = score_dataset(dataset_path)
    print(f"--- 1. cities.txt ENABLED ({len(s_list)} entries) ---")
    print(f"  location:   {pf['location']:3d}/{n} ({pf['location']/n:6.1%})")
    print(f"  ALL FIELDS: {all_ok:3d}/{n} ({all_ok/n:6.1%})")

    # 2. cities.txt DISABLED (fallback to embedded list)
    # Temporarily hide cities.txt
    real_path = Path(parse.__file__).parent / "cities.txt"
    temp_path = Path(parse.__file__).parent / "cities.txt.disabled"
    try:
        if real_path.exists():
            real_path.rename(temp_path)
        lookup_emb, s_list_emb = parse._load_gazetteer()
        parse._GAZETTEER_SET = lookup_emb
        parse._GAZETTEER_LIST = s_list_emb
        parse._CITY_REGEX = re.compile(r"\b(" + "|".join(re.escape(e) for e in s_list_emb) + r")\b", re.I)

        n, pf_emb, all_ok_emb = score_dataset(dataset_path)
        print(f"--- 2. cities.txt DISABLED (Embedded fallback: {len(s_list_emb)} entries) ---")
        print(f"  location:   {pf_emb['location']:3d}/{n} ({pf_emb['location']/n:6.1%})")
        print(f"  ALL FIELDS: {all_ok_emb:3d}/{n} ({all_ok_emb/n:6.1%})")
    finally:
        if temp_path.exists():
            temp_path.rename(real_path)

    # 3. All gazetteer disabled (empty gazetteer)
    parse._GAZETTEER_SET = set()
    parse._GAZETTEER_LIST = []
    parse._CITY_REGEX = re.compile(r"(?!)")  # never matches

    n, pf_zero, all_ok_zero = score_dataset(dataset_path)
    print(f"--- 3. ZERO GAZETTEER (pure regex/preposition fallback) ---")
    print(f"  location:   {pf_zero['location']:3d}/{n} ({pf_zero['location']/n:6.1%})")
    print(f"  ALL FIELDS: {all_ok_zero:3d}/{n} ({all_ok_zero/n:6.1%})")

    # Restore default
    lookup, s_list = parse._load_gazetteer()
    parse._GAZETTEER_SET = lookup
    parse._GAZETTEER_LIST = s_list
    parse._CITY_REGEX = re.compile(r"\b(" + "|".join(re.escape(e) for e in s_list) + r")\b", re.I)

if __name__ == "__main__":
    run_ablation("fresh_eval100.jsonl")
    run_ablation("simulation_fresh100.jsonl")
