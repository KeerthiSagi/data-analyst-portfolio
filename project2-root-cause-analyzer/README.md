# CAUSE — Metric Drop Root Cause Analyzer

CAUSE is a Streamlit app for investigating why a business metric moved between two periods. Pick a period and a comparison, and it shows how revenue, profit, orders, average order value and profit margin changed, which markets, regions, categories and customer segments account for the change, and whether a revenue change came from order volume or order value. Every number reconciles: group contributions add up to the total change, and the driver effects add up to the revenue change with nothing left unexplained.

**Live app:** https://data-analyst-portfolio-yictmcakk4rypw8ulkd85s.streamlit.app/

> CAUSE shows **where** a change happened, not **why**. Its findings point to areas worth investigating; they are not proven root causes.

## Contents

- [Dataset](#dataset)
- [The four pages](#the-four-pages)
- [Methodology](#methodology)
- [Assumptions and limitations](#assumptions-and-limitations)
- [Installation](#installation)
- [Running the app](#running-the-app)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project structure](#project-structure)

## Dataset

CAUSE uses the **Global Superstore** retail dataset, shared with Project 1 (`project1-atlas-analytics/data/Global_Superstore.xlsx`). The file is read-only: CAUSE never modifies it and never falls back to synthetic data.

| | |
|---|---|
| Order lines | 51,290 |
| Date range | 1 Jan 2011 – 31 Dec 2014 |
| Distinct orders (composite key) | 25,754 (vs 25,035 distinct Order IDs) |
| Markets / regions | 7 markets, 18 market-qualified regions |
| Categories / segments | 3 categories, 3 customer segments |

The loader looks for the file in this order and uses the first match:

1. The `CAUSE_DATA_PATH` environment variable (an error if it points to a missing file)
2. `project2-root-cause-analyzer/data/Global_Superstore.xlsx` (to run Project 2 on its own)
3. `project1-atlas-analytics/data/Global_Superstore.xlsx` (the shared copy; the default)

`.xlsx`, `.xls` and `.csv` files are supported. Column headers are matched loosely, so `Order ID`, `Order.ID` and `order_id` all work.

On load, the data is validated. Missing required columns, unreadable dates, non-numeric sales or profit, and missing IDs stop the app with a clear message. Problems that don't block analysis are recorded on the loader's validation report. With the current file, that's one order line with zero sales (kept as recorded) and 660 reused Order IDs (see [composite order keys](#composite-order-keys)). The sidebar shows the row count, distinct order count and date range of the loaded file.

## The four pages

All pages share the sidebar:

- **Analysis period:** Month, Quarter (default), Year, or a Custom date range. The default is the most recent period fully covered by the data.
- **Compare with:** the previous period of the same type, or the same period last year.
- **Filters:** Market, Region, Category and Customer Segment. An empty filter means "all".

Each page shows the current period, comparison period and active filters at the top, and warns when a comparison window falls outside the data or is only partly covered, when custom windows differ in length, or when the filters match no orders.

### 1. Metric Overview

A summary of the selected period against the comparison period.

- KPI cards for total revenue, total profit, distinct orders and profit margin, with absolute and percentage changes (margin in percentage points).
- **Notable changes:** metrics that moved by 10% or more (1 pp for margin).
- **Monthly revenue and profit** trend, with the two windows highlighted.
- **Revenue and profit by market** for the current period.
- **Category performance**, with loss-making categories and sub-categories called out.
- **Customer segment performance** table.
- **Performance insights:** rule-based findings generated from the figures on the page.

### 2. Root Cause Investigation

Finds which groups account for a metric's change.

- Choose a metric (Revenue, Profit, Orders or Profit Margin) and a dimension to **break down by** (Market, Region, Category or Customer Segment).
- A waterfall and table show each group's contribution, ranked by size, with its share of the net change and of the total movement.
- For profit margin, each group's contribution is split into a **rate effect** and a **mix effect**.
- Optionally pick a second dimension (**then by**). Without a parent selected, it lists every combination of the two dimensions. Select one parent group to **drill down** into it; the drill-down rows add up to that group's change.
- Rule-based findings: the largest contributors, concentration in a single group, and offsetting movements.

### 3. Revenue Driver Analysis

Splits the revenue change into its two drivers: **Revenue = Distinct Orders × Average Order Value (AOV)**.

- KPI cards for revenue, orders and AOV, plus the **order volume effect** and **order value effect**.
- **Revenue bridge:** a waterfall from comparison revenue, through the two effects, to current revenue.
- **Monthly trends** for orders and AOV.
- **Drivers by group:** the volume/AOV split within each market, region, category or segment.

### 4. Investigation Report

A shareable summary of the investigation, using the same settings and calculations as the Root Cause Investigation page (changing one changes the other).

- Summary, KPI comparison table, top positive and negative contributors, revenue driver and margin findings, analytical insights, and methodology notes.
- **Downloads:**
  - KPI comparison (CSV)
  - Contributions (CSV): every row of the main, drill-down or combination table
  - Findings (CSV)
  - Full report (Markdown)

CSV values are plain numbers: percentages in percent units (38.1 means 38.1%), margin changes in percentage points, money in USD.

## Methodology

### Metrics

| Metric | Definition |
|---|---|
| Revenue | Sum of `Sales` |
| Profit | Sum of `Profit` |
| Orders | Distinct composite order keys |
| Average order value | Revenue ÷ distinct orders |
| Profit margin | Total profit ÷ total revenue |

- **Percentage change** = (current − previous) ÷ previous. It is shown only when the previous value is positive; otherwise the app says why it is unavailable.
- **Profit margin** changes are always in **percentage points**: 12.5% → 10.0% is −2.5 pp, not −20%. Margin is never a sum or average of group margins.

### Periods

- Month, quarter and year periods are full calendar periods. "Previous period" is the previous calendar period of the same type, even when day counts differ (Mar → Feb).
- A custom range made of whole calendar months is shifted back by the same number of months (Jan–Mar → Oct–Dec). Any other custom range is compared with the equal-length window ending the day before it starts.
- Year-over-year shifts move 29 Feb to 28 Feb.

### Composite order keys

In Global Superstore, an **Order ID is not unique to one transaction**: 660 Order IDs are reused by different customers or on different dates. Counting Order IDs alone would undercount orders (25,035 instead of 25,754).

CAUSE therefore defines an order as:

```
order_key = Order ID | Customer ID | Order Date
```

The loader confirms that this key identifies single transactions: every order-level attribute (ship date, ship mode, priority, market, region, country, state, city, segment, customer name) has exactly one value per key.

### Allocated orders

An order can contain lines from several groups. For example, one order with furniture and technology lines counts once in each category. So the distinct order counts per group overlap and add up to more than the total, and they cannot be used directly to show contribution.

For contribution analysis, CAUSE uses **allocated orders**. Each order is split equally across the groups it touches:

```
allocated_orders(group) = Σ over orders containing the group of  1 / (number of groups in that order)
```

Each order contributes exactly 1 across all groups, so allocated orders add up to the distinct order total and group changes add up to the total change. With two dimensions, the split is hierarchical: first across the first dimension's groups, then within each of those across the second dimension's groups. This makes drill-down rows add up to their parent row.

Allocated orders are a convention for attribution, not an observed count. The actual (overlapping) distinct counts are shown alongside them and labelled as such.

### Contribution analysis (revenue, profit, orders)

For additive metrics, each group's contribution is its own change:

```
contribution(g) = value(g, current) − value(g, previous)
Σ contribution(g) = total change   (exactly)
```

Groups that exist in only one period are counted as zero in the other. Two shares are reported:

- **Share of net change** = contribution ÷ total change.
- **Share of total movement** = contribution ÷ Σ |contribution|.

When the net change is less than 20% of the total movement, groups largely offset each other and shares of the net change become misleading (a group can show +900%). In that case CAUSE hides the share of net change, shows the share of total movement instead, and explains why.

### Revenue decomposition: volume and AOV

Revenue = N × A, where N is distinct orders and A is average order value. The revenue change is split with a **midpoint (two-factor Shapley) decomposition**:

```
volume effect = (N₁ − N₀) × (A₀ + A₁) / 2
AOV effect    = (A₁ − A₀) × (N₀ + N₁) / 2
volume effect + AOV effect = R₁ − R₀   (exactly)
```

There is no interaction term or unexplained remainder, and the result does not depend on which factor is taken first. If a period has no orders, its AOV is undefined; the other period's AOV is used, so the whole change counts as volume.

**Per-group drivers** apply the same formula within each group, using the distinct orders that contain the group and the group's revenue per such order. Each group's two effects add up to its own revenue change, and the groups' revenue changes add up to the total. The group volume and AOV effects do **not** add up to the overall volume and AOV effects, because orders overlap across groups and the overall AOV also reflects the mix of groups. The app says so on the page.

### Profit margin decomposition: rate and mix

Overall margin is M = P ÷ R. Each group's contribution to the change in overall margin, in percentage points, is:

```
c(g) = 100 × ( P(g,1) / R₁ − P(g,0) / R₀ )
Σ c(g) = 100 × (M₁ − M₀)   (exactly)
```

Each contribution is split into:

```
mix effect  = 100 × (w₁ − w₀) × (m₀ + m₁) / 2
rate effect = c(g) − mix effect
```

where *w* is the group's share of total revenue and *m* is the group's own margin.

- The **rate effect** is the part caused by the group's own margin changing.
- The **mix effect** is the part caused by the group's revenue share changing.

When the group has revenue in both periods, the rate effect equals 100 × (m₁ − m₀) × (w₀ + w₁) / 2, the standard midpoint split. When a group has no revenue in one period, its margin there is undefined; the other period's margin is used, so a group entering or leaving the mix shows up as a mix effect. If either period has no positive revenue overall, the margin is undefined and the app explains that it cannot be decomposed.

### Findings

Findings are generated by rules from the computed numbers; no text is hardcoded. A change is flagged as significant at 10% or more (1 pp for margin), and a single group with at least 50% of the total movement is flagged as a concentration. Wording describes where a change is concentrated ("accounted for", "contributed") and never claims a cause.

### Reconciliation

Every decomposition carries a reconciliation check (sum of parts minus total), and the test suite asserts that it is zero, to floating-point precision, for every metric across every single and paired dimension, on hand-worked examples and on the real dataset.

## Assumptions and limitations

- **Contribution is not causation.** CAUSE identifies where a change is concentrated. Finding out why needs further investigation and business context.
- **Currency.** Values are shown in US dollars. The dataset doesn't state its currency, so this has not been verified.
- **Allocated orders are a convention.** The equal split is one reasonable way to attribute shared orders; other weightings (by revenue, for example) would give different group values.
- **Per-group drivers don't add up to the overall drivers** (see above). Only the overall revenue bridge reconciles exactly.
- **No scaling for period length.** Totals are compared as they are. A 31-day month compared with a 28-day month, or custom windows of different lengths, are not adjusted per day; the app warns when custom windows differ in length.
- **Partial periods.** Windows partly outside 2011–2014 are flagged, but their totals are understated.
- **Historical, static data.** The dataset ends on 31 Dec 2014 and is not updated. The app analyses one file; it has no live data connection.
- **Data quality issues are kept, not corrected.** The zero-sales line is kept as recorded, and reused Order IDs are handled with the composite key rather than removed.
- **Dimensions are fixed** to Market, Region, Category and Customer Segment. Region names repeat across markets ("Central" exists in US, EU and LATAM), so regions are labelled with their market, such as "US · Central".

## Installation

Requires **Python 3.10 or later** (tested on 3.13).

From the repository root:

```bash
cd project2-root-cause-analyzer
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # to run the app
pip install -r requirements-dev.txt  # to also run the tests
```

| File | Contents |
|---|---|
| `requirements.txt` | Runtime dependencies: streamlit, pandas, numpy, plotly, openpyxl |
| `requirements-dev.txt` | Everything in `requirements.txt`, plus pytest |

## Running the app

From this folder:

```bash
streamlit run app_root_cause.py
```

Or from the repository root:

```bash
streamlit run project2-root-cause-analyzer/app_root_cause.py
```

The app opens at http://localhost:8501. The midnight-blue theme comes from `.streamlit/config.toml` in this folder; Streamlit gives a config file next to the entry point priority over the repository root's, so the theme applies however the app is launched.

To use a different copy of the dataset:

```bash
CAUSE_DATA_PATH=/path/to/Global_Superstore.xlsx streamlit run app_root_cause.py
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Run from this folder; `pytest.ini` sets the test path and import path. The suite has 228 tests covering:

- Data loading, validation and the composite order key
- Period selection, comparison windows and coverage warnings
- KPI calculations and safe division
- Contribution analysis, order allocation and drill-down reconciliation
- Revenue volume/AOV and margin rate/mix decompositions, including hand-worked examples (`tests/hand_example.py`)
- Rule-based findings and their wording
- Chart data, CSV and Markdown exports
- Every page rendering through Streamlit's `AppTest`
- Reconciliation on the real Global Superstore file

## Deployment

The app is set up for [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push the repository to GitHub.
2. In Community Cloud, create an app from the repository and set:
   - **Branch:** `main`
   - **Main file path:** `project2-root-cause-analyzer/app_root_cause.py`
   - **Python version:** 3.10 or later (under Advanced settings)
3. Deploy.

Community Cloud installs dependencies from the `requirements.txt` next to the entry point, so it uses this folder's file rather than the repository root's. The theme is read from this folder's `.streamlit/config.toml`. The dataset is committed in `project1-atlas-analytics/data/`, so no extra setup is needed. The app uses no secrets or environment variables; `CAUSE_DATA_PATH` is optional.

## Project structure

```
project2-root-cause-analyzer/
├── app_root_cause.py        # Streamlit entry point: page setup, navigation, data loading
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Runtime + test dependencies
├── pytest.ini
├── .streamlit/config.toml   # Midnight-blue theme
├── cause/                   # Analytics engine (no Streamlit imports)
│   ├── config.py            # Data paths, column schema, dimensions
│   ├── data.py              # Loading, validation, composite order key
│   ├── periods.py           # Periods and comparison windows
│   ├── metrics.py           # KPIs and period-over-period changes
│   ├── contribution.py      # Contribution, allocated orders, margin rate/mix, drill-down
│   ├── decomposition.py     # Revenue volume/AOV decomposition
│   ├── insights.py          # Rule-based findings
│   └── report.py            # Shared investigation, CSV and Markdown exports
├── ui/                      # Streamlit helpers
│   ├── state.py             # Sidebar, cached loading, shared settings
│   ├── filters.py           # Filter and period selection logic
│   ├── chart_data.py        # Chart-ready tables
│   ├── charts.py            # Plotly charts
│   ├── components.py        # Cards, callouts, tables, methodology text
│   └── theme.py             # Colours and CSS
├── views/                   # The four pages
│   ├── overview.py
│   ├── investigation.py
│   ├── revenue_drivers.py
│   └── report.py
└── tests/
```
