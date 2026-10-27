"""Cached data loading, sidebar controls, and the per-run analysis context.

Sidebar widgets are rendered by the app entry point on every run, before
the selected page, so the same widgets (and their values) are shared by all
four pages and persist while navigating.
"""

from __future__ import annotations

from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from cause.data import LoadedDataset, load_dataset, resolve_data_path
from cause.periods import ComparisonMode, Granularity
from ui.filters import (
    COMPARISON_LABELS,
    GRANULARITY_LABELS,
    AnalysisContext,
    FilterSelection,
    PeriodChoice,
    build_context,
    calendar_choice,
    custom_choice,
    default_period,
    options_for,
    period_options,
    region_options,
)

CONTEXT_KEY = "cause_context"

FILTER_KEYS = {
    "Market": "f_market",
    "Region": "f_region",
    "Category": "f_category",
    "Customer Segment": "f_segment",
}
GRANULARITY_KEY = "p_granularity"
MODE_KEY = "p_mode"
CUSTOM_KEY = "p_custom"
PERIOD_KEYS = {
    Granularity.MONTH: "p_month",
    Granularity.QUARTER: "p_quarter",
    Granularity.YEAR: "p_year",
}
ALL_KEYS = [*FILTER_KEYS.values(), GRANULARITY_KEY, MODE_KEY, CUSTOM_KEY, *PERIOD_KEYS.values()]


# ------------------------------------------------------------------
# Data
# ------------------------------------------------------------------

@st.cache_data(show_spinner="Loading the Global Superstore dataset…", max_entries=2)
def _load_cached(path: str, modified_ns: int) -> LoadedDataset:
    # modified_ns is part of the cache key so an updated file is reloaded.
    return load_dataset(path)


def load_data() -> LoadedDataset:
    """Validated dataset, cached per file path and modification time."""
    path = resolve_data_path()
    return _load_cached(str(path), path.stat().st_mtime_ns)


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------

def keep_widget_state() -> None:
    """Keep widget values that are not rendered on this run.

    Streamlit discards a widget's value when the widget is not drawn (for
    example the Month picker while Quarter is selected). Re-assigning each
    key turns it into plain session state so earlier choices survive.
    """
    for key in ALL_KEYS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def _reset_filters() -> None:
    for key in FILTER_KEYS.values():
        st.session_state[key] = []


def _sidebar_label(text: str) -> None:
    st.sidebar.markdown(f'<div class="cause-side-label">{escape(text)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------

def _period_controls(data: pd.DataFrame) -> PeriodChoice:
    lo, hi = data["order_date"].min(), data["order_date"].max()
    sb = st.sidebar
    _sidebar_label("Analysis period")

    st.session_state.setdefault(GRANULARITY_KEY, GRANULARITY_LABELS[Granularity.QUARTER])
    st.session_state.setdefault(MODE_KEY, COMPARISON_LABELS[ComparisonMode.PREVIOUS_PERIOD])

    granularity_label = sb.segmented_control(
        "Period type",
        options=list(GRANULARITY_LABELS.values()),
        key=GRANULARITY_KEY,
        label_visibility="collapsed",
    )
    if granularity_label is None:
        # segmented_control can be deselected; ask instead of guessing.
        mode = ComparisonMode.PREVIOUS_PERIOD
        return PeriodChoice(Granularity.QUARTER, mode, None, "Choose a period type: Month, Quarter, Year or Custom.")
    granularity = next(g for g, lbl in GRANULARITY_LABELS.items() if lbl == granularity_label)

    if granularity is Granularity.CUSTOM:
        default = default_period(lo, hi, Granularity.QUARTER)
        st.session_state.setdefault(CUSTOM_KEY, (default.start, default.end))
        value = sb.date_input(
            "Current period",
            key=CUSTOM_KEY,
            min_value=lo.date(),
            max_value=hi.date(),
            format="YYYY-MM-DD",
        )
    else:
        key = PERIOD_KEYS[granularity]
        periods = period_options(lo, hi, granularity)
        labels = {p.start.isoformat(): p.label for p in periods}
        st.session_state.setdefault(key, default_period(lo, hi, granularity).start.isoformat())
        start_iso = sb.selectbox(
            "Current period",
            options=list(labels),
            format_func=lambda iso: labels.get(iso, iso),
            key=key,
        )

    mode_label = sb.radio(
        "Compare with",
        options=list(COMPARISON_LABELS.values()),
        key=MODE_KEY,
    )
    mode = next(m for m, lbl in COMPARISON_LABELS.items() if lbl == mode_label)

    if granularity is Granularity.CUSTOM:
        return custom_choice(value, mode)
    return calendar_choice(granularity, start_iso, mode)


def _filter_controls(data: pd.DataFrame) -> FilterSelection:
    sb = st.sidebar
    _sidebar_label("Filters")
    sb.caption("Leave a filter empty to include everything.")

    for key in FILTER_KEYS.values():
        st.session_state.setdefault(key, [])

    markets = sb.multiselect(
        "Market", options_for(data, "Market"), key=FILTER_KEYS["Market"], placeholder="All markets"
    )
    region_opts, conflicting = region_options(data, markets, st.session_state[FILTER_KEYS["Region"]])
    regions = sb.multiselect(
        "Region",
        region_opts,
        key=FILTER_KEYS["Region"],
        placeholder="All regions" if not markets else "All regions in selected markets",
        help="Regions are labelled with their market, because names such as 'Central' exist in several markets.",
    )
    if conflicting:
        sb.caption(f":orange[Outside selected markets: {', '.join(conflicting)}]")
    categories = sb.multiselect(
        "Category", options_for(data, "Category"), key=FILTER_KEYS["Category"], placeholder="All categories"
    )
    segments = sb.multiselect(
        "Customer Segment",
        options_for(data, "Customer Segment"),
        key=FILTER_KEYS["Customer Segment"],
        placeholder="All segments",
    )
    active = any(st.session_state[k] for k in FILTER_KEYS.values())
    sb.button("Reset filters", on_click=_reset_filters, disabled=not active, width="stretch")
    return FilterSelection(tuple(markets), tuple(regions), tuple(categories), tuple(segments))


def _data_status(loaded: LoadedDataset) -> None:
    r = loaded.report
    k = r.order_key
    st.sidebar.markdown(
        '<div class="cause-side-label">Data</div>'
        '<div class="cause-side-meta">'
        f"Global Superstore · {r.row_count:,} order lines · {k.distinct_order_keys:,} orders<br>"
        f"{r.date_min:%d %b %Y} – {r.date_max:%d %b %Y}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_sidebar(loaded: LoadedDataset) -> AnalysisContext:
    """Draw shared controls, build the analysis context, and store it."""
    keep_widget_state()
    data = loaded.data
    choice = _period_controls(data)
    selection = _filter_controls(data)
    _data_status(loaded)
    ctx = build_context(data, selection, choice)
    st.session_state[CONTEXT_KEY] = ctx
    return ctx


def get_context() -> AnalysisContext:
    """The context built by the app shell for this run."""
    ctx = st.session_state.get(CONTEXT_KEY)
    if ctx is None:
        st.error("The analysis context is not available. Open the app from app_root_cause.py.")
        st.stop()
    return ctx
