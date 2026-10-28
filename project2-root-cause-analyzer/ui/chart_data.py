"""Data preparation for KPI cards, tables and charts (pure pandas, no Streamlit).

Everything here reshapes results from cause/ for display. It performs no
new analytics, so the numbers shown are exactly the engine's numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cause.contribution import ContributionResult, MarginDecomposition
from cause.decomposition import RevenueDecomposition
from cause.insights import format_change, format_pct, format_pp, format_value, is_significant
from cause.metrics import Metric, MetricChange, margin_of, safe_divide_array

OTHER_PREFIX = "Other"


# ------------------------------------------------------------------
# KPI cards
# ------------------------------------------------------------------

@dataclass(frozen=True)
class KpiDisplay:
    label: str
    value: str
    delta: str | None
    tone: str
    footnote: str
    flagged: bool


def kpi_display(change: MetricChange, comparison_label: str, label: str | None = None) -> KpiDisplay:
    """Card text for one metric: current value, change, and comparison value."""
    m = change.metric
    value = format_value(m, change.current)
    previous = format_value(m, change.previous)
    if pd.isna(change.current):
        return KpiDisplay(label or m.label, value, "No value: revenue is zero", "caution",
                          f"{previous} in {comparison_label}", False)
    if m.is_percentage:
        delta = None if pd.isna(change.pp_change) else format_pp(change.pp_change)
    elif pd.isna(change.previous):
        delta = None
    else:
        pct = change.pct_change
        delta = format_change(m, change.absolute_change) + (
            f" ({format_pct(pct)})" if not pd.isna(pct) else " (% change n/a)"
        )
    tone = {"up": "positive", "down": "negative"}.get(change.direction, "neutral")
    if delta is None:
        delta, tone = (change.unavailable_note or "No comparison"), "caution"
    return KpiDisplay(
        label=label or m.label,
        value=value,
        delta=delta,
        tone=tone,
        footnote=f"{previous} in {comparison_label}",
        flagged=is_significant(change) and not pd.isna(change.absolute_change),
    )


# ------------------------------------------------------------------
# Group performance (overview)
# ------------------------------------------------------------------

def group_performance(current: pd.DataFrame, previous: pd.DataFrame, column: str) -> pd.DataFrame:
    """Revenue, profit and weighted margin per group, current and previous.

    Sorted by current revenue (largest first). Margin is each group's own
    profit / revenue, NaN when its revenue is zero.
    """
    cols = [column, "revenue_current", "profit_current", "revenue_previous", "profit_previous",
            "margin_current", "margin_previous", "margin_change_pp", "revenue_pct_change"]

    def sums(df):
        if df.empty:
            return pd.DataFrame(columns=["revenue", "profit"])
        return df.groupby(column).agg(revenue=("sales", "sum"), profit=("profit", "sum"))

    cur, prev = sums(current), sums(previous)
    if cur.empty and prev.empty:
        return pd.DataFrame(columns=cols)
    t = cur.join(prev, how="outer", lsuffix="_current", rsuffix="_previous")
    t = t.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    t.index.name = column
    t["margin_current"] = [margin_of(p, r) for p, r in zip(t["profit_current"], t["revenue_current"])]
    t["margin_previous"] = [margin_of(p, r) for p, r in zip(t["profit_previous"], t["revenue_previous"])]
    t["margin_change_pp"] = (t["margin_current"] - t["margin_previous"]) * 100
    prev_rev = t["revenue_previous"].to_numpy(float)
    t["revenue_pct_change"] = np.where(
        prev_rev > 0, safe_divide_array(t["revenue_current"] - prev_rev, prev_rev), np.nan
    )
    return t.reset_index().sort_values("revenue_current", ascending=False, kind="stable")[cols].reset_index(drop=True)


def loss_making(current: pd.DataFrame, column: str) -> pd.DataFrame:
    """Groups with negative total profit in the period, worst first."""
    if current.empty:
        return pd.DataFrame(columns=[column, "revenue", "profit"])
    g = current.groupby(column).agg(revenue=("sales", "sum"), profit=("profit", "sum")).reset_index()
    return g[g["profit"] < 0].sort_values("profit", kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------
# Contribution tables and waterfalls
# ------------------------------------------------------------------

def group_labels(analysis: ContributionResult | MarginDecomposition) -> list[str]:
    t = analysis.table
    return [" / ".join(str(row[d]) for d in analysis.dimensions) for _, row in t.iterrows()]


def contribution_display(result: ContributionResult) -> pd.DataFrame:
    """Numeric display table for an additive contribution (percent units)."""
    t = result.table
    out = pd.DataFrame({
        "Group": group_labels(result),
        "Previous": t["previous"].to_numpy(),
        "Current": t["current"].to_numpy(),
        "Change": t["change"].to_numpy(),
        "% change": (t["pct_change"] * 100).to_numpy(),
        "% of net change": (t["share_of_net"] * 100).to_numpy(),
        "% of total movement": (t["share_of_gross"] * 100).to_numpy(),
    })
    if result.metric is Metric.ORDERS:
        out["Actual orders (previous)"] = t["distinct_orders_previous"].to_numpy()
        out["Actual orders (current)"] = t["distinct_orders_current"].to_numpy()
    return out


def margin_display(result: MarginDecomposition) -> pd.DataFrame:
    t = result.table
    return pd.DataFrame({
        "Group": group_labels(result),
        "Contribution (pp)": t["contribution_pp"].to_numpy(),
        "Rate effect (pp)": t["rate_effect_pp"].to_numpy(),
        "Mix effect (pp)": t["mix_effect_pp"].to_numpy(),
        "Margin (previous) %": (t["margin_previous"] * 100).to_numpy(),
        "Margin (current) %": (t["margin_current"] * 100).to_numpy(),
        "Revenue share (previous) %": (t["revenue_share_previous"] * 100).to_numpy(),
        "Revenue share (current) %": (t["revenue_share_current"] * 100).to_numpy(),
    })


def waterfall_steps(result: ContributionResult, max_groups: int = 10) -> pd.DataFrame:
    """Previous total -> group changes -> current total.

    Groups beyond `max_groups` (by size of change) are folded into one
    "Other" step, so the steps always add up to the current total.
    """
    t = result.table
    labels = group_labels(result)
    changes = t["change"].to_numpy(float) if not t.empty else np.array([])
    keep = min(len(changes), max_groups if len(changes) > max_groups + 1 else len(changes))
    rows = [{"label": "Previous total", "measure": "absolute", "value": result.total_previous, "kind": "total"}]
    for label, change in zip(labels[:keep], changes[:keep]):
        rows.append({"label": label, "measure": "relative", "value": float(change),
                     "kind": "increase" if change >= 0 else "decrease"})
    if keep < len(changes):
        rest = float(changes[keep:].sum())
        rows.append({"label": f"{OTHER_PREFIX} ({len(changes) - keep} groups)", "measure": "relative",
                     "value": rest, "kind": "increase" if rest >= 0 else "decrease"})
    rows.append({"label": "Current total", "measure": "total", "value": result.total_current, "kind": "total"})
    return pd.DataFrame(rows)


def waterfall_gap(steps: pd.DataFrame) -> float:
    """Start + changes - end. ~0 when the waterfall reconciles."""
    start = steps.loc[steps["measure"] == "absolute", "value"].sum()
    rel = steps.loc[steps["measure"] == "relative", "value"].sum()
    end = steps.loc[steps["measure"] == "total", "value"].sum()
    return float(start + rel - end)


def margin_effects_long(result: MarginDecomposition, max_groups: int = 12) -> pd.DataFrame:
    """Rate and mix effect per group (pp) in long form for a stacked bar."""
    t = result.table.head(max_groups)
    labels = group_labels(result)[: len(t)]
    rows = []
    for label, (_, row) in zip(labels, t.iterrows()):
        rows.append({"group": label, "effect": "Rate effect", "value": row["rate_effect_pp"],
                     "contribution": row["contribution_pp"]})
        rows.append({"group": label, "effect": "Mix effect", "value": row["mix_effect_pp"],
                     "contribution": row["contribution_pp"]})
    return pd.DataFrame(rows, columns=["group", "effect", "value", "contribution"])


# ------------------------------------------------------------------
# Revenue drivers
# ------------------------------------------------------------------

def driver_waterfall_steps(d: RevenueDecomposition) -> pd.DataFrame:
    return pd.DataFrame([
        {"label": "Previous revenue", "measure": "absolute", "value": d.revenue_previous, "kind": "total"},
        {"label": "Order volume effect", "measure": "relative", "value": d.volume_effect,
         "kind": "increase" if d.volume_effect >= 0 else "decrease"},
        {"label": "Order value effect", "measure": "relative", "value": d.aov_effect,
         "kind": "increase" if d.aov_effect >= 0 else "decrease"},
        {"label": "Current revenue", "measure": "total", "value": d.revenue_current, "kind": "total"},
    ])


def driver_display(table: pd.DataFrame, column: str) -> pd.DataFrame:
    """Display table for decompose_revenue_by output."""
    return pd.DataFrame({
        "Group": table[column].astype(str).to_numpy(),
        "Revenue change": table["revenue_change"].to_numpy(),
        "Volume effect": table["volume_effect"].to_numpy(),
        "AOV effect": table["aov_effect"].to_numpy(),
        "Revenue (previous)": table["revenue_previous"].to_numpy(),
        "Revenue (current)": table["revenue_current"].to_numpy(),
        "Orders (previous)": table["orders_previous"].to_numpy(),
        "Orders (current)": table["orders_current"].to_numpy(),
        "AOV (previous)": table["aov_previous"].to_numpy(),
        "AOV (current)": table["aov_current"].to_numpy(),
    })


def driver_effects_long(table: pd.DataFrame, column: str, max_groups: int = 12) -> pd.DataFrame:
    t = table.head(max_groups)
    rows = []
    for _, row in t.iterrows():
        rows.append({"group": str(row[column]), "effect": "Volume effect", "value": row["volume_effect"]})
        rows.append({"group": str(row[column]), "effect": "AOV effect", "value": row["aov_effect"]})
    return pd.DataFrame(rows, columns=["group", "effect", "value"])


def is_finite(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))
