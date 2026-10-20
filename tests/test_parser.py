import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import parse_department_pdf, parse_afs_pdf
from analysis import rows_to_df, reconcile_department_totals, department_summary
import os

AFS_PDF = os.environ.get('AFS_PDF')
DEPT_PDF = os.environ.get('DEPARTMENT_PDF')

def test_department_sample():
    if not DEPT_PDF:
        return
    result = parse_department_pdf(DEPT_PDF, expected_demand=1)
    assert result.pages_processed == 36
    assert result.pages_ocr == 0
    df = rows_to_df(result.rows)
    salary = df[(df['Object Code'] == '01') & (df['Account Code'] == '01/001(03)(01)')].iloc[0]
    assert salary["2024-25 Actual (₹ '000)"] == 19544
    assert salary["2026-27 BE (₹ '000)"] == 23000
    checked = reconcile_department_totals(df)
    total = checked[(checked['Row Type'] == 'total') & (checked['Account Code'] == '01/001(03)(01)')].iloc[0]
    assert total['Status 2026-27 BE'] == 'MATCH'

    # The final "Total - Demand No.1" row is the authoritative department total.
    demand_total = df[df['Row Type'] == 'demand_total'].iloc[0]
    summary = department_summary(df).iloc[0]
    assert demand_total["2025-26 BE (₹ '000)"] == summary["2025-26 BE (₹ '000)"]
    assert demand_total["2025-26 RE (₹ '000)"] == summary["2025-26 RE (₹ '000)"]
    assert demand_total["2026-27 BE (₹ '000)"] == summary["2026-27 BE (₹ '000)"]


def test_afs_sample():
    if not AFS_PDF:
        return
    result = parse_afs_pdf(AFS_PDF)
    assert result.pages_processed == 38
    assert any(r.statement == 'Statement III - Public Account' for r in result.rows)


def test_department_summary_keeps_all_department_totals():
    import pandas as pd
    rows = pd.DataFrame([
        {
            "Department": "Adi Dravidar Welfare", "Row Type": "demand_total",
            "Source File": "d01.pdf", "Page": 33,
            "2024-25 Actual (₹ '000)": 100, "2025-26 BE (₹ '000)": 110,
            "2025-26 RE (₹ '000)": 120, "2026-27 BE (₹ '000)": 130,
        },
        {
            "Department": "Administrator", "Row Type": "demand_total",
            "Source File": "d02.pdf", "Page": 20,
            "2024-25 Actual (₹ '000)": 200, "2025-26 BE (₹ '000)": 210,
            "2025-26 RE (₹ '000)": 220, "2026-27 BE (₹ '000)": 230,
        },
    ])
    summary = department_summary(rows)
    assert set(summary["Department"]) == {"Adi Dravidar Welfare", "Administrator"}
    assert len(summary) == 2
