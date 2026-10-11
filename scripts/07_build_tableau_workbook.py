"""
07_build_tableau_workbook.py: build the Tableau dashboard from the CSVs.

Output: tableau/India_Market_Dashboard.twbx (open it in Tableau Public or Desktop)

What is a .twbx?
    A zip file with two things inside:
      India_Market_Dashboard.twb   plain XML that describes the data sources,
                                   the charts (Tableau calls them sheets) and
                                   the dashboards
      Data/Datasources/*.csv       copies of the CSVs the charts read
      Data/Extracts/*.hyper        the same data as Tableau extracts
    Rename it to .zip and you can look inside.

Why extracts?
    Tableau Public only saves workbooks whose data sources are extracts (a
    snapshot of the data in Tableau's own .hyper format). The script writes
    them with Tableau's Hyper API (pip install tableauhyperapi). Without that
    library it still builds the workbook, with live CSV connections only.

Why build it with code instead of clicking?
    1. It rebuilds itself when the data changes: rerun run_all.py.
    2. Every chart is written down in one readable list (SHEETS below), so you
       can say exactly what each chart shows and where its numbers come from.

How the script works:
    1. make_helper_tables()  reshapes two tables into the long shape Tableau likes
    2. DATASOURCES           one Tableau data source per CSV
    3. SHEETS                one entry per chart: rows, columns, colour, filters
    4. dashboards()          three pages: a title, the key finding, the charts
    5. write_extracts()      saves each CSV as a .hyper extract
    6. build_workbook()      turns those lists into Tableau's XML
    7. package()             zips the XML, the CSVs and the extracts into the .twbx
    8. validate()            reopens the file and checks every reference
"""

import io
import random
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import OUTPUT_DIR, PROJECT_DIR

try:   # Tableau's Hyper API writes the .hyper extracts (pip install tableauhyperapi)
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter,
                                 SqlType, TableDefinition, TableName, Telemetry)
except ImportError:
    HyperProcess = None

TABLEAU_DIR = PROJECT_DIR / "tableau"
WORKBOOK = "India_Market_Dashboard"
DATA_FOLDER = "Data/Datasources"     # where the CSVs sit inside the .twbx
EXTRACT_FOLDER = "Data/Extracts"     # where the .hyper extracts sit
USER_NS = "http://www.tableausoftware.com/xml/user"  # Tableau's extra XML namespace
ET.register_namespace("user", USER_NS)

# Dashboard size is a range, not fixed: Tableau shrinks the page to fit the
# window (down to the minimum) and stops growing at the maximum. The minimum
# fits a 14-inch laptop (1920x1080 at 150% scaling is 1280x720 usable, minus
# Tableau's menus and side panel), so a whole page shows without scrolling.
DASHBOARD_MIN_W, DASHBOARD_MIN_H = 800, 450
DASHBOARD_MAX_W, DASHBOARD_MAX_H = 1300, 880
INDIA = "#e07b00"                      # India is orange everywhere, as in charts/
GREY = "#9e9e9e"
MARKETS = ["Nifty 50", "S&P 500", "Shanghai Composite", "Nikkei 225",
           "FTSE 100", "DAX"]


# ---------------------------------------------------------------------------
# 1. Helper tables
# ---------------------------------------------------------------------------
def make_helper_tables():
    """Reshape two tables into long format: one row per bar or line point.

    Tableau colours by a column, so "local vs dollars vs rupees" has to be a
    column (Basis), not three separate columns.
    """
    summary = pd.read_csv(OUTPUT_DIR / "summary_metrics.csv")
    basis = {"CAGR": "In local currency", "CAGR_USD": "In US dollars",
             "CAGR_INR": "In rupees"}
    cagr = (summary.melt(id_vars=["Name", "Country", "Group"],
                         value_vars=list(basis), var_name="Basis",
                         value_name="Rate")
            .rename(columns={"Rate": "CAGR"}))
    cagr["Basis"] = cagr["Basis"].map(basis)
    cagr.to_csv(OUTPUT_DIR / "tableau_cagr_by_currency.csv", index=False)



# ---------------------------------------------------------------------------
# 2. Data sources and how each field should look
# ---------------------------------------------------------------------------
# key used in SHEETS -> (CSV in output/, name shown in Tableau's Data pane)
DATASOURCES = {
    "prices":   ("prices_daily.csv", "Daily prices"),
    "yearly":   ("yearly_returns.csv", "Yearly returns"),
    "vix":      ("india_vix.csv", "India VIX"),
    "summary":  ("summary_metrics.csv", "Summary metrics"),
    "cagr":     ("tableau_cagr_by_currency.csv", "CAGR by currency"),
    "corr":     ("correlations.csv", "Weekly correlations"),
    "rates":    ("rate_cycle_returns.csv", "Rate cycle returns"),
    "fpi":      ("fpi_flows.csv", "Foreign investor flows"),
}

DATE_FIELDS = {"Date", "Start", "End", "Start_Date", "End_Date",
               "MDD_Peak_Date", "MDD_Trough_Date", "MDD_Recovery_Date",
               "Best_Day_Date", "Worst_Day_Date"}
LABEL_NUMBERS = {"Year"}   # numbers used as labels: read as text, or Tableau shows "2,021"

# Tableau number formats: "p0.0%" = percentage with 1 decimal,
# "n#,##0;-#,##0" = number with thousands separators (positive;negative).
PERCENT_FIELDS = {"Total_Return", "CAGR", "CAGR_USD", "CAGR_INR",
                  "Annual_Volatility", "Annual_Volatility_USD", "Max_Drawdown", "Best_Day", "Worst_Day",
                  "Pct_Positive_Days", "Pct_Positive_Months", "Risk_Free_Used",
                  "Daily_Return", "Drawdown", "Rolling_Vol_60d", "Return",
                  "Annualised_Return", "MAPE", "Error_At_12_Months",
                  "Median_1Y_Return", "P10_1Y_Return", "P90_1Y_Return"}
WHOLE, TWO_DP = "n#,##0;-#,##0", "n#,##0.00;-#,##0.00"
FORMATS = {"Prob_Positive": "p0%", "Close": WHOLE, "Value": WHOLE,
           "FPI_Net_Equity_Rs_Crore": WHOLE, "Correlation": TWO_DP,
           "Sharpe": TWO_DP, "Sortino": TWO_DP, "Beta_vs_Nifty": TWO_DP}

# Friendlier field names (Tableau calls them captions).
CAPTIONS = {
    "Name": "Index", "Index_A": "Index", "Index_B": "Compared with",
    "Close": "Closing price", "Drawdown": "Below previous peak",
    "Index_100": "Growth of 100 (local currency)",
    "Index_100_USD": "Growth of 100 (US dollars)",
    "Index_100_INR": "Growth of 100 (rupees)",
    "Rolling_Vol_60d": "Volatility, last 60 days",
    "CAGR_USD": "CAGR in US dollars", "CAGR_INR": "CAGR in rupees",
    "Annual_Volatility": "Volatility (a year)",
    "Annual_Volatility_USD": "Volatility in US dollars (a year)",
    "Max_Drawdown": "Worst fall from a peak",
    "India_VIX": "India VIX", "Basis": "Measured in",
    "Phase": "RBI rate phase", "Annualised_Return": "Annualised return",
    "FPI_Net_Equity_Rs_Crore": "Net buying (Rs crore)",
    "Value": "Nifty 50 level", "MAPE": "Average error (MAPE)",
    "Error_At_12_Months": "Error after 12 months",
    "Median_1Y_Return": "Median 1-year return",
    "P10_1Y_Return": "Low case (10th percentile)",
    "P90_1Y_Return": "High case (90th percentile)",
    "Prob_Positive": "Chance of a gain",
}

# Fixed colours for some categories, so a market keeps its colour everywhere.
COLOURS = {
    "Name": {"Nifty 50": INDIA, "S&P 500": "#4c72b0", "FTSE 100": "#55a868",
             "DAX": "#8172b2", "Nikkei 225": "#c44e52",
             "Shanghai Composite": "#64b5cd", "Nifty Bank": "#2f4b7c"},
    "Group": {"India Broad": INDIA, "India Sector": "#4c72b0",
              "India Size": "#55a868", "Global": GREY},
    "Basis": {"In local currency": GREY, "In US dollars": "#4c72b0",
              "In rupees": INDIA},
}


class Source:
    """One CSV as a Tableau data source."""

    def __init__(self, key, file, caption, rng):
        self.key, self.file, self.caption = key, file, caption
        # Tableau gives every data source and connection a random internal
        # name. A fixed seed keeps the names the same on every rebuild.
        letters = "0123456789abcdefghijklmnopqrstuvwxyz"
        self.name = "federated." + "".join(rng.choice(letters) for _ in range(28))
        self.conn = "textscan." + "".join(rng.choice(letters) for _ in range(28))
        self.data = pd.read_csv(OUTPUT_DIR / file)
        self.types = {col: tableau_type(col, self.data[col]) for col in self.data.columns}
        self.hyper = file[:-4] + ".hyper"          # its extract file
        self.extract = HyperProcess is not None    # False if the Hyper API is missing

    def column_attrs(self, field):
        """The <column> tag: data type, role, display name and number format."""
        datatype = self.types[field]
        if datatype in ("string", "date"):
            role, kind = "dimension", ("nominal" if datatype == "string" else "ordinal")
        else:
            role, kind = "measure", "quantitative"
        attrs = {"caption": CAPTIONS.get(field, field.replace("_", " ")),
                 "datatype": datatype}
        fmt = "p0.0%" if field in PERCENT_FIELDS else FORMATS.get(field)
        if fmt and role == "measure":
            attrs["default-format"] = fmt
        attrs.update({"name": f"[{field}]", "role": role, "type": kind})
        return attrs


def tableau_type(column, values):
    """Map a CSV column to a Tableau data type."""
    if column in DATE_FIELDS:
        return "date"
    if column in LABEL_NUMBERS or pd.api.types.is_bool_dtype(values):
        return "string"            # True/False flags, read as text
    if pd.api.types.is_integer_dtype(values):
        return "integer"
    if pd.api.types.is_float_dtype(values):
        return "real"
    return "string"


# ---------------------------------------------------------------------------
# 3. The charts
# ---------------------------------------------------------------------------
# Each field is written as "how:Field":
#   dim:Name  -> Name as a category (a blue, discrete pill in Tableau)
#   sum:CAGR  -> SUM of CAGR (a green, continuous pill). Every mark in these
#                charts is exactly one CSV row, so the SUM is the value itself.
#   date:Date -> the exact date on a continuous time axis
SHEETS = [
    # ---- Page 1: India at a glance ----------------------------------------
    dict(name="Nifty 50 closing price", source="prices", mark="Line",
         cols=["date:Date"], rows=["sum:Close"], color="dim:Name",
         filters={"Name": ["Nifty 50"]}),
    dict(name="Nifty 50: how far below its last peak", source="prices",
         mark="Area", cols=["date:Date"], rows=["sum:Drawdown"],
         color="dim:Name", filters={"Name": ["Nifty 50"]}),
    dict(name="Nifty 50 return in each calendar year", source="yearly",
         mark="Bar", cols=["dim:Year"], rows=["sum:Return"], color="dim:Name",
         label="sum:Return",
         filters={"Name": ["Nifty 50"], "Currency_Basis": ["Local"]}),
    dict(name="India VIX: the market's fear gauge", source="vix", mark="Line",
         cols=["date:Date"], rows=["sum:India_VIX"]),

    # ---- Page 2: India vs the world ---------------------------------------
    dict(name="Growth of 100 invested, in US dollars", source="prices",
         mark="Line", cols=["date:Date"], rows=["sum:Index_100_USD"],
         color="dim:Name", filters={"Name": MARKETS}),
    # One panel per currency side by side (Basis on Columns), so each market
    # gets one row instead of three: readable on a small screen.
    dict(name="Yearly growth (CAGR) in three currencies", source="cagr",
         mark="Bar", rows=["dim:Name"], cols=["dim:Basis", "sum:CAGR"],
         color="dim:Basis", label="sum:CAGR", filters={"Name": MARKETS},
         sort=("dim:Name", "sum:CAGR", "DESC")),
    # No text labels: Nifty and Shanghai sit almost on top of each other, so
    # names would overlap. Colours match the legend next to "Growth of 100".
    dict(name="Risk vs return, in US dollars", source="summary", mark="Circle",
         cols=["sum:Annual_Volatility_USD"], rows=["sum:CAGR_USD"],
         color="dim:Name", filters={"Name": MARKETS}),
    dict(name="How closely markets move together", source="corr",
         mark="Square", rows=["dim:Index_A"], cols=["dim:Index_B"],
         color="sum:Correlation", label="sum:Correlation",
         filters={"Index_A": MARKETS, "Index_B": MARKETS}),

    # ---- Page 3: Inside India ---------------------------------------------
    dict(name="Indian indices: yearly growth (CAGR)", source="summary",
         mark="Bar", rows=["dim:Name"], cols=["sum:CAGR"], color="dim:Group",
         label="sum:CAGR",
         tooltip=["sum:Annual_Volatility", "sum:Max_Drawdown"],
         filters={"Country": ["India"]}, sort=("dim:Name", "sum:CAGR", "DESC")),
    dict(name="Indian indices: return in each calendar year", source="yearly",
         mark="Square", rows=["dim:Name"], cols=["dim:Year"],
         color="sum:Return", label="sum:Return",
         filters={"Country": ["India"], "Currency_Basis": ["Local"]}),
    dict(name="RBI rate cycle: annualised return in each phase",
         source="rates", mark="Bar", cols=["dim:Phase", "dim:Name"],
         rows=["sum:Annualised_Return"], color="dim:Name",
         label="sum:Annualised_Return",
         filters={"Name": ["Nifty 50", "Nifty Bank"]}),
    dict(name="Foreign investors' net buying of Indian shares", source="fpi",
         mark="Bar", cols=["dim:Year"], rows=["sum:FPI_Net_Equity_Rs_Crore"],
         label="sum:FPI_Net_Equity_Rs_Crore"),

]


def instance(token):
    """'sum:CAGR' -> ('[sum:CAGR:qk]', 'CAGR', 'Sum', 'quantitative').

    Tableau names every use of a field [aggregation:field:type]:
    qk = continuous (quantitative, a green pill), nk = category (a blue pill).
    """
    how, field = token.split(":", 1)
    prefix, suffix, derivation, kind = {
        "dim":  ("none", "nk", "None", "nominal"),
        "sum":  ("sum", "qk", "Sum", "quantitative"),
        "date": ("none", "qk", "None", "quantitative"),
    }[how]
    return f"[{prefix}:{field}:{suffix}]", field, derivation, kind


def sheet_tokens(sheet):
    """Every field use in a sheet: shelves, marks card, filters and sort."""
    tokens = list(sheet["rows"]) + list(sheet["cols"])
    tokens += [sheet[k] for k in ("color", "label") if sheet.get(k)]
    tokens += sheet.get("tooltip", [])
    tokens += [f"dim:{f}" for f in sheet.get("filters", {})]
    if sheet.get("sort"):
        tokens += list(sheet["sort"][:2])
    return list(dict.fromkeys(tokens))       # drop repeats, keep order


# ---------------------------------------------------------------------------
# 4. Dashboard text, computed from the data so it stays true after a rerun
# ---------------------------------------------------------------------------
def fmt_pct(x, decimals=1):
    return f"{x * 100:.{decimals}f}%"


def fmt_date(d):
    d = pd.Timestamp(d)
    return f"{d.day} {d:%b %Y}"


def dashboards():
    s = pd.read_csv(OUTPUT_DIR / "summary_metrics.csv").set_index("Name")
    nifty = s.loc["Nifty 50"]
    px = pd.read_csv(OUTPUT_DIR / "prices_daily.csv", parse_dates=["Date"])
    nifty_px = px[px["Name"] == "Nifty 50"].sort_values("Date")
    peak = nifty_px.loc[nifty_px["Close"].idxmax()]
    fx = pd.read_csv(OUTPUT_DIR / "fx_rates.csv")
    inr = fx[fx["Ticker"] == "INR=X"]["Rate"]
    rates = pd.read_csv(OUTPUT_DIR / "rate_cycle_returns.csv")
    hike = rates[(rates["Name"] == "Nifty Bank")
                 & rates["Phase"].str.contains("Hiking")].iloc[0]
    hike_months = round((pd.Timestamp(hike["End"]) - pd.Timestamp(hike["Start"])).days / 30.44)
    fpi = pd.read_csv(OUTPUT_DIR / "fpi_flows.csv").set_index("Year")

    usd = {n: fmt_pct(s.loc[n, "CAGR_USD"]) for n in MARKETS}
    # Rank the six markets by CAGR in dollars, so the sentence can't contradict the data.
    usd_rank = s.loc[MARKETS, "CAGR_USD"].sort_values(ascending=False)
    beat_india = [n for n in usd_rank.index if usd_rank[n] > usd_rank["Nifty 50"]]
    country = {"Nikkei 225": "Japan", "S&P 500": "the US", "DAX": "Germany",
               "FTSE 100": "the UK", "Shanghai Composite": "China"}
    if len(beat_india) == len(MARKETS) - 1:
        rank_text = "the worst of the six markets. "
    else:
        rank_text = f"number {len(beat_india) + 1} of the six markets. "
    better = ", ".join(f"{country[n]} ({usd[n]})" for n in beat_india)
    sectors = s[s["Country"] == "India"]["CAGR"]

    return [
        dict(name="India at a glance",
             title="India at a glance: the Nifty 50, Oct 2021 to Oct 2026",
             subtitle=(f"The Nifty 50 went from {nifty['Start_Price']:,.0f} to "
                       f"{nifty['End_Price']:,.0f}, up {fmt_pct(nifty['Total_Return'])} in five "
                       f"years, or {fmt_pct(nifty['CAGR'])} a year, about what a treasury "
                       f"bill paid. Its deepest fall was {fmt_pct(nifty['Max_Drawdown'])} "
                       f"({fmt_date(nifty['MDD_Peak_Date'])} to {fmt_date(nifty['MDD_Trough_Date'])}). "
                       f"It is now {fmt_pct(-nifty_px['Drawdown'].iloc[-1])} below its record "
                       f"close of {peak['Close']:,.0f} on {fmt_date(peak['Date'])}."),
             footer=("Calendar years: 2021 covers Oct to Dec only and 2026 runs to "
                     f"{fmt_date(nifty['End_Date'])}. India VIX is the market's expected "
                     "volatility for the next 30 days; above 20 happens on only 1 day in 10."),
             rows=[[("Nifty 50 closing price", 1, False),
                    ("Nifty 50: how far below its last peak", 1, False)],
                   [("Nifty 50 return in each calendar year", 1, False),
                    ("India VIX: the market's fear gauge", 1, False)]]),
        dict(name="India vs the world",
             title="India vs the world: did India keep up?",
             subtitle=(f"In US dollars the Nifty 50 returned {usd['Nifty 50']} a year, "
                       + rank_text
                       + f"The rupee fell from {inr.iloc[0]:.1f} to {inr.iloc[-1]:.1f} per "
                       f"dollar. Did better in dollars: {better}. India was one of the "
                       "calmest markets, and low risk came with low return."),
             footer=("Growth of 100: every index starts at 100 and is converted to US "
                     "dollars each day. Correlations use weekly returns because markets "
                     "close at different times. 1 = always move together, 0 = unrelated."),
             rows=[[("Growth of 100 invested, in US dollars", 1.5, True),
                    ("Risk vs return, in US dollars", 1, False)],
                   [("Yearly growth (CAGR) in three currencies", 1, False),
                    ("How closely markets move together", 1, False)]]),
        dict(name="Inside India",
             title="Inside India: sectors, company size and interest rates",
             subtitle=(f"Below the large caps the picture was better: Auto "
                       f"({fmt_pct(sectors['Nifty Auto (ETF)'])} a year), Midcap 50 "
                       f"({fmt_pct(sectors['Nifty Midcap 50'])}) and Pharma "
                       f"({fmt_pct(sectors['Nifty Pharma'])}) led, while IT lost "
                       f"{fmt_pct(-sectors['Nifty IT'])} a year. Bank stocks rose "
                       f"{fmt_pct(hike['Return'])} in the {hike_months} months the RBI was "
                       f"raising rates ({fmt_pct(hike['Annualised_Return'])} annualised), and "
                       f"foreign investors sold heavily in 2025 and 2026 "
                       f"(Rs {-fpi.loc[2025, 'FPI_Net_Equity_Rs_Crore'] / 1e5:.2f} and "
                       f"{-fpi.loc[2026, 'FPI_Net_Equity_Rs_Crore'] / 1e5:.2f} lakh crore)."),
             footer=("Auto and FMCG use ETFs that track the indices (Yahoo Finance has no "
                     "index data); the Auto ETF starts on 24 Jan 2022. Foreign flows: NSDL; "
                     "2025 is approximate and 2026 runs to 4 Sep."),
             rows=[[("Indian indices: yearly growth (CAGR)", 1, True),
                    ("Indian indices: return in each calendar year", 1, False)],
                   [("RBI rate cycle: annualised return in each phase", 1, False),
                    ("Foreign investors' net buying of Indian shares", 1, False)]]),
    ]


# ---------------------------------------------------------------------------
# 5. Extracts: the same data in Tableau's own .hyper format
# ---------------------------------------------------------------------------
HYPER_TYPES = {"date": "date", "string": "text", "real": "double",
               "integer": "big_int"}
NO_LOG = {"log_config": ""}   # stop Hyper writing a hyperd.log file


def to_python(value, datatype):
    """One CSV value as the Python type the Hyper API expects; blanks -> None."""
    if pd.isna(value):
        return None
    if datatype == "date":
        return pd.Timestamp(value).date()
    if datatype == "string":
        return str(value)
    if datatype == "integer":
        return int(value)
    return float(value)


def write_extracts(sources, folder):
    """Save every data source as a .hyper file. Tableau looks for the data in
    a table called Extract inside a schema called Extract."""
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                      parameters=NO_LOG) as hyper:
        for src in sources.values():
            table = TableDefinition(TableName("Extract", "Extract"), [
                TableDefinition.Column(col, getattr(SqlType, HYPER_TYPES[t])())
                for col, t in src.types.items()])
            rows = [[to_python(v, t) for v, t in zip(row, src.types.values())]
                    for row in src.data.itertuples(index=False)]
            with Connection(hyper.endpoint, folder / src.hyper,
                            CreateMode.CREATE_AND_REPLACE) as conn:
                conn.catalog.create_schema("Extract")
                conn.catalog.create_table(table)
                with Inserter(conn, table) as inserter:
                    inserter.add_rows(rows)
                    inserter.execute()


def read_extract(hyper, path):
    """Column names and row count of an extract, to check it against its CSV."""
    with Connection(hyper.endpoint, path) as conn:
        table = TableName("Extract", "Extract")
        columns = [c.name.unescaped for c in conn.catalog.get_table_definition(table).columns]
        count = conn.execute_scalar_query(f"SELECT COUNT(*) FROM {table}")
    return columns, count


# ---------------------------------------------------------------------------
# 6. Write Tableau's XML
# ---------------------------------------------------------------------------
def add(parent, tag, **attrs):
    """Shortcut: add a child tag. Python can't use 'class' as a keyword,
    so class_ becomes class."""
    attrs = {k.rstrip("_"): str(v) for k, v in attrs.items()}
    return ET.SubElement(parent, tag, attrs)


def add_datasource(parent, src):
    ds = ET.SubElement(parent, "datasource", {"caption": src.caption, "inline": "true",
                                              "name": src.name, "version": "18.1"})
    # Where the data lives: a text file inside the .twbx
    conn = add(ds, "connection", class_="federated")
    named = ET.SubElement(add(conn, "named-connections"), "named-connection",
                          {"caption": src.file[:-4], "name": src.conn})
    ET.SubElement(named, "connection", {"class": "textscan", "directory": DATA_FOLDER,
                                        "filename": src.file, "password": "",
                                        "server": ""})
    # The table and its columns, with their data types
    relation = ET.SubElement(conn, "relation", {"connection": src.conn, "name": src.file,
                                                "table": f"[{src.file[:-4]}#csv]",
                                                "type": "table"})
    cols = ET.SubElement(relation, "columns", {"character-set": "UTF-8", "header": "yes",
                                               "locale": "en_US", "separator": ","})
    for i, (col, datatype) in enumerate(src.types.items()):
        ET.SubElement(cols, "column", {"datatype": datatype, "name": col,
                                       "ordinal": str(i)})
    add(ds, "aliases", enabled="yes")
    # How each field behaves in Tableau: role, display name, number format
    for col in src.types:
        ET.SubElement(ds, "column", src.column_attrs(col))
    # Read the data from the .hyper extract instead of the CSV
    if src.extract:
        ext = add(ds, "extract", count="-1", enabled="true", units="records")
        hyper = ET.SubElement(ext, "connection", {
            "access_mode": "readonly", "authentication": "auth-none", "class": "hyper",
            "dbname": f"{EXTRACT_FOLDER}/{src.hyper}", "default-settings": "yes",
            "schema": "Extract", "sslmode": "", "tablename": "Extract",
            "update-time": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
            "username": "tableau_internal_user"})
        add(hyper, "relation", name="Extract", table="[Extract].[Extract]", type="table")
        add(add(hyper, "calculations"), "calculation", column="[Number of Records]",
            formula="1")
        add(hyper, "refresh", **{"increment-key": "", "incremental-updates": "false"})
    # Data pane layout. Tableau refuses to load the file if the two
    # *-percentage settings (how the pane is split) are missing.
    ET.SubElement(ds, "layout", {"dim-ordering": "alphabetic",
                                 "dim-percentage": "0.5",
                                 "measure-ordering": "alphabetic",
                                 "measure-percentage": "0.4",
                                 "show-structure": "true"})
    # Fixed colours, for fields that appear in COLOURS
    encodings = []
    for field, palette in COLOURS.items():
        if field in src.types:
            present = set(src.data[field].dropna().astype(str))
            pairs = [(v, c) for v, c in palette.items() if v in present]
            if pairs:
                encodings.append((field, pairs))
    if encodings:
        rule = add(add(ds, "style"), "style-rule", element="mark")
        for field, pairs in encodings:
            enc = ET.SubElement(rule, "encoding", {"attr": "color",
                                                   "field": f"[none:{field}:nk]",
                                                   "type": "palette"})
            for value, colour in pairs:
                add(add(enc, "map", to=colour), "bucket").text = f'"{value}"'


def add_worksheet(parent, sheet, src):
    ws = add(parent, "worksheet", name=sheet["name"])
    table = add(ws, "table")
    view = add(table, "view")
    add(add(view, "datasources"), "datasource", caption=src.caption, name=src.name)

    def ref(token):
        return f"[{src.name}].{instance(token)[0]}"

    # Which fields the sheet uses, and how (sum, category, exact date)
    tokens = sheet_tokens(sheet)
    deps = add(view, "datasource-dependencies", datasource=src.name)
    for field in sorted({instance(t)[1] for t in tokens}):
        ET.SubElement(deps, "column", src.column_attrs(field))
    for token in sorted(tokens, key=lambda t: instance(t)[0]):
        name, field, derivation, kind = instance(token)
        add(deps, "column-instance", column=f"[{field}]", derivation=derivation,
            name=name, pivot="key", type=kind)

    # Filters: keep only the listed values
    ui = {f"{{{USER_NS}}}ui-domain": "database",
          f"{{{USER_NS}}}ui-enumeration": "inclusive",
          f"{{{USER_NS}}}ui-marker": "enumerate"}
    filters = sheet.get("filters", {})
    for field, values in filters.items():
        level = instance(f"dim:{field}")[0]
        flt = add(view, "filter", class_="categorical", column=ref(f"dim:{field}"))
        if len(values) == 1:
            ET.SubElement(flt, "groupfilter", {"function": "member", "level": level,
                                               "member": f'"{values[0]}"', **ui})
        else:
            union = ET.SubElement(flt, "groupfilter", {"function": "union", **ui})
            for value in values:
                add(union, "groupfilter", function="member", level=level,
                    member=f'"{value}"')
    if sheet.get("sort"):
        dim, measure, direction = sheet["sort"]
        add(view, "sort", class_="computed", column=ref(dim), direction=direction,
            using=ref(measure))
    if filters:
        slices = add(view, "slices")
        for field in filters:
            add(slices, "column").text = ref(f"dim:{field}")
    add(view, "aggregation", value="true")
    add(table, "style")

    # The marks card: mark type, colour, label, tooltip
    pane = add(add(table, "panes"), "pane")
    add(add(pane, "view"), "breakdown", value="auto")
    add(pane, "mark", class_=sheet["mark"])
    marks = [("color", sheet.get("color")), ("text", sheet.get("label"))]
    marks += [("tooltip", t) for t in sheet.get("tooltip", [])]
    marks = [(kind, t) for kind, t in marks if t]
    if marks:
        enc = add(pane, "encodings")
        for kind, token in marks:
            add(enc, kind, column=ref(token))
    if sheet.get("label"):
        rule = add(add(pane, "style"), "style-rule", element="mark")
        add(rule, "format", attr="mark-labels-show", value="true")

    # Rows and Columns shelves; " / " nests one field inside another
    def shelf(tokens):
        refs = [ref(t) for t in tokens]
        return refs[0] if len(refs) == 1 else "(" + " / ".join(refs) + ")"

    add(table, "rows").text = shelf(sheet["rows"])
    add(table, "cols").text = shelf(sheet["cols"])


def add_dashboard(parent, page, sheets_by_name, sources):
    """Layout: title, finding, two rows of charts, footnote.

    Tableau positions are in units of 1/100,000 of the dashboard's width or
    height, so 50000 = half.
    """
    db = add(parent, "dashboard", name=page["name"])
    add(db, "style")
    add(db, "size", maxheight=DASHBOARD_MAX_H, maxwidth=DASHBOARD_MAX_W,
        minheight=DASHBOARD_MIN_H, minwidth=DASHBOARD_MIN_W)
    zones = add(db, "zones")
    ids = iter(range(1, 1000))
    full = 100000
    title_h, sub_h, foot_h = 5500, 9000, 4000   # room for 3 subtitle lines on a small screen
    row_h = (full - title_h - sub_h - foot_h) // len(page["rows"])
    legend_w = 12000

    root = add(zones, "zone", h=full, id=next(ids), type="layout-basic", w=full, x=0, y=0)
    column = add(root, "zone", h=full, id=next(ids), param="vert", type="layout-flow",
                 w=full, x=0, y=0)

    def text_zone(y, h, text, size, colour, bold=False):
        zone = add(column, "zone", h=h, id=next(ids), type="text", w=full, x=0, y=y)
        run_attrs = {"fontcolor": colour, "fontsize": str(size)}
        if bold:
            run_attrs["bold"] = "true"
        ET.SubElement(add(zone, "formatted-text"), "run", run_attrs).text = text

    text_zone(0, title_h, page["title"], 16, "#1f1f1f", bold=True)
    text_zone(title_h, sub_h, page["subtitle"], 10, "#333333")
    y = title_h + sub_h
    for row in page["rows"]:
        row_zone = add(column, "zone", h=row_h, id=next(ids), param="horz",
                       type="layout-flow", w=full, x=0, y=y)
        legends = sum(1 for _, _, legend in row if legend)
        chart_w = (full - legends * legend_w) / sum(weight for _, weight, _ in row)
        x = 0
        for i, (name, weight, legend) in enumerate(row):
            w = round(chart_w * weight)
            if i == len(row) - 1:          # last chart takes the rounding leftover
                w = full - x - (legend_w if legend else 0)
            add(row_zone, "zone", h=row_h, id=next(ids), name=name, w=w, x=x, y=y)
            x += w
            if legend:
                sheet = sheets_by_name[name]
                src = sources[sheet["source"]]
                add(row_zone, "zone", h=row_h, id=next(ids), name=name,
                    param=f"[{src.name}].{instance(sheet['color'])[0]}", type="color",
                    w=legend_w, x=x, y=y)
                x += legend_w
        y += row_h
    text_zone(y, full - y, page["footer"], 8, "#767676")


def add_windows(parent, pages, sheets, sources):
    """Tabs along the bottom of Tableau: dashboards first, then each chart."""
    windows = add(parent, "windows")
    for i, page in enumerate(pages):
        attrs = {"class": "dashboard", "name": page["name"]}
        if i == 0:
            attrs["maximized"] = "true"     # open on the first dashboard
        win = ET.SubElement(windows, "window", attrs)
        points = add(win, "viewpoints")
        for row in page["rows"]:
            for name, _, _ in row:
                add(add(points, "viewpoint", name=name), "zoom", type="entire-view")
        add(win, "active", id="-1")
    for sheet in sheets:
        win = add(windows, "window", class_="worksheet", name=sheet["name"])
        cards = add(win, "cards")
        left = add(add(cards, "edge", name="left"), "strip", size="160")
        for card in ("pages", "filters", "marks"):
            add(left, "card", type=card)
        top = add(cards, "edge", name="top")
        for card, size in (("columns", "2147483647"), ("rows", "2147483647"),
                           ("title", "31")):
            add(add(top, "strip", size=size), "card", type=card)
        if sheet.get("color"):
            src = sources[sheet["source"]]
            right = add(add(cards, "edge", name="right"), "strip", size="160")
            add(right, "card", param=f"[{src.name}].{instance(sheet['color'])[0]}",
                type="color")


def build_workbook(sources, pages):
    wb = ET.Element("workbook", {"source-build": "2018.1.0 (20181.18.0213.1250)",
                                 "source-platform": "win", "version": "18.1"})
    dss = add(wb, "datasources")
    for src in sources.values():
        add_datasource(dss, src)
    worksheets = add(wb, "worksheets")
    for sheet in SHEETS:
        add_worksheet(worksheets, sheet, sources[sheet["source"]])
    boards = add(wb, "dashboards")
    by_name = {s["name"]: s for s in SHEETS}
    for page in pages:
        add_dashboard(boards, page, by_name, sources)
    add_windows(wb, pages, SHEETS, sources)
    ET.indent(wb, space="  ")
    return ET.tostring(wb, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# 7. Package: zip the XML, the CSVs and the extracts into one .twbx
# ---------------------------------------------------------------------------
def package(twb_bytes, sources, extract_folder):
    """Numbers go in as plain decimals (0.0000429, not 4.29e-05), so Tableau's
    text reader can't misread any value."""
    TABLEAU_DIR.mkdir(exist_ok=True)
    path = TABLEAU_DIR / f"{WORKBOOK}.twbx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{WORKBOOK}.twb", twb_bytes)
        for src in sources.values():
            z.writestr(f"{DATA_FOLDER}/{src.file}",
                       src.data.to_csv(index=False, float_format="%.10f"))
            if src.extract:
                z.write(extract_folder / src.hyper, f"{EXTRACT_FOLDER}/{src.hyper}")
    return path


# ---------------------------------------------------------------------------
# 8. Validate: reopen the .twbx and check every reference
# ---------------------------------------------------------------------------
REF = re.compile(r"\[([^\]]+)\]\.(\[[^\]]+\])")


def validate(path):
    problems = []
    with zipfile.ZipFile(path) as z:
        files = {name: z.read(name) for name in z.namelist()}
    root = ET.fromstring(files[f"{WORKBOOK}.twb"])   # fails if the XML is broken

    # Data sources: the CSV is in the zip and the declared columns match it
    csv_of, fields_of = {}, {}
    for ds in root.find("datasources"):
        conn = ds.find(".//named-connection/connection")
        inside = f"{conn.get('directory')}/{conn.get('filename')}"
        if inside not in files:
            problems.append(f"{ds.get('caption')}: {inside} missing from the .twbx")
            continue
        data = pd.read_csv(io.BytesIO(files[inside]))
        if re.search(rb"\de[-+]?\d", files[inside]):
            problems.append(f"{inside}: has numbers in scientific notation")
        declared = [c.get("name") for c in ds.find(".//relation/columns")]
        if declared != list(data.columns):
            problems.append(f"{ds.get('caption')}: declared columns differ from the CSV")
        csv_of[ds.get("name")] = data
        fields_of[ds.get("name")] = {f"[{c}]" for c in data.columns}
        extract = ds.find("extract/connection")
        if extract is not None:
            hyper_file = extract.get("dbname")
            if hyper_file not in files:
                problems.append(f"{ds.get('caption')}: {hyper_file} missing from the .twbx")
                continue
            with tempfile.TemporaryDirectory() as tmp, HyperProcess(
                    telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                    parameters=NO_LOG) as hyper:
                copy = Path(tmp) / "check.hyper"
                copy.write_bytes(files[hyper_file])
                columns, count = read_extract(hyper, copy)
            if columns != list(data.columns) or count != len(data):
                problems.append(f"{hyper_file}: extract does not match the CSV "
                                f"({count} rows vs {len(data)})")

    # Sheets: every reference points at a real field, every filter value exists,
    # and every mark is exactly one CSV row (so SUM never adds rows together)
    sheet_names = set()
    for ws, sheet in zip(root.iter("worksheet"), SHEETS):
        name = ws.get("name")
        sheet_names.add(name)
        deps = ws.find(".//datasource-dependencies")
        ds_name = deps.get("datasource")
        data = csv_of[ds_name]
        cols = {c.get("name") for c in deps.findall("column")}
        insts = {c.get("name"): c.get("column") for c in deps.findall("column-instance")}
        for col in cols - fields_of[ds_name]:
            problems.append(f"{name}: unknown field {col}")
        for inst, col in insts.items():
            if col not in cols:
                problems.append(f"{name}: {inst} uses undeclared {col}")
        texts = [e.text for tag in ("rows", "cols") for e in ws.iter(tag)]
        texts += [e.text for e in ws.iter("column") if e.text]
        texts += [e.get(a) for e in ws.iter() for a in ("column", "using")
                  if e.get(a) and e.tag != "column-instance"]
        for text in texts:
            for ds_ref, inst in REF.findall(text):
                if ds_ref != ds_name or inst not in insts:
                    problems.append(f"{name}: broken reference {ds_ref}.{inst}")
        for gf in ws.iter("groupfilter"):
            if gf.get("member"):
                field = gf.get("level").split(":")[1]
                if gf.get("member").strip('"') not in set(data[field].astype(str)):
                    problems.append(f"{name}: filter value {gf.get('member')} not in {field}")
        rows = data
        for field, values in sheet.get("filters", {}).items():
            rows = rows[rows[field].astype(str).isin(values)]
        dims = [instance(t)[1] for t in sheet_tokens(sheet)
                if not t.startswith("sum:")]
        if rows.empty:
            problems.append(f"{name}: no data left after filters")
        elif rows.groupby(dims).size().max() > 1:
            problems.append(f"{name}: some marks would add up several rows")

    # Dashboards and tabs point at real sheets
    for db in root.iter("dashboard"):
        for zone in db.iter("zone"):
            if zone.get("name") and zone.get("name") not in sheet_names:
                problems.append(f"{db.get('name')}: zone for unknown sheet {zone.get('name')}")
    boards = {db.get("name") for db in root.iter("dashboard")}
    for win in root.iter("window"):
        if win.get("name") not in sheet_names | boards:
            problems.append(f"window for unknown sheet {win.get('name')}")
    return problems


def main():
    make_helper_tables()
    rng = random.Random(42)
    sources = {key: Source(key, file, caption, rng)
               for key, (file, caption) in DATASOURCES.items()}
    pages = dashboards()
    with tempfile.TemporaryDirectory() as tmp:
        if HyperProcess is not None:
            write_extracts(sources, Path(tmp))
        path = package(build_workbook(sources, pages), sources, Path(tmp))
    problems = validate(path)
    print(f"Saved {path.relative_to(PROJECT_DIR)}: {len(sources)} data sources, "
          f"{len(SHEETS)} sheets, {len(pages)} dashboards, "
          f"{path.stat().st_size / 1e6:.1f} MB")
    if HyperProcess is None:
        print("No extracts: tableauhyperapi is not installed, so the data sources read "
              "the CSVs directly. Tableau Public needs extracts: run "
              "'pip install tableauhyperapi' and rerun this script.")
    else:
        print(f"Extracts: {len(sources)} .hyper files written and checked against the CSVs.")
    if problems:
        print("Problems found:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print("Validation passed: every field, filter value and sheet reference checks out.")


if __name__ == "__main__":
    main()
