"""Page 3: Revenue Driver Analysis (Revenue = Distinct Orders × Average Order Value)."""

import streamlit as st

from cause import config
from cause.decomposition import decompose_revenue, decompose_revenue_by
from cause.insights import driver_finding, format_change, format_pct
from cause.metrics import Metric, compare_kpis, compute_kpis, monthly_trend
from ui import theme
from ui.chart_data import driver_display, driver_effects_long, driver_waterfall_steps, kpi_display
from ui.charts import effects_chart, show_chart, trend_chart, waterfall_chart, windows_caption
from ui.components import (
    callout,
    causation_note,
    empty_state,
    finding_callouts,
    kpi_card_html,
    kpi_cards,
    kpi_row,
    numeric_table,
    page_intro,
    section,
)
from ui.state import get_context

DRIVER_DIM_KEY = "drv_dimension"
DRIVER_FORMATS = {
    "Revenue (previous)": "money", "Revenue (current)": "money", "Revenue change": "money_change",
    "Orders (previous)": "count", "Orders (current)": "count",
    "AOV (previous)": "money", "AOV (current)": "money",
    "Volume effect": "money_change", "AOV effect": "money_change",
}


def render() -> None:
    ctx = get_context()
    page_intro(
        "Revenue Driver Analysis",
        "Revenue = distinct orders × average order value (AOV). The revenue change is split into an "
        "order-volume effect and an order-value effect that add up exactly.",
        ctx,
    )
    if not ctx.is_ready:
        return
    if not ctx.is_comparable:
        empty_state("No comparison available",
                    "Driver analysis needs orders in both periods. Choose another period, comparison "
                    "or wider filters.")
        return

    c = ctx.comparison
    changes = compare_kpis(compute_kpis(ctx.current), compute_kpis(ctx.previous))
    d = decompose_revenue(ctx.current, ctx.previous)
    rev = changes[Metric.REVENUE]
    kpi_cards([
        kpi_display(changes[Metric.REVENUE], c.comparison.label, "Revenue"),
        kpi_display(changes[Metric.ORDERS], c.comparison.label, "Distinct orders"),
        kpi_display(changes[Metric.AOV], c.comparison.label, "Average order value"),
    ])
    kpi_row([
        kpi_card_html("Revenue change", format_change(Metric.REVENUE, d.revenue_change),
                      format_pct(rev.pct_change) if rev.pct_change == rev.pct_change else rev.unavailable_note,
                      _tone(d.revenue_change),
                      footnote="Volume effect + order value effect"),
        kpi_card_html("Order volume effect", format_change(Metric.REVENUE, d.volume_effect),
                      tone=_tone(d.volume_effect),
                      footnote="Change in orders × average AOV of both periods"),
        kpi_card_html("Order value effect", format_change(Metric.REVENUE, d.aov_effect),
                      tone=_tone(d.aov_effect),
                      footnote="Change in AOV × average orders of both periods"),
    ])

    with section("Revenue bridge", "Comparison revenue plus the two effects equals current revenue "
                 "(midpoint decomposition, no unexplained remainder)."):
        show_chart(waterfall_chart(driver_waterfall_steps(d), "Revenue"), height=360, key="drv_waterfall")
        finding_callouts([driver_finding(d)])

    _trend_section(ctx)
    _dimension_section(ctx)
    causation_note()


def _tone(v: float) -> str:
    return "positive" if v > 0 else ("negative" if v < 0 else "neutral")


def _trend_section(ctx) -> None:
    trend = monthly_trend(ctx.filtered)
    with section("Monthly trends", windows_caption(
            ctx, "Revenue, distinct orders and AOV by month, shown separately because their scales differ.")):
        cols = st.columns(3, gap="medium")
        specs = [
            ("revenue", "Revenue", theme.CATEGORICAL[0], dict(money=True)),
            ("orders", "Distinct orders", theme.CATEGORICAL[2], dict(money=False)),
            ("aov", "Average order value", theme.CATEGORICAL[1], dict(money=True)),
        ]
        for col, (field, name, color, kw) in zip(cols, specs):
            with col:
                st.markdown(f"**{name}**")
                show_chart(trend_chart(trend, ctx, [(field, name, color)], **kw), height=260, key=f"drv_trend_{field}")
        st.caption("Months with no orders show no AOV (it is undefined there).")


def _dimension_section(ctx) -> None:
    with section("Drivers by group", "Volume and order-value effects within each group."):
        st.session_state.setdefault(DRIVER_DIM_KEY, "Market")
        dim_label = st.selectbox("Group by", list(config.DIMENSIONS), key=DRIVER_DIM_KEY)
        column = config.DIMENSIONS[dim_label]
        table = decompose_revenue_by(ctx.current, ctx.previous, dim_label)
        if table.empty:
            empty_state("No groups to show", "No orders match the current filters.")
            return
        callout(
            "How to read group effects",
            "Each row's volume and order-value effects add up to that group's revenue change, and the "
            "revenue changes add up to the total. The group effects do not necessarily add up to the overall "
            "volume and order-value effects: an order can appear in several groups (orders here are actual "
            "distinct orders containing the group), and the overall AOV also reflects the mix of groups.",
            "caution",
        )
        long = driver_effects_long(table, column)
        show_chart(effects_chart(long, {"Volume effect": theme.CATEGORICAL[2], "AOV effect": theme.CATEGORICAL[1]},
                                 "USD", money=True),
                   height=max(260, 34 * long["group"].nunique() + 90), key="drv_group_effects")
        numeric_table(driver_display(table, column), DRIVER_FORMATS, key="drv_group_table")
        st.caption("Ranked by size of revenue change. Groups new in one period have an undefined AOV there, "
                   "so their whole change is a volume effect.")


render()
