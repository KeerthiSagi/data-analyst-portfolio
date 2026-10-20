import html

import streamlit as st
import pandas as pd

from utils.theme import initialize_theme
from utils.data_loader import load_superstore_data
from utils.kpi_metrics import (
    aggregate_kpi_trends,
    build_sparkline,
    format_display_date,
    format_exact_currency,
    format_headline_currency,
    format_period_comparison,
    prior_period_caption,
)
from utils.executive_analytics import (
    GROUP_METRICS,
    TREND_BOTH,
    TREND_MARGIN,
    TREND_PROFIT,
    TREND_REVENUE,
    build_executive_insights,
    build_performance_bar,
    build_trend_figure,
    discount_margin_bands,
    format_revenue_mix,
    metric_has_negative,
    summarize_groups,
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
# EXECUTIVE ANALYTICS
# Reuse the sparkline buckets for the trend chart so margin,
# frequency, and gaps stay consistent with the KPI cards.
# ============================================================

category_summary = summarize_groups(filtered_df, "Category")
region_summary = summarize_groups(filtered_df, "Region")
discount_bands = discount_margin_bands(filtered_df)
prior_window = None
if comparison_ready:
    prior_window = (
        f"{format_display_date(previous_start)} – {format_display_date(previous_end)}"
    )

insights = build_executive_insights(
    categories=category_summary,
    regions=region_summary,
    comparison_ready=comparison_ready,
    revenue_change=revenue_change,
    margin_change=margin_change,
    prior_window=prior_window,
    discount_bands=discount_bands,
)


def render_chart(figure, empty_message, chart_key):
    if figure is None:
        st.info(empty_message)
        return
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key=chart_key,
    )


def selected_metric(label, options, default, widget_key):
    choice = st.segmented_control(
        label,
        options=options,
        default=default,
        key=widget_key,
        width="content",
        wrap=True,
    )
    return choice or default


# ============================================================
# REVENUE & PROFIT TRENDS
# ============================================================

st.subheader("Revenue & Profit Trends")

trend_metric = selected_metric(
    "Trend metric",
    options=[TREND_BOTH, TREND_REVENUE, TREND_PROFIT, TREND_MARGIN],
    default=TREND_BOTH,
    widget_key="exec_trend_metric",
)

trend_note = (
    f"{trends.grain} buckets. Profit margin is period profit divided by period revenue. "
    "Periods with no revenue are left blank on the margin series."
)
if trend_metric == TREND_BOTH:
    trend_note += " Revenue and profit use separate axes because their scales differ."
st.caption(trend_note)

render_chart(
    build_trend_figure(trends, trend_metric),
    "No trend points are available for this metric.",
    "exec_trend_chart",
)


# ============================================================
# REVENUE COMPOSITION
# ============================================================

st.write("")
st.subheader("Revenue Composition")

category_metric = selected_metric(
    "Category metric",
    options=list(GROUP_METRICS),
    default=TREND_REVENUE,
    widget_key="exec_category_metric",
)
st.caption(format_revenue_mix(category_summary))

render_chart(
    build_performance_bar(category_summary, category_metric, orientation="v"),
    "No category values are available for this metric.",
    "exec_category_chart",
)


# ============================================================
# GEOGRAPHIC REVENUE PERFORMANCE
# ============================================================

st.write("")
st.subheader("Geographic Revenue Performance")

region_metric = selected_metric(
    "Region metric",
    options=list(GROUP_METRICS),
    default=TREND_REVENUE,
    widget_key="exec_region_metric",
)

region_note = f"Regions ranked by {region_metric.lower()}."
if metric_has_negative(region_summary, region_metric):
    region_note += " Red bars are negative values."
st.caption(region_note)

render_chart(
    build_performance_bar(region_summary, region_metric, orientation="h"),
    "No regional values are available for this metric.",
    "exec_region_chart",
)


# ============================================================
# EXECUTIVE INSIGHTS
# ============================================================

st.write("")
st.subheader("Executive Insights")

if not insights:
    st.info("No executive insights are available for this selection.")
else:
    insight_columns = st.columns(2, gap="small", wrap=True)
    for index, insight in enumerate(insights):
        with insight_columns[index % 2]:
            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-title">{html.escape(insight.title)}</div>
                    <div class="insight-body">{html.escape(insight.body)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "ATLAS ANALYTICS | Global Superstore Dataset | "
    "Historical Reporting: 2011–2014"
)