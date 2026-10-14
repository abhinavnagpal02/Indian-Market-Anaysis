# Indian Stock Market: 5 Years in Review (Oct 2021 to Oct 2026)

How did Indian equities perform over the last five years, what drove them,
and how did they compare with the US, China, Japan, the UK and Germany?

Python (pandas, numpy, matplotlib) for the analysis, Tableau for the
dashboard. Daily data from 1 Oct 2021 to 5 Oct 2026 for 11 indices, 2 index
ETFs and 5 currencies, plus India's GDP, inflation, repo rate and foreign
investor flows.

**Interactive dashboard:** [India Market Dashboard on Tableau Public](https://public.tableau.com/views/India_Market_Dashboard/Indiaataglance)
(three pages: India at a glance, India vs the world, Inside India). The
workbook is also in `tableau/India_Market_Dashboard.twbx`.

## Key findings

1. **Nifty 50 grew 28.7% in five years, 5.2% a year.** That is slightly
   below the roughly 6% a year a 91-day treasury bill paid, so investors got
   almost no reward for the extra risk (Sharpe ratio about 0).
2. **For a dollar investor, India returned nothing.** The rupee fell from
   74.3 to 96.3 per dollar, which wiped out the whole gain: Nifty's annual
   return in US dollars was -0.2%.
3. **India lagged every major market except China.** Annual growth in local
   currency: Nikkei 19.4%, S&P 500 12.3%, DAX 10.7%, FTSE 8.3%, Nifty 5.2%,
   Shanghai 1.4%.
4. **An Indian who invested abroad did much better.** ₹100 put into the
   S&P 500 in Oct 2021 became ₹231, against ₹129 in the Nifty 50.
5. **Smaller swings, lower returns.** Nifty was one of the least volatile of
   the six markets (13.8% a year), and its worst fall (-17%) was milder than
   the US, German, Japanese and Chinese ones (-25% to -27%).
6. **The gains came from mid caps and a few sectors.** Mid caps rose 105%,
   Auto (ETF, from Jan 2022) 134% and Pharma 79%, while IT lost 19%.
7. **2026 has been a bad year.** Nifty is down 13.7% year to date, hit by
   the oil shock, record foreign selling and a falling rupee.
8. **The result depends on when you measure.** Measured to the January 2026
   peak, Nifty grew 10.0% a year; measured to 5 Oct 2026, 5.2%.

## Charts

| | |
|---|---|
| ![Growth in USD](charts/01_growth_usd_vs_world.png) | ![CAGR local vs USD](charts/02_cagr_local_vs_usd.png) |
| ![Risk vs return](charts/03_risk_return.png) | ![Nifty drawdown](charts/04_nifty_drawdown.png) |
| ![Sectors](charts/05_sector_cagr.png) | ![Correlation](charts/06_correlation_heatmap.png) |
| ![Rupee](charts/07_inr_usd.png) | ![VIX](charts/08_vix_vs_nifty.png) |
| ![Rolling correlation](charts/09_rolling_correlation.png) | ![Rate cycle](charts/10_rate_cycle.png) |

## Method

1. **Data:** daily closing prices from Yahoo Finance (`yfinance`). Yahoo has
   no data for the Nifty Auto and FMCG indices, so ETFs that track them stand
   in (AUTOBEES from 24 Jan 2022, FMCGIETF).
2. **Cleaning:** removed missing, zero and duplicate prices, aligned each
   market on its own trading days, and matched currency rates "as of" each date.
3. **Metrics:** returns, CAGR (local, USD, INR), volatility, Sharpe, Sortino,
   drawdowns, beta, VaR/CVaR, weekly correlations and rolling 1-year metrics.
4. **Macro and events:** GDP, CPI, repo rate and foreign investor flows from
   official releases, plus 24 market events checked against the price data.

## Limitations

- Most indices are price-only (no dividends); the DAX includes dividends.
- Five years is a short window, and it ends inside a correction.
- Valuations (P/E), company earnings and domestic fund flows are not covered.

## How to run

```
pip install -r requirements.txt
cd scripts
python 01_download_data.py      # main indices and currencies -> data/raw_prices.csv
python 01b_download_extra.py    # ETF stand-ins, Midcap 50, India VIX -> data/raw_prices_extra.csv
python run_all.py               # analysis, macro, deep dives, charts, Tableau workbook
```

## Project structure

```
scripts/   01/01b download · 02 analysis · 04 charts · 05 macro · 06 deep dives · 07 Tableau workbook · config
data/      raw downloaded prices
output/    21 CSVs with the results
charts/    10 PNG charts
tableau/   India_Market_Dashboard.twbx
```

Data: Yahoo Finance, 1 Oct 2021 to 5 Oct 2026. Not investment advice.
