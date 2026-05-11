"""
PDF Extraction Module
Reads all PDF files from /pdfs directory using pdfplumber.
Returns raw page text for downstream parsing.
"""

import os
import pdfplumber
from typing import List, Dict, Any


def _lines_from_words(page) -> List[str]:
    """
    Build text lines by grouping pdfplumber words by their vertical position.

    pdfplumber's ``extract_text()`` orders text by reading flow, which can
    re-order multi-column pages so that sizes appear in one block and their
    matching prices in another. Grouping words by ``top`` (rounded to the
    nearest pixel, with a small tolerance) and sorting each row left-to-right
    keeps every (size, price) pair on the same line.
    """
    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    except Exception:
        words = []
    if not words:
        text = page.extract_text() or ""
        return [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Group by y-row (within 3pt tolerance)
    rows: List[List[Dict[str, Any]]] = []
    for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
        placed = False
        for row in rows:
            if abs(row[0]["top"] - w["top"]) <= 3:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])

    lines: List[str] = []
    for row in rows:
        row.sort(key=lambda x: x["x0"])
        line = " ".join(w["text"] for w in row).strip()
        if line:
            lines.append(line)
    return lines


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

    # Recursively collect PDFs from pdf_dir and subfolders.
    # Skip macOS resource-fork files (start with "._").
    # Skip the PQ_West folder (group has been removed from the tool).
    pdf_paths = []
    for root, dirs, files in os.walk(pdf_dir):
        dirs[:] = [d for d in dirs if d.lower() != "pq_west"]
        for f in files:
            if f.startswith("._"):
                continue
            if f.lower().endswith(".pdf"):
                pdf_paths.append(os.path.join(root, f))
    pdf_paths.sort()

    if not pdf_paths:
        print(f"  WARNING: No PDFs found in {pdf_dir}")
        return results

    for filepath in pdf_paths:
        filename = os.path.basename(filepath)
        pdf_data: Dict[str, Any] = {
            "filename": filename,
            "filepath": filepath,
            "pages": [],
        }

        # HomeHardware PDFs have a multi-column page layout that confuses
        # pdfplumber's default extract_text() (sizes and prices end up on
        # different lines). Use word-bbox-based reconstruction instead so
        # each (size, price) pair stays on the same row.
        fn_lower = filename.lower()
        use_word_rows = (
            "_hh_" in fn_lower
            or "home_hardware" in fn_lower
            or "homehardware" in fn_lower
        )

        try:
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    if use_word_rows:
                        lines = _lines_from_words(page)
                        raw_text = "\n".join(lines)
                    else:
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
