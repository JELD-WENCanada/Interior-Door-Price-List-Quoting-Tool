# JELD-WEN Interior Door Master Quoting Tool

A complete, production-grade quoting application that reads all 5 JELD-WEN interior door pricing PDFs and produces a structured Excel workbook + interactive quoting CLI.

---

## Quick Start

```bash
# 1. From the quote-app directory:
cd quote-app

# 2. Install dependencies (first time only):
pip install -r requirements.txt

# 3. Run everything: extract PDFs → build Excel → launch quoting tool
python run.py

# OR: extract only (no quoting UI)
python run.py --extract

# OR: launch quoting UI only (uses existing pricing_data.json)
python run.py --quote
```

---

## Project Structure

```
quote-app/
├── pdfs/               → symlink to parent folder containing all 5 PDFs
├── output/
│   ├── pricing_data.json          ← extracted + normalized pricing data
│   └── JELDWEN_Master_Pricing.xlsx ← formatted Excel workbook
├── src/
│   ├── extract.py      → PDF text extraction (pdfplumber)
│   ├── parser.py       → text → structured JSON (dealer-specific parsers)
│   ├── builder.py      → JSON → formatted Excel workbook
│   ├── quote_engine.py → price lookup + quote calculation
│   └── app.py          → interactive CLI quoting interface
├── run.py              → master entry point
├── verify.py           → spot-check data quality
└── requirements.txt
```

---

## What Gets Extracted

| PDF | Dealer Group | Records |
|-----|-------------|---------|
| Trimlite | Trimlite | 108 price + 14 add-ons |
| PQ East / Specialty | PQ East | 232 price + 17 add-ons |
| Group K (K-Dealer) | Group K | 398 price + 39 add-ons |
| Group A (Castle) | Group A | 398 price + 39 add-ons |
| Group B (Grunthal) | Group B | 398 price + 39 add-ons |

**Total: 1,534 pricing records + 148 add-ons** across all PDFs.

---

## Excel Workbook Sheets

| Sheet | Contents |
|-------|---------|
| Summary | Record counts per sheet |
| Master Pricing | All 1,534 price records |
| Group A Slabs | Castle Dealers – door slabs |
| Group A Bifolds | Castle Dealers – bifold pricing |
| Group B Slabs | Grunthal Lumber – door slabs |
| Group B Bifolds | Grunthal Lumber – bifold pricing |
| Group K Slabs | K-Dealer – door slabs |
| Group K Bifolds | K-Dealer – bifold pricing |
| Trimlite Slabs | Trimlite – door slabs |
| PQ East Slabs | Specialty Building Products – door slabs |
| Add-ons - All Groups | All machining / jamb / hardware add-ons |
| Add-ons {Group} | Per-group add-on breakdown |

---

## Normalized Data Schema

### Price Record
```json
{
  "dealer_group": "Group A",
  "product_type": "door | bifold",
  "style": "COLONIST TEXT",
  "size": "12\"",
  "variant": "HC",
  "price": "$64.45",
  "price_numeric": 64.45,
  "options": [],
  "source_pdf": "Grp_A_2025_April_4_..."
}
```

### Add-on Record
```json
{
  "dealer_group": "Group A",
  "addon_name": "Machining for 1 3/8\": 3 Hinges and Lock",
  "price": "$9.55",
  "price_numeric": 9.55,
  "description": "",
  "applicable_to": ["door", "bifold"],
  "source_pdf": "..."
}
```

---

## Quoting Tool Usage

The interactive CLI guides you through:

1. **Dealer Group** – Group A, B, K, Trimlite, PQ East
2. **Product Type** – door or bifold
3. **Door Style** – COLONIST TEXT, CARRARA, CONMORE, etc.
4. **Size** – individual sizes or ranges as extracted from PDF
5. **Variant** – HC, SC 1-3/8, SC 1-3/4, Full TL, LTL, etc.
6. **Quantity**
7. **Add-ons** – any machining, jamb, or hardware options

The tool calculates a full itemised quote and can export it to Excel.

---

## Data Coverage

### Styles Covered

| Style | Groups |
|-------|--------|
| COLONIST TEXT / Camden | A, B, K |
| PRIMED HARDB | A, B, K |
| CARRARA / ROCKPORT / SANTA FE | A, B, K |
| CONMORE / MADISON / MONROE / BIRKDALE / CRAFTSMAN | A, B, K |
| Colonial Moulded / Conmore / Flat Moulded (Shaker) / Primed Hardboard | Trimlite, PQ East |

### Size Ranges

- **Central (A/B/K):** Individual sizes 12"–38", every size preserved
- **Trimlite:** Ranges (12"–18", 20"–24", 26" & 28", 30", 32", 34", 36", 38", 40"–48")
- **PQ East:** Same ranges as Trimlite, two pricing tiers (Full TL / LTL)

### Add-on Categories

- Machining (hinges, locks, fire ratings, mortice)
- Jamb options (MDF, FJP, rabbeted prehung – multiple depths)
- Hardware options (hinge finish, ball catch, flush bolt, BB hinges)
- Solid core upgrades (1 3/8 SC, 1 3/4 SC)
- Non-standard charge

---

## Rules

- ✅ All prices read directly from PDFs – no hardcoded values
- ✅ Every PDF row preserved – no data collapsed or assumed
- ✅ Missing data stored as "N/A" or "NOT FOUND IN PDF"
- ✅ Size ranges NOT collapsed (e.g. "12\" to 18\"" kept as-is for range PDFs)
- ✅ Each dealer group has independent pricing

---

## Dependencies

```
pdfplumber>=0.10.0   # PDF text extraction
pandas>=2.0.0        # DataFrame processing
openpyxl>=3.1.0      # Excel workbook generation
rich>=13.0.0         # Terminal UI
tabulate>=0.9.0      # Table formatting
```
