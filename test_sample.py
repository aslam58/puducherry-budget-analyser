from pathlib import Path
from parser import parse_afs_pdf, parse_department_pdf
from excel_export import build_workbook

BASE = Path(__file__).parent.parent
AFS = BASE / 'AFS202627.pdf'
ADI = BASE / 'Adi dravidar.pdf'
OUT = BASE / 'sample_budget_analysis.xlsx'

afs = parse_afs_pdf(str(AFS))
adi = parse_department_pdf(str(ADI), expected_demand=1)
print('AFS', len(afs.rows), 'rows', afs.pages_processed, 'pages', 'OCR pages', afs.pages_ocr)
print('ADI', len(adi.rows), 'rows', adi.pages_processed, 'pages', 'OCR pages', adi.pages_ocr)
print('ADI sample:')
for r in adi.rows[:10]:
    print(r.account_code, r.object_code, r.object_head, r.actual_2024_25, r.be_2025_26, r.re_2025_26, r.be_2026_27)
build_workbook(afs, {1: adi}, str(OUT))
print('created', OUT, OUT.stat().st_size)
