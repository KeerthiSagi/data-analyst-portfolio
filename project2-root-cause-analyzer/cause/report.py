"""One investigation, shared by the Investigation and Report pages.

`run_investigation` composes the validated engine (metrics, contribution,
decomposition, insights) for a chosen metric and dimensions. Both pages
call it with the same inputs, so the report and its CSV exports always
match what the investigation page shows.

Export tables keep numbers numeric. Percentages are in percent units
(38.1 means 38.1%) and margin changes are in percentage points; column
names say which.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from cause.contribution import (
    ContributionResult,
    MarginDecomposition,
    contribution_analysis,
    dimension_label,
    drill_down,
    resolve_dimensions,
)
from cause.decomposition import RevenueDecomposition, decompose_revenue
from cause.insights import (
    CAUSATION_NOTE,
    Finding,
    contributor_findings,
    driver_finding,
    format_change,
    format_pct,
    format_pp,
    format_value,
    headline_finding,
    is_significant,
    margin_findings,
    top_contributors,
)
from cause.metrics import Metric, MetricChange, compare_kpis, compute_kpis

INVESTIGATION_METRICS = (Metric.REVENUE, Metric.PROFIT, Metric.ORDERS, Metric.MARGIN)
KPI_EXPORT_METRICS = (Metric.REVENUE, Metric.PROFIT, Metric.ORDERS, Metric.AOV, Metric.MARGIN)

Analysis = ContributionResult | MarginDecomposition


# ------------------------------------------------------------------
# Investigation
# ------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationSettings:
    metric: Metric
    primary: str                     # dimension column
    secondary: str | None = None     # dimension column
    parent: str | None = None        # a group of the primary dimension

    def __post_init__(self):
        if self.metric not in INVESTIGATION_METRICS:
            raise ValueError(f"{self.metric.label} cannot be investigated by contribution.")
        if self.secondary is not None and self.secondary == self.primary:
            raise ValueError("Choose a secondary dimension different from the primary one.")


@dataclass(frozen=True)
class FindingRecord:
    finding: Finding
    metric: str
    scope: str        # dimension or drill-down scope the finding refers to


@dataclass
class InvestigationResult:
    settings: InvestigationSettings
    comparison_label: str
    changes: dict[Metric, MetricChange]
    main: Analysis
    drill: Analysis | None
    drill_error: str | None
    combinations: Analysis | None
    revenue_drivers: RevenueDecomposition
    findings: list[FindingRecord] = field(default_factory=list)

    @property
    def metric(self) -> Metric:
        return self.settings.metric

    @property
    def headline(self) -> MetricChange:
        return self.changes[self.metric]

    @property
    def drill_scope(self) -> str | None:
        s = self.settings
        if s.parent is None or s.secondary is None:
            return None
        return f"{dimension_label(s.primary)} = {s.parent} → {dimension_label(s.secondary)}"


def run_investigation(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    settings: InvestigationSettings,
    comparison_label: str,
) -> InvestigationResult:
    metric = settings.metric
    (primary,) = resolve_dimensions([settings.primary])
    changes = compare_kpis(compute_kpis(current), compute_kpis(previous))
    main = contribution_analysis(current, previous, [primary], metric)

    drill, drill_error, combos = None, None, None
    if settings.secondary is not None:
        (secondary,) = resolve_dimensions([settings.secondary])
        if settings.parent is not None:
            try:
                drill = drill_down(current, previous, primary, settings.parent, secondary, metric)
            except ValueError as exc:
                drill_error = str(exc)
        else:
            combos = contribution_analysis(current, previous, [primary, secondary], metric)

    result = InvestigationResult(
        settings=settings,
        comparison_label=comparison_label,
        changes=changes,
        main=main,
        drill=drill,
        drill_error=drill_error,
        combinations=combos,
        revenue_drivers=decompose_revenue(current, previous),
    )
    result.findings = _collect_findings(result)
    return result


def _collect_findings(result: InvestigationResult) -> list[FindingRecord]:
    metric = result.metric
    records: list[FindingRecord] = []

    def add(findings, scope, metric_label=metric.label):
        records.extend(FindingRecord(f, metric_label, scope) for f in findings)

    # Headline for the chosen metric, plus any other KPI that moved notably.
    for m in INVESTIGATION_METRICS:
        change = result.changes[m]
        if m is metric or is_significant(change):
            add([headline_finding(change, result.comparison_label)], "Overall", m.label)

    main_scope = " × ".join(result.main.dimension_labels)
    add(contributor_findings(result.main), main_scope)
    if isinstance(result.main, MarginDecomposition):
        add(margin_findings(result.main), main_scope)

    if result.drill is not None:
        add(contributor_findings(result.drill), result.drill_scope)
        if isinstance(result.drill, MarginDecomposition):
            add(margin_findings(result.drill), result.drill_scope)

    if metric in (Metric.REVENUE, Metric.ORDERS):
        add([driver_finding(result.revenue_drivers)], "Revenue drivers", Metric.REVENUE.label)
    return records


# ------------------------------------------------------------------
# Export tables
# ------------------------------------------------------------------

def _pct(x: float) -> float:
    return x * 100 if x is not None and not pd.isna(x) else math.nan


def kpi_comparison_frame(changes: dict[Metric, MetricChange]) -> pd.DataFrame:
    rows = []
    for m in KPI_EXPORT_METRICS:
        c = changes[m]
        scale = 100 if m is Metric.MARGIN else 1   # margin values in percent
        rows.append({
            "metric": m.label,
            "unit": "percent" if m is Metric.MARGIN else ("orders" if m is Metric.ORDERS else "USD"),
            "previous_value": c.previous * scale if not pd.isna(c.previous) else math.nan,
            "current_value": c.current * scale if not pd.isna(c.current) else math.nan,
            "absolute_change": (c.absolute_change * scale) if not m.is_percentage else math.nan,
            "pct_change": _pct(c.pct_change),
            "pp_change": c.pp_change,
            "note": c.unavailable_note or "",
        })
    return pd.DataFrame(rows)


def contribution_frame(analysis: Analysis, scope: str | None = None) -> pd.DataFrame:
    """Contribution table for export, one row per group."""
    dims = analysis.dimensions
    t = analysis.table
    out = pd.DataFrame({
        "dimension": " × ".join(analysis.dimension_labels),
        "group": [" / ".join(str(row[d]) for d in dims) for _, row in t.iterrows()],
    })
    if scope:
        out.insert(0, "scope", scope)
    if isinstance(analysis, MarginDecomposition):
        out["previous_margin_pct"] = (t["margin_previous"] * 100).to_numpy()
        out["current_margin_pct"] = (t["margin_current"] * 100).to_numpy()
        out["margin_change_pp"] = t["margin_change_pp"].to_numpy()
        out["previous_revenue_share_pct"] = (t["revenue_share_previous"] * 100).to_numpy()
        out["current_revenue_share_pct"] = (t["revenue_share_current"] * 100).to_numpy()
        out["rate_effect_pp"] = t["rate_effect_pp"].to_numpy()
        out["mix_effect_pp"] = t["mix_effect_pp"].to_numpy()
        out["contribution_pp"] = t["contribution_pp"].to_numpy()
    else:
        out["previous_value"] = t["previous"].to_numpy()
        out["current_value"] = t["current"].to_numpy()
        out["contribution"] = t["change"].to_numpy()
        out["pct_change"] = (t["pct_change"] * 100).to_numpy()
        if analysis.metric is Metric.ORDERS:
            out["distinct_orders_previous"] = t["distinct_orders_previous"].to_numpy()
            out["distinct_orders_current"] = t["distinct_orders_current"].to_numpy()
    out["share_of_net_change_pct"] = (t["share_of_net"] * 100).to_numpy()
    out["share_of_total_movement_pct"] = (t["share_of_gross"] * 100).to_numpy()
    out["metric"] = analysis.metric.label
    out["basis"] = (
        "Allocated orders (equal split across overlapping groups)"
        if analysis.metric is Metric.ORDERS
        else ("Percentage points of overall margin" if isinstance(analysis, MarginDecomposition) else "USD")
    )
    return out


def findings_frame(records: list[FindingRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "finding_type": r.finding.category,
                "tone": r.finding.tone,
                "title": r.finding.title,
                "finding_text": r.finding.detail,
                "metric": r.metric,
                "scope": r.scope,
            }
            for r in records
        ],
        columns=["finding_type", "tone", "title", "finding_text", "metric", "scope"],
    )


def investigation_contribution_frame(result: InvestigationResult) -> pd.DataFrame:
    """Main, drill-down and combination tables stacked for one CSV."""
    frames = [contribution_frame(result.main, scope="All groups")]
    if result.drill is not None:
        frames.append(contribution_frame(result.drill, scope=result.drill_scope))
    if result.combinations is not None:
        frames.append(contribution_frame(result.combinations, scope="Combinations"))
    return pd.concat(frames, ignore_index=True)


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


# ------------------------------------------------------------------
# Readable report
# ------------------------------------------------------------------

def _contributors_md(analysis: Analysis, direction: str, n: int = 5) -> list[str]:
    col = "contribution_pp" if isinstance(analysis, MarginDecomposition) else "change"
    top = top_contributors(analysis, n, direction)
    if top.empty:
        return ["- None"]
    return [
        f"- {' / '.join(str(row[d]) for d in analysis.dimensions)}: "
        f"{format_change(analysis.metric, row[col])}"
        for _, row in top.iterrows()
    ]


def report_markdown(
    result: InvestigationResult,
    filters: list[tuple[str, str]],
    methodology: list[tuple[str, str]],
    generated_at: datetime,
) -> str:
    m = result.metric
    h = result.headline
    lines = [
        "# CAUSE Investigation Report",
        f"Generated {generated_at:%d %b %Y %H:%M}",
        "",
        f"**Metric:** {m.label}  ",
        f"**Comparison:** {result.comparison_label}  ",
        f"**Breakdown:** {' × '.join(result.main.dimension_labels)}"
        + (f" (drill-down: {result.drill_scope})" if result.drill_scope else ""),
        "",
        "**Filters:** " + "; ".join(f"{k}: {v}" for k, v in filters),
        "",
        "## KPI comparison",
        "| Metric | Previous | Current | Change |",
        "|---|---|---|---|",
    ]
    for metric in KPI_EXPORT_METRICS:
        c = result.changes[metric]
        if metric.is_percentage:
            change = format_pp(c.pp_change)
        else:
            change = format_change(metric, c.absolute_change)
            change += f" ({format_pct(c.pct_change)})" if not pd.isna(c.pct_change) else " (% n/a)"
        lines.append(f"| {metric.label} | {format_value(metric, c.previous)} | "
                     f"{format_value(metric, c.current)} | {change} |")
    lines += ["", f"## Largest positive contributors ({m.label})", *_contributors_md(result.main, "positive"),
              "", f"## Largest negative contributors ({m.label})", *_contributors_md(result.main, "negative"),
              "", "## Findings"]
    lines += [f"- **{r.finding.title}** ({r.scope}): {r.finding.detail}" for r in result.findings] or ["- None"]
    lines += ["", "## Methodology and limitations", f"_{CAUSATION_NOTE}_", ""]
    lines += [f"- **{t}.** {b}" for t, b in methodology]
    return "\n".join(lines) + "\n"
