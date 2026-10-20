# Puducherry Government Budget Analyser — FY 2026-27

A local macOS desktop application for parsing the Puducherry Government Annual Financial Statement (AFS) and the 39 Demand for Grants PDFs into one Excel workbook.

## Design decisions confirmed by the user

- Desktop application on macOS.
- AFS upload + one or more PDFs per department.
- Exactly 39 departments from the official Demand list supplied by the user.
- `..` is treated as numeric zero, while the original token is retained.
- Table extraction first; OCR fallback only when structured extraction fails.
- If OCR remains uncertain, the value is left blank and the page/row is flagged.
- Printed totals are independently reconciled against extracted child rows where the hierarchy permits.
- Partial department uploads are allowed; missing departments are explicitly reported.
- Source values remain in ₹ thousands and equivalent ₹ crore columns are also generated.
- No AFS-vs-department reconciliation is performed.
- Department-level headline metrics use the final printed `Total - Demand No.X` row (the summary immediately before `Details of Establishment`) as the authoritative total; overlapping Revenue/Capital, Major Head, Charged and Voted totals are not summed together.

## Run on macOS

1. Install Python 3.11+.
2. Install Tesseract if it is not already available:
   ```bash
   brew install tesseract
   ```
3. Open Terminal in this folder.
4. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Start the application:
   ```bash
   python app.py
   ```

## Output workbook

The generated workbook contains source-preserving raw data, department sheets, AFS sheets, departmental analysis, overall analysis, charts, budget-change rankings, and a validation report.

No financial value is hard-coded into the application.
