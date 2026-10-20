from pathlib import Path
import math
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

from analysis import add_analysis_columns, department_summary, overall_metrics, rows_to_df, reconcile_department_totals
from config import DEPARTMENTS
from utils import safe_sheet_name

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
SUBHEADER_FILL = PatternFill("solid", fgColor="D9EAF7")
WHITE_FONT = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
THIN = Side(style="thin", color="B7B7B7")


def _style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=THIN)
    for col in range(1, ws.max_column + 1):
        max_len = 0
        for row in ws.iter_rows(min_col=col, max_col=col, max_row=min(ws.max_row, 250)):
            v = row[0].value
            max_len = max(max_len, len(str(v)) if v is not None else 0)
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 2, 10), 42)
    ws.sheet_view.showGridLines = False


def _write_df(ws, df):
    if df is None:
        return
    if df.empty:
        ws.append(["No data available"])
        return
    for row in [list(df.columns)] + df.where(pd.notna(df), None).values.tolist():
        ws.append(row)
    _style_sheet(ws)
    # Numeric formatting.
    for col_idx, col in enumerate(df.columns, start=1):
        if any(token in str(col) for token in ["₹ '000", "₹ crore", "Change"]):
            for r in range(2, ws.max_row + 1):
                ws.cell(r, col_idx).number_format = '#,##0.00;[Red]-#,##0.00'
        if "%" in str(col):
            for r in range(2, ws.max_row + 1):
                ws.cell(r, col_idx).number_format = '0.00'


def _add_bar_chart(ws, title, categories_col, data_col, anchor="J2", max_rows=None):
    if ws.max_row < 3:
        return
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = title
    chart.y_axis.title = "Department"
    chart.x_axis.title = "₹ crore"
    end = min(ws.max_row, max_rows or ws.max_row)
    data = Reference(ws, min_col=data_col, min_row=1, max_row=end)
    cats = Reference(ws, min_col=categories_col, min_row=2, max_row=end)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.height = 10
    chart.width = 18
    ws.add_chart(chart, anchor)


def _add_line_chart(ws, title, anchor="J2"):
    if ws.max_row < 2 or ws.max_column < 2:
        return
    chart = LineChart()
    chart.title = title
    chart.y_axis.title = "₹ crore"
    chart.x_axis.title = "Financial year"
    data = Reference(ws, min_col=2, max_col=5, min_row=1, max_row=2)
    chart.add_data(data, titles_from_data=True, from_rows=True)
    cats = Reference(ws, min_col=2, max_col=5, min_row=1, max_row=1)
    chart.set_categories(cats)
    chart.height = 8
    chart.width = 16
    ws.add_chart(chart, anchor)


def _write_department_sheet(wb, name, df):
    df = reconcile_department_totals(df)
    df = add_analysis_columns(df)
    ws = wb.create_sheet(safe_sheet_name(name))
    _write_df(ws, df)
    for idx, col in enumerate(df.columns, start=1):
        if "%" in str(col):
            ws.conditional_formatting.add(
                f"{get_column_letter(idx)}2:{get_column_letter(idx)}{ws.max_row}",
                ColorScaleRule(start_type='min', start_color='F8696B',
                               mid_type='percentile', mid_value=50, mid_color='FFEB84',
                               end_type='max', end_color='63BE7B')
            )

    # Department-specific analysis sheet with trend and composition charts.
    analysis_name = safe_sheet_name(name.replace("D", "D", 1) + " Analysis")
    if analysis_name in wb.sheetnames:
        analysis_name = safe_sheet_name(name[:26] + " Analysis")
    aws = wb.create_sheet(analysis_name)
    aws.append(["Metric", "Value"])
    non_total = df[df["Row Type"].eq("detail")].copy()
    demand_total = df[df["Row Type"].eq("demand_total")].copy()
    total = df[df["Row Type"].eq("total")].copy()
    # Use the final printed "Total - Demand No.X" as the authoritative department total.
    # Other top-level totals overlap with each other and would otherwise double-count.
    if not demand_total.empty:
        top = demand_total.iloc[[0]].copy()
    elif not total.empty:
        levels = pd.to_numeric(total["Hierarchy Level"], errors="coerce")
        min_level = levels.min()
        top = total[levels.eq(min_level)].copy() if pd.notna(min_level) else total
    else:
        top = non_total
    vals = {}
    for c in ["2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)", "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"]:
        vals[c] = top[c].sum(min_count=1) if not top.empty else float('nan')
        aws.append([c, vals[c] / 10000 if pd.notna(vals[c]) else None])
    aws.append(["2026-27 BE vs 2025-26 RE (%)", ((vals["2026-27 BE (₹ '000)"] - vals["2025-26 RE (₹ '000)"]) / vals["2025-26 RE (₹ '000)"] * 100) if vals["2025-26 RE (₹ '000)"] else None])
    _style_sheet(aws)
    for r in range(2, aws.max_row + 1):
        aws.cell(r, 2).number_format = '#,##0.00'

    # Trend data for a line chart.
    aws["D1"] = "Period"; aws["E1"] = "₹ crore"
    periods = [("2024-25 Actual", vals["2024-25 Actual (₹ '000)"]), ("2025-26 BE", vals["2025-26 BE (₹ '000)"]), ("2025-26 RE", vals["2025-26 RE (₹ '000)"]), ("2026-27 BE", vals["2026-27 BE (₹ '000)"])]
    for i, (period, value) in enumerate(periods, start=2):
        aws.cell(i, 4, period); aws.cell(i, 5, value / 10000 if pd.notna(value) else None)
    chart = LineChart()
    chart.title = f"{name} Budget Trend"
    chart.y_axis.title = "₹ crore"
    chart.x_axis.title = "Period"
    chart.add_data(Reference(aws, min_col=5, min_row=1, max_row=5), titles_from_data=True)
    chart.set_categories(Reference(aws, min_col=4, min_row=2, max_row=5))
    chart.height = 8; chart.width = 14
    aws.add_chart(chart, "G2")

    # Top object-head chart.
    if not non_total.empty and "Object Head" in non_total.columns:
        comp = non_total[non_total["Object Head"].fillna("").ne("")].copy()
        if not comp.empty:
            top_obj = comp.groupby("Object Head")["2026-27 BE (₹ '000)"].sum().sort_values(ascending=False).head(10).reset_index()
            aws["G20"] = "Top Object Heads — 2026-27 BE"
            aws["G20"].font = BOLD
            aws.cell(21, 7, "Object Head"); aws.cell(21, 8, "₹ crore")
            for i, row in top_obj.iterrows():
                aws.cell(22+i, 7, row["Object Head"])
                aws.cell(22+i, 8, row["2026-27 BE (₹ '000)"] / 10000)
            chart2 = BarChart()
            chart2.type = "bar"
            chart2.title = "Top 10 Object Heads — 2026-27 BE"
            chart2.add_data(Reference(aws, min_col=8, min_row=21, max_row=21+len(top_obj)), titles_from_data=True)
            chart2.set_categories(Reference(aws, min_col=7, min_row=22, max_row=21+len(top_obj)))
            chart2.height = 10; chart2.width = 16
            aws.add_chart(chart2, "J20")
    return ws


def _write_afs_analysis(wb, afs_df):
    ws = wb.create_sheet("AFS Analysis")
    if afs_df.empty:
        ws.append(["No AFS data available"])
        return
    totals = afs_df[afs_df["Row Type"].eq("total")].copy()
    ws.append(["Statement", "Section", "2024-25 Actual (₹ crore)", "2025-26 BE (₹ crore)", "2025-26 RE (₹ crore)", "2026-27 BE (₹ crore)"])
    # Use total rows by statement/section to avoid treating individual account heads as the whole AFS.
    g = totals.groupby(["Statement", "Section"], dropna=False)[[
        "2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)", "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"
    ]].max().reset_index()
    for _, r in g.iterrows():
        ws.append([r["Statement"], r["Section"], r.iloc[2]/10000, r.iloc[3]/10000, r.iloc[4]/10000, r.iloc[5]/10000])
    _style_sheet(ws)
    chart = BarChart()
    chart.title = "AFS 2026-27 BE by Statement / Section"
    chart.y_axis.title = "₹ crore"
    chart.x_axis.title = "Statement / Section"
    chart.add_data(Reference(ws, min_col=6, min_row=1, max_row=ws.max_row), titles_from_data=True)
    cats = Reference(ws, min_col=1, max_col=2, min_row=2, max_row=ws.max_row)
    # openpyxl does not support multi-column categories cleanly in every Excel version;
    # use statement labels as the category axis.
    chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
    chart.height = 10; chart.width = 18
    ws.add_chart(chart, "H2")

def build_workbook(afs_result, department_results, output_path: str):
    wb = Workbook()
    wb.remove(wb.active)

    # README
    ws = wb.create_sheet("README")
    readme = [
        ["Puducherry Government Budget Analyser", "FY 2026-27"],
        ["Purpose", "Parse Annual Financial Statement and department Demand for Grants PDFs into a single analytical workbook."],
        ["Source units", "Source documents are in ₹ thousands. Workbook also provides ₹ crore columns."],
        ["Department total rule", "For each department, the final printed 'Total - Demand No.X' row is treated as the authoritative department total. Overlapping charged/voted, revenue/capital and major-head totals are not summed together."],
        ["Missing '..'", "Treated as 0 as instructed by the user; raw source token is preserved."],
        ["Uncertain values", "Extraction attempts table parsing first and records pages requiring OCR/validation."],
        ["AFS vs Department reconciliation", "Intentionally not performed, per user instruction."],
        ["Partial uploads", "Workbook is generated for uploaded departments and missing departments are explicitly listed."],
    ]
    for row in readme:
        ws.append(row)
    ws["A1"].font = Font(size=16, bold=True)
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 100
    ws.sheet_view.showGridLines = False

    # AFS sheets
    if afs_result:
        afs_df = rows_to_df(afs_result.rows)
        afs_df = add_analysis_columns(afs_df)
        # Split by statement and section for navigability.
        for (statement, section), group in afs_df.groupby(["Statement", "Section"], dropna=False):
            label = safe_sheet_name(f"AFS {statement} {section}".strip())
            # Ensure uniqueness because Excel limits sheet names to 31 characters.
            base = label[:31]
            candidate = base
            n = 1
            while candidate in wb.sheetnames:
                suffix = f"~{n}"
                candidate = base[:31-len(suffix)] + suffix
                n += 1
            _write_df(wb.create_sheet(candidate), group.reset_index(drop=True))
        _write_df(wb.create_sheet("AFS Raw"), afs_df)
        _write_afs_analysis(wb, afs_df)

    all_department_rows = []
    for number, result in sorted(department_results.items()):
        dept = next(d for d in DEPARTMENTS if d.number == number)
        df = rows_to_df(result.rows)
        if not df.empty:
            _write_department_sheet(wb, dept.sheet_name, df)
            all_department_rows.extend(result.rows)

    all_df = rows_to_df(all_department_rows)
    summary = department_summary(all_df)
    _write_df(wb.create_sheet("Department Summary"), summary)

    # Overall analysis
    metrics = overall_metrics(summary)
    _write_df(wb.create_sheet("Overall Analysis"), metrics)

    # Statistical analysis across uploaded departments.
    if not summary.empty:
        stats_ws = wb.create_sheet("Statistical Analysis")
        be = summary["2026-27 BE (₹ '000)"].dropna()
        change = summary["Change vs 2025-26 RE (%)"].dropna()
        stats = [
            ["Statistic", "2026-27 BE (₹ crore)"],
            ["Department count uploaded", int(len(summary))],
            ["Mean", be.mean()/10000],
            ["Median", be.median()/10000],
            ["Standard deviation", be.std(ddof=1)/10000 if len(be)>1 else 0],
            ["Minimum", be.min()/10000],
            ["Maximum", be.max()/10000],
            ["Largest department share (%)", be.max()/be.sum()*100 if be.sum() else None],
            ["Mean change vs 2025-26 RE (%)", change.mean() if len(change) else None],
            ["Median change vs 2025-26 RE (%)", change.median() if len(change) else None],
            ["Largest increase vs RE (%)", change.max() if len(change) else None],
            ["Largest decrease vs RE (%)", change.min() if len(change) else None],
        ]
        for row in stats: stats_ws.append(row)
        _style_sheet(stats_ws)
        for r in range(2, stats_ws.max_row+1): stats_ws.cell(r,2).number_format = '#,##0.00'

    # Department comparison chart data
    if not summary.empty:
        chart_ws = wb.create_sheet("Overall Charts")
        chart_ws.append(["Department", "2024-25 Actual (₹ crore)", "2025-26 BE (₹ crore)", "2025-26 RE (₹ crore)", "2026-27 BE (₹ crore)"])
        for _, r in summary.iterrows():
            chart_ws.append([
                r["Department"],
                r["2024-25 Actual (₹ '000)"] / 10000,
                r["2025-26 BE (₹ '000)"] / 10000,
                r["2025-26 RE (₹ '000)"] / 10000,
                r["2026-27 BE (₹ '000)"] / 10000,
            ])
        _style_sheet(chart_ws)
        _add_bar_chart(chart_ws, "2026-27 BE by Department", 1, 5, "G2", max_rows=min(chart_ws.max_row, 21))

        # Top increases/decreases table.
        inc_ws = wb.create_sheet("Budget Changes")
        changes = summary[["Department", "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)", "Change vs 2025-26 RE (₹ '000)", "Change vs 2025-26 RE (%)"]].copy()
        changes["Change vs 2025-26 RE (₹ crore)"] = changes["Change vs 2025-26 RE (₹ '000)"] / 10000
        _write_df(inc_ws, changes.sort_values("Change vs 2025-26 RE (₹ '000)", ascending=False))

    # Validation report
    validation_rows = []
    if afs_result:
        for m in afs_result.validation_messages:
            validation_rows.append({"File": afs_result.file_path, **m})
    for number, result in department_results.items():
        for m in result.validation_messages:
            validation_rows.append({"File": result.file_path, **m})
    for number, result in department_results.items():
        for r in result.rows:
            if r.flag:
                validation_rows.append({
                    "File": r.source_file, "Page": r.source_page,
                    "Severity": "INFO", "message": r.flag
                })
    missing = [d for d in DEPARTMENTS if d.number not in department_results]
    for d in missing:
        validation_rows.append({"File": "", "Page": "", "Severity": "WARNING", "message": f"Department {d.number:02d} - {d.name} was not uploaded."})
    validation_df = pd.DataFrame(validation_rows, columns=["File", "Page", "Severity", "message"])
    _write_df(wb.create_sheet("Validation Report"), validation_df)

    # Workbook metadata
    wb.properties.title = "Puducherry Government Budget Analysis FY 2026-27"
    wb.properties.subject = "Annual Financial Statement and Department Demands"
    wb.properties.creator = "Puducherry Budget Analyser"

    # Put README first and make all sheets print-friendly.
    wb._sheets.sort(key=lambda ws: (0 if ws.title == "README" else 1, ws.title))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
