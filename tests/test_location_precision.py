"""
test_location_precision.py — Tests ensuring location precision:
1. Messages with no delivery location return location=None.
2. Ambiguous common words / commodity terms (mandi, una, pali, ara, bhind, sagar)
   are NOT falsely extracted as locations when lowercase and lacking prepositional context.
3. Ambiguous words with proper capitalisation or prepositional context ARE extracted.
"""
import unittest
import json
import glob
import os
from parse import parse_rfq

class TestLocationPrecision(unittest.TestCase):

    def test_null_location_messages_remain_none(self):
        """Messages with null expected location must return None."""
        test_cases = [
            "need quote for 500 kg shrink wrap 25 mic",
            "need quote for bopp bags 65 gsm",
            "fibc jumbo bag catalogue aur price list bhej do",
            "stretch wrap film best rate required",
            "corrugated boxes rate list chahiye urgently",
            "bopp bag 65 gsm quotation chahiye",
            "fibc bags price list please",
            "bopp bags manufacturer contact details required",
            "corrugated boxes wholesale price list please",
        ]
        for text in test_cases:
            res = parse_rfq(text)
            self.assertIsNone(
                res["location"],
                f"Expected location=None for text {text!r}, got {res['location']!r}"
            )

    def test_common_words_not_treated_as_locations_without_context(self):
        """Common commodity / market terms without capitalisation or preposition must not be locations."""
        false_positive_cases = [
            "grain mandi ke liye bopp bags 10000 pcs",
            "need 5000 pcs bopp bags from grain mandi",
            "sabzi mandi packaging bags 20000 pcs",
            "una quality pouch 5000 pcs",
            "pali packing material 1000 pcs",
            "ara mill boxes 500 pcs",
            "bhind rate quotation 2000 pcs",
            "sagar enterprise corrugated box 5000 pcs",
        ]
        for text in false_positive_cases:
            res = parse_rfq(text)
            self.assertIsNone(
                res["location"],
                f"Expected None for common word in {text!r}, got {res['location']!r}"
            )

    def test_ambiguous_words_with_capitalisation_or_preposition_are_extracted(self):
        """Ambiguous words with capitalisation or prepositional cues must be correctly extracted."""
        true_positive_cases = [
            ("need 5000 pcs bopp bags delivery Mandi", "Mandi"),
            ("bopp bags 5000 pcs in una", "Una"),
            ("paanch hazaar jumbo bags 1 ton SWL Pali", "Pali"),
            ("stretch wrap film 25 mic, 10 ton, dispatch to Pali", "Pali"),
            ("boxes 500 pcs delivery Bhind", "Bhind"),
            ("pouch 10000 pcs Sagar", "Sagar"),
            ("bags 20000 pcs in Ara", "Ara"),
        ]
        for text, expected_loc in true_positive_cases:
            res = parse_rfq(text)
            self.assertEqual(
                res["location"],
                expected_loc,
                f"Expected {expected_loc!r} for {text!r}, got {res['location']!r}"
            )

if __name__ == "__main__":
    unittest.main()
