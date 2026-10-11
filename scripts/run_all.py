"""run_all.py — run every step in order (after raw_prices.csv exists)."""
import runpy
for step in ["02_analysis.py", "05_macro_data.py", "06_deep_dives.py",
             "04_charts.py", "07_build_tableau_workbook.py"]:
    print(f"\n===== {step} =====")
    runpy.run_path(step, run_name="__main__")
