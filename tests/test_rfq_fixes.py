"""Failing unit tests to reproduce real RFQ parsing bugs before applying general fixes.
Written for Phase 4 of the Kypson RFQ parser evaluation.
"""
import unittest
from unittest import mock
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

    # ── 8. Guarded bare cardinals (tin/che/sat/aat excluded to prevent collisions) ──
    def test_tin_box_returns_quantity_500(self):
        r = parse_rfq("tin box 500 pcs Pune")
        self.assertEqual(r["quantity"], 500)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Pune")

    # ── 9. Guarded multi-product splitting (requires number in seg1 + different categories) ──
    def test_bopp_aur_woven_bags_keeps_quantity(self):
        r = parse_rfq("bopp aur woven bags 5000 pcs Nagpur")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Nagpur")

    def test_stretch_and_shrink_film_keeps_quantity(self):
        r = parse_rfq("stretch and shrink film 500 kg Pune")
        self.assertEqual(r["category"], "film")
        self.assertEqual(r["quantity"], 500)
        self.assertEqual(r["unit"], "kg")
        self.assertEqual(r["location"], "Pune")

    def test_bopp_and_woven_sack_keeps_quantity(self):
        r = parse_rfq("bopp and woven sack 1 lakh Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 100000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Surat")

    # ── 10. MOQ / Minimum Order constraints ──
    def test_moq_with_higher_order_quantity(self):
        r = parse_rfq("MOQ 500 pcs hai lekin humko 10000 pcs chahiye Surat bopp bags 60 gsm")
        self.assertEqual(r["quantity"], 10000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["gsm"], 60)
        self.assertEqual(r["location"], "Surat")

    def test_moq_alone_returns_none(self):
        r = parse_rfq("bopp bags 65 gsm MOQ 500 pcs Nagpur")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["gsm"], 65)
        self.assertEqual(r["location"], "Nagpur")

    # ── 11. Multi-product with 'or' / 'ya' disjunctive delimiters ──
    def test_multi_product_or_delimiter(self):
        r = parse_rfq("need 2000 bopp bags 60 gsm or 500 kg stretch film 25 mic Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 60)
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Surat")

    def test_multi_product_ya_delimiter(self):
        r = parse_rfq("need 2000 bopp bags 60 gsm ya 500 kg stretch film 25 mic Surat")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 60)
        self.assertIsNone(r["micron"])
        self.assertEqual(r["location"], "Surat")

    # ── 12. Buyer-side 'min' wording vs supplier MOQ constraint ──
    def test_buyer_minimum_quantity_kept_when_alone(self):
        r = parse_rfq("need bopp bags minimum quantity 5000 pcs Nagpur")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Nagpur")

    def test_buyer_minimum_pcs_kept(self):
        r = parse_rfq("minimum 5000 pcs bopp bags Nagpur")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Nagpur")

    def test_buyer_min_qty_kept_when_alone(self):
        r = parse_rfq("min qty 2000 pcs jumbo bag Pune")
        self.assertEqual(r["category"], "fibc")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Pune")

    def test_buyer_min_dropped_when_another_quantity_exists(self):
        r = parse_rfq("min qty 500 pcs lekin humko 10000 pcs chahiye Surat bopp bags 60 gsm")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 10000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 60)
        self.assertEqual(r["location"], "Surat")

    def test_supplier_minimum_order_quantity_alone_returns_none(self):
        r = parse_rfq("bopp bags 65 gsm minimum order quantity 500 pcs Nagpur")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])
        self.assertEqual(r["gsm"], 65)
        self.assertEqual(r["location"], "Nagpur")

    # ── 13. English number words ──
    def test_english_number_words_five_thousand(self):
        r = parse_rfq("need five thousand corrugated boxes Delhi")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Delhi")

    def test_english_number_words_twenty_five_thousand(self):
        r = parse_rfq("twenty five thousand bopp bags Surat")
        self.assertEqual(r["quantity"], 25000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["location"], "Surat")

    def test_english_number_words_two_tonnes(self):
        r = parse_rfq("two tonnes stretch film Morbi")
        self.assertEqual(r["quantity"], 2)
        self.assertEqual(r["unit"], "mt")
        self.assertEqual(r["category"], "film")
        self.assertEqual(r["location"], "Morbi")

    # ── 14. Composite numerals & Hindi fractions ──
    def test_composite_numeral_1_lakh_20_hazaar(self):
        r = parse_rfq("need 1 lakh 20 hazaar bopp bags Surat")
        self.assertEqual(r["quantity"], 120000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["location"], "Surat")

    def test_composite_numeral_ek_lakh_paanch_hazaar(self):
        r = parse_rfq("ek lakh paanch hazaar woven sack Ahmedabad")
        self.assertEqual(r["quantity"], 105000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["location"], "Ahmedabad")

    def test_fraction_saade_teen_hazaar(self):
        r = parse_rfq("saade teen hazaar corrugated box Pune")
        self.assertEqual(r["quantity"], 3500)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Pune")

    # ── 15. Location: ALL-CAPS specs, sign-offs, per-word stopwords ──
    def test_location_all_caps_spec_not_joined(self):
        r = parse_rfq("BOPP BAGS 50000 PCS 70 GSM SAYAN")
        self.assertEqual(r["location"], "Sayan")

    def test_location_signoff_regards_not_location(self):
        r = parse_rfq("corrugated box 5000 pcs Regards Rajesh Kumar")
        self.assertIsNone(r["location"])

    def test_location_signoff_thanks_not_location(self):
        r = parse_rfq("need 10000 bags Thanks Amit")
        self.assertIsNone(r["location"])

    def test_location_good_morning_not_location(self):
        r = parse_rfq("5000 boxes Good Morning")
        self.assertIsNone(r["location"])

    def test_location_kindly_revert_not_location(self):
        r = parse_rfq("1000 pouches Kindly Revert")
        self.assertIsNone(r["location"])

    def test_location_unlisted_city_with_thanks(self):
        r = parse_rfq("500 kg film 25 mic Kovvur. Thanks")
        self.assertEqual(r["location"], "Kovvur")

    # ── 16. Explicit destination beats origin ──
    def test_destination_beats_origin_dakor(self):
        r = parse_rfq("pickup Surat, deliver to Dakor")
        self.assertEqual(r["location"], "Dakor")

    def test_destination_beats_origin_kuppam(self):
        r = parse_rfq("from Morbi plant send 10 ton stretch film to Kuppam")
        self.assertEqual(r["location"], "Kuppam")

    def test_destination_beats_origin_nilanga(self):
        r = parse_rfq("Delhi se Nilanga tak 5000 boxes")
        self.assertEqual(r["location"], "Nilanga")

    def test_destination_beats_origin_umarkhed(self):
        r = parse_rfq("supplier in Rajkot, our site in Umarkhed need 2000 bopp bags")
        self.assertEqual(r["location"], "Umarkhed")

    def test_destination_beats_origin_surat(self):
        r = parse_rfq("from factory in Ahmedabad dispatch 2000 boxes to Surat")
        self.assertEqual(r["location"], "Surat")

    # ── 17. Unlisted city placed FIRST with precision guards ──
    def test_city_first_kovvur(self):
        r = parse_rfq("Kovvur pouch 60 micron 75000")
        self.assertEqual(r["location"], "Kovvur")

    def test_city_first_hapur_colon(self):
        r = parse_rfq("Hapur: jumbo bag 500 pcs")
        self.assertEqual(r["location"], "Hapur")

    def test_city_first_nirmal_telangana(self):
        r = parse_rfq("Nirmal Telangana woven sack 10000 pcs")
        self.assertEqual(r["location"], "Nirmal")

    def test_city_first_precision_words_not_locations(self):
        non_cities = [
            "Please quote for 5000 boxes",
            "Hello need 10000 bopp bags",
            "Quote required for stretch film 500 kg",
            "Need 2000 corrugated boxes",
            "Required 5000 bopp bags",
            "Regarding quotation for 10000 woven sacks",
            "Sir please send price for 5000 boxes",
            "Urgent need 2000 boxes",
        ]
        for msg in non_cities:
            r = parse_rfq(msg)
            self.assertIsNone(r["location"], f"Expected None location for: {msg}")

    # ── 18. Negation & false deletion guards ──
    def test_negation_bopp_nahi_chahiye_woven_sack(self):
        r = parse_rfq("bopp bag nahi chahiye, woven sack chahiye 5000 pcs Surat")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Surat")

    def test_negation_dont_need_jumbo_need_pp_woven(self):
        r = parse_rfq("dont need jumbo bag. need pp woven bag 2000 pcs Pune")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["location"], "Pune")

    def test_negation_no_shrink_only_stretch(self):
        r = parse_rfq("no shrink film, only stretch film 25 mic 500 kg Morbi")
        self.assertEqual(r["category"], "film")
        self.assertEqual(r["quantity"], 500)
        self.assertEqual(r["unit"], "kg")
        self.assertEqual(r["micron"], 25)
        self.assertEqual(r["location"], "Morbi")

    def test_negation_guard_no_of_bags(self):
        r = parse_rfq("No of bags 5000 pcs corrugated box Delhi")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Delhi")

    def test_negation_guard_not_less_than(self):
        r = parse_rfq("not less than 5000 bags woven sack Surat")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["location"], "Surat")

    # ── 19. Past order vs current requirement ──
    def test_past_order_last_time_dropped(self):
        r = parse_rfq("last time 1000 pcs, now need 5000 pcs corrugated box Pune")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Pune")

    def test_past_order_earlier_dropped(self):
        r = parse_rfq("earlier 10 ton, this time 20 ton stretch film Morbi")
        self.assertEqual(r["quantity"], 20)
        self.assertEqual(r["unit"], "mt")
        self.assertEqual(r["category"], "film")
        self.assertEqual(r["location"], "Morbi")

    # ── 20. Comma split: requires quantities on both sides ──
    def test_comma_split_not_product_boundary_bag_for_25kg_rice(self):
        r = parse_rfq("need bag for 25 kg rice, bopp laminated 10000 pcs 90 gsm Nagpur")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["quantity"], 10000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["gsm"], 90)
        self.assertEqual(r["location"], "Nagpur")

    def test_comma_split_no_shrink_only_stretch_micron_and_qty(self):
        r = parse_rfq("no shrink film, only stretch film 20 mic 300 kg Kodad")
        self.assertEqual(r["category"], "film")
        self.assertEqual(r["quantity"], 300)
        self.assertEqual(r["unit"], "kg")
        self.assertEqual(r["micron"], 20)
        self.assertEqual(r["location"], "Kodad")

    # ── 21. Phone numbers, IDs, and order-weight vs bag size ──
    def test_phone_spaced_digits_not_quantity(self):
        r = parse_rfq("Contact 98765 43210 need corrugated box Surat")
        self.assertIsNone(r["quantity"])
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Surat")

    def test_phone_dashed_not_quantity(self):
        r = parse_rfq("+91-98250-12345 corrugated box Surat")
        self.assertIsNone(r["quantity"])
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Surat")

    def test_order_id_not_quantity(self):
        r = parse_rfq("order id 4521 woven sack 60 gsm 20000 pcs Surat")
        self.assertEqual(r["quantity"], 20000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["gsm"], 60)
        self.assertEqual(r["location"], "Surat")

    def test_quote_no_not_quantity(self):
        r = parse_rfq("Quote no 1023 need 5000 boxes Pune")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Pune")

    def test_10_ton_woven_sack_50kg_bags(self):
        r = parse_rfq("10 ton woven sack 50 kg bags Pune")
        self.assertEqual(r["quantity"], 10)
        self.assertEqual(r["unit"], "mt")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["location"], "Pune")

    # ── 22. Devanagari numbers and cities ──
    def test_devanagari_number_words(self):
        r = parse_rfq("बीस हजार बोरी चाहिए सूरत")
        self.assertEqual(r["quantity"], 20000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "woven_sack")
        self.assertEqual(r["location"], "Surat")

    def test_devanagari_lakh(self):
        r = parse_rfq("एक लाख कार्टन दिल्ली")
        self.assertEqual(r["quantity"], 100000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "corrugated_box")
        self.assertEqual(r["location"], "Delhi")

    def test_devanagari_city_pune(self):
        r = parse_rfq("50000 BOPP बैग चाहिए, 70 gsm, पुणे")
        self.assertEqual(r["quantity"], 50000)
        self.assertEqual(r["unit"], "pcs")
        self.assertEqual(r["category"], "bopp_bag")
        self.assertEqual(r["gsm"], 70)
        self.assertEqual(r["location"], "Pune")

    def test_devanagari_city_nashik(self):
        r = parse_rfq("10000 कार्टन नासिक")
        self.assertEqual(r["quantity"], 10000)
        self.assertEqual(r["location"], "Nashik")

    def test_devanagari_city_patna(self):
        r = parse_rfq("5000 पाउच पटना")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["location"], "Patna")

    # ── 23. Debug flag behavior ──
    def test_debug_flag_re_raises_on_error(self):
        # Normal call with invalid type returns default
        r = parse_rfq(12345)  # type: ignore
        self.assertEqual(r["category"], "corrugated_box")
        self.assertIsNone(r["quantity"])

        # Debug call re-raises if an unexpected internal exception is simulated
        with unittest.mock.patch("parse.normalize_text", side_effect=RuntimeError("Simulated bug")):
            with self.assertRaises(RuntimeError):
                parse_rfq("bopp bags 5000 pcs Pune", debug=True)
            # Without debug flag, it falls back safely to default
            r2 = parse_rfq("bopp bags 5000 pcs Pune", debug=False)
            self.assertEqual(r2["category"], "corrugated_box")
            self.assertIsNone(r2["quantity"])

    # ── 24. Mutation test coverage (kills mutants) ──
    def test_paune_arithmetic(self):
        r = parse_rfq("paune do lakh bopp bags Surat")
        self.assertEqual(r["quantity"], 175000)
        self.assertEqual(r["unit"], "pcs")

    def test_sawa_arithmetic(self):
        r = parse_rfq("sawa teen lakh bopp bags Surat")
        self.assertEqual(r["quantity"], 325000)
        self.assertEqual(r["unit"], "pcs")

    def test_pin_mask_at_end(self):
        r = parse_rfq("need 5000 Surat 395003")
        self.assertEqual(r["quantity"], 5000)
        self.assertEqual(r["location"], "Surat")

    def test_price_budget_mask(self):
        r = parse_rfq("need 2000 budget 50000 Pune")
        self.assertEqual(r["quantity"], 2000)
        self.assertEqual(r["location"], "Pune")

    def test_dimension_mask(self):
        r = parse_rfq("size 2000 x 3000 need 500 Ahmedabad")
        self.assertEqual(r["quantity"], 500)
        self.assertEqual(r["location"], "Ahmedabad")

    def test_freight_logistics_mask(self):
        r = parse_rfq("corrugated boxes chahiye 2 truck load Surat")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])

    def test_date_mask(self):
        r = parse_rfq("need boxes by 15 Aug Surat")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])

    def test_lead_time_mask(self):
        r = parse_rfq("need boxes in 10 days Surat")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])

    def test_capacity_swl_mask(self):
        r = parse_rfq("jumbo bag 1 ton SWL Surat")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["unit"])

    def test_dest_delivery_beats_origin(self):
        r = parse_rfq("from Morbi plant send 10 ton to Kuppam")
        self.assertEqual(r["location"], "Kuppam")

    def test_dest_delivery_without_to(self):
        r = parse_rfq("ex-factory Vapi, delivery Mahuva, 10000 boxes")
        self.assertEqual(r["location"], "Mahuva")

    # ── 25. Precision probe guards ──
    def test_probe_moq_with_order_quantity_keeps_location_none(self):
        r = parse_rfq("MOQ 500 pcs hai lekin humko 10000 pcs chahiye")
        self.assertEqual(r["quantity"], 10000)
        self.assertIsNone(r["location"])

    def test_probe_signoff_regards_person_name_not_location(self):
        r = parse_rfq("Regards Rajesh Sharma")
        self.assertIsNone(r["location"])
        self.assertIsNone(r["quantity"])

    def test_probe_kindly_revert_not_location(self):
        r = parse_rfq("Kindly revert with best rates")
        self.assertIsNone(r["location"])

    def test_probe_gstin_not_location(self):
        r = parse_rfq("GSTIN 24AAACH7409R1ZZ")
        self.assertIsNone(r["location"])

    def test_probe_order_id_alone_not_quantity(self):
        r = parse_rfq("order id 4521")
        self.assertIsNone(r["quantity"])











if __name__ == "__main__":
    unittest.main()
