# Tableau dashboard

The interactive dashboard is `tableau/India_Market_Dashboard.twbx`: three
pages, 12 charts, built from the CSVs in `output/`.

## Open it

1. Install **Tableau Public** (free, public.tableau.com) or use Tableau Desktop.
2. In Tableau: **File > Open** and pick `tableau/India_Market_Dashboard.twbx`.
   The data is packed inside the file, so nothing else is needed.
3. The tabs along the bottom are the three dashboards. The single charts are
   hidden; right-click a dashboard tab > **Unhide All Sheets** to see them.
4. To publish: **File > Save to Tableau Public As** (free account). On the
   published page, keep **Show Sheets as Tabs** turned on, so visitors can move
   between the three dashboards. The data sources are already **extracts**,
   which Tableau Public requires: a live connection reads the CSV every time,
   while an extract is a fast snapshot in Tableau's own `.hyper` format.

If Tableau says it can't find a data file, click **Edit Connection** and pick
the CSV with the same name from `output/`.

### What is on each page

| Dashboard | Charts | Data file |
|---|---|---|
| India at a glance | Nifty 50 closing price · how far below its last peak · return in each calendar year · India VIX | `prices_daily`, `yearly_returns`, `india_vix` |
| India vs the world | Growth of 100 in US dollars · CAGR in three currencies · risk vs return · correlation heatmap | `prices_daily`, `tableau_cagr_by_currency`, `summary_metrics`, `correlations` |
| Inside India | Sector and size CAGR · return in each calendar year · RBI rate cycle · foreign investor flows | `summary_metrics`, `yearly_returns`, `rate_cycle_returns`, `fpi_flows` |

Each page has a title, a one-line finding computed from the data, and a
footnote with the caveats. India is orange on every chart.

### Viewing tip

Tableau starts every axis at zero, which squashes the Nifty price line into
the top of its chart. Right-click its vertical axis > **Edit Axis** > untick
**Include zero**.

### How the workbook is built

`scripts/07_build_tableau_workbook.py` writes the workbook. A `.twbx` is a
zip file: rename it to `.zip` to see `India_Market_Dashboard.twb`
(plain XML describing the data sources, charts and dashboards), a
`Data/Datasources/` folder with the CSVs, and a `Data/Extracts/` folder with
the same data as Tableau extracts.

- Each chart in the script's `SHEETS` list is exactly what you would drag in
  Tableau: what goes on Rows and Columns, the mark type (Line, Bar, Area,
  Square, Circle), what goes on Colour and Label, and the filters.
- `sum:CAGR` means SUM(CAGR) as a continuous (green) pill; `dim:Name` means
  Name as a discrete (blue) pill. Every mark is exactly one CSV row, so the
  SUM is just the value.
- One table is reshaped to "long" format first
  (`tableau_cagr_by_currency.csv`), because Tableau colours by a column:
  "local vs dollars vs rupees" has to be one column with three values, not
  three columns.
- Each CSV is also saved as a `.hyper` extract with Tableau's Hyper API
  (`pip install tableauhyperapi`), because Tableau Public only accepts
  extracts.
- Before saving, the script reopens the file and checks that every field,
  filter value and sheet name it refers to really exists, and that each
  extract has the same columns and row count as its CSV.
- `python run_all.py` reruns the analysis and rebuilds the workbook, so the
  dashboard stays in sync with the data.
