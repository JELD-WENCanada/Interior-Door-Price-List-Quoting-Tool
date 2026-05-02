"""
run.py – Master pipeline entry point

Runs the full extraction → parse → Excel build pipeline, then
optionally launches the interactive quoting CLI.

Usage:
    python run.py              # Full pipeline + quoting tool
    python run.py --extract    # Extraction + Excel only (no quoting UI)
    python run.py --quote      # Quoting UI only (re-uses existing data)
"""

import argparse
import json
import os
import sys

# ── path setup ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATA_FILE = os.path.join(OUTPUT_DIR, "pricing_data.json")
EXCEL_FILE = os.path.join(OUTPUT_DIR, "JELDWEN_Master_Pricing.xlsx")

sys.path.insert(0, SRC_DIR)

from extract import extract_all_pdfs, summarise_extraction
from parser import parse_all
from builder import build_excel


def run_extraction_pipeline() -> None:
    """Extract → Parse → Save JSON → Build Excel."""
    print("\n" + "=" * 60)
    print("  JELD-WEN Master Quoting Tool – Extraction Pipeline")
    print("=" * 60)

    # ── Step 1: Extract ──────────────────────────────────────────────────────
    print("\n[Step 1] Extracting text from PDFs …")
    all_pdfs = extract_all_pdfs(PDF_DIR)
    if not all_pdfs:
        print("  ERROR: No PDFs extracted. Check the pdfs/ directory.")
        sys.exit(1)
    summarise_extraction(all_pdfs)

    # ── Step 2: Parse ────────────────────────────────────────────────────────
    print("\n[Step 2] Parsing pricing data …")
    data = parse_all(all_pdfs)

    # ── Step 3: Save JSON ────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    print(f"\n[Step 3] Saved pricing data → {DATA_FILE}")
    print(f"          Records : {len(data['records'])}")
    print(f"          Add-ons : {len(data['addons'])}")

    # ── Step 4: Build Excel ──────────────────────────────────────────────────
    print("\n[Step 4] Building Excel workbook …")
    build_excel(data, EXCEL_FILE)

    print("\n" + "=" * 60)
    print("  Extraction complete!")
    print(f"  JSON  → {DATA_FILE}")
    print(f"  Excel → {EXCEL_FILE}")
    print("=" * 60 + "\n")


def run_quoting_ui() -> None:
    """Launch the interactive quoting CLI."""
    from app import main as app_main
    app_main()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JELD-WEN Master Quoting Tool"
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Run extraction pipeline only (no quoting UI)",
    )
    parser.add_argument(
        "--quote",
        action="store_true",
        help="Launch quoting UI only (requires existing pricing_data.json)",
    )
    args = parser.parse_args()

    if args.quote:
        run_quoting_ui()
    elif args.extract:
        run_extraction_pipeline()
    else:
        # Default: run everything
        run_extraction_pipeline()
        run_quoting_ui()


if __name__ == "__main__":
    main()
