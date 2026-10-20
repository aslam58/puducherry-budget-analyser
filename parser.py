import re
from pathlib import Path

import pdfplumber

from config import DEPARTMENT_BY_NUMBER
from models import ExtractedRow, ParseResult
from utils import clean_text, detect_demand, hierarchy_level, looks_like_account_code, normalize_numeric_token
from ocr_fallback import ocr_page

HEADER_PATTERNS = {
    "revenue": re.compile(r"Revenue Section|வருவாய்ப் பகுதி", re.I),
    "capital": re.compile(r"Capital Account|மூலதனக் கணக்கு", re.I),
    "public_account": re.compile(r"PUBLIC ACCOUNT|பொதுக்கணக்கு", re.I),
}


def _cell_lines(cell):
    return [clean_text(x) for x in (cell or "").splitlines() if clean_text(x)]


def _first_account_code(text):
    for token in re.findall(r"(?<!\d)\d{2,4}(?:/\d{3,4})?(?:\(\d+\))*", text or ""):
        if looks_like_account_code(token):
            return token
    return ""


def _parse_object_blocks(head_cell):
    """Split an English department-head cell into object-code blocks.

    Example: 01 Salaries / 08 Leave Travel / Concession becomes two blocks,
    while continuation lines are retained in the relevant block.
    """
    lines = _cell_lines(head_cell)
    blocks = []
    current = None
    for line in lines:
        m = re.match(r"^(\d{1,3})\s+(?!-)(.+)$", line)
        if m:
            if current:
                blocks.append(current)
            current = {"code": m.group(1), "lines": [m.group(2)]}
        elif current:
            current["lines"].append(line)
    if current:
        blocks.append(current)
    for b in blocks:
        b["description"] = clean_text(" ".join(b["lines"]))
    return blocks


def _parse_department_context(head_cell):
    lines = _cell_lines(head_cell)
    codes = []
    for line in lines:
        code = _first_account_code(line)
        if code:
            codes.append(code)
    # Last hierarchical code before object-head lines is usually the most specific context.
    return codes[-1] if codes else ""


def _total_info(head_cell):
    joined = clean_text(" ".join(_cell_lines(head_cell)))
    # The final summary immediately before "Details of Establishment" contains
    # the authoritative department total, e.g. "Total - Demand No.1".
    # It has no hierarchical account code, so it must be classified separately.
    demand_total = bool(re.search(r"\bTotal\s*-\s*Demand\s+No\.?\s*\d+", joined, re.I))
    if demand_total:
        return True, "", joined, "demand_total"
    if re.search(r"\bTotal\s*-", joined, re.I):
        return True, _first_account_code(joined), joined, "total"
    return False, "", joined, ""


def _numeric_lines(cell):
    return _cell_lines(cell)


def _make_department_row(path, page_no, demand_no, section, account_code, obj_code, obj_head,
                         nums, raw_nums, row_type="detail", description="", region="", confidence=1.0,
                         method="table", flag=""):
    vals, raws, statuses = [], [], []
    for token in nums:
        v, raw, status = normalize_numeric_token(token)
        vals.append(v); raws.append(raw); statuses.append(status)
    flags = [x for x in flag.split("; ") if x]
    if "UNPARSED" in statuses: flags.append("UNPARSED_NUMBER")
    if "MISSING" in statuses: flags.append("MISSING_NUMBER")
    if "ZERO_NOT_STATED" in statuses: flags.append("DOTS_TREATED_AS_ZERO")
    dept_name = DEPARTMENT_BY_NUMBER[demand_no].name if demand_no in DEPARTMENT_BY_NUMBER else ""
    return ExtractedRow(
        source_file=path, source_page=page_no, demand_no=demand_no, department=dept_name,
        statement="Demand for Grants", section=section, account_code=account_code,
        hierarchy_level=hierarchy_level(account_code), description=description,
        region=region, object_code=obj_code, object_head=obj_head,
        actual_2024_25=vals[0] if len(vals) > 0 else None,
        be_2025_26=vals[1] if len(vals) > 1 else None,
        re_2025_26=vals[2] if len(vals) > 2 else None,
        be_2026_27=vals[3] if len(vals) > 3 else None,
        raw_actual=raws[0] if len(raws) > 0 else "",
        raw_be_2025=raws[1] if len(raws) > 1 else "",
        raw_re_2025=raws[2] if len(raws) > 2 else "",
        raw_be_2026=raws[3] if len(raws) > 3 else "",
        row_type=row_type, extraction_method=method, confidence=confidence,
        flag="; ".join(sorted(set(flags))),
    )


def _department_rows_from_table(path, page_no, demand_no, section, table):
    if not table:
        return []
    out = []
    for row in table:
        if not row or len(row) < 6:
            continue
        joined = " ".join(clean_text(x) for x in row if x)
        if "Heads of Account" in joined or "Budget Estimate" in joined or "Accounts" in joined:
            continue
        # Columns: actual, BE25, RE25, Tamil head, English head, BE26.
        num_cols = [row[0], row[1], row[2], row[5]]
        nlines = [_numeric_lines(c) for c in num_cols]
        max_n = max((len(x) for x in nlines), default=0)
        eng = row[4] or ""
        blocks = _parse_object_blocks(eng)
        total_flag, total_code, total_desc, total_kind = _total_info(eng)

        # Multi-item rows are aligned by object code blocks and numeric lines.
        if len(blocks) == max_n and max_n > 1:
            context_code = _parse_department_context(eng)
            # Context code can accidentally be an object code; derive the parent from the English lines.
            hierarchy_codes = re.findall(r"(?<!\d)\d{2}/\d{3}(?:\(\d+\))*", eng)
            parent_code = hierarchy_codes[-1] if hierarchy_codes else ""
            for i, block in enumerate(blocks):
                nums = [nlines[c][i] if i < len(nlines[c]) else "" for c in range(4)]
                region = ""
                if "Pondicherry Region" in eng: region = "Pondicherry"
                elif "Karaikal Region" in eng: region = "Karaikal"
                elif "Mahe Region" in eng: region = "Mahe"
                elif "Yanam Region" in eng: region = "Yanam"
                out.append(_make_department_row(
                    path, page_no, demand_no, section, parent_code, block["code"], block["description"],
                    nums, nums, region=region
                ))
            continue

        # A subtotal/total row has one numeric line and a total label.
        if total_flag and max_n == 1:
            nums = [x[0] if x else "" for x in nlines]
            out.append(_make_department_row(
                path, page_no, demand_no, section, total_code, "", "", nums, nums,
                row_type=total_kind or "total", description=total_desc
            ))
            continue

        # Single detail row with one object code block.
        if len(blocks) == 1 and max_n == 1:
            nums = [x[0] if x else "" for x in nlines]
            hierarchy_codes = re.findall(r"(?<!\d)\d{2}/\d{3}(?:\(\d+\))*", eng)
            parent_code = hierarchy_codes[-1] if hierarchy_codes else ""
            region = ""
            if "Pondicherry Region" in eng: region = "Pondicherry"
            elif "Karaikal Region" in eng: region = "Karaikal"
            elif "Mahe Region" in eng: region = "Mahe"
            elif "Yanam Region" in eng: region = "Yanam"
            out.append(_make_department_row(
                path, page_no, demand_no, section, parent_code, blocks[0]["code"], blocks[0]["description"],
                nums, nums, region=region
            ))
            continue

        # Hierarchy/section-only row. Keep it for audit context, but with no fabricated numbers.
        if eng.strip():
            nums = [x[0] if x else "" for x in nlines]
            code = _first_account_code(eng)
            out.append(_make_department_row(
                path, page_no, demand_no, section, code, "", "", nums, nums,
                row_type="header", description=clean_text(eng)
            ))
    return out


def _ocr_fallback_department(path, page_no, demand_no, section):
    """Conservative OCR fallback.

    Only creates a row when OCR produces an unambiguous object code plus four numeric
    values on the same line. Otherwise it returns no financial row and flags the page.
    """
    text = ocr_page(path, page_no)
    rows = []
    for line in text.splitlines():
        line = clean_text(line)
        if not line:
            continue
        code_match = re.search(r"(?<!\d)(\d{1,3})\s+([A-Za-z][A-Za-z .&'/-]{2,})$", line)
        nums = re.findall(r"(?<!\w)[0-9OolI]+(?:,[0-9OolI]+)*(?:\.[0-9OolI]+)?|\.\.(?!\w)", line)
        if code_match and len(nums) == 4:
            normalized = [normalize_numeric_token(x)[0] for x in nums]
            if all(v is not None for v in normalized):
                rows.append(_make_department_row(
                    path, page_no, demand_no, section, "", code_match.group(1), code_match.group(2),
                    nums, nums, confidence=0.55, method="ocr", flag="OCR_FALLBACK"
                ))
    return rows


def parse_department_pdf(file_path: str, expected_demand: int | None = None) -> ParseResult:
    path = str(Path(file_path))
    result = ParseResult(path, "department")
    current_section = ""
    demand_no = expected_demand

    with pdfplumber.open(path) as pdf:
        result.pages_processed = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            detected = detect_demand(text)
            if detected:
                demand_no = detected
            for key, pat in HEADER_PATTERNS.items():
                if pat.search(text):
                    current_section = key
                    break

            tables = page.extract_tables()
            if not tables:
                result.pages_ocr += 1
                ocr_rows = _ocr_fallback_department(path, page_no, demand_no, current_section)
                result.rows.extend(ocr_rows)
                result.validation_messages.append({
                    "severity": "WARNING", "page": page_no,
                    "message": f"Structured table extraction failed; OCR fallback attempted. Recovered {len(ocr_rows)} row(s)."
                })
                if not ocr_rows:
                    result.validation_messages.append({
                        "severity": "ERROR", "page": page_no,
                        "message": "OCR could not produce sufficiently unambiguous financial rows; values were left blank."
                    })
                continue
            for table in tables:
                result.rows.extend(_department_rows_from_table(path, page_no, demand_no, current_section, table))

    if expected_demand and demand_no and expected_demand != demand_no:
        result.validation_messages.append({
            "severity": "ERROR", "page": 1,
            "message": f"Uploaded file says Demand No. {demand_no}, but it was assigned to Demand No. {expected_demand}."
        })
    return result


def _afs_description_blocks(eng_cell):
    lines = _cell_lines(eng_cell)
    blocks = []
    current = None
    for line in lines:
        m = re.match(r"^(\d{4})\.\s*(.*)$", line)
        if m:
            if current:
                blocks.append(current)
            current = {"code": m.group(1), "lines": [m.group(2)]}
        elif current:
            current["lines"].append(line)
        elif line:
            # Category labels such as A. TAX REVENUE / (a) Goods and Services tax.
            current = {"code": "", "lines": [line]}
    if current:
        blocks.append(current)
    for b in blocks:
        b["description"] = clean_text(" ".join(b["lines"]))
    return blocks


def _make_afs_row(path, page_no, statement, section, desc, account_code, nums, row_type="detail", method="table", confidence=1.0, flag=""):
    vals, raws, statuses = [], [], []
    for token in nums:
        v, raw, status = normalize_numeric_token(token)
        vals.append(v); raws.append(raw); statuses.append(status)
    flags = [x for x in flag.split("; ") if x]
    if "UNPARSED" in statuses: flags.append("UNPARSED_NUMBER")
    if "MISSING" in statuses: flags.append("MISSING_NUMBER")
    if "ZERO_NOT_STATED" in statuses: flags.append("DOTS_TREATED_AS_ZERO")
    return ExtractedRow(
        source_file=path, source_page=page_no, demand_no=None, department="", statement=statement,
        section=section, account_code=account_code, hierarchy_level=hierarchy_level(account_code),
        description=desc, actual_2024_25=vals[0] if len(vals)>0 else None,
        be_2025_26=vals[1] if len(vals)>1 else None, re_2025_26=vals[2] if len(vals)>2 else None,
        be_2026_27=vals[3] if len(vals)>3 else None, raw_actual=raws[0] if len(raws)>0 else "",
        raw_be_2025=raws[1] if len(raws)>1 else "", raw_re_2025=raws[2] if len(raws)>2 else "",
        raw_be_2026=raws[3] if len(raws)>3 else "", row_type=row_type,
        extraction_method=method, confidence=confidence, flag="; ".join(sorted(set(flags)))
    )


def _afs_rows_from_table(path, page_no, statement, section, table):
    out = []
    for row in table:
        if not row or len(row) < 6:
            continue
        joined = " ".join(clean_text(x) for x in row if x)
        if "Heads of Account" in joined or "Budget Estimate" in joined or "Accounts" in joined:
            continue
        # AFS columns: Tamil description, English description, Actual, BE25, RE25, BE26.
        nums_cells = [row[2], row[3], row[4], row[5]]
        nlines = [_numeric_lines(c) for c in nums_cells]
        max_n = max((len(x) for x in nlines), default=0)
        eng = row[1] or ""
        blocks = _afs_description_blocks(eng)
        if len(blocks) == max_n and max_n > 1:
            for i, b in enumerate(blocks):
                nums = [nlines[c][i] if i < len(nlines[c]) else "" for c in range(4)]
                row_type = "total" if b["description"].lower().startswith("total") else "detail"
                out.append(_make_afs_row(path, page_no, statement, section, b["description"], b["code"], nums, row_type=row_type))
            continue
        if max_n == 1:
            nums = [x[0] if x else "" for x in nlines]
            code = _first_account_code(eng)
            row_type = "total" if re.search(r"\bTotal\b", eng, re.I) else ("detail" if code else "header")
            out.append(_make_afs_row(path, page_no, statement, section, clean_text(eng), code, nums, row_type=row_type))
            continue
        if eng.strip():
            out.append(_make_afs_row(path, page_no, statement, section, clean_text(eng), _first_account_code(eng), [x[0] if x else "" for x in nlines], row_type="header"))
    return out


def parse_afs_pdf(file_path: str) -> ParseResult:
    path = str(Path(file_path))
    result = ParseResult(path, "AFS")
    current_statement = ""
    current_section = ""
    with pdfplumber.open(path) as pdf:
        result.pages_processed = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            m_statement = re.search(r"STATEMENT\s*-\s*(I{1,3}|IV)(?![A-Za-z])", text, re.I)
            if m_statement:
                roman = m_statement.group(1).upper()
                current_statement = {"I": "Statement I - Consolidated Fund", "II": "Statement II", "III": "Statement III - Public Account", "IV": "Statement IV"}.get(roman, current_statement)
            if re.search(r"RECEIPTS", text, re.I): current_section = "Receipts"
            elif re.search(r"DISBURSEMENTS", text, re.I): current_section = "Disbursements"
            tables = page.extract_tables()
            if not tables:
                result.pages_ocr += 1
                # AFS OCR is intentionally conservative; page is flagged if structured extraction fails.
                try:
                    _ = ocr_page(path, page_no)
                except Exception as exc:
                    result.validation_messages.append({"severity":"ERROR", "page":page_no, "message":f"OCR fallback failed: {exc}"})
                result.validation_messages.append({"severity":"WARNING", "page":page_no, "message":"Structured AFS table extraction failed; OCR fallback attempted. No uncertain financial values were invented."})
                continue
            for table in tables:
                result.rows.extend(_afs_rows_from_table(path, page_no, current_statement, current_section, table))
    return result
