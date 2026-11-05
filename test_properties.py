"""
test_properties.py — Property-based and metamorphic tests for parse_rfq.
"""

import unittest
import string
import random
from parse import parse_rfq, VALID_CATEGORIES


class TestProperties(unittest.TestCase):

    def test_schema_guarantee(self):
        """Always exactly six keys and valid types, even on random/garbage inputs."""
        inputs = [
            "",
            "   ",
            "\n\t",
            "asdkjhasd 1283719823 @#%@#",
            "1234567890",
            "😂😂😂 📦📦📦",
            "need quote",
            "A" * 10000,  # very long string
            "None",
            "null",
        ]
        for text in inputs:
            res = parse_rfq(text)
            self.assertIsInstance(res, dict)
            self.assertEqual(
                sorted(res.keys()),
                sorted(["category", "quantity", "unit", "gsm", "micron", "location"])
            )
            self.assertIn(res["category"], VALID_CATEGORIES)
            self.assertIn(res["unit"], ("pcs", "kg", "mt"))
            if res["quantity"] is not None:
                self.assertIsInstance(res["quantity"], (int, float))
            if res["gsm"] is not None:
                self.assertIsInstance(res["gsm"], int)
            if res["micron"] is not None:
                self.assertIsInstance(res["micron"], int)
            if res["location"] is not None:
                self.assertIsInstance(res["location"], str)

    def test_never_raises_on_fuzz(self):
        """Fuzz testing with random character combinations never crashes."""
        rng = random.Random(42)
        chars = string.ascii_letters + string.digits + string.punctuation + " \t\n०१२३४५६७८९हज़ारबैग"
        for _ in range(500):
            length = rng.randint(0, 150)
            rand_str = "".join(rng.choice(chars) for _ in range(length))
            try:
                res = parse_rfq(rand_str)
                self.assertIsInstance(res, dict)
            except Exception as e:
                self.fail(f"parse_rfq raised exception {e} on input: {rand_str!r}")

    def test_invariance_case_and_padding(self):
        """Case variations, extra spaces, and padding with common noise phrases preserve output."""
        base = "bopp bags chahiye 40 hazaar, 65 gsm, Nagpur"
        expected = parse_rfq(base)

        variants = [
            "BOPP BAGS CHAHIYE 40 HAZAAR, 65 GSM, NAGPUR",
            "bopp   bags    chahiye    40    hazaar,   65   gsm,    Nagpur",
            "Hi sir, bopp bags chahiye 40 hazaar, 65 gsm, Nagpur pls urgent thanks",
            "bopp bags chahiye 40 hazaar , 65 gsm , Nagpur !!!",
            "bopp bags chahiye 40 hazaar, 65 gsm, Nagpur. Contact ASAP.",
        ]
        for v in variants:
            out = parse_rfq(v)
            self.assertEqual(out["category"], expected["category"])
            self.assertEqual(out["quantity"], expected["quantity"])
            self.assertEqual(out["unit"], expected["unit"])
            self.assertEqual(out["gsm"], expected["gsm"])
            self.assertEqual(out["micron"], expected["micron"])
            self.assertEqual(out["location"], expected["location"])

    def test_metamorphic_quantity_equivalences(self):
        """Metamorphic: 40 hazaar == 40000 == 40k == 0.4 lakh."""
        num_variants = [
            ("bopp bags 40 hazaar 65 gsm Nagpur", 40000),
            ("bopp bags 40000 65 gsm Nagpur", 40000),
            ("bopp bags 40k 65 gsm Nagpur", 40000),
            ("bopp bags 40,000 pcs 65 gsm Nagpur", 40000),
            ("bopp bags 2.5 lac 65 gsm Nagpur", 250000),
            ("bopp bags 2,50,000 65 gsm Nagpur", 250000),
            ("bopp bags 250k 65 gsm Nagpur", 250000),
        ]
        for text, expected_qty in num_variants:
            out = parse_rfq(text)
            self.assertEqual(out["quantity"], expected_qty, f"Failed for text: {text}")

    def test_unspaced_tokens_and_boundaries(self):
        """Verify unspaced digits and stuck units (500kg, 25mic, 500pcs, 65gsm, 2.5lac) and boundary preservation (15k, 12x18inch, 3ply, A4)."""
        cases = [
            ("need quote for 500kg shrink wrap 25 mic", {"quantity": 500, "unit": "kg", "micron": 25}),
            ("bopp bags 15k Jaipur", {"quantity": 15000, "unit": "pcs", "location": "Jaipur"}),
            ("bopp bags 2.5lac Jaipur", {"quantity": 250000, "unit": "pcs", "location": "Jaipur"}),
            ("corrugated box 12x18inch 500 pcs Jaipur", {"quantity": 500, "unit": "pcs", "category": "corrugated_box"}),
            ("corrugated box 3ply 500 pcs Jaipur", {"quantity": 500, "unit": "pcs", "category": "corrugated_box"}),
            ("A4 mono carton 500 pcs Jaipur", {"quantity": 500, "unit": "pcs", "category": "mono_carton"}),
            ("bopp bags 65gsm 500pcs Nagpur", {"quantity": 500, "unit": "pcs", "gsm": 65, "location": "Nagpur"}),
            ("stretch film 25mic 500kg Surat", {"quantity": 500, "unit": "kg", "micron": 25, "location": "Surat"}),
        ]
        for text, expected in cases:
            out = parse_rfq(text)
            for k, v in expected.items():
                self.assertEqual(out[k], v, f"Failed for {text!r} on key {k}: expected {v}, got {out[k]}")

    def test_metamorphic_location_substitution(self):
        """Replacing a city with another gazetteer city changes ONLY the location field."""
        cities = ["Nagpur", "Jaipur", "Surat", "Ahmedabad", "Indore", "Dubai", "Ludhiana"]
        base_template = "bopp bags chahiye 40 hazaar, 65 gsm, {city}"
        
        for c in cities:
            out = parse_rfq(base_template.format(city=c))
            self.assertEqual(out["category"], "bopp_bag")
            self.assertEqual(out["quantity"], 40000)
            self.assertEqual(out["unit"], "pcs")
            self.assertEqual(out["gsm"], 65)
            self.assertIsNone(out["micron"])
            self.assertEqual(out["location"], c)


if __name__ == "__main__":
    unittest.main()
