"""Shipping and logistics KPIs for the regional intelligence page.

Order-to-shipment days measure Ship_Date minus Order_Date. That is processing
time until shipment, not delivery time to the customer. Shipping cost is never
subtracted from recorded profit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.palette import (
    ACCENT,
    CARD,
    CATEGORICAL,
    CHART_FONT,
    CHART_HOVERLABEL,
    GRID,
    NEGATIVE,
    PROFIT_COLOR,
    REVENUE_COLOR,
    SHIP_COST_COLOR,
    SHIP_DAYS_COLOR,
    SHIP_RATIO_COLOR,
    TEXT_SECONDARY,
    ZEROLINE,
)

from utils.kpi_metrics import (
    GRAIN_NAMES,
    format_exact_currency,
    resolve_frequency,
)


SHIP_MODE_COLORS = {
    "Standard Class": CATEGORICAL[0],
    "Second Class": CATEGORICAL[1],
    "First Class": CATEGORICAL[2],
    "Same Day": CATEGORICAL[3],
}

SHIP_MODE_METRICS = {
    "Revenue": ("revenue", "currency", REVENUE_COLOR),
    "Profit": ("profit", "currency", PROFIT_COLOR),
    "Shipping Cost": ("shipping_cost", "currency", SHIP_COST_COLOR),
    "Shipping Cost Ratio": ("shipping_cost_ratio", "percent", SHIP_RATIO_COLOR),
    "Average Order-to-Shipment Days": ("avg_processing_days", "days", SHIP_DAYS_COLOR),
}

REGION_SHIP_METRICS = {
    "Total Shipping Cost": ("shipping_cost", "currency", ACCENT),
    "Shipping Cost Ratio": ("shipping_cost_ratio", "percent", SHIP_COST_COLOR),
}

TREND_METRICS = (
    "Total Shipping Cost",
    "Shipping Cost Ratio",
    "Average Order-to-Shipment Days",
)

NEGATIVE_COLOR = NEGATIVE


def filter_shipping_modes(df: pd.DataFrame, modes) -> pd.DataFrame:
    """Optional logistics-only Ship_Mode filter. Does not replace page filters."""

    if df.empty or "Ship_Mode" not in df.columns:
        return df.iloc[0:0] if df.empty else df
    return df.loc[df["Ship_Mode"].isin(modes)]


def calculate_processing_intervals(df: pd.DataFrame) -> pd.DataFrame:
    """Attach order-to-shipment days and validity flags.

    Valid intervals have both dates and a non-negative day count.
    Negative intervals are kept in the frame for auditing but excluded from averages.
    """

    if df.empty:
        empty = df.copy()
        empty["processing_days"] = pd.Series(dtype="float64")
        empty["interval_valid"] = pd.Series(dtype="bool")
        empty["interval_negative"] = pd.Series(dtype="bool")
        empty["interval_missing"] = pd.Series(dtype="bool")
        return empty

    work = df.copy()
    if "Order_Date" not in work.columns or "Ship_Date" not in work.columns:
        work["processing_days"] = np.nan
        work["interval_valid"] = False
        work["interval_negative"] = False
        work["interval_missing"] = True
        return work

    days = (work["Ship_Date"] - work["Order_Date"]).dt.days
    missing = work["Order_Date"].isna() | work["Ship_Date"].isna() | days.isna()
    negative = (~missing) & (days < 0)
    work["processing_days"] = days.astype("float64")
    work["interval_missing"] = missing
    work["interval_negative"] = negative
    work["interval_valid"] = (~missing) & (~negative)
    return work


def calculate_logistics_kpis(df: pd.DataFrame) -> dict:
    """Headline logistics KPIs for the current filter.

    Average processing days and same-day rate are line-item metrics over valid
    order-to-shipment intervals. Shipping cost ratio is undefined when revenue is zero.
    """

    empty = {
        "shipping_cost": 0.0,
        "revenue": 0.0,
        "shipping_cost_ratio": None,
        "avg_processing_days": None,
        "median_processing_days": None,
        "same_day_rate": None,
        "valid_intervals": 0,
        "missing_intervals": 0,
        "negative_intervals": 0,
        "line_items": 0,
        "orders": 0,
    }
    if df.empty or "Shipping_Cost" not in df.columns:
        return empty

    work = calculate_processing_intervals(df)
    revenue = float(work["Sales"].sum()) if "Sales" in work.columns else 0.0
    shipping_cost = float(work["Shipping_Cost"].sum())
    valid = work.loc[work["interval_valid"], "processing_days"]
    return {
        "shipping_cost": shipping_cost,
        "revenue": revenue,
        "shipping_cost_ratio": None if revenue == 0 else shipping_cost / revenue * 100,
        "avg_processing_days": None if valid.empty else float(valid.mean()),
        "median_processing_days": None if valid.empty else float(valid.median()),
        "same_day_rate": None if valid.empty else float((valid == 0).mean() * 100),
        "valid_intervals": int(work["interval_valid"].sum()),
        "missing_intervals": int(work["interval_missing"].sum()),
        "negative_intervals": int(work["interval_negative"].sum()),
        "line_items": len(work),
        "orders": int(work["Order_ID"].nunique()) if "Order_ID" in work.columns else 0,
    }


def aggregate_shipping_modes(df: pd.DataFrame) -> pd.DataFrame:
    """One row per shipping mode with revenue, cost, margin, and processing metrics."""

    columns = [
        "ship_mode",
        "revenue",
        "profit",
        "margin",
        "orders",
        "line_items",
        "shipping_cost",
        "shipping_cost_ratio",
        "avg_processing_days",
        "median_processing_days",
        "same_day_rate",
        "valid_intervals",
        "negative_intervals",
        "missing_intervals",
    ]
    if df.empty or "Ship_Mode" not in df.columns or "Shipping_Cost" not in df.columns:
        return pd.DataFrame(columns=columns)

    work = calculate_processing_intervals(df)
    frames = []
    for mode, part in work.groupby("Ship_Mode", sort=True):
        valid = part.loc[part["interval_valid"], "processing_days"]
        revenue = float(part["Sales"].sum())
        profit = float(part["Profit"].sum())
        shipping_cost = float(part["Shipping_Cost"].sum())
        frames.append(
            {
                "ship_mode": mode,
                "revenue": revenue,
                "profit": profit,
                "margin": None if revenue == 0 else profit / revenue * 100,
                "orders": int(part["Order_ID"].nunique()),
                "line_items": len(part),
                "shipping_cost": shipping_cost,
                "shipping_cost_ratio": None if revenue == 0 else shipping_cost / revenue * 100,
                "avg_processing_days": None if valid.empty else float(valid.mean()),
                "median_processing_days": None if valid.empty else float(valid.median()),
                "same_day_rate": None if valid.empty else float((valid == 0).mean() * 100),
                "valid_intervals": int(part["interval_valid"].sum()),
                "negative_intervals": int(part["interval_negative"].sum()),
                "missing_intervals": int(part["interval_missing"].sum()),
            }
        )
    return pd.DataFrame(frames).sort_values("shipping_cost", ascending=False).reset_index(drop=True)


def aggregate_regional_shipping_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, shipping cost, and cost ratio by region."""

    columns = ["region", "revenue", "shipping_cost", "shipping_cost_ratio", "orders", "line_items"]
    if df.empty or "Region" not in df.columns or "Shipping_Cost" not in df.columns:
        return pd.DataFrame(columns=columns)

    grouped = (
        df.groupby("Region", as_index=False)
        .agg(
            revenue=("Sales", "sum"),
            shipping_cost=("Shipping_Cost", "sum"),
            orders=("Order_ID", "nunique"),
            line_items=("Sales", "size"),
        )
        .rename(columns={"Region": "region"})
    )
    grouped["shipping_cost_ratio"] = (
        grouped["shipping_cost"] / grouped["revenue"].mask(grouped["revenue"] == 0) * 100
    )
    return grouped.sort_values("shipping_cost", ascending=False).reset_index(drop=True)


def aggregate_processing_time(df: pd.DataFrame) -> dict:
    """Distribution and mode-level averages for valid order-to-shipment intervals."""

    work = calculate_processing_intervals(df)
    valid = work.loc[work["interval_valid"]]
    distribution = (
        valid["processing_days"]
        .value_counts()
        .sort_index()
        .rename_axis("days")
        .reset_index(name="line_items")
        if not valid.empty
        else pd.DataFrame(columns=["days", "line_items"])
    )
    by_mode = aggregate_shipping_modes(df).loc[
        :,
        [
            "ship_mode",
            "avg_processing_days",
            "median_processing_days",
            "same_day_rate",
            "valid_intervals",
            "line_items",
        ],
    ]
    return {
        "distribution": distribution,
        "by_mode": by_mode,
        "valid_intervals": int(work["interval_valid"].sum()) if not work.empty else 0,
        "negative_intervals": int(work["interval_negative"].sum()) if not work.empty else 0,
        "missing_intervals": int(work["interval_missing"].sum()) if not work.empty else 0,
        "avg_processing_days": None if valid.empty else float(valid["processing_days"].mean()),
        "median_processing_days": None if valid.empty else float(valid["processing_days"].median()),
        "same_day_rate": None if valid.empty else float((valid["processing_days"] == 0).mean() * 100),
    }


def aggregate_shipping_trends(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Time series of shipping cost, cost ratio, and average processing days.

    Buckets follow the executive sparkline rule. Ratios use aggregated sums.
    Processing averages use only valid line-item intervals inside each bucket.
    """

    columns = [
        "period",
        "label",
        "shipping_cost",
        "revenue",
        "shipping_cost_ratio",
        "avg_processing_days",
        "frequency",
        "grain",
    ]
    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    period_days = int((end_ts - start_ts).days) + 1
    frequency = resolve_frequency(max(period_days, 1))
    grain = GRAIN_NAMES[frequency]
    index = _bucket_index(start_ts, end_ts, frequency)

    if df.empty or "Shipping_Cost" not in df.columns:
        return pd.DataFrame(
            {
                "period": index,
                "label": _labels(index, frequency),
                "shipping_cost": np.nan,
                "revenue": np.nan,
                "shipping_cost_ratio": np.nan,
                "avg_processing_days": np.nan,
                "frequency": frequency,
                "grain": grain,
            }
        )

    work = calculate_processing_intervals(df)
    order_day = work["Order_Date"].dt.normalize()
    work = work.loc[(order_day >= start_ts) & (order_day <= end_ts)].copy()
    if work.empty:
        return pd.DataFrame(
            {
                "period": index,
                "label": _labels(index, frequency),
                "shipping_cost": np.nan,
                "revenue": np.nan,
                "shipping_cost_ratio": np.nan,
                "avg_processing_days": np.nan,
                "frequency": frequency,
                "grain": grain,
            }
        )

    buckets = _bucket_start(work["Order_Date"], frequency)
    totals = (
        work.groupby(buckets, sort=True)
        .agg(shipping_cost=("Shipping_Cost", "sum"), revenue=("Sales", "sum"))
    )
    valid = work.loc[work["interval_valid"]]
    if valid.empty:
        days = pd.Series(dtype="float64")
    else:
        days = valid.groupby(_bucket_start(valid["Order_Date"], frequency))["processing_days"].mean()

    totals.index = pd.to_datetime(totals.index).tz_localize(None).normalize()
    days.index = pd.to_datetime(days.index).tz_localize(None).normalize() if len(days) else days.index
    totals = totals.reindex(index)
    days = days.reindex(index)
    ratio = totals["shipping_cost"] / totals["revenue"].mask(totals["revenue"] == 0) * 100

    return pd.DataFrame(
        {
            "period": index,
            "label": _labels(index, frequency),
            "shipping_cost": totals["shipping_cost"].to_numpy(),
            "revenue": totals["revenue"].to_numpy(),
            "shipping_cost_ratio": ratio.to_numpy(),
            "avg_processing_days": days.to_numpy(),
            "frequency": frequency,
            "grain": grain,
        }
    )


def generate_logistics_insights(
    modes: pd.DataFrame,
    regions: pd.DataFrame,
    kpis: dict,
) -> list[dict]:
    """Up to five logistics notes from the filtered view."""

    if modes.empty and regions.empty:
        return [{"title": "No logistics results", "body": "No transactions match the current filters."}]

    notes = [
        _shipping_cost_leader(modes),
        _shipping_cost_intensity(modes),
        _processing_time_leader(modes),
        _regional_shipping_exposure(regions),
        _same_day_leader(modes),
        _profitability_comparison(modes),
    ]
    return [note for note in notes if note][:5]


def build_shipping_mode_chart(modes: pd.DataFrame, metric: str):
    """Ranked horizontal bars for one shipping-mode metric."""

    spec = SHIP_MODE_METRICS.get(metric, SHIP_MODE_METRICS["Shipping Cost"])
    return _ranked_bar(
        modes,
        label_column="ship_mode",
        value_column=spec[0],
        color=spec[2],
        kind=spec[1],
        axis_title=metric,
        color_map=SHIP_MODE_COLORS,
    )


def build_regional_shipping_chart(regions: pd.DataFrame, metric: str):
    """Regional shipping cost or cost-ratio comparison."""

    spec = REGION_SHIP_METRICS.get(metric, REGION_SHIP_METRICS["Total Shipping Cost"])
    return _ranked_bar(
        regions,
        label_column="region",
        value_column=spec[0],
        color=spec[2],
        kind=spec[1],
        axis_title=metric,
    )


def build_processing_distribution(distribution: pd.DataFrame):
    """Line-item counts by order-to-shipment days."""

    if distribution.empty or not distribution["line_items"].notna().any():
        return None
    figure = go.Figure(
        data=[
            go.Bar(
                x=distribution["days"],
                y=distribution["line_items"],
                marker=dict(color=SHIP_DAYS_COLOR),
                hovertemplate=(
                    "Order-to-shipment days: %{x}<br>Line items: %{y:,}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(**_chart_layout(320), showlegend=False, bargap=0.2)
    figure.update_xaxes(title="Order-to-shipment days", showgrid=False, dtick=1, automargin=True)
    figure.update_yaxes(
        title="Line items",
        showgrid=True,
        gridcolor=GRID,
        tickformat=",",
    )
    return figure


def build_processing_by_mode(by_mode: pd.DataFrame):
    """Average processing days by shipping mode."""

    return _ranked_bar(
        by_mode,
        label_column="ship_mode",
        value_column="avg_processing_days",
        color=SHIP_DAYS_COLOR,
        kind="days",
        axis_title="Average order-to-shipment days",
        color_map=SHIP_MODE_COLORS,
    )


def build_cost_margin_scatter(modes: pd.DataFrame):
    """Shipping cost ratio vs profit margin by shipping mode. Observational only."""

    if modes.empty:
        return None
    plot = modes.dropna(subset=["shipping_cost_ratio", "margin"])
    if plot.empty:
        return None
    colors = [SHIP_MODE_COLORS.get(mode, ACCENT) for mode in plot["ship_mode"]]
    hover = [
        (
            f"{row.ship_mode}<br>Shipping cost ratio: {row.shipping_cost_ratio:.2f}%"
            f"<br>Profit margin: {row.margin:.2f}%"
            f"<br>Shipping cost: {format_exact_currency(row.shipping_cost)}"
            f"<br>Revenue: {format_exact_currency(row.revenue)}"
        )
        for row in plot.itertuples()
    ]
    # Labels near the plot edges anchor inward so they are not clipped.
    ratios = plot["shipping_cost_ratio"].astype(float)
    low, span = float(ratios.min()), float(ratios.max() - ratios.min())
    positions = []
    for value in ratios:
        share = (value - low) / span if span else 0.5
        positions.append("top right" if share < 0.15 else "top left" if share > 0.85 else "top center")
    figure = go.Figure(
        data=[
            go.Scatter(
                x=plot["shipping_cost_ratio"],
                y=plot["margin"],
                mode="markers+text",
                text=plot["ship_mode"],
                textposition=positions,
                textfont=dict(color=TEXT_SECONDARY, size=12),
                cliponaxis=False,
                marker=dict(size=14, color=colors),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    figure.update_layout(**_chart_layout(360), showlegend=False)
    figure.update_xaxes(**{**_percent_axis("Shipping cost ratio"), "automargin": True})
    figure.update_yaxes(**{**_percent_axis("Profit margin"), "automargin": True})
    return figure


def build_shipping_trend(trends: pd.DataFrame, metric: str):
    """Single-metric logistics time series."""

    column = {
        "Total Shipping Cost": "shipping_cost",
        "Shipping Cost Ratio": "shipping_cost_ratio",
        "Average Order-to-Shipment Days": "avg_processing_days",
    }.get(metric, "shipping_cost")
    kind = {
        "shipping_cost": "currency",
        "shipping_cost_ratio": "percent",
        "avg_processing_days": "days",
    }[column]
    if trends.empty or not trends[column].notna().any():
        return None

    point_count = int(trends[column].notna().sum())
    hover = [_trend_hover(row, column) for row in trends.to_dict("records")]
    figure = go.Figure(
        data=[
            go.Scatter(
                x=trends["period"],
                y=trends[column],
                mode="markers" if point_count == 1 else "lines",
                connectgaps=False,
                line=dict(color=ACCENT, width=2.4),
                marker=dict(color=ACCENT, size=7),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    frequency = str(trends["frequency"].iloc[0])
    figure.update_layout(**_chart_layout(400), showlegend=False)
    figure.update_xaxes(
        title=None,
        showgrid=False,
        tickformat="%b %d" if frequency in {"D", "W"} else "%b %Y",
        automargin=True,
    )
    if kind == "currency":
        figure.update_yaxes(**_currency_axis(metric))
    elif kind == "percent":
        figure.update_yaxes(**_percent_axis(metric))
    else:
        figure.update_yaxes(**_days_axis(metric))
    return figure


def processing_caption(summary: dict) -> str:
    """Explain processing metrics and any excluded intervals."""

    parts = [
        "Order-to-shipment days measure Ship Date minus Order Date. "
        "This is processing time until shipment, not delivery time to the customer."
    ]
    if summary["negative_intervals"]:
        parts.append(
            f"{summary['negative_intervals']:,} line items with negative intervals "
            "were excluded from processing-time averages."
        )
    if summary["missing_intervals"]:
        parts.append(
            f"{summary['missing_intervals']:,} line items with missing dates "
            "were excluded from processing-time averages."
        )
    return " ".join(parts)


def _shipping_cost_leader(modes: pd.DataFrame):
    if modes.empty or not modes["shipping_cost"].notna().any():
        return None
    leader = modes.sort_values(["shipping_cost", "ship_mode"]).iloc[-1]
    return {
        "title": "Shipping cost leader",
        "body": (
            f"{leader['ship_mode']} has the highest total shipping cost in this view at "
            f"{format_exact_currency(leader['shipping_cost'])} across "
            f"{int(leader['line_items']):,} line items."
        ),
    }


def _shipping_cost_intensity(modes: pd.DataFrame):
    valid = modes.dropna(subset=["shipping_cost_ratio"])
    if valid.empty:
        return None
    leader = valid.sort_values(["shipping_cost_ratio", "ship_mode"]).iloc[-1]
    return {
        "title": "Shipping cost intensity",
        "body": (
            f"{leader['ship_mode']} has the highest shipping cost-to-revenue ratio at "
            f"{leader['shipping_cost_ratio']:.2f}% "
            f"({format_exact_currency(leader['shipping_cost'])} on "
            f"{format_exact_currency(leader['revenue'])} of revenue)."
        ),
    }


def _processing_time_leader(modes: pd.DataFrame):
    valid = modes.dropna(subset=["avg_processing_days"])
    if valid.empty:
        return None
    leader = valid.sort_values(["avg_processing_days", "ship_mode"]).iloc[0]
    return {
        "title": "Fastest order-to-shipment processing",
        "body": (
            f"{leader['ship_mode']} has the shortest average order-to-shipment interval "
            f"at {leader['avg_processing_days']:.2f} days per line item. "
            "This is not a delivery-time measure."
        ),
    }


def _regional_shipping_exposure(regions: pd.DataFrame):
    valid = regions.dropna(subset=["shipping_cost_ratio"])
    if valid.empty:
        return None
    leader = valid.sort_values(["shipping_cost_ratio", "region"]).iloc[-1]
    return {
        "title": "Regional shipping exposure",
        "body": (
            f"{leader['region']} has the highest shipping cost ratio in this view at "
            f"{leader['shipping_cost_ratio']:.2f}% "
            f"({format_exact_currency(leader['shipping_cost'])} on "
            f"{format_exact_currency(leader['revenue'])} of revenue)."
        ),
    }


def _same_day_leader(modes: pd.DataFrame):
    valid = modes.dropna(subset=["same_day_rate"])
    if valid.empty:
        return None
    leader = valid.sort_values(["same_day_rate", "ship_mode"]).iloc[-1]
    if float(leader["same_day_rate"]) <= 0:
        return None
    return {
        "title": "Same-day shipment rate",
        "body": (
            f"{leader['ship_mode']} has the highest same-day shipment rate at "
            f"{leader['same_day_rate']:.1f}% of valid line items "
            f"({int(leader['valid_intervals']):,} valid intervals)."
        ),
    }


def _profitability_comparison(modes: pd.DataFrame):
    valid = modes.dropna(subset=["shipping_cost_ratio", "margin"])
    if len(valid) < 2:
        return None
    costliest = valid.sort_values(["shipping_cost_ratio", "ship_mode"]).iloc[-1]
    leanest = valid.sort_values(["shipping_cost_ratio", "ship_mode"]).iloc[0]
    if costliest["ship_mode"] == leanest["ship_mode"]:
        return None
    return {
        "title": "Cost ratio and margin comparison",
        "body": (
            f"{costliest['ship_mode']} has a {costliest['shipping_cost_ratio']:.2f}% shipping cost ratio "
            f"and a {costliest['margin']:.2f}% profit margin, compared with "
            f"{leanest['ship_mode']} at {leanest['shipping_cost_ratio']:.2f}% cost ratio and "
            f"{leanest['margin']:.2f}% margin. These figures describe an observed association, "
            "not a causal effect of shipping cost on profit."
        ),
    }


def _ranked_bar(frame, label_column, value_column, color, kind, axis_title, color_map=None):
    if frame.empty or value_column not in frame.columns:
        return None
    plot_df = frame.dropna(subset=[value_column]).sort_values(value_column, ascending=True)
    if plot_df.empty:
        return None

    colors = []
    for row in plot_df.to_dict("records"):
        if float(row[value_column]) < 0:
            colors.append(NEGATIVE_COLOR)
        elif color_map:
            colors.append(color_map.get(row[label_column], color))
        else:
            colors.append(color)

    hover = []
    for row in plot_df.to_dict("records"):
        value = row[value_column]
        if kind == "currency":
            formatted = format_exact_currency(value)
        elif kind == "percent":
            formatted = f"{float(value):.2f}%"
        else:
            formatted = f"{float(value):.2f} days"
        hover.append(f"{row[label_column]}<br>{axis_title}: {formatted}")

    figure = go.Figure(
        data=[
            go.Bar(
                y=plot_df[label_column],
                x=plot_df[value_column],
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
        height, bargap = max(300, 48 * count + 90), 0.42
    else:
        height, bargap = min(480, max(340, 40 * count + 100)), 0.28
    figure.update_layout(
        height=height,
        margin=dict(l=72, r=36, t=24, b=56, pad=4),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        showlegend=False,
        bargap=bargap,
        font=CHART_FONT,
        hoverlabel=CHART_HOVERLABEL,
    )
    if kind == "currency":
        figure.update_xaxes(**{**_currency_axis(axis_title), "automargin": True})
    elif kind == "percent":
        figure.update_xaxes(**{**_percent_axis(axis_title), "automargin": True})
    else:
        figure.update_xaxes(**{**_days_axis(axis_title), "automargin": True})
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=plot_df[label_column].tolist(),
        title=None,
        showgrid=False,
        automargin=True,
    )
    return figure


def _trend_hover(row: dict, column: str) -> str:
    if pd.isna(row[column]):
        return f"{row['label']}<br>No transactions"
    if column == "shipping_cost":
        value = format_exact_currency(row[column])
    elif column == "shipping_cost_ratio":
        value = f"{float(row[column]):.2f}%"
    else:
        value = f"{float(row[column]):.2f} days"
    revenue = "unavailable" if pd.isna(row["revenue"]) else format_exact_currency(row["revenue"])
    cost = "unavailable" if pd.isna(row["shipping_cost"]) else format_exact_currency(row["shipping_cost"])
    return (
        f"{row['label']}<br>{value}"
        f"<br>Shipping cost: {cost}"
        f"<br>Revenue: {revenue}"
    )


def _chart_layout(height: int) -> dict:
    return dict(
        height=height,
        margin=dict(l=56, r=28, t=40, b=64, pad=4),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=CHART_FONT,
        hoverlabel=CHART_HOVERLABEL,
    )


def _currency_axis(title):
    return dict(
        title=title,
        tickformat="$,.0f",
        showgrid=True,
        gridcolor=GRID,
        zeroline=True,
        zerolinecolor=ZEROLINE,
        rangemode="normal",
    )


def _percent_axis(title):
    return dict(
        title=title,
        ticksuffix="%",
        showgrid=True,
        gridcolor=GRID,
        zeroline=True,
        zerolinecolor=ZEROLINE,
        rangemode="normal",
    )


def _days_axis(title):
    return dict(
        title=title,
        ticksuffix=" days",
        showgrid=True,
        gridcolor=GRID,
        zeroline=True,
        zerolinecolor=ZEROLINE,
        rangemode="tozero",
    )


def _bucket_start(dates: pd.Series, frequency: str) -> pd.Series:
    if frequency == "D":
        return dates.dt.normalize()
    if frequency == "W":
        return dates.dt.to_period("W-SUN").dt.start_time.dt.normalize()
    return dates.dt.to_period("M").dt.to_timestamp().dt.normalize()


def _bucket_index(start_ts: pd.Timestamp, end_ts: pd.Timestamp, frequency: str) -> pd.DatetimeIndex:
    if frequency == "D":
        index = pd.date_range(start_ts, end_ts, freq="D")
    elif frequency == "W":
        index = pd.period_range(start_ts, end_ts, freq="W-SUN").to_timestamp()
    else:
        index = pd.period_range(start_ts, end_ts, freq="M").to_timestamp()
    return pd.to_datetime(index).tz_localize(None).normalize()


def _labels(index: pd.DatetimeIndex, frequency: str) -> list[str]:
    labels = []
    for timestamp in index:
        stamp = pd.Timestamp(timestamp)
        if frequency == "D":
            labels.append(f"{stamp.strftime('%b')} {stamp.day}, {stamp.year}")
        elif frequency == "W":
            labels.append(f"Week of {stamp.strftime('%b')} {stamp.day}, {stamp.year}")
        else:
            labels.append(stamp.strftime("%b %Y"))
    return labels
