"""
PDF Extraction Module
Reads all PDF files from /pdfs directory using pdfplumber.
Returns raw page text for downstream parsing.
"""

import os
import pdfplumber
from typing import List, Dict, Any


def extract_all_pdfs(pdf_dir: str) -> List[Dict[str, Any]]:
    """
    Extract text from all PDF files in the given directory.

    Args:
        pdf_dir: Path to folder containing PDFs.

    Returns:
        List of dicts, one per PDF:
          {
            'filename': str,
            'filepath': str,
            'pages': [
              {'page_num': int, 'text': str, 'lines': List[str]}
            ]
          }
    """
    results = []

    if not os.path.isdir(pdf_dir):
        print(f"  ERROR: PDF directory not found: {pdf_dir}")
        return results

    pdf_files = sorted([f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")])

    if not pdf_files:
        print(f"  WARNING: No PDFs found in {pdf_dir}")
        return results

    for filename in pdf_files:
        filepath = os.path.join(pdf_dir, filename)
        pdf_data: Dict[str, Any] = {
            "filename": filename,
            "filepath": filepath,
            "pages": [],
        }

        try:
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    raw_text = page.extract_text() or ""
                    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
                    pdf_data["pages"].append(
                        {
                            "page_num": i + 1,
                            "text": raw_text,
                            "lines": lines,
                        }
                    )
            results.append(pdf_data)
            print(f"  [OK] {filename}  ({len(pdf_data['pages'])} pages)")
        except Exception as exc:
            print(f"  [ERROR] {filename}: {exc}")

    return results


def summarise_extraction(all_pdfs: List[Dict[str, Any]]) -> None:
    """Print a quick summary of what was extracted."""
    print(f"\n{'='*60}")
    print(f"  Extraction summary: {len(all_pdfs)} PDFs")
    print(f"{'='*60}")
    for p in all_pdfs:
        print(f"  {p['filename']}")
        print(f"    Pages: {len(p['pages'])}")
        for pg in p["pages"]:
            print(f"    P{pg['page_num']}: {len(pg['lines'])} lines")
    print()
