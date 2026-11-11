"""
parse.py — RFQ information extractor for Kypson B2B packaging marketplace.

Extracts six structured fields from raw Indian B2B packaging RFQ text:
  category, quantity, unit, gsm, micron, location.

Architecture: deterministic 7-stage pipeline.
  1. Normalize (Unicode, Devanagari, whitespace)
  2. Extract GSM (regex, mask from text)
  3. Extract micron (regex, mask from text)
  4. Mask interfering patterns (phones, PINs, dimensions, prices, ply, colours, dates)
  5. Classify category (priority-ordered keyword matching)
  6. Extract quantity + unit (Indian-number parsing, candidate scoring/filtering)
  7. Extract location (gazetteer + contextual pattern fallback)

No ML models, no paid APIs.  Pure Python 3.10+ standard library.
"""

import re
import unicodedata
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: CONSTANTS & LEXICONS
# ═══════════════════════════════════════════════════════════════════════════

# -- Valid output values --
VALID_CATEGORIES = (
    "bopp_bag", "woven_sack", "corrugated_box",
    "pouch", "film", "mono_carton", "fibc",
)

# Option A decision: unit when quantity is missing (set to 'pcs'/'kg' or None)
MISSING_QUANTITY_UNIT = None

# -- Devanagari digit → ASCII digit --
_DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# -- Devanagari word → Romanised equivalent (sorted longest-first) --
_DEVA_WORDS = [
    # Packaging specs and products
    ("कार्टन", " carton "), ("जीएसएम", " gsm "), ("माइक्रोन", " micron "),
    ("सीमेंट", " cement "), ("हज़ार", " hazaar "), ("हजार", " hazaar "),
    ("लाख", " lakh "), ("करोड़", " crore "), ("चाहिए", " chahiye "),
    ("चाहिये", " chahiye "), ("बैग", " bag "), ("बोप्प", " bopp "),
    ("बॉक्स", " box "), ("पाउच", " pouch "), ("फिल्म", " film "),
    ("जंबो", " jumbo "), ("जम्बो", " jumbo "), ("पीस", " pcs "),
    ("किलो", " kg "), ("ग्राम", " gram "), ("मिली", " ml "),
    ("लीटर", " ltr "), ("सैक", " sack "), ("बोरी", " sack "),
    ("प्लाई", " ply "), ("टन", " ton "),

    # Numbers and Hindi fractions in Devanagari
    ("साढ़े", " saadhe "), ("पौने", " paune "), ("डेढ़", " dedh "), ("ढाई", " dhai "), ("सवा", " sava "),
    ("पंचानवे", " 95 "), ("नब्बे", " 90 "), ("पचासी", " 85 "), ("अस्सी", " 80 "), ("पचहत्तर", " 75 "),
    ("सत्तर", " 70 "), ("पैंसठ", " 65 "), ("साठ", " 60 "), ("पचपन", " 55 "), ("पचास", " 50 "),
    ("पैंतालीस", " 45 "), ("चालीस", " 40 "), ("पैंतीस", " 35 "), ("बत्तीस", " 32 "), ("इकत्तीस", " 31 "),
    ("तीस", " 30 "), ("उनतीस", " 29 "), ("अट्ठाईस", " 28 "), ("सत्ताईस", " 27 "), ("छब्बीस", " 26 "),
    ("पच्चीस", " 25 "), ("चौबीस", " 24 "), ("तेईस", " 23 "), ("बाईस", " 22 "), ("इक्कीस", " 21 "),
    ("बीस", " 20 "), ("उन्नीस", " 19 "), ("अठारह", " 18 "), ("सत्रह", " 17 "), ("सोलह", " 16 "),
    ("पंद्रह", " 15 "), ("पन्द्रह", " 15 "), ("चौदह", " 14 "), ("तेरह", " 13 "), ("बारह", " 12 "),
    ("ग्यारह", " 11 "), ("दस", " 10 "), ("नौ", " 9 "), ("आठ", " 8 "), ("सात", " 7 "),
    ("छह", " 6 "), ("छः", " 6 "), ("पांच", " 5 "), ("पाँच", " 5 "), ("चार", " 4 "),
    ("तीन", " 3 "), ("दो", " 2 "), ("एक", " 1 "), ("सौ", " 100 "),

    # ~150 most common Indian cities / industrial hubs in Devanagari
    ("अहमदाबाद", " Ahmedabad "), ("हैदराबाद", " Hyderabad "), ("कोलकाता", " Kolkata "),
    ("वडोदरा", " Vadodara "), ("लखनऊ", " Lucknow "), ("कानपुर", " Kanpur "),
    ("नागपुर", " Nagpur "), ("मुंबई", " Mumbai "), ("दिल्ली", " Delhi "),
    ("नई दिल्ली", " Delhi "), ("जयपुर", " Jaipur "), ("इंदौर", " Indore "),
    ("भोपाल", " Bhopal "), ("सूरत", " Surat "), ("चेन्नई", " Chennai "),
    ("बेंगलुरु", " Bengaluru "), ("बैंगलोर", " Bengaluru "), ("पुणे", " Pune "),
    ("पटना", " Patna "), ("नासिक", " Nashik "), ("राजकोट", " Rajkot "),
    ("भावनगर", " Bhavnagar "), ("जामनगर", " Jamnagar "), ("गांधीनगर", " Gandhinagar "),
    ("जूनागढ़", " Junagadh "), ("आनंद", " Anand "), ("नवसारी", " Navsari "),
    ("मोरबी", " Morbi "), ("नडियाद", " Nadiad "), ("सुरेंद्रनगर", " Surendranagar "),
    ("भरूच", " Bharuch "), ("वापी", " Vapi "), ("अंकलेश्वर", " Ankleshwar "),
    ("कलोल", " Kalol "), ("पालनपुर", " Palanpur "), ("पाटन", " Patan "),
    ("दाहोद", " Dahod "), ("गोधरा", " Godhra "), ("भुज", " Bhuj "),
    ("कच्छ", " Kutch "), ("अमरेली", " Amreli "), ("वलसाड", " Valsad "),
    ("दीव", " Diu "), ("दमन", " Daman "), ("सिलवासा", " Silvassa "),
    ("उमरगाम", " Umbergaon "), ("पोरबंदर", " Porbandar "), ("बोटाद", " Botad "),
    ("गोंडल", " Gondal "), ("हिम्मतनगर", " Himatnagar "), ("मेहसाणा", " Mehsana "),
    ("महेसाणा", " Mehsana "), ("सायान", " Sayan "), ("सायन", " Sayan "),
    ("दाभोई", " Dabhoi "), ("कपड़वंज", " Kapadvanj "), ("डीसा", " Deesa "),
    ("ठाणे", " Thane "), ("औरंगाबाद", " Aurangabad "), ("संभाजीनगर", " Sambhajinagar "),
    ("सोलापुर", " Solapur "), ("अमरावती", " Amravati "), ("कोल्हापुर", " Kolhapur "),
    ("नवी मुंबई", " Navi Mumbai "), ("उल्हासनगर", " Ulhasnagar "), ("कल्याण", " Kalyan "),
    ("डोंबिवली", " Dombivli "), ("वसई", " Vasai "), ("विरार", " Virar "),
    ("मीरा भयंदर", " Mira Bhayandar "), ("भिवंडी", " Bhiwandi "), ("नांदेड़", " Nanded "),
    ("जलगांव", " Jalgaon "), ("अकोला", " Akola "), ("लातूर", " Latur "),
    ("धुले", " Dhule "), ("चंद्रपुर", " Chandrapur "), ("परभणी", " Parbhani "),
    ("इचलकरंजी", " Ichalkaranji "), ("जालना", " Jalna "), ("भुसावल", " Bhusawal "),
    ("पनवेल", " Panvel "), ("सतारा", " Satara "), ("सांगली", " Sangli "),
    ("बारामती", " Baramati "), ("चाकण", " Chakan "), ("तलेगांव", " Talegaon "),
    ("रालेगांव", " Ralegaon "), ("कर्जत", " Karjat "), ("उमरखेड", " Umarkhed "),
    ("निलंगा", " Nilanga "), ("इगतपुरी", " Igatpuri "), ("शिरडी", " Shirdi "),
    ("महाड", " Mahad "), ("रोहा", " Roha "), ("तारापुर", " Tarapur "),
    ("बोईसर", " Boisar "), ("अहमदनगर", " Ahmednagar "), ("पिंपरी", " Pimpri "),
    ("चिंचवड़", " Chinchwad "), ("नोएडा", " Noida "), ("ग्रेटर नोएडा", " Greater Noida "),
    ("गुड़गांव", " Gurgaon "), ("गुरुग्राम", " Gurugram "), ("फरीदाबाद", " Faridabad "),
    ("गाजियाबाद", " Ghaziabad "), ("आगरा", " Agra "), ("वाराणसी", " Varanasi "),
    ("प्रयागराज", " Prayagraj "), ("इलाहाबाद", " Allahabad "), ("मेरठ", " Meerut "),
    ("बरेली", " Bareilly "), ("अलीगढ़", " Aligarh "), ("मुरादाबाद", " Moradabad "),
    ("सहारनपुर", " Saharanpur "), ("गोरखपुर", " Gorakhpur "), ("झांशी", " Jhansi "),
    ("मथुरा", " Mathura "), ("हापुड़", " Hapur "), ("मुजफ्फरनगर", " Muzaffarnagar "),
    ("फिरोजाबाद", " Firozabad "), ("सोनभद्र", " Sonbhadra "), ("जोधपुर", " Jodhpur "),
    ("कोटा", " Kota "), ("बीकानेर", " Bikaner "), ("अजमेर", " Ajmer "),
    ("उदयपुर", " Udaipur "), ("भीलवाड़ा", " Bhilwara "), ("अलवर", " Alwar "),
    ("भरतपुर", " Bharatpur "), ("श्रीगंगानगर", " Sriganganagar "), ("सीकर", " Sikar "),
    ("पाली", " Pali "), ("नीमराना", " Neemrana "), ("भिवाड़ी", " Bhiwadi "),
    ("ग्वालियर", " Gwalior "), ("जबलपुर", " Jabalpur "), ("उज्जैन", " Ujjain "),
    ("सागर", " Sagar "), ("देवास", " Dewas "), ("सतना", " Satna "),
    ("रतलाम", " Ratlam "), ("रीवा", " Rewa "), ("कटनी", " Katni "),
    ("सिंगरौली", " Singrauli "), ("बुरहानपुर", " Burhanpur "), ("खंडवा", " Khandwa "),
    ("पीथमपुर", " Pithampur "), ("लुधियाना", " Ludhiana "), ("अमृतसर", " Amritsar "),
    ("जालंधर", " Jalandhar "), ("पटियाला", " Patiala "), ("बठिंडा", " Bathinda "),
    ("मोहाली", " Mohali "), ("चंडीगढ़", " Chandigarh "), ("अंबाला", " Ambala "),
    ("पानीपत", " Panipat "), ("करनाल", " Karnal "), ("रोहतक", " Rohtak "),
    ("हिसार", " Hisar "), ("सोनीपत", " Sonipat "), ("बहादुरगढ़", " Bahadurgarh "),
    ("रेवाड़ी", " Rewari "), ("मानेसर", " Manesar "), ("यमुनानगर", " Yamunanagar "),
    ("पंचकुला", " Panchkula "), ("गया", " Gaya "), ("भागलपुर", " Bhagalpur "),
    ("मुजफ्फरपुर", " Muzaffarpur "), ("पूर्णिया", " Purnia "), ("दरभंगा", " Darbhanga "),
    ("बिहारशरीफ", " Bihar Sharif "), ("रांची", " Ranchi "), ("जमशेदपुर", " Jamshedpur "),
    ("धनबाद", " Dhanbad "), ("बोकारो", " Bokaro "), ("देवघर", " Deoghar "),
    ("हजारीबाग", " Hazaribagh "), ("रायपुर", " Raipur "), ("भिलाई", " Bhilai "),
    ("बिलासपुर", " Bilaspur "), ("दुर्ग", " Durg "), ("कोरबा", " Korba "),
    ("राजनंदगांव", " Rajnandgaon "), ("रायगढ़", " Raigarh "), ("देहरादून", " Dehradun "),
    ("हरिद्वार", " Haridwar "), ("रुड़की", " Roorkee "), ("हल्द्वानी", " Haldwani "),
    ("रुद्रपुर", " Rudrapur "), ("ऋषिकेश", " Rishikesh "), ("काशीपुर", " Kashipur "),
    ("जम्मू", " Jammu "), ("श्रीनगर", " Srinagar "), ("शिमला", " Shimla "),
    ("बद्दी", " Baddi "), ("सोलन", " Solan "), ("सिकंदराबाद", " Secunderabad "),
    ("वारंगल", " Warangal "), ("निजामाबाद", " Nizamabad "), ("करीमनगर", " Karimnagar "),
    ("खम्मम", " Khammam "), ("रामगुंडम", " Ramagundam "), ("महबूबनगर", " Mahbubnagar "),
    ("नलगोंडा", " Nalgonda "), ("आदिलाबाद", " Adilabad "), ("जहीराबाद", " Zaheerabad "),
    ("जंगांव", " Jangaon "), ("निर्मल", " Nirmal "), ("मैसूर", " Mysore "),
    ("हुबली", " Hubli "), ("धारवाड़", " Dharwad "), ("मंगलुरु", " Mangalore "),
    ("मंगलोर", " Mangalore "), ("बेलगाम", " Belgaum "), ("गुलबर्गा", " Gulbarga "),
    ("दावणगेरे", " Davanagere "), ("बेलारी", " Bellary "), ("शिमोगा", " Shimoga "),
    ("तुमकुर", " Tumkur "), ("होसुर", " Hosur "), ("कोयंबटूर", " Coimbatore "),
    ("मदुरै", " Madurai "), ("तिरुचिरापल्ली", " Tiruchirappalli "), ("सलेम", " Salem "),
    ("तिरुपुर", " Tirupur "), ("इरोड", " Erode "), ("वेल्लोर", " Vellore "),
    ("तूतीकोरिन", " Tuticorin "), ("डिंडीगुल", " Dindigul "), ("तंजावूर", " Thanjavur "),
    ("नागरकोइल", " Nagercoil "), ("कांचीपुरम", " Kanchipuram "), ("करूर", " Karur "),
    ("शिवकाशी", " Sivakasi "), ("कोच्चि", " Kochi "), ("तिरुवनंतपुरम", " Thiruvananthapuram "),
    ("कोझिकोड", " Kozhikode "), ("त्रिशूर", " Thrissur "), ("कोल्लम", " Kollam "),
    ("पलक्कड़", " Palakkad "), ("अलप्पुझा", " Alappuzha "), ("कन्नूर", " Kannur "),
    ("विशाखापट्टनम", " Visakhapatnam "), ("विजयवाड़ा", " Vijayawada "), ("गुंटूर", " Guntur "),
    ("नेल्लोर", " Nellore "), ("कुरनूल", " Kurnool "), ("राजमुंदरी", " Rajahmundry "),
    ("तिरुपति", " Tirupati "), ("काकीनाडा", " Kakinada "), ("अनंतपुर", " Anantapur "),
    ("कडपा", " Kadapa "), ("विजयनगरम", " Vizianagaram "), ("एलुरु", " Eluru "),
    ("ओंगोल", " Ongole "), ("हावड़ा", " Howrah "), ("दुर्गापुर", " Durgapur "),
    ("आसनसोल", " Asansol "), ("सिलीगुड़ी", " Siliguri "), ("खड़गपुर", " Kharagpur "),
    ("हल्दिया", " Haldia "), ("भुवनेश्वर", " Bhubaneswar "), ("कटक", " Cuttack "),
    ("राउरकेला", " Rourkela "), ("संबलपुर", " Sambalpur "), ("बरहमपुर", " Berhampur "),
    ("बालेश्वर", " Balasore "), ("झारसुगुड़ा", " Jharsuguda "), ("गुवाहाटी", " Guwahati "),
    ("डिब्रूगढ़", " Dibrugarh "), ("सिलचर", " Silchar "), ("जोरहाट", " Jorhat "),
]
_DEVA_WORDS = sorted(_DEVA_WORDS, key=lambda x: len(x[0]), reverse=True)

# -- Hindi fractional prefixes → float multiplier --
# "dedh lakh" = 1.5 × 1,00,000 = 1,50,000
_HINDI_FRACTIONS = {
    "dedh": 1.5, "derh": 1.5,
    "dhai": 2.5, "adhai": 2.5, "aadhai": 2.5, "dhaai": 2.5,
    "sava": 1.25, "sawa": 1.25, "sawwa": 1.25,
    "paune": 0.75, "paaune": 0.75, "pone": 0.75,
    "saadhe": 0.5, "sadhe": 0.5, "sarhe": 0.5, "saade": 0.5, "sade": 0.5,
}

# -- Hindi cardinal number words (Romanised) → int --
# Only treated as numbers when followed by a magnitude word.
_HINDI_CARDINALS = {
    "ek": 1, "do": 2, "teen": 3, "tin": 3, "char": 4,
    "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
    "saat": 7, "sat": 7, "aath": 8, "aat": 8,
    "nau": 9, "dus": 10, "das": 10, "gyarah": 11, "gyara": 11,
    "barah": 12, "pandrah": 15, "pandra": 15, "solah": 16,
    "bees": 20, "bis": 20, "pachis": 25, "pachees": 25,
    "tees": 30, "chalis": 40, "chalees": 40, "chaalis": 40,
    "pachas": 50, "sau": 100,
}

# -- Magnitude multiplier words → factor --
_MAGNITUDES = {
    "sau": 100, "hundred": 100,
    "hazaar": 1000, "hazar": 1000, "hajar": 1000, "hajaar": 1000,
    "thousand": 1000,
    "lakh": 100_000, "lac": 100_000, "lacs": 100_000, "lakhs": 100_000,
    "crore": 10_000_000, "cr": 10_000_000, "karod": 10_000_000,
}

# -- Unit token sets → canonical unit string --
_PCS_TOKENS = frozenset({
    "pcs", "pc", "nos", "no", "numbers", "number", "units", "unit",
    "pieces", "piece", "bags", "bag", "boxes", "box",
    "sacks", "sack", "pouches", "pouch", "cartons", "carton",
    "rolls", "roll", "sheets", "sheet",
})
_KG_TOKENS = frozenset({"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"})
_MT_TOKENS = frozenset({"mt", "ton", "tons", "tonne", "tonnes"})
_QUINTAL_TOKENS = frozenset({"quintal", "quintals", "qtl", "qtls"})

# -- Capacity / fill-weight context words --
_CAPACITY_WORDS = frozenset({
    "capacity", "cap", "swl", "load", "holding", "holds",
    "carrying", "filling",
})

# -- Price / rate context words --
_PRICE_WORDS = frozenset({
    "rate", "price", "rs", "inr", "budget", "cost",
    "rupee", "rupees", "paisa",
})

# -- Product nouns (for fill-weight detection) --
_PRODUCT_NOUNS = frozenset({
    "bag", "bags", "sack", "sacks", "pouch", "pouches",
    "box", "boxes", "carton", "cartons", "packet", "packets",
    "packing", "bore", "bori", "container",
})

# -- Location stopwords: words that must NEVER be returned as a location --
_LOC_STOPWORDS = frozenset({
    # Business / inquiry
    "need", "quote", "price", "rate", "urgent", "pls", "please",
    "hi", "hello", "sir", "ji", "bhai", "madam", "sahab",
    "contact", "call", "send", "delivery", "deliver", "supply",
    "order", "chahiye", "chahie", "bhej", "batao", "lagega",
    "hume", "mujhe", "liye", "karo", "kijiye", "dijiye", "mangta",
    "requirement", "enquiry", "inquiry", "query", "required",
    "require", "want", "wanted", "best", "good",
    # Packaging / material
    "bopp", "bop", "boop", "woven", "corrugated", "pouch", "film",
    "bag", "bags", "box", "boxes", "sack", "sacks", "carton",
    "cartons", "fibc", "jumbo", "jambo", "mono", "shrink", "stretch",
    "cling", "laminated", "lamination", "hdpe", "ldpe", "lldpe",
    "pp", "pe", "packaging", "packing", "printed", "print",
    "printing", "colour", "color", "gsm", "micron", "mic",
    "ply", "liner", "flute", "kraft", "duplex", "zipper", "spout",
    "doypack", "valve", "gusset", "handle", "tape", "star",
    "cement", "fertilizer", "sugar", "rice", "flour", "atta", "dal",
    "sheet", "roll", "wrap", "seal", "side", "center", "bottom",
    # Units
    "pcs", "pc", "nos", "kg", "kgs", "mt", "ton", "tonne", "tons",
    "tonnes", "pieces", "units", "numbers", "bags", "boxes",
    "sacks", "rolls", "sheets", "kilo", "kilos",
    # Number words
    "lakh", "lac", "lakhs", "lacs", "hazaar", "hazar", "hajar",
    "crore", "cr", "thousand", "hundred", "sau",
    # General noise
    "thanks", "thank", "regards", "ok", "okay", "asap", "sample",
    "quality", "grade", "type", "size", "plain", "natural",
    "white", "transparent", "clear", "virgin", "new", "old",
    "filling", "capacity", "cap", "swl", "load",
    "per", "cost", "budget", "inr", "rs", "rupee",
    "morning", "evening", "revert", "sincerely", "waiting", "reply",
    "moq", "kindly", "gstin", "gst", "quote", "quotation", "order",
    "po", "rfq", "sir", "dear", "hello", "hi", "hey", "team", "rates",
    "discount", "address",
    # Verbs / common English
    "the", "for", "and", "with", "from", "this", "that",
    "can", "you", "your", "our", "will", "not",
    "also", "any", "all", "about", "would", "like",
})


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: TEXT NORMALISATION
# ═══════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """Normalise Unicode, Devanagari digits/words, symbols, and whitespace."""
    if not isinstance(text, str) or not text.strip():
        return ""
    # Unicode NFKC normalisation
    text = unicodedata.normalize("NFKC", text)
    # Devanagari digits ०-९ → 0-9
    text = text.translate(_DEVA_DIGITS)
    # Devanagari words → Romanised
    for deva, roman in _DEVA_WORDS:
        text = text.replace(deva, roman)
    # Currency / micro symbols
    text = text.replace("₹", " rs ")
    text = text.replace("µ", " micron ")
    # Remove thousand-separator commas between digits (e.g. 1,50,000 -> 150000)
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    # Remove remaining non-ASCII (emojis, special chars)
    text = re.sub(r"[^\x00-\x7F]", " ", text)
    # Split digit from stuck known unit only (e.g. "500kg" -> "500 kg", "500pcs" -> "500 pcs")
    _stuck_units = (
        r"(?:kg|kgs|pcs|pc|nos|mt|ton|tonne|tonnes|gsm|mic|micron|microns|"
        r"lakh|lakhs|lac|lacs|hazaar|hazar)"
    )
    text = re.sub(r"(?<=\d)(" + _stuck_units + r")\b", r" \1", text, flags=re.I)
    text = re.sub(r"\b(" + _stuck_units + r")(?=\d)", r"\1 ", text, flags=re.I)
    # Pad select punctuation so tokens split cleanly: , ; : ! ? / (but not inside digits)
    text = re.sub(r"([;!?])", r" \1 ", text)
    text = re.sub(r"(?<!\d),|,(?!\d)", " , ", text)
    text = _composite_numerals(text)
    text = _english_numbers(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


_CARD_WORDS = "|".join(sorted(_HINDI_CARDINALS.keys(), key=len, reverse=True))
_COMPOSITE_LAKH_THOUS_RE = re.compile(
    r"\b(\d+|" + _CARD_WORDS + r")\s*(?:lakhs?|lacs?)\s*(?:and|aur)?\s*"
    r"(\d+|" + _CARD_WORDS + r")\s*(?:haza+r|thousands?|k\b)",
    re.I,
)


def _composite_numerals(text: str) -> str:
    """Combine composite numerals: '1 lakh 20 hazaar' -> '120000', 'ek lakh paanch hazaar' -> '105000'."""
    def _parse_part(w: str) -> int:
        w = w.lower()
        if w.isdigit():
            return int(w)
        return _HINDI_CARDINALS.get(w, 0)

    def repl(m):
        lakh_val = _parse_part(m.group(1))
        thous_val = _parse_part(m.group(2))
        return str(lakh_val * 100000 + thous_val * 1000)

    return _COMPOSITE_LAKH_THOUS_RE.sub(repl, text)



_ENG_ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90,
}
_ENG_DIGIT = r"(?:one|two|three|four|five|six|seven|eight|nine)"
_ENG_NUM_RE = re.compile(
    r"\b(" + "|".join(sorted(_ENG_ONES.keys(), key=len, reverse=True)) + r")"
    r"(?:[\s-]+(" + _ENG_DIGIT + r"))?"
    r"(?=\s+(?:thousand|hundred|lakh|lac|crore|tonnes?|tons?|mt|pieces?|pcs|nos|kg|kgs|bags?|boxes?|cartons?|sacks?)\b)",
    re.I,
)


def _english_numbers(text: str) -> str:
    """Normalize English number phrases: 'twenty five thousand' -> '25 thousand', 'two tonnes' -> '2 tonnes'."""
    def repl(m):
        tens = _ENG_ONES[m.group(1).lower()]
        units = _ENG_ONES[m.group(2).lower()] if m.group(2) else 0
        return str(tens + units)
    return _ENG_NUM_RE.sub(repl, text)



# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: GSM & MICRON EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def extract_gsm(text: str) -> tuple:
    """Extract GSM value; return (int_or_None, text_with_match_masked)."""
    # Pattern A: number then GSM keyword — "65 gsm", "65gsm", "65 g/m2"
    m = re.search(r"\b(\d{2,3})\s*(?:gsm|g\s*/\s*m2|g/m2)\b", text, re.I)
    if m:
        val = int(m.group(1))
        if 20 <= val <= 600:
            return val, text[: m.start()] + " " * len(m.group()) + text[m.end() :]

    # Pattern B: GSM keyword then number — "gsm 65", "gsm: 65"
    m = re.search(r"\b(?:gsm|g\s*/\s*m2)\s*[:\-=]?\s*(\d{2,3})\b", text, re.I)
    if m:
        val = int(m.group(1))
        if 20 <= val <= 600:
            return val, text[: m.start()] + " " * len(m.group()) + text[m.end() :]

    # Pattern C: "65 gms" when plausibly GSM (not grams-of-product)
    m = re.search(r"\b(\d{2,3})\s*gms\b", text, re.I)
    if m:
        val = int(m.group(1))
        after = text[m.end() : m.end() + 25].lower()
        if 30 <= val <= 600 and not re.match(
            r"\s*(?:pouch|packet|pack|bag|sachet|bottle)", after
        ):
            return val, text[: m.start()] + " " * len(m.group()) + text[m.end() :]

    return None, text


def extract_micron(text: str) -> tuple:
    """Extract micron value; return (int_or_None, text_with_match_masked)."""
    # Pattern A: number then micron keyword — "25 mic", "25micron", "25 my"
    m = re.search(
        r"\b(\d{1,3})\s*(?:microns?|mic|micorn|my|mu)\b", text, re.I
    )
    if m:
        val = int(m.group(1))
        if 5 <= val <= 500:
            return val, text[: m.start()] + " " * len(m.group()) + text[m.end() :]

    # Pattern B: keyword then number — "mic 25", "micron: 25"
    m = re.search(
        r"\b(?:microns?|mic|my)\s*[:\-=]?\s*(\d{1,3})\b", text, re.I
    )
    if m:
        val = int(m.group(1))
        if 5 <= val <= 500:
            return val, text[: m.start()] + " " * len(m.group()) + text[m.end() :]

    return None, text


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: INTERFERING-PATTERN MASKING
# ═══════════════════════════════════════════════════════════════════════════

def mask_interfering_patterns(text: str) -> str:
    """Mask numbers that are NOT order quantities: phones, PINs, dims, etc."""

    # Phone numbers: 10-digit Indian mobile (continuous, 5+5, 4+6, 3+3+4, or with prefix)
    text = re.sub(
        r"(?:\b(?:contact|call|phone|mobile|mob|ph|whatsapp|wa|cell)\s*[:\-]?\s*)?"
        r"(?:\+?91[\s\-]?|0)?[6-9](?:\d[\s\-]?){9}\b"
        r"(?!\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|rolls?|sheets?|kg|kgs|mt|ton|tonnes?)\b)",
        " ", text, flags=re.I,
    )

    # Order / Quote / Reference / Inquiry IDs: "order id 4521", "Quote no 1023", "PO# 9876", "ref: 1234"
    text = re.sub(
        r"\b(?:order|quote|quotation|ref|reference|enquiry|inquiry|po|req|rfq|tracking|token)"
        r"\s*(?:id|no|num|number|#|code)\s*[:\-#]?\s*[A-Z0-9-]*\d[A-Z0-9-]*\b",
        " ", text, flags=re.I,
    )
    text = re.sub(
        r"\b(?:quote|ref|reference|po|rfq)\s*[:\-#]\s*[A-Z0-9-]*\d[A-Z0-9-]*\b",
        " ", text, flags=re.I,
    )

    # PIN codes: "pin 440001", "pincode: 110020"
    text = re.sub(
        r"\b(?:pin|pincode|pin\s*code)\s*[:\-]?\s*\d{6}\b", " ", text, flags=re.I
    )
    # Standalone 6-digit at end of text (likely PIN near a city)
    text = re.sub(r"\b[1-8]\d{5}\s*$", " ", text)

    # Freight / logistics unit masking: "1 truck load", "2 container" (not product quantities)
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:truck|container|tempo|trailer|gadi|gaadi|trolley|lorry|fcl|lcl)(?:\s*loads?)?\b",
        " ", text, flags=re.I,
    )

    # Dimensions: "12x18 inch", "40×60 cm", "300*450*50 mm"
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:x|×|\*|by)\s*\d+(?:\.\d+)?"
        r"(?:\s*(?:x|×|\*|by)\s*\d+(?:\.\d+)?)?"
        r"(?:\s*(?:inch|in|\"|mm|cm|mtr|meter|metre|m|feet|ft))?\b",
        " ", text, flags=re.I,
    )

    # Prices/rates: "rate 85/kg", "rs 12", "budget 50000" (only if NOT followed by pcs/units)
    text = re.sub(
        r"\b(?:rate|price|rs|inr|budget|cost)\s*[:\-]?\s*(\d+(?:\.\d+)?)(?:\s*/\s*\w+)?"
        r"(?!\s*(?:pcs|pc|nos|bags|boxes|units|pieces|sacks|kg|mt|ton))\b",
        " ", text, flags=re.I,
    )
    # "₹45/bag" → already replaced ₹ with "rs" in normalise
    # "85/kg", "12/pc" (bare rate fraction)
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*/\s*(?:kg|pc|pcs|bag|unit|piece|box|mt|ton)\b",
        " ", text, flags=re.I,
    )

    # Ply counts: "3 ply", "5 ply"
    text = re.sub(r"\b\d{1,2}\s*ply\b", " __PLY ", text, flags=re.I)

    # Colour counts: "4 colour", "2 color printing"
    text = re.sub(r"\b\d{1,2}\s*colou?r\b", " ", text, flags=re.I)

    # Side-print specs: "2 side print"
    text = re.sub(r"\b\d{1,2}\s*side\b", " ", text, flags=re.I)

    # Dates: "15th Aug", "25/11/2024"
    text = re.sub(
        r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*",
        " ", text, flags=re.I,
    )
    text = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", text)

    # Lead times: "10 days", "2 weeks"
    text = re.sub(r"\b\d+\s*(?:days?|weeks?|months?)\b", " ", text, flags=re.I)

    # Supplier constraint / MOQ masking: literal acronym "MOQ" and "minimum order quantity"
    text = re.sub(
        r"\b(?:moq|min(?:imum)?\s*order\s*quantity)\s*[:\-]?\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|rolls?|sheets?|kg|kgs|mt|ton|tonnes?))?\b",
        " ", text, flags=re.I,
    )
    text = re.sub(
        r"\b\d[\d,]*(?:\.\d+)?\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|rolls?|sheets?|kg|kgs|mt|ton|tonnes?)?\s*(?:moq|min(?:imum)?\s*order\s*quantity)\b",
        " ", text, flags=re.I,
    )

    # Past orders / historical references: "last time 1000 pcs", "earlier 10 ton", "previously 5000", "pehle 2000"
    text = re.sub(
        r"\b(?:last\s+time|earlier|previously|pehle|previous(?:\s+order)?)(?:\s+(?:we\s+ordered|we\s+bought|ordered|taken|bought|humne\s+liya))?\s*[:\-]?\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|rolls?|sheets?|kg|kgs|mt|ton|tonnes?))?\b",
        " ", text, flags=re.I,
    )

    # Gram / milliliter pack contents: "500 gm", "250g pack", "100 ml" (fill size, not order quantity)
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:gm|gms|grams?|g\b|ml|ltrs?|litres?|liters?)(?!\s*/\s*m2)\b",
        " ", text, flags=re.I,
    )

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: CATEGORY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def classify_category(text: str, gsm: int | None = None) -> str:
    """Classify RFQ into one of 7 packaging categories using priority rules."""
    t = text.lower()

    # ── Priority 1: FIBC / jumbo / bulk bags ──
    # Checked first because "jumbo bag" contains "bag" which could match others.
    if re.search(r"\bfibc\b", t):
        return "fibc"
    if re.search(r"\b(?:jumbo|jambo)\b", t) and not re.search(r"\b(?:roll|film|box|carton)\b", t):
        return "fibc"
    if re.search(r"\b(?:bulk|big|baffle)\s*bags?\b", t):
        return "fibc"

    # ── Priority 2: BOPP bag (BOPP bag/sack/woven, but NOT "BOPP film" or "BOPP tape/rolls") ──
    has_bopp = bool(re.search(r"\b(?:bopp|bop|boop|opp)\b", t))
    has_bopp_film = bool(re.search(r"\b(?:bopp|bop|boop)\s*(?:film|tape|roll)\b", t) or re.search(r"\b(?:tape|rolls?)\b", t))
    if has_bopp and not has_bopp_film:
        return "bopp_bag"

    # ── Priority 3: Mono carton ──
    if re.search(r"\bmono\s*(?:carton|cartoon)s?\b", t):
        return "mono_carton"
    if re.search(r"\b(?:folding|duplex|cosmetic|pharma)\s*(?:carton|cartoon|box)s?\b", t):
        return "mono_carton"
    if re.search(r"\bduplex\s+board\b", t):
        return "mono_carton"
    if re.search(r"\bcartoo?ns?\b", t) and ((gsm is not None and gsm >= 200) or re.search(r"\b\d+\s*gsm\b", t) or "gsm" in t) and not re.search(r"\bcorrugated\b|__PLY", t):
        return "mono_carton"

    # ── Priority 4: Film (shrink, stretch, cling, BOPP film, LDPE film) ──
    if re.search(r"\b(?:shrink|shrnk|stretch)\b", t) and not re.search(r"\b(?:bags?|sacks?|box|boxes|carton|pouch)\b", t):
        return "film"
    if re.search(r"\bcling\s*film\b", t):
        return "film"
    if has_bopp_film:
        return "film"
    if re.search(r"\b(?:ldpe|lldpe|hdpe|pe)\s*film\b", t):
        return "film"
    if re.search(r"\b(?:packaging|lamination|pallet)\s*film\b", t):
        return "film"

    # ── Priority 5: Corrugated box explicit ("corrugated", "master carton", ply) ──
    # Check explicit corrugated BEFORE generic pouch to handle "corrugated box with inner pouch"
    if re.search(r"\bcorrugated\b", t):
        return "corrugated_box"
    if re.search(r"\b__PLY\b", t):  # masked ply → corrugated
        return "corrugated_box"
    if re.search(r"\bmaster\s*(?:carton|box)\b", t):
        return "corrugated_box"

    # ── Priority 6: Woven sack / PP woven / cement / AD Star / bori ──
    if re.search(r"\bwoven\b", t):
        return "woven_sack"
    if re.search(r"\bpp\s*(?:bags?|sacks?)\b", t):
        return "woven_sack"
    if re.search(r"\b(?:cement|fertili[sz]er|sand|sugar|rice|atta|flour|dal)\s*(?:bags?|sacks?)\b", t):
        return "woven_sack"
    if re.search(r"\bad\s*star\b", t) or re.search(r"\badstar\b", t):
        return "woven_sack"
    if re.search(r"\bhdpe\s*(?:bags?|sacks?)\b", t):
        return "woven_sack"
    if re.search(r"\blaminated\s*sack\b", t):
        return "woven_sack"
    if re.search(r"\b(?:bori|bore)\b", t):
        return "woven_sack"

    # ── Priority 7: Pouch ──
    if re.search(r"\b(?:stand\s*up|zipper|spout|retort|vacuum)\s*pouch", t):
        return "pouch"
    if re.search(r"\bdoypack\b", t):
        return "pouch"
    if re.search(r"\b(?:pouche?s?|pauch(?:es)?)\b", t):
        return "pouch"
    if re.search(r"\bzipper\b", t):
        return "pouch"
    if re.search(r"\b(?:3|three)\s*side\s*seal\b", t):
        return "pouch"
    if re.search(r"\bcenter\s*seal\b", t):
        return "pouch"

    # ── Fallback single-word matches ──
    if re.search(r"\bfilm\b", t) or re.search(r"\bwrap\b", t):
        return "film"
    if re.search(r"\bsacks?\b", t):
        return "woven_sack"
    # "cement ke liye bag" → woven_sack
    if re.search(r"\bcement\b", t) and re.search(r"\bbags?\b", t):
        return "woven_sack"
    if re.search(r"\bboxe?s?\b", t):
        return "corrugated_box"
    if re.search(r"\bcartoo?ns?\b", t):
        return "corrugated_box"
    if re.search(r"\bbags?\b", t):
        return "woven_sack"
    if re.search(r"\brolls?\b", t):
        return "film"

    # Absolute fallback
    return "corrugated_box"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: NUMBER PARSING & QUANTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def _canonicalise_unit(token: str) -> str | None:
    """Map a raw unit token to canonical 'pcs', 'kg', or 'mt'."""
    if not token:
        return None
    w = token.lower().strip()
    if w in _PCS_TOKENS:
        return "pcs"
    if w in _KG_TOKENS:
        return "kg"
    if w in _MT_TOKENS:
        return "mt"
    if w in _QUINTAL_TOKENS:
        return "quintal"
    if w == "metric":
        return "mt"  # part of "metric ton"
    return None


def _peek_unit(text: str, pos: int) -> str | None:
    """Look for a unit token at or shortly after position `pos` in text."""
    remaining = text[pos:].lstrip()
    words = re.findall(r"\w+", remaining[:60])
    if not words:
        return None
    # Skip optional packaging adjectives to find the unit noun (e.g. "5000 [jumbo] bags")
    skip_adj = {
        "jumbo", "jambo", "bulk", "cement", "plain", "printed", "corrugated",
        "woven", "pp", "hdpe", "ldpe", "bopp", "bop", "mono", "folding",
        "heavy", "duty", "side", "seal", "ply", "mic", "gsm", "star", "ad",
        "valve", "zipper", "stand", "up", "spout", "pack", "packing", "size",
    }
    for i, w in enumerate(words[:4]):
        w_lower = w.lower()
        if w_lower == "metric" and i + 1 < len(words) and words[i + 1].lower() in ("ton", "tonne", "tons", "tonnes"):
            return "mt"
        canon = _canonicalise_unit(w_lower)
        if canon:
            return canon
        if w_lower not in skip_adj:
            break
    return None


def _peek_unit_before(text: str, pos: int) -> str | None:
    """Look for a unit token immediately before position `pos` in text."""
    before = text[:pos].rstrip()
    m = re.search(r"(\w+)\s*$", before)
    if not m:
        return None
    return _canonicalise_unit(m.group(1))


def _to_int_or_float(value: float):
    """Return int if the value is whole, otherwise float."""
    if value == int(value):
        return int(value)
    return float(value)


def _build_magnitude_re() -> str:
    """Build a regex alternation of all magnitude words."""
    words = sorted(_MAGNITUDES.keys(), key=len, reverse=True)
    return "|".join(re.escape(w) for w in words)


def _build_fraction_re() -> str:
    """Build a regex alternation of all Hindi fractional prefixes."""
    words = sorted(_HINDI_FRACTIONS.keys(), key=len, reverse=True)
    return "|".join(re.escape(w) for w in words)


def _build_cardinal_re() -> str:
    """Build a regex alternation of all Hindi cardinal number words."""
    words = sorted(_HINDI_CARDINALS.keys(), key=len, reverse=True)
    return "|".join(re.escape(w) for w in words)


_MAG_RE = _build_magnitude_re()
_FRAC_RE = _build_fraction_re()
_CARD_RE = _build_cardinal_re()

_BARE_CARDINALS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4,
    "paanch": 5, "panch": 5, "chhe": 6,
    "saat": 7, "aath": 8,
    "nau": 9, "das": 10, "dus": 10,
}
_BARE_CARD_RE = "|".join(re.escape(w) for w in sorted(_BARE_CARDINALS.keys(), key=len, reverse=True))

_PROD_NOUN_OR_UNIT_FOLLOW = (
    r"(?:(?:corrugated|master|plain|printed|mono|duplex|woven|pp|bopp|shrink|stretch|jumbo)\s+)?"
    r"(?:box|boxes|cartoo?ns?|cartoon|bags?|pouche?s?|pauch(?:es)?|sacks?|bore?|bori|rolls?|sheets?|"
    r"pcs|pc|nos|units?|pieces?|numbers?|kg|kgs|kilo|mt|tons?|tonnes?)"
)
_BARE_CARD_PAT = re.compile(
    r"\b(" + _BARE_CARD_RE + r")\s+(?=" + _PROD_NOUN_OR_UNIT_FOLLOW + r"\b)", re.I
)

_PRODUCT_KEYWORD_RE = re.compile(
    r"\b("
    r"bopp|bop|boop|opp|"
    r"fibc|jumbo|jambo|"
    r"mono\s*cartoo?ns?|folding\s*cartoo?ns?|duplex|"
    r"shrink|stretch|cling|film|rolls?|"
    r"corrugated|box|boxes|cartoo?ns?|cartoon|"
    r"woven|sacks?|bori|bore|ad\s*star|adstar|"
    r"pouche?s?|pauch(?:es)?|doypack|zipper|"
    r"bags?"
    r")\b",
    re.I,
)

_PROD_DELIM_RE = re.compile(r"(?:\b(?:and|aur|or|ya)\b|[&,+])", re.I)


def _split_first_product_segment(text: str) -> tuple[str, bool]:
    """Split multi-product RFQ at and/aur/&/,/+ and return (first_segment, is_multi)."""
    delims = list(_PROD_DELIM_RE.finditer(text))
    if not delims:
        return text, False

    slices = []
    prev = 0
    for d in delims:
        slices.append((prev, d.start()))
        prev = d.end()
    slices.append((prev, len(text)))

    prod_indices = []
    for i, (start, end) in enumerate(slices):
        if _PRODUCT_KEYWORD_RE.search(text[start:end]):
            prod_indices.append(i)

    if len(prod_indices) < 2:
        return text, False

    second_idx = prod_indices[1]
    split_pos = delims[second_idx - 1].start()
    delim_token = delims[second_idx - 1].group().strip()
    first_segment = text[:split_pos].strip()
    second_segment = text[delims[second_idx - 1].end():].strip()

    # Comma split guard: stop treating a comma as a product boundary unless BOTH sides contain a quantity
    if delim_token == ",":
        cands1 = _find_quantity_candidates(first_segment)
        valid1 = [
            c for c in cands1
            if not _is_capacity(c, first_segment)
            and not re.search(r"\b(?:for|of)\s*$", first_segment[max(0, c["start"] - 15) : c["start"]].lower())
        ]
        cands2 = _find_quantity_candidates(second_segment)
        valid2 = [
            c for c in cands2
            if not _is_capacity(c, second_segment)
            and not re.search(r"\b(?:for|of)\s*$", second_segment[max(0, c["start"] - 15) : c["start"]].lower())
        ]
        if not (valid1 and valid2):
            return text, False

    # Guard 1: First segment must contain a number (quantity/spec digits or number words, not just product names)
    has_number = bool(
        re.search(r"\d", first_segment)
        or re.search(r"\b(?:" + _CARD_RE + r"|" + _MAG_RE + r"|" + _FRAC_RE + r")\b", first_segment, re.I)
    )
    if not has_number:
        return text, False

    # Guard 2: The two product segments must resolve to different categories
    cat1 = classify_category(first_segment)
    cat2 = classify_category(second_segment)
    if cat1 == cat2:
        return text, False

    return first_segment, True


def _find_quantity_candidates(text: str) -> list[dict]:
    """Find all numeric expressions in text with value, position, and unit."""
    candidates = []
    used_spans = []  # (start, end) of already-matched regions

    def _overlaps(start, end):
        return any(s <= start < e or s < end <= e for s, e in used_spans)

    # ── Group 0: Hindi fraction + cardinal + magnitude ──
    # e.g. "paune do lakh" → (2 - 0.25) × 100000 = 175000
    # "sawa teen lakh" → (3 + 0.25) × 100000 = 325000
    # "saadhe char lakh" → (4 + 0.5) × 100000 = 450000
    pat0 = re.compile(
        r"\b(" + _FRAC_RE + r")\s+(" + _CARD_RE + r")\s+(" + _MAG_RE + r")\b", re.I
    )
    for m in pat0.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        frac_w = m.group(1).lower()
        card_val = _HINDI_CARDINALS[m.group(2).lower()]
        mag_val = _MAGNITUDES[m.group(3).lower()]
        if frac_w in ("paune", "paaune", "pone"):
            calc_val = (card_val - 0.25) * mag_val
        elif frac_w in ("sava", "sawa", "sawwa"):
            calc_val = (card_val + 0.25) * mag_val
        elif frac_w in ("saadhe", "sadhe", "sarhe", "saade", "sade"):
            calc_val = (card_val + 0.5) * mag_val
        else:
            calc_val = _HINDI_FRACTIONS.get(frac_w, 1.0) * card_val * mag_val
        candidates.append({
            "value": calc_val,
            "start": m.start(), "end": m.end(),
            "unit": _peek_unit(text, m.end()),
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 1: Hindi fraction + magnitude ──
    # e.g. "dedh lakh" → 1.5 × 100000 = 150000
    pat1 = re.compile(
        r"\b(" + _FRAC_RE + r")\s+(" + _MAG_RE + r")\b", re.I
    )
    for m in pat1.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        frac = _HINDI_FRACTIONS[m.group(1).lower()]
        mag = _MAGNITUDES[m.group(2).lower()]
        candidates.append({
            "value": frac * mag,
            "start": m.start(), "end": m.end(),
            "unit": _peek_unit(text, m.end()),
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 2: Hindi cardinal + magnitude ──
    # e.g. "do hazaar" → 2 × 1000 = 2000
    pat2 = re.compile(
        r"\b(" + _CARD_RE + r")\s+(" + _MAG_RE + r")\b", re.I
    )
    for m in pat2.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        card = _HINDI_CARDINALS[m.group(1).lower()]
        mag = _MAGNITUDES[m.group(2).lower()]
        candidates.append({
            "value": card * mag,
            "start": m.start(), "end": m.end(),
            "unit": _peek_unit(text, m.end()),
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 2b: bare "sau" / "hundred" followed by unit token ──
    # e.g. "sau pcs" → 100 pcs
    pat_sau = re.compile(r"\b(sau|hundred)\b", re.I)
    for m in pat_sau.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        unit = _peek_unit(text, m.end())
        if unit:
            candidates.append({
                "value": 100.0,
                "start": m.start(), "end": m.end(),
                "unit": unit,
                "raw": m.group(),
            })
            used_spans.append((m.start(), m.end()))

    # ── Group 2c: bare Hindi cardinal followed by product noun or unit word ──
    # e.g. "char carton box", "do box", "das pcs" (NOT "do send quote" or "bhej do")
    for m in _BARE_CARD_PAT.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        token = m.group(1).lower()
        if token == "do":
            before_txt = text[:m.start()].strip().lower()
            last_word = before_txt.split()[-1] if before_txt else ""
            if last_word in ("bhej", "kar", "bata", "de", "kr", "pls", "please"):
                continue
        card_val = _BARE_CARDINALS[token]
        unit = _peek_unit(text, m.end())
        candidates.append({
            "value": float(card_val),
            "start": m.start(), "end": m.end(),
            "unit": unit,
            "raw": m.group(1),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 3: digits + K/k or L/l suffix ──
    # e.g. "20k" → 20000, "10L" → 1000000 (10 lakh)
    pat3 = re.compile(r"\b(\d+(?:\.\d+)?)\s*([kK]|[lL])\b")
    for m in pat3.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        suffix = m.group(2).lower()
        multiplier = 100_000 if suffix == "l" else 1000
        val = float(m.group(1)) * multiplier
        candidates.append({
            "value": val,
            "start": m.start(), "end": m.end(),
            "unit": _peek_unit(text, m.end()),
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 4: digits + magnitude word ──
    # e.g. "2.5 lakh" → 250000, "40 hazaar" → 40000
    pat4 = re.compile(
        r"\b(\d+(?:\.\d+)?)\s+(" + _MAG_RE + r")\b", re.I
    )
    for m in pat4.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        val = float(m.group(1)) * _MAGNITUDES[m.group(2).lower()]
        candidates.append({
            "value": val,
            "start": m.start(), "end": m.end(),
            "unit": _peek_unit(text, m.end()),
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    # ── Group 5: plain number (handles Indian comma format and decimals < 1 like 0.5 MT) ──
    # e.g. "5000", "1,50,000", "0.5"
    pat5 = re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\b")
    for m in pat5.finditer(text):
        if _overlaps(m.start(), m.end()):
            continue
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        if val <= 0:  # ignore 0 and negative
            continue
        unit = _peek_unit(text, m.end())
        # Also check if this number is right after a unit (e.g. "kg 500")
        if unit is None:
            before_txt = text[:m.start()].rstrip()
            # Only peek unit before if not preceded by another number (e.g. "kg 500", but NOT "25 kg 10000")
            if not re.search(r"\d+\s*\w+\s*$", before_txt):
                unit = _peek_unit_before(text, m.start())
        candidates.append({
            "value": val,
            "start": m.start(), "end": m.end(),
            "unit": unit,
            "raw": m.group(),
        })
        used_spans.append((m.start(), m.end()))

    for c in candidates:
        if c["unit"] == "quintal":
            c["value"] = c["value"] * 100.0
            c["unit"] = "kg"

    return candidates


def _context_words(text: str, start: int, end: int, window: int = 40) -> str:
    """Get lowered context words around a span for fill-weight/capacity checks."""
    before = text[max(0, start - window) : start].lower()
    after = text[end : end + window].lower()
    return before + " | " + after


def _is_capacity(candidate: dict, text: str) -> bool:
    """Return True if the candidate quantity is a capacity/SWL spec, not order qty."""
    # Look directly after candidate (and its unit) for capacity markers: e.g. "1000 kg capacity", "1 ton SWL"
    after = text[candidate["end"] : candidate["end"] + 30].lower()
    before = text[max(0, candidate["start"] - 25) : candidate["start"]].lower()

    # Marker right after candidate or right after unit
    if re.search(r"^\s*(?:kg|ton|tonne|mt)?\s*(?:capacity|cap|swl|load|holding|carrying|holds)\b", after):
        return True
    # Marker right before candidate: e.g. "capacity: 1000 kg", "SWL 1 ton"
    if re.search(r"\b(?:capacity|cap|swl|load|holding|carrying|holds)\s*[:\-=]?\s*$", before):
        return True
    return False


def _is_moq_supplier(candidate: dict, text: str) -> bool:
    """Return True if candidate is explicitly labeled with literal acronym 'MOQ' or 'minimum order quantity'."""
    after = text[candidate["end"] : candidate["end"] + 30].lower()
    before = text[max(0, candidate["start"] - 35) : candidate["start"]].lower()
    if re.search(r"\b(?:moq|min(?:imum)?\s*order\s*quantity)\s*[:\-]?\s*$", before):
        return True
    if re.search(r"^\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|kg|kgs|mt|ton|tonnes?)?\s*(?:moq|min(?:imum)?\s*order\s*quantity)\b", after):
        return True
    return False


def _is_min_wording(candidate: dict, text: str) -> bool:
    """Return True if candidate is qualified by buyer-side 'min' wording (e.g. 'min qty', 'minimum quantity', 'minimum', 'min')."""
    before = text[max(0, candidate["start"] - 30) : candidate["start"]].lower()
    after = text[candidate["end"] : candidate["end"] + 30].lower()
    if re.search(r"\bmin(?:imum)?(?:\s*(?:order|qty|quantity))?\s*[:\-]?\s*$", before):
        return True
    if re.search(r"^\s*(?:pcs|pc|nos|bags?|boxes?|cartons?|sacks?|units?|pieces?|kg|kgs|mt|ton|tonnes?)?\s*min(?:imum)?(?:\s*(?:order|qty|quantity))?\b", after):
        return True
    return False


def _is_fill_weight(
    candidate: dict, text: str, all_candidates: list, category: str
) -> bool:
    """Return True if the candidate is a fill weight (e.g. '25 kg bag', 'bag 50 kg')."""
    # Film is ordered by weight — kg/mt is the real quantity, not fill weight
    if category == "film":
        return False
    # Only kg/mt candidates can be fill weights
    if candidate["unit"] not in ("kg", "mt"):
        return False
    # Metric tonnes are never the fill-weight of small packaging
    if candidate["unit"] == "mt" and category in (
        "woven_sack", "bopp_bag", "pouch", "corrugated_box", "mono_carton"
    ):
        return False
    # Need at least one other candidate to mark this one as fill weight
    if len(all_candidates) < 2:
        return False

    after = text[candidate["end"] : candidate["end"] + 40].lower()
    before = text[max(0, candidate["start"] - 25) : candidate["start"]].lower()

    # Pattern: "<number> kg bag" or "bag <number> kg" (product noun before or after)
    for noun in _PRODUCT_NOUNS:
        if re.search(r"\b" + re.escape(noun) + r"\b", after[:25]):
            return True
        if re.search(r"\b" + re.escape(noun) + r"\b", before):
            return True

    # Pattern: "of <number> kg" or "for <number> kg" — fill weight after "of" / "for"
    if re.search(r"\b(?:of|for)\s*$", before):
        return True

    # Pattern: "ke <number> kg", "ka <number> kg"
    if re.search(r"\b(?:ke|ka|ki|wale|wala|wali)\s*$", before):
        return True

    # Pattern: "<number> kg ke <quantity>" (Hindi: "25 kg ke 2 lakh")
    if re.search(r"^\s*(?:ke|ka|ki|wale|wala|wali|qty|quantity)\b", after):
        return True

    # Pattern: "<number> kg x" or "x <number> kg" (multiplicative)
    if re.search(r"\bx\s*$", before) or re.search(r"^\s*x\b", after):
        return True

    # Pattern: standard bag fill weight (<= 100 kg) when another candidate exists
    other_vals = [c["value"] for c in all_candidates if c is not candidate]
    if candidate["value"] <= 100 and any(v >= 200 for v in other_vals):
        return True

    return False


def extract_quantity_and_unit(text: str, category: str) -> tuple:
    """Extract order quantity and canonical unit from cleaned RFQ text."""
    candidates = _find_quantity_candidates(text)

    default_unit = "kg" if category == "film" else "pcs"

    if not candidates:
        return None, default_unit

    # Filter out capacity, fill-weight, and supplier MOQ constraint candidates
    valid = []
    for c in candidates:
        if _is_capacity(c, text):
            continue
        if _is_fill_weight(c, text, candidates, category):
            continue
        if _is_moq_supplier(c, text):
            continue
        valid.append(c)

    if not valid:
        # All filtered — check if any candidate has an explicit count (pcs) that isn't supplier MOQ
        pcs_cands = [c for c in candidates if c["unit"] == "pcs" and not _is_moq_supplier(c, text)]
        if pcs_cands:
            valid = pcs_cands
        else:
            # All candidates were purely capacity or fill weight specs (no order quantity)
            return None, default_unit

    # Buyer wording ('min ...') numbers are dropped only when another quantity exists in the message
    non_min_candidates = [c for c in valid if not _is_min_wording(c, text)]
    if non_min_candidates:
        valid = non_min_candidates

    # Selection: prefer candidates with explicit unit
    if category != "film":
        count_cands = [c for c in valid if c["unit"] == "pcs" or c["value"] >= 200]
        small_kg = [c for c in valid if c["unit"] in ("kg", "mt") and c["value"] <= 100]
        if count_cands and small_kg:
            valid = count_cands

    with_unit = [c for c in valid if c["unit"] is not None]
    if with_unit:
        if category == "film":
            # Prefer kg/mt for film
            preferred = [c for c in with_unit if c["unit"] in ("kg", "mt")]
            chosen = preferred[0] if preferred else with_unit[0]
        else:
            # Prefer pcs for discrete products
            preferred = [c for c in with_unit if c["unit"] == "pcs"]
            chosen = preferred[0] if preferred else with_unit[0]
    else:
        # No explicit unit: take the largest remaining number
        chosen = max(valid, key=lambda c: c["value"])

    unit = chosen["unit"] or default_unit
    qty = _to_int_or_float(chosen["value"])
    return qty, unit


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: LOCATION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

_STATES = frozenset({
    "maharashtra", "gujarat", "rajasthan", "punjab", "haryana", "uttar pradesh",
    "madhya pradesh", "bihar", "jharkhand", "odisha", "west bengal", "karnataka",
    "kerala", "tamil nadu", "telangana", "andhra pradesh", "assam", "chhattisgarh",
    "uttarakhand", "himachal pradesh", "delhi", "goa", "up", "mp",
})


def _load_gazetteer() -> tuple:
    """Load city/location names; return (set_of_lowercase, list_sorted_by_length)."""
    entries = set()
    cities_path = Path(__file__).parent / "cities.txt"
    if cities_path.exists():
        with open(cities_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    entries.add(line)
    else:
        # Embedded fallback: all 300+ Indian cities + export destinations
        entries = {
            "Abu Dhabi", "Accra", "Addis Ababa", "Afghanistan", "Agartala", "Agra",
            "Ahmedabad", "Aizawl", "Ajmer", "Akola", "Aligarh", "Allahabad",
            "Alwar", "Ambala", "Amravati", "Amritsar", "Anantapur", "Andhra Pradesh",
            "Ankleshwar", "Arunachal Pradesh", "Asansol", "Assam", "Aurangabad", "Australia",
            "Baddi", "Bahrain", "Ballari", "Banaras", "Bangalore", "Bangkok",
            "Bangladesh", "Bareilly", "Barmer", "Baroda", "Bathinda", "Belagavi",
            "Belgaum", "Belgium", "Bellary", "Bengaluru", "Berlin", "Bhagalpur",
            "Bharuch", "Bhavnagar", "Bhilai", "Bhilwara", "Bhimavaram", "Bhiwandi",
            "Bhiwani", "Bhiwadi", "Bhopal", "Bhubaneswar", "Bidar", "Bihar", "Bikaner",
            "Bilaspur", "Bokaro", "Bombay", "Brazil", "Cairo", "Calcutta",
            "Calicut", "Canada", "Chandigarh", "Chandrapur", "Chennai", "Chhattisgarh",
            "China", "Chittagong", "Chittoor", "Chittorgarh", "Cochin", "Coimbatore", "Colombo",
            "Cuttack", "Daman", "Dar es Salaam", "Davangere", "Dehradun", "Delhi",
            "Dewas", "Dhaka", "Dhanbad", "Dhule", "Dibrugarh", "Dimapur",
            "Dindigul", "Doha", "Dombivli", "Dubai", "Durban", "Durg",
            "Durgapur", "Egypt", "Eluru", "Ernakulam", "Erode", "Ethiopia",
            "Faridabad", "Firozabad", "France", "Gandhidham", "Gandhinagar", "Gangtok",
            "Gaya", "Germany", "Ghana", "Ghaziabad", "Goa", "Gondia",
            "Gorakhpur", "Greater Noida", "Gujarat", "Gulbarga", "Guntur", "Gurgaon",
            "Gurugram", "Guwahati", "Gwalior", "Haldia", "Haldwani", "Haridwar",
            "Haryana", "Hassan", "Hazaribagh", "Himachal Pradesh", "Hisar", "Hoshiarpur",
            "Hosur", "Howrah", "Hubli", "Hyderabad", "Ichalkaranji", "Imphal",
            "Indonesia", "Indore", "Iran", "Iraq", "Istanbul", "Italy",
            "Itanagar", "Jabalpur", "Jaipur", "Jakarta", "Jalandhar", "Jalgaon",
            "Jammu", "Jamnagar", "Jamshedpur", "Japan", "Jeddah", "Jharkhand",
            "Jharsuguda", "Jodhpur", "Johannesburg", "Jorhat", "Kadapa", "Kakinada",
            "Kalaburagi", "Kalyan", "Kampala", "Kandla", "Kanpur", "Karimnagar",
            "Karnal", "Karnataka", "Karur", "Kashipur", "Kathmandu", "Kenya",
            "Kerala", "Khammam", "Kishangarh", "Kochi", "Kohima", "Kolhapur",
            "Kolkata", "Korba", "Kota", "Kozhikode", "Kuala Lumpur", "Kurnool",
            "Kutch", "Kuwait", "Lagos", "Latur", "London", "Lucknow",
            "Ludhiana", "Madhya Pradesh", "Madras", "Madurai", "Maharashtra", "Malaysia",
            "Manali", "Mandya", "Mangalore", "Mangaluru", "Manila", "Manipur",
            "Margao", "Mathura", "Meerut", "Meghalaya", "Mehsana", "Melbourne",
            "Mexico", "Mizoram", "Mohali", "Mombasa", "Moradabad", "Morbi",
            "Morocco", "Moscow", "Mumbai", "Mundra", "Muscat", "Muzaffarnagar",
            "Muzaffarpur", "Myanmar", "Mysore", "Mysuru", "Nagaland", "Nagpur",
            "Nairobi", "Nalagarh", "Namakkal", "Nanded", "Nashik", "Navi Mumbai",
            "Navsari", "Neemrana", "Nellore", "Nepal", "Netherlands", "New Delhi",
            "New Zealand", "Nigeria", "Nizamabad", "Noida", "Odisha", "Oman",
            "Ongole", "Palakkad", "Palghar", "Pali", "Panaji", "Panchkula",
            "Panipat", "Panvel", "Paris", "Parwanoo", "Pathankot", "Patna",
            "Philippines", "Pithampur", "Pondicherry", "Poona", "Porbandar", "Prayagraj", "Puducherry",
            "Pune", "Punjab", "Qatar", "Raichur", "Raipur", "Rajahmundry",
            "Rajasthan", "Rajkot", "Ranchi", "Ratlam", "Ratnagiri", "Rewa",
            "Rishikesh", "Riyadh", "Rohtak", "Roorkee", "Rourkela", "Rudrapur",
            "Russia", "Saharanpur", "Salem", "Sambalpur", "Sambhajinagar", "Sangli",
            "Sao Paulo", "Satara", "Satna", "Saudi Arabia", "Selaqui", "Sharjah",
            "Shillong", "Shimla", "Shimoga", "Sikar", "Sikkim", "Siliguri",
            "Silvassa", "Singapore", "Sitarganj", "Solan", "Solapur", "Sonipat",
            "South Africa", "South Korea", "Spain", "Sri Ganganagar", "Sri Lanka", "Srinagar",
            "Surat", "Surendranagar", "Sydney", "Tamil Nadu", "Tanzania", "Telangana",
            "Tezpur", "Thailand", "Thane", "Thanjavur", "Thiruvananthapuram", "Thrissur",
            "Tiruchirappalli", "Tirupati", "Tirupur", "Tokyo", "Toronto", "Trichy",
            "Tripura", "Trivandrum", "Tumkur", "Turkey", "UAE", "UK",
            "USA", "Udaipur", "Uganda", "Ujjain", "United Kingdom", "United States",
            "Uttar Pradesh", "Uttarakhand", "Vadodara", "Valsad", "Vapi", "Varanasi",
            "Vasai", "Vasco", "Vellore", "Vietnam", "Vijayawada", "Virar",
            "Visakhapatnam", "Vizag", "Warangal", "Wardha", "West Bengal", "Yangon",
            "Yavatmal",
        }

    # Build a lookup set (lowercase) and a list sorted longest-first
    lookup = {e.lower() for e in entries}
    sorted_list = sorted(entries, key=len, reverse=True)
    return lookup, sorted_list


_AMBIGUOUS_CITY_WORDS = frozenset({
    "mandi", "una", "pali", "ara", "bhind", "sagar", "dhar", "guna",
    "gola", "puri", "tonk", "bar", "nana", "line", "cantt", "road",
    "market", "nagar", "pur", "bad", "garh", "hall", "point",
})

_GAZETTEER_SET, _GAZETTEER_LIST = _load_gazetteer()
_CITY_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(e) for e in _GAZETTEER_LIST) + r")\b",
    re.I,
)


_SIGNOFF_WORDS = r"(?:regards|thanks|thank\s+you|kindly\s+revert|kindly|revert|reply|good\s+morning|good\s+evening|waiting|sincerely|warm\s+regards|best\s+regards)"
_SIGNOFF_TRAILING_RE = re.compile(
    r"(?:^|[\s,.;!?]+)(?:" + _SIGNOFF_WORDS + r")(?:[\s\w.,!?-]{0,60})?$",
    re.I,
)


_DEST_PATTERNS = [
    re.compile(r'(?i:\b(?:deliver(?:y)?|dispatch|send|ship|destination)\s+(?:it\s+)?(?:to|at|in|:|for)?\s*)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)'),
    re.compile(r'(?i:\bse\s+)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)(?i:\s+tak\b)'),
    re.compile(r'(?i:\b(?:our\s+)?(?:site|warehouse|client)\s+(?:in|at)\s+)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)'),
    re.compile(r'(?i:\bto\s+)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*(?:[.,!?]|$)'),
]


def extract_location(text: str) -> str | None:
    """Extract delivery location using gazetteer match + contextual fallback."""

    # ── Layer 0: Explicit destination phrase beats origin / general text ──
    for pat in _DEST_PATTERNS:
        m0 = pat.search(text)
        if m0:
            cand = m0.group(1).strip()
            words = cand.split()
            while words and words[0].lower() in _LOC_STOPWORDS:
                words.pop(0)
            if words and not any(w.lower() in _LOC_STOPWORDS for w in words) and len(" ".join(words)) >= 3:
                return _title_case_location(" ".join(words))

    # ── Layer 1: Gazetteer lookup with origin vs destination resolution ──
    matches = []
    for m in _CITY_REGEX.finditer(text):
        matched = m.group(1)
        low = matched.lower()
        if low in _LOC_STOPWORDS:
            continue
        s, e = m.span()
        before = text[max(0, s - 35) : s].lower()
        after = text[e : min(len(text), e + 25)].lower()

        is_origin = bool(
            re.search(r"\b(?:from|dispatch\s+from|pickup\s+from|pickup|supplier\s+in)\s*$", before)
            or re.search(r"\bfrom\s+(?:factory|plant|warehouse|mill|godown|unit|site)\s+in\s*$", before)
            or re.search(r"^\s*se\b", after)
        )
        is_dest = bool(
            not is_origin and (
                re.search(r"\b(?:to|deliver(?:y)?|dispatch|send|at|in|for)\s*[:\-=]?\s*$", before)
                or re.search(r"^\s*(?:deliver|delivery|ko)\b", after)
            )
        )

        # Precision guard: ambiguous common words must have capitalisation or prepositional context
        if low in _AMBIGUOUS_CITY_WORDS:
            if not (matched[0].isupper() or is_dest or is_origin):
                continue
            if low == "mandi" and re.search(r"\b(?:grain|sabzi|anaj|krishi|vegetable|cotton|timber|fruit)\s*$", before):
                continue

        matches.append({
            "matched": matched,
            "start": s,
            "end": e,
            "is_origin": is_origin,
            "is_dest": is_dest,
            "is_state": low in _STATES,
        })

    if matches:
        # If there are explicit destination matches, pick the first destination match
        dest_matches = [m for m in matches if m["is_dest"] and not m["is_origin"]]
        if dest_matches:
            non_state = [m for m in dest_matches if not m["is_state"]]
            return _title_case_location((non_state or dest_matches)[0]["matched"])

        # Non-origin matches (drop origin if another match exists)
        non_origin = [m for m in matches if not m["is_origin"]]
        if non_origin:
            non_state = [m for m in non_origin if not m["is_state"]]
            if non_state:
                return _title_case_location(non_state[0]["matched"])
            # If only a state matched, check if it was preceded by an unlisted town: e.g. "Nirmal Telangana"
            s0 = non_origin[0]["start"]
            before_state = text[max(0, s0 - 25) : s0].strip()
            m_town = re.search(r"([A-Z][a-zA-Z]{2,})$", before_state)
            if m_town and m_town.group(1).lower() not in _LOC_STOPWORDS:
                return _title_case_location(m_town.group(1))
            return _title_case_location(non_origin[0]["matched"])

        return _title_case_location(matches[0]["matched"])

    # ── Layer 2: Contextual preposition patterns ──
    # "to Mumbai", "in Jaipur", "at Surat", "delivery Pune", "for Nagpur"
    prep_pat = re.compile(
        r"\b(?:to|in|at|near|for|deliver(?:y)?)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b"
    )
    for m in prep_pat.finditer(text):
        candidate = m.group(1)
        if candidate.lower() not in _LOC_STOPWORDS and len(candidate) >= 3:
            return _title_case_location(candidate)

    # Hinglish: "Nagpur me", "Delhi mein", "Surat ke liye"
    hindi_pat = re.compile(
        r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:me|mein|ke\s+liye)\b"
    )
    for m in hindi_pat.finditer(text):
        candidate = m.group(1)
        if candidate.lower() not in _LOC_STOPWORDS and len(candidate) >= 3:
            return _title_case_location(candidate)

    # "<City> delivery" pattern
    delivery_pat = re.compile(
        r"\b([A-Z][a-zA-Z]+)\s+deliver(?:y)?\b"
    )
    for m in delivery_pat.finditer(text):
        candidate = m.group(1)
        if candidate.lower() not in _LOC_STOPWORDS and len(candidate) >= 3:
            return _title_case_location(candidate)

    # ── Layer 3: Terminal pattern (unseen city at end of RFQ message) ──
    # Strip any trailing sign-off clauses first (e.g. ". Thanks", "\nRegards Rajesh Kumar")
    clean_text = _SIGNOFF_TRAILING_RE.sub("", text.strip())
    term_m = re.search(r"(?:^|[\s,])([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*[.!?]*$", clean_text)
    if term_m:
        candidate = term_m.group(1).strip()
        words = candidate.split()
        skip_set = _LOC_STOPWORDS | _PCS_TOKENS | _KG_TOKENS | _MT_TOKENS | {"gsm", "mic", "micron", "ply", "rs", "inr"}
        while words and words[0].lower() in skip_set:
            words.pop(0)  # "GSM SAYAN" -> "SAYAN"
        # Check stopwords per word, not per phrase
        if words and not any(w.lower() in _LOC_STOPWORDS for w in words):
            candidate = " ".join(words)
            c_low = candidate.lower()
            if (
                len(candidate) >= 3
                and c_low not in skip_set
                and c_low not in VALID_CATEGORIES
            ):
                return _title_case_location(candidate)

    # ── Layer 4: message *starts* with an unlisted capitalised word ("Kovvur pouch 60 micron 75000", "Hapur: jumbo bag ...")
    first = re.match(
        r"^([A-Z][a-zA-Z]{2,})\s*[:,\-]?\s+(?:(?:[a-zA-Z]+)\s+)?(?:\d|bopp|woven|pouch|jumbo|fibc|stretch|shrink|film|box|carton|mono|corrugated|cement|bag|sack|packaging)",
        text,
    )
    if first:
        cand = first.group(1).strip()
        c_low = cand.lower()
        if c_low not in _LOC_STOPWORDS and c_low not in _PCS_TOKENS and c_low not in _KG_TOKENS:
            return _title_case_location(cand)

    return None


def _title_case_location(s: str) -> str:
    """Title-case a location string, preserving multi-word capitalisation."""
    return " ".join(w.capitalize() for w in s.split())


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

_NEG_RE = re.compile(
    r'(?:\b[a-z0-9_/-]+(?:\s+[a-z0-9_/-]+){0,2}\s+(?:nahi|nahin|nhi)\s+(?:chahiye|chahie|chaiye|lagega|hoga)\b'
    r'|\b(?:dont|don\'t|do\s+not)\s+(?:need|want|require|looking\s+for)?\s*(?:any\s+)?(?:[a-z0-9_/-]+(?:\s+[a-z0-9_/-]+){0,2}\s+(?:bags?|sacks?|pouch(?:es)?|films?|box(?:es)?|cartons?|fibc|wrap))\b'
    r'|\bno\s+(?!of\b|less\b|more\b)(?:[a-z0-9_/-]+(?:\s+[a-z0-9_/-]+){0,2}\s+(?:bags?|sacks?|pouch(?:es)?|films?|box(?:es)?|cartons?|fibc|wrap))\b'
    r'|\bnot\s+(?!less\b|more\b|only\b)(?:need\s+|want\s+)?(?:[a-z0-9_/-]+(?:\s+[a-z0-9_/-]+){0,2}\s+(?:bags?|sacks?|pouch(?:es)?|films?|box(?:es)?|cartons?|fibc|wrap))\b)',
    re.I,
)


def _drop_negated_products(text: str) -> str:
    """Drop negated product clauses like 'bopp bag nahi chahiye', 'dont need jumbo bag'."""
    cleaned = _NEG_RE.sub(" ", text)
    if re.search(r"\d|\b(?:bag|sack|box|film|pouch|carton|fibc|wrap|corrugated|woven|bopp)\b", cleaned, re.I):
        return cleaned
    return text


def parse_rfq(text: str, debug: bool = False) -> dict:
    """Parse a raw Indian B2B packaging RFQ message into 6 structured fields.

    Parameters:
        text: Raw RFQ message string.
        debug: If True, re-raises any unhandled internal exceptions for debugging
               instead of swallowing them with the safe default.
    """
    # Safe default — returned on any unhandled error
    default = {
        "category": "corrugated_box",
        "quantity": None,
        "unit": None,
        "gsm": None,
        "micron": None,
        "location": None,
    }
    try:
        if not isinstance(text, str) or not text.strip():
            return default

        # Defensive guard: cap input length to prevent ReDoS / memory DOS on huge payloads
        text = text[:10000]

        # Stage 1: Normalise
        norm = normalize_text(text)
        if not norm:
            return default
        norm = _drop_negated_products(norm)

        # Multi-product check: isolate first product segment if multi-product
        first_seg, is_multi = _split_first_product_segment(norm)
        target_text = first_seg if is_multi else norm

        # Stage 2-3: Extract GSM and micron (+ mask from target text)
        gsm, target_text = extract_gsm(target_text)
        micron, target_text = extract_micron(target_text)

        # Stage 4: Mask interfering patterns
        cleaned = mask_interfering_patterns(target_text)

        # Stage 5: Classify category
        category = classify_category(cleaned, gsm=gsm)

        # Stage 6: Extract quantity and unit
        quantity, unit = extract_quantity_and_unit(cleaned, category)

        # Option A: missing quantity ⇒ missing unit
        if quantity is None:
            unit = MISSING_QUANTITY_UNIT

        # Stage 7: Extract location (from first segment if present, else shared full text)
        location = extract_location(first_seg) if is_multi else None
        if not location:
            location = extract_location(norm)

        # ── Validate and return ──
        if category not in VALID_CATEGORIES:
            category = "corrugated_box"
        if unit not in (None, "pcs", "kg", "mt"):
            unit = "kg" if category == "film" else "pcs"
        if gsm is not None:
            gsm = int(gsm)
        if micron is not None:
            micron = int(micron)

        return {
            "category": category,
            "quantity": quantity,
            "unit": unit,
            "gsm": gsm,
            "micron": micron,
            "location": location,
        }

    except Exception as exc:
        if debug:
            raise exc
        return default
