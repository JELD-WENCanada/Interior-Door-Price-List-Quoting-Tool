"""
Parser Module
Converts raw PDF text (from extract.py) into normalized pricing records.

Supports 5 PDF formats:
  1. Trimlite       – slab price ranges, adders
  2. PQ East        – two-tier (Full TL / LTL) slab ranges, adders
  3. Central Group A/B/K – individual slab sizes, bifolds (HC + SC), adders/jambs/options

Normalized schema per record:
  {
    "dealer_group": str,
    "product_type": "door" | "bifold" | "add_on",
    "style": str,
    "size": str,
    "variant": str,          # e.g. "HC", "SC 1-3/8", "SC 1-3/4", "Full TL", "LTL"
    "price": str,            # "$XX.XX", "N/A", "On Request", "NOT FOUND IN PDF"
    "price_numeric": float | None,
    "options": list,
    "source_pdf": str,
  }

Add-on schema:
  {
    "dealer_group": str,
    "addon_name": str,
    "price": str,
    "price_numeric": float | None,
    "description": str,
    "applicable_to": list,
    "source_pdf": str,
  }
"""

import re
from typing import List, Dict, Any, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────────────────────────────────────

_NA_VALS = {"n/a", "na", ""}

PRICE_RE = re.compile(
    r"\$[\d,]+\.?\d*|[\d,]+\.\d+\s*\$|On Request",
    re.IGNORECASE,
)

NA_RE = re.compile(r"\bN/?A\b", re.IGNORECASE)


def _parse_price_token(token: str) -> Tuple[str, Optional[float]]:
    """
    Return (display_str, numeric_or_None) for a single price token.
    Token might be  "$64.45",  "37.00 $",  "N/A",  "On Request".
    """
    t = token.strip()
    if t.upper() in ("N/A", "NA"):
        return "N/A", None
    if t.lower() == "on request":
        return "On Request", None
    m = re.search(r"([\d,]+\.?\d*)", t)
    if m:
        val_str = m.group(1).replace(",", "")
        try:
            return f"${float(val_str):.2f}", float(val_str)
        except ValueError:
            pass
    return "NOT FOUND IN PDF", None


def _extract_price_tokens(line: str) -> List[Tuple[str, Optional[float]]]:
    """
    Extract all price tokens from a line.
    Handles "$XX.XX", "XX.XX $", "N/A", "On Request" in sequence.
    """
    tokens: List[Tuple[str, Optional[float]]] = []
    # Replace "N/A" or "NA" placeholders before running the price regex
    # so we can pick them up in order.
    # We'll split the line into segments and classify each.
    # Strategy: find all money/NA/OnRequest tokens in left-to-right order.
    combined = re.compile(
        r"(\$[\d,]+\.?\d*)|([\d,]+\.?\d+\s*\$)|(N/?A\b)|(On Request)",
        re.IGNORECASE,
    )
    for m in combined.finditer(line):
        raw = m.group(0).strip()
        tokens.append(_parse_price_token(raw))
    return tokens


def _make_record(
    dealer_group: str,
    product_type: str,
    style: str,
    size: str,
    variant: str,
    price_display: str,
    price_numeric: Optional[float],
    source_pdf: str,
    options: Optional[List] = None,
) -> Dict[str, Any]:
    return {
        "dealer_group": dealer_group,
        "product_type": product_type,
        "style": style,
        "size": size,
        "variant": variant,
        "price": price_display,
        "price_numeric": price_numeric,
        "options": options or [],
        "source_pdf": source_pdf,
    }


def _make_addon(
    dealer_group: str,
    addon_name: str,
    price_display: str,
    price_numeric: Optional[float],
    description: str,
    applicable_to: List[str],
    source_pdf: str,
) -> Dict[str, Any]:
    return {
        "dealer_group": dealer_group,
        "addon_name": addon_name,
        "price": price_display,
        "price_numeric": price_numeric,
        "description": description,
        "applicable_to": applicable_to,
        "source_pdf": source_pdf,
    }


# ──────────────────────────────────────────────────────────────────────────────
# PDF type detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_pdf_type(filename: str) -> str:
    """
    Return one of: 'trimlite' | 'pq_east' | 'central_a' | 'central_b' | 'central_k'
    """
    fn = filename.lower()
    if "trimlite" in fn:
        return "trimlite"
    if "pq_east" in fn or "specialty" in fn:
        return "pq_east"
    if "grp_a" in fn or "_a_dealer" in fn:
        return "central_a"
    if "grp_b" in fn or "_aa_dealer" in fn or "grunthal" in fn:
        return "central_b"
    if "k_dealer" in fn or "_k_" in fn:
        return "central_k"
    return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# Shared size-range patterns (used by Trimlite + PQ East)
# ──────────────────────────────────────────────────────────────────────────────

_RANGE_SIZE_RE = re.compile(
    r'^(\d+["\']'
    r'(?:'
    r'(?:\s*(?:to|&)\s*\d+["\'])'   # "12\" to 18\"" or "12\" & 28\""
    r'|'
    r'(?:\s*,\s*\d+["\'])*'          # "40\", 42\", 44\""
    r')?'
    r'(?:\s+Euro)?'                   # optional "Euro" suffix  e.g. "38\" Euro"
    r')',
    re.IGNORECASE,
)
_HEIGHT_ADD_RE = re.compile(r'^Height\s+((?:\d+["\']\s*or\s*)?\d+["\'])', re.IGNORECASE)
_SC_ADD_RE = re.compile(r'^1\s*3/8\s+solid\s+core\s+(\d+[\'\"]{1,2})\s*add', re.IGNORECASE)
_HC_174_ADD_RE = re.compile(r'^1\s*3/4\s+hollow\s+core(?:\s+(\d+[\'\"]{1,2}))?\s+add', re.IGNORECASE)

# Section change markers
_BIFOLD_SECTION_RE = re.compile(r'^Bifold\s+\d+', re.IGNORECASE)
_FIRE_SECTION_RE   = re.compile(r'^1\s*3/4\s+20\s+min', re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────────────────
# Trimlite parser
# ──────────────────────────────────────────────────────────────────────────────

_TRIMLITE_STYLES = ["Colonial Moulded", "Conmore", "Flat Moulded (Shaker)", "Primed Hardboard"]


def _parse_range_based_page(
    lines: List[str],
    dealer: str,
    tier: str,
    source_pdf: str,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse a single pricing page that uses size-range rows (Trimlite / PQ East).
    Handles three sections:
      1. Standard HC slabs
      2. Bifold HC (starts after "Bifold XX in" line)
      3. 1-3/4 fire-rated slab (starts after "1 3/4 20 min" line)
    Returns (records, addons).
    """
    records: List[Dict] = []
    addons: List[Dict] = []
    styles = _TRIMLITE_STYLES

    # State: 'slab' | 'bifold' | 'fire'
    state = "slab"
    bifold_height_label = ""

    for line in lines:
        # ── Section transitions ───────────────────────────────────────────────
        if _BIFOLD_SECTION_RE.match(line):
            state = "bifold"
            # Capture the bifold height (e.g. "78 5/8" or "79")
            bh = re.search(r'Bifold\s+([\d/ ]+(?:in\.?)?)', line, re.IGNORECASE)
            bifold_height_label = bh.group(1).strip() if bh else ""
            continue

        if _FIRE_SECTION_RE.match(line):
            state = "fire"
            continue

        # ── Skip noise lines ──────────────────────────────────────────────────
        if re.match(
            r'^(shrink|Net Pricing|Trimlite|Specialty|5-May|May 5|FULL TRUCK|LESS THAN TRUCK|'
            r'1000 Door|NOTE:|Slab\s|Flat Mould|Colonial|Moulded\s|\(Shaker\)|'
            r'\d+\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))',
            line,
            re.IGNORECASE,
        ):
            continue

        # ── 1-3/4 hollow core adder row ───────────────────────────────────────
        hcm = _HC_174_ADD_RE.match(line)
        if hcm and state == "slab":
            ht = hcm.group(1)  # May be None if no height dimension on the line
            size_label = f"1 3/4 HC {ht} add" if ht else "1 3/4 HC add"
            prices = _extract_price_tokens(line[hcm.end():])
            for idx, style in enumerate(styles):
                pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                records.append(_make_record(dealer, "door", style, size_label, f"{tier}-HC-1-3/4-Add", pd, pn, source_pdf))
            continue

        # ── SC 1-3/8 adder row ────────────────────────────────────────────────
        scm = _SC_ADD_RE.match(line)
        if scm and state == "slab":
            ht = scm.group(1)
            prices = _extract_price_tokens(line[scm.end():])
            for idx, style in enumerate(styles):
                pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                records.append(_make_record(dealer, "door", style, f"1 3/8 SC {ht} add", f"{tier}-SC-1-3/8-Add", pd, pn, source_pdf))
            continue

        # ── Height adder row ──────────────────────────────────────────────────
        hm = _HEIGHT_ADD_RE.match(line)
        if hm:
            ht = hm.group(1)
            prices = _extract_price_tokens(line[hm.end():])
            if state == "slab":
                v = f"{tier}-HC-Height-Add"
                pt = "door"
            elif state == "bifold":
                v = f"{tier}-Bifold-Height-Add"
                pt = "bifold"
            else:
                v = f"{tier}-Fire-Height-Add"
                pt = "door"
            for idx, style in enumerate(styles):
                pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                records.append(_make_record(dealer, pt, style, f"Height {ht} add", v, pd, pn, source_pdf))
            continue

        # ── Single-value adder line (e.g. "For pivot or bypass door add $4.20") ──
        if re.match(r'^(For pivot|Less than|20 Min Lab|Off standard)', line, re.IGNORECASE):
            prices = _extract_price_tokens(line)
            if prices:
                first_m_list = list(re.finditer(
                    r'(\$[\d,]+\.?\d*)|(\d[\d,]*\.\d+\s*\$)|(N/?A\b)|(On Request)',
                    line, re.IGNORECASE
                ))
                if first_m_list:
                    first_m = first_m_list[0]   # Use FIRST price, not last
                    name = line[: first_m.start()].strip().rstrip(':').strip()
                    if name:
                        pd, pn = prices[0]       # First price is the actual adder cost
                        addons.append(_make_addon(dealer, name, pd, pn, tier, ["door", "bifold"], source_pdf))
            continue

        # ── Regular size row ──────────────────────────────────────────────────
        m = _RANGE_SIZE_RE.match(line)
        if m:
            size_str = m.group(1).strip()
            prices = _extract_price_tokens(line[m.end():])

            if state == "slab":
                variant = f"{tier}"
                pt = "door"
            elif state == "bifold":
                variant = f"{tier}-Bifold HC c/w Hardware"
                pt = "bifold"
            else:  # fire
                variant = f"{tier}-SC 1-3/4 20min Fire"
                pt = "door"

            for idx, style in enumerate(styles):
                pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                records.append(_make_record(dealer, pt, style, size_str, variant, pd, pn, source_pdf))
            continue

    return records, addons


def parse_trimlite(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    """Parse the Trimlite PDF (all pricing pages)."""
    records: List[Dict] = []
    addons: List[Dict] = []
    source = pdf_data["filename"]

    for pg in pdf_data["pages"]:
        pnum = pg["page_num"]
        lines = pg["lines"]

        if pnum == 1:
            recs, ads = _parse_range_based_page(lines, "Trimlite", "HC", source)
            records.extend(recs)
            addons.extend(ads)
        elif pnum == 2:
            addons.extend(_parse_adders_page(lines, "Trimlite", source))
        # Pages 3-5 are availability charts – no pricing data

    return {"records": records, "addons": addons}


def _parse_adders_page(lines: List[str], dealer: str, source_pdf: str) -> List[Dict]:
    """
    Parse a generic adders page.
    Each line is expected to be "Description ... $price" or "Description ... On Request".
    """
    # ── Pre-process: merge orphan price-only lines with the following description ──
    # PDFs sometimes put the price on one line and the description on the next
    # (e.g. PQ East "Wood rails" → "$14.00" on one line, description on next).
    processed: List[str] = []
    i = 0
    _PRICE_TOKEN_RE = re.compile(
        r'(\$[\d,]+\.?\d*)|([\d,]+\.?\d+\s*\$)|(N/?A\b)|(On Request)',
        re.IGNORECASE,
    )
    while i < len(lines):
        line = lines[i]
        prices_in = _extract_price_tokens(line)
        name_only = _PRICE_TOKEN_RE.sub('', line).strip()
        if prices_in and not name_only and i + 1 < len(lines):
            # This line is a bare price — look ahead for a description
            next_line = lines[i + 1]
            if not _extract_price_tokens(next_line):
                processed.append(next_line.strip() + ' ' + line.strip())
                i += 2
                continue
        processed.append(line)
        i += 1

    records: List[Dict] = []
    _SKIP_RE = re.compile(
        r'^(?:\*{2}|NET PRICE|Customer|Group|Castle|Grunthal|A-Dealer|AA-Dealer|'
        r'Jamb|Option|Non-Standard|Regional|Price|See|'
        r'\d+\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))',
        re.IGNORECASE,
    )
    for line in processed:
        if _SKIP_RE.match(line):
            continue
        prices = _extract_price_tokens(line)
        if not prices:
            continue
        last_price_match = list(re.finditer(
            r'(\$[\d,]+\.?\d*)|([\d,]+\.?\d+\s*\$)|(N/?A\b)|(On Request)',
            line, re.IGNORECASE,
        ))
        if not last_price_match:
            continue
        last_m = last_price_match[-1]
        name = line[: last_m.start()].strip().rstrip(':').strip()
        # Filter: empty names or footnote lines that start with a parenthesis
        if not name or name.startswith('('):
            continue
        pd, pn = prices[-1]
        records.append(
            _make_addon(dealer, name, pd, pn, "", ["door", "bifold"], source_pdf)
        )
    return records


# ──────────────────────────────────────────────────────────────────────────────
# PQ East parser  (two-tier pricing – reuses shared range-based parser)
# ──────────────────────────────────────────────────────────────────────────────

def parse_pq_east(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    """Parse the PQ East / Specialty Building Products PDF."""
    records: List[Dict] = []
    addons: List[Dict] = []
    source = pdf_data["filename"]

    for pg in pdf_data["pages"]:
        pnum = pg["page_num"]
        lines = pg["lines"]

        if pnum == 1:
            recs, ads = _parse_range_based_page(lines, "PQ East", "Full TL", source)
            records.extend(recs)
            addons.extend(ads)
        elif pnum == 2:
            recs, ads = _parse_range_based_page(lines, "PQ East", "LTL", source)
            records.extend(recs)
            addons.extend(ads)
        elif pnum == 3:
            addons.extend(_parse_adders_page(lines, "PQ East", source))
        # Pages 4-6 are availability charts

    return {"records": records, "addons": addons}


# ──────────────────────────────────────────────────────────────────────────────
# Central dealers parser  (Group A, B, K)
# ──────────────────────────────────────────────────────────────────────────────

# Slab header lines – detect "SLAB <STYLE1> <STYLE2> ..."
_CENTRAL_SLAB_HDR_RE = re.compile(r'^SLAB\s+(.+)$', re.IGNORECASE)
# Individual size row  e.g. "12" $64.45 $64.45 $53.60"
_CENTRAL_SIZE_RE = re.compile(r'^(\d+["\'])\s+')
# Height adder rows  e.g. "** HEIGHT 84" HC Add only $30.75 N/A $30.75"
_CENTRAL_HEIGHT_RE = re.compile(r'^\**\s*HEIGHT\s+(\d+["\'])', re.IGNORECASE)
# SC adder rows  e.g. "** 1 3/8 SC 80'' Add only $88.00 ..."
_CENTRAL_SC_RE = re.compile(r'^\**\s*1\s*3/8\s+SC\s+(\d+["\']|[\d]+[\'"]{1,2})\s+Add', re.IGNORECASE)
# Style-level EasyIN / Prehung adder on slab pages
_CENTRAL_EASY_IN_RE = re.compile(r'^Add for Easy-IN', re.IGNORECASE)
_CENTRAL_PREHUNG_RE = re.compile(r'^Add for Prehung', re.IGNORECASE)
# BIFOLDS section header
_BIFOLDS_HDR_RE = re.compile(r'^BIFOLDS?\s*$', re.IGNORECASE)
# SC 1-3/4 bifolds header  e.g. "1-3/4 SC CONMORE MADISON ..."
_SC_BIFOLD_HDR_RE = re.compile(r'^1[-–]3/4\s+SC\s+(.+)$', re.IGNORECASE)
# Column header immediately after BIFOLDS (same styles as current slab group)
_COL_HDR_RE = re.compile(r'^[A-Z][A-Z ]+(?:\s+[A-Z][A-Z]+)+\s*$')
# Range size row for SC bifolds  e.g. "20" to 24""
_RANGE_SIZE_START_RE = re.compile(r'^(\d+["\'](?:\s*(?:to|&)\s*\d+["\'])?)')

# Known style names for multi-word style splitting
_KNOWN_STYLES = {
    "COLONIST TEXT", "COLONIST TEX", "CAMDEN", "PRIMED HARDB", "PRIMED HARDBOARD",
    "CARRARA", "ROCKPORT", "SANTA FE",
    "CONMORE", "MADISON", "MONROE", "BIRKDALE", "CRAFTSMAN",
}

def _split_style_header(header_str: str) -> List[str]:
    """
    Split a style header string like "COLONIST TEXT CAMDEN PRIMED HARDB"
    into individual style names, trying longest-match against known styles.
    """
    # Try matching multi-word known styles first
    text = header_str.strip().upper()
    result = []
    # Try 3-word, then 2-word, then 1-word chunks
    tokens = text.split()
    i = 0
    while i < len(tokens):
        matched = False
        for length in (3, 2, 1):
            candidate = " ".join(tokens[i : i + length])
            if candidate in _KNOWN_STYLES:
                result.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            # Just take single token
            result.append(tokens[i])
            i += 1
    return result


def _parse_central_pages(
    pages: List[Dict],
    dealer_group: str,
    source_pdf: str,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse the pricing pages (P1-P4) of a Central dealer PDF.

    Returns (records, addons).
    """
    records: List[Dict] = []
    addons: List[Dict] = []

    # State machine variables
    current_styles: List[str] = []
    in_slab = False
    in_bifold_hc = False
    in_sc174 = False           # 1-3/4 SC door slab section (NOT a bifold section)
    bifold_styles: List[str] = []
    sc174_styles: List[str] = []

    for pg in pages:
        pnum = pg["page_num"]
        lines = pg["lines"]

        # Pages 5+ are availability charts – skip
        if pnum > 4:
            continue

        # Page 4 is adders page
        if pnum == 4:
            addons.extend(_parse_adders_page(lines, dealer_group, source_pdf))
            continue

        # Pages 1–3 are pricing pages
        for line in lines:
            # ── Skip header/footer lines ──────────────────────────────────────
            if re.match(
                r'^(NET PRICE|Customer|Group|Castle|Grunthal|A-Dealer|AA-Dealer|'
                r'Non standard|See other|Regional freight|Price subject|'
                r'\*{1,2}See avail|c/w Hard)',
                line,
                re.IGNORECASE,
            ):
                continue
            # Skip date-only lines
            if re.match(r'^\d+\s+(January|April|May|June)', line, re.IGNORECASE):
                continue

            # ── SLAB header ───────────────────────────────────────────────────
            shm = _CENTRAL_SLAB_HDR_RE.match(line)
            if shm:
                current_styles = _split_style_header(shm.group(1))
                in_slab = True
                in_bifold_hc = False
                in_sc174 = False
                continue

            # ── BIFOLDS section header ────────────────────────────────────────
            if _BIFOLDS_HDR_RE.match(line):
                in_slab = False
                in_bifold_hc = True
                in_sc174 = False
                bifold_styles = []   # will be set by next column header
                continue

            # ── 1-3/4 SC door slab section header e.g. "1-3/4 SC CONMORE MADISON ..." ───────────────────────────────────────
            scbm = _SC_BIFOLD_HDR_RE.match(line)
            if scbm:
                in_slab = False
                in_bifold_hc = False
                in_sc174 = True
                sc174_styles = _split_style_header(scbm.group(1))
                continue

            # ── Column header row (after BIFOLDS marker) ──────────────────────
            # e.g. "CONMORE MADISON MONROE BIRKDALE CRAFTSMAN"
            if in_bifold_hc and not bifold_styles:
                candidate_styles = _split_style_header(line)
                if len(candidate_styles) >= 2 and all(
                    s in _KNOWN_STYLES for s in candidate_styles
                ):
                    bifold_styles = candidate_styles
                    continue

            # ── Height adder row ──────────────────────────────────────────────
            chm = _CENTRAL_HEIGHT_RE.match(line)
            if chm:
                height_val = chm.group(1)
                # Determine variant label
                if "HC" in line.upper():
                    v_label = f"HC-Height-{height_val}-Add"
                elif in_sc174:
                    v_label = f"SC-1-3/4-Height-{height_val}-Add"
                else:
                    v_label = f"Height-{height_val}-Add"

                prices = _extract_price_tokens(line[chm.end():])
                active_styles = (
                    sc174_styles
                    if in_sc174
                    else (bifold_styles if in_bifold_hc else current_styles)
                )
                pt = "bifold" if in_bifold_hc else "door"
                for idx, style in enumerate(active_styles):
                    pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                    records.append(_make_record(dealer_group, pt, style, f"Height {height_val} add", v_label, pd, pn, source_pdf))
                continue

            # ── SC 1-3/8 adder row ────────────────────────────────────────────
            scam = _CENTRAL_SC_RE.match(line)
            if scam:
                sc_height = scam.group(1)
                size_str = f"1 3/8 SC {sc_height} add"
                prices = _extract_price_tokens(line[scam.end():])
                for idx, style in enumerate(current_styles):
                    pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                    records.append(_make_record(dealer_group, "door", style, size_str, "SC-1-3/8-Add", pd, pn, source_pdf))
                continue

            # ── HC 1-3/4 adder row (per-page, per-style) ─────────────────────
            # e.g. "** 1 3/4 HC 80" Add only $31.80 $31.80 $30.75"
            hc174m = re.match(r'^\**\s*1\s*3/4\s+HC\s+(\d+["\'])\s+Add', line, re.IGNORECASE)
            if hc174m and in_slab:
                ht = hc174m.group(1)
                prices = _extract_price_tokens(line[hc174m.end():])
                for idx, style in enumerate(current_styles):
                    pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                    records.append(_make_record(dealer_group, "door", style, f"1 3/4 HC {ht} add", "HC-1-3/4-Add", pd, pn, source_pdf))
                continue

            # ── Easy-IN per-style adder ───────────────────────────────────────
            if _CENTRAL_EASY_IN_RE.match(line):
                prices = _extract_price_tokens(line)
                for idx, style in enumerate(current_styles):
                    pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                    addons.append(_make_addon(
                        dealer_group,
                        "Add for Easy-IN 4-9/16 MDF to HC/SC",
                        pd, pn, f"Per style: {style}",
                        ["door"], source_pdf,
                    ))
                continue

            # ── Prehung per-style adder ───────────────────────────────────────
            if _CENTRAL_PREHUNG_RE.match(line):
                prices = _extract_price_tokens(line)
                for idx, style in enumerate(current_styles):
                    pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                    addons.append(_make_addon(
                        dealer_group,
                        "Add for Prehung 4-9/16 FJP to HC/SC",
                        pd, pn, f"Per style: {style}",
                        ["door"], source_pdf,
                    ))
                continue

            # ── Regular slab size row ─────────────────────────────────────────
            if in_slab:
                sm = _CENTRAL_SIZE_RE.match(line)
                if sm:
                    size_str = sm.group(1)
                    # Check for Euro suffix (e.g. "38" Euro")
                    euro_m = re.match(r'^(\d+["\']\s+Euro)', line, re.IGNORECASE)
                    if euro_m:
                        size_str = euro_m.group(1).strip()
                        prices = _extract_price_tokens(line[euro_m.end():])
                    else:
                        prices = _extract_price_tokens(line[sm.end():])
                    for idx, style in enumerate(current_styles):
                        pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                        records.append(_make_record(dealer_group, "door", style, size_str, "HC", pd, pn, source_pdf))
                    continue

            # ── HC Bifold size row ────────────────────────────────────────────
            if in_bifold_hc and bifold_styles:
                sm = _CENTRAL_SIZE_RE.match(line)
                if sm:
                    size_str = sm.group(1)
                    prices = _extract_price_tokens(line[sm.end():])
                    for idx, style in enumerate(bifold_styles):
                        pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                        records.append(_make_record(dealer_group, "bifold", style, size_str, "HC c/w Hardware", pd, pn, source_pdf))
                    continue

            # ── SC 1-3/4 door slab size row ───────────────────────────────────────────
            if in_sc174 and sc174_styles:
                sm = _RANGE_SIZE_START_RE.match(line)
                if sm:
                    size_str = sm.group(1).strip()
                    prices = _extract_price_tokens(line[sm.end():])
                    for idx, style in enumerate(sc174_styles):
                        pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                        records.append(_make_record(dealer_group, "door", style, size_str, "SC 1-3/4", pd, pn, source_pdf))
                    continue

    return records, addons


def parse_central(pdf_data: Dict[str, Any], group_name: str) -> Dict[str, List]:
    """Parse a Central dealer PDF (Group A, B, or K)."""
    records, addons = _parse_central_pages(
        pdf_data["pages"], group_name, pdf_data["filename"]
    )
    return {"records": records, "addons": addons}


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────

def parse_pdf(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    """
    Detect PDF type and route to the appropriate parser.
    Returns {'records': [...], 'addons': [...]}.
    """
    pdf_type = detect_pdf_type(pdf_data["filename"])

    if pdf_type == "trimlite":
        return parse_trimlite(pdf_data)
    elif pdf_type == "pq_east":
        return parse_pq_east(pdf_data)
    elif pdf_type == "central_a":
        return parse_central(pdf_data, "Group A")
    elif pdf_type == "central_b":
        return parse_central(pdf_data, "Group B")
    elif pdf_type == "central_k":
        return parse_central(pdf_data, "Group K")
    else:
        print(f"  WARNING: Unknown PDF type for '{pdf_data['filename']}' – skipping")
        return {"records": [], "addons": []}


def parse_all(all_pdfs: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    Parse all extracted PDFs.
    Returns {'records': [...], 'addons': [...]}.
    """
    all_records: List[Dict] = []
    all_addons: List[Dict] = []

    for pdf_data in all_pdfs:
        print(f"  Parsing: {pdf_data['filename']}")
        result = parse_pdf(pdf_data)
        all_records.extend(result["records"])
        all_addons.extend(result["addons"])
        print(f"    → {len(result['records'])} price records, {len(result['addons'])} add-ons")

    print(f"\n  Total: {len(all_records)} records, {len(all_addons)} add-ons")
    return {"records": all_records, "addons": all_addons}
