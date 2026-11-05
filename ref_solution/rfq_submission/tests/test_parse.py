"""Unit tests. Run: python -m unittest discover -s tests -v   (from the project folder)"""
import json, os, random, string, sys, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parse import parse_rfq, CATEGORIES

KEYS = {"category", "quantity", "unit", "gsm", "micron", "location"}
ROOT = os.path.join(os.path.dirname(__file__), "..")


def check_contract(tc, r):
    tc.assertEqual(set(r), KEYS)
    tc.assertIn(r["category"], CATEGORIES)
    tc.assertTrue(r["quantity"] is None or (isinstance(r["quantity"], (int, float)) and not isinstance(r["quantity"], bool)))
    tc.assertIn(r["unit"], ("pcs", "kg", "mt", None))
    for k in ("gsm", "micron"):
        tc.assertTrue(r[k] is None or isinstance(r[k], int))
    tc.assertTrue(r["location"] is None or isinstance(r["location"], str))


class TestWorkedExamples(unittest.TestCase):
    def test_examples_from_brief(self):
        self.assertEqual(parse_rfq("bopp bags chahiye 40 hazaar, 65 gsm, Nagpur"),
            {"category": "bopp_bag", "quantity": 40000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Nagpur"})
        self.assertEqual(parse_rfq("jumbo bag 1000 kg capacity, 500 pcs, Vadodara"),
            {"category": "fibc", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Vadodara"})
        self.assertEqual(parse_rfq("need quote for 500 kg shrink wrap 25 mic"),
            {"category": "film", "quantity": 500, "unit": "kg", "gsm": None, "micron": 25, "location": None})


class TestNumbers(unittest.TestCase):
    def q(self, s):
        r = parse_rfq(s); return r["quantity"], r["unit"]

    def test_indian_formats(self):
        for s, want in [("bopp bags 1 lakh", 100000), ("bopp bags 2.5 lac", 250000), ("bopp bags 15K", 15000),
                        ("bopp bags 1,50,000", 150000), ("bopp bags 40 hazaar", 40000), ("bopp bags do hazaar", 2000),
                        ("bopp bags dedh lakh", 150000), ("bopp bags sava lakh", 125000), ("bopp bags 1 crore", 10000000),
                        ("bopp bags 20k pcs", 20000), ("bopp bags 1.5k", 1500), ("bopp bags 5000", 5000)]:
            with self.subTest(s=s):
                self.assertEqual(self.q(s)[0], want)

    def test_units(self):
        self.assertEqual(self.q("film 2 ton"), (2, "mt"))
        self.assertEqual(self.q("film 2 tonne"), (2, "mt"))
        self.assertEqual(self.q("film 2 MT"), (2, "mt"))
        self.assertEqual(self.q("film 500 kg"), (500, "kg"))
        self.assertEqual(self.q("box 100 pcs"), (100, "pcs"))
        self.assertEqual(self.q("box 100"), (100, "pcs"))
        self.assertEqual(self.q("film 300"), (300, "kg"))  # film without unit defaults to kg

    def test_missing_quantity(self):
        self.assertEqual(self.q("woven sacks required"), (None, None))


class TestTraps(unittest.TestCase):
    def q(self, s):
        return parse_rfq(s)["quantity"]

    def test_fill_weight_is_not_quantity(self):
        self.assertEqual(self.q("25 kg bags 500 pcs bopp"), 500)
        self.assertEqual(self.q("cement bags 50 kg 2 lakh"), 200000)
        self.assertEqual(self.q("bags of 50 kg 400 nos"), 400)
        self.assertEqual(self.q("woven sack 50 kg x 2000 bags"), 2000)
        self.assertEqual(self.q("50kg ke 3000 bags"), 3000)

    def test_capacity_is_not_quantity(self):
        self.assertEqual(self.q("jumbo bag 1000 kg capacity 500 pcs"), 500)
        self.assertEqual(self.q("fibc 1 ton SWL 200 pcs"), 200)
        self.assertEqual(self.q("jumbo 2 tonne 300 nos"), 300)

    def test_size_price_phone_pincode_ply_colour(self):
        self.assertEqual(self.q("pouch 12x18 inch 5000 pcs"), 5000)
        self.assertEqual(self.q("bopp bags rate 85 per kg 5000 pcs"), 5000)
        self.assertEqual(self.q("call 9876543210 box 700 pcs"), 700)
        self.assertEqual(self.q("box 800 pcs Nagpur 440001"), 800)
        self.assertEqual(self.q("5 ply box 1500 pcs"), 1500)
        self.assertEqual(self.q("mono carton 4 colour 500 pcs"), 500)
        self.assertEqual(self.q("need 1000 boxes in 15 days"), 1000)

    def test_gsm_micron_not_quantity(self):
        r = parse_rfq("film 25 mic 500 kg")
        self.assertEqual((r["micron"], r["quantity"]), (25, 500))
        r = parse_rfq("mono carton 300 gsm 10000 pcs")
        self.assertEqual((r["gsm"], r["quantity"]), (300, 10000))
        r = parse_rfq("pouch 100 micron 25000 pcs")  # regression: "micron 250" must not be read
        self.assertEqual((r["micron"], r["quantity"]), (100, 25000))


class TestCategory(unittest.TestCase):
    def c(self, s):
        return parse_rfq(s)["category"]

    def test_all_categories(self):
        cases = {"bopp_bag": ["bopp bags", "BOPP laminated woven bag", "boop bag", "bop bags 5000"],
                 "woven_sack": ["cement bags", "AD Star bags", "pp woven sack", "hdpe sack"],
                 "corrugated_box": ["box 500", "5 ply corrugated box", "carton box", "boxes chahiye"],
                 "pouch": ["stand up pouch", "zipper pouch", "pouche 5000", "spout pouch"],
                 "film": ["shrink film", "stretch wrap", "stretch film 20 mic", "shrnk wrap"],
                 "mono_carton": ["mono carton", "folding carton", "mono cartoon", "cosmetic carton"],
                 "fibc": ["jumbo bag", "bulk bag", "FIBC", "jambo bag", "big bag 1 ton"]}
        for cat, msgs in cases.items():
            for m in msgs:
                with self.subTest(m=m):
                    self.assertEqual(self.c(m), cat)

    def test_priority(self):
        self.assertEqual(self.c("bopp film 20 mic"), "film")
        self.assertEqual(self.c("bopp laminated pouch"), "pouch")
        self.assertEqual(self.c("jumbo bag with bopp"), "fibc")


class TestLocation(unittest.TestCase):
    def loc(self, s):
        return parse_rfq(s)["location"]

    def test_known_and_aliases(self):
        self.assertEqual(self.loc("box 500 pcs Navi Mumbai"), "Navi Mumbai")
        self.assertEqual(self.loc("box 500 pcs NAGPUR"), "Nagpur")
        self.assertEqual(self.loc("box 500 pcs bombay"), "Bombay")
        self.assertEqual(self.loc("pouch 5000 pcs to UAE"), "UAE")
        self.assertEqual(self.loc("film 1 mt Sri Lanka"), "Sri Lanka")

    def test_unseen_places_via_fallback(self):
        self.assertEqual(self.loc("bopp bags 5000 pcs deliver Tumakuru"), "Tumakuru")
        self.assertEqual(self.loc("bopp bags 5000 pcs 70 gsm, Muzaffarpur"), "Muzaffarpur")
        self.assertEqual(self.loc("film 500 kg 20 mic to Palakkad"), "Palakkad")

    def test_none_when_absent(self):
        for s in ["box 500 pcs", "need quote for 500 kg shrink wrap 25 mic", "bopp bags chahiye urgent", "pouch 100 mic 5000 pcs please"]:
            with self.subTest(s=s):
                self.assertIsNone(self.loc(s))

    def test_pincode_not_location(self):
        self.assertIsNone(self.loc("bopp bags 8000 pcs pin 440001"))

    def test_real_town_not_miscorrected(self):
        self.assertEqual(self.loc("shrink film 25 mic 10 mt Bhiwadi"), "Bhiwadi")

    def test_destination_preferred_over_origin(self):
        self.assertEqual(self.loc("shrink film 800 kg from Mumbai deliver Pune"), "Pune")


class TestRobustness(unittest.TestCase):
    def test_garbage_inputs_never_raise(self):
        rnd = random.Random(7)
        inputs = ["", " ", None, "   \n\t", "!!!???", "0", "000000", "😀😀 bopp 😀", "a" * 20000, "बोप्प बैग 40 हज़ार चाहिए नागपुर",
                  "१० हजार box", "1e9 box", "-5 box", "box 1,,,,,000", "bopp ..... ,,,, 65 gsm ,,", "\x00\x01 box", 12345, ["x"]]
        inputs += ["".join(rnd.choice(string.printable) for _ in range(rnd.randint(1, 80))) for _ in range(500)]
        for s in inputs:
            with self.subTest(s=str(s)[:30]):
                check_contract(self, parse_rfq(s))

    def test_devanagari(self):
        r = parse_rfq("बोप्प बैग 40 हज़ार चाहिए नागपुर")
        self.assertEqual((r["category"], r["quantity"], r["location"]), ("bopp_bag", 40000, "Nagpur"))

    def test_invariance_to_case_spacing_and_filler(self):
        base = parse_rfq("bopp bags 40 hazaar 65 gsm Nagpur")
        for v in ["BOPP BAGS 40 HAZAAR 65 GSM NAGPUR", "  bopp   bags  40   hazaar  65 gsm   Nagpur  ",
                  "Hi sir, bopp bags 40 hazaar 65 gsm Nagpur pls urgent", "bopp bags 40 hazaar 65 gsm Nagpur!!!"]:
            with self.subTest(v=v):
                self.assertEqual(parse_rfq(v), base)

    def test_metamorphic_quantity_spellings(self):
        outs = {parse_rfq(f"bopp bags {q} 65 gsm Pune")["quantity"] for q in ("40000", "40k", "40 hazaar", "40,000", "40 thousand")}
        self.assertEqual(outs, {40000})

    def test_metamorphic_city_swap_changes_only_location(self):
        a, b = parse_rfq("film 500 kg 20 mic Pune"), parse_rfq("film 500 kg 20 mic Jaipur")
        a["location"] = b["location"] = None
        self.assertEqual(a, b)

    def test_deterministic_and_pure(self):
        s = "bopp bags 40 hazaar 65 gsm Nagpur"
        self.assertEqual(parse_rfq(s), parse_rfq(s))


class TestDatasets(unittest.TestCase):
    """Regression guard: dev + holdout + red-team must stay at or above these floors."""
    def acc(self, name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        ok = 0
        for r in rows:
            g = parse_rfq(r["text"])
            e = r["expected"]
            ok += all((str(g[k]).lower() == str(e[k]).lower()) if k == "location" else (g[k] == e[k]) for k in e)
        return ok / len(rows), len(rows)

    def test_floors(self):
        for name, floor in [("my_tests.jsonl", 0.95), ("holdout.jsonl", 0.90), ("redteam.jsonl", 0.90)]:
            a, n = self.acc(name)
            with self.subTest(name=name):
                self.assertGreaterEqual(a, floor, f"{name}: {a:.3f}")

    def test_dev_file_format_and_size(self):
        with open(os.path.join(ROOT, "my_tests.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        self.assertGreaterEqual(len(rows), 40)
        for r in rows:
            self.assertEqual(set(r), {"text", "expected"})
            self.assertEqual(set(r["expected"]), KEYS)

    def test_speed(self):
        t = time.time()
        for _ in range(200):
            parse_rfq("bopp bags chahiye 40 hazaar, 65 gsm, Nagpur")
        self.assertLess(time.time() - t, 5)


if __name__ == "__main__":
    unittest.main()
