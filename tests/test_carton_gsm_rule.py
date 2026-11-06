"""
test_carton_gsm_rule.py — Unit tests for the carton GSM classification assumption:
1. Plain 'box' or 'carton' with GSM >= 200 is classified as mono_carton.
2. Plain 'box' with GSM < 200 (e.g. 150 gsm) remains corrugated_box.
3. Explicit corrugated descriptors ('corrugated', ply) remain corrugated_box regardless of GSM.
"""
import unittest
from parse import parse_rfq

class TestCartonGSMRule(unittest.TestCase):

    def test_plain_box_low_gsm_remains_corrugated(self):
        """Plain box with GSM < 200 must remain corrugated_box."""
        cases = [
            "box 150 gsm 5000 pcs Mumbai",
            "box 120 gsm 10000 pcs Delhi",
            "plain box 180 gsm 2000 nos Pune",
        ]
        for text in cases:
            r = parse_rfq(text)
            self.assertEqual(
                r["category"],
                "corrugated_box",
                f"Expected corrugated_box for {text!r}, got {r['category']!r}"
            )

    def test_plain_carton_high_gsm_becomes_mono_carton(self):
        """Carton with GSM >= 200 without corrugated markers is classified as mono_carton."""
        cases = [
            ("carton 250 gsm 5000 pcs Mumbai", "mono_carton"),
            ("carton 300 gsm 10000 pcs Ahmedabad", "mono_carton"),
            ("carton 220 gsm 20000 pcs Jaipur", "mono_carton"),
            ("mono carton 350 gsm 15k pcs Baddi", "mono_carton"),
        ]
        for text, expected_cat in cases:
            r = parse_rfq(text)
            self.assertEqual(
                r["category"],
                expected_cat,
                f"Expected {expected_cat!r} for {text!r}, got {r['category']!r}"
            )

    def test_explicit_corrugated_with_high_gsm_stays_corrugated(self):
        """Explicit corrugated markers (corrugated, ply) must never become mono_carton."""
        cases = [
            "corrugated box 250 gsm 5000 pcs Surat",
            "5 ply corrugated carton 300 gsm 2000 pcs Indore",
            "3 ply box 220 gsm 1000 pcs Bhiwandi",
        ]
        for text in cases:
            r = parse_rfq(text)
            self.assertEqual(
                r["category"],
                "corrugated_box",
                f"Expected corrugated_box for {text!r}, got {r['category']!r}"
            )

if __name__ == "__main__":
    unittest.main()
