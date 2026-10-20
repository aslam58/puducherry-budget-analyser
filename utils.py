import re
from pathlib import Path

NUMBER_RE = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?$")
ACCOUNT_RE = re.compile(r"^\d{2,4}(?:/\d{3,4})?(?:\(\d+\))*$")
DEMAND_RE = re.compile(r"DEMAND\s+NO\.?\s*[-:]?\s*(\d+)", re.I)


def clean_text(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split()).strip()


def normalize_numeric_token(value: str):
    """Return (numeric_value, normalized_source, status).

    '..' is explicitly treated as zero per the user's instruction.
    Empty/unknown values remain None so they can be flagged.
    """
    s = clean_text(value)
    if s in {"", "-"}:
        return None, s, "MISSING"
    if s in {"..", "…", "..."}:
        return 0.0, s, "ZERO_NOT_STATED"
    s2 = s.replace(",", "")
    if NUMBER_RE.match(s):
        try:
            return float(s2), s, "OK"
        except ValueError:
            pass
    # OCR may produce common punctuation substitutions.
    s2 = s2.replace("O", "0").replace("o", "0")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", s2):
        try:
            return float(s2), s, "OCR_NORMALIZED"
        except ValueError:
            pass
    return None, s, "UNPARSED"


def detect_demand(text: str):
    m = DEMAND_RE.search(text or "")
    return int(m.group(1)) if m else None


def looks_like_account_code(text: str) -> bool:
    return bool(ACCOUNT_RE.match(clean_text(text)))


def hierarchy_level(account_code: str):
    code = clean_text(account_code)
    if not code:
        return None
    return 1 + len(re.findall(r"\(\d+\)", code))


def safe_sheet_name(name: str) -> str:
    name = re.sub(r"[\\/*?:\[\]]", "-", name)
    return name[:31]


def format_source_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())
