from parse import parse_rfq

tests = [
    # 1. Phonetic Hindi spelling 'pachees' (standard is pachis)
    ('pachees hazaar bopp bags chahiye 65 gsm Nagpur', {'q': 25000, 'loc': 'Nagpur'}),
    # 2. Hindi number 'chaalis'
    ('chaalis hazaar cement bags Jaipur', {'q': 40000, 'loc': 'Jaipur'}),
    # 3. 'sau' without prefix ('sau pcs' = 100)
    ('sau pcs jumbo bags Vadodara', {'q': 100, 'loc': 'Vadodara'}),
    # 4. 'dedh hazaar' (1.5 * 1000 = 1500)
    ('dedh hazaar bopp bag Surat', {'q': 1500, 'loc': 'Surat'}),
    # 5. Missing space before unit: '500kg'
    ('need quote for 500kg shrink wrap 25 mic', {'q': 500, 'u': 'kg'}),
    # 6. Missing space before unit: '500pcs'
    ('500pcs jumbo bags 1000 kg capacity Vadodara', {'q': 500, 'u': 'pcs'}),
    # 7. '10 quintal' (1 quintal = 100 kg -> 1000 kg or 1 mt)
    ('10 quintal pp woven sacks Indore', {'q': 1000, 'u': 'kg'}),
    # 8. 'k' with decimals: '2.5k'
    ('2.5k pcs bopp bags 65 gsm Nagpur', {'q': 2500, 'u': 'pcs'}),
    # 9. 'L' with decimal: '1.5L'
    ('1.5L bopp bags 65 gsm Nagpur', {'q': 150000, 'u': 'pcs'}),
    # 10. Multi-item: '1000 bags and 500 boxes'
    ('need 1000 bopp bags and 500 corrugated boxes Nagpur', {'q': 1000, 'c': 'bopp_bag'}),
    # 11. Rate with slash: 'rate 85/kg for 500 kg stretch film'
    ('rate 85/kg for 500 kg stretch film', {'q': 500, 'u': 'kg'}),
    # 12. City name in lowercase: 'nagpur'
    ('bopp bags 40 hazaar 65 gsm nagpur', {'loc': 'Nagpur'}),
    # 13. Origin vs Destination: 'Nagpur se Mumbai delivery'
    ('bopp bags 40000 pcs Nagpur se Mumbai delivery', {'loc': 'Mumbai'}),
    # 14. Unknown city with transit marker in lowercase: 'delivery to ankleshwar'
    ('bopp bags 40000 pcs delivery to ankleshwar', {'loc': 'Ankleshwar'}),
    # 15. Capacity with 'cap': 'jumbo bag 1 ton cap 500 pcs Vadodara'
    ('jumbo bag 1 ton cap 500 pcs Vadodara', {'q': 500, 'loc': 'Vadodara'}),
    # 16. Dimension with mm: '1200 mm stretch film 500 kg Surat'
    ('1200 mm stretch film 500 kg Surat', {'q': 500, 'loc': 'Surat'}),
    # 17. '500 rolls' of stretch film
    ('500 rolls stretch film 25 mic Ahmedabad', {'q': 500, 'u': 'pcs'}),
    # 18. Indian comma '20,00,000' (20 lakh)
    ('20,00,000 pcs cement bags Jaipur', {'q': 2000000, 'loc': 'Jaipur'}),
    # 19. Film in MT: 'need 5 MT stretch wrap film Morbi'
    ('need 5 MT stretch wrap film Morbi', {'q': 5, 'u': 'mt'}),
    # 20. GSM spaced: '65 g s m'
    ('bopp bag 65 g s m 40000 pcs Nagpur', {'gsm': 65}),
    # 21. Micron written as '25u'
    ('stretch film 25u 500 kg Surat', {'mic': 25}),
    # 22. '50 kg bags 1000 Morbi' (fill weight before quantity, no unit on quantity)
    ('50 kg bags 1000 Morbi', {'q': 1000, 'loc': 'Morbi'}),
    # 23. '1000 bags of 50 kg Morbi'
    ('1000 bags of 50 kg Morbi', {'q': 1000, 'loc': 'Morbi'}),
    # 24. '1 truck load' (non-standard logistics unit)
    ('1 truck load cement bags Jaipur', {'q': None}),
    # 25. '2 container' (non-standard logistics unit)
    ('2 container bopp bags Nagpur', {'q': None}),
    # 26. Price before quantity: 'rs 25 per bag, 5000 bags Jaipur'
    ('rs 25 per bag, 5000 bags Jaipur', {'q': 5000, 'loc': 'Jaipur'}),
    # 27. Date in text: 'need on 15-08-2024, 5000 bags Jaipur'
    ('need on 15-08-2024, 5000 bags Jaipur', {'q': 5000, 'loc': 'Jaipur'}),
    # 28. 'paanch hazar' vs '5 hazar'
    ('paanch hazar bopp bags Nagpur', {'q': 5000, 'loc': 'Nagpur'}),
    # 29. Corrugated box ply '9 ply'
    ('9 ply box 500 pcs Pune', {'q': 500, 'loc': 'Pune'}),
    # 30. Standalone 'cement bag' without pcs: 'cement bags 50000'
    ('cement bags 50000 Jaipur', {'q': 50000, 'loc': 'Jaipur'})
]

print("Index | Input | Output | Remarks")
print("-" * 80)
for i, (text, exp) in enumerate(tests, 1):
    res = parse_rfq(text)
    print(f"[{i:02d}] '{text[:35]}...'")
    print(f"     -> cat={res['category']} q={res['quantity']} u={res['unit']} gsm={res['gsm']} mic={res['micron']} loc={res['location']}")
