# ATLAS Analytics — Executive Sales Intelligence Dashboard

Interactive Streamlit dashboard for Global Superstore sales, profitability, customer segments, regional performance, and shipping logistics.

**Live app:** https://data-analyst-portfolio-onoez34kn8frqtuwvybao8.streamlit.app/

## Features

- Executive KPIs (revenue, profit, margin, orders, AOV) with sparklines
- Customer segment performance and discount analysis
- Regional comparisons across markets
- Shipping cost, mode, and order-to-shipment processing metrics
- Interactive Data Explorer with CSV export
- 140 automated tests

## Dataset

`data/Global_Superstore.xlsx` — 51,290 order **line items**, 25,035 unique orders (2011–2014).

## Run locally

From this directory:

```bash
pip install -r requirements.txt
streamlit run app_kpi_dashboard.py
```

Or from the repository root:

```bash
streamlit run project1-atlas-analytics/app_kpi_dashboard.py
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Structure

```text
project1-atlas-analytics/
├── app_kpi_dashboard.py   # Executive Overview (entry point)
├── pages/                 # Segment, Regional/Logistics, Data Explorer
├── utils/                 # Loaders, KPIs, analytics, theme, navigation
├── data/                  # Global Superstore
├── tests/
├── docs/screenshots/
└── requirements.txt
```
