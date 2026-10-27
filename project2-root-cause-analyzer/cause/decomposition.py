"""Revenue = Orders × Average Order Value, split into two effects.

Midpoint (two-factor Shapley) decomposition:

    volume effect = (N1 - N0) × (A0 + A1) / 2
    AOV effect    = (A1 - A0) × (N0 + N1) / 2

Because R = N × A in both periods, volume + AOV = R1 - R0 exactly, with
no interaction term left over, and swapping the order of the factors
gives the same answer.

When a period has no orders its AOV is undefined. The other period's AOV
is used in its place, so the whole change is attributed to volume (no
orders became some orders, or the reverse).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cause import config
from cause.contribution import _with_dims, dimension_label, resolve_dimensions
from cause.metrics import compute_kpis, safe_divide, safe_divide_array


@dataclass(frozen=True)
class RevenueDecomposition:
    revenue_previous: float
    revenue_current: float
    orders_previous: float
    orders_current: float

    @property
    def aov_previous(self) -> float:
        return safe_divide(self.revenue_previous, self.orders_previous)

    @property
    def aov_current(self) -> float:
        return safe_divide(self.revenue_current, self.orders_current)

    @property
    def revenue_change(self) -> float:
        return self.revenue_current - self.revenue_previous

    @property
    def orders_change(self) -> float:
        return self.orders_current - self.orders_previous

    @property
    def aov_change(self) -> float:
        """NaN when either period has no orders."""
        return self.aov_current - self.aov_previous

    def _filled_aov(self) -> tuple[float, float]:
        a0, a1 = self.aov_previous, self.aov_current
        if math.isnan(a0) and math.isnan(a1):
            return 0.0, 0.0
        if math.isnan(a0):
            return a1, a1
        if math.isnan(a1):
            return a0, a0
        return a0, a1

    @property
    def volume_effect(self) -> float:
        a0, a1 = self._filled_aov()
        return self.orders_change * (a0 + a1) / 2

    @property
    def aov_effect(self) -> float:
        a0, a1 = self._filled_aov()
        return (a1 - a0) * (self.orders_previous + self.orders_current) / 2

    @property
    def residual(self) -> float:
        """volume + AOV - revenue change. Should be ~0."""
        return self.volume_effect + self.aov_effect - self.revenue_change

    @property
    def dominant_driver(self) -> str | None:
        """'volume', 'aov', or None when there is no change."""
        v, a = abs(self.volume_effect), abs(self.aov_effect)
        if v == 0 and a == 0:
            return None
        return "volume" if v >= a else "aov"

    @property
    def notes(self) -> list[str]:
        notes = []
        if self.orders_previous == 0 and self.orders_current == 0:
            notes.append("Neither period has orders.")
        elif self.orders_previous == 0:
            notes.append(
                "The comparison period has no orders, so its average order value is "
                "undefined; the full change is shown as a volume effect."
            )
        elif self.orders_current == 0:
            notes.append(
                "The current period has no orders, so its average order value is "
                "undefined; the full change is shown as a volume effect."
            )
        return notes


def decompose_revenue(current: pd.DataFrame, previous: pd.DataFrame) -> RevenueDecomposition:
    """Decompose the total revenue change using distinct (composite-key) orders."""
    cur, prev = compute_kpis(current), compute_kpis(previous)
    return RevenueDecomposition(
        revenue_previous=prev.revenue,
        revenue_current=cur.revenue,
        orders_previous=float(prev.orders),
        orders_current=float(cur.orders),
    )


def decompose_revenue_by(
    current: pd.DataFrame, previous: pd.DataFrame, dimension: str
) -> pd.DataFrame:
    """Volume / AOV split within each group of one dimension.

    Orders per group are distinct orders containing that group, and AOV is
    the group's revenue per such order. Each row reconciles to its own
    revenue change, and revenue changes add up to the total, but the
    group volume and AOV effects do not add up to the overall volume and
    AOV effects: orders overlap across groups and the overall AOV also
    reflects the mix of groups.
    """
    (dim,) = resolve_dimensions([dimension])
    key = config.ORDER_KEY_COLUMN

    def sums(df):
        if df.empty:
            return pd.DataFrame(columns=["revenue", "orders"])
        df = _with_dims(df, [dim])
        return df.groupby(dim).agg(revenue=("sales", "sum"), orders=(key, "nunique"))

    prev, cur = sums(previous), sums(current)
    table = prev.join(cur, how="outer", lsuffix="_previous", rsuffix="_current")
    table = table.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    table.index.name = dim

    r0, r1 = table["revenue_previous"].to_numpy(float), table["revenue_current"].to_numpy(float)
    n0, n1 = table["orders_previous"].to_numpy(float), table["orders_current"].to_numpy(float)
    a0, a1 = safe_divide_array(r0, n0), safe_divide_array(r1, n1)
    a0f = np.where(np.isnan(a0), np.where(np.isnan(a1), 0.0, a1), a0)
    a1f = np.where(np.isnan(a1), a0f, a1)

    table["aov_previous"] = a0
    table["aov_current"] = a1
    table["revenue_change"] = r1 - r0
    table["volume_effect"] = (n1 - n0) * (a0f + a1f) / 2
    table["aov_effect"] = (a1f - a0f) * (n0 + n1) / 2
    table = table.reset_index()
    table.attrs["dimension_label"] = dimension_label(dim)
    order = table["revenue_change"].abs().sort_values(ascending=False, kind="stable").index
    return table.loc[order].reset_index(drop=True)
