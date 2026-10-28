"""Page 1: Metric Overview."""

import streamlit as st

from cause.contribution import additive_contribution, margin_decomposition
from cause.insights import contributor_findings, headline_finding, is_significant, margin_findings
from cause.metrics import Metric, compare_kpis, compute_kpis, monthly_trend
from ui.chart_data import group_performance, kpi_display, loss_making
from ui.charts import (
    PROFIT_COLOR,
    REVENUE_COLOR,
    grouped_bars,
    show_chart,
    trend_chart,
    windows_caption,
)
from ui.components import (
    callout,
    causation_note,
    empty_state,
    finding_callouts,
    kpi_cards,
    numeric_table,
    page_intro,
    section,
)
from ui.state import get_context

KPI_METRICS = [
    (Metric.REVENUE, "Total revenue"),
    (Metric.PROFIT, "Total profit"),
    (Metric.ORDERS, "Distinct orders"),
    (Metric.MARGIN, "Profit margin"),
]


def render() -> None:
    ctx = get_context()
    page_intro(
        "Metric Overview",
        "Revenue, profit, orders and margin for the selected period compared with the "
        "comparison period. All figures follow the sidebar filters.",
        ctx,
    )
    if not ctx.is_ready:
        return
    if ctx.current.empty:
        empty_state("No orders in the current period",
                    "Choose another period or widen the filters in the sidebar.")
        return

    c = ctx.comparison
    changes = compare_kpis(compute_kpis(ctx.current), compute_kpis(ctx.previous))
    kpi_cards([kpi_display(changes[m], c.comparison.label, label) for m, label in KPI_METRICS])
    _notable_changes(changes, c.label)

    with section("Monthly revenue and profit", windows_caption(
            ctx, "Monthly totals for the filtered data. Months without orders stay on the axis.")):
        trend = monthly_trend(ctx.filtered)
        show_chart(trend_chart(trend, ctx, [("revenue", "Revenue", REVENUE_COLOR),
                                            ("profit", "Profit", PROFIT_COLOR)]),
                   height=340, key="ov_trend")

    left, right = st.columns(2, gap="medium")
    with left:
        _market_section(ctx)
    with right:
        _category_section(ctx)
    _segment_section(ctx)
    _insights_section(ctx, changes)


def _notable_changes(changes, label: str) -> None:
    flagged = [m for m, _ in KPI_METRICS if is_significant(changes[m])]
    if flagged and changes[Metric.REVENUE].previous:
        names = ", ".join(m.label.lower() for m in flagged)
        callout("Notable changes",
                f"{names.capitalize()} moved by at least 10% (or 1 percentage point for margin) "
                f"for {label}. Cards marked 'Notable' show these metrics.", "caution")


def _market_section(ctx) -> None:
    perf = group_performance(ctx.current, ctx.previous, "market")
    with section("Revenue and profit by market", f"Current period ({ctx.comparison.current.label}), "
                 "ranked by revenue. Hover for values."):
        if perf.empty:
            empty_state("No market data", "No orders match the current filters.")
            return
        show_chart(grouped_bars(perf, "market", [("revenue_current", "Revenue", REVENUE_COLOR),
                                                ("profit_current", "Profit", PROFIT_COLOR)]),
                   height=max(260, 46 * len(perf) + 80), key="ov_market")


def _category_section(ctx) -> None:
    perf = group_performance(ctx.current, ctx.previous, "category")
    with section("Category performance", "Current period revenue and profit by category."):
        if perf.empty:
            empty_state("No category data", "No orders match the current filters.")
            return
        show_chart(grouped_bars(perf, "category", [("revenue_current", "Revenue", REVENUE_COLOR),
                                                  ("profit_current", "Profit", PROFIT_COLOR)]),
                   height=max(260, 46 * len(perf) + 80), key="ov_category")
        losing = perf[perf["profit_current"] < 0]
        if not losing.empty:
            callout("Loss-making categories",
                    "; ".join(f"{r.category}: profit ${r.profit_current:,.0f} on revenue ${r.revenue_current:,.0f}"
                              for r in losing.itertuples()), "negative")
        subs = loss_making(ctx.current, "sub_category")
        if not subs.empty:
            listed = "; ".join(f"{r.sub_category} (${r.profit:,.0f})" for r in subs.head(5).itertuples())
            more = f" and {len(subs) - 5} more" if len(subs) > 5 else ""
            callout(f"{len(subs)} loss-making sub-categor{'y' if len(subs) == 1 else 'ies'}",
                    f"Negative total profit in the current period: {listed}{more}.", "negative")
        elif losing.empty:
            callout("No loss-making categories", "Every category and sub-category made a profit "
                    "in the current period.", "positive")


def _segment_section(ctx) -> None:
    perf = group_performance(ctx.current, ctx.previous, "segment")
    with section("Customer segment performance",
                 f"{ctx.comparison.current.label} vs {ctx.comparison.comparison.label}. "
                 "Margin is each segment's profit ÷ revenue; its change is in percentage points."):
        if perf.empty:
            empty_state("No segment data", "No orders match the current filters.")
            return
        table = perf.rename(columns={
            "segment": "Segment",
            "revenue_current": "Revenue",
            "revenue_pct_change": "Revenue change %",
            "profit_current": "Profit",
            "profit_previous": "Profit (previous)",
            "margin_current": "Margin %",
            "margin_change_pp": "Margin change (pp)",
        })
        table["Revenue change %"] = table["Revenue change %"] * 100
        table["Margin %"] = table["Margin %"] * 100
        numeric_table(
            table[["Segment", "Revenue", "Revenue change %", "Profit", "Profit (previous)",
                   "Margin %", "Margin change (pp)"]],
            {"Revenue": "money", "Revenue change %": "pct", "Profit": "money",
             "Profit (previous)": "money", "Margin %": "plain_pct", "Margin change (pp)": "pp"},
            key="ov_segments",
        )


def _insights_section(ctx, changes) -> None:
    with section("Performance insights", "Generated from the figures above."):
        if not ctx.is_comparable:
            empty_state("No comparison available",
                        "Insights need orders in both periods. Choose another period or comparison.")
            return
        findings = [headline_finding(changes[m], ctx.comparison.label)
                    for m, _ in KPI_METRICS if is_significant(changes[m])]
        findings += contributor_findings(additive_contribution(ctx.current, ctx.previous, "Market", "revenue"), n=2)
        findings += margin_findings(margin_decomposition(ctx.current, ctx.previous, "Category"))
        if findings:
            finding_callouts(findings)
        else:
            callout("No notable changes", "No metric moved by 10% or more (1 pp for margin).", "neutral")
        causation_note()


render()
