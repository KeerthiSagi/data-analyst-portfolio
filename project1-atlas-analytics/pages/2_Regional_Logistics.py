import html

import pandas as pd
import streamlit as st

from utils.data_loader import load_superstore_data
from utils.kpi_metrics import format_exact_currency, format_headline_currency
from utils.logistics_analytics import (
    REGION_SHIP_METRICS,
    SHIP_MODE_METRICS,
    TREND_METRICS as LOGISTICS_TREND_METRICS,
    aggregate_processing_time,
    aggregate_regional_shipping_cost,
    aggregate_shipping_modes,
    aggregate_shipping_trends,
    build_cost_margin_scatter,
    build_processing_by_mode,
    build_processing_distribution,
    build_regional_shipping_chart,
    build_shipping_mode_chart,
    build_shipping_trend,
    calculate_logistics_kpis,
    filter_shipping_modes,
    generate_logistics_insights,
    processing_caption,
)
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
from utils.navigation import (
    render_page_header,
    render_project_nav,
    render_section_header,
    render_section_nav,
    render_sidebar_brand,
)
from utils.theme import PLOTLY_CONFIG, initialize_theme


st.set_page_config(
    page_title="Regional Performance | Atlas Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

initialize_theme()

df = load_superstore_data()


# ============================================================
# SIDEBAR FILTERS
# ============================================================

render_sidebar_brand()
render_project_nav("regional")

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

render_page_header(
    eyebrow="GEOGRAPHIC INTELLIGENCE / REGIONAL REPORTING",
    title="Regional Performance Intelligence",
    subtitle=(
        "Revenue, profitability, and commercial performance across global "
        "business regions, plus shipping and logistics intelligence."
    ),
)
render_section_nav(
    [
        ("regional-performance", "Regional Performance"),
        ("shipping-logistics", "Shipping & Logistics"),
    ]
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


def render_chart(figure, empty_message, chart_key):
    if figure is None:
        st.info(empty_message)
        return
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        config=PLOTLY_CONFIG,
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
# KPI CARDS
# ============================================================

render_section_header(
    anchor="regional-performance",
    eyebrow="REGIONAL PERFORMANCE",
    title="Regional commercial results",
    caption="Page filters apply to every regional view below.",
)

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

st.write("")


# ============================================================
# SHIPPING & LOGISTICS INTELLIGENCE
# ============================================================

render_section_header(
    anchor="shipping-logistics",
    eyebrow="SHIPPING & LOGISTICS INTELLIGENCE",
    title="Shipping Cost, Mode Performance, and Order-to-Shipment Processing",
    caption=(
        "Logistics metrics use the same page filters above. "
        "Order-to-shipment days are Ship Date minus Order Date — processing time until "
        "shipment, not delivery time to the customer. Shipping cost is not subtracted "
        "from recorded profit."
    ),
)

ship_modes = sorted(filtered["Ship_Mode"].dropna().unique().tolist()) if "Ship_Mode" in filtered.columns else []
selected_ship_modes = st.multiselect(
    "Shipping Mode (logistics section only)",
    options=ship_modes,
    default=ship_modes,
    help="Scopes only the Shipping & Logistics sections. Page-wide regional analytics stay unchanged.",
)
logistics_df = filter_shipping_modes(filtered, selected_ship_modes)

if logistics_df.empty:
    st.warning("No logistics data available for the selected shipping modes.")
else:
    logistics_kpis = calculate_logistics_kpis(logistics_df)
    shipping_modes = aggregate_shipping_modes(logistics_df)
    regional_shipping = aggregate_regional_shipping_cost(logistics_df)
    processing = aggregate_processing_time(logistics_df)
    shipping_trends = aggregate_shipping_trends(logistics_df, start_date, end_date)
    logistics_insights = generate_logistics_insights(
        shipping_modes,
        regional_shipping,
        logistics_kpis,
    )

    def display_days(value):
        if value is None or pd.isna(value):
            return "Unavailable"
        return f"{float(value):.2f}"

    def display_rate(value):
        if value is None or pd.isna(value):
            return "Unavailable"
        return f"{float(value):.1f}%"

    logistics_cards = st.columns(4, gap="small", wrap=True)
    render_kpi_card(
        logistics_cards[0],
        card_key="kpi_ship_cost",
        label="Total Shipping Cost",
        value=display_currency(logistics_kpis["shipping_cost"]),
        value_title=exact_title("Exact shipping cost", logistics_kpis["shipping_cost"]),
        footer="Sum of Shipping_Cost in the logistics view",
    )
    render_kpi_card(
        logistics_cards[1],
        card_key="kpi_ship_ratio",
        label="Shipping Cost Ratio",
        value=display_margin(logistics_kpis["shipping_cost_ratio"]),
        value_title="Shipping cost divided by revenue",
        footer="Shipping cost as a share of revenue",
    )
    render_kpi_card(
        logistics_cards[2],
        card_key="kpi_ship_days",
        label="Avg Order-to-Shipment Days",
        value=display_days(logistics_kpis["avg_processing_days"]),
        value_title="Mean days per valid order line item",
        footer="Mean days per valid line item",
    )
    render_kpi_card(
        logistics_cards[3],
        card_key="kpi_same_day",
        label="Same-Day Shipment Rate",
        value=display_rate(logistics_kpis["same_day_rate"]),
        value_title="Share of valid line items shipped the same day",
        footer="Line items where Ship Date equals Order Date",
    )

    st.write("")
    st.subheader("Shipping Mode Performance")
    mode_metric = selected_metric(
        "Shipping mode metric",
        options=list(SHIP_MODE_METRICS),
        default="Shipping Cost",
        widget_key="logistics_mode_metric",
    )
    st.caption(
        "Modes differ in order mix and basket size. "
        "A higher shipping cost does not by itself mean weaker profitability."
    )
    render_chart(
        build_shipping_mode_chart(shipping_modes, mode_metric),
        "No shipping-mode values are available for this metric.",
        "logistics_mode_chart",
    )

    st.write("")
    ship_left, ship_right = st.columns(2, gap="medium", wrap=True)
    with ship_left:
        st.subheader("Regional Shipping Cost Analysis")
        region_ship_metric = selected_metric(
            "Regional shipping metric",
            options=list(REGION_SHIP_METRICS),
            default="Total Shipping Cost",
            widget_key="logistics_region_metric",
        )
        st.caption(
            "Total shipping cost reflects volume. Shipping cost ratio shows shipping "
            "expense relative to revenue. The ratio is not a profitability measure."
        )
        render_chart(
            build_regional_shipping_chart(regional_shipping, region_ship_metric),
            "Regional shipping values are unavailable for this selection.",
            "logistics_region_chart",
        )
    with ship_right:
        st.subheader("Shipping Cost & Profitability")
        st.caption(
            "Observed association between shipping cost ratio and profit margin by mode. "
            "Shipping cost is not subtracted from recorded profit, and the chart does not "
            "imply causation."
        )
        render_chart(
            build_cost_margin_scatter(shipping_modes),
            "Cost and margin comparison is unavailable for this selection.",
            "logistics_scatter_chart",
        )

    st.write("")
    st.subheader("Order-to-Shipment Processing Time")
    st.caption(processing_caption(processing))
    process_left, process_right = st.columns(2, gap="medium", wrap=True)
    with process_left:
        render_chart(
            build_processing_by_mode(processing["by_mode"]),
            "Average processing days are unavailable for this selection.",
            "logistics_processing_mode_chart",
        )
    with process_right:
        render_chart(
            build_processing_distribution(processing["distribution"]),
            "Processing-time distribution is unavailable for this selection.",
            "logistics_processing_dist_chart",
        )
    if logistics_kpis["median_processing_days"] is not None:
        st.caption(
            f"Median order-to-shipment days: {logistics_kpis['median_processing_days']:.2f} "
            f"across {logistics_kpis['valid_intervals']:,} valid line items."
        )

    st.write("")
    st.subheader("Shipping & Logistics Trends")
    logistics_trend_metric = selected_metric(
        "Logistics trend metric",
        options=list(LOGISTICS_TREND_METRICS),
        default="Total Shipping Cost",
        widget_key="logistics_trend_metric",
    )
    st.caption(
        f"{str(shipping_trends['grain'].iloc[0]).capitalize()} totals for the selected "
        "reporting period. Shipping cost ratio uses aggregated cost divided by aggregated "
        "revenue. Average processing days use valid line-item intervals only."
    )
    render_chart(
        build_shipping_trend(shipping_trends, logistics_trend_metric),
        "No logistics trend values are available for this metric.",
        "logistics_trend_chart",
    )

    st.write("")
    st.subheader("Logistics Business Insights")
    if logistics_insights:
        logistics_insight_columns = st.columns(min(len(logistics_insights), 2), gap="small", wrap=True)
        for index, note in enumerate(logistics_insights):
            with logistics_insight_columns[index % 2]:
                st.markdown(
                    f"""
                    <div class="insight-card">
                        <div class="insight-title">{html.escape(note["title"])}</div>
                        <div class="insight-body">{html.escape(note["body"])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.divider()
st.caption(
    "ATLAS ANALYTICS | Global Superstore Dataset | "
    "Historical Reporting: 2011–2014"
)
