import json
from collections import Counter

with open('output/pricing_data.json') as f:
    data = json.load(f)

records = data['records']
addons = data['addons']

print('=== SPOT-CHECK: Price Verification ===')
checks = [
    ('Trimlite',  'Colonial Moulded', '12" to 18"', 'HC',              37.00),
    ('Trimlite',  'Conmore',          '30"',         'HC',              45.70),
    ('PQ East',   'Colonial Moulded', '12" to 18"', 'Full TL',         41.60),
    ('Group A',   'COLONIST TEXT',    '12"',         'HC',              64.45),
    ('Group K',   'COLONIST TEXT',    '12"',         'HC',              54.55),
    ('Group K',   'CONMORE',          '36"',         'HC',              68.95),
    ('Group B',   'CONMORE',          '24"',         'HC c/w Hardware', 83.20),
    ('Group K',   'CONMORE',          '24"',         'HC c/w Hardware', 74.05),
    ('Group A',   'CONMORE',          '18"',         'SC 1-3/4',       196.40),
]

idx = {}
for r in records:
    key = (r['dealer_group'], r['style'], r['size'], r['variant'])
    idx[key] = r

passed = 0
failed = 0
for dg, style, size, var, expected in checks:
    key = (dg, style, size, var)
    rec = idx.get(key)
    if rec:
        pn = rec.get('price_numeric')
        if pn == expected:
            status = 'PASS'
            passed += 1
        else:
            status = 'FAIL (got {})'.format(pn)
            failed += 1
    else:
        status = 'MISSING'
        failed += 1
    print('  [{}]  {} | {} | {} | {} -> expect ${}'.format(
        status, dg, style, size, var, expected))

print('\nResults: {} passed, {} failed'.format(passed, failed))

print('\n=== Records by dealer_group + product_type ===')
ct = Counter((r['dealer_group'], r['product_type']) for r in records)
for (dg, pt), n in sorted(ct.items()):
    print('  {:<14} {:<10} {:>4} records'.format(dg, pt, n))

print('\n=== Add-ons by dealer_group ===')
ct2 = Counter(a['dealer_group'] for a in addons)
for dg, n in sorted(ct2.items()):
    print('  {:<14} {:>4} add-ons'.format(dg, n))

print('\n=== Sample bifold records (Group A) ===')
bf = [r for r in records if r['dealer_group']=='Group A' and r['product_type']=='bifold'][:8]
for r in bf:
    print('  {} | {} | {} | {}'.format(r['style'], r['size'], r['variant'], r['price']))

print('\n=== Sample Group K addons ===')
kaddons = [a for a in addons if a['dealer_group']=='Group K'][:8]
for a in kaddons:
    print('  {} -> {}'.format(a['addon_name'], a['price']))
