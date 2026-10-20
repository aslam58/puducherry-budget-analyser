import math
import pandas as pd
import numpy as np

from config import THOUSANDS_PER_CRORE
from models import ParseResult, ExtractedRow


def rows_to_df(rows: list[ExtractedRow]) -> pd.DataFrame:
    data = []
    for r in rows:
        data.append({
            "Source File": r.source_file,
            "Page": r.source_page,
            "Demand No.": r.demand_no,
            "Department": r.department,
            "Statement": r.statement,
            "Section": r.section,
            "Account Code": r.account_code,
            "Hierarchy Level": r.hierarchy_level,
            "Description": r.description,
            "Region": r.region,
            "Object Code": r.object_code,
            "Object Head": r.object_head,
            "2024-25 Actual (₹ '000)": r.actual_2024_25,
            "2025-26 BE (₹ '000)": r.be_2025_26,
            "2025-26 RE (₹ '000)": r.re_2025_26,
            "2026-27 BE (₹ '000)": r.be_2026_27,
            "2024-25 Actual (₹ crore)": _crore(r.actual_2024_25),
            "2025-26 BE (₹ crore)": _crore(r.be_2025_26),
            "2025-26 RE (₹ crore)": _crore(r.re_2025_26),
            "2026-27 BE (₹ crore)": _crore(r.be_2026_27),
            "Raw 2024-25": r.raw_actual,
            "Raw 2025-26 BE": r.raw_be_2025,
            "Raw 2025-26 RE": r.raw_re_2025,
            "Raw 2026-27 BE": r.raw_be_2026,
            "Row Type": r.row_type,
            "Extraction Method": r.extraction_method,
            "Confidence": r.confidence,
            "Flags": r.flag,
            "Printed Total (₹ '000)": r.printed_total,
            "Calculated Total (₹ '000)": r.calculated_total,
            "Reconciliation Difference (₹ '000)": r.reconciliation_difference,
            "Reconciliation Status": r.reconciliation_status,
        })
    return pd.DataFrame(data)


def _crore(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v / THOUSANDS_PER_CRORE


def _pct(a, b):
    if b is None or b == 0 or pd.isna(b):
        return np.nan
    return (a - b) / b * 100 if a is not None and not pd.isna(a) else np.nan


def add_analysis_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    a = df["2024-25 Actual (₹ '000)"].astype(float)
    be25 = df["2025-26 BE (₹ '000)"].astype(float)
    re25 = df["2025-26 RE (₹ '000)"].astype(float)
    be26 = df["2026-27 BE (₹ '000)"].astype(float)
    df["2025-26 RE vs BE Change (₹ '000)"] = re25 - be25
    df["2025-26 RE vs BE %"] = np.where(be25 != 0, (re25 - be25) / be25 * 100, np.nan)
    df["2026-27 BE vs 2025-26 RE Change (₹ '000)"] = be26 - re25
    df["2026-27 BE vs 2025-26 RE %"] = np.where(re25 != 0, (be26 - re25) / re25 * 100, np.nan)
    df["2026-27 BE vs 2025-26 BE Change (₹ '000)"] = be26 - be25
    df["2026-27 BE vs 2025-26 BE %"] = np.where(be25 != 0, (be26 - be25) / be25 * 100, np.nan)
    df["2025-26 BE vs 2024-25 Actual %"] = np.where(a != 0, (be25 - a) / a * 100, np.nan)
    return df


def department_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    # Prefer printed totals at the highest hierarchy level. This prevents double-counting
    # child subtotals while still retaining separate top-level revenue/capital heads.
    # The final "Total - Demand No.X" row is the authoritative department total.
    # Do NOT sum other top-level totals: the demand page contains overlapping
    # Revenue/Capital, Major Head, Charged and Voted totals which would double-count.
    demand_total = df[df["Row Type"].eq("demand_total")].copy()
    if not demand_total.empty:
        # IMPORTANT: there is one authoritative demand-total row PER DEPARTMENT.
        # The previous implementation used iloc[[0]], which accidentally kept
        # only the first department (usually Demand 01) from the combined dataset.
        # Never sum demand totals across rows blindly; select one authoritative
        # row for each department. If duplicate copies of the same PDF were
        # uploaded, identical totals are de-duplicated.
        value_cols = [
            "2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)",
            "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"
        ]
        demand_total = demand_total.drop_duplicates(
            subset=["Department"] + value_cols, keep="last"
        )
        # If multiple distinct demand-total rows remain for a department
        # (for example conflicting/duplicate source files), use the last
        # authoritative row in document order rather than double-counting it.
        # Such ambiguity should be surfaced by Validation Report separately.
        demand_total = (
            demand_total.sort_values(["Department", "Source File", "Page"],
                                     na_position="last")
            .groupby("Department", dropna=False, as_index=False)
            .tail(1)
        )
        top = demand_total.copy()
    else:
        total = df[df["Row Type"].eq("total")].copy()
        if not total.empty:
            levels = pd.to_numeric(total["Hierarchy Level"], errors="coerce")
            min_level = levels.min()
            top = total[levels.eq(min_level)].copy() if pd.notna(min_level) else total.copy()
        else:
            # Transparent fallback if a document contains no printed totals.
            top = df[df["Row Type"].ne("total")].copy()
    grouped = top.groupby("Department", dropna=False)[[
        "2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)",
        "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"
    ]].sum(min_count=1).reset_index()
    grouped["2026-27 BE (₹ crore)"] = grouped["2026-27 BE (₹ '000)"] / THOUSANDS_PER_CRORE
    grouped["Change vs 2025-26 RE (₹ '000)"] = grouped["2026-27 BE (₹ '000)"] - grouped["2025-26 RE (₹ '000)"]
    grouped["Change vs 2025-26 RE (%)"] = np.where(
        grouped["2025-26 RE (₹ '000)"] != 0,
        grouped["Change vs 2025-26 RE (₹ '000)"] / grouped["2025-26 RE (₹ '000)"] * 100,
        np.nan,
    )
    grouped["Change vs 2025-26 BE (₹ '000)"] = grouped["2026-27 BE (₹ '000)"] - grouped["2025-26 BE (₹ '000)"]
    grouped["Change vs 2025-26 BE (%)"] = np.where(
        grouped["2025-26 BE (₹ '000)"] != 0,
        grouped["Change vs 2025-26 BE (₹ '000)"] / grouped["2025-26 BE (₹ '000)"] * 100,
        np.nan,
    )
    return grouped.sort_values("2026-27 BE (₹ '000)", ascending=False)


def overall_metrics(department_summary_df: pd.DataFrame) -> pd.DataFrame:
    if department_summary_df.empty:
        return pd.DataFrame()
    sums = department_summary_df[[
        "2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)",
        "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"
    ]].sum()
    re_vs_be = sums["2025-26 RE (₹ '000)"] - sums["2025-26 BE (₹ '000)"]
    new_vs_re = sums["2026-27 BE (₹ '000)"] - sums["2025-26 RE (₹ '000)"]
    rows = [
        ("2024-25 Actual", sums["2024-25 Actual (₹ '000)"], sums["2024-25 Actual (₹ '000)"] / THOUSANDS_PER_CRORE),
        ("2025-26 BE", sums["2025-26 BE (₹ '000)"], sums["2025-26 BE (₹ '000)"] / THOUSANDS_PER_CRORE),
        ("2025-26 RE", sums["2025-26 RE (₹ '000)"], sums["2025-26 RE (₹ '000)"] / THOUSANDS_PER_CRORE),
        ("2026-27 BE", sums["2026-27 BE (₹ '000)"], sums["2026-27 BE (₹ '000)"] / THOUSANDS_PER_CRORE),
        ("RE vs BE change", re_vs_be, re_vs_be / sums["2025-26 BE (₹ '000)"] * 100 if sums["2025-26 BE (₹ '000)"] else np.nan),
        ("2026-27 BE vs RE change", new_vs_re, new_vs_re / sums["2025-26 RE (₹ '000)"] * 100 if sums["2025-26 RE (₹ '000)"] else np.nan),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value (₹ '000)", "Value / Rate"])


def reconcile_department_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Independently reconcile printed subtotal rows against child detail rows.

    A total with account code X is compared with detail rows whose account code starts
    with X and has a deeper hierarchy level. We do not overwrite source totals.
    """
    if df.empty:
        return df
    out = df.copy()
    numeric_cols = ["2024-25 Actual (₹ '000)", "2025-26 BE (₹ '000)", "2025-26 RE (₹ '000)", "2026-27 BE (₹ '000)"]
    for idx, row in out.iterrows():
        if row.get("Row Type") != "total" or not row.get("Account Code"):
            continue
        code = str(row["Account Code"])
        level = row.get("Hierarchy Level")
        if pd.isna(level):
            continue
        children = out[(out["Row Type"] == "detail") & out["Account Code"].fillna("").astype(str).str.startswith(code)]
        # Leaf totals have the same account code as their object-head detail rows;
        # higher totals have deeper descendant codes. Both are valid children.
        children = children[children["Hierarchy Level"].fillna(0) >= float(level)]
        if children.empty:
            continue
        for col in numeric_cols:
            calc = children[col].sum(min_count=1)
            printed = row[col]
            if pd.isna(calc) or pd.isna(printed):
                continue
            # Tiny tolerance protects against floating representation, not financial discrepancies.
            diff = float(printed) - float(calc)
            status = "MATCH" if abs(diff) < 0.01 else "MISMATCH"
            # Store a compact overall reconciliation status; detailed values for each year are added below.
            suffix = col.split(" (")[0]
            out.at[idx, f"Calculated {suffix} (₹ '000)"] = calc
            out.at[idx, f"Difference {suffix} (₹ '000)"] = diff
            out.at[idx, f"Status {suffix}"] = status
    return out
