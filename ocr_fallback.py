"""OCR fallback helpers.

OCR is deliberately isolated from the primary parser. The application can invoke this
module only for pages where structured extraction failed. Values that OCR cannot parse
confidently are returned as None and flagged rather than invented.
"""
from PIL import Image
import io
import re
import fitz
import pytesseract

from utils import normalize_numeric_token


def ocr_page(pdf_path: str, page_number: int, dpi: int = 220):
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(image, config="--psm 6")
    return text


def ocr_numeric_candidates(text: str):
    candidates = []
    for token in re.findall(r"(?<!\w)[0-9OolI.,]+(?!\w)", text):
        v, raw, status = normalize_numeric_token(token)
        if v is not None:
            candidates.append((v, raw, status))
    return candidates
