"""Failing unit tests to reproduce real RFQ parsing bugs before applying general fixes.
Written for Phase 4 of the Kypson RFQ parser evaluation.
"""
import unittest
from parse import parse_rfq

class TestRFQFixes(unittest.TestCase):
    # ── 1. Fill weight vs order quantity ──
    def test_fill_weight_cement_bag_50kg_5lakh(self):
        r = parse_rfq("cement bag 50kg 5 lakh Ludhiana")
        self.assertEqual(r["quantity"], 500000)
        self.assertEqual(r["unit"], "pcs")

    def test_fill_weight_woven_bag_25kg_ke_2lakh(self):
        r = parse_rfq("woven bag 25 kg ke 2 lakh Meerut")
        self.assertEqual(r["quantity"], 200000)
        self.assertEqual(r["unit"], "pcs")

    def test_fill_weight_50kg_bori_1lakh(self):
        r = parse_rfq("50 kg bori 1 lakh")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["quantity"], 100000)
        self.assertEqual(r["unit"], "pcs")

    def test_fill_weight_pp_bags_25kg_10000(self):
        r = parse_rfq("PP bags 25 kg 10000")
        self.assertEqual(r["quantity"], 10000)
        self.assertEqual(r["unit"], "pcs")

    # ── 2. Gram package size masking ──
    def test_pouch_500gm_pack_size_not_quantity(self):
        r = parse_rfq("pouch 500 gm 20000 pcs Surat")
        self.assertEqual(r["quantity"], 20000)
        self.assertEqual(r["unit"], "pcs")

    def test_stand_up_pouch_250gm_size_not_quantity(self):
        r = parse_rfq("stand up pouch 250 gm 5000 pcs Hyderabad")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")

    # ── 3. Bare category keyword classification ──
    def test_bare_bopp_classification(self):
        r = parse_rfq("bopp 5000 pcs")
        self.assertEqual(r["category"], "bopp_bag")

    def test_bopp_with_gsm_and_qty(self):
        r = parse_rfq("BOPP 70 GSM 25 KG 60,000 PCS SILIGURI")
        self.assertEqual(r["category"], "bopp_bag")

    def test_bare_jumbo_classification(self):
        r = parse_rfq("jumbo 800 pcs Germany")
        self.assertEqual(r["category"], "fibc")

    def test_bare_shrink_classification(self):
        r = parse_rfq("shrink 25 mic 500 kg")
        self.assertEqual(r["category"], "film")

    # ── 4. Origin vs Destination delivery location ──
    def test_from_mumbai_deliver_pune(self):
        r = parse_rfq("shrink film 25 mic 800 kg from Mumbai deliver Pune")
        self.assertEqual(r["location"], "Pune")

    # ── 5. Unseen city fallback at end of sentence ──
    def test_unseen_city_end_pithampur(self):
        r = parse_rfq("mono carton 1 lakh 350 gsm Pithampur")
        self.assertEqual(r["location"], "Pithampur")

    def test_unseen_city_end_chittoor(self):
        r = parse_rfq("woven sack 5 ton Chittoor")
        self.assertEqual(r["location"], "Chittoor")

    def test_unseen_city_end_bhiwadi(self):
        r = parse_rfq("shrink film 25 mic 10 mt Bhiwadi")
        self.assertEqual(r["location"], "Bhiwadi")

    # ── 6. Multi-product messages (first product attributes only + shared location) ──
    def test_multi_product_bopp_and_stretch_film(self):
        r = parse_rfq("need 2000 bopp bags 60 gsm and 500 kg stretch film 25 mic delivery to Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 60)
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Surat")

    def test_multi_product_first_segment_no_quantity(self):
        r = parse_rfq("need bopp bags 65 gsm and 500 kg stretch film 25 mic delivery to Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])
        self.assertEqual(r["gsm"], 65)
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Surat")

    def test_multi_product_with_comma_delimiter(self):
        r = parse_rfq("2000 bopp bags 60 gsm, 500 kg stretch film 25 mic, delivery Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 60)
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Surat")

    # ── 7. Bare Hindi cardinals (followed by product noun or unit word, not English prose) ──
    def test_bare_hindi_cardinal_char_carton_box(self):
        r = parse_rfq("humko char carton box chahiye Pune")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["quantity"], 4)
        self.assertEqual(r["unit"], "pcs")
        self.assertIsNone(r["gsm"])
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Pune")

    def test_bare_hindi_cardinal_do_box(self):
        r = parse_rfq("do box chahiye Delhi")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["quantity"], 2)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Delhi")

    def test_hindi_cardinal_do_hazaar_still_works(self):
        r = parse_rfq("do hazaar corrugated boxes Ludhiana")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Ludhiana")

    def test_english_prose_do_send_quote_not_treated_as_quantity(self):
        r = parse_rfq("do send quote for bopp bags 65 gsm Nagpur")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["gsm"], 65)
        self.assertEqual(r["location"], "Nagpur")

    def test_hindi_verb_bhej_do_not_treated_as_quantity(self):
        r = parse_rfq("fibc jumbo bag catalogue aur price list bhej do")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])
        self.assertEqual(r["category"], "fibc")

if __name__ == "__main__":
    unittest.main()
