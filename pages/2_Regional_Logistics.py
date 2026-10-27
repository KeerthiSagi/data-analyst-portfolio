import html

import pandas as pd
import streamlit as st

from utils.data_loader import load_superstore_data
from utils.kpi_metrics import format_exact_currency, format_headline_currency
from utils.regional_analytics import (
    DEFAULT_TREND_REGIONS,
    METRIC_SPECS,
    TREND_METRICS,
    aggregate_regional_performance,
    aggregate_regional_trends,
    build_margin_chart,
    build_regional_comparison,
    build_regional_trend,
    build_revenue_contribution,
    calculate_regional_kpis,
    default_trend_regions,
    filter_orders,
    generate_regional_insights,
    profit_contribution_caption,
    profitability_highlights,
    trend_caption,
)
from utils.theme import initialize_theme


st.set_page_config(
    page_title="Regional Performance Intelligence | Atlas Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_theme()

df = load_superstore_data()


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.markdown("### Report Filters")

min_date = df["Order_Date"].min().date()
max_date = df["Order_Date"].max().date()
date_selection = st.sidebar.date_input(
    "Reporting Period",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

regions = sorted(df["Region"].dropna().unique().tolist())
categories = sorted(df["Category"].dropna().unique().tolist())
segments = sorted(df["Segment"].dropna().unique().tolist())

selected_regions = st.sidebar.multiselect("Region", options=regions, default=regions)
selected_categories = st.sidebar.multiselect(
    "Product Category",
    options=categories,
    default=categories,
)
selected_segments = st.sidebar.multiselect(
    "Customer Segment",
    options=segments,
    default=segments,
)

if isinstance(date_selection, (tuple, list)) and len(date_selection) == 2:
    start_date, end_date = date_selection
else:
    start_date, end_date = min_date, max_date

filtered = filter_orders(
    df,
    start=start_date,
    end=end_date,
    regions=selected_regions,
    categories=selected_categories,
    segments=selected_segments,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="dashboard-eyebrow">
        GEOGRAPHIC INTELLIGENCE / REGIONAL REPORTING
    </div>
    <div class="dashboard-title">
        Regional Performance Intelligence
    </div>
    <div class="dashboard-subtitle">
        Revenue, profitability, and commercial performance
        across global business regions.
    </div>
    """,
    unsafe_allow_html=True,
)

if filtered.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

kpis = calculate_regional_kpis(filtered)
performance = aggregate_regional_performance(filtered)
highlights = profitability_highlights(performance)


def display_margin(value):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{float(value):.2f}%"


def display_currency(value):
    if value is None or pd.isna(value):
        return "Unavailable"
    return format_headline_currency(value)


def display_orders(value):
    return f"{int(value):,}"


def exact_title(label, value):
    if value is None or pd.isna(value):
        return f"{label} is unavailable"
    return f"{label}: {format_exact_currency(value)}"


def render_kpi_card(column, *, card_key, label, value, value_title, footer):
    with column:
        with st.container(border=True, key=card_key, height="stretch", gap="xxsmall"):
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


def render_chart(figure, empty_message, chart_key):
    if figure is None:
        st.info(empty_message)
        return
    st.plotly_chart(figure, width="stretch", theme=None, key=chart_key)


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
# KPI CARDS
# ============================================================

cards = st.columns(4, gap="small", wrap=True)
render_kpi_card(
    cards[0],
    card_key="kpi_revenue",
    label="Total Revenue",
    value=display_currency(kpis["revenue"]),
    value_title=exact_title("Exact revenue", kpis["revenue"]),
    footer="Gross sales in the selected view",
)
render_kpi_card(
    cards[1],
    card_key="kpi_profit",
    label="Total Profit",
    value=display_currency(kpis["profit"]),
    value_title=exact_title("Exact profit", kpis["profit"]),
    footer="Reported transaction profit",
)
render_kpi_card(
    cards[2],
    card_key="kpi_margin",
    label="Profit Margin",
    value=display_margin(kpis["margin"]),
    value_title="Profit divided by revenue",
    footer="Aggregate profit as a share of revenue",
)
render_kpi_card(
    cards[3],
    card_key="kpi_orders",
    label="Unique Orders",
    value=display_orders(kpis["orders"]),
    value_title=f"Distinct Order_ID values: {kpis['orders']:,}",
    footer="Distinct orders in the selected view",
)

st.write("")


# ============================================================
# REGIONAL PERFORMANCE COMPARISON
# ============================================================

st.subheader("Regional Performance Comparison")
comparison_metric = selected_metric(
    "Comparison metric",
    options=list(METRIC_SPECS),
    default="Revenue",
    widget_key="regional_comparison_metric",
)
st.caption("Each chart uses one metric so dollars and percentages stay on separate axes.")
render_chart(
    build_regional_comparison(performance, comparison_metric),
    "No regional values are available for this metric.",
    "regional_comparison_chart",
)


# ============================================================
# CONTRIBUTION AND PROFITABILITY
# ============================================================

st.write("")
left, right = st.columns(2, gap="medium", wrap=True)

with left:
    st.subheader("Revenue Contribution by Region")
    if kpis["revenue"] == 0:
        st.caption("Revenue share is unavailable because filtered revenue is zero.")
    else:
        top = performance.sort_values("revenue", ascending=False).head(5)
        mix = " · ".join(
            f"{row.region} {row.revenue_share:.1f}%"
            for row in top.itertuples()
            if pd.notna(row.revenue_share)
        )
        st.caption(f"Top share of filtered revenue: {mix}")
    render_chart(
        build_revenue_contribution(performance),
        "Revenue contribution is unavailable for this selection.",
        "regional_contribution_chart",
    )

with right:
    st.subheader("Regional Profitability Health")
    st.caption(profit_contribution_caption(performance))
    render_chart(
        build_margin_chart(performance),
        "Profit margin is unavailable because region revenue is zero.",
        "regional_margin_chart",
    )

if highlights:
    note_columns = st.columns(min(len(highlights), 2), gap="small", wrap=True)
    for index, note in enumerate(highlights):
        with note_columns[index % 2]:
            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-title">{html.escape(note["title"])}</div>
                    <div class="insight-body">{html.escape(note["body"])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.write("")


# ============================================================
# REGIONAL TRENDS
# ============================================================

st.subheader("Regional Performance Trends")
available_regions = performance["region"].tolist()
trend_default = [name for name in default_trend_regions(performance) if name in available_regions]
trend_regions = st.multiselect(
    "Trend chart regions",
    options=available_regions,
    default=trend_default,
    help="Defaults to the top five regions by filtered revenue. This control does not change the page filters.",
)
# Insights use the default top regions so clearing the chart control does not erase trend context.
insight_trends = aggregate_regional_trends(
    filtered,
    start_date,
    end_date,
    regions=trend_default or available_regions[:DEFAULT_TREND_REGIONS],
)
insights = generate_regional_insights(performance, insight_trends)

if not trend_regions:
    st.info("Select at least one region to display the trend chart.")
else:
    trends = aggregate_regional_trends(filtered, start_date, end_date, regions=trend_regions)
    trend_metric = selected_metric(
        "Trend metric",
        options=list(TREND_METRICS),
        default="Revenue",
        widget_key="regional_trend_metric",
    )
    st.caption(trend_caption(trends))
    render_chart(
        build_regional_trend(trends, trend_metric),
        "No trend values are available for this metric.",
        "regional_trend_chart",
    )

st.write("")


# ============================================================
# DYNAMIC INSIGHTS
# ============================================================

st.subheader("Regional Business Insights")
if insights:
    insight_columns = st.columns(min(len(insights), 2), gap="small", wrap=True)
    for index, note in enumerate(insights):
        with insight_columns[index % 2]:
            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-title">{html.escape(note["title"])}</div>
                    <div class="insight-body">{html.escape(note["body"])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.write("")


# ============================================================
# COMPARISON TABLE
# ============================================================

st.subheader("Regional Comparison Detail")
st.caption(
    "Distinct orders are counted inside each region. An order that appears in more "
    "than one region is counted in each of those rows, so the order column is not "
    "expected to add up to the page total."
)

table = performance.rename(
    columns={
        "region": "Region",
        "revenue": "Revenue",
        "revenue_share": "Revenue Share",
        "profit": "Profit",
        "margin": "Profit Margin",
        "orders": "Unique Orders",
        "aov": "Average Order Value",
        "line_items": "Order Line Items",
    }
)[
    [
        "Region",
        "Revenue",
        "Revenue Share",
        "Profit",
        "Profit Margin",
        "Unique Orders",
        "Average Order Value",
        "Order Line Items",
    ]
]

st.dataframe(
    table,
    width="stretch",
    hide_index=True,
    column_config={
        "Revenue": st.column_config.NumberColumn(format="$%,.2f"),
        "Revenue Share": st.column_config.NumberColumn(format="%.1f%%"),
        "Profit": st.column_config.NumberColumn(format="$%,.2f"),
        "Profit Margin": st.column_config.NumberColumn(format="%.2f%%"),
        "Unique Orders": st.column_config.NumberColumn(format="%,d"),
        "Average Order Value": st.column_config.NumberColumn(format="$%,.2f"),
        "Order Line Items": st.column_config.NumberColumn(format="%,d"),
    },
)

st.divider()
st.caption(
    "ATLAS ANALYTICS | Global Superstore Dataset | "
    "Historical Reporting: 2011–2014"
)
