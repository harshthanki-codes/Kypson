#!/usr/bin/env python3
"""
score.py — Local test runner for parse_rfq.

Reads a JSONL file of {"text": ..., "expected": {...}} lines,
runs parse_rfq on each, compares per-field, and prints accuracy.

Usage:  python score.py my_tests.jsonl
"""

import json
import sys
import time
from parse import parse_rfq


def fields_match(expected, actual, field):
    """Compare a single field between expected and actual output."""
    e = expected.get(field)
    a = actual.get(field)

    # Both None / null
    if e is None and a is None:
        return True

    # One is None, other is not
    if e is None or a is None:
        return False

    # Numeric fields: compare values (int vs float tolerance)
    if field in ("quantity", "gsm", "micron"):
        try:
            return abs(float(e) - float(a)) < 0.01
        except (TypeError, ValueError):
            return False

    # String fields: case-insensitive exact match
    if isinstance(e, str) and isinstance(a, str):
        return e.strip().lower() == a.strip().lower()

    return e == a


def main():
    if len(sys.argv) < 2:
        print("Usage: python score.py <tests.jsonl>")
        sys.exit(1)

    test_file = sys.argv[1]
    all_fields = ["category", "quantity", "unit", "gsm", "micron", "location"]

    # Counters
    total = 0
    field_correct = {f: 0 for f in all_fields}
    all_correct = 0
    failures = []

    start = time.time()

    with open(test_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"  SKIP line {line_num}: invalid JSON")
                continue

            text = row.get("text", "")
            expected = row.get("expected", {})
            actual = parse_rfq(text)
            total += 1

            row_ok = True
            wrong_fields = []
            for f_name in all_fields:
                if fields_match(expected, actual, f_name):
                    field_correct[f_name] += 1
                else:
                    row_ok = False
                    wrong_fields.append(f_name)

            if row_ok:
                all_correct += 1
            else:
                failures.append({
                    "line": line_num,
                    "text": text[:80],
                    "wrong": wrong_fields,
                    "expected": expected,
                    "actual": actual,
                })

    elapsed = time.time() - start

    # ── Print results ──
    print(f"\n{'='*60}")
    print(f"  Score Report: {test_file}")
    print(f"{'='*60}")
    print(f"  Total examples : {total}")
    print(f"  Exact match    : {all_correct}/{total}  ({100*all_correct/max(total,1):.1f}%)")
    print(f"  Time           : {elapsed:.2f}s")
    print()
    print("  Per-field accuracy:")
    for f_name in all_fields:
        pct = 100 * field_correct[f_name] / max(total, 1)
        print(f"    {f_name:12s} : {field_correct[f_name]:3d}/{total}  ({pct:.1f}%)")
    print()

    if failures:
        print(f"  Failures ({len(failures)}):")
        print(f"  {'-'*56}")
        for fail in failures[:30]:  # Show up to 30
            safe_text = fail['text'].encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            print(f"  Line {fail['line']}: \"{safe_text}...\"")
            for wf in fail["wrong"]:
                print(f"    {wf}: expected={fail['expected'].get(wf)!r}  got={fail['actual'].get(wf)!r}")
            print()

    print(f"{'='*60}")
    return 0 if all_correct == total else 1


if __name__ == "__main__":
    sys.exit(main())
