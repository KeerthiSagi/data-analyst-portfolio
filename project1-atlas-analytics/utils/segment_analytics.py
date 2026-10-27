"""Customer-segment KPIs for the segment intelligence page.

Average order value is filtered revenue divided by distinct Order_ID values.
It is not the mean of line-item sales. Segment order counts are not additive
when one order contains more than one segment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.kpi_metrics import (
    GRAIN_NAMES,
    aggregate_kpi_trends,
    format_exact_currency,
    resolve_frequency,
)


SEGMENT_COLORS = {
    "Consumer": "#4F46E5",
    "Corporate": "#8B5CF6",
    "Home Office": "#0EA5E9",
}

# Trend and discount comparisons use the Phase 4B palette. The Phase 4A
# contribution chart keeps SEGMENT_COLORS.
TREND_SEGMENT_COLORS = {
    "Consumer": "#4F46E5",
    "Corporate": "#10B981",
    "Home Office": "#8B5CF6",
}

DISCOUNT_BINS = [-0.001, 0.0, 0.1, 0.2, 0.3, np.inf]
DISCOUNT_LABELS = ["0%", ">0%–10%", ">10%–20%", ">20%–30%", ">30%"]
DISCOUNT_METRICS = ("Revenue", "Profit", "Profit Margin")
TREND_METRICS = ("Revenue", "Profit", "Profit Margin")
SEGMENT_ORDER = ("Consumer", "Corporate", "Home Office")

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
    "line_items",
    "average_discount",
    "negative_line_items",
    "negative_line_rate",
    "loss_amount",
    "orders_with_loss_lines",
    "unprofitable_orders",
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
            line_items=("Sales", "size"),
        )
        .rename(columns={"Segment": "segment"})
    )
    grouped = grouped.merge(_loss_stats(df), on="segment", how="left")
    for column in ("negative_line_items", "orders_with_loss_lines", "unprofitable_orders"):
        grouped[column] = grouped[column].fillna(0).astype(int)
    grouped["loss_amount"] = grouped["loss_amount"].fillna(0.0)
    grouped["negative_line_rate"] = (
        grouped["negative_line_items"] / grouped["line_items"].mask(grouped["line_items"] == 0) * 100
    )
    if "Discount" in df.columns:
        average_discount = df.groupby("Segment")["Discount"].mean() * 100
        grouped["average_discount"] = grouped["segment"].map(average_discount)
    else:
        grouped["average_discount"] = np.nan
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    grouped["aov"] = grouped["revenue"] / grouped["orders"].mask(grouped["orders"] == 0)
    grouped["revenue_share"] = calculate_segment_revenue_share(grouped["revenue"])
    total_profit = float(grouped["profit"].sum())
    if total_profit > 0:
        grouped["profit_share"] = grouped["profit"] / total_profit * 100
    else:
        grouped["profit_share"] = np.nan
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)


def _loss_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Line-item losses and the two different order counts they can imply."""

    segments = df["Segment"].dropna().unique()
    stats = pd.DataFrame({"segment": segments})
    loss_rows = df.loc[df["Profit"] < 0]
    if loss_rows.empty:
        stats["negative_line_items"] = 0
        stats["loss_amount"] = 0.0
        stats["orders_with_loss_lines"] = 0
    else:
        counted = (
            loss_rows.groupby("Segment", as_index=False)
            .agg(
                negative_line_items=("Profit", "size"),
                loss_amount=("Profit", "sum"),
                orders_with_loss_lines=("Order_ID", "nunique"),
            )
            .rename(columns={"Segment": "segment"})
        )
        stats = stats.merge(counted, on="segment", how="left")

    order_profit = df.groupby(["Segment", "Order_ID"], as_index=False)["Profit"].sum()
    unprofitable = (
        order_profit.loc[order_profit["Profit"] < 0]
        .groupby("Segment")["Order_ID"]
        .nunique()
    )
    stats["unprofitable_orders"] = stats["segment"].map(unprofitable)
    return stats


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
    count = len(plot_df)
    if count <= 3:
        height, bargap = 260, 0.68
    elif count <= 6:
        height, bargap = max(300, 44 * count + 90), 0.42
    else:
        height, bargap = min(420, max(340, 36 * count + 100)), 0.24
    figure.update_layout(
        height=height,
        margin=dict(l=72, r=36, t=24, b=56, pad=4),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        bargap=bargap,
        font=dict(family="Source Sans Pro, sans-serif", color="#0F172A", size=13),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0", font=dict(size=12), align="left"),
    )
    value_axis = _currency_axis(axis_title) if kind == "currency" else _percent_axis(axis_title)
    value_axis = {**value_axis, "automargin": True}
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


def assign_discount_band(discount: pd.Series) -> pd.Series:
    """Non-overlapping bands. 10%, 20%, and 30% stay in the band they close."""

    return pd.cut(
        discount,
        bins=DISCOUNT_BINS,
        labels=DISCOUNT_LABELS,
        include_lowest=True,
        right=True,
    )


def aggregate_discount_profitability(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, profit, aggregate margin, and line counts by segment and band."""

    columns = ["segment", "band", "revenue", "profit", "margin", "line_items"]
    if df.empty or "Discount" not in df.columns or "Segment" not in df.columns:
        return pd.DataFrame(columns=columns)

    work = df.loc[:, ["Segment", "Sales", "Profit", "Discount"]].copy()
    work["band"] = assign_discount_band(work["Discount"])
    work = work.dropna(subset=["band"])
    if work.empty:
        return pd.DataFrame(columns=columns)

    grouped = (
        work.groupby(["Segment", "band"], observed=False)
        .agg(
            revenue=("Sales", "sum"),
            profit=("Profit", "sum"),
            line_items=("Sales", "size"),
        )
        .reset_index()
        .rename(columns={"Segment": "segment"})
    )
    grouped["revenue"] = grouped["revenue"].fillna(0.0)
    grouped["profit"] = grouped["profit"].fillna(0.0)
    grouped["line_items"] = grouped["line_items"].fillna(0).astype(int)
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    grouped["band"] = grouped["band"].astype(str)
    return grouped.sort_values(["segment", "band"]).reset_index(drop=True)


def aggregate_segment_trends(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """One row per segment and time bucket inside the selected window.

    Buckets follow the executive sparkline rule: daily through 45 days,
    weekly through 180 days, then monthly. Missing buckets stay empty.
    Margin is bucket profit divided by bucket revenue.
    """

    columns = ["segment", "period", "label", "revenue", "profit", "margin", "frequency", "grain"]
    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    period_days = int((end_ts - start_ts).days) + 1
    frequency = resolve_frequency(max(period_days, 1))
    grain = GRAIN_NAMES[frequency]
    if df.empty or "Segment" not in df.columns:
        return pd.DataFrame(columns=columns)

    frames = []
    for segment in _segment_order(df["Segment"].dropna().unique()):
        subset = df.loc[df["Segment"] == segment]
        trends = aggregate_kpi_trends(subset, start_date, end_date)
        frames.append(
            pd.DataFrame(
                {
                    "segment": segment,
                    "period": pd.to_datetime(trends.revenue["period"]).to_numpy(),
                    "label": trends.revenue["label"].to_numpy(),
                    "revenue": trends.revenue["value"].to_numpy(),
                    "profit": trends.profit["value"].to_numpy(),
                    "margin": trends.margin["value"].to_numpy(),
                    "frequency": frequency,
                    "grain": grain,
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def loss_analysis_caption(performance: pd.DataFrame) -> str:
    """Explain line-item losses without adding segment order counts together."""

    if performance.empty or int(performance["negative_line_items"].sum()) == 0:
        return "No line items in this view have negative profit."
    parts = []
    ordered = performance.sort_values("loss_amount")
    for row in ordered.to_dict("records"):
        rate = "unavailable" if pd.isna(row["negative_line_rate"]) else f"{row['negative_line_rate']:.1f}%"
        parts.append(
            f"{row['segment']}: {int(row['negative_line_items']):,} loss lines ({rate}), "
            f"{format_exact_currency(row['loss_amount']).replace('$', '\\$')}"
        )
    return (
        " · ".join(parts)
        + ". Hover separates loss-making lines, orders that contain one, and orders "
        "that are unprofitable after every line is combined. An order can contain a "
        "loss-making line and still finish in profit. Order counts are not additive across segments."
    )


def build_loss_chart(performance: pd.DataFrame):
    """Horizontal bars for the sum of negative line-item profit."""

    if performance.empty or "loss_amount" not in performance.columns:
        return None
    if int(performance["negative_line_items"].sum()) == 0:
        return None
    plot_df = performance.sort_values("loss_amount", ascending=False)
    colors = [NEGATIVE_COLOR if float(value) < 0 else "#94A3B8" for value in plot_df["loss_amount"]]
    hover = [_loss_hover(row) for row in plot_df.to_dict("records")]
    figure = go.Figure(
        data=[
            go.Bar(
                y=plot_df["segment"],
                x=plot_df["loss_amount"],
                orientation="h",
                marker=dict(color=colors),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    count = len(plot_df)
    height = 260 if count <= 3 else min(420, max(300, 44 * count + 90))
    figure.update_layout(
        **_chart_layout(height),
        bargap=0.68 if count <= 3 else 0.42,
        showlegend=False,
    )
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=plot_df["segment"].tolist(),
        title=None,
        showgrid=False,
        automargin=True,
    )
    figure.update_xaxes(**{**_currency_axis("Total loss amount"), "automargin": True})
    return figure


def build_discount_chart(discount: pd.DataFrame, metric: str):
    """Grouped bars. One metric per axis, with each selected segment in its own color."""

    spec = {
        "Revenue": ("revenue", "currency"),
        "Profit": ("profit", "currency"),
        "Profit Margin": ("margin", "percent"),
    }.get(metric, ("revenue", "currency"))
    column, kind = spec
    if discount.empty or column not in discount.columns or not discount[column].notna().any():
        return None

    figure = go.Figure()
    for segment in _segment_order(discount["segment"].unique()):
        part = discount.loc[discount["segment"] == segment].drop_duplicates("band").set_index("band")
        part = part.reindex(DISCOUNT_LABELS)
        hover = []
        for band in DISCOUNT_LABELS:
            row = part.loc[band] if band in part.index else None
            hover.append(_discount_hover(segment, band, row))
        figure.add_trace(
            go.Bar(
                name=segment,
                x=list(DISCOUNT_LABELS),
                y=part[column],
                marker=dict(color=TREND_SEGMENT_COLORS.get(segment, "#4F46E5")),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )
    figure.update_layout(
        **_chart_layout(340),
        barmode="group",
        bargap=0.28,
        bargroupgap=0.12,
        legend=_legend(),
    )
    axis = _currency_axis(metric) if kind == "currency" else _percent_axis(metric)
    figure.update_xaxes(
        title=None,
        showgrid=False,
        automargin=True,
        categoryorder="array",
        categoryarray=list(DISCOUNT_LABELS),
    )
    figure.update_yaxes(**{**axis, "automargin": True})
    return figure


def build_segment_trend(trends: pd.DataFrame, metric: str):
    """Multi-segment time series. Gaps stay open and zero-revenue margins stay blank."""

    column = {"Revenue": "revenue", "Profit": "profit", "Profit Margin": "margin"}.get(metric, "revenue")
    kind = "percent" if column == "margin" else "currency"
    if trends.empty or column not in trends.columns or not trends[column].notna().any():
        return None

    figure = go.Figure()
    for segment in _segment_order(trends["segment"].unique()):
        part = trends.loc[trends["segment"] == segment].sort_values("period")
        if not part[column].notna().any():
            continue
        point_count = int(part[column].notna().sum())
        custom = [
            _trend_hover(row, column)
            for row in part.to_dict("records")
        ]
        figure.add_trace(
            go.Scatter(
                name=segment,
                x=part["period"],
                y=part[column],
                mode="markers" if point_count == 1 else "lines",
                connectgaps=False,
                line=dict(color=TREND_SEGMENT_COLORS.get(segment, "#4F46E5"), width=2.4),
                marker=dict(color=TREND_SEGMENT_COLORS.get(segment, "#4F46E5"), size=7),
                hovertext=custom,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )
    if not figure.data:
        return None
    frequency = str(trends["frequency"].iloc[0])
    figure.update_layout(**_chart_layout(420), legend=_legend(), hovermode="x unified")
    figure.update_xaxes(
        title=None,
        showgrid=False,
        tickformat="%b %d" if frequency in {"D", "W"} else "%b %Y",
        automargin=True,
    )
    axis = _percent_axis(metric) if kind == "percent" else _currency_axis(metric)
    figure.update_yaxes(**axis)
    return figure


def trend_caption(trends: pd.DataFrame) -> str:
    if trends.empty:
        return "No time buckets are available for this selection."
    grain = str(trends["grain"].iloc[0]).lower()
    return (
        f"{grain.capitalize()} totals for the selected reporting period. "
        "Profit margin is profit divided by revenue inside each bucket. "
        "Buckets with no transactions are left blank, and a bucket with zero revenue has no margin."
    )


def build_segment_insights(performance: pd.DataFrame, discount: pd.DataFrame, trends: pd.DataFrame) -> list[dict]:
    """Up to five calculated notes. Filtered-out segments are never mentioned."""

    if performance.empty:
        return [{"title": "No segment results", "body": "No transactions match the current filters."}]

    notes = [
        _revenue_insight(performance),
        _margin_insight(performance),
        _discount_insight(discount),
        _loss_insight(performance),
    ]
    trend_note = _trend_insight(trends, performance)
    aov_note = _aov_insight(performance)
    # A single segment has no AOV comparison, and a small gap is less useful
    # than a material change between two buckets in the selected window.
    prefer_trend = trend_note is not None and (
        len(performance) == 1 or _aov_spread_is_small(performance)
    )
    notes.append(trend_note if prefer_trend else (aov_note or trend_note))
    return [note for note in notes if note][:5]


def _revenue_insight(performance: pd.DataFrame) -> dict:
    leader = performance.sort_values(["revenue", "segment"]).iloc[-1]
    amount = format_exact_currency(leader["revenue"])
    if len(performance) == 1:
        body = f"{leader['segment']} is the only segment in this view, with {amount} of revenue."
    else:
        share = "an undefined share" if pd.isna(leader["revenue_share"]) else f"{leader['revenue_share']:.1f}%"
        body = (
            f"{leader['segment']} contributes the most revenue in this view: "
            f"{amount}, {share} of filtered revenue."
        )
    return {"title": "Revenue leadership", "body": body}


def _margin_insight(performance: pd.DataFrame):
    valid = performance.dropna(subset=["margin"])
    if valid.empty:
        return None
    leader = valid.sort_values(["margin", "segment"]).iloc[-1]
    amount = format_exact_currency(leader["revenue"])
    if len(performance) == 1:
        body = f"{leader['segment']} profit margin is {leader['margin']:.2f}% on {amount} of revenue."
    else:
        body = (
            f"{leader['segment']} has the highest profit margin in this view at "
            f"{leader['margin']:.2f}% on {amount} of revenue."
        )
    return {"title": "Profitability leadership", "body": body}


def _aov_insight(performance: pd.DataFrame):
    valid = performance.dropna(subset=["aov"])
    if valid.empty:
        return None
    leader = valid.sort_values(["aov", "segment"]).iloc[-1]
    amount = format_exact_currency(leader["aov"])
    if len(performance) == 1:
        body = f"{leader['segment']} average order value is {amount}."
    else:
        trailer = valid.sort_values(["aov", "segment"]).iloc[0]
        gap = float(leader["aov"] - trailer["aov"])
        if leader["segment"] == trailer["segment"] or gap == 0:
            body = f"{leader['segment']} has the highest average order value in this view at {amount}."
        else:
            body = (
                f"{leader['segment']} has the highest average order value in this view at {amount}, "
                f"{format_exact_currency(gap)} above {trailer['segment']}."
            )
    return {"title": "Average order value", "body": body}


def _discount_insight(discount: pd.DataFrame):
    if discount.empty:
        return None
    totals = (
        discount.groupby("band", as_index=False)
        .agg(revenue=("revenue", "sum"), profit=("profit", "sum"), line_items=("line_items", "sum"))
    )
    totals["margin"] = totals["profit"] / totals["revenue"].mask(totals["revenue"] == 0) * 100
    totals["band"] = pd.Categorical(totals["band"], categories=DISCOUNT_LABELS, ordered=True)
    populated = totals.loc[totals["line_items"] > 0].sort_values("band")
    base = populated.loc[populated["band"] == "0%"]
    others = populated.loc[populated["band"] != "0%"].dropna(subset=["margin"])
    if base.empty or others.empty or pd.isna(base.iloc[0]["margin"]):
        return None
    deepest = others.iloc[-1]
    base_row = base.iloc[0]
    body = (
        f"Lines with a {base_row['band']} discount produced a {base_row['margin']:.2f}% margin "
        f"on {format_exact_currency(base_row['revenue'])}. "
        f"Lines in the {deepest['band']} band produced a {deepest['margin']:.2f}% margin "
        f"on {format_exact_currency(deepest['revenue'])}. "
        "These figures describe an observed association between discount band and profit margin."
    )
    return {"title": "Discount behavior", "body": body}


def _loss_insight(performance: pd.DataFrame):
    if "negative_line_rate" not in performance.columns:
        return None
    if int(performance["negative_line_items"].sum()) == 0:
        return {
            "title": "Loss exposure",
            "body": "No line items in this view have negative profit.",
        }
    valid = performance.dropna(subset=["negative_line_rate"])
    leader = valid.sort_values(["negative_line_rate", "negative_line_items", "segment"]).iloc[-1]
    rate = f"{leader['negative_line_rate']:.1f}%"
    lines = f"{int(leader['negative_line_items']):,} of {int(leader['line_items']):,}"
    loss = format_exact_currency(leader["loss_amount"])
    with_loss = int(leader["orders_with_loss_lines"])
    unprofitable = int(leader["unprofitable_orders"])
    if len(performance) == 1:
        opening = f"{rate} of {leader['segment']} line items have negative profit ({lines})."
    else:
        opening = (
            f"{leader['segment']} has the highest negative-profit line rate in this view "
            f"at {rate} ({lines} lines)."
        )
    body = (
        f"{opening} Those lines total {loss}. "
        f"{with_loss:,} orders contain a loss-making line, while {unprofitable:,} orders "
        "are unprofitable after every line is combined."
    )
    return {"title": "Loss exposure", "body": body}


def _trend_insight(trends: pd.DataFrame, performance: pd.DataFrame):
    if trends.empty or performance.empty:
        return None
    leader_name = performance.sort_values(["revenue", "segment"]).iloc[-1]["segment"]
    series = trends.loc[trends["segment"] == leader_name].sort_values("period")
    populated = series.dropna(subset=["revenue"])
    if len(populated) < 2:
        return None
    latest = populated.iloc[-1]
    frequency = str(series["frequency"].iloc[0])
    earlier = None
    threshold = 15.0
    if frequency == "M":
        year_earlier = pd.Timestamp(latest["period"]) - pd.DateOffset(years=1)
        match = populated.loc[pd.to_datetime(populated["period"]).eq(year_earlier)]
        if not match.empty:
            earlier = match.iloc[0]
            threshold = 5.0
    if earlier is None:
        earlier = populated.iloc[-2]
    if float(earlier["revenue"]) == 0 or pd.isna(earlier["revenue"]):
        return None
    change = (float(latest["revenue"]) - float(earlier["revenue"])) / float(earlier["revenue"]) * 100
    if abs(change) < threshold:
        return None
    direction = "higher" if change > 0 else "lower"
    body = (
        f"{leader_name} revenue in {latest['label']} was {format_exact_currency(latest['revenue'])}, "
        f"{abs(change):.1f}% {direction} than {earlier['label']}. "
        "The comparison uses two buckets inside the selected reporting period."
    )
    return {"title": "Performance trend", "body": body}


def _aov_spread_is_small(performance: pd.DataFrame) -> bool:
    valid = performance.dropna(subset=["aov"])
    if len(valid) < 2:
        return False
    highest = float(valid["aov"].max())
    if highest == 0:
        return False
    return (highest - float(valid["aov"].min())) / highest < 0.02


def _segment_order(values) -> list[str]:
    present = {str(value) for value in values}
    ordered = [name for name in SEGMENT_ORDER if name in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _loss_hover(row: dict) -> str:
    rate = "unavailable" if pd.isna(row["negative_line_rate"]) else f"{row['negative_line_rate']:.1f}%"
    return (
        f"{row['segment']}<br>Negative-profit line items: {int(row['negative_line_items']):,} ({rate})"
        f"<br>Total loss amount: {format_exact_currency(row['loss_amount'])}"
        f"<br>Orders containing a loss-making line: {int(row['orders_with_loss_lines']):,}"
        f"<br>Orders unprofitable overall: {int(row['unprofitable_orders']):,}"
    )


def _discount_hover(segment: str, band: str, row) -> str:
    if row is None or pd.isna(row.get("line_items", np.nan)):
        return f"{segment}<br>{band}<br>No line items"
    margin = "unavailable" if pd.isna(row["margin"]) else f"{float(row['margin']):.2f}%"
    revenue = 0.0 if pd.isna(row["revenue"]) else row["revenue"]
    profit = 0.0 if pd.isna(row["profit"]) else row["profit"]
    return (
        f"{segment}<br>{band}<br>Revenue: {format_exact_currency(revenue)}"
        f"<br>Profit: {format_exact_currency(profit)}"
        f"<br>Margin: {margin}"
        f"<br>Line items: {int(row['line_items']):,}"
    )


def _trend_hover(row: dict, column: str) -> str:
    if pd.isna(row[column]):
        return f"{row['segment']}<br>{row['label']}<br>No transactions"
    revenue = "unavailable" if pd.isna(row["revenue"]) else format_exact_currency(row["revenue"])
    profit = "unavailable" if pd.isna(row["profit"]) else format_exact_currency(row["profit"])
    margin = "unavailable" if pd.isna(row["margin"]) else f"{float(row['margin']):.2f}%"
    return (
        f"{row['segment']}<br>{row['label']}<br>Revenue: {revenue}"
        f"<br>Profit: {profit}<br>Margin: {margin}"
    )


def _chart_layout(height: int) -> dict:
    return dict(
        height=height,
        margin=dict(l=56, r=28, t=48, b=64, pad=4),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Source Sans Pro, sans-serif", color="#0F172A", size=13),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0", font=dict(size=12), align="left"),
    )


def _legend() -> dict:
    return dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None)
