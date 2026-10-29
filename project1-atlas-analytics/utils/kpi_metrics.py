"""KPI comparison copy and sparkline aggregation for the executive dashboard.

Sparklines use only rows inside the requested reporting window. Missing
time buckets stay empty (NaN). They are not filled with zeros.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.palette import (
    CHART_HOVERLABEL,
    FONT_STACK,
    MARGIN_COLOR,
    NEGATIVE,
    ORDERS_COLOR,
    POSITIVE,
    PROFIT_COLOR,
    REVENUE_COLOR,
    TEXT,
    TEXT_SECONDARY,
)


# Short windows stay daily, medium windows roll up to weeks, and longer
# reporting periods use months so the sparkline stays readable.
DAILY_MAX_DAYS = 45
WEEKLY_MAX_DAYS = 180

SPARKLINE_COLORS = {
    "revenue": REVENUE_COLOR,
    "profit": PROFIT_COLOR,
    "margin": MARGIN_COLOR,
    "orders": ORDERS_COLOR,
}

COMPARISON_POSITIVE = POSITIVE
COMPARISON_NEGATIVE = NEGATIVE
COMPARISON_MUTED = TEXT_SECONDARY

GRAIN_NAMES = {
    "D": "Daily",
    "W": "Weekly",
    "M": "Monthly",
}


@dataclass(frozen=True)
class KpiTrends:
    """Chronological sparkline frames for the four executive KPIs."""

    frequency: str
    grain: str
    revenue: pd.DataFrame
    profit: pd.DataFrame
    margin: pd.DataFrame
    orders: pd.DataFrame


def resolve_frequency(period_days: int) -> str:
    """Choose daily, weekly, or monthly buckets from the window length."""

    if period_days <= DAILY_MAX_DAYS:
        return "D"
    if period_days <= WEEKLY_MAX_DAYS:
        return "W"
    return "M"


def format_display_date(value) -> str:
    """Format a date as 'January 1, 2014'."""

    timestamp = pd.Timestamp(value)
    return f"{timestamp.strftime('%B')} {timestamp.day}, {timestamp.year}"


def prior_period_caption(start, end, available: bool) -> str:
    """Exact prior-window dates, or the unavailable comparison message."""

    if not available:
        return "Comparison unavailable"

    return (
        f"Prior period: {format_display_date(start)}"
        f" – {format_display_date(end)}"
    )


def format_headline_currency(value: float) -> str:
    """Compact headline currency. Millions keep two decimals."""

    numeric = float(value)
    sign = "-" if numeric < 0 else ""
    magnitude = abs(numeric)

    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.2f}M"

    return f"{sign}${magnitude:,.0f}"


def format_exact_currency(value: float) -> str:
    """Full currency with cents, for tooltips."""

    numeric = float(value)
    sign = "-" if numeric < 0 else ""
    return f"{sign}${abs(numeric):,.2f}"


def format_delta_currency(value: float) -> str:
    """Currency for a profit movement when a percent rate would mislead."""

    numeric = abs(float(value))
    sign = "-" if float(value) < 0 else ""

    if numeric >= 1_000_000:
        return f"{sign}${numeric / 1_000_000:.2f}M"
    if numeric >= 10_000:
        return f"{sign}${numeric / 1_000:.1f}K"

    return f"{sign}${numeric:,.0f}"


def format_period_comparison(
    change,
    *,
    unit: str = "%",
    metric: str = "generic",
    current=None,
    previous=None,
) -> tuple[str, str]:
    """Comparison line and color.

    Profit is not shown as a conventional growth rate when the prior period
    was already a loss. A move from -100 to -50 is a narrower loss, not +50%
    growth. Zero or missing baselines return "Comparison unavailable".
    """

    if change is None or (metric == "profit" and previous is not None and previous < 0 and current is None):
        return "Comparison unavailable", COMPARISON_MUTED

    if metric == "profit" and previous is not None and previous < 0:
        current_value = float(current)
        delta = current_value - float(previous)
        amount = format_delta_currency(abs(delta))

        if current_value > 0:
            return "▲ Returned to profit vs prior period", COMPARISON_POSITIVE
        if current_value == 0:
            return "▲ Reached break-even vs prior period", COMPARISON_POSITIVE
        if delta > 0:
            return (
                f"▲ Loss narrowed by {amount} vs prior period",
                COMPARISON_POSITIVE,
            )
        if delta < 0:
            return (
                f"▼ Loss widened by {amount} vs prior period",
                COMPARISON_NEGATIVE,
            )
        return "Loss unchanged vs prior period", COMPARISON_MUTED

    rounded = round(abs(float(change)), 1)
    if rounded == 0:
        return f"0.0{unit} vs prior period", COMPARISON_MUTED
    if change > 0:
        return f"▲ {rounded:.1f}{unit} vs prior period", COMPARISON_POSITIVE
    return f"▼ {rounded:.1f}{unit} vs prior period", COMPARISON_NEGATIVE


def aggregate_kpi_trends(df: pd.DataFrame, start_date, end_date) -> KpiTrends:
    """Aggregate filtered orders into sparkline frames.

    Revenue and profit are sums. Profit margin is period profit divided by
    period revenue. Orders are distinct Order_ID values inside each bucket.
    Distinct orders in separate buckets are not forced to equal the KPI total.
    """

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    period_days = int((end_ts - start_ts).days) + 1
    frequency = resolve_frequency(max(period_days, 1))
    index = _bucket_index(start_ts, end_ts, frequency)

    columns = ["Order_Date", "Order_ID", "Sales", "Profit"]
    if df.empty:
        grouped = pd.DataFrame(
            index=index,
            data={"revenue": np.nan, "profit": np.nan, "orders": np.nan},
        )
    else:
        work = df.loc[:, columns].copy()
        order_day = work["Order_Date"].dt.normalize()
        work = work.loc[(order_day >= start_ts) & (order_day <= end_ts)]
        work = work.copy()

        if work.empty:
            grouped = pd.DataFrame(
                index=index,
                data={"revenue": np.nan, "profit": np.nan, "orders": np.nan},
            )
        else:
            buckets = _bucket_start(work["Order_Date"], frequency)
            grouped = (
                work.groupby(buckets, sort=True)
                .agg(
                    revenue=("Sales", "sum"),
                    profit=("Profit", "sum"),
                    orders=("Order_ID", "nunique"),
                )
            )
            grouped.index = pd.to_datetime(grouped.index).tz_localize(None).normalize()
            grouped = grouped.reindex(index)

    revenue = grouped["revenue"]
    profit = grouped["profit"]
    # Zero-revenue buckets have no defined margin. Do not average line margins.
    margin = profit / revenue.mask(revenue == 0) * 100

    return KpiTrends(
        frequency=frequency,
        grain=GRAIN_NAMES[frequency],
        revenue=_series_frame(index, revenue, frequency),
        profit=_series_frame(index, profit, frequency),
        margin=_series_frame(index, margin, frequency),
        orders=_series_frame(index, grouped["orders"], frequency),
    )


def build_sparkline(frame: pd.DataFrame, metric: str):
    """Minimal Plotly sparkline, or None when every bucket is empty."""

    if frame.empty or not frame["value"].notna().any():
        return None

    color = SPARKLINE_COLORS[metric]
    point_count = int(frame["value"].notna().sum())
    mode = "markers" if point_count == 1 else "lines"
    customdata = np.column_stack(
        [
            frame["label"].astype(str),
            [_format_hover_value(metric, value) for value in frame["value"]],
        ]
    )

    trace = go.Scatter(
        x=frame["period"],
        y=frame["value"],
        mode=mode,
        line=dict(color=color, width=2.2),
        marker=dict(color=color, size=8),
        connectgaps=False,
        customdata=customdata,
        hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
        cliponaxis=False,
    )
    if mode == "lines":
        trace.fill = "tozeroy"
        trace.fillcolor = _rgba(color, 0.14)

    figure = go.Figure(data=[trace])
    figure.update_layout(
        height=78,
        margin=dict(l=2, r=2, t=10, b=2),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        font=dict(family=FONT_STACK, size=12, color=TEXT),
        hoverlabel=CHART_HOVERLABEL,
    )
    figure.update_xaxes(
        visible=False,
        showgrid=False,
        zeroline=False,
        fixedrange=True,
        type="date",
    )
    figure.update_yaxes(
        visible=False,
        showgrid=False,
        zeroline=False,
        fixedrange=True,
        rangemode="normal",
        range=_padded_y_range(frame["value"]),
    )
    return figure


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


def _series_frame(index: pd.DatetimeIndex, values, frequency: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period": pd.to_datetime(index),
            "value": pd.to_numeric(values, errors="coerce"),
            "label": _labels(index, frequency),
        }
    )


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


def _format_hover_value(metric: str, value) -> str:
    if pd.isna(value):
        return "No transactions"
    if metric == "orders":
        return f"{int(value):,} orders"
    if metric == "margin":
        return f"{float(value):.2f}%"
    return format_exact_currency(value)


def _padded_y_range(values: pd.Series) -> list[float]:
    """Keep peaks and negative values inside the sparkline, without inventing points."""

    present = pd.to_numeric(values, errors="coerce").dropna()
    low = float(present.min())
    high = float(present.max())
    span = high - low
    cushion = max(abs(low) * 0.2, 1.0) if span == 0 else span * 0.18
    return [low - cushion, high + cushion]


def _rgba(hex_color: str, alpha: float) -> str:
    color = hex_color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red},{green},{blue},{alpha})"
