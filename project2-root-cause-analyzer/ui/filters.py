"""Shared filter and period-selection logic (no Streamlit imports, so it is testable).

Conventions
-----------
* An empty multiselect means "no restriction" (all values). The UI says so
  explicitly ("All markets") so this is never a silent choice.
* Region options follow the selected markets. If a region is selected and
  its market is later deselected, the region is NOT removed; it is kept,
  reported as conflicting, and matches no rows until the user changes one
  of the two selections.
* Current and comparison periods are cut from the same filtered frame, so
  both always use identical dimension filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from cause import config
from cause.periods import (
    ComparisonMode,
    Granularity,
    Period,
    PeriodComparison,
    available_periods,
    calendar_period,
    compare_periods,
    custom_period,
)

# Filter name -> (data column, plural label for "All ...")
FILTERS: dict[str, tuple[str, str]] = {
    "Market": ("market", "markets"),
    "Region": (config.MARKET_REGION_COLUMN, "regions"),
    "Category": ("category", "categories"),
    "Customer Segment": ("segment", "segments"),
}

GRANULARITY_LABELS = {
    Granularity.MONTH: "Month",
    Granularity.QUARTER: "Quarter",
    Granularity.YEAR: "Year",
    Granularity.CUSTOM: "Custom",
}
COMPARISON_LABELS = {
    ComparisonMode.PREVIOUS_PERIOD: "Previous period",
    ComparisonMode.YEAR_OVER_YEAR: "Same period last year",
}


# ------------------------------------------------------------------
# Dimension filters
# ------------------------------------------------------------------

@dataclass(frozen=True)
class FilterSelection:
    markets: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    segments: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, tuple[str, ...]]:
        return {
            "Market": self.markets,
            "Region": self.regions,
            "Category": self.categories,
            "Customer Segment": self.segments,
        }

    @property
    def is_unfiltered(self) -> bool:
        return not any(self.as_dict().values())


def options_for(df: pd.DataFrame, filter_name: str) -> list[str]:
    column = FILTERS[filter_name][0]
    return sorted(df[column].dropna().unique().tolist())


def region_options(
    df: pd.DataFrame, markets: tuple[str, ...] | list[str], selected_regions=()
) -> tuple[list[str], list[str]]:
    """(options to show, selected regions that conflict with the markets).

    Options are the regions inside the selected markets (all regions when no
    market is selected), plus any already-selected region that falls outside
    them, so the user's choice is kept rather than silently dropped.
    """
    col = config.MARKET_REGION_COLUMN
    scope = df if not markets else df[df["market"].isin(markets)]
    in_scope = sorted(scope[col].dropna().unique().tolist())
    conflicting = [r for r in selected_regions if r not in in_scope]
    return in_scope + sorted(conflicting), conflicting


def apply_filters(df: pd.DataFrame, selection: FilterSelection) -> pd.DataFrame:
    """Rows matching every non-empty filter."""
    mask = pd.Series(True, index=df.index)
    for name, values in selection.as_dict().items():
        if values:
            mask &= df[FILTERS[name][0]].isin(values)
    return df[mask]


def selection_warnings(df: pd.DataFrame, selection: FilterSelection) -> list[str]:
    warnings = []
    _, conflicting = region_options(df, selection.markets, selection.regions)
    if conflicting:
        warnings.append(
            "Selected region(s) outside the selected markets match no data: "
            + ", ".join(conflicting)
            + ". Remove them or add their market."
        )
    if apply_filters(df, selection).empty:
        warnings.append("No orders match the current filters. Widen or reset the filters.")
    return warnings


def summarize_selection(selection: FilterSelection, max_items: int = 3) -> list[tuple[str, str]]:
    """[(filter name, readable value)] for display, e.g. ("Market", "EU, US")."""
    out = []
    for name, values in selection.as_dict().items():
        plural = FILTERS[name][1]
        if not values:
            text = f"All {plural}"
        elif len(values) <= max_items:
            text = ", ".join(values)
        else:
            text = ", ".join(values[:max_items]) + f" +{len(values) - max_items} more"
        out.append((name, text))
    return out


# ------------------------------------------------------------------
# Period selection
# ------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodChoice:
    """Result of reading the period controls.

    `period` is None when the controls are incomplete (e.g. a custom range
    with only a start date); `message` then says what is missing.
    """

    granularity: Granularity
    mode: ComparisonMode
    period: Period | None
    message: str | None = None


def period_options(data_min, data_max, granularity: Granularity) -> list[Period]:
    """Calendar periods available for a granularity, most recent first."""
    return available_periods(data_min, data_max, granularity)


def default_period(data_min, data_max, granularity: Granularity) -> Period:
    """Most recent period that is fully inside the data."""
    periods = period_options(data_min, data_max, granularity)
    lo, hi = pd.Timestamp(data_min).date(), pd.Timestamp(data_max).date()
    for p in periods:
        if p.start >= lo and p.end <= hi:
            return p
    return periods[0]


def custom_choice(value, mode: ComparisonMode) -> PeriodChoice:
    """Interpret a st.date_input range value."""
    if isinstance(value, (list, tuple)):
        dates = [d for d in value if d is not None]
    elif value is None:
        dates = []
    else:
        dates = [value]
    if len(dates) < 2:
        return PeriodChoice(
            Granularity.CUSTOM, mode, None, "Choose both a start and an end date for the custom range."
        )
    start, end = dates[0], dates[1]
    if end < start:
        return PeriodChoice(Granularity.CUSTOM, mode, None, "The end date is before the start date.")
    return PeriodChoice(Granularity.CUSTOM, mode, custom_period(start, end))


def calendar_choice(granularity: Granularity, start_iso: str | None, mode: ComparisonMode) -> PeriodChoice:
    if not start_iso:
        return PeriodChoice(granularity, mode, None, "Choose a period.")
    return PeriodChoice(granularity, mode, calendar_period(granularity, date.fromisoformat(start_iso)))


# ------------------------------------------------------------------
# Combined context
# ------------------------------------------------------------------

@dataclass
class AnalysisContext:
    """Everything a page needs, built once per run by the app shell."""

    data: pd.DataFrame                  # full validated dataset
    filtered: pd.DataFrame              # after dimension filters
    selection: FilterSelection
    choice: PeriodChoice
    comparison: PeriodComparison | None
    current: pd.DataFrame
    previous: pd.DataFrame
    data_range: tuple[pd.Timestamp, pd.Timestamp]
    warnings: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """A period is chosen (the comparison may still be empty)."""
        return self.comparison is not None

    @property
    def is_comparable(self) -> bool:
        return self.comparison is not None and self.comparison.is_comparable


def build_context(
    data: pd.DataFrame, selection: FilterSelection, choice: PeriodChoice
) -> AnalysisContext:
    """Apply filters, then cut current and comparison windows from the same rows."""
    data_range = (data["order_date"].min(), data["order_date"].max())
    filtered = apply_filters(data, selection)
    warnings = selection_warnings(data, selection)
    empty = filtered.iloc[0:0]

    if choice.period is None:
        if choice.message:
            warnings.append(choice.message)
        return AnalysisContext(data, filtered, selection, choice, None, empty, empty, data_range, warnings)

    comparison = compare_periods(filtered["order_date"], choice.period, choice.mode, data_range=data_range)
    current = filtered[comparison.current.mask(filtered["order_date"])]
    previous = filtered[comparison.comparison.mask(filtered["order_date"])]
    # Avoid repeating "no orders match filters" from both sources.
    for w in comparison.warnings:
        if w not in warnings and not (filtered.empty and w.startswith("No data matches")):
            warnings.append(w)
    return AnalysisContext(
        data, filtered, selection, choice, comparison, current, previous, data_range, warnings
    )
