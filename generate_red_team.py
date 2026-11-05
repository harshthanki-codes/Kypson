"""
generate_red_team.py — Generates 150 challenging adversarial RFQ examples for P4.
"""

import json

adversarial_examples = [
    # ── Category 1: Two quantities & complex fill-weight syntax ──
    {"text": "500 pcs of 25 kg bags required for sugar delivery to Amravati",
     "expected": {"category": "woven_sack", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Amravati"}},
    {"text": "bags of 50 kg 400 nos pp woven sack Akola",
     "expected": {"category": "woven_sack", "quantity": 400, "unit": "pcs", "gsm": None, "micron": None, "location": "Akola"}},
    {"text": "100 kg x 20 bags pp woven sacks needed Wardha",
     "expected": {"category": "woven_sack", "quantity": 20, "unit": "pcs", "gsm": None, "micron": None, "location": "Wardha"}},
    {"text": "need 25kg packaging bags 10000 pieces Yavatmal",
     "expected": {"category": "woven_sack", "quantity": 10000, "unit": "pcs", "gsm": None, "micron": None, "location": "Yavatmal"}},
    {"text": "cement packing 50 kg bag x 5000 units Chandrapur",
     "expected": {"category": "woven_sack", "quantity": 5000, "unit": "pcs", "gsm": None, "micron": None, "location": "Chandrapur"}},
    {"text": "1000 pcs of 1 ton fibc bulk bag Gondia",
     "expected": {"category": "fibc", "quantity": 1000, "unit": "pcs", "gsm": None, "micron": None, "location": "Gondia"}},
    {"text": "jumbo bags 500 pcs each holding 1000 kg Latur",
     "expected": {"category": "fibc", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Latur"}},
    {"text": "pouches of 500 gms pack 25000 pcs Nanded",
     "expected": {"category": "pouch", "quantity": 25000, "unit": "pcs", "gsm": None, "micron": None, "location": "Nanded"}},
    {"text": "carton box of 20 kg load capacity 1500 pcs Satara",
     "expected": {"category": "corrugated_box", "quantity": 1500, "unit": "pcs", "gsm": None, "micron": None, "location": "Satara"}},
    {"text": "50 kg urea bag 12000 nos Sangli",
     "expected": {"category": "woven_sack", "quantity": 12000, "unit": "pcs", "gsm": None, "micron": None, "location": "Sangli"}},

    # ── Category 2: Quantity before category or at the very end ──
    {"text": "40000 bopp bags 65 gsm Nagpur",
     "expected": {"category": "bopp_bag", "quantity": 40000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Nagpur"}},
    {"text": "10000 corrugated boxes 3 ply Ratnagiri",
     "expected": {"category": "corrugated_box", "quantity": 10000, "unit": "pcs", "gsm": None, "micron": None, "location": "Ratnagiri"}},
    {"text": "bopp bag 70 gsm Dhule delivery 50000 pcs",
     "expected": {"category": "bopp_bag", "quantity": 50000, "unit": "pcs", "gsm": 70, "micron": None, "location": "Dhule"}},
    {"text": "stretch film 25 mic Jalgaon order quantity 2000 kg",
     "expected": {"category": "film", "quantity": 2000, "unit": "kg", "gsm": None, "micron": 25, "location": "Jalgaon"}},
    {"text": "corrugated box 5 ply required at Panvel, count 3500",
     "expected": {"category": "corrugated_box", "quantity": 3500, "unit": "pcs", "gsm": None, "micron": None, "location": "Panvel"}},
    {"text": "fibc bulk bags dispatch to Palghar quantity 800",
     "expected": {"category": "fibc", "quantity": 800, "unit": "pcs", "gsm": None, "micron": None, "location": "Palghar"}},

    # ── Category 3: Category only implied / indirect phrasing ──
    {"text": "cement ke liye bag 50000 chahiye Gandhidham",
     "expected": {"category": "woven_sack", "quantity": 50000, "unit": "pcs", "gsm": None, "micron": None, "location": "Gandhidham"}},
    {"text": "atta packaging bags 20 hazaar pcs Mundra",
     "expected": {"category": "woven_sack", "quantity": 20000, "unit": "pcs", "gsm": None, "micron": None, "location": "Mundra"}},
    {"text": "pallets ko wrap karne ke liye film 500 kg Mehsana",
     "expected": {"category": "film", "quantity": 500, "unit": "kg", "gsm": None, "micron": None, "location": "Mehsana"}},
    {"text": "shipping master carton 500 pcs Surendranagar",
     "expected": {"category": "corrugated_box", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Surendranagar"}},
    {"text": "chemical packaging jumbo 1 ton 300 pcs Porbandar",
     "expected": {"category": "fibc", "quantity": 300, "unit": "pcs", "gsm": None, "micron": None, "location": "Porbandar"}},
    {"text": "toothpaste folding box 300 gsm 50k pcs Navsari",
     "expected": {"category": "mono_carton", "quantity": 50000, "unit": "pcs", "gsm": 300, "micron": None, "location": "Navsari"}},
    {"text": "namkeen packing standup pouch 15k pcs Valsad",
     "expected": {"category": "pouch", "quantity": 15000, "unit": "pcs", "gsm": None, "micron": None, "location": "Valsad"}},

    # ── Category 4: Conflicting category keywords ──
    {"text": "BOPP film for woven bag lamination 500 kg Bhavnagar",
     "expected": {"category": "film", "quantity": 500, "unit": "kg", "gsm": None, "micron": None, "location": "Bhavnagar"}},
    {"text": "BOPP laminated woven sack 50000 pcs Jamnagar",
     "expected": {"category": "bopp_bag", "quantity": 50000, "unit": "pcs", "gsm": None, "micron": None, "location": "Jamnagar"}},
    {"text": "mono carton box duplex board 10000 pcs Gandhinagar",
     "expected": {"category": "mono_carton", "quantity": 10000, "unit": "pcs", "gsm": None, "micron": None, "location": "Gandhinagar"}},
    {"text": "corrugated box with inner pouch 2000 pcs Sonipat",
     "expected": {"category": "corrugated_box", "quantity": 2000, "unit": "pcs", "gsm": None, "micron": None, "location": "Sonipat"}},
    {"text": "shrink wrap for carton boxes 300 kg Karnal",
     "expected": {"category": "film", "quantity": 300, "unit": "kg", "gsm": None, "micron": None, "location": "Karnal"}},

    # ── Category 5: Sheets and rolls ──
    {"text": "corrugated 3 ply sheets 5000 sheets Rohtak",
     "expected": {"category": "corrugated_box", "quantity": 5000, "unit": "pcs", "gsm": None, "micron": None, "location": "Rohtak"}},
    {"text": "stretch film 200 rolls 23 mic Hisar",
     "expected": {"category": "film", "quantity": 200, "unit": "pcs", "gsm": None, "micron": 23, "location": "Hisar"}},
    {"text": "bopp tape rolls 1000 rolls Ambala",
     "expected": {"category": "film", "quantity": 1000, "unit": "pcs", "gsm": None, "micron": None, "location": "Ambala"}},
    {"text": "bubble wrap film 50 rolls Bhiwani",
     "expected": {"category": "film", "quantity": 50, "unit": "pcs", "gsm": None, "micron": None, "location": "Bhiwani"}},

    # ── Category 6: Unknown cities & pattern fallback ──
    {"text": "bopp bags 20k pcs 65 gsm delivery to Ankola",
     "expected": {"category": "bopp_bag", "quantity": 20000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Ankola"}},
    {"text": "fibc jumbo bag 500 pcs in Ranipet",
     "expected": {"category": "fibc", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Ranipet"}},
    {"text": "corrugated cartons 1000 pcs for Changanassery",
     "expected": {"category": "corrugated_box", "quantity": 1000, "unit": "pcs", "gsm": None, "micron": None, "location": "Changanassery"}},
    {"text": "stand up pouch 10k pcs at Bagalkot",
     "expected": {"category": "pouch", "quantity": 10000, "unit": "pcs", "gsm": None, "micron": None, "location": "Bagalkot"}},
    {"text": "pp woven sacks 25000 pcs, Hospet",
     "expected": {"category": "woven_sack", "quantity": 25000, "unit": "pcs", "gsm": None, "micron": None, "location": "Hospet"}},
    {"text": "stretch film 500 kg 25 mic, Sirsi",
     "expected": {"category": "film", "quantity": 500, "unit": "kg", "gsm": None, "micron": 25, "location": "Sirsi"}},
    {"text": "cement bags 40 hazaar pcs, Mirzapur",
     "expected": {"category": "woven_sack", "quantity": 40000, "unit": "pcs", "gsm": None, "micron": None, "location": "Mirzapur"}},
    {"text": "mono carton 15k pcs, Sambhal",
     "expected": {"category": "mono_carton", "quantity": 15000, "unit": "pcs", "gsm": None, "micron": None, "location": "Sambhal"}},

    # ── Category 7: Number formats (10L, 2.5 cr, Indian commas, decimals) ──
    {"text": "10L bopp bags 60 gsm Bathinda",
     "expected": {"category": "bopp_bag", "quantity": 1000000, "unit": "pcs", "gsm": 60, "micron": None, "location": "Bathinda"}},
    {"text": "2.5 cr cement bags for mega project in Hoshiarpur",
     "expected": {"category": "woven_sack", "quantity": 25000000, "unit": "pcs", "gsm": None, "micron": None, "location": "Hoshiarpur"}},
    {"text": "5,00,000 pcs woven sacks 70 gsm Pathankot",
     "expected": {"category": "woven_sack", "quantity": 500000, "unit": "pcs", "gsm": 70, "micron": None, "location": "Pathankot"}},
    {"text": "1,25,000 bopp laminated bags Mohali",
     "expected": {"category": "bopp_bag", "quantity": 125000, "unit": "pcs", "gsm": None, "micron": None, "location": "Mohali"}},
    {"text": "7,500 corrugated boxes 5 ply Panchkula",
     "expected": {"category": "corrugated_box", "quantity": 7500, "unit": "pcs", "gsm": None, "micron": None, "location": "Panchkula"}},
    {"text": "0.5 MT stretch film 23 mic Meerut",
     "expected": {"category": "film", "quantity": 0.5, "unit": "mt", "gsm": None, "micron": 23, "location": "Meerut"}},
    {"text": "2.5 ton shrink film Saharanpur",
     "expected": {"category": "film", "quantity": 2.5, "unit": "mt", "gsm": None, "micron": None, "location": "Saharanpur"}},

    # ── Category 8: Vernacular & Romanised Hindi variations ──
    {"text": "ek lakh bopp bags chahiye 65 gsm Mathura",
     "expected": {"category": "bopp_bag", "quantity": 100000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Mathura"}},
    {"text": "paanch sau jumbo bag 1000 kg capacity Roorkee",
     "expected": {"category": "fibc", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Roorkee"}},
    {"text": "dus hazar corrugated boxes 3 ply Kashipur",
     "expected": {"category": "corrugated_box", "quantity": 10000, "unit": "pcs", "gsm": None, "micron": None, "location": "Kashipur"}},
    {"text": "bees hazaar pouch zipper Haldwani",
     "expected": {"category": "pouch", "quantity": 20000, "unit": "pcs", "gsm": None, "micron": None, "location": "Haldwani"}},
    {"text": "pachas hazaar cement bags Rishikesh",
     "expected": {"category": "woven_sack", "quantity": 50000, "unit": "pcs", "gsm": None, "micron": None, "location": "Rishikesh"}},
    {"text": "char hazaar mono carton Sitarganj",
     "expected": {"category": "mono_carton", "quantity": 4000, "unit": "pcs", "gsm": None, "micron": None, "location": "Sitarganj"}},
    {"text": "teen lakh woven sacks Muzaffarnagar",
     "expected": {"category": "woven_sack", "quantity": 300000, "unit": "pcs", "gsm": None, "micron": None, "location": "Muzaffarnagar"}},

    # ── Category 9: Devanagari variations ──
    {"text": "१०,००० बोप्प बैग ६५ जीएसएम नागपुर",
     "expected": {"category": "bopp_bag", "quantity": 10000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Nagpur"}},
    {"text": "५०० जंबो बैग १ टन क्षमता वडोदरा",
     "expected": {"category": "fibc", "quantity": 500, "unit": "pcs", "gsm": None, "micron": None, "location": "Vadodara"}},
    {"text": "१ लाख सीमेंट की बोरी जयपुर",
     "expected": {"category": "woven_sack", "quantity": 100000, "unit": "pcs", "gsm": None, "micron": None, "location": "Jaipur"}},
    {"text": "२५०० बॉक्स ५ प्लाई दिल्ली",
     "expected": {"category": "corrugated_box", "quantity": 2500, "unit": "pcs", "gsm": None, "micron": None, "location": "Delhi"}},
    {"text": "५०,००० पाउच जिपर मुंबई",
     "expected": {"category": "pouch", "quantity": 50000, "unit": "pcs", "gsm": None, "micron": None, "location": "Mumbai"}},

    # ── Category 10: Heavy noise, email signatures, salutations ──
    {"text": "Dear Sir, please quote for 25000 pcs bopp bags 70 gsm to Bikaner. Regards, Sharma Traders",
     "expected": {"category": "bopp_bag", "quantity": 25000, "unit": "pcs", "gsm": 70, "micron": None, "location": "Bikaner"}},
    {"text": "Hi team, urgently required 1200 pcs fibc bag 1 ton swl delivery at Durg. Thanks, Patel",
     "expected": {"category": "fibc", "quantity": 1200, "unit": "pcs", "gsm": None, "micron": None, "location": "Durg"}},
    {"text": "PLS SEND BEST PRICE 50000 PCS CEMENT BAG AD STAR RAIPUR URGENT PLS CONTACT 9898989898",
     "expected": {"category": "woven_sack", "quantity": 50000, "unit": "pcs", "gsm": None, "micron": None, "location": "Raipur"}},
    {"text": "Hello, need 1000 kg stretch film 29 micron delivery near Bilaspur plant. ASAP.",
     "expected": {"category": "film", "quantity": 1000, "unit": "kg", "gsm": None, "micron": 29, "location": "Bilaspur"}},
    {"text": "AOA, please send quotation for 10000 pcs mono carton duplex board 300 gsm Korba",
     "expected": {"category": "mono_carton", "quantity": 10000, "unit": "pcs", "gsm": 300, "micron": None, "location": "Korba"}},
    {"text": "URGENT ORDER: 2000 boxes 7 ply size 18x12x10 for export to Dubai, quote CIF",
     "expected": {"category": "corrugated_box", "quantity": 2000, "unit": "pcs", "gsm": None, "micron": None, "location": "Dubai"}},

    # ── Category 11: International destinations ──
    {"text": "50000 woven sacks 80 gsm export to Kenya",
     "expected": {"category": "woven_sack", "quantity": 50000, "unit": "pcs", "gsm": 80, "micron": None, "location": "Kenya"}},
    {"text": "1000 fibc bags 1 ton SWL shipment to Nigeria",
     "expected": {"category": "fibc", "quantity": 1000, "unit": "pcs", "gsm": None, "micron": None, "location": "Nigeria"}},
    {"text": "50000 bopp bags 65 gsm order for Nepal",
     "expected": {"category": "bopp_bag", "quantity": 50000, "unit": "pcs", "gsm": 65, "micron": None, "location": "Nepal"}},
    {"text": "10 MT stretch film 23 mic to Bangladesh",
     "expected": {"category": "film", "quantity": 10, "unit": "mt", "gsm": None, "micron": 23, "location": "Bangladesh"}},
    {"text": "1 lakh standup pouch 70 mic to Sri Lanka",
     "expected": {"category": "pouch", "quantity": 100000, "unit": "pcs", "gsm": None, "micron": 70, "location": "Sri Lanka"}},
    {"text": "2000 pcs jumbo bag 1.5 ton capacity export to Germany",
     "expected": {"category": "fibc", "quantity": 2000, "unit": "pcs", "gsm": None, "micron": None, "location": "Germany"}},
    {"text": "5000 corrugated cartons 5 ply for export to USA",
     "expected": {"category": "corrugated_box", "quantity": 5000, "unit": "pcs", "gsm": None, "micron": None, "location": "USA"}},
    {"text": "20000 mono cartons 350 gsm export to UK",
     "expected": {"category": "mono_carton", "quantity": 20000, "unit": "pcs", "gsm": 350, "micron": None, "location": "UK"}},
    {"text": "40000 pcs pp woven sacks delivery at Tanzania",
     "expected": {"category": "woven_sack", "quantity": 40000, "unit": "pcs", "gsm": None, "micron": None, "location": "Tanzania"}},
    {"text": "15 MT packaging film export to Ghana",
     "expected": {"category": "film", "quantity": 15, "unit": "mt", "gsm": None, "micron": None, "location": "Ghana"}},

    # ── Category 12: Missing fields variations ──
    {"text": "bopp bag 65 gsm quotation chahiye",
     "expected": {"category": "bopp_bag", "quantity": None, "unit": "pcs", "gsm": 65, "micron": None, "location": None}},
    {"text": "fibc bags price list please",
     "expected": {"category": "fibc", "quantity": None, "unit": "pcs", "gsm": None, "micron": None, "location": None}},
    {"text": "corrugated box manufacturer in Ahmedabad",
     "expected": {"category": "corrugated_box", "quantity": None, "unit": "pcs", "gsm": None, "micron": None, "location": "Ahmedabad"}},
    {"text": "stretch film roll 23 mic rate per kg",
     "expected": {"category": "film", "quantity": None, "unit": "kg", "gsm": None, "micron": 23, "location": None}},
    {"text": "mono carton box samples needed Pune",
     "expected": {"category": "mono_carton", "quantity": None, "unit": "pcs", "gsm": None, "micron": None, "location": "Pune"}},
    {"text": "zipper pouch 100g size price Jaipur",
     "expected": {"category": "pouch", "quantity": None, "unit": "pcs", "gsm": None, "micron": None, "location": "Jaipur"}},
    {"text": "cement bag ad star required",
     "expected": {"category": "woven_sack", "quantity": None, "unit": "pcs", "gsm": None, "micron": None, "location": None}},
    {"text": "5000 pcs bopp bags",
     "expected": {"category": "bopp_bag", "quantity": 5000, "unit": "pcs", "gsm": None, "micron": None, "location": None}},
    {"text": "1000 kg shrink film",
     "expected": {"category": "film", "quantity": 1000, "unit": "kg", "gsm": None, "micron": None, "location": None}},
    {"text": "2000 pcs corrugated boxes",
     "expected": {"category": "corrugated_box", "quantity": 2000, "unit": "pcs", "gsm": None, "micron": None, "location": None}},
]

# We will expand systematically up to 150 items with realistic industrial permutations
cities_extra = [
    "Jamshedpur", "Bokaro", "Dhanbad", "Haldia", "Siliguri", "Asansol", "Jharsuguda",
    "Rourkela", "Cuttack", "Sambalpur", "Bhubaneswar", "Guwahati", "Imphal", "Shillong",
    "Agartala", "Aizawl", "Dimapur", "Jorhat", "Dibrugarh", "Dehradun", "Haridwar",
    "Roorkee", "Rudrapur", "Kashipur", "Haldwani", "Baddi", "Nalagarh", "Solan",
    "Shimla", "Srinagar", "Jammu", "Udhampur", "Bathinda", "Hoshiarpur", "Pathankot",
    "Karnal", "Panipat", "Sonipat", "Hisar", "Rohtak", "Bhiwani", "Sirsa",
    "Alwar", "Bharatpur", "Bhilwara", "Sikar", "Pali", "Barmer", "Chittorgarh",
    "Ujjain", "Dewas", "Ratlam", "Satna", "Rewa", "Katni", "Singrauli",
    "Bilaspur", "Korba", "Raigarh", "Rajnandgaon", "Jagdalpur", "Ambikapur",
    "Solapur", "Kolhapur", "Sangli", "Satara", "Jalgaon", "Dhule", "Nanded",
    "Latur", "Akola", "Amravati", "Wardha", "Chandrapur", "Gondia", "Yavatmal",
    "Morbi", "Ankleshwar", "Bharuch", "Vapi", "Silvassa", "Daman", "Valsad"
]

quantities_extra = [
    (5000, "pcs", "5000 pcs"), (10000, "pcs", "10k pcs"), (25000, "pcs", "25,000 pcs"),
    (50000, "pcs", "50 hazaar pcs"), (100000, "pcs", "1 lakh pcs"), (150000, "pcs", "1.5 lakh pcs"),
    (200000, "pcs", "2 lakh pcs"), (250000, "pcs", "2.5 lac pcs"), (500000, "pcs", "5 lakh pcs"),
    (500, "kg", "500 kg"), (1000, "kg", "1000 kg"), (2000, "kg", "2000 kg"),
    (5, "mt", "5 MT"), (10, "mt", "10 ton"), (20, "mt", "20 tonne")
]

cats_extra = [
    ("bopp_bag", "bopp laminated bags 65 gsm", 65, None),
    ("woven_sack", "pp woven sacks 50 kg packing", None, None),
    ("corrugated_box", "corrugated boxes 5 ply 14x10x8", None, None),
    ("pouch", "stand up zipper pouch 70 mic", None, 70),
    ("film", "stretch wrap film 25 mic", None, 25),
    ("mono_carton", "mono carton folding box 300 gsm", 300, None),
    ("fibc", "fibc bulk bags 1 ton SWL", None, None),
]

idx = 0
while len(adversarial_examples) < 150:
    city = cities_extra[idx % len(cities_extra)]
    cat, phrase, gsm, mic = cats_extra[idx % len(cats_extra)]
    
    # Select appropriate quantity & unit based on category
    if cat == "film":
        q_val, q_unit, q_str = quantities_extra[9 + (idx % 6)]  # kg or mt
    else:
        q_val, q_unit, q_str = quantities_extra[idx % 9]  # pcs
        
    text = f"Requirement: {phrase}, {q_str}, dispatch to {city}"
    adversarial_examples.append({
        "text": text,
        "expected": {
            "category": cat,
            "quantity": q_val,
            "unit": q_unit,
            "gsm": gsm,
            "micron": mic,
            "location": city
        }
    })
    idx += 1

print(f"Total red-team examples generated: {len(adversarial_examples)}")
with open("red_team.jsonl", "w", encoding="utf-8") as f:
    for ex in adversarial_examples:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
