"""Reusable UI building blocks. All text from data is HTML-escaped."""

from __future__ import annotations

import re
from contextlib import contextmanager
from html import escape

import streamlit as st

from cause.insights import CAUSATION_NOTE
from ui.filters import AnalysisContext, COMPARISON_LABELS, summarize_selection

TONES = {"positive", "negative", "neutral", "caution"}


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Headers and sections
# ------------------------------------------------------------------

def page_header(title: str, subtitle: str = "", eyebrow: str = "CAUSE") -> None:
    _html(
        '<div class="cause-header">'
        f'<div class="cause-eyebrow">{escape(eyebrow)}</div>'
        f'<h1 class="cause-title">{escape(title)}</h1>'
        + (f'<p class="cause-subtitle">{escape(subtitle)}</p>' if subtitle else "")
        + "</div>"
    )


@contextmanager
def section(title: str, caption: str | None = None, key: str | None = None):
    """A bordered card section. Use as `with section("Title"): ...`.

    The container key (prefix "cause-section-") is what the CSS styles.
    """
    slug = key or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    with st.container(border=True, key=f"cause-section-{slug}"):
        st.markdown(f"#### {title}")
        if caption:
            st.caption(caption)
        yield


# ------------------------------------------------------------------
# KPI cards
# ------------------------------------------------------------------

def kpi_card_html(
    label: str,
    value: str,
    delta: str | None = None,
    tone: str = "neutral",
    footnote: str | None = None,
    flagged: bool = False,
) -> str:
    tone = tone if tone in TONES else "neutral"
    badge = '<span class="cause-badge">Notable</span>' if flagged else ""
    parts = [
        f'<div class="cause-card{" cause-flag" if flagged else ""}">',
        f'<div class="cause-kpi-label">{escape(label)}{badge}</div>',
        f'<div class="cause-kpi-value">{escape(value)}</div>',
    ]
    if delta:
        parts.append(f'<div class="cause-kpi-delta cause-tone-{tone}">{escape(delta)}</div>')
    if footnote:
        parts.append(f'<div class="cause-kpi-foot">{escape(footnote)}</div>')
    parts.append("</div>")
    return "".join(parts)


def kpi_row(cards: list[str]) -> None:
    """Render KPI cards (from kpi_card_html) in a responsive grid."""
    _html('<div class="cause-grid">' + "".join(cards) + "</div>")


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

def callout(title: str, body: str, tone: str = "neutral") -> None:
    tone = tone if tone in TONES else "neutral"
    _html(
        f'<div class="cause-callout {tone}">'
        f'<div class="cause-callout-title">{escape(title)}</div>'
        f'<div class="cause-callout-body">{escape(body)}</div></div>'
    )


def warning_message(text: str) -> None:
    st.warning(text, icon=":material/warning:")


def empty_state(title: str, body: str) -> None:
    _html(
        '<div class="cause-empty">'
        f'<div class="cause-empty-title">{escape(title)}</div>'
        f'<div class="cause-empty-body">{escape(body)}</div></div>'
    )


# ------------------------------------------------------------------
# Context summaries
# ------------------------------------------------------------------

def filter_summary(ctx: AnalysisContext) -> None:
    """Chips showing the periods being compared and every active filter."""
    chips = []
    if ctx.comparison is not None:
        chips.append(
            f'<span class="cause-chip period">Current <b>{escape(ctx.comparison.current.label)}</b></span>'
        )
        chips.append(
            f'<span class="cause-chip period">Compared with <b>{escape(ctx.comparison.comparison.label)}</b>'
            f" · {escape(COMPARISON_LABELS[ctx.comparison.mode].lower())}</span>"
        )
    for name, text in summarize_selection(ctx.selection):
        chips.append(f'<span class="cause-chip">{escape(name)}: <b>{escape(text)}</b></span>')
    _html('<div class="cause-chips">' + "".join(chips) + "</div>")


def context_warnings(ctx: AnalysisContext) -> None:
    for w in ctx.warnings:
        warning_message(w)
    if ctx.is_ready and not ctx.is_comparable:
        warning_message(
            "This comparison is not available: at least one period has no orders for the "
            "current filters. Choose another period or comparison, or widen the filters."
        )


def page_intro(title: str, subtitle: str, ctx: AnalysisContext) -> None:
    """Standard top of every page: header, filter chips, warnings."""
    page_header(title, subtitle)
    filter_summary(ctx)
    context_warnings(ctx)


# ------------------------------------------------------------------
# Methodology
# ------------------------------------------------------------------

METHODOLOGY = [
    ("Contribution, not causation",
     "CAUSE shows where a change happened (which markets, regions, categories or segments "
     "moved). That points to areas worth investigating; it does not prove why the change happened."),
    ("How orders are counted",
     "An order is one Order ID + Customer ID + Order Date. Some Order IDs are reused for "
     "different customers or dates, so the ID alone would undercount orders."),
    ("Allocated vs actual orders",
     "One order can include several categories or segments, so actual order counts per group "
     "overlap and add up to more than the total. For contribution charts each order is split "
     "equally across the groups it touches (an equal-split convention), so groups add up to "
     "the true total. These values are labelled 'allocated orders'."),
    ("Profit margin in percentage points",
     "Margin is total profit ÷ total revenue, never an average of group margins. Changes are "
     "shown in percentage points (pp): 12.5% → 10.0% is −2.5 pp, not −20%."),
    ("Revenue drivers",
     "Revenue change is split into an order-volume effect and an average-order-value effect that "
     "add up exactly. Per-group volume and order-value effects do not necessarily add up to the "
     "overall effects, because orders overlap across groups and the overall average also "
     "reflects the mix of groups."),
    ("Currency",
     "Values are shown in US dollars. The dataset does not state its currency, so this is an "
     "assumption that has not been independently verified."),
]


def methodology_section() -> None:
    with st.expander("Methodology and limitations", icon=":material/info:"):
        st.caption(CAUSATION_NOTE)
        for title, body in METHODOLOGY:
            st.markdown(f"**{title}.** {body}")
