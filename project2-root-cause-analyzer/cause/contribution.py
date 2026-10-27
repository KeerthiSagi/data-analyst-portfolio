"""Contribution analysis: which groups account for a change between periods.

Contribution is descriptive. It shows where a change is concentrated,
not why it happened.

Additive metrics (revenue, profit)
    change_g = value_g(current) - value_g(previous); the sum over groups
    equals the total change exactly.

Orders (allocated)
    Distinct order counts overlap across groups (an order with furniture
    and technology lines counts in both categories), so they cannot be
    added up. For contribution, each order is split equally across the
    groups it touches, so each order adds exactly 1 across all groups and
    group values sum to the true distinct order count. With two
    dimensions, the split is hierarchical: first across the first
    dimension's groups, then within each of those across the second
    dimension's groups. This makes drill-down rows add up to their parent
    row. Actual distinct counts per group are reported alongside, labelled
    as overlapping.

Profit margin (rate / mix)
    Margin = total profit / total revenue (never a sum or average of
    group margins). Each group's contribution in percentage points is
        c_g = 100 * (P_g1 / R_1 - P_g0 / R_0)
    which sums exactly to the overall pp change. It is split into
        mix  = 100 * (w_g1 - w_g0) * (m_g0 + m_g1) / 2
        rate = c_g - mix
    where w is the group's revenue share and m its own margin. When the
    group has revenue in both periods, rate equals
    100 * (m_g1 - m_g0) * (w_g0 + w_g1) / 2 exactly (the standard
    midpoint split). When a group has no revenue in one period its margin
    is undefined there; the other period's margin is used, so entering or
    leaving the mix shows up as a mix effect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd

from cause import config
from cause.data import count_orders
from cause.metrics import Metric, VALUE_COLUMNS, margin_of, safe_divide_array

# A net change smaller than this share of the gross movement (sum of
# absolute group changes) makes "% of net change" misleading: a group can
# show +900% simply because others offset it. Shares of net change are
# suppressed below this level and shares of gross movement are used.
SMALL_NET_THRESHOLD = 0.20

ALLOCATED_BASIS = (
    "Allocated orders: each order is split equally across the groups it "
    "touches, so groups add up to the distinct order total."
)
DISTINCT_BASIS = (
    "Distinct orders per group overlap (one order can appear in several "
    "groups) and do not add up to the total."
)


# ------------------------------------------------------------------
# Dimensions
# ------------------------------------------------------------------

def resolve_dimensions(dimensions: str | Sequence[str]) -> list[str]:
    """Accept dimension labels ("Region") or columns ("market_region")."""
    if isinstance(dimensions, str):
        dimensions = [dimensions]
    columns = []
    valid_columns = set(config.DIMENSIONS.values())
    for dim in dimensions:
        column = config.DIMENSIONS.get(dim, dim)
        if column not in valid_columns:
            allowed = ", ".join(config.DIMENSIONS)
            raise ValueError(f"Unknown dimension '{dim}'. Choose from: {allowed}.")
        if column in columns:
            raise ValueError(f"Dimension '{dim}' is listed twice.")
        columns.append(column)
    if not columns:
        raise ValueError("Choose at least one dimension.")
    return columns


def dimension_label(column: str) -> str:
    for label, col in config.DIMENSIONS.items():
        if col == column:
            return label
    return column


def _with_dims(df: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    """Ensure no missing dimension values (groupby would silently drop them)."""
    missing = [d for d in dims if d not in df.columns]
    if missing:
        raise ValueError(f"Data is missing dimension column(s): {', '.join(missing)}.")
    if any(df[d].isna().any() for d in dims):
        df = df.copy()
        for d in dims:
            df[d] = df[d].fillna(config.MISSING_LABEL)
    return df


# ------------------------------------------------------------------
# Order allocation
# ------------------------------------------------------------------

def allocate_orders(df: pd.DataFrame, dimensions: str | Sequence[str]) -> pd.DataFrame:
    """Allocated and distinct order counts per group.

    Returns columns: *dims, allocated_orders, distinct_orders.
    sum(allocated_orders) == number of distinct orders in df.
    """
    dims = resolve_dimensions(dimensions)
    key = config.ORDER_KEY_COLUMN
    if df.empty:
        return pd.DataFrame(columns=[*dims, "allocated_orders", "distinct_orders"])
    df = _with_dims(df, dims)
    combos = df[[key, *dims]].drop_duplicates()
    weight = pd.Series(1.0, index=combos.index)
    for level, dim in enumerate(dims):
        groups_at_level = combos.groupby([key, *dims[:level]])[dim].transform("nunique")
        weight = weight / groups_at_level
    combos = combos.assign(weight=weight)
    return (
        combos.groupby(dims)
        .agg(allocated_orders=("weight", "sum"), distinct_orders=(key, "nunique"))
        .reset_index()
    )


# ------------------------------------------------------------------
# Additive contribution (revenue, profit, allocated orders)
# ------------------------------------------------------------------

@dataclass
class ContributionResult:
    metric: Metric
    dimensions: list[str]
    table: pd.DataFrame
    total_previous: float
    total_current: float
    gross_movement: float
    shares_reliable: bool
    basis: str
    notes: list[str] = field(default_factory=list)

    @property
    def total_change(self) -> float:
        return self.total_current - self.total_previous

    @property
    def reconciliation_error(self) -> float:
        """sum(group changes) - total change. Should be ~0."""
        if self.table.empty:
            return 0.0 - self.total_change
        return float(self.table["change"].sum()) - self.total_change

    @property
    def dimension_labels(self) -> list[str]:
        return [dimension_label(d) for d in self.dimensions]


def _group_values(df: pd.DataFrame, dims: list[str], metric: Metric) -> pd.DataFrame:
    if metric is Metric.ORDERS:
        alloc = allocate_orders(df, dims)
        return alloc.set_index(dims)[["allocated_orders", "distinct_orders"]].rename(
            columns={"allocated_orders": "value"}
        )
    if df.empty:
        return pd.DataFrame(columns=["value"])
    df = _with_dims(df, dims)
    return df.groupby(dims)[VALUE_COLUMNS[metric]].sum().to_frame("value")


def _combine_periods(prev: pd.DataFrame, cur: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    """Outer-join two per-group frames; groups missing in a period get 0."""
    prev = prev.reset_index() if not prev.empty else pd.DataFrame(columns=[*dims, *prev.columns])
    cur = cur.reset_index() if not cur.empty else pd.DataFrame(columns=[*dims, *cur.columns])
    merged = prev.merge(cur, on=dims, how="outer", suffixes=("_previous", "_current"))
    value_cols = [c for c in merged.columns if c not in dims]
    merged[value_cols] = merged[value_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return merged


def _add_shares(table: pd.DataFrame, total_change: float, change_col: str = "change"):
    """Add share_of_net / share_of_gross; return (table, gross, reliable, notes)."""
    changes = table[change_col].to_numpy(dtype=float)
    gross = float(np.abs(changes).sum())
    notes: list[str] = []
    reliable = gross > 0 and total_change != 0 and abs(total_change) >= SMALL_NET_THRESHOLD * gross
    if gross == 0:
        notes.append("No group changed between the two periods.")
    elif not reliable:
        notes.append(
            "The net change is small compared with the movements of individual groups, "
            "which largely offset each other. Shares of the net change would be misleading, "
            "so absolute contributions and shares of gross movement are shown instead."
        )
    table["share_of_net"] = changes / total_change if reliable else np.nan
    table["share_of_gross"] = safe_divide_array(changes, gross) if gross > 0 else np.nan
    return table, gross, reliable, notes


def additive_contribution(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    dimensions: str | Sequence[str],
    metric: Metric | str,
) -> ContributionResult:
    """Contribution of each group to the change in revenue, profit or orders."""
    metric = Metric(metric)
    if not metric.is_additive:
        raise ValueError(f"{metric.label} is not additive; use margin_decomposition().")
    dims = resolve_dimensions(dimensions)

    table = _combine_periods(
        _group_values(previous, dims, metric), _group_values(current, dims, metric), dims
    )
    table = table.rename(columns={"value_previous": "previous", "value_current": "current"})
    if metric is Metric.ORDERS:
        total_previous, total_current = float(count_orders(previous)), float(count_orders(current))
        basis = ALLOCATED_BASIS
    else:
        col = VALUE_COLUMNS[metric]
        total_previous = float(previous[col].sum()) if not previous.empty else 0.0
        total_current = float(current[col].sum()) if not current.empty else 0.0
        basis = f"{metric.label} summed by group; groups add up to the total."

    table["change"] = table["current"] - table["previous"]
    prev_vals = table["previous"].to_numpy(dtype=float)
    table["pct_change"] = np.where(
        prev_vals > 0, safe_divide_array(table["change"], prev_vals), np.nan
    )
    total_change = total_current - total_previous
    table, gross, reliable, notes = _add_shares(table, total_change)
    if metric is Metric.ORDERS:
        notes.append(DISTINCT_BASIS)
    if previous.empty:
        notes.append("The comparison period has no data; every group is counted as new.")
    if current.empty:
        notes.append("The current period has no data.")

    table = _order_columns(table, dims, metric)
    return ContributionResult(
        metric=metric,
        dimensions=dims,
        table=table,
        total_previous=total_previous,
        total_current=total_current,
        gross_movement=gross,
        shares_reliable=reliable,
        basis=basis,
        notes=notes,
    )


def _order_columns(table: pd.DataFrame, dims: list[str], metric: Metric) -> pd.DataFrame:
    cols = [*dims, "previous", "current", "change", "pct_change", "share_of_net", "share_of_gross"]
    if metric is Metric.ORDERS:
        cols += ["distinct_orders_previous", "distinct_orders_current"]
    table = table[cols]
    order = table["change"].abs().sort_values(ascending=False, kind="stable").index
    return table.loc[order].reset_index(drop=True)


# ------------------------------------------------------------------
# Profit margin: rate / mix
# ------------------------------------------------------------------

@dataclass
class MarginDecomposition:
    dimensions: list[str]
    table: pd.DataFrame
    revenue_previous: float
    revenue_current: float
    profit_previous: float
    profit_current: float
    shares_reliable: bool
    notes: list[str] = field(default_factory=list)

    metric: Metric = Metric.MARGIN

    @property
    def margin_previous(self) -> float:
        return margin_of(self.profit_previous, self.revenue_previous)

    @property
    def margin_current(self) -> float:
        return margin_of(self.profit_current, self.revenue_current)

    @property
    def comparable(self) -> bool:
        return not (math.isnan(self.margin_previous) or math.isnan(self.margin_current))

    @property
    def change_pp(self) -> float:
        if not self.comparable:
            return math.nan
        return (self.margin_current - self.margin_previous) * 100

    @property
    def rate_effect_pp(self) -> float:
        return float(self.table["rate_effect_pp"].sum()) if self.comparable else math.nan

    @property
    def mix_effect_pp(self) -> float:
        return float(self.table["mix_effect_pp"].sum()) if self.comparable else math.nan

    @property
    def reconciliation_error(self) -> float:
        """sum(group contributions) - overall pp change. Should be ~0."""
        if not self.comparable:
            return 0.0
        return float(self.table["contribution_pp"].sum()) - self.change_pp

    @property
    def split_error(self) -> float:
        """(rate + mix) - contribution, summed. Should be ~0."""
        if not self.comparable:
            return 0.0
        return self.rate_effect_pp + self.mix_effect_pp - float(self.table["contribution_pp"].sum())

    @property
    def dimension_labels(self) -> list[str]:
        return [dimension_label(d) for d in self.dimensions]


MARGIN_COLUMNS = [
    "revenue_previous", "revenue_current", "profit_previous", "profit_current",
    "revenue_share_previous", "revenue_share_current",
    "margin_previous", "margin_current", "margin_change_pp",
    "rate_effect_pp", "mix_effect_pp", "contribution_pp",
    "share_of_net", "share_of_gross",
]


def margin_decomposition(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    dimensions: str | Sequence[str],
) -> MarginDecomposition:
    """Split the change in overall profit margin into group rate and mix effects."""
    dims = resolve_dimensions(dimensions)

    def sums(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["revenue", "profit"])
        df = _with_dims(df, dims)
        return df.groupby(dims).agg(revenue=("sales", "sum"), profit=("profit", "sum"))

    table = _combine_periods(sums(previous), sums(current), dims)
    r0 = table["revenue_previous"].to_numpy(dtype=float)
    r1 = table["revenue_current"].to_numpy(dtype=float)
    p0 = table["profit_previous"].to_numpy(dtype=float)
    p1 = table["profit_current"].to_numpy(dtype=float)
    R0 = float(previous["sales"].sum()) if not previous.empty else 0.0
    R1 = float(current["sales"].sum()) if not current.empty else 0.0
    P0 = float(previous["profit"].sum()) if not previous.empty else 0.0
    P1 = float(current["profit"].sum()) if not current.empty else 0.0

    result = MarginDecomposition(
        dimensions=dims, table=table, revenue_previous=R0, revenue_current=R1,
        profit_previous=P0, profit_current=P1, shares_reliable=False,
    )
    if not result.comparable:
        which = [name for name, r in (("comparison", R0), ("current", R1)) if r <= 0]
        result.notes.append(
            f"Profit margin is undefined because the {' and '.join(which)} period "
            "has no positive revenue, so it cannot be decomposed."
        )
        for col in MARGIN_COLUMNS:
            if col not in table.columns:
                table[col] = np.nan
        result.table = table[[*dims, *MARGIN_COLUMNS]]
        return result

    w0, w1 = r0 / R0, r1 / R1
    m0 = np.where(r0 > 0, safe_divide_array(p0, r0), np.nan)
    m1 = np.where(r1 > 0, safe_divide_array(p1, r1), np.nan)
    # Fill an undefined margin with the other period's so entering or
    # leaving the mix is treated as a mix effect.
    m0_filled = np.where(np.isnan(m0), np.where(np.isnan(m1), 0.0, m1), m0)
    m1_filled = np.where(np.isnan(m1), m0_filled, m1)

    contribution = (p1 / R1 - p0 / R0) * 100
    mix = (w1 - w0) * (m0_filled + m1_filled) / 2 * 100
    rate = contribution - mix

    table["revenue_share_previous"] = w0
    table["revenue_share_current"] = w1
    table["margin_previous"] = m0
    table["margin_current"] = m1
    table["margin_change_pp"] = (m1 - m0) * 100   # NaN when either side undefined
    table["rate_effect_pp"] = rate
    table["mix_effect_pp"] = mix
    table["contribution_pp"] = contribution

    table, _, reliable, notes = _add_shares(table, result.change_pp, "contribution_pp")
    zero_rev = int(((r0 <= 0) | (r1 <= 0)).sum())
    if zero_rev:
        notes.append(
            f"{zero_rev} group(s) had no revenue in one period; their own margin is "
            "undefined there, so their effect is counted as mix."
        )
    order = table["contribution_pp"].abs().sort_values(ascending=False, kind="stable").index
    result.table = table.loc[order, [*dims, *MARGIN_COLUMNS]].reset_index(drop=True)
    result.shares_reliable = reliable
    result.notes.extend(notes)
    return result


# ------------------------------------------------------------------
# Dispatch and drill-down
# ------------------------------------------------------------------

def contribution_analysis(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    dimensions: str | Sequence[str],
    metric: Metric | str,
) -> ContributionResult | MarginDecomposition:
    metric = Metric(metric)
    if metric is Metric.MARGIN:
        return margin_decomposition(current, previous, dimensions)
    if metric is Metric.AOV:
        raise ValueError(
            "Average order value is a ratio; use decomposition.decompose_revenue() "
            "for volume and order-value effects."
        )
    return additive_contribution(current, previous, dimensions, metric)


def drill_down(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    parent_dimension: str,
    parent_value: str,
    child_dimension: str,
    metric: Metric | str,
) -> ContributionResult | MarginDecomposition:
    """Break one parent group down by a second dimension.

    * Revenue / profit / orders: the rows are the parent's slice of the
      two-dimension table, so child changes add up to the parent's change
      (orders use the hierarchical allocation for this).
    * Margin: decomposes the parent group's own margin (profit / revenue
      within the parent), so child contributions add up to the parent's
      margin change in pp.
    """
    metric = Metric(metric)
    parent_col, child_col = resolve_dimensions([parent_dimension, child_dimension])

    if metric is Metric.MARGIN:
        def in_parent(df):
            return df if df.empty else df[_with_dims(df, [parent_col])[parent_col] == parent_value]
        result = margin_decomposition(in_parent(current), in_parent(previous), [child_col])
        result.notes.append(
            f"Margin within {dimension_label(parent_col)} = {parent_value} only."
        )
        return result

    pair = contribution_analysis(current, previous, [parent_col, child_col], metric)
    parent = contribution_analysis(current, previous, [parent_col], metric)
    parent_row = parent.table[parent.table[parent_col] == parent_value]
    if parent_row.empty:
        raise ValueError(
            f"'{parent_value}' has no data for {dimension_label(parent_col)} in either period."
        )
    rows = pair.table[pair.table[parent_col] == parent_value].drop(columns=[parent_col])
    total_previous = float(parent_row["previous"].iloc[0])
    total_current = float(parent_row["current"].iloc[0])
    rows = rows.reset_index(drop=True)
    rows, gross, reliable, notes = _add_shares(rows, total_current - total_previous)
    notes.append(f"Within {dimension_label(parent_col)} = {parent_value}.")
    if metric is Metric.ORDERS:
        notes.append(
            "Allocated orders follow the drill-down order: each order is split across "
            f"{dimension_label(parent_col)} groups first, then within each across "
            f"{dimension_label(child_col)} groups."
        )
    return ContributionResult(
        metric=metric,
        dimensions=[child_col],
        table=rows,
        total_previous=total_previous,
        total_current=total_current,
        gross_movement=gross,
        shares_reliable=reliable,
        basis=pair.basis,
        notes=notes,
    )


def reconciliation_checks(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    dimension_sets: Sequence[Sequence[str]] | None = None,
) -> pd.DataFrame:
    """Run every metric over each dimension set and report reconciliation error."""
    if dimension_sets is None:
        cols = list(config.DIMENSIONS.values())
        dimension_sets = [[c] for c in cols] + [
            [a, b] for i, a in enumerate(cols) for b in cols[i + 1:]
        ]
    rows = []
    for dims in dimension_sets:
        for metric in (Metric.REVENUE, Metric.PROFIT, Metric.ORDERS, Metric.MARGIN):
            res = contribution_analysis(current, previous, dims, metric)
            total = res.change_pp if metric is Metric.MARGIN else res.total_change
            rows.append({
                "metric": metric.label,
                "dimensions": " × ".join(dimension_label(d) for d in dims),
                "groups": len(res.table),
                "total_change": total,
                "reconciliation_error": res.reconciliation_error,
                "rate_mix_error": res.split_error if metric is Metric.MARGIN else 0.0,
            })
    return pd.DataFrame(rows)
