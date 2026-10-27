"""Checks against the real Global Superstore file.

Skipped when the dataset is not available. These assert structural
properties only, never specific business figures.
"""

import pytest

from cause import config
from cause.data import DataSourceError, count_orders, load_dataset, resolve_data_path

try:
    resolve_data_path()
    HAVE_DATA = True
except DataSourceError:
    HAVE_DATA = False

pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="Global Superstore dataset not found")


@pytest.fixture(scope="module")
def loaded():
    return load_dataset()


def test_loads_without_errors(loaded):
    assert loaded.report.ok
    assert loaded.report.row_count == len(loaded.data) > 0


def test_composite_key_is_consistent(loaded):
    check = loaded.report.order_key
    assert check.is_consistent, check.inconsistent_attributes
    assert check.distinct_order_keys >= check.distinct_order_ids
    assert count_orders(loaded.data) == check.distinct_order_keys
    assert check.order_rows > check.distinct_order_keys


def test_market_region_labels_are_unique_per_market(loaded):
    df = loaded.data
    per_label = df.groupby(config.MARKET_REGION_COLUMN)["market"].nunique()
    assert (per_label == 1).all()


def test_all_dimensions_present(loaded):
    for column in config.DIMENSIONS.values():
        assert column in loaded.data.columns
        assert loaded.data[column].notna().all()


def test_contributions_reconcile_on_real_data(loaded):
    from cause.contribution import reconciliation_checks
    from cause.decomposition import decompose_revenue
    from cause.metrics import period_frames
    from cause.periods import ComparisonMode, Granularity, calendar_period, compare_periods

    df = loaded.data
    comparison = compare_periods(
        df["order_date"], calendar_period(Granularity.YEAR, loaded.report.date_max),
        ComparisonMode.PREVIOUS_PERIOD,
    )
    current, previous = period_frames(df, comparison)
    checks = reconciliation_checks(current, previous)
    scale = max(1.0, float(df["sales"].abs().sum()))
    assert checks["reconciliation_error"].abs().max() < 1e-9 * scale
    assert checks["rate_mix_error"].abs().max() < 1e-9
    assert abs(decompose_revenue(current, previous).residual) < 1e-9 * scale
