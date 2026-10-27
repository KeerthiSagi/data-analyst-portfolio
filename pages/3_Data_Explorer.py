"""Interactive Data Explorer for Global Superstore transaction records."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from utils.data_explorer import (
    COUNTRY_SCOPE_ALL,
    COUNTRY_SCOPE_SELECTED,
    CSV_FILENAME,
    DEFAULT_VISIBLE_COLUMNS,
    PREVIEW_ROW_LIMIT,
    SEARCH_COLUMNS,
    available_columns,
    calculate_data_quality,
    calculate_explorer_kpis,
    filter_explorer_data,
    prepare_csv_export,
    prepare_display_frame,
    resolve_country_selection,
    search_explorer_data,
)
from utils.data_loader import load_superstore_data
from utils.kpi_metrics import format_exact_currency, format_headline_currency
from utils.navigation import render_page_header, render_project_nav, render_sidebar_brand
from utils.theme import initialize_theme


st.set_page_config(
    page_title="Data Explorer | Atlas Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_theme()

df = load_superstore_data()


COLUMN_LABELS = {
    "Order_ID": "Order ID",
    "Order_Date": "Order Date",
    "Ship_Date": "Ship Date",
    "Customer_ID": "Customer ID",
    "Customer_Name": "Customer Name",
    "Product_ID": "Product ID",
    "Product_Name": "Product Name",
    "Sub_Category": "Sub-Category",
    "Ship_Mode": "Shipping Mode",
    "Order_Priority": "Order Priority",
    "Shipping_Cost": "Shipping Cost",
    "Shipping_Days": "Shipping Days",
    "Year_Month": "Year Month",
    "Row_ID": "Row ID",
}


def display_currency(value):
    if value is None or pd.isna(value):
        return "—"
    return format_headline_currency(value)


def exact_title(label, value):
    if value is None or pd.isna(value):
        return f"{label} is unavailable"
    return f"{label}: {format_exact_currency(value)}"


def render_kpi_card(column, *, card_key, label, value, value_title, footer):
    with column:
        with st.container(border=True, key=card_key, gap="xxsmall"):
            st.markdown(
                f"""
                <div class="kpi-card-body">
                    <div class="kpi-label">{html.escape(label)}</div>
                    <div class="kpi-value" title="{html.escape(value_title)}">{html.escape(value)}</div>
                    <div class="kpi-footer">{html.escape(footer)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def column_config_for(columns: list[str]) -> dict:
    config = {}
    for column in columns:
        label = COLUMN_LABELS.get(column, column.replace("_", " "))
        if column in {"Order_Date", "Ship_Date"}:
            config[column] = st.column_config.DateColumn(label, format="YYYY-MM-DD")
        elif column == "Year_Month":
            config[column] = st.column_config.DatetimeColumn(label, format="YYYY-MM")
        elif column in {"Sales", "Profit", "Shipping_Cost"}:
            config[column] = st.column_config.NumberColumn(label, format="$%.2f")
        elif column == "Discount":
            config[column] = st.column_config.NumberColumn(label, format="%.1f%%")
        elif column in {"Quantity", "Shipping_Days", "Year", "weeknum", "Row_ID"}:
            config[column] = st.column_config.NumberColumn(label, format="%d")
        else:
            config[column] = st.column_config.TextColumn(label)
    return config


# ============================================================
# SIDEBAR FILTERS
# ============================================================

if "explorer_reset" not in st.session_state:
    st.session_state.explorer_reset = 0

reset_token = st.session_state.explorer_reset

render_sidebar_brand()
render_project_nav("explorer")

st.sidebar.markdown("### Explorer Filters")

if st.sidebar.button("Reset Filters", width="stretch", key="explorer_reset_button"):
    st.session_state.explorer_reset += 1
    st.rerun()

min_date = df["Order_Date"].min().date()
max_date = df["Order_Date"].max().date()

date_selection = st.sidebar.date_input(
    "Reporting Period",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    key=f"explorer_dates_{reset_token}",
)

regions = sorted(df["Region"].dropna().unique().tolist()) if "Region" in df.columns else []
countries = sorted(df["Country"].dropna().unique().tolist()) if "Country" in df.columns else []
categories = sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else []
sub_categories = (
    sorted(df["Sub_Category"].dropna().unique().tolist()) if "Sub_Category" in df.columns else []
)
segments = sorted(df["Segment"].dropna().unique().tolist()) if "Segment" in df.columns else []
ship_modes = sorted(df["Ship_Mode"].dropna().unique().tolist()) if "Ship_Mode" in df.columns else []

selected_regions = st.sidebar.multiselect(
    "Region",
    options=regions,
    default=regions,
    key=f"explorer_regions_{reset_token}",
)

if countries:
    st.sidebar.markdown("Country")
    country_scope = st.sidebar.radio(
        "Country scope",
        options=[COUNTRY_SCOPE_ALL, COUNTRY_SCOPE_SELECTED],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key=f"explorer_country_scope_{reset_token}",
        help="All countries keeps the full geographic scope without listing every country chip.",
    )
    selected_country_values = []
    if country_scope == COUNTRY_SCOPE_SELECTED:
        selected_country_values = st.sidebar.multiselect(
            "Select countries",
            options=countries,
            default=[],
            key=f"explorer_countries_{reset_token}",
            placeholder="Search countries…",
            help="Search and choose one or more countries. Leave empty to return no country matches.",
        )
        if not selected_country_values:
            st.sidebar.caption("No countries selected — results will be empty until you choose at least one.")
    else:
        st.sidebar.caption(f"Including all {len(countries):,} countries.")
    selected_countries = resolve_country_selection(
        countries,
        scope=country_scope,
        selected=selected_country_values,
    )
else:
    selected_countries = None

selected_categories = st.sidebar.multiselect(
    "Category",
    options=categories,
    default=categories,
    key=f"explorer_categories_{reset_token}",
)
selected_sub_categories = st.sidebar.multiselect(
    "Sub-Category",
    options=sub_categories,
    default=sub_categories,
    key=f"explorer_sub_categories_{reset_token}",
)
selected_segments = st.sidebar.multiselect(
    "Customer Segment",
    options=segments,
    default=segments,
    key=f"explorer_segments_{reset_token}",
)
selected_ship_modes = st.sidebar.multiselect(
    "Shipping Mode",
    options=ship_modes,
    default=ship_modes,
    key=f"explorer_ship_modes_{reset_token}",
)

st.sidebar.markdown("### Search")
search_query = st.sidebar.text_input(
    "Search orders, products, or customers",
    value="",
    placeholder="Order ID, product, customer…",
    help="Case-insensitive partial match on Order ID, Product Name, Customer Name, and Customer ID.",
    key=f"explorer_search_{reset_token}",
)

if isinstance(date_selection, (tuple, list)) and len(date_selection) == 2:
    start_date, end_date = date_selection
else:
    start_date, end_date = min_date, max_date

filtered = filter_explorer_data(
    df,
    start=start_date,
    end=end_date,
    regions=selected_regions,
    countries=selected_countries,
    categories=selected_categories,
    sub_categories=selected_sub_categories,
    segments=selected_segments,
    ship_modes=selected_ship_modes,
)

view = search_explorer_data(filtered, search_query)
kpis = calculate_explorer_kpis(view)
quality = calculate_data_quality(view)


# ============================================================
# HEADER
# ============================================================

render_page_header(
    eyebrow="TRANSACTION ACCESS / RECORD EXPLORATION",
    title="Data Explorer",
    subtitle=(
        "Explore, filter, and export Global Superstore "
        "transaction records."
    ),
)


# ============================================================
# DATASET OVERVIEW
# ============================================================

cards = st.columns(4, gap="small", wrap=True)
render_kpi_card(
    cards[0],
    card_key="kpi_lines",
    label="Filtered Order Line Items",
    value=f"{kpis['line_items']:,}",
    value_title=f"Matching order line items: {kpis['line_items']:,}",
    footer="Rows after filters and search",
)
render_kpi_card(
    cards[1],
    card_key="kpi_orders",
    label="Unique Orders",
    value=f"{kpis['orders']:,}",
    value_title=f"Distinct Order_ID values: {kpis['orders']:,}",
    footer="Distinct orders in the current view",
)
render_kpi_card(
    cards[2],
    card_key="kpi_revenue",
    label="Total Revenue",
    value=display_currency(kpis["revenue"]),
    value_title=exact_title("Exact revenue", kpis["revenue"]),
    footer="SUM(Sales) in the current view",
)
render_kpi_card(
    cards[3],
    card_key="kpi_profit",
    label="Total Profit",
    value=display_currency(kpis["profit"]),
    value_title=exact_title("Exact profit", kpis["profit"]),
    footer="SUM(Profit) in the current view",
)

st.write("")


# ============================================================
# COLUMN SELECTION + TABLE
# ============================================================

st.subheader("Transaction Records")

default_columns = available_columns(df, DEFAULT_VISIBLE_COLUMNS)
all_columns = list(df.columns)
selected_columns = st.multiselect(
    "Visible columns",
    options=all_columns,
    default=default_columns,
    format_func=lambda name: COLUMN_LABELS.get(name, name.replace("_", " ")),
    key=f"explorer_columns_{reset_token}",
)

if not selected_columns:
    selected_columns = default_columns or all_columns[: min(8, len(all_columns))]

display = prepare_display_frame(view, selected_columns, limit=PREVIEW_ROW_LIMIT)

if view.empty:
    st.info("No records match the current filters and search. Adjust filters or use Reset Filters.")
else:
    if display["truncated"]:
        st.caption(
            f"Table preview: {display['preview_rows']:,} of {display['total_rows']:,} matching records "
            f"(capped at {display['limit']:,} rows for readability). "
            "CSV download exports every matching row."
        )
    else:
        st.caption(f"Showing all {display['total_rows']:,} matching records.")

    preview = display["preview"].copy()
    if "Discount" in preview.columns:
        # Store rates as 0–1; table shows percentage points like other ATLAS pages.
        preview["Discount"] = preview["Discount"] * 100

    st.dataframe(
        preview,
        width="stretch",
        hide_index=True,
        column_config=column_config_for(display["columns"]),
        height=420,
    )


# ============================================================
# CSV EXPORT
# ============================================================

st.subheader("Export")
st.caption(
    "Exports always use the active filters and search. The table above may be a preview; "
    "downloads include every matching row."
)

export_col, visible_col = st.columns(2, gap="medium", wrap=True)

with export_col:
    with st.container(border=True):
        st.download_button(
            label="Download Filtered Data",
            data=prepare_csv_export(view),
            file_name=CSV_FILENAME,
            mime="text/csv",
            width="stretch",
            type="primary",
            help="Exports every filtered and searched row with all original columns.",
            disabled=view.empty,
            key="explorer_download_all",
        )
        st.caption("All columns · every matching row · UTF-8 CSV")

with visible_col:
    with st.container(border=True):
        st.download_button(
            label="Download Visible Columns Only",
            data=prepare_csv_export(view, columns=selected_columns),
            file_name="atlas_filtered_superstore_visible.csv",
            mime="text/csv",
            width="stretch",
            help="Optional export limited to the columns currently selected above.",
            disabled=view.empty,
            key="explorer_download_visible",
        )
        st.caption("Optional · only columns selected for the table")


# ============================================================
# DATA QUALITY
# ============================================================

st.subheader("Data Quality Overview")
st.caption("Quality metrics are calculated on the currently filtered and searched rows.")

if view.empty:
    st.info("Data quality metrics appear once the current view contains records.")
else:
    quality_cols = st.columns(4, gap="small", wrap=True)
    quality_cols[0].metric("Total records", f"{quality['total_records']:,}")
    quality_cols[1].metric("Total columns", f"{quality['total_columns']:,}")
    quality_cols[2].metric("Full-row duplicates", f"{quality['full_row_duplicates']:,}")
    quality_cols[3].metric("Repeated Order IDs", f"{quality['repeated_order_ids']:,}")

    if quality["date_start"] and quality["date_end"]:
        st.caption(
            f"Date coverage: {quality['date_start']} → {quality['date_end']} · "
            f"Unique orders: {quality['unique_orders']:,}. "
            "Repeated Order IDs are expected for multi-line orders and are not full-row duplicates."
        )
    else:
        st.caption(
            f"Unique orders: {quality['unique_orders']:,}. "
            "Repeated Order IDs are expected for multi-line orders and are not full-row duplicates."
        )

    missing = quality["missing_by_column"]
    st.markdown("##### Missing values by column")
    if missing.empty:
        st.success("No missing values in the current view.")
    else:
        missing_frame = missing.reset_index()
        missing_frame.columns = ["Column", "Missing values"]
        missing_frame["Share of rows"] = (
            missing_frame["Missing values"] / quality["total_records"] * 100
        )
        st.dataframe(
            missing_frame,
            width="stretch",
            hide_index=True,
            column_config={
                "Column": st.column_config.TextColumn("Column"),
                "Missing values": st.column_config.NumberColumn("Missing values", format="%d"),
                "Share of rows": st.column_config.NumberColumn("Share of rows", format="%.2f%%"),
            },
        )

search_fields = available_columns(df, SEARCH_COLUMNS)
st.caption(
    "Search fields: "
    + (", ".join(COLUMN_LABELS.get(name, name) for name in search_fields) or "none available")
    + "."
)
