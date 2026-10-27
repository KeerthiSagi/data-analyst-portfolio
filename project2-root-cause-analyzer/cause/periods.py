"""Period selection and comparison windows.

Rules
-----
* Month / quarter / year periods are full calendar periods.
* "Previous period" for a calendar period is the previous calendar period
  of the same type (Mar 2013 -> Feb 2013, even though the day counts differ).
* "Same period last year" shifts a calendar period back one year.
* A custom range that covers whole calendar months is shifted by whole
  months (Jan-Mar -> Oct-Dec), so quarter-like ranges compare cleanly.
  Any other custom range is compared with the window of equal length that
  ends the day before it starts.
* Year-over-year date shifts clamp 29 Feb to 28 Feb.
* Coverage is reported against the data's date range so the UI can say
  when a comparison window is empty or only partly covered.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

import pandas as pd


class Granularity(str, Enum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class ComparisonMode(str, Enum):
    PREVIOUS_PERIOD = "previous_period"
    YEAR_OVER_YEAR = "year_over_year"


class Coverage(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


COMPARISON_LABELS = {
    (Granularity.MONTH, ComparisonMode.PREVIOUS_PERIOD): "previous month",
    (Granularity.QUARTER, ComparisonMode.PREVIOUS_PERIOD): "previous quarter",
    (Granularity.YEAR, ComparisonMode.PREVIOUS_PERIOD): "previous year",
    (Granularity.CUSTOM, ComparisonMode.PREVIOUS_PERIOD): "previous period",
}
YOY_LABEL = "same period last year"


# ------------------------------------------------------------------
# Date helpers
# ------------------------------------------------------------------

def _to_date(value: date | pd.Timestamp | str) -> date:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        # datetime is a subclass of date; strip any time part.
        return date(value.year, value.month, value.day)
    return pd.Timestamp(value).date()


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months(d: date, months: int) -> date:
    """Shift by whole months, clamping the day to the target month's length."""
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def shift_years(d: date, years: int) -> date:
    """Shift by whole years; 29 Feb becomes 28 Feb in non-leap years."""
    return add_months(d, 12 * years)


def _months_spanned(start: date, end: date) -> int | None:
    """Number of whole calendar months if [start, end] is exactly whole months."""
    if start.day != 1 or end != month_end(end.year, end.month):
        return None
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


# ------------------------------------------------------------------
# Period
# ------------------------------------------------------------------

@dataclass(frozen=True)
class Period:
    """Inclusive date range [start, end]."""

    start: date
    end: date
    granularity: Granularity = Granularity.CUSTOM

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"Period end ({self.end:%d %b %Y}) is before its start ({self.start:%d %b %Y})."
            )

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def label(self) -> str:
        if self.granularity is Granularity.MONTH:
            return f"{self.start:%b %Y}"
        if self.granularity is Granularity.QUARTER:
            return f"Q{(self.start.month - 1) // 3 + 1} {self.start.year}"
        if self.granularity is Granularity.YEAR:
            return f"{self.start.year}"
        return f"{self.start:%d %b %Y} – {self.end:%d %b %Y}"

    def mask(self, dates: pd.Series) -> pd.Series:
        """Boolean mask of rows whose date falls inside the period."""
        normalized = pd.to_datetime(dates).dt.normalize()
        return (normalized >= pd.Timestamp(self.start)) & (normalized <= pd.Timestamp(self.end))


def calendar_period(granularity: Granularity, anchor: date | pd.Timestamp | str) -> Period:
    """The month, quarter or year that contains `anchor`."""
    granularity = Granularity(granularity)
    d = _to_date(anchor)
    if granularity is Granularity.MONTH:
        return Period(date(d.year, d.month, 1), month_end(d.year, d.month), granularity)
    if granularity is Granularity.QUARTER:
        first_month = 3 * ((d.month - 1) // 3) + 1
        return Period(
            date(d.year, first_month, 1), month_end(d.year, first_month + 2), granularity
        )
    if granularity is Granularity.YEAR:
        return Period(date(d.year, 1, 1), date(d.year, 12, 31), granularity)
    raise ValueError("Use custom_period() for custom ranges.")


def custom_period(start: date | pd.Timestamp | str, end: date | pd.Timestamp | str) -> Period:
    return Period(_to_date(start), _to_date(end), Granularity.CUSTOM)


def comparison_period(current: Period, mode: ComparisonMode) -> Period:
    """The window `current` is compared against."""
    mode = ComparisonMode(mode)
    g = current.granularity

    if mode is ComparisonMode.YEAR_OVER_YEAR:
        if g is Granularity.CUSTOM:
            return Period(shift_years(current.start, -1), shift_years(current.end, -1), g)
        return calendar_period(g, shift_years(current.start, -1))

    # Previous period
    if g is Granularity.MONTH:
        return calendar_period(g, add_months(current.start, -1))
    if g is Granularity.QUARTER:
        return calendar_period(g, add_months(current.start, -3))
    if g is Granularity.YEAR:
        return calendar_period(g, shift_years(current.start, -1))

    months = _months_spanned(current.start, current.end)
    if months is not None:
        start = add_months(current.start, -months)
        prev_end = add_months(current.start, -1)
        return Period(start, month_end(prev_end.year, prev_end.month), g)

    end = current.start - timedelta(days=1)
    return Period(end - timedelta(days=current.days - 1), end, g)


def available_periods(
    data_min: date | pd.Timestamp, data_max: date | pd.Timestamp, granularity: Granularity
) -> list[Period]:
    """Calendar periods touching the data range, most recent first."""
    granularity = Granularity(granularity)
    if granularity is Granularity.CUSTOM:
        raise ValueError("Custom periods are chosen with a date range, not a list.")
    lo, hi = _to_date(data_min), _to_date(data_max)
    periods = []
    current = calendar_period(granularity, lo)
    while current.start <= hi:
        periods.append(current)
        current = calendar_period(granularity, current.end + timedelta(days=1))
    return list(reversed(periods))


def coverage(period: Period, data_min: date | pd.Timestamp, data_max: date | pd.Timestamp) -> Coverage:
    """How much of `period` falls inside the data's date range."""
    lo, hi = _to_date(data_min), _to_date(data_max)
    if period.end < lo or period.start > hi:
        return Coverage.NONE
    if period.start >= lo and period.end <= hi:
        return Coverage.FULL
    return Coverage.PARTIAL


# ------------------------------------------------------------------
# Comparison bundle
# ------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodComparison:
    current: Period
    comparison: Period
    mode: ComparisonMode
    current_coverage: Coverage
    comparison_coverage: Coverage
    current_rows: int
    comparison_rows: int
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def mode_label(self) -> str:
        if self.mode is ComparisonMode.YEAR_OVER_YEAR:
            return YOY_LABEL
        return COMPARISON_LABELS[(self.current.granularity, self.mode)]

    @property
    def label(self) -> str:
        return f"{self.current.label} vs {self.comparison.label} ({self.mode_label})"

    @property
    def is_comparable(self) -> bool:
        """Both windows contain data, so changes can be computed."""
        return self.current_rows > 0 and self.comparison_rows > 0


def compare_periods(
    dates: pd.Series,
    current: Period,
    mode: ComparisonMode = ComparisonMode.PREVIOUS_PERIOD,
    data_range: tuple[date | pd.Timestamp, date | pd.Timestamp] | None = None,
) -> PeriodComparison:
    """Build the comparison window and describe its data coverage.

    `dates` is the order-date column of the (already filtered) dataset and
    drives the row counts. `data_range` is the full dataset's (min, max)
    date; when given, coverage is judged against it so a narrow filter is
    not mistaken for missing history.
    """
    mode = ComparisonMode(mode)
    comp = comparison_period(current, mode)
    dates = pd.to_datetime(dates).dropna()
    warnings: list[str] = []

    if dates.empty:
        cur_cov = comp_cov = Coverage.NONE
        cur_rows = comp_rows = 0
        warnings.append("No data matches the current filters.")
    else:
        lo, hi = (pd.Timestamp(data_range[0]), pd.Timestamp(data_range[1])) if data_range else (dates.min(), dates.max())
        cur_cov, comp_cov = coverage(current, lo, hi), coverage(comp, lo, hi)
        cur_rows = int(current.mask(dates).sum())
        comp_rows = int(comp.mask(dates).sum())

        for name, period, cov, rows in (
            ("Current period", current, cur_cov, cur_rows),
            ("Comparison period", comp, comp_cov, comp_rows),
        ):
            if cov is Coverage.NONE:
                warnings.append(
                    f"{name} ({period.label}) is outside the data range "
                    f"({lo:%d %b %Y} – {hi:%d %b %Y})."
                )
            elif cov is Coverage.PARTIAL:
                warnings.append(
                    f"{name} ({period.label}) is only partly covered by the data "
                    f"({lo:%d %b %Y} – {hi:%d %b %Y}); totals may be understated."
                )
            elif rows == 0:
                warnings.append(f"{name} ({period.label}) has no orders for the current filters.")

    if current.granularity is Granularity.CUSTOM and current.days != comp.days:
        warnings.append(
            f"Windows differ in length ({current.days} vs {comp.days} days); "
            "totals are compared as-is, not scaled per day."
        )

    return PeriodComparison(
        current=current,
        comparison=comp,
        mode=mode,
        current_coverage=cur_cov,
        comparison_coverage=comp_cov,
        current_rows=cur_rows,
        comparison_rows=comp_rows,
        warnings=tuple(warnings),
    )
