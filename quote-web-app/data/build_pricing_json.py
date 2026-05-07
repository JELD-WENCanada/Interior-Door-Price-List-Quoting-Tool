#!/usr/bin/env python3
"""
build_pricing_json.py
Transforms quote-app/output/pricing_data.json into a web-ready JS data file.

Outputs:
  data/pricing_data.js   – window.PRICING_DATA = {...};  (works from file://)
  data/pricing.json      – plain JSON (for reference / fetch-based servers)

Run from inside quote-web-app/:
    python3 data/build_pricing_json.py
"""

import json
import os
import re
from datetime import date
from collections import defaultdict

BASE  = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(BASE, '..', '..', 'quote-app', 'output', 'pricing_data.json')
OUT_JS   = os.path.join(BASE, 'pricing_data.js')
OUT_JSON = os.path.join(BASE, 'pricing.json')

# ─── Human-readable group labels ────────────────────────────────────────────
GROUP_LABELS = {
    "Group A":      "Group A – Castle Dealers",
    "Group B":      "Group B – Grunthal Lumber (AA-Dealer)",
    "Group D":      "Group D – Sexton",
    "Group F":      "Group F – ILDC West",
    "Group K":      "Group K – Volume Independent Dealers",
    "Trimlite":     "Trimlite",
    "PQ East":      "PQ East – Specialty Building Products",
    "PQ West":      "PQ West – Specialty Building Products (Alexandria Moulding)",
    "HomeHardware": "Home Hardware – Non-Committed",
}

# ─── Dealer rebate percentages (off subtotal before tax) ─────────────────────
# Maps group key → rebate as decimal (0.1275 = 12.75%).
GROUP_REBATES = {
    "Group A":      0.1275,   # Castle
    "Group D":      0.1075,   # Sexton
    "Group F":      0.18,     # ILDC
    "HomeHardware": 0.21,     # Home Hardware
    "PQ East":      0.05,     # Alexandria Moulding / PQ East
    "PQ West":      0.05,     # Alexandria Moulding / PQ West
}

# ─── Add-on category patterns (order matters – first match wins) ─────────────
ADDON_CATEGORIES = [
    ("Fire Rating",    re.compile(r'fire|20\s*min|45\s*min|60.*90\s*min', re.I)),
    ("Machining",      re.compile(r'machining|dead\s*bolt|viewer|mortice|flush bolt|pivot|slider|wood rail|closure|50k', re.I)),
    ("Jambs",          re.compile(r'jamb|easy.?in|prehung|mdf|fjp|primed|rabbeted', re.I)),
    ("Hardware",       re.compile(r'hinge|ball\s*catch|flush\s*bolt|bb\s*hinge', re.I)),
    ("Upgrades",       re.compile(r'solid\s*core|hollow\s*core|non.?formaldehyde|non.?standard', re.I)),
    ("Other",          re.compile(r'.*')),
]


def size_sort_key(s: str):
    """Sort sizes: individual numeric → ranges → adders."""
    s = s.strip()
    if re.search(r'\badd\b|height', s, re.I):
        first = re.match(r'(\d+)', s)
        return (2, int(first.group(1)) if first else 999, s)
    if re.search(r'\bto\b|&|,', s):
        first = re.match(r'(\d+)', s)
        return (1, int(first.group(1)) if first else 999, s)
    first = re.match(r'(\d+)', s)
    return (0, int(first.group(1)) if first else 999, s)


def get_addon_category(name: str) -> str:
    for cat_name, pattern in ADDON_CATEGORIES:
        if pattern.search(name):
            return cat_name
    return "Other"


def main():
    if not os.path.isfile(INPUT):
        print(f"ERROR: Source not found: {INPUT}")
        print("Run  python run.py --extract  from quote-app/ first.")
        return

    with open(INPUT, 'r') as f:
        raw = json.load(f)

    records    = raw.get('records', [])
    raw_addons = raw.get('addons', [])

    # ── Products ──────────────────────────────────────────────────────────────
    products = []
    for r in records:
        price = r.get('price_numeric')       # None = N/A
        disp  = r.get('price', 'N/A')
        prod = {
            'group':         r['dealer_group'],
            'type':          r['product_type'],   # 'door' | 'bifold'
            'style':         r['style'],
            'size':          r['size'],
            'variant':       r['variant'],
            'price':         price,
            'price_display': disp,
        }
        if r.get('qty_tiers'):
            prod['qty_tiers'] = r['qty_tiers']
        products.append(prod)

    # Sort for consistent JS output
    products.sort(key=lambda p: (
        p['group'], p['type'], p['style'],
        size_sort_key(p['size']), p['variant']
    ))

    # ── Add-ons (deduplicate by group + name + price) ─────────────────────────
    seen   = {}   # key → addon dict
    for a in raw_addons:
        pn = a.get('price_numeric')
        if pn is None:
            continue       # skip "On Request" and missing-price entries

        group = a['dealer_group']
        name  = a['addon_name']
        key   = (group, name, round(pn, 2))

        if key not in seen:
            applies_to = a.get('applicable_to', ['door', 'bifold'])
            if not isinstance(applies_to, list):
                applies_to = [applies_to]

            seen[key] = {
                'group':      group,
                'name':       name,
                'price':      pn,
                'category':   get_addon_category(name),
                'applies_to': applies_to,
            }

    addons = list(seen.values())
    addons.sort(key=lambda a: (a['group'], a['category'], a['price']))

    # ── Catalog: unique styles + sizes per group/type ─────────────────────────
    catalog = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for p in products:
        catalog[p['group']][p['type']][p['style']].add(p['size'])

    # Convert sets to sorted lists
    catalog_out = {}
    for grp, types in catalog.items():
        catalog_out[grp] = {}
        for typ, styles in types.items():
            catalog_out[grp][typ] = {
                sty: sorted(sizes, key=size_sort_key)
                for sty, sizes in sorted(styles.items())
            }

    # ── Final structure ───────────────────────────────────────────────────────
    data = {
        'meta': {
            'generated_at':   date.today().isoformat(),
            'record_count':   len(products),
            'addon_count':    len(addons),
        },
        'groups':  GROUP_LABELS,
        'rebates': GROUP_REBATES,
        'catalog': catalog_out,
        'products': products,
        'addons':   addons,
    }

    # Write JSON
    os.makedirs(BASE, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [OK] {OUT_JSON}  ({len(products)} products, {len(addons)} addons)")

    # Write JS – sets window.PRICING_DATA so it works via file://
    js = (
        f"// Auto-generated by build_pricing_json.py  [{date.today()}]\n"
        "window.PRICING_DATA = "
        + json.dumps(data, indent=2, ensure_ascii=False)
        + ";\n"
    )
    with open(OUT_JS, 'w', encoding='utf-8') as f:
        f.write(js)
    print(f"  [OK] {OUT_JS}")


if __name__ == '__main__':
    main()
