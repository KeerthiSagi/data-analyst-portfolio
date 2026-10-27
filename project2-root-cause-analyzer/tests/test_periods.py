from datetime import date

import pandas as pd
import pytest

from cause.periods import (
    ComparisonMode,
    Coverage,
    Granularity,
    Period,
    add_months,
    available_periods,
    calendar_period,
    compare_periods,
    comparison_period,
    coverage,
    custom_period,
    shift_years,
)

PREV = ComparisonMode.PREVIOUS_PERIOD
YOY = ComparisonMode.YEAR_OVER_YEAR


# ------------------------------------------------------------------
# Date arithmetic
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "start, months, expected",
    [
        (date(2014, 1, 31), -1, date(2013, 12, 31)),
        (date(2014, 3, 31), -1, date(2014, 2, 28)),
        (date(2012, 3, 31), -1, date(2012, 2, 29)),   # leap year
        (date(2014, 1, 15), 13, date(2015, 2, 15)),
        (date(2014, 12, 1), 1, date(2015, 1, 1)),
    ],
)
def test_add_months_clamps_day(start, months, expected):
    assert add_months(start, months) == expected


def test_shift_years_leap_day():
    assert shift_years(date(2012, 2, 29), -1) == date(2011, 2, 28)
    assert shift_years(date(2016, 2, 29), -4) == date(2012, 2, 29)


# ------------------------------------------------------------------
# Calendar periods
# ------------------------------------------------------------------

def test_calendar_month_boundaries():
    p = calendar_period(Granularity.MONTH, "2014-02-17")
    assert (p.start, p.end, p.days, p.label) == (date(2014, 2, 1), date(2014, 2, 28), 28, "Feb 2014")
    leap = calendar_period(Granularity.MONTH, date(2012, 2, 3))
    assert leap.end == date(2012, 2, 29) and leap.days == 29


@pytest.mark.parametrize(
    "anchor, start, end, label",
    [
        ("2014-01-01", date(2014, 1, 1), date(2014, 3, 31), "Q1 2014"),
        ("2014-06-30", date(2014, 4, 1), date(2014, 6, 30), "Q2 2014"),
        ("2014-08-15", date(2014, 7, 1), date(2014, 9, 30), "Q3 2014"),
        ("2014-12-31", date(2014, 10, 1), date(2014, 12, 31), "Q4 2014"),
    ],
)
def test_calendar_quarter_boundaries(anchor, start, end, label):
    p = calendar_period(Granularity.QUARTER, anchor)
    assert (p.start, p.end, p.label) == (start, end, label)


def test_calendar_year():
    p = calendar_period(Granularity.YEAR, pd.Timestamp("2012-07-04 13:00"))
    assert (p.start, p.end, p.days, p.label) == (date(2012, 1, 1), date(2012, 12, 31), 366, "2012")


def test_period_rejects_reversed_range():
    with pytest.raises(ValueError, match="before its start"):
        custom_period("2014-05-01", "2014-04-01")


def test_calendar_period_rejects_custom():
    with pytest.raises(ValueError):
        calendar_period(Granularity.CUSTOM, "2014-01-01")


# ------------------------------------------------------------------
# Comparison windows
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "granularity, anchor, mode, expected_start, expected_end",
    [
        # Previous calendar month, across a year boundary
        (Granularity.MONTH, "2014-01-10", PREV, date(2013, 12, 1), date(2013, 12, 31)),
        # Previous month is a full (shorter) calendar month, not 31 days back
        (Granularity.MONTH, "2013-03-10", PREV, date(2013, 2, 1), date(2013, 2, 28)),
        (Granularity.MONTH, "2012-03-10", PREV, date(2012, 2, 1), date(2012, 2, 29)),
        # Year over year, leap February vs non-leap February
        (Granularity.MONTH, "2012-02-10", YOY, date(2011, 2, 1), date(2011, 2, 28)),
        (Granularity.QUARTER, "2014-02-01", PREV, date(2013, 10, 1), date(2013, 12, 31)),
        (Granularity.QUARTER, "2014-05-01", YOY, date(2013, 4, 1), date(2013, 6, 30)),
        (Granularity.YEAR, "2013-06-01", PREV, date(2012, 1, 1), date(2012, 12, 31)),
        (Granularity.YEAR, "2013-06-01", YOY, date(2012, 1, 1), date(2012, 12, 31)),
    ],
)
def test_calendar_comparisons(granularity, anchor, mode, expected_start, expected_end):
    current = calendar_period(granularity, anchor)
    comp = comparison_period(current, mode)
    assert (comp.start, comp.end) == (expected_start, expected_end)
    assert comp.granularity is granularity


def test_custom_whole_months_shift_by_months():
    current = custom_period("2014-01-01", "2014-03-31")   # 90 days
    comp = comparison_period(current, PREV)
    assert (comp.start, comp.end) == (date(2013, 10, 1), date(2013, 12, 31))


def test_custom_whole_months_ending_in_leap_february():
    current = custom_period("2012-03-01", "2012-04-30")
    comp = comparison_period(current, PREV)
    assert (comp.start, comp.end) == (date(2012, 1, 1), date(2012, 2, 29))


def test_custom_partial_range_uses_equal_length_window():
    current = custom_period("2014-03-10", "2014-03-23")   # 14 days
    comp = comparison_period(current, PREV)
    assert (comp.start, comp.end) == (date(2014, 2, 24), date(2014, 3, 9))
    assert comp.days == current.days == 14


def test_custom_equal_length_window_across_leap_day():
    current = custom_period("2012-03-01", "2012-03-10")
    comp = comparison_period(current, PREV)
    assert (comp.start, comp.end) == (date(2012, 2, 20), date(2012, 2, 29))


def test_custom_year_over_year_with_leap_day():
    current = custom_period("2012-02-15", "2012-02-29")
    comp = comparison_period(current, YOY)
    assert (comp.start, comp.end) == (date(2011, 2, 15), date(2011, 2, 28))


def test_single_day_custom_period():
    current = custom_period("2014-01-01", "2014-01-01")
    comp = comparison_period(current, PREV)
    assert (comp.start, comp.end) == (date(2013, 12, 31), date(2013, 12, 31))


# ------------------------------------------------------------------
# Period lists and coverage
# ------------------------------------------------------------------

def test_available_periods_latest_first():
    quarters = available_periods(date(2013, 11, 5), date(2014, 4, 2), Granularity.QUARTER)
    assert [q.label for q in quarters] == ["Q2 2014", "Q1 2014", "Q4 2013"]


def test_available_periods_rejects_custom():
    with pytest.raises(ValueError):
        available_periods(date(2014, 1, 1), date(2014, 2, 1), Granularity.CUSTOM)


def test_coverage_states():
    lo, hi = date(2011, 1, 1), date(2014, 12, 31)
    assert coverage(calendar_period(Granularity.MONTH, "2014-06-01"), lo, hi) is Coverage.FULL
    assert coverage(calendar_period(Granularity.MONTH, "2010-12-01"), lo, hi) is Coverage.NONE
    assert coverage(custom_period("2010-12-15", "2011-01-15"), lo, hi) is Coverage.PARTIAL


def test_period_mask_is_inclusive_and_ignores_time():
    dates = pd.Series(pd.to_datetime(["2014-01-31 23:59", "2014-02-01", "2014-02-28 08:00", "2014-03-01"], format="mixed"))
    mask = calendar_period(Granularity.MONTH, "2014-02-01").mask(dates)
    assert mask.tolist() == [False, True, True, False]


# ------------------------------------------------------------------
# Comparison bundle
# ------------------------------------------------------------------

def _dates(*values):
    return pd.Series(pd.to_datetime(list(values)))


def test_compare_periods_happy_path_and_label():
    dates = _dates("2014-02-03", "2014-02-20", "2014-03-05")
    result = compare_periods(dates, calendar_period(Granularity.MONTH, "2014-03-01"), PREV,
                             data_range=(date(2011, 1, 1), date(2014, 12, 31)))
    assert result.is_comparable
    assert (result.current_rows, result.comparison_rows) == (1, 2)
    assert result.label == "Mar 2014 vs Feb 2014 (previous month)"
    assert result.warnings == ()   # calendar months of different length are normal


def test_compare_periods_yoy_label():
    dates = _dates("2013-04-03", "2014-04-20")
    result = compare_periods(dates, calendar_period(Granularity.QUARTER, "2014-04-01"), YOY)
    assert result.label == "Q2 2014 vs Q2 2013 (same period last year)"
    assert result.is_comparable


def test_compare_periods_comparison_before_data():
    dates = _dates("2011-01-03", "2011-01-20")
    result = compare_periods(dates, calendar_period(Granularity.MONTH, "2011-01-01"), PREV)
    assert result.comparison_coverage is Coverage.NONE
    assert result.comparison_rows == 0
    assert not result.is_comparable
    assert any("outside the data range" in w for w in result.warnings)


def test_compare_periods_in_range_but_no_rows():
    dates = _dates("2014-01-03", "2014-03-20")
    result = compare_periods(dates, calendar_period(Granularity.MONTH, "2014-03-01"), PREV)
    assert result.comparison_coverage is Coverage.FULL
    assert result.comparison_rows == 0
    assert not result.is_comparable
    assert any("has no orders" in w for w in result.warnings)


def test_compare_periods_uses_full_data_range_for_coverage():
    # The filtered rows start in March, but the dataset itself starts earlier.
    dates = _dates("2014-03-05")
    result = compare_periods(
        dates,
        calendar_period(Granularity.MONTH, "2014-03-01"),
        PREV,
        data_range=(date(2011, 1, 1), date(2014, 12, 31)),
    )
    assert result.comparison_coverage is Coverage.FULL
    assert any("has no orders" in w for w in result.warnings)


def test_compare_periods_empty_data():
    result = compare_periods(pd.Series([], dtype="datetime64[ns]"),
                             calendar_period(Granularity.MONTH, "2014-03-01"))
    assert not result.is_comparable
    assert result.current_coverage is Coverage.NONE
    assert "No data matches the current filters." in result.warnings


def test_compare_periods_partial_coverage_warning():
    dates = _dates("2011-01-01", "2011-02-01")
    current = custom_period("2011-01-10", "2011-01-20")   # previous window starts 31 Dec 2010
    result = compare_periods(dates, current, PREV)
    assert result.comparison_coverage is Coverage.PARTIAL
    assert any("partly covered" in w for w in result.warnings)


def test_custom_length_mismatch_is_flagged():
    dates = _dates("2011-02-20", "2012-02-20")
    result = compare_periods(dates, custom_period("2012-02-15", "2012-02-29"), YOY)
    assert any("differ in length" in w for w in result.warnings)


def test_period_is_hashable_for_caching():
    assert len({calendar_period(Granularity.MONTH, "2014-01-01"),
                calendar_period(Granularity.MONTH, "2014-01-20")}) == 1
