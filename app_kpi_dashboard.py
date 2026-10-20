import html

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from utils.theme import initialize_theme
from utils.data_loader import load_superstore_data
from utils.kpi_metrics import (
    aggregate_kpi_trends,
    build_sparkline,
    format_exact_currency,
    format_headline_currency,
    format_period_comparison,
    prior_period_caption,
)


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


revenue_change = None
profit_change = None
margin_change = None
orders_change = None

previous_df = pd.DataFrame()

# Determine the number of calendar days in the selected period.
period_days = (end_date - start_date).days + 1

# Compare against an equally long period immediately before it.
previous_end = start_date - pd.Timedelta(days=1)
previous_start = previous_end - pd.Timedelta(days=period_days - 1)

dataset_start = df["Order_Date"].min().date()

# Only calculate comparisons when the entire previous
# reporting period is covered by the dataset.
if previous_start >= dataset_start:

    previous_df = df[
        (df["Order_Date"].dt.date >= previous_start)
        &
        (df["Order_Date"].dt.date <= previous_end)
        &
        (df["Region"].isin(selected_regions))
        &
        (df["Category"].isin(selected_categories))
    ].copy()


previous_revenue = None
previous_profit = None
previous_orders = None
comparison_ready = not previous_df.empty

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
        total_revenue,
        previous_revenue
    )

    profit_change = calculate_change(
        total_profit,
        previous_profit
    )

    orders_change = calculate_change(
        total_orders,
        previous_orders
    )

    if previous_margin is not None:
        margin_change = profit_margin - previous_margin


# ============================================================
# KPI CARDS
# ============================================================

trends = aggregate_kpi_trends(filtered_df, start_date, end_date)
comparison_detail = prior_period_caption(
    previous_start,
    previous_end,
    comparison_ready,
)


def render_kpi_card(
    column,
    *,
    card_key,
    label,
    value,
    value_title,
    accent,
    comparison,
    comparison_color,
    footer,
    figure,
    chart_key,
):
    """Premium KPI card: metric, prior-period comparison, and sparkline."""

    with column:
        with st.container(border=True, key=card_key, height="stretch", gap="xxsmall"):
            st.markdown(
                f"""
                <div class="kpi-card-body kpi-{accent}">
                    <div class="kpi-label-row">
                        <div class="kpi-label">{html.escape(label)}</div>
                        <div class="kpi-grain">{html.escape(trends.grain)}</div>
                    </div>
                    <div class="kpi-value" title="{html.escape(value_title)}">{html.escape(value)}</div>
                    <div
                        class="kpi-comparison"
                        style="color:{comparison_color};"
                        title="{html.escape(comparison_detail)}"
                    >{html.escape(comparison)}</div>
                    <div class="kpi-footer">{html.escape(footer)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if figure is None:
                st.markdown(
                    '<div class="kpi-spark-empty">No trend in this period</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.plotly_chart(
                    figure,
                    width="stretch",
                    height=78,
                    theme=None,
                    config={
                        "displayModeBar": False,
                        "responsive": True,
                    },
                    key=chart_key,
                )


revenue_comparison, revenue_color = format_period_comparison(
    revenue_change,
    metric="revenue",
    current=total_revenue,
    previous=previous_revenue,
)
profit_comparison, profit_color = format_period_comparison(
    profit_change,
    metric="profit",
    current=total_profit,
    previous=previous_profit,
)
margin_comparison, margin_color = format_period_comparison(
    margin_change,
    unit=" pp",
    metric="margin",
)
orders_comparison, orders_color = format_period_comparison(
    orders_change,
    metric="orders",
    current=total_orders,
    previous=previous_orders,
)

k1, k2, k3, k4 = st.columns(4, gap="small", wrap=True)

render_kpi_card(
    k1,
    card_key="kpi_revenue",
    label="Total Revenue",
    value=format_headline_currency(total_revenue),
    value_title=f"Exact revenue: {format_exact_currency(total_revenue)}",
    accent="indigo",
    comparison=revenue_comparison,
    comparison_color=revenue_color,
    footer="Gross sales generated",
    figure=build_sparkline(trends.revenue, "revenue"),
    chart_key="sparkline_revenue",
)

render_kpi_card(
    k2,
    card_key="kpi_profit",
    label="Total Profit",
    value=format_headline_currency(total_profit),
    value_title=f"Exact profit: {format_exact_currency(total_profit)}",
    accent="emerald",
    comparison=profit_comparison,
    comparison_color=profit_color,
    footer="Reported transaction profit",
    figure=build_sparkline(trends.profit, "profit"),
    chart_key="sparkline_profit",
)

render_kpi_card(
    k3,
    card_key="kpi_margin",
    label="Profit Margin",
    value=f"{profit_margin:.2f}%",
    value_title="Profit divided by revenue",
    accent="violet",
    comparison=margin_comparison,
    comparison_color=margin_color,
    footer="Profit as a share of revenue",
    figure=build_sparkline(trends.margin, "margin"),
    chart_key="sparkline_margin",
)

render_kpi_card(
    k4,
    card_key="kpi_orders",
    label="Total Orders",
    value=f"{total_orders:,}",
    value_title=f"Exact distinct orders: {total_orders:,}",
    accent="sky",
    comparison=orders_comparison,
    comparison_color=orders_color,
    footer="Unique customer orders",
    figure=build_sparkline(trends.orders, "orders"),
    chart_key="sparkline_orders",
)

if comparison_ready:
    st.caption(comparison_detail)

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
        width="stretch"
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
        width="stretch"
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
    width="stretch"
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