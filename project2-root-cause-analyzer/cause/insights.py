"""Rule-based findings built only from computed results.

Every sentence is generated from numbers passed in; nothing is hardcoded.
Wording describes where a change is concentrated ("accounted for",
"contributed") and never claims a cause.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from cause.contribution import ContributionResult, MarginDecomposition
from cause.decomposition import RevenueDecomposition
from cause.metrics import Metric, MetricChange

CAUSATION_NOTE = (
    "Contribution analysis shows where a change happened, not why. These findings are "
    "associations to investigate further, not confirmed root causes."
)

# A change at or above these sizes is flagged as significant.
SIGNIFICANT_PCT_CHANGE = 0.10   # 10% for revenue, profit, orders, AOV
SIGNIFICANT_PP_CHANGE = 1.0     # 1 percentage point for margin

# A single group accounting for at least this share of gross movement is
# called out as a concentration.
CONCENTRATION_SHARE = 0.50


@dataclass(frozen=True)
class Finding:
    category: str      # headline | contributor | concentration | offset | driver | margin | data
    tone: str          # positive | negative | neutral | caution
    title: str
    detail: str


# ------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------

def format_value(metric: Metric, value: float, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    sign = "+" if signed and value > 0 else ""
    if metric is Metric.MARGIN:
        return f"{sign}{value * 100:.1f}%"
    if metric is Metric.ORDERS:
        if abs(value - round(value)) < 1e-9:
            return f"{sign}{value:,.0f}"
        return f"{sign}{value:,.1f}"
    neg = "-" if value < 0 else ""
    return f"{sign}{neg}${abs(value):,.0f}"


def format_change(metric: Metric, change: float) -> str:
    """Signed absolute change; margin changes are expressed in pp."""
    if change is None or pd.isna(change):
        return "n/a"
    if metric is Metric.MARGIN:
        return format_pp(change)
    return format_value(metric, change, signed=True)


def format_pp(pp: float) -> str:
    if pp is None or pd.isna(pp):
        return "n/a"
    return f"{'+' if pp > 0 else ''}{pp:.1f} pp"


def format_pct(fraction: float) -> str:
    if fraction is None or pd.isna(fraction):
        return "n/a"
    return f"{'+' if fraction > 0 else ''}{fraction * 100:.1f}%"


def _share(fraction: float) -> str:
    return f"{abs(fraction) * 100:.0f}%"


def _tone(value: float, positive_is_good: bool = True) -> str:
    if value is None or pd.isna(value) or value == 0:
        return "neutral"
    good = value > 0 if positive_is_good else value < 0
    return "positive" if good else "negative"


# ------------------------------------------------------------------
# Significance
# ------------------------------------------------------------------

def is_significant(change: MetricChange) -> bool:
    if change.metric.is_percentage:
        return not pd.isna(change.pp_change) and abs(change.pp_change) >= SIGNIFICANT_PP_CHANGE
    pct = change.pct_change
    if pd.isna(pct):
        # No valid baseline: any non-zero move from a zero/negative base is notable.
        return not pd.isna(change.absolute_change) and change.absolute_change != 0
    return abs(pct) >= SIGNIFICANT_PCT_CHANGE


def significant_changes(changes: dict[Metric, MetricChange]) -> list[Metric]:
    return [m for m, c in changes.items() if is_significant(c)]


# ------------------------------------------------------------------
# Contributor tables
# ------------------------------------------------------------------

def _change_column(result: ContributionResult | MarginDecomposition) -> str:
    return "contribution_pp" if isinstance(result, MarginDecomposition) else "change"


def top_contributors(
    result: ContributionResult | MarginDecomposition, n: int = 3, direction: str = "negative"
) -> pd.DataFrame:
    """Largest positive or negative contributors, biggest first."""
    if direction not in ("positive", "negative"):
        raise ValueError("direction must be 'positive' or 'negative'.")
    col = _change_column(result)
    table = result.table
    if table.empty:
        return table
    subset = table[table[col] > 0] if direction == "positive" else table[table[col] < 0]
    return subset.sort_values(col, ascending=(direction == "negative"), kind="stable").head(n)


def _group_name(row: pd.Series, dims: list[str]) -> str:
    return " / ".join(str(row[d]) for d in dims)


# ------------------------------------------------------------------
# Finding rules
# ------------------------------------------------------------------

def headline_finding(change: MetricChange, comparison_label: str) -> Finding:
    m = change.metric
    if m.is_percentage:
        size = format_pp(change.pp_change)
    else:
        pct = change.pct_change
        size = format_change(m, change.absolute_change)
        size += f" ({format_pct(pct)})" if not pd.isna(pct) else f" ({change.unavailable_note})"
    if change.unavailable_note and m.is_percentage:
        detail = f"{m.label} cannot be compared for {comparison_label}: {change.unavailable_note}."
        return Finding("headline", "caution", f"{m.label}: not comparable", detail)
    detail = (
        f"{m.label} moved from {format_value(m, change.previous)} to "
        f"{format_value(m, change.current)}, a change of {size}, for {comparison_label}."
    )
    verb = {"up": "increased", "down": "decreased", "flat": "was unchanged"}.get(change.direction, "changed")
    return Finding("headline", _tone(change.absolute_change), f"{m.label} {verb}", detail)


def contributor_findings(
    result: ContributionResult | MarginDecomposition, n: int = 3
) -> list[Finding]:
    """Largest negative and positive contributors, concentration and offsets."""
    findings: list[Finding] = []
    metric = result.metric
    col = _change_column(result)
    table = result.table
    dims = result.dimensions
    dim_label = " × ".join(result.dimension_labels)
    is_margin = isinstance(result, MarginDecomposition)
    if table.empty or (is_margin and not result.comparable):
        return findings

    net = result.change_pp if is_margin else result.total_change
    net_text = format_change(metric, net)
    unit = "orders (allocated)" if metric is Metric.ORDERS else ""

    for direction in ("negative", "positive"):
        top = top_contributors(result, n, direction)
        if top.empty:
            continue
        parts = []
        for _, row in top.iterrows():
            piece = f"{_group_name(row, dims)} {format_change(metric, row[col])}"
            share = row["share_of_net"]
            if result.shares_reliable and not pd.isna(share):
                if share >= 0:
                    piece += f" ({_share(share)} of the net change)"
                else:
                    piece += f" (moved against the net change, offsetting an amount equal to {_share(share)} of it)"
            parts.append(piece)
        label = "declines" if direction == "negative" else "gains"
        title = f"Largest {label} by {dim_label}"
        detail = (
            f"Groups that contributed most to {label} in {metric.label}"
            f"{' ' + unit if unit else ''}: " + "; ".join(parts) + f". Net change: {net_text}."
        )
        findings.append(Finding("contributor", direction, title, detail))

    leader = table.iloc[0]
    share_gross = leader["share_of_gross"]
    if not pd.isna(share_gross) and abs(share_gross) >= CONCENTRATION_SHARE and len(table) > 1:
        findings.append(Finding(
            "concentration",
            _tone(leader[col]),
            f"Change concentrated in {_group_name(leader, dims)}",
            f"{_group_name(leader, dims)} accounted for {_share(share_gross)} of the gross "
            f"movement in {metric.label} across {dim_label} "
            f"({format_change(metric, leader[col])}).",
        ))

    gains = float(table.loc[table[col] > 0, col].sum())
    losses = float(table.loc[table[col] < 0, col].sum())
    if gains > 0 and losses < 0 and not result.shares_reliable:
        findings.append(Finding(
            "offset",
            "caution",
            "Offsetting movements",
            f"Gains of {format_change(metric, gains)} and declines of "
            f"{format_change(metric, losses)} across {dim_label} largely offset each other, "
            f"leaving a net change of {net_text}. Percentages of the net change are not "
            "shown here, as they would overstate individual groups.",
        ))
    return findings


def margin_findings(result: MarginDecomposition) -> list[Finding]:
    if not result.comparable:
        return [Finding("data", "caution", "Margin not comparable", " ".join(result.notes))]
    rate, mix, total = result.rate_effect_pp, result.mix_effect_pp, result.change_pp
    dim_label = " × ".join(result.dimension_labels)
    larger = "rate" if abs(rate) >= abs(mix) else "mix"
    explanation = (
        "changes in margins within groups" if larger == "rate"
        else f"revenue shifting between {dim_label} groups with different margins"
    )
    detail = (
        f"Profit margin moved from {format_value(Metric.MARGIN, result.margin_previous)} to "
        f"{format_value(Metric.MARGIN, result.margin_current)} ({format_pp(total)}). "
        f"Rate effect (margins within each {dim_label} group): {format_pp(rate)}. "
        f"Mix effect (shift in revenue share between groups): {format_pp(mix)}. "
        f"The larger component is {explanation}."
    )
    return [Finding("margin", _tone(total), f"Margin change by {dim_label}: rate vs mix", detail)]


def driver_finding(decomp: RevenueDecomposition) -> Finding:
    vol, aov = decomp.volume_effect, decomp.aov_effect
    if decomp.dominant_driver is None:
        return Finding("driver", "neutral", "No revenue change", "Revenue did not change between the periods.")
    lead = "order volume" if decomp.dominant_driver == "volume" else "average order value"
    aov_text = (
        f"average order value went from {format_value(Metric.REVENUE, decomp.aov_previous)} to "
        f"{format_value(Metric.REVENUE, decomp.aov_current)}"
        if not pd.isna(decomp.aov_change) else "average order value is undefined in one period"
    )
    detail = (
        f"Orders went from {decomp.orders_previous:,.0f} to {decomp.orders_current:,.0f} and "
        f"{aov_text}. Volume effect: {format_change(Metric.REVENUE, vol)}; "
        f"order value effect: {format_change(Metric.REVENUE, aov)}; together they equal the "
        f"revenue change of {format_change(Metric.REVENUE, decomp.revenue_change)}. "
        f"In this decomposition, {lead} accounts for the larger part."
    )
    if decomp.notes:
        detail += " " + " ".join(decomp.notes)
    return Finding("driver", _tone(decomp.revenue_change), f"Revenue driver: {lead}", detail)


def generate_findings(
    changes: dict[Metric, MetricChange],
    comparison_label: str,
    contributions: list[ContributionResult | MarginDecomposition] | None = None,
    revenue_decomposition: RevenueDecomposition | None = None,
    comparable: bool = True,
    data_notes: list[str] | None = None,
) -> list[Finding]:
    """Assemble findings in reading order. Returns only data notes if not comparable."""
    findings: list[Finding] = [
        Finding("data", "caution", "Data note", note) for note in (data_notes or [])
    ]
    if not comparable:
        findings.append(Finding(
            "data", "caution", "Comparison unavailable",
            f"{comparison_label} cannot be compared because one of the periods has no data.",
        ))
        return findings

    flagged = set(significant_changes(changes))
    for metric in (Metric.REVENUE, Metric.PROFIT, Metric.ORDERS, Metric.MARGIN):
        if metric in changes and metric in flagged:
            findings.append(headline_finding(changes[metric], comparison_label))

    for result in contributions or []:
        findings.extend(contributor_findings(result))
        if isinstance(result, MarginDecomposition):
            findings.extend(margin_findings(result))

    if revenue_decomposition is not None:
        findings.append(driver_finding(revenue_decomposition))
    return findings
