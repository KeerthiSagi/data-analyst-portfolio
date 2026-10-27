from datetime import date

import pandas as pd
import pytest

from cause.periods import ComparisonMode, Granularity
from ui.filters import (
    FilterSelection,
    apply_filters,
    build_context,
    calendar_choice,
    custom_choice,
    default_period,
    options_for,
    region_options,
    selection_warnings,
    summarize_selection,
)
from tests.hand_example import load_example

PREV = ComparisonMode.PREVIOUS_PERIOD
YOY = ComparisonMode.YEAR_OVER_YEAR


def test_options_for_uses_market_qualified_regions():
    df, _, _ = load_example()
    assert options_for(df, "Region") == ["EU · Central", "US · Central"]
    assert options_for(df, "Market") == ["EU", "US"]


def test_region_options_follow_market():
    df, _, _ = load_example()
    assert region_options(df, ())[0] == ["EU · Central", "US · Central"]
    assert region_options(df, ("US",))[0] == ["US · Central"]


def test_region_selection_outside_market_is_kept_and_reported():
    df, _, _ = load_example()
    options, conflicting = region_options(df, ("US",), ("EU · Central",))
    assert options == ["US · Central", "EU · Central"]   # still selectable, not dropped
    assert conflicting == ["EU · Central"]
    sel = FilterSelection(markets=("US",), regions=("EU · Central",))
    warnings = selection_warnings(df, sel)
    assert any("outside the selected markets" in w for w in warnings)
    assert any("No orders match" in w for w in warnings)


def test_empty_selection_means_all():
    df, _, _ = load_example()
    sel = FilterSelection()
    assert sel.is_unfiltered
    assert len(apply_filters(df, sel)) == len(df)
    assert selection_warnings(df, sel) == []


def test_apply_filters_multi_select_and_combined():
    df, _, _ = load_example()
    sel = FilterSelection(categories=("Furniture", "Technology"))
    assert set(apply_filters(df, sel)["category"]) == {"Furniture", "Technology"}
    sel = FilterSelection(markets=("US",), segments=("Consumer",), categories=("Technology",))
    out = apply_filters(df, sel)
    assert len(out) == 3 and set(out["market"]) == {"US"}


def test_summarize_selection():
    sel = FilterSelection(markets=("EU",), categories=("A", "B", "C", "D"))
    summary = dict(summarize_selection(sel))
    assert summary == {
        "Market": "EU",
        "Region": "All regions",
        "Category": "A, B, C +1 more",
        "Customer Segment": "All segments",
    }


# ------------------------------------------------------------------
# Period choices
# ------------------------------------------------------------------

def test_default_period_is_latest_complete():
    assert default_period("2011-01-01", "2014-12-31", Granularity.QUARTER).label == "Q4 2014"
    # Data ends mid-quarter: the partial quarter is not chosen by default.
    assert default_period("2011-01-01", "2014-11-15", Granularity.QUARTER).label == "Q3 2014"
    assert default_period("2011-01-01", "2014-11-15", Granularity.MONTH).label == "Oct 2014"


def test_calendar_choice():
    c = calendar_choice(Granularity.MONTH, "2014-02-01", YOY)
    assert c.period.label == "Feb 2014" and c.mode is YOY and c.message is None
    assert calendar_choice(Granularity.MONTH, None, PREV).period is None


@pytest.mark.parametrize(
    "value, ok, message",
    [
        ((date(2014, 1, 1), date(2014, 3, 31)), True, None),
        ((date(2014, 1, 1),), False, "Choose both a start and an end date"),
        ((), False, "Choose both a start and an end date"),
        (None, False, "Choose both a start and an end date"),
        ((date(2014, 3, 1), date(2014, 1, 1)), False, "end date is before"),
    ],
)
def test_custom_choice(value, ok, message):
    c = custom_choice(value, PREV)
    assert (c.period is not None) is ok
    if message:
        assert message in c.message


# ------------------------------------------------------------------
# Context
# ------------------------------------------------------------------

def test_context_uses_same_filters_for_both_periods():
    df, _, _ = load_example()
    sel = FilterSelection(categories=("Furniture",))
    ctx = build_context(df, sel, calendar_choice(Granularity.MONTH, "2014-02-01", PREV))
    assert ctx.is_comparable
    assert set(ctx.current["category"]) == {"Furniture"}
    assert set(ctx.previous["category"]) == {"Furniture"}
    assert (len(ctx.current), len(ctx.previous)) == (1, 2)
    assert ctx.comparison.label == "Feb 2014 vs Jan 2014 (previous month)"


def test_context_not_comparable_when_comparison_has_no_data():
    df, _, _ = load_example()
    ctx = build_context(df, FilterSelection(), calendar_choice(Granularity.MONTH, "2014-01-01", PREV))
    assert ctx.is_ready and not ctx.is_comparable
    assert any("Dec 2013" in w for w in ctx.warnings)


def test_context_coverage_uses_full_data_range():
    # Filtering to EU must not make the comparison look "outside the data range".
    df, _, _ = load_example()
    sel = FilterSelection(markets=("EU",))
    ctx = build_context(df, sel, calendar_choice(Granularity.MONTH, "2014-02-01", PREV))
    assert ctx.is_comparable
    assert not any("outside the data range" in w for w in ctx.warnings)


def test_context_with_incomplete_period():
    df, _, _ = load_example()
    ctx = build_context(df, FilterSelection(), custom_choice((date(2014, 1, 1),), PREV))
    assert not ctx.is_ready and not ctx.is_comparable
    assert ctx.current.empty and ctx.previous.empty
    assert any("start and an end date" in w for w in ctx.warnings)


def test_context_with_no_matching_rows_has_single_clear_warning():
    df, _, _ = load_example()
    sel = FilterSelection(markets=("US",), segments=("Corporate",))
    ctx = build_context(df, sel, calendar_choice(Granularity.MONTH, "2014-02-01", PREV))
    assert ctx.filtered.empty and not ctx.is_comparable
    assert sum("No orders match" in w for w in ctx.warnings) == 1
    assert not any(w.startswith("No data matches") for w in ctx.warnings)
