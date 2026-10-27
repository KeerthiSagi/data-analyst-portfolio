"""KPI calculations and period-over-period changes.

Terminology used across the app
-------------------------------
* Absolute change       current - previous, in the metric's own unit.
* Percentage change     (current - previous) / previous. Only defined when
                        the previous value is positive.
* Percentage-point (pp) the difference between two percentages. Used for
  change                profit margin; a margin is never shown as a % change.
* Contribution          a group's share of a net change (see contribution.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from cause import config
from cause.data import count_orders
from cause.periods import PeriodComparison


class Metric(str, Enum):
    REVENUE = "revenue"
    PROFIT = "profit"
    ORDERS = "orders"
    AOV = "aov"
    MARGIN = "margin"

    @property
    def label(self) -> str:
        return METRIC_LABELS[self]

    @property
    def is_additive(self) -> bool:
        """Group values add up to the total (so a waterfall is valid)."""
        return self in (Metric.REVENUE, Metric.PROFIT, Metric.ORDERS)

    @property
    def is_percentage(self) -> bool:
        """Changes are reported in percentage points, not % change."""
        return self is Metric.MARGIN


METRIC_LABELS = {
    Metric.REVENUE: "Revenue",
    Metric.PROFIT: "Profit",
    Metric.ORDERS: "Orders",
    Metric.AOV: "Average Order Value",
    Metric.MARGIN: "Profit Margin",
}

# Source column for the summable metrics.
VALUE_COLUMNS = {Metric.REVENUE: "sales", Metric.PROFIT: "profit"}


# ------------------------------------------------------------------
# Safe arithmetic
# ------------------------------------------------------------------

def safe_divide(numerator: float, denominator: float) -> float:
    """numerator / denominator, or NaN when the denominator is 0 or missing."""
    if denominator is None or numerator is None:
        return math.nan
    if pd.isna(denominator) or pd.isna(numerator) or denominator == 0:
        return math.nan
    return float(numerator) / float(denominator)


def safe_divide_array(numerator, denominator) -> np.ndarray:
    """Element-wise safe division; NaN where the denominator is 0 or missing."""
    num = np.asarray(numerator, dtype=float)
    den = np.asarray(denominator, dtype=float)
    out = np.full(np.broadcast(num, den).shape, np.nan)
    ok = (den != 0) & ~np.isnan(den) & ~np.isnan(num)
    np.divide(num, den, out=out, where=ok)
    return out


def margin_of(profit: float, revenue: float) -> float:
    """Profit / revenue as a fraction. NaN when revenue is zero or negative."""
    if pd.isna(revenue) or revenue <= 0:
        return math.nan
    return float(profit) / float(revenue)


def pct_change(previous: float, current: float) -> float:
    """Relative change. NaN when the baseline is zero, negative or missing."""
    if pd.isna(previous) or pd.isna(current) or previous <= 0:
        return math.nan
    return (float(current) - float(previous)) / float(previous)


def pct_change_note(previous: float) -> str | None:
    """Why a percentage change is unavailable, or None if it is available."""
    if pd.isna(previous):
        return "n/a: no comparison value"
    if previous == 0:
        return "n/a: comparison value is zero"
    if previous < 0:
        return "n/a: comparison value is negative"
    return None


# ------------------------------------------------------------------
# KPIs
# ------------------------------------------------------------------

@dataclass(frozen=True)
class KPIs:
    revenue: float
    profit: float
    orders: int          # distinct transactions (composite key)
    order_rows: int      # line items

    @property
    def aov(self) -> float:
        """Average order value: revenue per distinct order."""
        return safe_divide(self.revenue, self.orders)

    @property
    def margin(self) -> float:
        """Revenue-weighted profit margin (total profit / total revenue)."""
        return margin_of(self.profit, self.revenue)

    @property
    def is_empty(self) -> bool:
        return self.order_rows == 0

    def value(self, metric: Metric) -> float:
        return {
            Metric.REVENUE: self.revenue,
            Metric.PROFIT: self.profit,
            Metric.ORDERS: float(self.orders),
            Metric.AOV: self.aov,
            Metric.MARGIN: self.margin,
        }[Metric(metric)]


def compute_kpis(df: pd.DataFrame) -> KPIs:
    if df.empty:
        return KPIs(revenue=0.0, profit=0.0, orders=0, order_rows=0)
    return KPIs(
        revenue=float(df["sales"].sum()),
        profit=float(df["profit"].sum()),
        orders=count_orders(df),
        order_rows=len(df),
    )


# ------------------------------------------------------------------
# Changes
# ------------------------------------------------------------------

@dataclass(frozen=True)
class MetricChange:
    metric: Metric
    previous: float
    current: float

    @property
    def absolute_change(self) -> float:
        if pd.isna(self.previous) or pd.isna(self.current):
            return math.nan
        return float(self.current) - float(self.previous)

    @property
    def pct_change(self) -> float:
        """Relative change; always NaN for margin (use pp_change)."""
        if self.metric.is_percentage:
            return math.nan
        return pct_change(self.previous, self.current)

    @property
    def pp_change(self) -> float:
        """Percentage-point change; only defined for margin."""
        if not self.metric.is_percentage:
            return math.nan
        return self.absolute_change * 100

    @property
    def unavailable_note(self) -> str | None:
        """Why the headline change cannot be shown, if it cannot."""
        if self.metric.is_percentage:
            if pd.isna(self.previous) or pd.isna(self.current):
                return "n/a: margin is undefined when revenue is zero"
            return None
        return pct_change_note(self.previous)

    @property
    def direction(self) -> str:
        change = self.absolute_change
        if pd.isna(change):
            return "n/a"
        if change > 0:
            return "up"
        if change < 0:
            return "down"
        return "flat"


def compare_kpis(current: KPIs, previous: KPIs) -> dict[Metric, MetricChange]:
    return {m: MetricChange(m, previous.value(m), current.value(m)) for m in Metric}


def period_frames(df: pd.DataFrame, comparison: PeriodComparison) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(current rows, comparison rows) for a PeriodComparison."""
    if df.empty:
        return df, df
    current = df[comparison.current.mask(df["order_date"])]
    previous = df[comparison.comparison.mask(df["order_date"])]
    return current, previous


# ------------------------------------------------------------------
# Trends
# ------------------------------------------------------------------

def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly revenue, profit, distinct orders, AOV and margin.

    Months without orders inside the data range are kept with zero
    revenue and an undefined (NaN) margin and AOV, so gaps stay visible.
    An order belongs to exactly one month because its key includes the
    order date, so monthly order counts add up to the period total.
    """
    columns = ["month", "revenue", "profit", "orders", "aov", "margin"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    month = df["order_date"].dt.to_period("M").dt.to_timestamp()
    grouped = df.assign(month=month).groupby("month").agg(
        revenue=("sales", "sum"),
        profit=("profit", "sum"),
        orders=(config.ORDER_KEY_COLUMN, "nunique"),
    )
    full_range = pd.date_range(grouped.index.min(), grouped.index.max(), freq="MS")
    grouped = grouped.reindex(full_range, fill_value=0)
    grouped.index.name = "month"
    grouped["aov"] = safe_divide_array(grouped["revenue"], grouped["orders"])
    revenue = grouped["revenue"].to_numpy(dtype=float)
    grouped["margin"] = np.where(revenue > 0, safe_divide_array(grouped["profit"], revenue), np.nan)
    return grouped.reset_index()[columns]
