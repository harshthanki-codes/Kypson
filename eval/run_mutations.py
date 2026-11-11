"""run_mutations.py — Automated mutation testing of 20 critical parsing rules."""
import subprocess
import sys

mutants = [
    ("1. paune arithmetic", "card_val - 0.25", "card_val + 0.25"),
    ("2. sawa arithmetic", "card_val + 0.25", "card_val - 0.25"),
    ("3. saadhe arithmetic", "card_val + 0.5", "card_val + 0.25"),
    ("4. phone mask", r"(?:\+?91[\s\-]?|0)?[6-9](?:\d[\s\-]?){9}\b", r"999999999999999"),
    ("5. PIN mask", r"\b[1-8]\d{5}\s*$", r"999999999999999"),
    ("6. price/rate mask", r"\b(?:rate|price|rs|inr|budget|cost)\s*[:\-]?\s*(\d+(?:\.\d+)?)", r"NOMATCHPRICE"),
    ("7. dimension mask", r"\b\d+(?:\.\d+)?\s*(?:x|×|\*|by)\s*\d+(?:\.\d+)?", r"NOMATCHDIM"),
    ("8. freight mask", r"(?:truck|container|tempo|trailer|gadi|gaadi|trolley|lorry|fcl|lcl)", r"NOMATCHFREIGHT"),
    ("9. ply mask", r"\b\d{1,2}\s*ply\b", r"NOMATCHPLY"),
    ("10. date mask", r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", r"NOMATCHDATE"),
    ("11. lead times mask", r"\b\d+\s*(?:days?|weeks?|months?)\b", r"NOMATCHLEAD"),
    ("12. gram pack mask", r"(?:gm|gms|grams?|g\b|ml|ltrs?|litres?|liters?)", r"NOMATCHGRAM"),
    ("13. fill weight mt guard", 'candidate["unit"] == "mt" and category in (', 'False and candidate["unit"] == "mt" and category in ('),
    ("14. capacity check", r"(?:capacity|cap|swl|load|holding|carrying|holds)", r"NOMATCHCAP"),
    ("15. dest to pattern", r"(?i:\bto\s+)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*(?:[.,!?]|$)", r"NOMATCHTO"),
    ("16. dest deliver pattern", r"deliver(?:y)?|dispatch|send|ship|destination", r"NOMATCHDELIV"),
    ("17. composite numerals", r"_composite_numerals(text)", r"text"),
    ("18. english numbers", r"_english_numbers(text)", r"text"),
    ("19. trailing signoff filter", r"_SIGNOFF_TRAILING_RE.sub", r"str"),
    ("20. order ID mask", r'r"\s*(?:id|no|num|number|#|code)\s*[:\-#]?\s*[A-Z0-9-]*\d[A-Z0-9-]*\b"', r'r" NOMATCHORDERID"'),
]

with open("parse.py", "r", encoding="utf-8") as f:
    orig_code = f.read()

results = []
try:
    for name, orig_sub, mut_sub in mutants:
        if orig_sub not in orig_code:
            results.append((name, "ERROR: Target string not found in parse.py"))
            continue
        mutated_code = orig_code.replace(orig_sub, mut_sub, 1)
        with open("parse.py", "w", encoding="utf-8") as f:
            f.write(mutated_code)

        # Check against tests/
        res = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True)
        if res.returncode != 0:
            results.append((name, "KILLED (unit tests)"))
            continue

        # Check against test_properties.py
        res_prop = subprocess.run([sys.executable, "-m", "unittest", "test_properties.py"], capture_output=True, text=True)
        if res_prop.returncode != 0:
            results.append((name, "KILLED (property tests)"))
            continue

        # Check against my_tests.jsonl
        res_my = subprocess.run([sys.executable, "score.py", "my_tests.jsonl"], capture_output=True, text=True)
        if "100.0%" not in res_my.stdout.splitlines()[-1]:
            results.append((name, "KILLED (my_tests.jsonl)"))
            continue

        # Check against holdout.jsonl
        res_hold = subprocess.run([sys.executable, "score.py", "holdout.jsonl"], capture_output=True, text=True)
        if "100.0%" not in res_hold.stdout.splitlines()[-1]:
            results.append((name, "KILLED (holdout.jsonl)"))
            continue

        results.append((name, "SURVIVED"))
finally:
    with open("parse.py", "w", encoding="utf-8") as f:
        f.write(orig_code)

print("=" * 60)
print("MUTATION TESTING REPORT (20 RULES):")
print("=" * 60)
for name, status in results:
    print(f"{name:32}: {status}")
killed = sum(1 for _, s in results if "KILLED" in s)
print(f"\nTotal Mutants: {len(results)} | Killed: {killed} | Survivors: {len(results) - killed}")
