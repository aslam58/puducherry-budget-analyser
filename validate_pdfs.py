import argparse
from parser import parse_afs_pdf, parse_department_pdf
from analysis import rows_to_df, reconcile_department_totals

parser = argparse.ArgumentParser(description='Validate parser against supplied Puducherry PDFs.')
parser.add_argument('--afs', required=True, help='Path to AFS PDF')
parser.add_argument('--department', required=True, help='Path to department Demand PDF')
parser.add_argument('--demand', type=int, default=1)
args = parser.parse_args()

afs = parse_afs_pdf(args.afs)
dept = parse_department_pdf(args.department, expected_demand=args.demand)
print(f'AFS: {len(afs.rows)} rows, {afs.pages_processed} pages, {afs.pages_ocr} OCR fallback pages')
print(f'Department {args.demand:02d}: {len(dept.rows)} rows, {dept.pages_processed} pages, {dept.pages_ocr} OCR fallback pages')
df = reconcile_department_totals(rows_to_df(dept.rows))
matched = sum((df[c] == 'MATCH').sum() for c in df.columns if c.startswith('Status '))
mismatched = sum((df[c] == 'MISMATCH').sum() for c in df.columns if c.startswith('Status '))
print(f'Reconciliation matches: {matched}; mismatches: {mismatched}')
print('Validation messages:', len(afs.validation_messages) + len(dept.validation_messages))
