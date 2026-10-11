"""
05_macro_data.py — the economic backdrop (GDP, inflation, interest rates,
foreign investor flows), typed in from official releases.

Why typed in? These are a handful of yearly numbers; downloading them from
an API would be more code than data. Every number has a Source column so
you can check it. Run:  python 05_macro_data.py

Caveats:
- GDP: India rebased its GDP series to 2022-23 in 2026. FY25 and FY26 come
  from the new series; FY22-FY24 are from the older 2011-12 series.
- CPI: FY26 is the April-December 2025 average (full-year figure was not
  final when this was compiled). India's CPI was also rebased in 2026.
- FPI flows are calendar years (Jan-Dec) from NSDL; 2025 and 2026 are
  rounded figures from news reports, and 2026 runs only to 4 Sep 2026.
"""

import pandas as pd

from config import OUTPUT_DIR

macro = pd.DataFrame([
    # Fiscal_Year, GDP real growth %, CPI avg %, GDP source, CPI source
    ("FY2021-22", 9.7, 5.5, "MoSPI (2011-12 base)", "MoSPI / RBI"),
    ("FY2022-23", 7.6, 6.7, "MoSPI (2011-12 base)", "Economic Survey 2025-26"),
    ("FY2023-24", 9.2, 5.4, "MoSPI (2011-12 base)", "MoSPI / RBI"),
    ("FY2024-25", 7.1, 4.6, "MoSPI PE 5 Jun 2026 (2022-23 base)", "MoSPI / RBI"),
    ("FY2025-26", 7.7, 1.7, "MoSPI PE 5 Jun 2026 (2022-23 base)",
     "Economic Survey 2025-26 (Apr-Dec 2025 avg)"),
], columns=["Fiscal_Year", "GDP_Growth_Pct", "CPI_Inflation_Pct",
            "GDP_Source", "CPI_Source"])

fpi = pd.DataFrame([
    # Calendar year, net FPI equity flow in Rs crore (negative = selling)
    (2021, 25752, "NSDL via Upstox"),
    (2022, -121439, "NSDL via Upstox"),
    (2023, 171107, "NSDL via Upstox"),
    (2024, 427, "NSDL via Upstox"),
    (2025, -166000, "NSDL via PTI/Free Press Journal (approx., full year)"),
    (2026, -232000, "NSDL via PTI/Free Press Journal (approx., 1 Jan to 4 Sep 2026)"),
], columns=["Year", "FPI_Net_Equity_Rs_Crore", "Source"])

repo = pd.DataFrame([
    # Every RBI repo rate change in the period (rate in % after the change)
    ("2021-10-01", 4.00, "Starting level (unchanged since May 2020)"),
    ("2022-05-04", 4.40, "Hike +40 bps (unscheduled)"),
    ("2022-06-08", 4.90, "Hike +50 bps"),
    ("2022-08-05", 5.40, "Hike +50 bps"),
    ("2022-09-30", 5.90, "Hike +50 bps"),
    ("2022-12-07", 6.25, "Hike +35 bps"),
    ("2023-02-08", 6.50, "Hike +25 bps (last hike)"),
    ("2025-02-07", 6.25, "Cut -25 bps (first cut in ~5 years)"),
    ("2025-04-09", 6.00, "Cut -25 bps"),
    ("2025-06-06", 5.50, "Cut -50 bps"),
    ("2025-12-05", 5.25, "Cut -25 bps"),
], columns=["Date", "Repo_Rate_Pct", "Event"])
repo["Source"] = "RBI MPC statements"

macro.to_csv(OUTPUT_DIR / "macro_india.csv", index=False)
fpi.to_csv(OUTPUT_DIR / "fpi_flows.csv", index=False)
repo.to_csv(OUTPUT_DIR / "repo_rate.csv", index=False)
print("Saved macro_india.csv, fpi_flows.csv, repo_rate.csv")
