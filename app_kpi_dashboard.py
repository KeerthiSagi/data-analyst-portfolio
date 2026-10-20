import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from utils.theme import initialize_theme
from utils.data_loader import load_superstore_data


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Executive Overview | Atlas Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

initialize_theme()


# ============================================================
# INITIALIZE DATA — GLOBAL SUPERSTORE
# ============================================================

df = load_superstore_data()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div style="
        font-size:1.15rem;
        font-weight:800;
        color:#4F46E5;
        margin-bottom:5px;
    ">
        ◈ ATLAS ANALYTICS
    </div>
    <div style="
        color:#64748B;
        font-size:0.8rem;
        margin-bottom:25px;
    ">
        Global Sales Intelligence
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("### Report Filters")

# ============================================================
# REPORTING YEAR FILTER
# ============================================================

available_years = sorted(
    df["Order_Date"].dt.year.dropna().unique().tolist()
)

selected_years = st.sidebar.multiselect(
    "Reporting Years",
    options=available_years,
    default=available_years,
    help="Select one or more years to analyze."
)

min_date = df["Order_Date"].min().date()
max_date = df["Order_Date"].max().date()

date_selection = st.sidebar.date_input(
    "Reporting Period",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

regions = sorted(df["Region"].unique().tolist())

selected_regions = st.sidebar.multiselect(
    "Region",
    options=regions,
    default=regions
)

categories = sorted(df["Category"].unique().tolist())

selected_categories = st.sidebar.multiselect(
    "Product Category",
    options=categories,
    default=categories
)

if (
    isinstance(date_selection, (tuple, list))
    and len(date_selection) == 2
):
    start_date, end_date = date_selection
else:
    start_date, end_date = min_date, max_date


# ============================================================
# FILTER DATA
# ============================================================

filtered_df = df[
    (df["Order_Date"].dt.year.isin(selected_years))
    &
    (df["Order_Date"].dt.date >= start_date)
    &
    (df["Order_Date"].dt.date <= end_date)
    &
    (df["Region"].isin(selected_regions))
    &
    (df["Category"].isin(selected_categories))
].copy()

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="dashboard-eyebrow">
        GLOBAL SALES INTELLIGENCE / EXECUTIVE REPORTING
    </div>

    <div class="dashboard-title">
        Executive Overview
    </div>

    <div class="dashboard-subtitle">
        Monitor revenue, profitability, and business performance
        across global markets.
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# KPI CALCULATIONS
# ============================================================

total_revenue = filtered_df["Sales"].sum()
total_profit = filtered_df["Profit"].sum()
total_orders = filtered_df["Order_ID"].nunique()

profit_margin = (
    total_profit / total_revenue * 100
    if total_revenue != 0
    else 0
)


# ============================================================
# PREVIOUS-PERIOD COMPARISON
# ============================================================

def calculate_change(current, previous):
    if previous is None or previous == 0:
        return None

    return (current - previous) / abs(previous) * 100


previous_df = pd.DataFrame()

# Comparisons require consecutive selected years.
years_are_consecutive = (
    len(selected_years) > 0
    and selected_years == list(
        range(min(selected_years), max(selected_years) + 1)
    )
)

if years_are_consecutive:

    period_length = len(selected_years)

    previous_years = list(
        range(
            min(selected_years) - period_length,
            min(selected_years)
        )
    )

    # Only compare when the entire previous period exists.
    if set(previous_years).issubset(set(available_years)):

        previous_df = df[
            (df["Order_Date"].dt.year.isin(previous_years))
            &
            (df["Region"].isin(selected_regions))
            &
            (df["Category"].isin(selected_categories))
        ].copy()

        # Match the selected month/day window for a single-year
        # comparison when both date inputs fall in that year.
        if (
            period_length == 1
            and start_date.year == end_date.year
            and start_date.year == selected_years[0]
        ):
            previous_df = previous_df[
                (
                    (previous_df["Order_Date"].dt.month * 100
                     + previous_df["Order_Date"].dt.day)
                    >= (start_date.month * 100 + start_date.day)
                )
                &
                (
                    (previous_df["Order_Date"].dt.month * 100
                     + previous_df["Order_Date"].dt.day)
                    <= (end_date.month * 100 + end_date.day)
                )
            ]


revenue_change = None
profit_change = None
margin_change = None
orders_change = None

if not previous_df.empty:

    previous_revenue = previous_df["Sales"].sum()
    previous_profit = previous_df["Profit"].sum()
    previous_orders = previous_df["Order_ID"].nunique()

    previous_margin = (
        previous_profit / previous_revenue * 100
        if previous_revenue != 0
        else None
    )

    revenue_change = calculate_change(
        total_revenue, previous_revenue
    )

    profit_change = calculate_change(
        total_profit, previous_profit
    )

    orders_change = calculate_change(
        total_orders, previous_orders
    )

    if previous_margin is not None:
        margin_change = profit_margin - previous_margin


# ============================================================
# KPI CARDS
# ============================================================

def kpi_card(label, value, footer, color, change=None, unit="%"):

    if change is None:
        comparison_text = "No prior-period data"
        comparison_color = "#94A3B8"
    else:
        arrow = "▲" if change >= 0 else "▼"
        comparison_text = f"{arrow} {abs(change):.1f}{unit} vs prior period"
        comparison_color = (
            "#059669" if change >= 0 else "#DC2626"
        )

    st.markdown(
        f"""
        <div class="kpi-card kpi-{color}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-footer">{footer}</div>
            <div style="
                margin-top:12px;
                font-size:0.78rem;
                font-weight:700;
                color:{comparison_color};
            ">
                {comparison_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

k1, k2, k3, k4 = st.columns(4)

with k1:
    kpi_card(
        "Total Revenue",
        f"${total_revenue:,.0f}",
        "Gross sales generated",
        "indigo",
        revenue_change
    )

with k2:
    kpi_card(
        "Total Profit",
        f"${total_profit:,.0f}",
        "Reported transaction profit",
        "green",
        profit_change
    )

with k3:
    kpi_card(
        "Profit Margin",
        f"{profit_margin:.2f}%",
        "Profit as a share of revenue",
        "violet",
        margin_change,
        unit=" pp"
    )

with k4:
    kpi_card(
        "Total Orders",
        f"{total_orders:,}",
        "Unique customer orders",
        "sky",
        orders_change
    )

st.write("")
st.write("")


# ============================================================
# MONTHLY PERFORMANCE
# ============================================================

monthly = (
    filtered_df
    .groupby("Year_Month", as_index=False)
    [["Sales", "Profit"]]
    .sum()
)

monthly = monthly.rename(
    columns={
        "Sales": "Revenue",
        "Profit": "Profit"
    }
)


# ============================================================
# CHART ROW 1
# ============================================================

left, right = st.columns([3, 2])

with left:

    st.subheader("Revenue & Profit Trends")

    fig_line = px.line(
        monthly,
        x="Year_Month",
        y=["Revenue", "Profit"],
        markers=True,
        color_discrete_sequence=[
            "#4F46E5",
            "#10B981"
        ],
        labels={
            "Year_Month": "Month",
            "value": "Amount ($)",
            "variable": "Metric"
        }
    )

    fig_line.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=30, b=20),
        hovermode="x unified",
        legend_title_text="",
        plot_bgcolor="white",
        paper_bgcolor="white"
    )

    st.plotly_chart(
        fig_line,
        use_container_width=True
    )


with right:

    st.subheader("Revenue Composition")

    category_data = (
        filtered_df
        .groupby("Category", as_index=False)["Sales"]
        .sum()
    )

    fig_donut = px.pie(
        category_data,
        values="Sales",
        names="Category",
        hole=0.62,
        color_discrete_sequence=[
            "#4F46E5",
            "#8B5CF6",
            "#A5B4FC"
        ]
    )

    fig_donut.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="white",
        legend=dict(
            orientation="h",
            y=-0.1
        ),
        annotations=[
            dict(
                text="REVENUE MIX",
                x=0.5,
                y=0.5,
                font=dict(
                    size=13,
                    color="#64748B"
                ),
                showarrow=False
            )
        ]
    )

    st.plotly_chart(
        fig_donut,
        use_container_width=True
    )


# ============================================================
# REGIONAL PERFORMANCE
# ============================================================

st.write("")

st.subheader("Geographic Revenue Performance")

regional = (
    filtered_df
    .groupby("Region", as_index=False)["Sales"]
    .sum()
    .sort_values("Sales", ascending=True)
)

fig_region = px.bar(
    regional,
    x="Sales",
    y="Region",
    orientation="h",
    color_discrete_sequence=["#6366F1"],
    labels={
        "Sales": "Revenue ($)",
        "Region": "Region"
    }
)

fig_region.update_layout(
    height=340,
    margin=dict(l=20, r=20, t=20, b=20),
    plot_bgcolor="white",
    paper_bgcolor="white"
)

st.plotly_chart(
    fig_region,
    use_container_width=True
)


# ============================================================
# EXECUTIVE INSIGHTS
# ============================================================

st.write("")
st.subheader("Executive Insights")

top_category = (
    category_data
    .sort_values("Sales", ascending=False)
    .iloc[0]["Category"]
)

top_region = (
    regional
    .sort_values("Sales", ascending=False)
    .iloc[0]["Region"]
)

profit_status = (
    "positive profitability"
    if total_profit >= 0
    else "negative profitability"
)

i1, i2, i3 = st.columns(3)

with i1:
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">Revenue Leader</div>
            <div class="insight-body">
                {top_category} contributes the highest revenue
                among product categories.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with i2:
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">Top Performing Region</div>
            <div class="insight-body">
                {top_region} generates the highest sales
                in the selected reporting period.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with i3:
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">Profitability Health</div>
            <div class="insight-body">
                The business reports {profit_status},
                with an overall profit margin of
                {profit_margin:.2f}%.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "ATLAS ANALYTICS | Global Superstore Dataset | "
    "Historical Reporting: 2011–2014"
)