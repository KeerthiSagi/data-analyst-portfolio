"""Customer-segment KPIs for the segment intelligence page.

Average order value is filtered revenue divided by distinct Order_ID values.
It is not the mean of line-item sales. Segment order counts are not additive
when one order contains more than one segment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.kpi_metrics import format_exact_currency


SEGMENT_COLORS = {
    "Consumer": "#4F46E5",
    "Corporate": "#8B5CF6",
    "Home Office": "#0EA5E9",
}

METRIC_SPECS = {
    "Revenue": ("revenue", "currency", "#4F46E5"),
    "Profit": ("profit", "currency", "#10B981"),
    "Profit Margin": ("margin", "percent", "#8B5CF6"),
    "Average Order Value": ("aov", "currency", "#0EA5E9"),
}

NEGATIVE_COLOR = "#DC2626"

PERFORMANCE_COLUMNS = [
    "segment",
    "revenue",
    "profit",
    "margin",
    "orders",
    "aov",
    "revenue_share",
    "profit_share",
]


def filter_orders(df, *, start, end, regions, categories, segments) -> pd.DataFrame:
    """Apply the segment-page filters without copying the source frame first."""

    if df.empty:
        return df.iloc[0:0]
    mask = (
        (df["Order_Date"].dt.date >= start)
        & (df["Order_Date"].dt.date <= end)
        & df["Region"].isin(regions)
        & df["Category"].isin(categories)
        & df["Segment"].isin(segments)
    )
    return df.loc[mask]


def calculate_segment_kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs for the current filter.

    Margin and average order value are None when the denominator is zero.
    """

    if df.empty:
        return {
            "revenue": 0.0,
            "profit": 0.0,
            "margin": None,
            "orders": 0,
            "aov": None,
        }

    revenue = float(df["Sales"].sum())
    profit = float(df["Profit"].sum())
    orders = int(df["Order_ID"].nunique())
    margin = revenue and profit / revenue * 100
    aov = orders and revenue / orders
    return {
        "revenue": revenue,
        "profit": profit,
        "margin": None if revenue == 0 else float(margin),
        "orders": orders,
        "aov": None if orders == 0 else float(aov),
    }


def calculate_segment_revenue_share(revenue: pd.Series) -> pd.Series:
    """Segment revenue as a percent of the filtered total. Zero total stays undefined."""

    total = float(revenue.sum())
    if total == 0:
        return pd.Series(np.nan, index=revenue.index, dtype="float64")
    return revenue / total * 100


def aggregate_segment_performance(df: pd.DataFrame) -> pd.DataFrame:
    """One row per segment with revenue, profit, margin, orders, and AOV.

    Profit share is withheld when total profit is zero or negative so a loss
    cannot appear as a normal contribution percentage.
    """

    if df.empty or "Segment" not in df.columns:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)

    grouped = (
        df.groupby("Segment", as_index=False)
        .agg(
            revenue=("Sales", "sum"),
            profit=("Profit", "sum"),
            orders=("Order_ID", "nunique"),
        )
        .rename(columns={"Segment": "segment"})
    )
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    grouped["aov"] = grouped["revenue"] / grouped["orders"].mask(grouped["orders"] == 0)
    grouped["revenue_share"] = calculate_segment_revenue_share(grouped["revenue"])
    total_profit = float(grouped["profit"].sum())
    if total_profit > 0:
        grouped["profit_share"] = grouped["profit"] / total_profit * 100
    else:
        grouped["profit_share"] = np.nan
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)


def calculate_segment_profitability(performance: pd.DataFrame) -> dict:
    """Leaders, laggards, losses, and high-revenue weak-margin segments."""

    empty = performance.empty
    valid_margin = performance.dropna(subset=["margin"]) if not empty else performance
    negative = performance.loc[performance["profit"] < 0] if not empty else performance
    high_revenue_low_margin = None
    if not empty and performance["revenue_share"].notna().any():
        overall_margin = _overall_margin(performance)
        candidates = valid_margin.loc[valid_margin["revenue_share"] >= 20]
        if overall_margin is not None and not candidates.empty:
            weaker = candidates.loc[candidates["margin"] < overall_margin]
            if not weaker.empty:
                high_revenue_low_margin = weaker.sort_values("margin").iloc[0]

    return {
        "highest_margin": None if valid_margin.empty else valid_margin.sort_values("margin").iloc[-1],
        "lowest_margin": None if valid_margin.empty else valid_margin.sort_values("margin").iloc[0],
        "negative_profit": negative,
        "high_revenue_low_margin": high_revenue_low_margin,
        "profit_share_available": not empty and bool(performance["profit_share"].notna().any()),
    }


def profitability_highlights(performance: pd.DataFrame) -> list[dict]:
    """Short, calculated notes for the profitability section."""

    if performance.empty:
        return [{"title": "No segment results", "body": "No transactions match the current filters."}]

    findings = calculate_segment_profitability(performance)
    notes = []
    highest = findings["highest_margin"]
    lowest = findings["lowest_margin"]
    if highest is not None:
        notes.append(
            {
                "title": "Highest margin",
                "body": (
                    f"{highest['segment']} has the highest profit margin at {highest['margin']:.2f}% "
                    f"on {format_exact_currency(highest['revenue'])} of revenue."
                ),
            }
        )
    if lowest is not None and (highest is None or lowest["segment"] != highest["segment"]):
        notes.append(
            {
                "title": "Lowest margin",
                "body": (
                    f"{lowest['segment']} has the lowest profit margin at {lowest['margin']:.2f}% "
                    f"on {format_exact_currency(lowest['revenue'])} of revenue."
                ),
            }
        )

    losses = findings["negative_profit"]
    if not losses.empty:
        names = ", ".join(losses.sort_values("profit")["segment"].astype(str))
        worst = losses.sort_values("profit").iloc[0]
        notes.append(
            {
                "title": "Negative profit",
                "body": (
                    f"{names} recorded negative profit. {worst['segment']} is the largest loss at "
                    f"{format_exact_currency(worst['profit'])} on {format_exact_currency(worst['revenue'])} "
                    "of revenue. Revenue scale does not make that segment profitable."
                ),
            }
        )

    weak = findings["high_revenue_low_margin"]
    if weak is not None and (highest is None or weak["segment"] != highest["segment"]):
        gap = float(highest["margin"] - weak["margin"]) if highest is not None else None
        gap_text = (
            f" That is {gap:.1f} percentage points below {highest['segment']}."
            if gap is not None
            else ""
        )
        share = "" if pd.isna(weak["revenue_share"]) else f"{weak['revenue_share']:.1f}% of revenue"
        notes.append(
            {
                "title": "Revenue without margin strength",
                "body": (
                    f"{weak['segment']} generates {share} at a {weak['margin']:.2f}% margin."
                    f"{gap_text} High revenue is not the same as a strong margin."
                ),
            }
        )
    return notes


def profit_contribution_caption(performance: pd.DataFrame) -> str:
    """Profit-share line, or an explicit reason it is withheld."""

    if performance.empty or not performance["profit_share"].notna().any():
        return "Profit contribution is withheld because total profit is not positive."
    parts = [
        f"{row['segment']} {row['profit_share']:.1f}%"
        for row in performance.sort_values("profit", ascending=False).to_dict("records")
        if pd.notna(row["profit_share"])
    ]
    return "Profit contribution: " + " · ".join(parts)


def build_segment_comparison(performance: pd.DataFrame, metric: str):
    """One-metric ranked bar chart. Dollars and percentages never share an axis."""

    spec = METRIC_SPECS.get(metric, METRIC_SPECS["Revenue"])
    return _ranked_bar(
        performance,
        column=spec[0],
        color=spec[2],
        kind=spec[1],
        axis_title=metric,
    )


def build_revenue_contribution(performance: pd.DataFrame):
    """Horizontal revenue bars. Share stays in the hover so the axis stays in dollars."""

    if performance.empty or not performance["revenue"].notna().any():
        return None
    if float(performance["revenue"].sum()) == 0:
        return None
    return _ranked_bar(
        performance,
        column="revenue",
        color="#4F46E5",
        kind="currency",
        axis_title="Revenue",
        color_by_segment=True,
    )


def build_margin_chart(performance: pd.DataFrame):
    """Profit-margin comparison. Negative margins use a distinct color."""

    return _ranked_bar(
        performance,
        column="margin",
        color="#8B5CF6",
        kind="percent",
        axis_title="Profit margin",
    )


def _ranked_bar(performance, column, color, kind, axis_title, color_by_segment=False):
    if performance.empty or column not in performance.columns:
        return None
    plot_df = performance.dropna(subset=[column]).sort_values(column, ascending=True)
    if plot_df.empty:
        return None

    colors = []
    for row in plot_df.to_dict("records"):
        if float(row[column]) < 0:
            colors.append(NEGATIVE_COLOR)
        elif color_by_segment:
            colors.append(SEGMENT_COLORS.get(row["segment"], color))
        else:
            colors.append(color)

    hover = [_hover(row) for row in plot_df.to_dict("records")]
    figure = go.Figure(
        data=[
            go.Bar(
                y=plot_df["segment"],
                x=plot_df[column],
                orientation="h",
                marker=dict(color=colors),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        height=min(420, max(260, 64 * len(plot_df) + 90)),
        margin=dict(l=8, r=16, t=8, b=8),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        bargap=0.32,
        font=dict(family="Source Sans Pro, sans-serif", color="#0F172A", size=13),
    )
    value_axis = _currency_axis(axis_title) if kind == "currency" else _percent_axis(axis_title)
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=plot_df["segment"].tolist(),
        title=None,
        showgrid=False,
        automargin=True,
    )
    figure.update_xaxes(**value_axis)
    return figure


def _hover(row: dict) -> str:
    share = "unavailable" if pd.isna(row["revenue_share"]) else f"{row['revenue_share']:.1f}%"
    profit_share = "withheld" if pd.isna(row["profit_share"]) else f"{row['profit_share']:.1f}%"
    margin = "unavailable" if pd.isna(row["margin"]) else f"{row['margin']:.2f}%"
    aov = "unavailable" if pd.isna(row["aov"]) else format_exact_currency(row["aov"])
    return (
        f"{row['segment']}<br>Revenue: {format_exact_currency(row['revenue'])} ({share} of revenue)"
        f"<br>Profit: {format_exact_currency(row['profit'])}"
        f"<br>Profit contribution: {profit_share}"
        f"<br>Margin: {margin}"
        f"<br>Orders: {int(row['orders']):,}"
        f"<br>Average order value: {aov}"
    )


def _overall_margin(performance: pd.DataFrame):
    revenue = float(performance["revenue"].sum())
    if revenue == 0:
        return None
    return float(performance["profit"].sum()) / revenue * 100


def _currency_axis(title):
    return dict(
        title=title,
        tickformat="$,.0f",
        showgrid=True,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#CBD5E1",
        rangemode="normal",
    )


def _percent_axis(title):
    return dict(
        title=title,
        ticksuffix="%",
        showgrid=True,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#CBD5E1",
        rangemode="normal",
    )
