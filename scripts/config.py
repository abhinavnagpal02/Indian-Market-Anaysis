"""
config.py — one place for every setting the project uses.

Why a separate file? If you want to change the date range or add an index,
you edit it here once instead of hunting through three scripts.
"""

from pathlib import Path

# ---- Folders --------------------------------------------------------------
# Path(__file__) is this file; .parent.parent is the project folder.
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"        # raw downloaded prices
OUTPUT_DIR = PROJECT_DIR / "output"    # Tableau-ready CSVs
CHART_DIR = PROJECT_DIR / "charts"     # PNG charts for the report

# ---- Period ---------------------------------------------------------------
START_DATE = "2021-10-01"
END_DATE = "2026-10-06"   # yfinance treats END as exclusive

# ---- What we download -----------------------------------------------------
# Each entry: Yahoo ticker -> (short name, country, group, currency)
INDICES = {
    # India, broad market
    "^NSEI":      ("Nifty 50",          "India",   "India Broad",  "INR"),
    "^BSESN":     ("Sensex",            "India",   "India Broad",  "INR"),
    # India, sectors (NSE sector indices)
    "^NSEBANK":   ("Nifty Bank",        "India",   "India Sector", "INR"),
    "^CNXIT":     ("Nifty IT",          "India",   "India Sector", "INR"),
    "^CNXPHARMA": ("Nifty Pharma",      "India",   "India Sector", "INR"),
    "^CNXAUTO":   ("Nifty Auto",        "India",   "India Sector", "INR"),
    "^CNXFMCG":   ("Nifty FMCG",        "India",   "India Sector", "INR"),
    "^CNXMETAL":  ("Nifty Metal",       "India",   "India Sector", "INR"),
    "^CNXENERGY": ("Nifty Energy",      "India",   "India Sector", "INR"),
    "^CNXREALTY": ("Nifty Realty",      "India",   "India Sector", "INR"),
    "^CNXINFRA":  ("Nifty Infra",       "India",   "India Sector", "INR"),
    "^CNXPSUBANK":("Nifty PSU Bank",    "India",   "India Sector", "INR"),
    "NIFTY_FIN_SERVICE.NS": ("Nifty Financial Services", "India", "India Sector", "INR"),
    "^CNXCONSUM": ("Nifty India Consumption", "India", "India Sector", "INR"),
    # ETF stand-ins, used only when Yahoo has no data for the index itself.
    # Caveat: an ETF price also includes reinvested dividends (minus fees),
    # so it runs ~1% a year ahead of the plain price index.
    "AUTOBEES.NS": ("Nifty Auto (ETF)", "India",   "India Sector", "INR"),
    "AUTOIETF.NS": ("Nifty Auto (ETF)", "India",   "India Sector", "INR"),
    "FMCGIETF.NS": ("Nifty FMCG (ETF)", "India",   "India Sector", "INR"),
    # India, by company size (mid and small companies vs the big 50)
    "^NSEMDCP50": ("Nifty Midcap 50",   "India",   "India Size",   "INR"),
    "NIFTY_MIDCAP_100.NS": ("Nifty Midcap 100", "India", "India Size", "INR"),
    "^CNXSC":     ("Nifty Smallcap 100","India",   "India Size",   "INR"),
    # Other major economies
    "^GSPC":      ("S&P 500",           "USA",     "Global",       "USD"),
    "000001.SS":  ("Shanghai Composite","China",   "Global",       "CNY"),
    "^N225":      ("Nikkei 225",        "Japan",   "Global",       "JPY"),
    "^FTSE":      ("FTSE 100",          "UK",      "Global",       "GBP"),
    "^GDAXI":     ("DAX",               "Germany", "Global",       "EUR"),
}

# India VIX: the market's "fear gauge" (expected volatility over the next
# 30 days, in %). It is not a price you can invest in, so it is kept out of
# the return calculations and saved as its own table.
VIX_TICKER = "^INDIAVIX"

# Exchange rates, used to convert every index into US dollars so that
# country comparisons are fair (a 10% gain in rupees is less if the rupee fell).
# Yahoo quotes "INR=X" as rupees per 1 USD, "GBPUSD=X" as USD per 1 GBP, etc.
FX = {
    "INR=X":    ("INR", "per_usd"),   # 1 USD = x INR  -> divide to get USD
    "CNY=X":    ("CNY", "per_usd"),
    "JPY=X":    ("JPY", "per_usd"),
    "GBPUSD=X": ("GBP", "usd_per"),   # 1 GBP = x USD  -> multiply to get USD
    "EURUSD=X": ("EUR", "usd_per"),
}

# ---- Risk-free rates for the Sharpe ratio --------------------------------
# Rough average short-term government rate over Oct 2021 - Oct 2026 in each
# currency (annual, decimal). These are approximations; the Sharpe ratio is
# not very sensitive to small changes here. Edit if you find better numbers.
RISK_FREE = {
    "INR": 0.060,  # India 91-day T-bill averaged roughly 6%
    "USD": 0.035,  # US T-bill: ~0% in 2021, ~5% in 2023-24
    "CNY": 0.018,
    "JPY": 0.002,
    "GBP": 0.033,
    "EUR": 0.020,
}

TRADING_DAYS = 252   # trading days in a year, used to annualise
