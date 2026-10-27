"""Regional KPIs for the Regional Performance Intelligence page.

Average order value is filtered revenue divided by distinct Order_ID values.
Regional distinct order counts are not additive when one order spans regions.
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


METRIC_SPECS = {
    "Revenue": ("revenue", "currency", "#4F46E5"),
    "Profit": ("profit", "currency", "#10B981"),
    "Profit Margin": ("margin", "percent", "#8B5CF6"),
    "Average Order Value": ("aov", "currency", "#0EA5E9"),
}

TREND_METRICS = ("Revenue", "Profit", "Profit Margin")
NEGATIVE_COLOR = "#DC2626"
DEFAULT_TREND_REGIONS = 5

REGION_COLORS = {
    "Central": "#4F46E5",
    "South": "#8B5CF6",
    "North": "#10B981",
    "Oceania": "#0EA5E9",
    "Southeast Asia": "#F59E0B",
    "North Asia": "#EC4899",
    "EMEA": "#6366F1",
    "Africa": "#14B8A6",
    "Central Asia": "#A855F7",
    "West": "#3B82F6",
    "East": "#22C55E",
    "Caribbean": "#F97316",
    "Canada": "#64748B",
}

PERFORMANCE_COLUMNS = [
    "region",
    "revenue",
    "profit",
    "margin",
    "orders",
    "aov",
    "revenue_share",
    "profit_share",
    "line_items",
]


def filter_orders(df, *, start, end, regions, categories, segments) -> pd.DataFrame:
    """Apply the regional-page filters without copying the source frame first."""

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


def calculate_regional_kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs for the current filter.

    Margin is None when revenue is zero. Orders use distinct Order_ID values.
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


def calculate_regional_revenue_share(revenue: pd.Series) -> pd.Series:
    """Region revenue as a percent of the filtered total. Zero total stays undefined."""

    total = float(revenue.sum())
    if total == 0:
        return pd.Series(np.nan, index=revenue.index, dtype="float64")
    return revenue / total * 100


def aggregate_regional_performance(df: pd.DataFrame) -> pd.DataFrame:
    """One row per region with revenue, profit, margin, orders, and AOV.

    Profit share is withheld when total profit is zero or negative.
    """

    if df.empty or "Region" not in df.columns:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)

    grouped = (
        df.groupby("Region", as_index=False)
        .agg(
            revenue=("Sales", "sum"),
            profit=("Profit", "sum"),
            orders=("Order_ID", "nunique"),
            line_items=("Sales", "size"),
        )
        .rename(columns={"Region": "region"})
    )
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    grouped["aov"] = grouped["revenue"] / grouped["orders"].mask(grouped["orders"] == 0)
    grouped["revenue_share"] = calculate_regional_revenue_share(grouped["revenue"])
    total_profit = float(grouped["profit"].sum())
    if total_profit > 0:
        grouped["profit_share"] = grouped["profit"] / total_profit * 100
    else:
        grouped["profit_share"] = np.nan
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)


def calculate_regional_profitability(performance: pd.DataFrame) -> dict:
    """Leaders, laggards, losses, and high-revenue weak-margin regions."""

    empty = performance.empty
    valid_margin = performance.dropna(subset=["margin"]) if not empty else performance
    negative = performance.loc[performance["profit"] < 0] if not empty else performance
    high_revenue_low_margin = None
    if not empty and performance["revenue_share"].notna().any():
        overall_margin = _overall_margin(performance)
        candidates = valid_margin.loc[valid_margin["revenue_share"] >= 10]
        if overall_margin is not None and not candidates.empty:
            weaker = candidates.loc[candidates["margin"] < overall_margin]
            if not weaker.empty:
                high_revenue_low_margin = weaker.sort_values("margin").iloc[0]

    return {
        "highest_margin": None if valid_margin.empty else valid_margin.sort_values("margin").iloc[-1],
        "lowest_margin": None if valid_margin.empty else valid_margin.sort_values("margin").iloc[0],
        "highest_profit": None if empty else performance.sort_values("profit").iloc[-1],
        "negative_profit": negative,
        "high_revenue_low_margin": high_revenue_low_margin,
        "profit_share_available": not empty and bool(performance["profit_share"].notna().any()),
    }


def profitability_highlights(performance: pd.DataFrame) -> list[dict]:
    """Short notes for the profitability section."""

    if performance.empty:
        return [{"title": "No regional results", "body": "No transactions match the current filters."}]

    findings = calculate_regional_profitability(performance)
    notes = []
    highest = findings["highest_margin"]
    lowest = findings["lowest_margin"]
    if highest is not None:
        notes.append(
            {
                "title": "Highest margin",
                "body": (
                    f"{highest['region']} has the highest profit margin at {highest['margin']:.2f}% "
                    f"on {format_exact_currency(highest['revenue'])} of revenue."
                ),
            }
        )
    if lowest is not None and (highest is None or lowest["region"] != highest["region"]):
        notes.append(
            {
                "title": "Lowest margin",
                "body": (
                    f"{lowest['region']} has the lowest profit margin at {lowest['margin']:.2f}% "
                    f"on {format_exact_currency(lowest['revenue'])} of revenue."
                ),
            }
        )

    losses = findings["negative_profit"]
    if not losses.empty:
        names = ", ".join(losses.sort_values("profit")["region"].astype(str))
        worst = losses.sort_values("profit").iloc[0]
        notes.append(
            {
                "title": "Negative profit",
                "body": (
                    f"{names} recorded negative profit. {worst['region']} is the largest loss at "
                    f"{format_exact_currency(worst['profit'])} on {format_exact_currency(worst['revenue'])} "
                    "of revenue. Revenue scale does not make that region profitable."
                ),
            }
        )

    weak = findings["high_revenue_low_margin"]
    if weak is not None and (highest is None or weak["region"] != highest["region"]):
        gap = float(highest["margin"] - weak["margin"]) if highest is not None else None
        gap_text = (
            f" That is {gap:.1f} percentage points below {highest['region']}."
            if gap is not None
            else ""
        )
        share = "" if pd.isna(weak["revenue_share"]) else f"{weak['revenue_share']:.1f}% of revenue"
        notes.append(
            {
                "title": "Revenue without margin strength",
                "body": (
                    f"{weak['region']} generates {share} at a {weak['margin']:.2f}% margin."
                    f"{gap_text} High revenue is not the same as a strong margin."
                ),
            }
        )
    return notes


def profit_contribution_caption(performance: pd.DataFrame) -> str:
    """Profit-share line for the leading regions, or why it is withheld."""

    if performance.empty or not performance["profit_share"].notna().any():
        return "Profit contribution is withheld because total profit is not positive."
    top = performance.sort_values("profit", ascending=False).head(5)
    parts = [
        f"{row['region']} {row['profit_share']:.1f}%"
        for row in top.to_dict("records")
        if pd.notna(row["profit_share"])
    ]
    return "Top profit contribution: " + " · ".join(parts)


def default_trend_regions(performance: pd.DataFrame, limit: int = DEFAULT_TREND_REGIONS) -> list[str]:
    """Top regions by filtered revenue for the trend chart default."""

    if performance.empty:
        return []
    return performance.sort_values("revenue", ascending=False)["region"].head(limit).tolist()


def aggregate_regional_trends(df: pd.DataFrame, start_date, end_date, regions=None) -> pd.DataFrame:
    """One row per selected region and time bucket.

    Buckets follow the executive sparkline rule: daily through 45 days,
    weekly through 180 days, then monthly. Missing buckets stay empty.
    """

    columns = ["region", "period", "label", "revenue", "profit", "margin", "frequency", "grain"]
    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    period_days = int((end_ts - start_ts).days) + 1
    frequency = resolve_frequency(max(period_days, 1))
    grain = GRAIN_NAMES[frequency]
    if df.empty or "Region" not in df.columns:
        return pd.DataFrame(columns=columns)

    available = sorted(df["Region"].dropna().unique().tolist())
    if regions is None:
        selected = available
    else:
        selected = [name for name in regions if name in set(available)]
    if not selected:
        return pd.DataFrame(columns=columns)

    frames = []
    for region in selected:
        subset = df.loc[df["Region"] == region]
        trends = aggregate_kpi_trends(subset, start_date, end_date)
        frames.append(
            pd.DataFrame(
                {
                    "region": region,
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
    return pd.concat(frames, ignore_index=True)


def build_regional_comparison(performance: pd.DataFrame, metric: str):
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
        color_by_region=True,
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


def build_regional_trend(trends: pd.DataFrame, metric: str):
    """Multi-region time series. Gaps stay open and zero-revenue margins stay blank."""

    column = {"Revenue": "revenue", "Profit": "profit", "Profit Margin": "margin"}.get(metric, "revenue")
    kind = "percent" if column == "margin" else "currency"
    if trends.empty or column not in trends.columns or not trends[column].notna().any():
        return None

    figure = go.Figure()
    for region in _region_order(trends["region"].unique()):
        part = trends.loc[trends["region"] == region].sort_values("period")
        if not part[column].notna().any():
            continue
        point_count = int(part[column].notna().sum())
        color = REGION_COLORS.get(region, "#4F46E5")
        custom = [_trend_hover(row, column) for row in part.to_dict("records")]
        figure.add_trace(
            go.Scatter(
                name=region,
                x=part["period"],
                y=part[column],
                mode="markers" if point_count == 1 else "lines",
                connectgaps=False,
                line=dict(color=color, width=2.4),
                marker=dict(color=color, size=7),
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
        f"{grain.capitalize()} totals for the regions selected in the trend chart. "
        "Profit margin is profit divided by revenue inside each bucket. "
        "Buckets with no transactions are left blank, and a bucket with zero revenue has no margin."
    )


def generate_regional_insights(performance: pd.DataFrame, trends: pd.DataFrame) -> list[dict]:
    """Up to five calculated notes. Filtered-out regions are never mentioned."""

    if performance.empty:
        return [{"title": "No regional results", "body": "No transactions match the current filters."}]

    notes = [
        _revenue_insight(performance),
        _margin_insight(performance),
        _revenue_profit_mismatch(performance),
        _risk_insight(performance),
        _concentration_insight(performance),
        _trend_insight(trends, performance),
    ]
    return [note for note in notes if note][:5]


def _revenue_insight(performance: pd.DataFrame) -> dict:
    leader = performance.sort_values(["revenue", "region"]).iloc[-1]
    amount = format_exact_currency(leader["revenue"])
    if len(performance) == 1:
        body = f"{leader['region']} is the only region in this view, with {amount} of revenue."
    else:
        share = "an undefined share" if pd.isna(leader["revenue_share"]) else f"{leader['revenue_share']:.1f}%"
        body = (
            f"{leader['region']} contributes the most revenue in this view: "
            f"{amount}, {share} of filtered revenue."
        )
    return {"title": "Revenue leadership", "body": body}


def _margin_insight(performance: pd.DataFrame):
    valid = performance.dropna(subset=["margin"])
    if valid.empty:
        return None
    leader = valid.sort_values(["margin", "region"]).iloc[-1]
    revenue_leader = performance.sort_values(["revenue", "region"]).iloc[-1]
    amount = format_exact_currency(leader["revenue"])
    if len(performance) == 1:
        body = f"{leader['region']} profit margin is {leader['margin']:.2f}% on {amount} of revenue."
    elif leader["region"] == revenue_leader["region"]:
        body = (
            f"{leader['region']} has both the highest revenue and the highest profit margin "
            f"in this view at {leader['margin']:.2f}% on {amount} of revenue."
        )
    else:
        body = (
            f"{leader['region']} has the highest profit margin in this view at {leader['margin']:.2f}% "
            f"on {amount} of revenue. It is not the revenue leader."
        )
    return {"title": "Profitability leadership", "body": body}


def _revenue_profit_mismatch(performance: pd.DataFrame):
    if len(performance) < 2:
        return None
    revenue_leader = performance.sort_values(["revenue", "region"]).iloc[-1]
    profit_leader = performance.sort_values(["profit", "region"]).iloc[-1]
    if revenue_leader["region"] == profit_leader["region"]:
        return {
            "title": "Revenue and profit alignment",
            "body": (
                f"{revenue_leader['region']} leads both revenue and profit in this view: "
                f"{format_exact_currency(revenue_leader['revenue'])} of revenue and "
                f"{format_exact_currency(profit_leader['profit'])} of profit."
            ),
        }
    return {
        "title": "Revenue vs profit mismatch",
        "body": (
            f"{revenue_leader['region']} leads revenue at {format_exact_currency(revenue_leader['revenue'])}, "
            f"while {profit_leader['region']} leads profit at {format_exact_currency(profit_leader['profit'])}. "
            "The largest revenue region is not the largest profit contributor."
        ),
    }


def _risk_insight(performance: pd.DataFrame):
    losses = performance.loc[performance["profit"] < 0]
    if not losses.empty:
        worst = losses.sort_values("profit").iloc[0]
        return {
            "title": "Profitability risk",
            "body": (
                f"{worst['region']} recorded negative profit of {format_exact_currency(worst['profit'])} "
                f"on {format_exact_currency(worst['revenue'])} of revenue "
                f"({worst['margin']:.2f}% margin)."
            ),
        }

    valid = performance.dropna(subset=["margin"])
    if valid.empty or len(valid) < 2:
        return None
    lowest = valid.sort_values(["margin", "region"]).iloc[0]
    highest = valid.sort_values(["margin", "region"]).iloc[-1]
    gap = float(highest["margin"] - lowest["margin"])
    if gap < 5:
        return None
    return {
        "title": "Profitability risk",
        "body": (
            f"{lowest['region']} has the weakest margin in this view at {lowest['margin']:.2f}% "
            f"on {format_exact_currency(lowest['revenue'])} of revenue. "
            f"That is {gap:.1f} percentage points below {highest['region']}."
        ),
    }


def _concentration_insight(performance: pd.DataFrame):
    if len(performance) < 3 or not performance["revenue_share"].notna().any():
        return None
    top = performance.sort_values("revenue", ascending=False).head(3)
    share = float(top["revenue_share"].sum())
    names = ", ".join(top["region"].astype(str))
    return {
        "title": "Regional concentration",
        "body": (
            f"{names} together account for {share:.1f}% of filtered revenue. "
            "Revenue is concentrated among a small set of regions in this view."
        ),
    }


def _trend_insight(trends: pd.DataFrame, performance: pd.DataFrame):
    if trends.empty or performance.empty:
        return None
    leader_name = performance.sort_values(["revenue", "region"]).iloc[-1]["region"]
    series = trends.loc[trends["region"] == leader_name].sort_values("period")
    if series.empty:
        return None
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
    return {
        "title": "Regional trend",
        "body": (
            f"{leader_name} revenue in {latest['label']} was {format_exact_currency(latest['revenue'])}, "
            f"{abs(change):.1f}% {direction} than {earlier['label']}. "
            "The comparison uses two buckets inside the selected reporting period."
        ),
    }


def _ranked_bar(performance, column, color, kind, axis_title, color_by_region=False):
    if performance.empty or column not in performance.columns:
        return None
    plot_df = performance.dropna(subset=[column]).sort_values(column, ascending=True)
    if plot_df.empty:
        return None

    colors = []
    for row in plot_df.to_dict("records"):
        if float(row[column]) < 0:
            colors.append(NEGATIVE_COLOR)
        elif color_by_region:
            colors.append(REGION_COLORS.get(row["region"], color))
        else:
            colors.append(color)

    hover = [_hover(row) for row in plot_df.to_dict("records")]
    figure = go.Figure(
        data=[
            go.Bar(
                y=plot_df["region"],
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
        height, bargap = min(560, max(340, 36 * count + 100)), 0.24
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
        categoryarray=plot_df["region"].tolist(),
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
        f"{row['region']}<br>Revenue: {format_exact_currency(row['revenue'])} ({share} of revenue)"
        f"<br>Profit: {format_exact_currency(row['profit'])}"
        f"<br>Profit contribution: {profit_share}"
        f"<br>Margin: {margin}"
        f"<br>Orders: {int(row['orders']):,}"
        f"<br>Average order value: {aov}"
        f"<br>Order line items: {int(row['line_items']):,}"
    )


def _trend_hover(row: dict, column: str) -> str:
    if pd.isna(row[column]):
        return f"{row['region']}<br>{row['label']}<br>No transactions"
    revenue = "unavailable" if pd.isna(row["revenue"]) else format_exact_currency(row["revenue"])
    profit = "unavailable" if pd.isna(row["profit"]) else format_exact_currency(row["profit"])
    margin = "unavailable" if pd.isna(row["margin"]) else f"{float(row['margin']):.2f}%"
    return (
        f"{row['region']}<br>{row['label']}<br>Revenue: {revenue}"
        f"<br>Profit: {profit}<br>Margin: {margin}"
    )


def _region_order(values) -> list[str]:
    present = {str(value) for value in values}
    preferred = [name for name in REGION_COLORS if name in present]
    preferred.extend(sorted(present - set(preferred)))
    return preferred


def _overall_margin(performance: pd.DataFrame):
    revenue = float(performance["revenue"].sum())
    if revenue == 0:
        return None
    return float(performance["profit"].sum()) / revenue * 100


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
