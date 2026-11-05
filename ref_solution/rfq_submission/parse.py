"""RFQ parser for Kypson: turns a messy Hinglish buyer message into six fields.

Approach: plain rules, no models, standard library only.
  1. normalise text (Devanagari digits/words, spaces)
  2. pull out gsm and micron first so their numbers are not mistaken for quantity
  3. collect every number as a quantity *candidate*, reject the ones that are really
     fill weight, capacity, sizes, price, phone, pincode, ply, colours, dates...
  4. pick the best remaining candidate; convert lakh/hazaar/k/crore
  5. category from a prioritised keyword lexicon with typo tolerance
  6. location from a city/state/country list, then pattern fallbacks for unseen places
"""
import difflib
import re

CATEGORIES = ("bopp_bag", "woven_sack", "corrugated_box", "pouch", "film", "mono_carton", "fibc")

# ----------------------------------------------------------------------------- normalise
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEV_WORDS = {  # a few Devanagari words -> Roman equivalents
    "हज़ार": " hazaar ", "हजार": " hazaar ", "लाख": " lakh ", "करोड़": " crore ", "करोड": " crore ",
    "बैग": " bag ", "बोप्प": " bopp ", "बॉप": " bopp ", "बोपप": " bopp ", "जंबो": " jumbo ",
    "पाउच": " pouch ", "फिल्म": " film ", "बॉक्स": " box ", "कार्टन": " carton ", "बोरी": " sack ",
    "नागपुर": " Nagpur ", "मुंबई": " Mumbai ", "दिल्ली": " Delhi ", "पुणे": " Pune ", "जयपुर": " Jaipur ",
    "अहमदाबाद": " Ahmedabad ", "सूरत": " Surat ", "लखनऊ": " Lucknow ", "कानपुर": " Kanpur ",
    "इंदौर": " Indore ", "भोपाल": " Bhopal ", "वडोदरा": " Vadodara ", "हैदराबाद": " Hyderabad ",
    "चेन्नई": " Chennai ", "कोलकाता": " Kolkata ", "पटना": " Patna ", "रायपुर": " Raipur ",
}

_WORDNUM = {"ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
            "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "chhah": 6, "six": 6, "saat": 7, "seven": 7,
            "aath": 8, "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10, "barah": 12, "pandrah": 15,
            "bees": 20, "twenty": 20, "pachis": 25, "tees": 30, "chalis": 40, "pachas": 50, "fifty": 50,
            "dedh": 1.5, "derh": 1.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5, "sava": 1.25, "sawa": 1.25}
_MULT_WORDS = r"lakhs?|lacs?|lac|hazaa?r|hajaa?r|hazar|thousand|crores?|sau|hundred"
_MULT = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "hazaar": 1e3, "hazar": 1e3, "hajar": 1e3,
         "hajaar": 1e3, "thousand": 1e3, "crore": 1e7, "crores": 1e7, "cr": 1e7, "sau": 100, "hundred": 100, "k": 1e3}


def _normalize(text):
    t = str(text).translate(_DEV_DIGITS).replace("×", "x").replace("​", "")
    for k, v in _DEV_WORDS.items():
        t = t.replace(k, v)
    return t


def _words_to_digits(low):
    """'do hazaar' -> '2 hazaar', 'dedh lakh' -> '1.5 lakh' (only before a multiplier word)."""
    pat = r"\b(" + "|".join(_WORDNUM) + r")\s+(" + _MULT_WORDS + r")\b"
    return re.sub(pat, lambda m: f"{_WORDNUM[m.group(1)]} {m.group(2)}", low)


# ----------------------------------------------------------------------------- gsm / micron
_GSM_AFTER = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*-?\s*(?:gsm|gms|gsn|g\.s\.m|g/m2|g/m²|gm/m2|gram/m)\b")
_GSM_BEFORE = re.compile(r"\bgsm\s*[:=\-]?\s*(\d{1,3}(?:\.\d+)?)(?![\d,]|\s*(?:pcs|nos|kg|mt|bags?|lakh|lac|k\b|hazaar))")
_MIC_AFTER = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*-?\s*(?:mic(?:ron)?s?|micr[oa]ns?|micorns?|mics|my|μm?|µm?|um)\b")
_MIC_BEFORE = re.compile(r"\bmic(?:ron)?s?\s*[:=\-]?\s*(\d{1,3}(?:\.\d+)?)(?![\d,]|\s*(?:pcs|nos|kg|mt|bags?|lakh|lac|k\b|hazaar|tons?|tonnes?))")


def _find_attr(low, after, before):
    """Return (value, [spans]) for gsm/micron; first match wins."""
    val, spans = None, []
    for rx in (after, before):  # "65 gsm" form first, then "gsm 65"; the second never reuses text of the first
        for m in rx.finditer(low):
            if any(s < m.end() and m.start() < e for s, e in spans):
                continue
            spans.append(m.span())
            if val is None:
                val = int(round(float(m.group(1))))
    return val, spans


# ----------------------------------------------------------------------------- quantity
_NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_CAND = re.compile(r"(?<![A-Za-z0-9.])(?P<num>" + _NUM + r")(?:\s*(?P<mult>" + _MULT_WORDS + r"|cr)(?![a-z])|\s?(?P<k>k)(?![a-z]))?")
_UNIT = re.compile(r"\s*-?\s*(?P<u>pcs?|pieces?|nos\.?|numbers?|units?|bags?|boxes|box|sacks?|pouch(?:es)?|cartons?|rolls?|"
                   r"kgs?|kilograms?|kilos?|kg|mts?|tons?|tonnes?|metric\s+tons?|mtons?|tn)(?![a-z])")
_COUNT_U = ("pc", "pi", "no", "nu", "un", "ba", "bo", "sa", "po", "ca", "ro")


def _unit_class(u):
    u = u.lower()
    if u.startswith(("kg", "kilo")):
        return "kg"
    if u.startswith(("mt", "ton", "metric", "mton", "tn")):
        return "mt"
    return "pcs"


_PRICE_BEFORE = re.compile(r"(?:rs\.?|inr|₹|rate|price|budget|cost|amount|@|rupees?)\s*[:=\-]?\s*$")
_PRICE_AFTER = re.compile(r"^\s*(?:/-|rs\b|rupees?|inr|₹|/\s*(?:kg|pc|pcs|piece|bag|mt|ton|unit)|per\s+(?:kg|pc|pcs|piece|bag|mt|ton|unit)|budget)")
_OTHER_AFTER = re.compile(r"^\s*(?:days?|din|dino|weeks?|hafte|months?|mahine|years?|hrs?|hours?|%|percent|sides?|layers?|"
                          r"colou?rs?|colours?|ply|ply\b|inch|inches|in\b|\"|'|cm|mm|ft|feet|foot|mtrs?|meters?|metres?|sq|"
                          r"ml|ltrs?|litres?|liters?|l\b|gm|gms|gram|grams|g\b|oz|truck|container|trailer|lorry|"
                          r"st\b|nd\b|rd\b|th\b|am\b|pm\b|x\s*\d|\*\s*\d|/\s*\d|-\s*\d)")
_MONTH = re.compile(r"^\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)")
_FILL_BEFORE = re.compile(r"(?:bags?|sacks?|pouch\w*|packing|pack|packets?|each|per|size|weight|wt|capacity|cap|swl|load|of)\s*(?:of|:|=|-)?\s*$")
_CAP_AFTER = re.compile(r"^\s*(?:capacity|cap\b|swl|load|lifting|holding|holds|handl|safe)")
_FILL_AFTER_HI = re.compile(r"^\s*(?:ke|ka|ki|wale|wala|wali|vale|vala)\b")
_BAGISH_AFTER = re.compile(r"^\s*(?:per\s+)?(?:bags?|sacks?|pouch\w*|packs?|packing|packets?|bori|cement|ad\s*star|bopp|woven|pp\b|jumbo|fibc|big|bulk|laminated|hdpe|size)")
_PER_UNIT_X = re.compile(r"^\s*[x*]\s*\d")


def _quantity_candidates(low, blocked):
    out = []
    for m in _CAND.finditer(low):
        s, e = m.span()
        if any(bs < e and s < be for bs, be in blocked):
            continue
        raw = m.group("num")
        digits = raw.replace(",", "")
        val = float(digits)
        mult = m.group("mult") or m.group("k")
        if mult:
            val *= _MULT.get(mult.lower().rstrip("."), 1)
        um = _UNIT.match(low, e)
        unit, uend = (None, e)
        if um:
            unit, uend = _unit_class(um.group("u")), um.end()
        out.append(dict(val=val, start=s, end=e, uend=uend, unit=unit, mult=bool(mult), raw=raw,
                        digits=digits, before=low[max(0, s - 28):s], after=low[uend:uend + 30],
                        after_num=low[e:e + 30], explicit_count=bool(um and unit == "pcs")))
    return out


def _reject(c, category):
    """Return a reason string if this number is NOT the ordered quantity, else None."""
    b, a, an, dg = c["before"], c["after"], c["after_num"], c["digits"]
    if len(dg) >= 10 or re.search(r"\+\s*91\s*$", b) or re.search(r"\b(?:ph|phone|mob|mobile|call|whatsapp|wa|contact|cell)\b\s*(?:no\.?|number)?\s*[:\-]?\s*$", b):
        return "phone"
    if len(dg) == 6 and not c["mult"] and not c["unit"] and not dg.endswith("000") and "," not in c["raw"]:
        return "pincode"
    if re.search(r"(?:pin|pincode|pin\s*code|zip)\s*[:\-]?\s*$", b):
        return "pincode"
    if _PRICE_BEFORE.search(b) or _PRICE_AFTER.match(c["after_num"]) or (c["unit"] is None and _PRICE_AFTER.match(c["after"])):
        return "price"
    if re.search(r"\d\s*[x*]\s*$", b) and not c["unit"]:
        return "dimension"
    if c["unit"] is None and _OTHER_AFTER.match(an):
        return "other"
    if c["unit"] == "pcs" and re.match(r"\s*(?:bags?|boxes|box|cartons?|sacks?|pouch\w*)", an) is None and _OTHER_AFTER.match(an) and not c["explicit_count"]:
        return "other"
    if _MONTH.match(an):
        return "date"
    if re.search(r"\d\s*[/\-]\s*$", b) or re.match(r"\s*[/]\s*\d", an):
        return "date_or_range"
    if c["unit"] in ("kg", "mt"):
        if _CAP_AFTER.match(a) or re.search(r"(?:capacity|cap|swl|load|lifting|holding)\s*(?:of)?\s*[:=\-]?\s*$", b):
            return "capacity"
        if _PER_UNIT_X.match(a) or re.search(r"[x*]\s*$", b):
            return "per_unit_weight"
        if _FILL_AFTER_HI.match(a):
            return "fill_weight"
        # a fill weight is a few kg per bag; tonnes only count as per-bag weight for jumbo bags
        small = c["val"] <= 100 and c["unit"] == "kg"
        if _BAGISH_AFTER.match(a) and (category == "fibc" or small):
            return "fill_weight"
        if _FILL_BEFORE.search(b) and (category == "fibc" or small):
            return "fill_weight"
    if c["unit"] is None and _PER_UNIT_X.match(an):
        return "dimension"
    return None


def _pick_quantity(low, category, blocked):
    cands = [c for c in _quantity_candidates(low, blocked) if _reject(c, category) is None]
    if not cands:
        return None, None
    count = [c for c in cands if c["unit"] == "pcs"]
    weight = [c for c in cands if c["unit"] in ("kg", "mt")]
    mult = [c for c in cands if c["unit"] is None and c["mult"]]
    bare = [c for c in cands if c["unit"] is None and not c["mult"]]
    order = (weight, count, mult, bare) if category == "film" else (count, mult, weight, bare)
    for group in order:
        if group:
            c = group[0]
            unit = c["unit"] or ("kg" if category == "film" else "pcs")
            val = c["val"]
            if abs(val - round(val)) < 1e-9:
                val = int(round(val))
            else:
                val = round(val, 6)
            return val, unit
    return None, None


# ----------------------------------------------------------------------------- category
_KW_FIBC = ("jumbo", "jambo", "jumbu", "fibc", "bulk bag", "big bag", "bulkbag", "super sack", "supersack", "ton bag", "tonne bag")
_KW_MONO = ("mono carton", "monocarton", "mono-carton", "mono cartoon", "folding carton", "cosmetic carton", "pharma carton",
            "duplex box", "duplex carton", "mono box", "medicine box", "mono cartn", "mono kartan")
_KW_POUCH = ("pouch", "pouche", "pauch", "standup", "stand up", "stand-up", "zipper", "zip lock", "ziplock", "spout", "doypack", "sachet")
_KW_FILM = ("film", "shrink", "stretch", "cling", "wrap", "lldpe", "rolls", "roll")
_KW_BOPP = ("bopp", "bop ", "boop", "b.o.p.p", "laminated", "lamination")
_KW_WOVEN = ("woven", "pp bag", "hdpe", "cement", "ad star", "adstar", "a.d. star", "sack", "raffia", "bori", "pp sack", "star bag", "ad-star")
_KW_BOX = ("corrugated", "box", "boxes", "carton", "cartoon", "cartons", "ply box", "master carton", "kartan")
_BAGWORDS = ("bag", "sack", "woven", "bori")
_VOCAB = ["jumbo", "fibc", "pouch", "shrink", "stretch", "film", "bopp", "woven", "cement", "sack", "corrugated", "carton", "box", "boxes", "laminated", "zipper"]


def _fix_typos(low):
    """Map near-miss tokens (jambo, shrnk, micorn...) to canonical vocabulary using difflib."""
    toks = re.findall(r"[a-z]+", low)
    fixed = []
    for tk in toks:
        if len(tk) >= 5 and tk not in _VOCAB:
            mm = difflib.get_close_matches(tk, _VOCAB, n=1, cutoff=0.82)
            fixed.append(mm[0] if mm else tk)
        else:
            fixed.append(tk)
    return " ".join(fixed)


def _classify(low):
    text = " " + low + " "
    text2 = " " + _fix_typos(low) + " "
    def has(kws, t=None):
        t = t or text
        return any(k in t or k in text2 for k in kws)

    if has(_KW_FIBC):
        return "fibc"
    if has(_KW_MONO) or re.search(r"\bmono\b", text):
        return "mono_carton"
    if has(_KW_POUCH):
        return "pouch"
    bag = has(_BAGWORDS)
    if has(("corrugated", "master carton", "ply box")):
        return "corrugated_box"
    if has(_KW_FILM) and not bag:
        return "film"
    if has(_KW_BOPP) or re.search(r"\bbop\b", text):
        return "bopp_bag"
    if has(_KW_WOVEN):
        return "woven_sack"
    if has(_KW_BOX):
        return "corrugated_box"
    if has(_KW_FILM):
        return "film"
    return "woven_sack"  # last resort: a bare "bags" request is most often woven


# ----------------------------------------------------------------------------- location
_INDIA_CITIES = """
mumbai,delhi,new delhi,bangalore,bengaluru,hyderabad,ahmedabad,chennai,kolkata,pune,surat,jaipur,lucknow,kanpur,nagpur,
indore,thane,bhopal,visakhapatnam,vizag,pimpri-chinchwad,pimpri,patna,vadodara,baroda,ghaziabad,ludhiana,agra,nashik,
faridabad,meerut,rajkot,kalyan,vasai,varanasi,banaras,srinagar,aurangabad,dhanbad,amritsar,navi mumbai,allahabad,
prayagraj,ranchi,howrah,coimbatore,jabalpur,gwalior,vijayawada,jodhpur,madurai,raipur,kota,guwahati,chandigarh,solapur,
hubli,hubballi,dharwad,mysore,mysuru,tiruchirappalli,trichy,bareilly,aligarh,tiruppur,tirupur,moradabad,jalandhar,bhubaneswar,
salem,warangal,guntur,bhiwandi,saharanpur,gorakhpur,bikaner,amravati,noida,greater noida,jamshedpur,bhilai,cuttack,
firozabad,kochi,cochin,ernakulam,bhavnagar,dehradun,durgapur,asansol,nanded,kolhapur,ajmer,gulbarga,jamnagar,ujjain,
loni,siliguri,jhansi,ulhasnagar,nellore,jammu,sangli,belgaum,belagavi,mangalore,mangaluru,ambattur,tirunelveli,malegaon,
gaya,jalgaon,udaipur,maheshtala,davanagere,kozhikode,calicut,akola,kurnool,rajahmundry,bokaro,bellary,patiala,agartala,
bhagalpur,muzaffarnagar,bhatpara,panihati,latur,dhule,rohtak,korba,bhilwara,brahmapur,muzaffarpur,ahmednagar,mathura,
kollam,avadi,kadapa,anantapur,kamarhati,bilaspur,sambalpur,shahjahanpur,satara,bijapur,rampur,shimoga,chandrapur,junagadh,
thrissur,alwar,bardhaman,kulti,nizamabad,parbhani,tumkur,khammam,uzhavoor,bihar sharif,panipat,darbhanga,bally,aizawl,
dewas,ichalkaranji,karnal,bathinda,jalna,eluru,barasat,kirari suleman nagar,purnia,satna,mau,sonipat,sonepat,farrukhabad,
sagar,rourkela,durg,imphal,ratlam,hapur,arrah,anantapuram,karimnagar,etawah,ambarnath,north dumdum,bharatpur,begusarai,
new delhi,gandhidham,baranagar,tiruvottiyur,puducherry,pondicherry,sikar,thoothukudi,tuticorin,rewa,mirzapur,raichur,
pali,ramagundam,haridwar,vijayanagaram,tenali,nagercoil,sri ganganagar,karawal nagar,mango,thanjavur,bulandshahr,uluberia,
katni,sambhal,singrauli,nadiad,secunderabad,naihati,yamunanagar,bidhannagar,pallavaram,bidar,munger,panchkula,burhanpur,
raurkela,kharagpur,dindigul,gandhinagar,hospet,nangloi jat,malda,ongole,deoghar,chapra,haldia,khandwa,nandyal,morena,
amroha,anand,bhind,bhalswa jahangir pur,madhyamgram,bhiwani,berhampore,ambala,morbi,fatehpur,raebareli,khora,chittoor,
bhusawal,orai,bahraich,phusro,vellore,mehsana,raiganj,sirsa,danapur,serampore,sultan pur majra,guna,jaunpur,panvel,
shivpuri,surendranagar,unnao,hugli,alappuzha,kottayam,machilipatnam,shimla,adoni,udupi,tenali,proddatur,saharsa,hindupur,
sasaram,hajipur,bhimavaram,kumbakonam,dibrugarh,rae bareli,bhuj,kandla,mundra,navsari,valsad,vapi,silvassa,daman,
ankleshwar,bharuch,palanpur,porbandar,amreli,himmatnagar,godhra,surendranagar,veraval,botad,gondal,jetpur,okha,
tirupati,rajamahendravaram,kakinada,srikakulam,visakhapatnam,palakkad,kannur,kasaragod,malappuram,ooty,erode,karur,namakkal,
hosur,krishnagiri,dharmapuri,cuddalore,villupuram,kanchipuram,tiruvallur,chengalpattu,sivakasi,virudhunagar,theni,
bhadrak,balasore,baleshwar,puri,berhampur,jharsuguda,angul,dhenkanal,keonjhar,
jabalpur,chhindwara,balaghat,seoni,shahdol,sehore,vidisha,rajgarh,mandsaur,neemuch,khargone,barwani,dhar,pithampur,
nagda,betul,hoshangabad,itarsi,damoh,chhatarpur,tikamgarh,datia,
hisar,fatehabad,jind,kaithal,kurukshetra,rewari,gurgaon,gurugram,manesar,bahadurgarh,jhajjar,palwal,
sonipat,panipat,ambala,yamunanagar,mohali,zirakpur,baddi,solan,nalagarh,paonta sahib,parwanoo,
roorkee,rudrapur,haldwani,kashipur,kotdwara,rishikesh,jammu,kathua,udhampur,leh,
bhilwara,chittorgarh,pali,beawar,tonk,sawai madhopur,dausa,jhunjhunu,churu,hanumangarh,barmer,jaisalmer,sirohi,
mandi gobindgarh,khanna,moga,firozpur,abohar,hoshiarpur,pathankot,gurdaspur,
gorakhpur,basti,azamgarh,ballia,deoria,ghazipur,mau,bhadohi,sultanpur,faizabad,ayodhya,barabanki,sitapur,hardoi,
lakhimpur,pilibhit,budaun,badaun,etah,mainpuri,kannauj,banda,lalitpur,hathras,kasganj,shamli,baghpat,
nashik,nagpur,jalgaon,satara,sangli,solapur,latur,beed,osmanabad,parbhani,hingoli,yavatmal,wardha,gondia,bhandara,
ratnagiri,sindhudurg,raigad,palghar,bhiwandi,dombivli,mira road,badlapur,ulhasnagar,
chikmagalur,hassan,mandya,bagalkot,gadag,haveri,koppal,raichur,ballari,chitradurga,kolar,
secunderabad,karimnagar,adilabad,mahbubnagar,nalgonda,siddipet,
guwahati,silchar,jorhat,tezpur,nagaon,shillong,gangtok,itanagar,kohima,dimapur,
dhanbad,hazaribagh,giridih,ramgarh,phusro,jamtara,
raipur,bilaspur,korba,bhilai,durg,rajnandgaon,jagdalpur,ambikapur,
goa,panaji,margao,mapusa,vasco,
port blair,india"""
_STATES = """maharashtra,gujarat,rajasthan,punjab,haryana,uttar pradesh,up,madhya pradesh,mp,bihar,jharkhand,odisha,orissa,
west bengal,karnataka,kerala,tamil nadu,tamilnadu,telangana,andhra pradesh,andhra,assam,chhattisgarh,uttarakhand,
himachal pradesh,himachal,jammu and kashmir,goa,delhi ncr,ncr,sikkim,tripura,meghalaya,manipur,mizoram,nagaland"""
_COUNTRIES = """usa,us,america,united states,uk,united kingdom,england,uae,dubai,abu dhabi,sharjah,saudi arabia,saudi,ksa,riyadh,
jeddah,oman,muscat,qatar,doha,kuwait,bahrain,nepal,kathmandu,bangladesh,dhaka,sri lanka,colombo,pakistan,karachi,
afghanistan,bhutan,maldives,singapore,malaysia,indonesia,thailand,vietnam,china,japan,korea,germany,france,italy,spain,
netherlands,belgium,poland,turkey,egypt,kenya,nairobi,nigeria,lagos,ghana,tanzania,uganda,ethiopia,south africa,
mauritius,canada,australia,new zealand,brazil,mexico,russia,iran,iraq,israel,jordan,yemen,sudan,angola,zambia"""

_ALL_SINGLE = set()
_ALL_MULTI = set()
_COUNTRY_SET = set()
_STATE_SET = set()
for _src, _bucket in ((_INDIA_CITIES, None), (_STATES, _STATE_SET), (_COUNTRIES, _COUNTRY_SET)):
    for _n in re.split(r"[,\n]", _src):
        _n = _n.strip()
        if not _n:
            continue
        (_ALL_MULTI if " " in _n else _ALL_SINGLE).add(_n)
        if _bucket is not None:
            _bucket.add(_n)
_PLACE_AMBIG = {"us", "up", "mp", "mau", "india", "ncr", "mango", "khora", "hugli", "guna", "pali", "bally", "orai", "sagar", "tonk", "loni"}
_UPPER_WORDS = {"uae", "usa", "uk", "ksa", "us", "up", "mp", "ncr"}

_STOP = set("""a an the and or of to at in for from on with by is are was be been it this that these those i we you he she they
need needed want wanted require required requirement requirements looking quote quotation price prices rate rates urgent urgently
pls plz please thanks thank regards sir madam hi hello dear hey sirji bhai bhaiya kindly asap immediately today tomorrow
hai hain chahiye chahie chaiye chahiya bhejo bhej do dena dijiye batao batana bataiye kitna kitne lagega mujhe hume humein mere
mera meri apka aapka ke ka ki ko se me mein mai tak wala wale wali ek liye liya karna karo kar sakte hoga hogi
bag bags sack sacks box boxes carton cartons pouch pouches film films roll rolls wrap shrink stretch jumbo fibc bopp bop woven pp
hdpe ldpe lldpe cement ad star adstar laminated lamination mono corrugated cartoon bulk big pcs pc piece pieces nos no number
numbers unit units kg kgs kilo mt mts ton tons tonne tonnes metric gsm gms mic micron microns my ply layer print printed printing
inch inches cm mm ft size sizes colour color delivery deliver delivered shipping ship send dispatch location city place town
capacity swl load qty quantity order orders of contact call phone mobile whatsapp email mail regards supplier manufacturer
sample samples bulk good quality best cheap low cost budget lakh lakhs lac lacs hazaar hazar hajar crore thousand k
approx approximately around about minimum min max maximum total each per single double side sides plain white black blue red
green yellow transparent clear natural bopp pack packing packaging packet packets standup stand up zipper zip lock spout
doypack sachet new old available stock ready fast monthly weekly daily regular repeat sheet sheets tape bori laminate
available rs inr rupees rupee only also and then so but if when how what which who why where all any some more less
very much many few can could would should will shall may might must do does did done have has had not yes ok okay""".split())


def _title(name):
    return " ".join(w.upper() if w.lower() in _UPPER_WORDS else w.capitalize() for w in name.split())


def _is_stop(word):
    w = word.lower().strip(".,-")
    if w in _STOP:
        return True
    if len(w) >= 5:
        for k in ("bopp", "woven", "carton", "pouch", "jumbo", "shrink", "stretch", "corrugated", "chahiye", "quotation", "required"):
            if difflib.SequenceMatcher(None, w, k).ratio() >= 0.85:
                return True
    return False


_TOKEN = re.compile(r"[A-Za-z][A-Za-z'.\-]*|\d+")


def _gazetteer_matches(text):
    """All (name_as_written, canonical, start, kind) matches, longest n-gram first."""
    toks = [(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(text)]
    used, found = set(), []
    for n in (3, 2, 1):
        for i in range(len(toks) - n + 1):
            if any(j in used for j in range(i, i + n)):
                continue
            window = toks[i:i + n]
            if any(w[0].isdigit() for w in window):
                continue
            # words must be separated only by spaces/hyphens, not commas
            if any(re.search(r"[,;]", text[window[k][2]:window[k + 1][1]]) for k in range(n - 1)):
                continue
            key = " ".join(w[0].lower().strip(".'") for w in window)
            ok = key in (_ALL_MULTI if n > 1 else _ALL_SINGLE)
            if ok and n == 1:
                w0 = window[0][0]
                if key in _PLACE_AMBIG and not (w0[0].isupper() and (len(w0) > 3 or w0.isupper())):
                    ok = False
                if _is_stop(key) and key not in _COUNTRY_SET and key not in _ALL_SINGLE:
                    ok = False
            if ok:
                for j in range(i, i + n):
                    used.add(j)
                kind = "country" if key in _COUNTRY_SET else ("state" if key in _STATE_SET and key not in _ALL_SINGLE - _STATE_SET else "city")
                if key in ("goa", "delhi") or key.startswith("new delhi"):
                    kind = "city"
                found.append((_title(key), window[0][1], kind, key))
    found.sort(key=lambda x: x[1])
    return found


_STRONG = r"(?:deliver(?:y|ed)?|ship(?:ping|ped)?|send|dispatch|courier|location|loc|city|dest(?:ination)?|place|town|supply)"
_TRIG_STRONG = re.compile(r"\b" + _STRONG + r"\s*(?:to|at|in|for)?\s*[:\-]?\s*(?:to|at|in)?\s*([A-Za-z][A-Za-z.\-]+(?:\s[A-Z][a-z]+)?)")
_TRIG_WEAK = re.compile(r"\b(?:to|at|in|for)\s+([A-Za-z][A-Za-z.\-]+(?:\s[A-Z][a-z]+)?)")
_TRIG_POST = re.compile(r"\b([A-Za-z][A-Za-z.\-]+)\s+(?:me|mein|mai|tak|ko|delivery|wale|ke liye)\b")


def _clean_place(words):
    ws = [w for w in words.split() if w]
    out = []
    for w in ws[:2]:
        if _is_stop(w) or len(w.strip(".-")) < 3:
            break
        out.append(w.strip(".-"))
    return " ".join(out) if out else None


def _fallback_location(text, low_all):
    """For places that are not in the list: look at trigger words and sentence position."""
    for m in _TRIG_STRONG.finditer(text):
        p = _clean_place(m.group(1))
        if p:
            return _title(p)
    for m in _TRIG_WEAK.finditer(text):
        first = m.group(1).split()[0]
        if first[0].isupper() or (low_all and m.group(0).lower().startswith(("to ", "at "))):
            p = _clean_place(m.group(1))
            if p and not re.fullmatch(r"\d+", p):
                return _title(p)
    for m in _TRIG_POST.finditer(text):
        w = m.group(1)
        if not _is_stop(w) and len(w) >= 4 and (w[0].isupper() or low_all):
            return _title(w)
    # a capitalised place right before a pincode, e.g. "Nagpur 440022" or "Nagpur, 440022"
    m = re.search(r"\b([A-Z][a-zA-Z]{3,}(?:\s[A-Z][a-zA-Z]{3,})?)\s*,?\s*[1-9]\d{5}\b", text)
    if m and not any(_is_stop(w) for w in m.group(1).split()):
        return _title(m.group(1))
    # last comma-separated segment, e.g. "..., Muzaffarpur"
    segs = [s.strip(" .!?\n") for s in re.split(r"[,;\n]", text) if s.strip(" .!?\n")]
    if len(segs) > 1:
        last = segs[-1]
        ws = last.split()
        if 1 <= len(ws) <= 3 and all(re.fullmatch(r"[A-Za-z][A-Za-z.\-]+", w) for w in ws) and not any(_is_stop(w) for w in ws):
            return _title(last)
    # final capitalised word of the message (mixed-case text only)
    toks = re.findall(r"[A-Za-z][A-Za-z.\-]+|\d+", text)
    if toks:
        w = toks[-1]
        if w[0].isupper() and not _is_stop(w) and len(w) >= 4 and not low_all and not w.isupper():
            run = [w]  # extend backwards over a run of capitalised words: "Port Blair", "Sri Ganganagar"
            for prev in reversed(toks[:-1]):
                if len(run) < 2 and prev[0].isupper() and not _is_stop(prev) and len(prev) >= 3 and not prev.isdigit():
                    run.insert(0, prev)
                else:
                    break
            return _title(" ".join(run))
        if (low_all or w.isupper()) and len(toks) >= 2 and not _is_stop(w) and len(w) >= 4:
            before = text[:text.rfind(w)].rstrip()
            if re.search(r"(?:\d|,|pcs|nos|kg|mt|ton|tons|tonne|bags?|boxes|rolls|mic|micron|gsm)$", before.lower()):
                return _title(w)
    return None


def _fuzzy_city(text):
    best = None
    for m in _TOKEN.finditer(text):
        w = m.group(0)
        # strict on purpose: a real small town (Bhiwadi) must not be "corrected" into a bigger one (Bhiwandi)
        if len(w) >= 8 and w[0].isupper() and not _is_stop(w) and w.lower() not in _ALL_SINGLE:
            mm = difflib.get_close_matches(w.lower(), list(_ALL_SINGLE), n=1, cutoff=0.95)
            if mm:
                best = _title(mm[0])
                break
    return best


def _extract_location(text):
    low_all = text == text.lower() or text == text.upper()
    found = _gazetteer_matches(text)
    if found:
        if len(found) == 1:
            return found[0][0]
        before = lambda f: re.search(r"\bfrom\s*$", text[max(0, f[1] - 8):f[1]].lower())
        trig = lambda f: re.search(r"(?:deliver\w*|ship\w*|send|dispatch|to|at|location|city|destination)\s*[:\-]?\s*$", text[max(0, f[1] - 22):f[1]].lower())
        pool = [f for f in found if not before(f)] or found
        t = [f for f in pool if trig(f)]
        if t:
            return t[0][0]
        cities = [f for f in pool if f[2] == "city"]
        return (cities or pool)[0][0]
    fz = _fuzzy_city(text)
    if fz:
        return fz
    return _fallback_location(text, low_all)


# ----------------------------------------------------------------------------- public API
def parse_rfq(text: str) -> dict:
    result = {"category": "woven_sack", "quantity": None, "unit": None, "gsm": None, "micron": None, "location": None}
    try:
        t = _normalize("" if text is None else text)
        low = _words_to_digits(t.lower())
        gsm, gspans = _find_attr(low, _GSM_AFTER, _GSM_BEFORE)
        mic, mspans = _find_attr(low, _MIC_AFTER, _MIC_BEFORE)
        category = _classify(low)
        qty, unit = _pick_quantity(low, category, gspans + mspans)
        result.update(category=category, quantity=qty, unit=unit, gsm=gsm, micron=mic)
        try:
            result["location"] = _extract_location(t)
        except Exception:
            result["location"] = None
    except Exception:
        pass
    return result
