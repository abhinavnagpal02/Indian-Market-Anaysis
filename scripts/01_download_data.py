"""
01_download_data.py — download 5 years of daily closing prices from Yahoo Finance.

This file is deliberately standalone (it does not need config.py) so you can
copy just this one file to any laptop with Python and run:

    pip install yfinance pandas
    python 01_download_data.py

It saves raw_prices.csv next to itself (or in ../data/ if that folder exists).

Output format is "long" (one row per date per ticker):
    Date, Ticker, Close
Long format is what Tableau and pandas both like best: adding a new index
adds rows, not columns.
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

START_DATE = "2021-10-01"
END_DATE = "2026-10-06"   # exclusive

TICKERS = [
    # India: broad market and sectors
    "^NSEI", "^BSESN", "^NSEBANK", "^CNXIT", "^CNXPHARMA", "^CNXAUTO", "^CNXFMCG",
    # Other major economies: US, China, Japan, UK, Germany
    "^GSPC", "000001.SS", "^N225", "^FTSE", "^GDAXI",
    # Exchange rates (to convert everything into USD)
    "INR=X", "CNY=X", "JPY=X", "GBPUSD=X", "EURUSD=X",
]


def download_all(tickers, start, end):
    """Download daily closes for every ticker and return one long table."""
    frames = []
    for ticker in tickers:
        # auto_adjust=True gives prices adjusted for splits/dividends where
        # Yahoo has them. For indices this changes nothing, but it's good habit.
        df = yf.download(ticker, start=start, end=end,
                         auto_adjust=True, progress=False)
        if df.empty:
            print(f"  WARNING: no data for {ticker}")
            continue
        # Newer yfinance returns two-level column names; keep just 'Close'.
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        out = close.rename("Close").reset_index()
        out["Ticker"] = ticker
        frames.append(out[["Date", "Ticker", "Close"]])
        print(f"  {ticker:<10} {len(out):>5} rows  "
              f"{out['Date'].min().date()} to {out['Date'].max().date()}")
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print("Downloading from Yahoo Finance...")
    prices = download_all(TICKERS, START_DATE, END_DATE)

    here = Path(__file__).resolve().parent
    data_dir = here.parent / "data"
    target = (data_dir if data_dir.exists() else here) / "raw_prices.csv"
    prices.to_csv(target, index=False)
    print(f"\nSaved {len(prices):,} rows to {target}")
