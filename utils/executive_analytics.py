"""Executive Overview aggregations, charts, and narrative insights.

Time series reuse the sparkline buckets. Category and region margins are
group profit divided by group revenue. Row-level margins are never averaged.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.kpi_metrics import format_exact_currency


TREND_REVENUE = "Revenue"
TREND_PROFIT = "Profit"
TREND_MARGIN = "Profit Margin"
TREND_BOTH = "Revenue & Profit"

GROUP_METRICS = (TREND_REVENUE, TREND_PROFIT, TREND_MARGIN)

METRIC_COLUMN = {
    TREND_REVENUE: "revenue",
    TREND_PROFIT: "profit",
    TREND_MARGIN: "margin",
}

METRIC_COLOR = {
    TREND_REVENUE: "#4F46E5",
    TREND_PROFIT: "#10B981",
    TREND_MARGIN: "#8B5CF6",
}

NEGATIVE_COLOR = "#DC2626"

DISCOUNT_BINS = [-0.001, 0.0, 0.1, 0.2, 0.3, 1.01]
DISCOUNT_LABELS = ["No discount", "0–10%", "10–20%", "20–30%", "Above 30%"]


@dataclass(frozen=True)
class ExecutiveInsight:
    """One calculated observation for the filtered reporting view."""

    title: str
    body: str


def summarize_groups(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Revenue, profit, margin, and revenue share for one grouping column."""

    empty = pd.DataFrame(
        columns=["name", "revenue", "profit", "margin", "revenue_share", "profit_share"]
    )
    if df.empty or column not in df.columns:
        return empty

    grouped = (
        df.groupby(column, as_index=False)
        .agg(revenue=("Sales", "sum"), profit=("Profit", "sum"))
        .rename(columns={column: "name"})
    )
    total_revenue = float(grouped["revenue"].sum())
    total_profit = float(grouped["profit"].sum())
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    if total_revenue == 0:
        grouped["revenue_share"] = np.nan
    else:
        grouped["revenue_share"] = grouped["revenue"] / total_revenue * 100
    if total_profit > 0:
        grouped["profit_share"] = grouped["profit"] / total_profit * 100
    else:
        grouped["profit_share"] = np.nan
    return grouped


def trend_frame(trends) -> pd.DataFrame:
    """Join sparkline buckets into one chronological table.

    Margin stays the bucket margin already stored on the trend. It is not
    recomputed from an average of transactions.
    """

    frame = trends.revenue.loc[:, ["period", "label", "value"]].rename(columns={"value": "revenue"})
    frame = frame.merge(
        trends.profit.loc[:, ["period", "value"]].rename(columns={"value": "profit"}),
        on="period",
        how="left",
    )
    frame = frame.merge(
        trends.margin.loc[:, ["period", "value"]].rename(columns={"value": "margin"}),
        on="period",
        how="left",
    )
    return frame.sort_values("period").reset_index(drop=True)


def discount_margin_bands(df: pd.DataFrame) -> pd.DataFrame | None:
    """Margin by discount band. Empty or missing discount data returns None."""

    if df.empty or "Discount" not in df.columns:
        return None

    bands = pd.cut(
        df["Discount"],
        bins=DISCOUNT_BINS,
        labels=DISCOUNT_LABELS,
        include_lowest=True,
    )
    grouped = (
        df.groupby(bands, observed=True)
        .agg(revenue=("Sales", "sum"), profit=("Profit", "sum"))
        .reset_index()
    )
    grouped = grouped.rename(columns={"Discount": "band"})
    grouped["band"] = grouped["band"].astype(str)
    grouped["margin"] = grouped["profit"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    if grouped.empty:
        return None
    return grouped


def metric_has_negative(summary: pd.DataFrame, metric: str) -> bool:
    """True when the selected metric contains a negative value."""

    column = METRIC_COLUMN.get(metric)
    if summary.empty or column is None or column not in summary.columns:
        return False
    return bool((summary[column] < 0).fillna(False).any())


def format_revenue_mix(summary: pd.DataFrame) -> str:
    """One-line revenue composition, independent of the selected bar metric."""

    if summary.empty or not summary["revenue_share"].notna().any():
        return "Revenue share is unavailable for this selection."

    parts = [
        f"{row['name']} {row['revenue_share']:.1f}%"
        for row in summary.sort_values("revenue", ascending=False).to_dict("records")
        if pd.notna(row["revenue_share"])
    ]
    return "Share of revenue: " + " · ".join(parts)


def build_trend_figure(trends, selection: str):
    """Interactive revenue, profit, and margin chart.

    Revenue and profit are drawn on separate axes when shown together so the
    smaller profit series is not compressed onto the revenue scale.
    """

    frame = trend_frame(trends)
    if frame.empty:
        return None

    selection = selection or TREND_BOTH
    if selection == TREND_BOTH:
        if not frame["revenue"].notna().any() and not frame["profit"].notna().any():
            return None
        figure = go.Figure()
        _add_trend_trace(figure, frame, "revenue", "Revenue", METRIC_COLOR[TREND_REVENUE], rich=False)
        _add_trend_trace(
            figure,
            frame,
            "profit",
            "Profit",
            METRIC_COLOR[TREND_PROFIT],
            axis="y2",
            rich=False,
        )
        figure.update_layout(
            yaxis=_currency_axis("Revenue"),
            yaxis2=_currency_axis("Profit", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            hovermode="x unified",
        )
    else:
        column = METRIC_COLUMN.get(selection, "revenue")
        if not frame[column].notna().any():
            return None
        figure = go.Figure()
        _add_trend_trace(
            figure,
            frame,
            column,
            selection,
            METRIC_COLOR.get(selection, METRIC_COLOR[TREND_REVENUE]),
            rich=True,
        )
        if selection == TREND_MARGIN:
            figure.update_layout(yaxis=_percent_axis("Profit margin"), showlegend=False, hovermode="closest")
        else:
            figure.update_layout(yaxis=_currency_axis(selection), showlegend=False, hovermode="closest")

    figure.update_layout(
        height=380,
        margin=dict(l=48, r=28, t=48, b=64, pad=4),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Source Sans Pro, sans-serif", color="#0F172A", size=13),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0", font=dict(size=12), align="left"),
    )
    figure.update_xaxes(
        type="date",
        showgrid=False,
        title=None,
        automargin=True,
        tickformat=_tickformat(trends.frequency),
        hoverformat="%b %d, %Y",
    )
    figure.update_yaxes(automargin=True)
    return figure


def build_performance_bar(summary: pd.DataFrame, metric: str, orientation: str):
    """Ranked bar chart. Negative values stay visible and use a distinct color."""

    column = METRIC_COLUMN.get(metric, "revenue")
    if summary.empty or column not in summary.columns:
        return None

    plot_df = summary.dropna(subset=[column])
    if plot_df.empty:
        return None

    largest_first = orientation != "h"
    plot_df = plot_df.sort_values(column, ascending=not largest_first)
    color = METRIC_COLOR.get(metric, METRIC_COLOR[TREND_REVENUE])
    colors = [NEGATIVE_COLOR if float(value) < 0 else color for value in plot_df[column]]
    hover = [_performance_hover(row) for row in plot_df.to_dict("records")]
    names = plot_df["name"].tolist()
    values = plot_df[column].tolist()

    count = len(plot_df)
    if orientation == "h":
        trace = go.Bar(
            y=names,
            x=values,
            orientation="h",
            marker=dict(color=colors),
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
        if count <= 3:
            height, bargap = 260, 0.68
        elif count <= 6:
            height, bargap = max(300, 44 * count + 90), 0.42
        else:
            height, bargap = min(560, max(340, 36 * count + 100)), 0.24
        value_axis = "x"
        margins = dict(l=72, r=36, t=24, b=56, pad=4)
    else:
        trace = go.Bar(
            x=names,
            y=values,
            marker=dict(color=colors),
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
        height = 280 if count <= 3 else 320 if count <= 6 else 360
        bargap = 0.62 if count <= 3 else 0.42 if count <= 6 else 0.3
        value_axis = "y"
        margins = dict(l=48, r=28, t=24, b=72, pad=4)

    figure = go.Figure(data=[trace])
    figure.update_layout(
        height=height,
        margin=margins,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        bargap=bargap,
        font=dict(family="Source Sans Pro, sans-serif", color="#0F172A", size=13),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0", font=dict(size=12), align="left"),
    )
    category_axis = dict(
        categoryorder="array",
        categoryarray=names,
        title=None,
        showgrid=False,
        automargin=True,
        tickangle=0 if orientation == "h" or count <= 4 else -25,
    )
    value_settings = _percent_axis(metric) if metric == TREND_MARGIN else _currency_axis(metric)
    value_settings["showgrid"] = True
    value_settings["gridcolor"] = "#E2E8F0"
    value_settings["zeroline"] = True
    value_settings["zerolinecolor"] = "#CBD5E1"
    value_settings["automargin"] = True
    if value_axis == "x":
        figure.update_yaxes(**category_axis)
        figure.update_xaxes(**value_settings)
    else:
        figure.update_xaxes(**category_axis)
        figure.update_yaxes(**value_settings)
    return figure


def build_executive_insights(
    *,
    categories: pd.DataFrame,
    regions: pd.DataFrame,
    comparison_ready: bool,
    revenue_change,
    margin_change,
    prior_window: str | None,
    discount_bands: pd.DataFrame | None,
) -> list[ExecutiveInsight]:
    """Three to five filter-aware observations. Missing comparisons are omitted."""

    insights = [
        insight
        for insight in (
            _category_concentration(categories),
            _category_profit_gap(categories),
            _regional_insight(regions),
            _period_insight(comparison_ready, revenue_change, margin_change, prior_window),
            _discount_insight(discount_bands),
        )
        if insight is not None
    ]
    return insights[:5]


def _category_concentration(categories: pd.DataFrame) -> ExecutiveInsight | None:
    if categories.empty or not categories["revenue"].notna().any():
        return None

    ranked = categories.sort_values("revenue", ascending=False)
    leader = ranked.iloc[0]
    if len(categories) == 1:
        return ExecutiveInsight(
            "Category focus",
            (
                f"This view includes only {leader['name']}, with {_money(leader['revenue'])} "
                f"of revenue and {_margin_phrase(leader['margin'])}."
            ),
        )

    if float(leader["revenue"]) == 0 or pd.isna(leader["revenue_share"]):
        return ExecutiveInsight(
            "Revenue concentration",
            "Selected categories have no revenue, so a revenue share is unavailable.",
        )

    margin_rows = categories.dropna(subset=["margin"])
    if len(margin_rows) < 2:
        return ExecutiveInsight(
            "Revenue concentration",
            (
                f"{leader['name']} accounts for {leader['revenue_share']:.1f}% of revenue "
                f"({_money(leader['revenue'])})."
            ),
        )

    best = margin_rows.sort_values("margin", ascending=False).iloc[0]
    weakest = margin_rows.sort_values("margin", ascending=True).iloc[0]
    gap = float(best["margin"] - weakest["margin"])
    if weakest["name"] == leader["name"]:
        detail = (
            f"{leader['name']} also has the lowest margin among the selected categories, "
            f"at {weakest['margin']:.2f}%."
        )
    else:
        detail = (
            f"{weakest['name']} contributes {weakest['revenue_share']:.1f}% of revenue, "
            f"but its {weakest['margin']:.2f}% margin is {gap:.1f} percentage points below "
            f"{best['name']}."
        )
    return ExecutiveInsight(
        "Revenue concentration",
        (
            f"{leader['name']} accounts for {leader['revenue_share']:.1f}% of revenue "
            f"({_money(leader['revenue'])}). {detail}"
        ),
    )


def _category_profit_gap(categories: pd.DataFrame) -> ExecutiveInsight | None:
    if len(categories) < 2:
        return None

    losses = categories.loc[categories["profit"] < 0].sort_values("profit")
    if not losses.empty:
        worst = losses.iloc[0]
        names = ", ".join(losses["name"].astype(str))
        return ExecutiveInsight(
            "Profitability risk",
            (
                f"{names} recorded negative profit in this selection. {worst['name']} is the "
                f"largest loss at {_money(worst['profit'])} on {_money(worst['revenue'])} of revenue. "
                "Revenue volume does not make that result profitable."
            ),
        )

    if not categories["profit_share"].notna().any():
        return None

    gap = categories["revenue_share"] - categories["profit_share"]
    if float(gap.max()) < 1:
        return None

    overstated = categories.loc[gap.idxmax()]
    understated = categories.loc[gap.idxmin()]
    if overstated["name"] == understated["name"]:
        return None
    return ExecutiveInsight(
        "Revenue and profit diverge",
        (
            f"{overstated['name']} contributes {overstated['revenue_share']:.1f}% of revenue "
            f"but {overstated['profit_share']:.1f}% of profit. {understated['name']} contributes "
            f"{understated['revenue_share']:.1f}% of revenue and {understated['profit_share']:.1f}% "
            "of profit. Profit contribution does not follow revenue share."
        ),
    )


def _regional_insight(regions: pd.DataFrame) -> ExecutiveInsight | None:
    if regions.empty:
        return None

    if len(regions) == 1:
        row = regions.iloc[0]
        outcome = "a loss" if float(row["profit"]) < 0 else "profit"
        return ExecutiveInsight(
            "Regional focus",
            (
                f"This view includes only {row['name']}, with {_money(row['revenue'])} of revenue "
                f"and {outcome} of {_money(abs(float(row['profit'])))} at {_margin_phrase(row['margin'])}."
            ),
        )

    revenue_leader = regions.sort_values("revenue", ascending=False).iloc[0]
    profit_leader = regions.sort_values("profit", ascending=False).iloc[0]
    losses = regions.loc[regions["profit"] < 0].sort_values("profit")
    if not losses.empty:
        worst = losses.iloc[0]
        count = int(len(losses))
        noun = "region has" if count == 1 else "regions have"
        return ExecutiveInsight(
            "Regional profitability",
            (
                f"{revenue_leader['name']} generates {revenue_leader['revenue_share']:.1f}% of revenue "
                f"({_money(revenue_leader['revenue'])}). {count} {noun} negative profit, including "
                f"{worst['name']} at a loss of {_money(abs(float(worst['profit'])))} on "
                f"{_money(worst['revenue'])} of revenue. High revenue is not treated as profitability."
            ),
        )

    margin_rows = regions.dropna(subset=["margin"])
    if margin_rows.empty or pd.isna(revenue_leader["revenue_share"]):
        return ExecutiveInsight(
            "Regional focus",
            f"{revenue_leader['name']} is in the selected view, and a profit margin is unavailable.",
        )

    lowest = margin_rows.sort_values("margin", ascending=True).iloc[0]
    if profit_leader["name"] == revenue_leader["name"]:
        profit_clause = f"and also leads profit at {_money(profit_leader['profit'])}"
    else:
        profit_clause = (
            f"while {profit_leader['name']} leads profit at {_money(profit_leader['profit'])}"
        )
    return ExecutiveInsight(
        "Regional profitability",
        (
            f"{revenue_leader['name']} generates {revenue_leader['revenue_share']:.1f}% of revenue "
            f"({_money(revenue_leader['revenue'])}) {profit_clause}. {lowest['name']} has the lowest "
            f"profit margin at {lowest['margin']:.2f}% on {_money(lowest['revenue'])} of revenue. "
            "The revenue ranking and the margin ranking are separate findings."
        ),
    )


def _period_insight(comparison_ready, revenue_change, margin_change, prior_window) -> ExecutiveInsight | None:
    if not comparison_ready or not prior_window:
        return None

    parts = []
    if revenue_change is not None:
        parts.append(f"revenue is {_movement(revenue_change, 'percent')}")
    if margin_change is not None:
        parts.append(f"the profit margin is {_movement(margin_change, 'points')}")
    if not parts:
        return None

    direction = ""
    if (
        revenue_change is not None
        and margin_change is not None
        and revenue_change * margin_change < 0
    ):
        direction = " Revenue and margin moved in different directions."
    joined = " and ".join(parts)
    return ExecutiveInsight(
        "Period comparison",
        f"Versus {prior_window}, {joined}.{direction}",
    )


def _discount_insight(bands: pd.DataFrame | None) -> ExecutiveInsight | None:
    if bands is None or bands.empty:
        return None

    base_rows = bands.loc[bands["band"] == "No discount"]
    if base_rows.empty or pd.isna(base_rows.iloc[0]["margin"]):
        return None

    base = base_rows.iloc[0]
    total_revenue = float(bands["revenue"].sum())
    candidates = bands.loc[bands["band"] != "No discount"].dropna(subset=["margin"])
    candidates = candidates.loc[candidates["revenue"] > 0]
    if total_revenue > 0:
        candidates = candidates.loc[candidates["revenue"] / total_revenue >= 0.01]
    if candidates.empty:
        return None

    # Prefer the deepest discount band that actually has a lower margin.
    ordered = [label for label in reversed(DISCOUNT_LABELS) if label != "No discount"]
    contrast = None
    for label in ordered:
        match = candidates.loc[candidates["band"] == label]
        if match.empty:
            continue
        row = match.iloc[0]
        if float(row["margin"]) < float(base["margin"]) - 1:
            contrast = row
            break
    if contrast is None:
        return None

    return ExecutiveInsight(
        "Discount and margin",
        (
            f"Lines with no discount show a {base['margin']:.2f}% margin on {_money(base['revenue'])} "
            f"of revenue. Lines in the {contrast['band']} band show a {contrast['margin']:.2f}% margin on "
            f"{_money(contrast['revenue'])} of revenue. The margin is lower in the higher discount band. "
            "This is an association in the filtered orders, not evidence that the discount caused the difference."
        ),
    )


def _movement(change, kind: str) -> str:
    magnitude = abs(float(change))
    if magnitude < 0.05:
        if kind == "points":
            return "unchanged"
        return "unchanged"
    if kind == "points":
        word = "higher" if change > 0 else "lower"
        return f"{magnitude:.1f} percentage points {word}"
    word = "higher" if change > 0 else "lower"
    return f"{magnitude:.1f}% {word}"


def _add_trend_trace(figure, frame, column, name, color, axis="y", rich=True):
    point_count = int(frame[column].notna().sum())
    if point_count <= 1:
        mode = "markers"
    elif point_count <= 16:
        mode = "lines+markers"
    else:
        mode = "lines"

    if rich:
        customdata = np.column_stack(
            [
                frame["label"].astype(str),
                [_money_or_unavailable(value) for value in frame["revenue"]],
                [_money_or_unavailable(value) for value in frame["profit"]],
                [_margin_or_unavailable(value) for value in frame["margin"]],
            ]
        )
        hovertemplate = (
            "%{customdata[0]}<br>Revenue: %{customdata[1]}"
            "<br>Profit: %{customdata[2]}<br>Margin: %{customdata[3]}<extra></extra>"
        )
    else:
        formatted = [
            _margin_or_unavailable(value) if column == "margin" else _money_or_unavailable(value)
            for value in frame[column]
        ]
        customdata = np.column_stack([frame["label"].astype(str), formatted])
        hovertemplate = "%{customdata[0]}<br>" + name + ": %{customdata[1]}<extra></extra>"

    figure.add_trace(
        go.Scatter(
            x=frame["period"],
            y=frame[column],
            name=name,
            mode=mode,
            yaxis=axis,
            line=dict(color=color, width=2.4),
            marker=dict(color=color, size=7),
            connectgaps=False,
            customdata=customdata,
            hovertemplate=hovertemplate,
        )
    )


def _currency_axis(title, overlaying=None, side=None):
    axis = dict(
        title=title,
        tickformat="$,.0f",
        separatethousands=True,
        showgrid=True,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#CBD5E1",
        rangemode="normal",
    )
    if overlaying:
        axis["overlaying"] = overlaying
        axis["side"] = side
        axis["showgrid"] = False
    return axis


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


def _tickformat(frequency: str) -> str:
    if frequency == "D":
        return "%b %d"
    if frequency == "W":
        return "%b %d"
    return "%b %Y"


def _performance_hover(row: dict) -> str:
    share = "unavailable" if pd.isna(row["revenue_share"]) else f"{row['revenue_share']:.1f}% of total"
    return (
        f"{row['name']}<br>Revenue: {_money(row['revenue'])} ({share})"
        f"<br>Profit: {_money(row['profit'])}<br>Margin: {_margin_or_unavailable(row['margin'])}"
    )


def _money(value) -> str:
    if pd.isna(value):
        return "unavailable"
    return format_exact_currency(value)


def _money_or_unavailable(value) -> str:
    return _money(value)


def _margin_or_unavailable(value) -> str:
    if pd.isna(value):
        return "unavailable"
    return f"{float(value):.2f}%"


def _margin_phrase(value) -> str:
    if pd.isna(value):
        return "a profit margin that is unavailable because revenue is zero"
    return f"a {float(value):.2f}% profit margin"
