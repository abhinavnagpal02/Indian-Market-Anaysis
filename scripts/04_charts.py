"""
04_charts.py — static PNG charts for the written report / GitHub README.
(The interactive version of these lives in Tableau.)

Run:  python 04_charts.py   (after 02_analysis.py and 06_deep_dives.py)
"""

import matplotlib
matplotlib.use("Agg")            # draw to files, no screen needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from config import OUTPUT_DIR, CHART_DIR

CHART_DIR.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 9})
INDIA = "#E07B00"   # India highlighted in one colour, everyone else muted
# Fixed colour per foreign market, so a market keeps its colour on every chart.
MARKET_COLOUR = {"S&P 500": "#4C72B0", "FTSE 100": "#55A868", "DAX": "#8172B2",
                 "Nikkei 225": "#C44E52", "Shanghai Composite": "#64B5CD"}

daily = pd.read_csv(OUTPUT_DIR / "prices_daily.csv", parse_dates=["Date"])
summary = pd.read_csv(OUTPUT_DIR / "summary_metrics.csv")
pct = mtick.PercentFormatter(1.0)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHART_DIR / name)
    plt.close(fig)
    print("saved", name)


# 1. Growth of 100 in USD: Nifty vs the world --------------------------------
fig, ax = plt.subplots(figsize=(8, 4.2))
glob = daily[(daily["Group"] == "Global") | (daily["Ticker"] == "^NSEI")]
for name, g in glob.groupby("Name"):
    is_india = name == "Nifty 50"
    ax.plot(g["Date"], g["Index_100_USD"], label=name,
            color=INDIA if is_india else MARKET_COLOUR.get(name, "grey"),
            lw=2.4 if is_india else 1.2)
ax.axhline(100, color="grey", lw=0.8)
ax.set_title("Growth of 100 invested (in US dollars)")
ax.legend(ncol=3, fontsize=8, frameon=False)
save(fig, "01_growth_usd_vs_world.png")

# 2. CAGR local vs USD --------------------------------------------------------
s = summary[summary["Group"].isin(["India Broad", "India Size", "Global"])].sort_values("CAGR_USD")
fig, ax = plt.subplots(figsize=(7, 3.8))
y = range(len(s))
ax.barh([i + 0.2 for i in y], s["CAGR"], height=0.4, label="Local currency", color="#9DB4D6")
ax.barh([i - 0.2 for i in y], s["CAGR_USD"], height=0.4, label="In USD", color="#2F5C9A")
ax.set_yticks(list(y), s["Name"])
ax.xaxis.set_major_formatter(pct)
ax.set_title("Annual growth rate (CAGR): local currency vs USD")
ax.legend(frameon=False)
save(fig, "02_cagr_local_vs_usd.png")

# 3. Risk vs return scatter --------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4.5))
for _, r in summary.iterrows():
    c = INDIA if r["Country"] == "India" else "#4C72B0"
    ax.scatter(r["Annual_Volatility"], r["CAGR"], color=c, s=40)
    ax.annotate(r["Name"], (r["Annual_Volatility"], r["CAGR"]), fontsize=7,
                xytext=(4, 2), textcoords="offset points")
ax.xaxis.set_major_formatter(pct); ax.yaxis.set_major_formatter(pct)
ax.set_xlabel("Risk: annual volatility"); ax.set_ylabel("Return: CAGR (local)")
ax.set_title("Risk vs return (top-left is best)")
save(fig, "03_risk_return.png")

# 4. Nifty drawdown ----------------------------------------------------------
n = daily[daily["Ticker"] == "^NSEI"]
fig, ax = plt.subplots(figsize=(8, 3))
ax.fill_between(n["Date"], n["Drawdown"], 0, color="#C44E52", alpha=0.6)
ax.yaxis.set_major_formatter(pct)
ax.set_title("Nifty 50: % below its previous peak (drawdown)")
save(fig, "04_nifty_drawdown.png")

# 5. Sector performance -------------------------------------------------------
sec = summary[summary["Country"] == "India"].sort_values("CAGR")
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.barh(sec["Name"], sec["CAGR"],
        color=[INDIA if n in ("Nifty 50", "Sensex") else "#8C8C8C" for n in sec["Name"]])
ax.xaxis.set_major_formatter(pct)
ax.set_title("Indian sectors vs the market: CAGR")
save(fig, "05_sector_cagr.png")

# 6. Correlation heatmap -------------------------------------------------------
corr = pd.read_csv(OUTPUT_DIR / "correlations.csv").pivot(
    index="Index_A", columns="Index_B", values="Correlation")
order = ["Nifty 50", "Sensex", "S&P 500", "FTSE 100", "DAX", "Nikkei 225",
         "Shanghai Composite"]
order = [o for o in order if o in corr.index]
corr = corr.loc[order, order]
fig, ax = plt.subplots(figsize=(6, 5))
im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(order)), order, rotation=45, ha="right")
ax.set_yticks(range(len(order)), order)
for i in range(len(order)):
    for j in range(len(order)):
        val = corr.iloc[i, j]
        ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                color="white" if abs(val) > 0.6 else "black")   # readable on dark cells
ax.grid(False)
fig.colorbar(im, shrink=0.8)
ax.set_title("Weekly return correlation")
save(fig, "06_correlation_heatmap.png")

# 7. INR per USD ----------------------------------------------------------------
fx = pd.read_csv(OUTPUT_DIR / "fx_rates.csv", parse_dates=["Date"])
inr = fx[fx["Ticker"] == "INR=X"]
fig, ax = plt.subplots(figsize=(8, 3))
ax.plot(inr["Date"], inr["Rate"], color=INDIA)
ax.set_title("Rupees per US dollar (up = weaker rupee)")
save(fig, "07_inr_usd.png")

# 8. India VIX vs Nifty -------------------------------------------------------------
vix_path = OUTPUT_DIR / "vix_vs_nifty.csv"
if vix_path.exists():
    v = pd.read_csv(vix_path, parse_dates=["Date"])
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 4.5), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(v["Date"], v["Nifty"], color=INDIA)
    a1.set_title("Nifty 50 (top) and India VIX, the fear gauge (bottom)")
    a2.plot(v["Date"], v["India_VIX"], color="#C44E52", lw=1)
    save(fig, "08_vix_vs_nifty.png")

# 9. Rolling correlation with Nifty -------------------------------------------------
rc = pd.read_csv(OUTPUT_DIR / "rolling_correlation.csv", parse_dates=["Week"])
fig, ax = plt.subplots(figsize=(8, 3.6))
for name, colour in MARKET_COLOUR.items():
    g = rc[rc["Name"] == name]
    if len(g):
        ax.plot(g["Week"], g["Rolling_1Y_Corr_With_Nifty"], label=name,
                color=colour, lw=1.2)
ax.axhline(0, color="grey", lw=0.8)
ax.set_title("How closely each market moved with Nifty (rolling 1-year correlation)")
ax.legend(ncol=3, fontsize=8, frameon=False)
save(fig, "09_rolling_correlation.png")

# 10. RBI rate cycle ----------------------------------------------------------------
cyc = pd.read_csv(OUTPUT_DIR / "rate_cycle_returns.csv")
names = [n for n in ["Nifty 50", "Nifty Bank", "Nifty IT", "Nifty Midcap 50"]
         if n in set(cyc["Name"])]
phases = sorted(cyc["Phase"].unique())
fig, ax = plt.subplots(figsize=(8, 3.8))
w = 0.8 / len(names)
for i, n in enumerate(names):
    vals = [cyc[(cyc["Phase"] == p) & (cyc["Name"] == n)]["Annualised_Return"].sum()
            for p in phases]
    ax.bar([x + i * w for x in range(len(phases))], vals, width=w, label=n,
           color=[INDIA, "#2F5C9A", "#55A868", "#8172B2"][i])
ax.set_xticks([x + w * (len(names) - 1) / 2 for x in range(len(phases))], phases)
ax.yaxis.set_major_formatter(pct)
ax.set_title("Annualised return in each phase of the RBI rate cycle")
ax.legend(frameon=False, fontsize=8)
save(fig, "10_rate_cycle.png")
