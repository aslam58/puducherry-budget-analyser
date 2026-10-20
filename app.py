import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import DEPARTMENTS
from pipeline import run_pipeline

class BudgetAnalyserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Puducherry Government Budget Analyser — FY 2026-27")
        self.root.geometry("1150x850")
        self.root.minsize(950, 650)

        self.afs_path = tk.StringVar()
        self.department_files = {d.number: [] for d in DEPARTMENTS}
        self.status = tk.StringVar(value="Ready. Upload the AFS and any number of department PDFs.")
        self.progress = tk.DoubleVar(value=0)
        self.widgets = {}

        self._build()

    def _build(self):
        top = ttk.Frame(self.root, padding=18)
        top.pack(fill="x")
        ttk.Label(top, text="Puducherry Government Budget Analyser", font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Label(top, text="Annual Financial Statement + 39 Demands for Grants • FY 2026-27", font=("TkDefaultFont", 11)).pack(anchor="w", pady=(4, 0))

        afs = ttk.LabelFrame(self.root, text="1. Annual Financial Statement", padding=12)
        afs.pack(fill="x", padx=18, pady=(0, 10))
        ttk.Button(afs, text="Upload AFS PDF", command=self.upload_afs).pack(side="left")
        ttk.Label(afs, textvariable=self.afs_path).pack(side="left", padx=12, fill="x", expand=True)
        ttk.Button(afs, text="Clear", command=lambda: self.afs_path.set("")).pack(side="right")

        dept_frame = ttk.LabelFrame(self.root, text="2. Department Demands", padding=10)
        dept_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        canvas = tk.Canvas(dept_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dept_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        headers = ["Demand", "Department", "Files", "Action"]
        for c, h in enumerate(headers):
            ttk.Label(inner, text=h, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=c, sticky="w", padx=6, pady=5)
        for r, d in enumerate(DEPARTMENTS, start=1):
            ttk.Label(inner, text=f"{d.number:02d}").grid(row=r, column=0, sticky="w", padx=6, pady=3)
            ttk.Label(inner, text=d.name).grid(row=r, column=1, sticky="w", padx=6, pady=3)
            label = ttk.Label(inner, text="0 file(s)")
            label.grid(row=r, column=2, sticky="w", padx=6, pady=3)
            self.widgets[d.number] = label
            ttk.Button(inner, text="Upload PDF(s)", command=lambda n=d.number: self.upload_department(n)).grid(row=r, column=3, padx=6, pady=3)
            ttk.Button(inner, text="Clear", command=lambda n=d.number: self.clear_department(n)).grid(row=r, column=4, padx=6, pady=3)

        bottom = ttk.Frame(self.root, padding=(18, 0, 18, 18))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status).pack(anchor="w", pady=(0, 6))
        ttk.Progressbar(bottom, variable=self.progress, maximum=100).pack(fill="x", pady=(0, 10))
        buttons = ttk.Frame(bottom)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Validate / Generate Excel", command=self.generate).pack(side="left")
        ttk.Button(buttons, text="Quit", command=self.root.destroy).pack(side="right")

    def upload_afs(self):
        path = filedialog.askopenfilename(title="Select Annual Financial Statement PDF", filetypes=[("PDF files", "*.pdf")])
        if path:
            self.afs_path.set(path)
            self.status.set("AFS selected. You can now upload department PDFs.")

    def upload_department(self, number):
        paths = filedialog.askopenfilenames(title=f"Select PDF(s) for Demand {number:02d}", filetypes=[("PDF files", "*.pdf")])
        if paths:
            self.department_files[number] = list(paths)
            self.widgets[number].configure(text=f"{len(paths)} file(s)")
            self.status.set(f"Demand {number:02d}: {len(paths)} PDF(s) selected.")

    def clear_department(self, number):
        self.department_files[number] = []
        self.widgets[number].configure(text="0 file(s)")

    def generate(self):
        if not self.afs_path.get():
            messagebox.showwarning("AFS required", "Please upload the Annual Financial Statement PDF.")
            return
        uploaded = {n: files for n, files in self.department_files.items() if files}
        if not uploaded:
            messagebox.showwarning("No departments", "Please upload at least one department Demand PDF.")
            return
        output = filedialog.asksaveasfilename(
            title="Save analysis workbook",
            defaultextension=".xlsx",
            initialfile="Puducherry_Budget_Analysis_2026-27.xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
        )
        if not output:
            return
        self.progress.set(0)
        self.status.set("Starting...")
        self._set_buttons_state("disabled")

        def worker():
            try:
                total_files = sum(len(v) for v in uploaded.values()) + 1
                completed = 0
                def progress(msg):
                    nonlocal completed
                    self.root.after(0, lambda m=msg: self.status.set(m))
                    if "parsed:" in msg.lower() or "Extracted" in msg or "workbook created" in msg:
                        completed += 1
                        self.root.after(0, lambda p=min(99, completed / total_files * 100): self.progress.set(p))
                run_pipeline(self.afs_path.get(), uploaded, output, progress)
                self.root.after(0, lambda: self.progress.set(100))
                self.root.after(0, lambda: self.status.set("Completed successfully."))
                self.root.after(0, lambda: messagebox.showinfo("Completed", f"Excel workbook created:\n\n{output}"))
            except Exception as exc:
                self.root.after(0, lambda e=exc: messagebox.showerror("Processing error", str(e)))
                self.root.after(0, lambda: self.status.set("Processing failed. Check the error message."))
            finally:
                self.root.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_buttons_state(self, state):
        # Avoid traversing every widget; generating while file dialogs are open is not expected.
        pass


def main():
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.1)
    except Exception:
        pass
    BudgetAnalyserApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
