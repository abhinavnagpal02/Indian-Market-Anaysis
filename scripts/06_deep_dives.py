"""
06_deep_dives.py — the questions behind the headline numbers.

Run:  python 06_deep_dives.py   (after 02_analysis.py and 05_macro_data.py)

1. Rolling 1-year return and volatility: is the market speeding up or cooling?
2. Rolling 1-year correlation with foreign markets: is India "decoupling"?
3. Tail risk: how often are there big daily moves, and how bad is a bad day?
4. India VIX: does the fear gauge line up with Nifty's falls?
5. Interest-rate cycle: how did Nifty and Nifty Bank do while the RBI was
   hiking, pausing and cutting?
6. Fiscal-year returns next to GDP growth and inflation.
7. Seasonality: average return by calendar month (with a warning label).
8. Key events, with what the market actually did that day.
"""

import numpy as np
import pandas as pd

from config import OUTPUT_DIR, TRADING_DAYS

daily = pd.read_csv(OUTPUT_DIR / "prices_daily.csv", parse_dates=["Date"])
monthly = pd.read_csv(OUTPUT_DIR / "monthly_returns.csv", parse_dates=["Month"])
wide = daily.pivot(index="Date", columns="Name", values="Close").sort_index()
NIFTY = "Nifty 50"


# ---------------------------------------------------------------------------
# 1 + 2. Rolling metrics
# ---------------------------------------------------------------------------
def rolling_metrics():
    """Rolling = recompute the metric every day over the last 12 months.

    Rolling_1Y_Return on 1 Jan 2024 = return from 1 Jan 2023 to 1 Jan 2024.
    Rolling correlation uses 52 weeks of weekly returns (same reason as in
    02_analysis: weekly returns avoid the time-zone lag between markets).
    """
    rows = []
    for name in wide.columns:
        s = wide[name].dropna()
        ret = s.pct_change()
        out = pd.DataFrame({
            "Date": s.index, "Name": name,
            "Rolling_1Y_Return": (s / s.shift(TRADING_DAYS) - 1).values,
            "Rolling_1Y_Vol": (ret.rolling(TRADING_DAYS).std()
                               * np.sqrt(TRADING_DAYS)).values,
        })
        rows.append(out)
    roll = pd.concat(rows, ignore_index=True)

    weekly = wide.resample("W-FRI").last().pct_change(fill_method=None)
    corr_rows = []
    for name in weekly.columns:
        if name == NIFTY:
            continue
        c = weekly[NIFTY].rolling(52, min_periods=40).corr(weekly[name])
        corr_rows.append(pd.DataFrame({"Week": c.index, "Name": name,
                                       "Rolling_1Y_Corr_With_Nifty": c.values}))
    corr = pd.concat(corr_rows, ignore_index=True).dropna()
    return roll.dropna(subset=["Rolling_1Y_Return"]), corr


# ---------------------------------------------------------------------------
# 3. Tail risk
# ---------------------------------------------------------------------------
def tail_risk():
    """Big-move statistics per index.

    - Skew < 0: crashes are bigger than rallies.
    - Excess kurtosis > 0: extreme days happen more often than a bell curve
      predicts ("fat tails").
    - VaR 95%: on 19 days out of 20, the daily loss was smaller than this.
    - CVaR 95%: the average loss on the remaining 1-in-20 worst days.
    """
    rows = []
    for name, g in daily.groupby("Name"):
        r = g["Daily_Return"].dropna()
        var95 = r.quantile(0.05)
        rows.append({
            "Name": name, "Group": g["Group"].iloc[0],
            "Skew": r.skew(), "Excess_Kurtosis": r.kurt(),
            "Days_Abs_Move_Over_2pct": int((r.abs() > 0.02).sum()),
            "Pct_Days_Abs_Move_Over_2pct": (r.abs() > 0.02).mean(),
            "VaR_95_Daily": var95, "CVaR_95_Daily": r[r <= var95].mean(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. India VIX
# ---------------------------------------------------------------------------
def vix_analysis():
    """Join India VIX to Nifty and describe how they relate.

    'Next 3 months return' asks: when fear was highest (top 10% of VIX days),
    what did Nifty do over the following ~63 trading days? With five years of
    data this is a description of what happened, not a trading rule.
    """
    path = OUTPUT_DIR / "india_vix.csv"
    if not path.exists():
        return None, None
    vix = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")["India_VIX"]
    n = wide[NIFTY].dropna()
    df = pd.concat([n.rename("Nifty"), vix], axis=1, join="inner").dropna()
    df["Nifty_Return"] = df["Nifty"].pct_change()
    df["VIX_Change"] = df["India_VIX"].pct_change()
    df["Nifty_Next_3M_Return"] = df["Nifty"].shift(-63) / df["Nifty"] - 1
    top = df["India_VIX"] >= df["India_VIX"].quantile(0.9)

    summary = pd.DataFrame([{
        "VIX_Average": df["India_VIX"].mean(),
        "VIX_Median": df["India_VIX"].median(),
        "VIX_Max": df["India_VIX"].max(),
        "VIX_Max_Date": df["India_VIX"].idxmax().date(),
        "VIX_Min": df["India_VIX"].min(),
        "VIX_Min_Date": df["India_VIX"].idxmin().date(),
        "Corr_VIX_Change_vs_Nifty_Return": df["VIX_Change"].corr(df["Nifty_Return"]),
        "Top10pct_VIX_Threshold": df["India_VIX"].quantile(0.9),
        "Avg_Next_3M_Return_When_VIX_Top10pct": df.loc[top, "Nifty_Next_3M_Return"].mean(),
        "Avg_Next_3M_Return_Other_Days": df.loc[~top, "Nifty_Next_3M_Return"].mean(),
    }])
    table = df.reset_index()[["Date", "Nifty", "India_VIX", "Nifty_Return", "VIX_Change"]]
    return summary, table


# ---------------------------------------------------------------------------
# 5. RBI rate cycle
# ---------------------------------------------------------------------------
def rate_cycle_returns():
    """Return of each Indian index during each phase of the RBI cycle.

    Phases come from the repo-rate decisions in repo_rate.csv:
    - Hold at 4%: start of data to the first hike (4 May 2022)
    - Hiking: 4 May 2022 to the last hike (8 Feb 2023), 4.00% -> 6.50%
    - Pause: 8 Feb 2023 to the first cut (7 Feb 2025)
    - Cutting: 7 Feb 2025 to the end of the data
    """
    phases = [("1. Hold at 4%", "2021-10-01", "2022-05-04"),
              ("2. Hiking", "2022-05-04", "2023-02-08"),
              ("3. Pause at 6.5%", "2023-02-08", "2025-02-07"),
              ("4. Cutting", "2025-02-07", str(wide.index[-1].date()))]
    india = daily.loc[daily["Country"] == "India", "Name"].unique()
    rows = []
    for phase, start, end in phases:
        for name in india:
            s = wide[name].dropna().loc[start:end]
            if len(s) < 20:
                continue
            years = (s.index[-1] - s.index[0]).days / 365.25
            total = s.iloc[-1] / s.iloc[0] - 1
            rows.append({"Phase": phase, "Start": start, "End": end, "Name": name,
                         "Return": total,
                         "Annualised_Return": (1 + total) ** (1 / years) - 1})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6. Fiscal-year returns next to the economy
# ---------------------------------------------------------------------------
def fiscal_year_vs_macro():
    """India's fiscal year runs April to March, so FY2023-24 = Apr 2023-Mar 2024.
    We line up Nifty's return in each fiscal year with GDP growth and CPI
    inflation for the same year. FY2021-22 only has data from October."""
    n = wide[NIFTY].dropna()
    macro = pd.read_csv(OUTPUT_DIR / "macro_india.csv")
    rows = []
    for fy in macro["Fiscal_Year"]:
        y0 = int(fy[2:6])                      # "FY2023-24" -> 2023
        s = n.loc[f"{y0}-04-01":f"{y0 + 1}-03-31"]
        if s.empty:
            continue
        before = n.loc[:f"{y0}-03-31"]
        base = before.iloc[-1] if len(before) else s.iloc[0]
        rows.append({"Fiscal_Year": fy, "Nifty_Return": s.iloc[-1] / base - 1,
                     "Partial": len(before) == 0})
    return macro.merge(pd.DataFrame(rows), on="Fiscal_Year", how="left")


# ---------------------------------------------------------------------------
# 7. Seasonality
# ---------------------------------------------------------------------------
def seasonality():
    """Average return per calendar month. Only ~5 observations per month, so
    a 'best month' here is mostly noise, and the README says so."""
    # Drop each index's first and last month: both are partial months.
    first = monthly.groupby("Name")["Month"].transform("min")
    last = monthly.groupby("Name")["Month"].transform("max")
    m = monthly[(monthly["Month"] > first) & (monthly["Month"] < last)]
    out = (m.groupby(["Name", "Month_Name"])["Return"]
             .agg(Avg_Return="mean", Pct_Positive=lambda x: (x > 0).mean(),
                  Years="count").reset_index())
    order = {mn: i for i, mn in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
    out["Month_Num"] = out["Month_Name"].map(order)
    return out.sort_values(["Name", "Month_Num"])


# ---------------------------------------------------------------------------
# 8. Events
# ---------------------------------------------------------------------------
EVENTS = [
    ("2022-02-24", "Global", "Russia invades Ukraine", "Geopolitics"),
    ("2022-03-16", "USA", "US Fed makes its first rate hike of the cycle", "Rates"),
    ("2022-05-04", "India", "RBI surprise hike: rate cycle begins (4.00% to 4.40%)", "Rates"),
    ("2023-01-25", "India", "Sell-off after Hindenburg report on Adani Group (published 24 Jan after Indian close)", "Corporate"),
    ("2023-02-08", "India", "RBI's last hike, repo at 6.50%", "Rates"),
    ("2023-03-10", "USA", "Silicon Valley Bank collapses", "Banking"),
    ("2024-06-04", "India", "General election results day", "Politics"),
    ("2024-08-05", "Japan", "Yen carry-trade unwind: global sell-off", "Global"),
    ("2024-09-24", "China", "China announces large stimulus package", "Policy"),
    ("2025-02-07", "India", "RBI's first rate cut in nearly 5 years (6.25%)", "Rates"),
    ("2025-04-03", "USA", "Markets react to US 'reciprocal' tariffs (announced 2 Apr after US close)", "Trade"),
    ("2025-04-07", "Global", "Tariff sell-off hits markets worldwide", "Trade"),
    ("2025-04-09", "USA", "US pauses most new tariffs for 90 days", "Trade"),
    ("2025-05-07", "India", "Operation Sindoor (India-Pakistan conflict)", "Geopolitics"),
    ("2025-05-12", "India", "Markets rally after India-Pakistan ceasefire", "Geopolitics"),
    ("2025-06-06", "India", "RBI cuts repo by 50 bps to 5.50%", "Rates"),
    ("2025-08-27", "India", "US 50% tariff on Indian goods takes effect", "Trade"),
    ("2025-09-22", "India", "GST rate cuts take effect", "Policy"),
    ("2025-12-05", "India", "RBI cuts repo to 5.25%", "Rates"),
    ("2026-02-04", "India IT", "Nifty IT's worst day in six years after Anthropic's Claude Cowork plugins raise AI-disruption fears", "Technology"),
    ("2026-02-24", "India IT", "AI-disruption fears hit IT stocks (Anthropic's legacy-code claims)", "Technology"),
    ("2026-03-02", "Global", "US/Israel-Iran war: oil supply shock begins (approx. date)", "Geopolitics"),
    ("2026-03-31", "Global", "Brent crude peaks at $118 a barrel", "Commodities"),
    ("2026-04-08", "India", "US-Iran ceasefire: Sensex's biggest one-day gain in 6 years", "Geopolitics"),
]
MARKET_INDEX = {"India": NIFTY, "USA": "S&P 500", "Japan": "Nikkei 225",
                "China": "Shanghai Composite", "Global": NIFTY,
                "India IT": "Nifty IT"}


def events_table():
    """Each event with the actual move in the most relevant index that day
    (or the next trading day if the market was shut), so the narrative is
    checked against the data rather than taken on trust."""
    rows = []
    for date, market, event, cat in EVENTS:
        name = MARKET_INDEX[market]
        r = daily[daily["Name"] == name].set_index("Date")["Daily_Return"]
        after = r.loc[date:]
        if after.empty:
            continue
        rows.append({"Date": date, "Market": market, "Event": event,
                     "Category": cat, "Index": name,
                     "Trading_Day_Used": after.index[0].date(),
                     "Index_Return_That_Day": after.iloc[0],
                     "Nifty_Return_That_Day":
                         daily[daily["Name"] == NIFTY].set_index("Date")
                         ["Daily_Return"].loc[date:].iloc[0]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    roll, roll_corr = rolling_metrics()
    tails = tail_risk()
    vix_summary, vix_table = vix_analysis()
    cycle = rate_cycle_returns()
    fy = fiscal_year_vs_macro()
    season = seasonality()
    events = events_table()

    roll.to_csv(OUTPUT_DIR / "rolling_metrics.csv", index=False)
    roll_corr.to_csv(OUTPUT_DIR / "rolling_correlation.csv", index=False)
    tails.to_csv(OUTPUT_DIR / "tail_risk.csv", index=False)
    cycle.to_csv(OUTPUT_DIR / "rate_cycle_returns.csv", index=False)
    fy.to_csv(OUTPUT_DIR / "fiscal_year_vs_macro.csv", index=False)
    season.to_csv(OUTPUT_DIR / "seasonality.csv", index=False)
    events.to_csv(OUTPUT_DIR / "market_events.csv", index=False)
    if vix_summary is not None:
        vix_summary.to_csv(OUTPUT_DIR / "vix_summary.csv", index=False)
        vix_table.to_csv(OUTPUT_DIR / "vix_vs_nifty.csv", index=False)

    pd.set_option("display.width", 200)
    print(tails.round(4).to_string(index=False))
    print(cycle[cycle["Name"].isin([NIFTY, "Nifty Bank"])].round(4).to_string(index=False))
    print(fy.round(4).to_string(index=False))
    if vix_summary is not None:
        print(vix_summary.T)
    print(events.round(4).to_string(index=False))
