"""
02_analysis.py — turn raw prices into every metric the project reports,
and save them as tidy, Tableau-ready CSVs in ../output/.

Run:  python 02_analysis.py

Each section below answers one question. The comment above each
function explains what it measures and why.
"""

import numpy as np
import pandas as pd

from config import (DATA_DIR, OUTPUT_DIR, INDICES, FX, RISK_FREE,
                    TRADING_DAYS, VIX_TICKER)

OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Load and clean
# ---------------------------------------------------------------------------
def load_prices():
    """Read every raw_prices*.csv file and split it into index prices,
    FX rates and India VIX.

    Cleaning steps:
    - parse dates as plain calendar dates (no timezone)
    - drop rows with missing or zero prices (bad ticks)
    - drop duplicate (Date, Ticker) rows
    - keep one series per index name (see pick_one_per_name)
    """
    files = sorted(DATA_DIR.glob("raw_prices*.csv"))
    raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    # Keep just YYYY-MM-DD: each market's own local trading date, no timezone shifts.
    raw["Date"] = pd.to_datetime(raw["Date"].astype(str).str[:10])
    raw = raw.dropna(subset=["Close"])
    raw = raw[raw["Close"] > 0]
    raw = raw.drop_duplicates(subset=["Date", "Ticker"], keep="last")

    missing = sorted(set(INDICES) - set(raw["Ticker"]))
    if missing:
        print("Not in the downloaded data (skipped):", ", ".join(missing))

    idx = pick_one_per_name(raw[raw["Ticker"].isin(INDICES)].copy())
    fx = remove_fx_spikes(raw[raw["Ticker"].isin(FX)].copy())
    vix = raw[raw["Ticker"] == VIX_TICKER].copy()
    return idx, fx, vix


def remove_fx_spikes(fx, jump=0.015):
    """Drop one-day bad ticks in the currency data.

    Yahoo sometimes records a wrong exchange rate for a single day: the rate
    jumps more than 1.5% and comes straight back the next day. Real
    currencies like the rupee almost never do that. Example from the data:
    INR=X 83.28 -> 85.19 -> 83.25 (2 Nov 2023). We delete such a day; the
    rate from the day before is then used in its place (forward fill).
    """
    keep = []
    for ticker, g in fx.groupby("Ticker"):
        g = g.sort_values("Date").copy()
        prev, nxt = g["Close"].shift(1), g["Close"].shift(-1)
        up, back = g["Close"] / prev - 1, nxt / g["Close"] - 1
        spike = (up.abs() > jump) & (back.abs() > jump) & (np.sign(up) != np.sign(back)) \
            & ((nxt / prev - 1).abs() < jump / 3)
        for d, v in g.loc[spike, ["Date", "Close"]].itertuples(index=False):
            print(f"FX bad tick removed: {ticker} {d.date()} ({v:.4f})")
        keep.append(g[~spike])
    return pd.concat(keep, ignore_index=True)


def pick_one_per_name(idx):
    """Avoid counting the same thing twice.

    - If two ETFs track the same index, keep the one with the longer history.
    - If the real index downloaded, drop its ETF stand-in.
    """
    info = idx.groupby("Ticker")["Date"].agg(["min", "count"])
    info["Name"] = [INDICES[t][0] for t in info.index]
    info = info.sort_values(["Name", "min", "count"], ascending=[True, True, False])
    keep = list(info.groupby("Name").head(1).index)

    real_names = {INDICES[t][0] for t in keep}
    keep = [t for t in keep
            if not (INDICES[t][0].endswith(" (ETF)")
                    and INDICES[t][0].replace(" (ETF)", "") in real_names)]
    dropped = sorted(set(info.index) - set(keep))
    if dropped:
        print("Duplicates dropped:", ", ".join(dropped))
    return idx[idx["Ticker"].isin(keep)]


def fx_to_usd_table(fx):
    """Build one table: Date x Currency -> how many USD one unit is worth.

    Example: if INR=X is 83.0 (83 rupees per dollar), one rupee = 1/83 USD.
    FX trades on different days from stock markets, so we fill gaps forward
    (use the last known rate) when we join it to index dates later.
    """
    wide = fx.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    usd = pd.DataFrame(index=wide.index)
    for ticker, (ccy, kind) in FX.items():
        if ticker not in wide:
            continue
        usd[ccy] = 1 / wide[ticker] if kind == "per_usd" else wide[ticker]
    usd["USD"] = 1.0
    return usd.ffill()


# ---------------------------------------------------------------------------
# 2. Daily table (the main Tableau source)
# ---------------------------------------------------------------------------
def build_daily(idx, usd_rates):
    """One row per index per trading day, with every daily-level field.

    - Index_100: price rebased so the first day = 100. Lets you plot
      Nifty (25,000) and FTSE (8,000) on one chart and compare growth.
    - Close_USD: price converted to dollars (fair cross-country comparison).
    - Close_INR: price converted to rupees: what an Indian investor who
      bought the foreign index actually earned, currency move included.
    - Daily_Return: % change from the previous trading day.
    - Drawdown: % below the highest price seen so far (0 = at a new high).
    - Rolling_Vol_60d: volatility of the last 60 days, annualised.
    """
    rows = []
    for ticker, g in idx.groupby("Ticker"):
        name, country, group, ccy = INDICES[ticker]
        g = g.sort_values("Date").set_index("Date")

        # Attach the FX rate valid on each date (last known rate, "as of").
        all_dates = usd_rates.index.union(g.index)
        rate = usd_rates[ccy].reindex(all_dates).ffill()
        g["Close_USD"] = g["Close"] * rate.reindex(g.index)
        # usd_rates["INR"] is USD per rupee, so dividing USD by it gives rupees.
        inr = usd_rates["INR"].reindex(all_dates).ffill()
        g["Close_INR"] = g["Close_USD"] / inr.reindex(g.index)

        g["Index_100"] = g["Close"] / g["Close"].iloc[0] * 100
        g["Index_100_USD"] = g["Close_USD"] / g["Close_USD"].iloc[0] * 100
        g["Index_100_INR"] = g["Close_INR"] / g["Close_INR"].iloc[0] * 100
        g["Daily_Return"] = g["Close"].pct_change()
        g["Drawdown"] = g["Close"] / g["Close"].cummax() - 1
        g["Rolling_Vol_60d"] = (g["Daily_Return"].rolling(60).std()
                                * np.sqrt(TRADING_DAYS))
        g["Name"], g["Country"], g["Group"], g["Currency"] = name, country, group, ccy
        rows.append(g.reset_index())

    daily = pd.concat(rows, ignore_index=True)
    cols = ["Date", "Ticker", "Name", "Country", "Group", "Currency", "Close",
            "Close_USD", "Close_INR", "Index_100", "Index_100_USD",
            "Index_100_INR", "Daily_Return", "Drawdown", "Rolling_Vol_60d"]
    return daily[cols]


# ---------------------------------------------------------------------------
# 3. Summary metrics: one row per index
# ---------------------------------------------------------------------------
def cagr(first, last, years):
    """Compound Annual Growth Rate: the steady yearly return that would turn
    `first` into `last` over `years`. Example: 100 -> 150 in 5 years
    gives (150/100)^(1/5) - 1 = 8.4% a year."""
    return (last / first) ** (1 / years) - 1


def drawdown_details(close):
    """Worst peak-to-trough fall, when it happened, and when it recovered."""
    peak = close.cummax()
    dd = close / peak - 1
    trough_date = dd.idxmin()
    peak_date = close.loc[:trough_date].idxmax()
    after = close.loc[trough_date:]
    recovered = after[after >= close.loc[peak_date]]
    recovery_date = recovered.index[0] if len(recovered) else pd.NaT
    return dd.min(), peak_date, trough_date, recovery_date


def build_summary(daily):
    """Return, risk and risk-adjusted metrics per index.

    Sharpe ratio = (average annual return - risk-free rate) / volatility.
    It answers: "how much extra return did I get per unit of risk taken?"
    Above 1 is very good, 0.5-1 decent, below 0 means a bank deposit won.

    "Average annual return" here is the arithmetic average daily return x 252,
    the textbook definition. It is higher than CAGR by roughly half the
    variance (Nifty: about 6.1% vs 5.2%), which is why Nifty's Sharpe comes
    out at +0.01 even though its CAGR (5.2%) is below the 6% T-bill rate.
    Using CAGR instead would give -0.06. Either way: about zero.
    """
    nifty = daily[daily["Ticker"] == "^NSEI"].set_index("Date")["Daily_Return"]
    out = []
    for ticker, g in daily.groupby("Ticker"):
        g = g.set_index("Date").sort_index()
        name, country, group, ccy = INDICES[ticker]
        years = (g.index[-1] - g.index[0]).days / 365.25
        r = g["Daily_Return"].dropna()

        ann_ret = r.mean() * TRADING_DAYS              # arithmetic, annualised
        ann_vol = r.std() * np.sqrt(TRADING_DAYS)
        # Volatility for a dollar investor (index move + currency move).
        ann_vol_usd = g["Close_USD"].pct_change().std() * np.sqrt(TRADING_DAYS)
        rf = RISK_FREE[ccy]
        sharpe = (ann_ret - rf) / ann_vol
        # Sortino only punishes downside moves (investors don't mind upside).
        downside = r[r < 0].std() * np.sqrt(TRADING_DAYS)
        sortino = (ann_ret - rf) / downside

        mdd, peak_d, trough_d, rec_d = drawdown_details(g["Close"])

        # Beta vs Nifty 50: if Nifty moves 1%, this index moves beta %.
        # Only meaningful for Indian indices (same trading days).
        beta = np.nan
        if country == "India":
            both = pd.concat([r, nifty], axis=1, join="inner").dropna()
            both.columns = ["x", "m"]
            beta = both["x"].cov(both["m"]) / both["m"].var()

        monthly = g["Close"].resample("ME").last().pct_change().dropna()

        out.append({
            "Ticker": ticker, "Name": name, "Country": country, "Group": group,
            "Currency": ccy,
            "Start_Date": g.index[0].date(), "End_Date": g.index[-1].date(),
            "Start_Price": g["Close"].iloc[0], "End_Price": g["Close"].iloc[-1],
            "Total_Return": g["Close"].iloc[-1] / g["Close"].iloc[0] - 1,
            "CAGR": cagr(g["Close"].iloc[0], g["Close"].iloc[-1], years),
            "CAGR_USD": cagr(g["Close_USD"].iloc[0], g["Close_USD"].iloc[-1], years),
            "CAGR_INR": cagr(g["Close_INR"].iloc[0], g["Close_INR"].iloc[-1], years),
            "Annual_Volatility": ann_vol, "Annual_Volatility_USD": ann_vol_usd,
            "Sharpe": sharpe, "Sortino": sortino, "Risk_Free_Used": rf,
            "Max_Drawdown": mdd, "MDD_Peak_Date": peak_d.date(),
            "MDD_Trough_Date": trough_d.date(),
            "MDD_Recovery_Date": rec_d.date() if pd.notna(rec_d) else None,
            "Beta_vs_Nifty": beta,
            "Best_Day": r.max(), "Best_Day_Date": r.idxmax().date(),
            "Worst_Day": r.min(), "Worst_Day_Date": r.idxmin().date(),
            "Pct_Positive_Days": (r > 0).mean(),
            "Pct_Positive_Months": (monthly > 0).mean(),
        })
    return pd.DataFrame(out).sort_values(["Group", "CAGR"], ascending=[True, False])


# ---------------------------------------------------------------------------
# 4. Calendar-year and monthly returns
# ---------------------------------------------------------------------------
def build_period_returns(daily):
    """Return per calendar year (local, USD and INR) and per month (local).

    The first and last year of each series are partial (2021 covers only
    Oct-Dec, 2026 only Jan to early Oct), so they are labelled
    'Partial_Year' — don't compare them to full years directly.
    """
    yearly, monthly = [], []
    for ticker, g in daily.groupby("Ticker"):
        g = g.set_index("Date").sort_index()
        name, country, group, _ = INDICES[ticker]
        partial = (g.index[0].year, g.index[-1].year)
        for col, label in [("Close", "Local"), ("Close_USD", "USD"),
                           ("Close_INR", "INR")]:
            # Use the previous year's last close as the base, so each year's
            # return covers the full year (not first-trading-day to last).
            ends = g[col].resample("YE").last()
            base = ends.shift(1)
            base.iloc[0] = g[col].iloc[0]
            for date, end_val in ends.items():
                yearly.append({"Ticker": ticker, "Name": name, "Country": country,
                               "Group": group, "Year": date.year,
                               "Currency_Basis": label,
                               "Return": end_val / base.loc[date] - 1,
                               "Partial_Year": date.year in partial})
        m = g["Close"].resample("ME").last()
        m_ret = m.pct_change()
        m_ret.iloc[0] = m.iloc[0] / g["Close"].iloc[0] - 1
        for date, ret in m_ret.items():
            monthly.append({"Ticker": ticker, "Name": name, "Country": country,
                            "Group": group, "Month": date.strftime("%Y-%m-01"),
                            "Year": date.year, "Month_Name": date.strftime("%b"),
                            "Return": ret})
    return pd.DataFrame(yearly), pd.DataFrame(monthly)


# ---------------------------------------------------------------------------
# 5. Correlations between markets
# ---------------------------------------------------------------------------
def build_correlations(daily):
    """How closely do markets move together? (+1 = in lockstep, 0 = unrelated)

    We use WEEKLY returns, not daily. Reason: Asian markets close before the
    US opens, so a US fall on Monday shows up in India on Tuesday. Daily
    correlation would wrongly look low; weekly smooths out the time-zone lag.
    """
    wide = daily.pivot(index="Date", columns="Name", values="Close")
    weekly = wide.resample("W-FRI").last().pct_change(fill_method=None).dropna(how="all")
    corr = weekly.corr()
    corr.index.name, corr.columns.name = "Index_A", "Index_B"
    long = corr.stack().rename("Correlation").reset_index()
    return long, corr


# ---------------------------------------------------------------------------
# 6. Biggest Nifty falls (drawdown episodes)
# ---------------------------------------------------------------------------
def build_drawdown_episodes(daily, ticker="^NSEI", threshold=-0.05):
    """List every Nifty fall of 5%+ from a peak, with dates and depth.

    An episode starts when the price drops below its running high and ends
    when it gets back to that high (recovery).
    """
    g = daily[daily["Ticker"] == ticker].set_index("Date")["Close"].sort_index()
    peak = g.cummax()
    dd = g / peak - 1
    episodes, in_dd, start = [], False, None
    for date, val in dd.items():
        if val < 0 and not in_dd:
            in_dd, start = True, date
        elif val == 0 and in_dd:
            seg = dd.loc[start:date]
            episodes.append((start, seg.idxmin(), date, seg.min()))
            in_dd = False
    if in_dd:
        seg = dd.loc[start:]
        episodes.append((start, seg.idxmin(), pd.NaT, seg.min()))

    rows = []
    for start, trough, end, depth in episodes:
        if depth > threshold:
            continue
        peak_date = g.loc[:start].index[-2] if g.index.get_loc(start) > 0 else start
        rows.append({
            "Ticker": ticker, "Peak_Date": peak_date.date(),
            "Trough_Date": trough.date(),
            "Recovery_Date": end.date() if pd.notna(end) else None,
            "Depth": depth,
            "Days_To_Trough": (trough - peak_date).days,
            "Days_To_Recover": (end - trough).days if pd.notna(end) else None,
        })
    return pd.DataFrame(rows).sort_values("Depth")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    idx, fx, vix = load_prices()
    usd = fx_to_usd_table(fx)

    daily = build_daily(idx, usd)
    summary = build_summary(daily)
    yearly, monthly = build_period_returns(daily)
    corr_long, corr_wide = build_correlations(daily)
    episodes = build_drawdown_episodes(daily)

    # FX table for Tableau (rupee story: INR per USD over time)
    fx_out = fx.rename(columns={"Close": "Rate"})

    daily.to_csv(OUTPUT_DIR / "prices_daily.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "summary_metrics.csv", index=False)
    yearly.to_csv(OUTPUT_DIR / "yearly_returns.csv", index=False)
    monthly.to_csv(OUTPUT_DIR / "monthly_returns.csv", index=False)
    corr_long.to_csv(OUTPUT_DIR / "correlations.csv", index=False)
    episodes.to_csv(OUTPUT_DIR / "nifty_drawdowns.csv", index=False)
    fx_out.to_csv(OUTPUT_DIR / "fx_rates.csv", index=False)
    if not vix.empty:
        vix.rename(columns={"Close": "India_VIX"})[["Date", "India_VIX"]] \
           .to_csv(OUTPUT_DIR / "india_vix.csv", index=False)

    pd.set_option("display.width", 200)
    print(summary[["Name", "CAGR", "CAGR_USD", "Annual_Volatility", "Sharpe",
                   "Max_Drawdown", "Beta_vs_Nifty"]].round(3).to_string(index=False))
    print("\nSaved CSVs to", OUTPUT_DIR)
