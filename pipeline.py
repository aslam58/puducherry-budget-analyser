from pathlib import Path
from parser import parse_afs_pdf, parse_department_pdf
from excel_export import build_workbook
from config import DEPARTMENT_BY_NUMBER


def run_pipeline(afs_path, department_files, output_path, progress=None):
    progress = progress or (lambda msg: None)
    afs_result = None
    if afs_path:
        progress("Parsing Annual Financial Statement...")
        afs_result = parse_afs_pdf(afs_path)
        progress(f"AFS parsed: {len(afs_result.rows)} rows from {afs_result.pages_processed} pages.")

    department_results = {}
    total = sum(len(v) for v in department_files.values())
    done = 0
    for number, files in sorted(department_files.items()):
        if number not in DEPARTMENT_BY_NUMBER:
            continue
        for file_path in files:
            done += 1
            progress(f"Parsing Demand {number:02d} - {DEPARTMENT_BY_NUMBER[number].name} ({done}/{total})...")
            result = parse_department_pdf(file_path, expected_demand=number)
            if number not in department_results:
                department_results[number] = result
            else:
                department_results[number].rows.extend(result.rows)
                department_results[number].validation_messages.extend(result.validation_messages)
                department_results[number].pages_processed += result.pages_processed
                department_results[number].pages_ocr += result.pages_ocr
            progress(f"  Extracted {len(result.rows)} rows.")

    progress("Building Excel workbook...")
    build_workbook(afs_result, department_results, output_path)
    progress(f"Workbook created: {output_path}")
    return output_path
