"""
01b_download_extra.py — extra Indian series that 01_download_data.py doesn't get.

Why a second script? Yahoo Finance has no data for the Nifty Auto and Nifty
FMCG indices (or most other NSE sector indices), so this tries a list of
candidates and keeps whatever exists:
- ETFs that track Nifty Auto and Nifty FMCG (stand-ins for the indices)
- Nifty Midcap 50 (mid-sized companies)
- India VIX (the market's "fear gauge")

Run:  python 01b_download_extra.py   -> saves raw_prices_extra.csv
(02_analysis.py reads every raw_prices*.csv file in ../data/.)

In Oct 2026 only AUTOBEES.NS, AUTOIETF.NS, FMCGIETF.NS, ^NSEMDCP50 and
^INDIAVIX returned data; the rest said "possibly delisted".
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

START, END = "2021-10-01", "2026-10-06"
CANDIDATES = [
    "^CNXAUTO", "^CNXFMCG",
    "AUTOBEES.NS", "AUTOIETF.NS", "FMCGIETF.NS",
    "^CNXMETAL", "^CNXENERGY", "^CNXREALTY", "^CNXINFRA", "^CNXPSUBANK",
    "NIFTY_FIN_SERVICE.NS", "^CNXCONSUM",
    "^NSEMDCP50", "NIFTY_MIDCAP_100.NS", "^CNXSC", "^INDIAVIX",
]

if __name__ == "__main__":
    frames = []
    for t in CANDIDATES:
        try:
            df = yf.Ticker(t).history(start=START, end=END, auto_adjust=True)
        except Exception as e:          # one bad ticker shouldn't stop the rest
            print(t, "ERROR", e)
            continue
        if df.empty:
            print(t, "NO DATA")
            continue
        out = df["Close"].rename("Close").reset_index()
        out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")   # drop the timezone
        out["Ticker"] = t
        frames.append(out[["Date", "Ticker", "Close"]])
        print(t, len(out), "rows", out["Date"].iloc[0], "to", out["Date"].iloc[-1])

    here = Path(__file__).resolve().parent
    data_dir = here.parent / "data"
    target = (data_dir if data_dir.exists() else here) / "raw_prices_extra.csv"
    pd.concat(frames, ignore_index=True).to_csv(target, index=False)
    print("Saved", target)
