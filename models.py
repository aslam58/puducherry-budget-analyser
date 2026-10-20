from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExtractedRow:
    source_file: str
    source_page: int
    demand_no: Optional[int]
    department: str
    statement: str
    section: str
    account_code: str = ""
    hierarchy_level: Optional[int] = None
    description: str = ""
    region: str = ""
    object_code: str = ""
    object_head: str = ""
    actual_2024_25: Optional[float] = None
    be_2025_26: Optional[float] = None
    re_2025_26: Optional[float] = None
    be_2026_27: Optional[float] = None
    raw_actual: str = ""
    raw_be_2025: str = ""
    raw_re_2025: str = ""
    raw_be_2026: str = ""
    row_type: str = "detail"
    extraction_method: str = "table"
    confidence: float = 1.0
    flag: str = ""
    printed_total: Optional[float] = None
    calculated_total: Optional[float] = None
    reconciliation_difference: Optional[float] = None
    reconciliation_status: str = ""

@dataclass
class ParseResult:
    file_path: str
    document_type: str
    rows: list[ExtractedRow] = field(default_factory=list)
    validation_messages: list[dict] = field(default_factory=list)
    pages_processed: int = 0
    pages_ocr: int = 0

@dataclass
class DepartmentUpload:
    number: int
    name: str
    files: list[str] = field(default_factory=list)
