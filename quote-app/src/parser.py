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
    qty_tiers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # Normalise whitespace in the size string so identical sizes from
    # different sections of a PDF (e.g. '12" x 80"(1\'0" x 6\'8")' vs
    # '12" x 80" (1\'0" x 6\'8")') de-duplicate cleanly downstream.
    size_norm = re.sub(r"\s+", " ", size.strip())
    size_norm = re.sub(r"\s*\(\s*", " (", size_norm)
    size_norm = re.sub(r"\s*\)", ")", size_norm)
    rec = {
        "dealer_group": dealer_group,
        "product_type": product_type,
        "style": style,
        "size": size_norm,
        "variant": variant,
        "price": price_display,
        "price_numeric": price_numeric,
        "options": options or [],
        "source_pdf": source_pdf,
    }
    if qty_tiers:
        rec["qty_tiers"] = qty_tiers
    return rec


def _make_addon(
    dealer_group: str,
    addon_name: str,
    price_display: str,
    price_numeric: Optional[float],
    description: str,
    applicable_to: List[str],
    source_pdf: str,
    qty_tiers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    addon = {
        "dealer_group": dealer_group,
        "addon_name": addon_name,
        "price": price_display,
        "price_numeric": price_numeric,
        "description": description,
        "applicable_to": applicable_to,
        "source_pdf": source_pdf,
    }
    if qty_tiers:
        addon["qty_tiers"] = qty_tiers
    return addon


# ──────────────────────────────────────────────────────────────────────────────
# PDF type detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_pdf_type(filename: str) -> str:
    """
    Return one of:
        'trimlite' | 'pq_east'
      | 'central_a' | 'central_b' | 'central_d' | 'central_f' | 'central_k'
      | 'home_hardware'
      | 'unknown'
    """
    fn = filename.lower()
    if "trimlite" in fn:
        return "trimlite"
    if "pq_east" in fn:
        return "pq_east"
    if "_hh_" in fn or "home_hardware" in fn or "homehardware" in fn:
        return "home_hardware"
    if "ildc" in fn or "grpf" in fn or "grp_f" in fn:
        return "central_f"
    if "sexton" in fn or "grp_d" in fn:
        return "central_d"
    if "grp_a" in fn or "_a_dealer" in fn:
        return "central_a"
    if "grp_b" in fn or "_aa_dealer" in fn or "grunthal" in fn:
        return "central_b"
    if "k_dealer" in fn or "_k_" in fn:
        return "central_k"
    if "specialty" in fn:  # PQ East fallback (older filename without "pq_east")
        return "pq_east"
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
                base = "Slab 1 3/8 hollow core"
                pt = "door"
            elif state == "bifold":
                base = "Bifold 1 3/8 c/w hardware"
                pt = "bifold"
            else:  # fire
                base = "Slab 1 3/4 20-min fire-rated"
                pt = "door"
            variant = f"{base} ({tier})" if tier else base

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
            recs, ads = _parse_range_based_page(lines, "Trimlite", "", source)
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
        # Use FIRST price token as the boundary so the addon name doesn't
        # accidentally absorb earlier price columns (e.g. "Machining ...
        # $9.63 $9.15" → name "Machining ...", not "Machining ... $9.63").
        first_m = last_price_match[0]
        name = line[: first_m.start()].strip().rstrip(':').strip()
        # Filter: empty names or footnote lines that start with a parenthesis
        if not name or name.startswith('('):
            continue
        # Use the LAST price (typically the higher / current tier) as the
        # representative price.
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
    "COLONIST TEXT", "COLONIST TEX", "COLONIST TEXTURED",
    "CAMDEN", "PRIMED HARDB", "PRIMED HARDBOARD",
    "CARRARA", "EURO", "ROCKPORT", "SANTA FE",
    "PRINCETON", "CONTINENTAL", "CAMBRIDGE",
    "CONMORE", "MADISON", "MONROE", "BIRKDALE", "CRAFTSMAN",
}

# Map raw / truncated header forms to a single canonical Title-Case style name.
# Applied in _split_style_header / _looks_like_style_header so the rest of the
# pipeline sees one consistent name regardless of how the PDF rendered it.
_STYLE_ALIASES: Dict[str, str] = {
    "COLONIST TEXT":      "Colonist Textured",
    "COLONIST TEX":       "Colonist Textured",
    "COLONIST TEXTURED":  "Colonist Textured",
    "PRIMED HARDB":       "Primed Hardboard",
    "PRIMED HARDBOARD":   "Primed Hardboard",
    "SANTA FE":           "Santa Fe",
    "CAMDEN":             "Camden",
    "CARRARA":            "Carrara",
    "EURO":               "Euro",
    "ROCKPORT":           "Rockport",
    "PRINCETON":          "Princeton",
    "CONTINENTAL":        "Continental",
    "CAMBRIDGE":          "Cambridge",
    "CONMORE":            "Conmore",
    "MADISON":            "Madison",
    "MONROE":             "Monroe",
    "BIRKDALE":           "Birkdale",
    "CRAFTSMAN":          "Craftsman",
}


def _canonicalize_style(name: str) -> str:
    """Return canonical Title-Case style name (e.g. 'PRIMED HARDB' -> 'Primed Hardboard')."""
    key = name.strip().upper()
    return _STYLE_ALIASES.get(key, name.strip().title())

def _split_style_header(header_str: str) -> List[str]:
    """
    Split a style header string like "COLONIST TEXT CAMDEN PRIMED HARDB"
    into individual style names, trying longest-match against known styles.
    Returns canonical Title-Case names (e.g. "Primed Hardboard").
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
                result.append(_canonicalize_style(candidate))
                i += length
                matched = True
                break
        if not matched:
            # Just take single token as-is (canonicalised)
            result.append(_canonicalize_style(tokens[i]))
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
                        records.append(_make_record(dealer_group, "door", style, size_str, "Slab 1 3/8 hollow core", pd, pn, source_pdf))
                    continue

            # ── HC Bifold size row ────────────────────────────────────────────
            if in_bifold_hc and bifold_styles:
                sm = _CENTRAL_SIZE_RE.match(line)
                if sm:
                    size_str = sm.group(1)
                    prices = _extract_price_tokens(line[sm.end():])
                    for idx, style in enumerate(bifold_styles):
                        pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                        records.append(_make_record(dealer_group, "bifold", style, size_str, "Bifold 1 3/8 c/w hardware", pd, pn, source_pdf))
                    continue

            # ── SC 1-3/4 door slab size row ───────────────────────────────────────────
            if in_sc174 and sc174_styles:
                sm = _RANGE_SIZE_START_RE.match(line)
                if sm:
                    size_str = sm.group(1).strip()
                    prices = _extract_price_tokens(line[sm.end():])
                    for idx, style in enumerate(sc174_styles):
                        pd, pn = prices[idx] if idx < len(prices) else ("NOT FOUND IN PDF", None)
                        records.append(_make_record(dealer_group, "door", style, size_str, "Slab 1 3/4 solid core", pd, pn, source_pdf))
                    continue

    return records, addons


def parse_central(pdf_data: Dict[str, Any], group_name: str) -> Dict[str, List]:
    """Parse a Central dealer PDF (Group A, B, or K)."""
    records, addons = _parse_central_pages(
        pdf_data["pages"], group_name, pdf_data["filename"]
    )
    return {"records": records, "addons": addons}


# ──────────────────────────────────────────────────────────────────────────────
# HomeHardware / Sexton / ILDC parser  (single-price-per-row, optional qty tiers)
# ──────────────────────────────────────────────────────────────────────────────
#
# Layout (one per page):
#     [Style availability header listing 1..N styles]
#     Section title:  "Slab 1 3/8 hollow core", "Bifold 1 3/8 c/w hardware",
#                     "Slab 1 3/8 solid core (Procore)", "Slab 1 3/4 hollow core",
#                     "Slab 1 3/4 solid core",
#                     "1 3/8\" HC Easy-Install MDF 4 9/16 x 9/16 (KD Unit)",
#                     "1 3/8\" HC Prehung FJ Primed 4 5/8 x 11/16 (assembled unit)"
#     Size rows:  "12\" x 80\" (1'0\" x 6'8\")  $XX.XX [ $YY.YY ]"
#     Height adders:  "HEIGHT 84\" Add  $X.XX [ $Y.YY ]",  "HEIGHT 96\" Add ..."
#
# Each row carries up to N prices, where N is the number of quantity tiers:
#     HomeHardware: 1 tier  (no breaks)
#     Sexton      : 2 tiers (1–1099, 1100+)
#     ILDC        : 2 tiers (1–299, 300–1099)
#
# Prices apply to ALL styles listed in the page header (single-price model).

_HH_SECTIONS = [
    # (regex, variant_label, product_type)
    (re.compile(r"Slab\s+1\s*3/8\s+hollow\s+core",                  re.I), "Slab 1 3/8 hollow core",                                 "door"),
    (re.compile(r"Bifold\s+1\s*3/8\s+c/?w\s+hardware",              re.I), "Bifold 1 3/8 c/w hardware",                              "bifold"),
    (re.compile(r"Slab\s+1\s*3/8\s+solid\s+core\s*\(Procore\)",     re.I), "Slab 1 3/8 solid core (Procore)",                        "door"),
    (re.compile(r"Slab\s+1\s*3/4\s+hollow\s+core",                  re.I), "Slab 1 3/4 hollow core",                                 "door"),
    (re.compile(r"Slab\s+1\s*3/4\s+solid\s+core",                   re.I), "Slab 1 3/4 solid core",                                  "door"),
    (re.compile(r"1\s*3/8\"?\s*HC\s+Easy[-\s]?Install\s+MDF",       re.I), "1 3/8 HC Easy-Install MDF (KD Unit)",                    "door"),
    (re.compile(r"1\s*3/8\"?\s*HC\s+Easy[-\s]?Install\s+FJ\s+Pine", re.I), "1 3/8 HC Easy-Install FJ Pine (KD Unit)",                "door"),
    (re.compile(r"1\s*3/8\"?\s*HC\s+Prehung\s+FJ\s+Primed",         re.I), "1 3/8 HC Prehung FJ Primed (assembled unit)",            "door"),
]

# Size row e.g. "12\" x 80\" (1'0\" x 6'8\")"   or   "38\" x 80\" (3'2\" x 6'8\") EURO"
_HH_SIZE_RE = re.compile(
    r'^\s*(\d+["\']\s*x\s*\d+["\'](?:\s*\([^)]*\))?(?:\s+EURO)?)\s*(.*)$',
    re.I,
)
# Height adder, e.g. "HEIGHT 84\" Add" or "HEIGHT 96\""
_HH_HEIGHT_RE = re.compile(r'^\s*HEIGHT\s+(\d+["\'])\s*(?:Add)?\s*(.*)$', re.I)


def _looks_like_style_header(line: str) -> List[str]:
    """If line contains 1+ recognised style names, return canonical names in order."""
    text = line.strip().upper()
    if not text:
        return []
    # Use the same longest-match logic as _split_style_header so that
    # multi-word styles ("SANTA FE", "COLONIST TEXTURED") aren't broken apart.
    tokens = re.findall(r"[A-Z][A-Z]+", text)
    found: List[str] = []
    i = 0
    while i < len(tokens):
        matched = False
        for length in (3, 2, 1):
            candidate = " ".join(tokens[i : i + length])
            if candidate in _KNOWN_STYLES:
                canon = _canonicalize_style(candidate)
                if canon not in found:
                    found.append(canon)
                i += length
                matched = True
                break
        if not matched:
            i += 1
    return found


def _parse_split_column_page(
    page_lines: List[str],
    dealer_group: str,
    source_pdf: str,
    tier_defs: List[Dict[str, Any]],
    current_styles: List[str],
) -> List[Dict]:
    """
    Fallback parser for pages whose pdfplumber output emits ALL prices in a
    stacked block before ANY size labels appear (e.g. Sexton Conmore p.5-6).

    Strategy: collect price rows in order, then walk the size/section labels
    and pair them up 1:1.
    """
    if not current_styles:
        return []

    records: List[Dict] = []
    n_tiers = max(1, len(tier_defs))

    # ── Collect price rows in order ──────────────────────────────────────
    price_rows: List[List[Tuple[str, Optional[float]]]] = []
    price_only_re = re.compile(
        r'^\s*(?:\$[\d,]+\.\d+|N/?A)(?:\s+(?:\$[\d,]+\.\d+|N/?A)){0,5}\s*$',
        re.I,
    )
    for ln in page_lines:
        if price_only_re.match(ln):
            tokens = _extract_price_tokens(ln)
            # Only accept rows with the expected number of tier columns
            if len(tokens) == n_tiers:
                price_rows.append(tokens)

    if not price_rows:
        return []

    # ── Walk size/section labels and consume prices in order ─────────────
    cur_variant: Optional[str] = None
    cur_ptype: Optional[str] = None
    pi = 0  # price index

    def _consume(size_label: str, ptype: str, variant: str) -> None:
        nonlocal pi
        if pi >= len(price_rows):
            return
        slots = price_rows[pi]
        pi += 1
        # Skip if all NOT FOUND (shouldn't happen, but defensive)
        if all(pn is None and pd in ("NOT FOUND IN PDF",) for pd, pn in slots):
            return

        tiers_payload: Optional[List[Dict[str, Any]]] = None
        if n_tiers > 1:
            tiers_payload = []
            for tdef, (pd, pn) in zip(tier_defs, slots):
                tiers_payload.append({
                    "min_qty":       tdef.get("min_qty"),
                    "max_qty":       tdef.get("max_qty"),
                    "price":         pd,
                    "price_numeric": pn,
                })
        pd_default, pn_default = slots[0]
        for style in current_styles:
            records.append(_make_record(
                dealer_group, ptype, style, size_label, variant,
                pd_default, pn_default, source_pdf,
                qty_tiers=tiers_payload,
            ))

    for raw_line in page_lines:
        line = raw_line.strip()
        if not line or price_only_re.match(line):
            continue

        # Section markers
        section_matched = False
        for pat, variant, ptype in _HH_SECTIONS:
            if pat.search(line):
                cur_variant = variant
                cur_ptype = ptype
                section_matched = True
                break
        if section_matched:
            continue

        if cur_variant is None or cur_ptype is None:
            continue

        # Height adder row (label only — price comes from the price block)
        hm = _HH_HEIGHT_RE.match(line)
        if hm and not _extract_price_tokens(hm.group(2) or ""):
            ht = hm.group(1)
            _consume(f"Height {ht} add", cur_ptype,
                     f"{cur_variant}-Height-{ht}-Add")
            continue

        # Size row (label only)
        sm = _HH_SIZE_RE.match(line)
        if sm and not _extract_price_tokens(sm.group(2) or ""):
            _consume(sm.group(1).strip(), cur_ptype, cur_variant)
            continue

    return records


def _parse_simple_dealer_pages(
    pages: List[Dict],
    dealer_group: str,
    source_pdf: str,
    tier_defs: List[Dict[str, Any]],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse HomeHardware / Sexton / ILDC PDFs.

    `tier_defs` is a list defining the quantity tiers, in the same order the
    price columns appear on the page, e.g.:
        [{"min_qty":1, "max_qty":1099}, {"min_qty":1100, "max_qty":None}]
    For HomeHardware (single price column), pass a single-element list.
    """
    records: List[Dict] = []
    addons: List[Dict] = []

    n_tiers = max(1, len(tier_defs))
    current_styles: List[str] = []
    cur_variant: Optional[str] = None
    cur_ptype: Optional[str] = None

    def _emit(size_str: str, prices: List[Tuple[str, Optional[float]]]) -> None:
        """Emit one record per (style × tier-1 price). Embed qty_tiers."""
        if not current_styles or cur_variant is None or cur_ptype is None:
            return
        # Pad/truncate to n_tiers
        slots = prices[:n_tiers]
        while len(slots) < n_tiers:
            slots.append(("NOT FOUND IN PDF", None))

        # Skip rows where every tier is missing
        if all(pn is None and pd in ("NOT FOUND IN PDF", "N/A") for pd, pn in slots):
            # but still emit if explicitly N/A (so users see the gap) — only skip "NOT FOUND"
            if all(pd == "NOT FOUND IN PDF" for pd, _ in slots):
                return

        # Build qty_tiers payload (only when more than one tier defined)
        tiers_payload: Optional[List[Dict[str, Any]]] = None
        if n_tiers > 1:
            tiers_payload = []
            for tdef, (pd, pn) in zip(tier_defs, slots):
                tiers_payload.append({
                    "min_qty":       tdef.get("min_qty"),
                    "max_qty":       tdef.get("max_qty"),
                    "price":         pd,
                    "price_numeric": pn,
                })

        # Default flat price = tier-1 price
        pd_default, pn_default = slots[0]

        for style in current_styles:
            records.append(_make_record(
                dealer_group, cur_ptype, style, size_str, cur_variant,
                pd_default, pn_default, source_pdf,
                qty_tiers=tiers_payload,
            ))

    for pg in pages:
        page_lines = pg["lines"]

        # ── Skip availability charts (no pricing on these pages) ──────────
        first_chunk = " ".join(page_lines[:6]).lower()
        if (
            "sizes available" in first_chunk
            or "dimensions disponibles" in first_chunk
            or "modèle / model" in first_chunk
        ):
            continue

        # ── Adders / additional-options page → parse separately ───────────
        if any(re.search(r"(additional options|machining for|jamb add-ons)",
                         ln, re.I) for ln in page_lines):
            addons.extend(_parse_adders_page(page_lines, dealer_group, source_pdf))
            continue

        # ── Detect rotated "PRIMED HARDBOARD" header (vertical text) ──────
        # pdfplumber emits rotated multi-line labels as a stack of 1-3 char
        # fragments at the top of the page. If a contiguous run of leading
        # short letter-only lines (after the page header text) joins to the
        # same letters as HARDBOARDPRIMED, treat the page as a Primed
        # Hardboard page.
        fragments: List[str] = []
        for ln in page_lines[:25]:
            s = ln.strip()
            if not s:
                continue
            # Accept short letter-only fragments (with possible internal spaces)
            if len(s) <= 6 and re.match(r"^[A-Za-z]+(?:\s+[A-Za-z]+)*$", s):
                fragments.append(re.sub(r"\s+", "", s))
            else:
                if fragments:
                    break  # contiguous run ended
                # Not started yet – keep scanning
                continue
        if len(fragments) >= 5:
            joined = "".join(fragments).upper()
            target_letters = sorted("HARDBOARDPRIMED")
            joined_sorted = sorted(joined)
            # Accept if joined letters are a subset of HARDBOARDPRIMED
            # and cover at least 8 of its 15 letters.
            if len(joined) >= 8 and all(
                joined_sorted.count(c) <= target_letters.count(c)
                for c in set(joined_sorted)
            ):
                current_styles = [_canonicalize_style("PRIMED HARDBOARD")]

        # ── Detect "COLONIST" + "TEXTURED" split across lines ─────────────
        # ILDC page 2 emits the multi-line label "COLONIST TEXTURED" where
        # COLONIST is alone on one line and TEXTURED is on a separate line.
        page_upper = [ln.strip().upper() for ln in page_lines[:20]]
        has_colonist = any("COLONIST" in ln for ln in page_upper)
        has_textured = any(ln == "TEXTURED" for ln in page_upper)
        force_add_colonist_textured = has_colonist and has_textured

        # ── Detect "split-column" layout (Sexton Conmore pages 5-6) ──────
        # In this layout the page emits ALL prices in one stacked block
        # *before* any size labels appear. The normal line-by-line parser
        # never sees a size+price combo and produces zero records, so we
        # detect this case and fall through to a paired-pass parser.
        price_only_re = re.compile(
            r'^\s*(?:\$[\d,]+\.\d+|N/?A)(?:\s+(?:\$[\d,]+\.\d+|N/?A)){0,5}\s*$',
            re.I,
        )
        leading_price_only = 0
        first_size_idx = None
        for idx, ln in enumerate(page_lines):
            if _HH_SIZE_RE.match(ln) or _HH_HEIGHT_RE.match(ln):
                first_size_idx = idx
                break
            if price_only_re.match(ln):
                leading_price_only += 1
        if leading_price_only >= 5 and first_size_idx is not None:
            # Collect *all* styles mentioned in the header band (lines
            # before the first size label that aren't price rows). On
            # Sexton multi-style pages, 5 styles share one price column.
            collected: list[str] = []
            for ln in page_lines[: first_size_idx + 1]:
                if price_only_re.match(ln):
                    continue
                if re.search(r"\$|\d+\.\d{2}", ln):
                    continue
                styles_here = _looks_like_style_header(ln)
                for s in styles_here:
                    if s not in collected:
                        collected.append(s)
            if force_add_colonist_textured:
                ct = _canonicalize_style("COLONIST TEXTURED")
                if ct not in collected:
                    collected.append(ct)
            if collected:
                current_styles = collected
            records.extend(_parse_split_column_page(
                page_lines, dealer_group, source_pdf,
                tier_defs, current_styles,
            ))
            continue

        for raw_line in page_lines:
            line = raw_line.strip()
            if not line:
                continue

            # ── Skip boiler-plate / footers ───────────────────────────────
            if re.match(
                r'^(NET PRICE|PRICE LIST|HOME HARDWARE|SEXTON|ILDC|'
                r'Effective|Wood Grain|Moulded|Flat Panel|'
                r'Carrara and Euro|Special Colonist|.{0,3}\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)|'
                r'List qty|Size$|Net Price$|"?6 panel|For all other|moulded doors|N/A$)',
                line, re.IGNORECASE,
            ):
                # Style availability rows ("Slab" / "Bifold" markers) still need style detection below
                pass

            # ── Style availability / header row ──────────────────────────
            # Lines mentioning multiple known styles update current_styles.
            styles_here = _looks_like_style_header(line)
            if len(styles_here) >= 1 and not _HH_SIZE_RE.match(line) and not _HH_HEIGHT_RE.match(line):
                # Avoid mistaking a price-only line for a header
                if not re.search(r"\$|\d+\.\d{2}", line):
                    if force_add_colonist_textured:
                        ct = _canonicalize_style("COLONIST TEXTURED")
                        if ct not in styles_here:
                            styles_here = [ct] + styles_here
                    # Replace current style list when a header line appears
                    # (header lines only appear at the top of each page).
                    current_styles = styles_here
                    continue

            # ── Section markers ──────────────────────────────────────────
            section_matched = False
            for pat, variant, ptype in _HH_SECTIONS:
                if pat.search(line):
                    cur_variant = variant
                    cur_ptype = ptype
                    section_matched = True
                    break
            if section_matched:
                continue

            # ── Height adder row ─────────────────────────────────────────
            hm = _HH_HEIGHT_RE.match(line)
            if hm and cur_variant and current_styles:
                ht = hm.group(1)
                rest = hm.group(2) or ""
                prices = _extract_price_tokens(rest)
                size_label = f"Height {ht} add"
                # Tier handling identical to size rows
                slots = prices[:n_tiers]
                while len(slots) < n_tiers:
                    slots.append(("NOT FOUND IN PDF", None))
                if all(pd == "NOT FOUND IN PDF" for pd, _ in slots):
                    continue
                tiers_payload = None
                if n_tiers > 1:
                    tiers_payload = [
                        {
                            "min_qty": td.get("min_qty"),
                            "max_qty": td.get("max_qty"),
                            "price":         pd,
                            "price_numeric": pn,
                        }
                        for td, (pd, pn) in zip(tier_defs, slots)
                    ]
                pd0, pn0 = slots[0]
                v_label = f"{cur_variant}-Height-{ht}-Add"
                for style in current_styles:
                    records.append(_make_record(
                        dealer_group, cur_ptype, style, size_label, v_label,
                        pd0, pn0, source_pdf,
                        qty_tiers=tiers_payload,
                    ))
                continue

            # ── Size row ─────────────────────────────────────────────────
            sm = _HH_SIZE_RE.match(line)
            if sm and cur_variant and current_styles:
                size_str = sm.group(1).strip()
                rest     = sm.group(2) or ""
                prices   = _extract_price_tokens(rest)
                _emit(size_str, prices)
                continue

    return records, addons


# Tier definitions per dealer
_HH_TIERS_HOMEHARDWARE = [{"min_qty": 1, "max_qty": None}]
_HH_TIERS_SEXTON       = [
    {"min_qty": 1,    "max_qty": 1099},
    {"min_qty": 1100, "max_qty": None},
]
_HH_TIERS_ILDC         = [
    {"min_qty": 1,   "max_qty": 299},
    {"min_qty": 300, "max_qty": 1099},
]


def parse_home_hardware(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    records, addons = _parse_simple_dealer_pages(
        pdf_data["pages"], "HomeHardware", pdf_data["filename"],
        _HH_TIERS_HOMEHARDWARE,
    )
    return {"records": records, "addons": addons}


def parse_sexton(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    records, addons = _parse_simple_dealer_pages(
        pdf_data["pages"], "Group D", pdf_data["filename"],
        _HH_TIERS_SEXTON,
    )
    return {"records": records, "addons": addons}


def parse_ildc(pdf_data: Dict[str, Any]) -> Dict[str, List]:
    records, addons = _parse_simple_dealer_pages(
        pdf_data["pages"], "Group F", pdf_data["filename"],
        _HH_TIERS_ILDC,
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
    elif pdf_type == "home_hardware":
        return parse_home_hardware(pdf_data)
    elif pdf_type == "central_d":
        return parse_sexton(pdf_data)
    elif pdf_type == "central_f":
        return parse_ildc(pdf_data)
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
