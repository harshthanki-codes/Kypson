"""
Verify that compiled regex gazetteer matching gives 100% IDENTICAL
results to the baseline linear iteration over the gazetteer list on every single message
in every .jsonl file.
"""
import json, glob, os, sys, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import parse

def find_cities_linear(text: str) -> list[str]:
    """Unoptimized linear baseline: search for each gazetteer entry individually."""
    matches = []
    for city in parse._GAZETTEER_LIST:
        for m in re.finditer(r"\b" + re.escape(city) + r"\b", text, re.I):
            matches.append((m.start(), m.end(), m.group()))
    matches.sort(key=lambda x: (x[0], -len(x[2])))
    return [m[2] for m in matches]

def find_cities_regex(text: str) -> list[str]:
    """Optimized compiled regex matching."""
    return [m.group() for m in parse._CITY_REGEX.finditer(text)]

differences = []
total = 0

jsonl_files = sorted(glob.glob("*.jsonl") + glob.glob("eval/*.jsonl"))
for fp in jsonl_files:
    with open(fp, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = row.get("text", row.get("message", ""))
            if not text:
                continue
            norm = parse.normalize_text(text)
            if not norm:
                continue
            total += 1
            linear_matches = find_cities_linear(norm)
            regex_matches = find_cities_regex(norm)
            if linear_matches != regex_matches:
                differences.append({
                    "file": fp,
                    "line": i,
                    "text": text,
                    "linear": linear_matches,
                    "regex": regex_matches,
                })

print(f"Total messages tested across all .jsonl files: {total}")
print(f"Differences between unoptimized linear scan and compiled regex: {len(differences)}")
if differences:
    for d in differences[:5]:
        print(f"DIFF: {d['file']}:{d['line']} - text: {d['text']!r}")
        print(f"  LINEAR: {d['linear']!r}")
        print(f"  REGEX:  {d['regex']!r}")
else:
    print("PROVEN: Exactly 0 differences. Behaviour is 100% identical.")
