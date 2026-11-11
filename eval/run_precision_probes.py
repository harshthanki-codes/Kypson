"""Run precision probes on 30 non-RFQ / odd messages."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from parse import parse_rfq

probes = [
    "",
    "Hello sir",
    "Please send quote",
    "Thanks",
    "9876543210",
    "no of bags",
    "not less than 5000 bags",
    "MOQ 500 pcs hai lekin humko 10000 pcs chahiye",
    "order id 4521",
    "Quote no 1023 woven sack 20000 pcs",
    "Good morning team",
    "Kindly revert with best rates",
    "Regards Rajesh Sharma",
    "Call me on +91-98250-12345",
    "delivery urgent",
    "payment terms 30 days",
    "GSTIN 24AAACH7409R1ZZ",
    "size 12x18 inch 3 ply",
    "rate 45 rs per kg",
    "what is your minimum order quantity?",
    "MOQ 1000 pcs",
    "sample bhej do",
    "looking for catalogue and price list",
    "interested in your packaging products",
    "previous order was good",
    "last time 500 pcs",
    "urgent dispatch required tomorrow",
    "how much discount on bulk order?",
    "contact whatsapp 98765 43210",
    "Please note our new address",
]

for idx, p in enumerate(probes, 1):
    res = parse_rfq(p)
    loc = str(res["location"])
    qty = str(res["quantity"])
    unit = str(res["unit"])
    cat = str(res["category"])
    print(f"{idx:2d}. loc={loc:<12} qty={qty:<10} unit={unit:<8} cat={cat:<16} text={p!r}")
