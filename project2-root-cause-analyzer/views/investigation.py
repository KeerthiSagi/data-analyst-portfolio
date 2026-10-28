"""Page 2: Root Cause Investigation."""

import streamlit as st

from cause.contribution import ALLOCATED_BASIS, DISTINCT_BASIS, MarginDecomposition, dimension_label
from cause.insights import format_change, format_pct, format_pp, format_value
from cause.metrics import Metric
from cause.report import run_investigation
from ui import theme
from ui.chart_data import (
    contribution_display,
    margin_display,
    margin_effects_long,
    waterfall_steps,
)
from ui.charts import effects_chart, show_chart, waterfall_chart
from ui.components import (
    callout,
    causation_note,
    empty_state,
    finding_callouts,
    kpi_card_html,
    kpi_row,
    numeric_table,
    page_intro,
    section,
)
from ui.state import get_context, investigation_controls

ADDITIVE_FORMATS = {
    Metric.REVENUE: {"Previous": "money", "Current": "money", "Change": "money_change"},
    Metric.PROFIT: {"Previous": "money", "Current": "money", "Change": "money_change"},
    Metric.ORDERS: {"Previous": "count1", "Current": "count1", "Change": "count_change",
                    "Actual orders (previous)": "count", "Actual orders (current)": "count"},
}
SHARE_FORMATS = {"% change": "pct", "% of net change": "pct", "% of total movement": "pct"}
MARGIN_FORMATS = {
    "Margin (previous) %": "plain_pct", "Margin (current) %": "plain_pct",
    "Revenue share (previous) %": "plain_pct", "Revenue share (current) %": "plain_pct",
    "Rate effect (pp)": "pp", "Mix effect (pp)": "pp", "Contribution (pp)": "pp",
}


def render() -> None:
    ctx = get_context()
    page_intro(
        "Root Cause Investigation",
        "Find which groups account for a metric's change between the two periods, then drill "
        "into one group. Results describe where the change happened, not why.",
        ctx,
    )
    if not ctx.is_ready:
        return
    with section("Investigation settings", key="inv-settings"):
        settings = investigation_controls(ctx)
    if settings is None:
        return
    if not ctx.is_comparable:
        empty_state("No comparison available",
                    "Contribution analysis needs orders in both periods. Choose another period, "
                    "comparison or wider filters.")
        return

    result = run_investigation(ctx.current, ctx.previous, settings, ctx.comparison.label)
    _headline(result, ctx)
    if isinstance(result.main, MarginDecomposition):
        _margin_section(result.main, "main", f"Margin change by {result.main.dimension_labels[0]}")
    else:
        _additive_section(result.main, "main", f"{result.metric.label} change by {result.main.dimension_labels[0]}")
    _drill_section(result)
    with section("Findings", "Rule-based findings generated from the numbers on this page."):
        finding_callouts([r.finding for r in result.findings])
        causation_note()


# ------------------------------------------------------------------
# Sections
# ------------------------------------------------------------------

def _headline(result, ctx) -> None:
    h = result.headline
    m = result.metric
    c = ctx.comparison
    if m.is_percentage:
        change, tone, extra = format_pp(h.pp_change), _tone(h.pp_change), None
        foot = "Percentage points. Margin = total profit ÷ total revenue."
    else:
        pct = h.pct_change
        change = format_change(m, h.absolute_change)
        extra = format_pct(pct) + " change" if pct == pct else (h.unavailable_note or "")
        tone = _tone(h.absolute_change)
        foot = "Current minus comparison"
    cards = [
        kpi_card_html(f"{m.label} · {c.comparison.label}", format_value(m, h.previous), footnote="Comparison period"),
        kpi_card_html(f"{m.label} · {c.current.label}", format_value(m, h.current), footnote="Current period"),
        kpi_card_html("Net change", change, extra, tone, footnote=foot),
    ]
    if m is Metric.ORDERS:
        cards.append(kpi_card_html("Order lines", f"{len(ctx.current):,} vs {len(ctx.previous):,}",
                                   footnote="Rows in the data; orders count distinct transactions"))
    kpi_row(cards)


def _tone(v) -> str:
    if v is None or v != v or v == 0:
        return "neutral"
    return "positive" if v > 0 else "negative"


def _notes(analysis) -> None:
    for note in analysis.notes:
        if note in (DISTINCT_BASIS,):
            continue
        st.caption(note)


def _additive_section(result, key: str, title: str, scope_note: str | None = None) -> None:
    m = result.metric
    caption = ("Waterfall from the comparison total to the current total. Each step is one group's "
               "change; the steps add up exactly.")
    if scope_note:
        caption = f"{scope_note} {caption}"
    with section(title, caption, key=f"inv-{key}-additive"):
        if result.table.empty:
            empty_state("No groups to show", "Neither period has data for this breakdown.")
            return
        if m is Metric.ORDERS:
            callout("Allocated orders", f"{ALLOCATED_BASIS} {DISTINCT_BASIS} The actual distinct "
                    "counts are shown in the last two table columns.", "neutral")
        steps = waterfall_steps(result)
        show_chart(waterfall_chart(steps, m.label, money=m is not Metric.ORDERS,
                                   decimals=1 if m is Metric.ORDERS else 0),
                   height=380, key=f"inv-{key}-waterfall")
        if not result.shares_reliable:
            callout("Small net change",
                    "Group movements largely offset each other, so '% of net change' is hidden. "
                    "Use the absolute change and '% of total movement' instead.", "caution")
        numeric_table(contribution_display(result), {**ADDITIVE_FORMATS[m], **SHARE_FORMATS},
                      key=f"inv-{key}-table")
        st.caption("Ranked by size of change. '% of net change' is the group's change ÷ the net change: "
                   "positive means it moved with the net change, negative means it offset it. "
                   "'% of total movement' is the group's change ÷ the sum of all groups' absolute changes: "
                   "negative means the group moved down.")
        _notes(result)


def _margin_section(result: MarginDecomposition, key: str, title: str, scope_note: str | None = None) -> None:
    caption = ("Each group's contribution to the overall margin change in percentage points, split into a "
               "rate effect (its own margin changed) and a mix effect (its share of revenue changed).")
    if scope_note:
        caption = f"{scope_note} {caption}"
    with section(title, caption, key=f"inv-{key}-margin"):
        if not result.comparable:
            empty_state("Margin cannot be decomposed", " ".join(result.notes))
            return
        kpi_row([
            kpi_card_html("Margin change", format_pp(result.change_pp), tone=_tone(result.change_pp),
                          footnote=f"{format_value(Metric.MARGIN, result.margin_previous)} → "
                                   f"{format_value(Metric.MARGIN, result.margin_current)}"),
            kpi_card_html("Rate effect", format_pp(result.rate_effect_pp), tone=_tone(result.rate_effect_pp),
                          footnote="Margins within groups"),
            kpi_card_html("Mix effect", format_pp(result.mix_effect_pp), tone=_tone(result.mix_effect_pp),
                          footnote="Shift in revenue share"),
            kpi_card_html("Total effect", format_pp(result.rate_effect_pp + result.mix_effect_pp),
                          footnote="Rate + mix = margin change"),
        ])
        long = margin_effects_long(result)
        show_chart(effects_chart(long, {"Rate effect": theme.CATEGORICAL[0], "Mix effect": theme.CATEGORICAL[6]}, "pp"),
                   height=max(260, 34 * long["group"].nunique() + 90), key=f"inv-{key}-effects")
        numeric_table(margin_display(result), MARGIN_FORMATS, key=f"inv-{key}-margin-table")
        st.caption("Group margins are shown for context only; they are never summed or averaged. "
                   "The contributions add up to the overall change.")
        _notes(result)


def _drill_section(result) -> None:
    s = result.settings
    if s.secondary is None:
        return
    secondary_label = dimension_label(s.secondary)
    primary_label = dimension_label(s.primary)
    if result.drill_error:
        callout("Drill-down unavailable", result.drill_error, "caution")
        return
    if result.drill is not None:
        scope = (f"Scope: only orders where {primary_label} = {s.parent}, broken down by {secondary_label}.")
        title = f"Drill-down: {s.parent} by {secondary_label}"
        if isinstance(result.drill, MarginDecomposition):
            _margin_section(result.drill, "drill", title,
                            scope + " Margin here is the parent group's own margin.")
        else:
            _parent_card(result)
            _additive_section(result.drill, "drill", title,
                              scope + " The steps add up to this group's change in the table above.")
        return
    combos = result.combinations
    title = f"Combinations: {primary_label} × {secondary_label}"
    if isinstance(combos, MarginDecomposition):
        _margin_section(combos, "combo", title, "Every combination of the two dimensions.")
        return
    with section(title, "Every combination of the two dimensions, ranked by size of change. "
                 f"Choose a {primary_label.lower()} above to drill into one.", key="inv-combo"):
        table = contribution_display(combos)
        numeric_table(table.head(25), {**ADDITIVE_FORMATS[combos.metric], **SHARE_FORMATS}, key="inv-combo-table")
        st.caption(f"Showing {min(25, len(table))} of {len(table)} combinations. Changes add up to the "
                   "overall change. The CSV export on the Investigation Report page has every row.")


def _parent_card(result) -> None:
    main = result.main.table
    s = result.settings
    row = main[main[s.primary] == s.parent]
    if row.empty:
        return
    r = row.iloc[0]
    m = result.metric
    pct = r["pct_change"]
    kpi_row([
        kpi_card_html(f"{s.parent} · comparison", format_value(m, r["previous"])),
        kpi_card_html(f"{s.parent} · current", format_value(m, r["current"])),
        kpi_card_html(f"{s.parent} · change", format_change(m, r["change"]),
                      format_pct(pct) if pct == pct else "% change n/a", _tone(r["change"])),
    ])


render()
