import math

import pandas as pd
import pytest

from cause.metrics import (
    KPIs,
    Metric,
    MetricChange,
    compare_kpis,
    compute_kpis,
    margin_of,
    monthly_trend,
    pct_change,
    pct_change_note,
    period_frames,
    safe_divide,
    safe_divide_array,
)
from cause.periods import ComparisonMode, Granularity, calendar_period, compare_periods
from tests.hand_example import load_example


# ------------------------------------------------------------------
# Safe arithmetic
# ------------------------------------------------------------------

def test_safe_divide():
    assert safe_divide(10, 4) == 2.5
    assert math.isnan(safe_divide(10, 0))
    assert math.isnan(safe_divide(10, float("nan")))
    assert math.isnan(safe_divide(None, 5))


def test_safe_divide_array():
    out = safe_divide_array([10, 5, 3], [2, 0, float("nan")])
    assert out[0] == 5 and math.isnan(out[1]) and math.isnan(out[2])


def test_margin_handles_zero_and_negative_revenue_and_negative_profit():
    assert margin_of(-30, 100) == pytest.approx(-0.30)
    assert math.isnan(margin_of(5, 0))
    assert math.isnan(margin_of(5, -10))


@pytest.mark.parametrize(
    "previous, current, expected, note",
    [
        (100, 150, 0.5, None),
        (100, -50, -1.5, None),
        (0, 50, math.nan, "n/a: comparison value is zero"),
        (-100, -50, math.nan, "n/a: comparison value is negative"),
        (float("nan"), 5, math.nan, "n/a: no comparison value"),
    ],
)
def test_pct_change_baselines(previous, current, expected, note):
    result = pct_change(previous, current)
    assert (math.isnan(result) and math.isnan(expected)) or result == pytest.approx(expected)
    assert pct_change_note(previous) == note


# ------------------------------------------------------------------
# KPIs (hand example)
# ------------------------------------------------------------------

def test_kpis_hand_example():
    _, current, previous = load_example()
    prev, cur = compute_kpis(previous), compute_kpis(current)
    assert (prev.revenue, prev.profit, prev.orders, prev.order_rows) == (400, 50, 2, 3)
    assert (cur.revenue, cur.profit, cur.orders, cur.order_rows) == (500, 50, 3, 4)
    assert prev.aov == pytest.approx(200)
    assert cur.aov == pytest.approx(500 / 3)
    assert prev.margin == pytest.approx(0.125)
    assert cur.margin == pytest.approx(0.10)


def test_orders_use_composite_key_not_order_id():
    _, current, _ = load_example()
    # O-2 in February is a different customer from O-2 in January.
    df, _, _ = load_example()
    assert df["order_id"].nunique() == 4
    assert compute_kpis(df).orders == 5
    assert compute_kpis(current).orders == 3


def test_margin_is_weighted_not_averaged():
    _, current, _ = load_example()
    group_margins = current.groupby("category").apply(
        lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False
    )
    assert compute_kpis(current).margin == pytest.approx(0.10)
    assert group_margins.mean() != pytest.approx(0.10)


def test_empty_kpis():
    df, _, _ = load_example()
    k = compute_kpis(df.iloc[0:0])
    assert (k.revenue, k.profit, k.orders, k.order_rows) == (0, 0, 0, 0)
    assert k.is_empty and math.isnan(k.aov) and math.isnan(k.margin)


# ------------------------------------------------------------------
# Changes
# ------------------------------------------------------------------

def test_compare_kpis_hand_example():
    _, current, previous = load_example()
    changes = compare_kpis(compute_kpis(current), compute_kpis(previous))
    rev = changes[Metric.REVENUE]
    assert rev.absolute_change == 100 and rev.pct_change == pytest.approx(0.25)
    assert math.isnan(rev.pp_change)
    margin = changes[Metric.MARGIN]
    assert margin.pp_change == pytest.approx(-2.5)
    assert math.isnan(margin.pct_change)            # never a % change for margin
    assert changes[Metric.PROFIT].direction == "flat"
    assert changes[Metric.ORDERS].pct_change == pytest.approx(0.5)
    assert changes[Metric.AOV].absolute_change == pytest.approx(500 / 3 - 200)


def test_change_from_negative_profit_baseline():
    change = MetricChange(Metric.PROFIT, previous=-200, current=100)
    assert change.absolute_change == 300
    assert math.isnan(change.pct_change)
    assert change.unavailable_note == "n/a: comparison value is negative"
    assert change.direction == "up"


def test_margin_change_when_revenue_was_zero():
    changes = compare_kpis(KPIs(100, 10, 1, 1), KPIs(0, 0, 0, 0))
    margin = changes[Metric.MARGIN]
    assert math.isnan(margin.pp_change)
    assert "undefined" in margin.unavailable_note
    assert changes[Metric.REVENUE].unavailable_note == "n/a: comparison value is zero"


def test_metric_properties():
    assert Metric.REVENUE.is_additive and Metric.ORDERS.is_additive
    assert not Metric.MARGIN.is_additive and not Metric.AOV.is_additive
    assert Metric.MARGIN.is_percentage and not Metric.AOV.is_percentage


# ------------------------------------------------------------------
# Period frames and trends
# ------------------------------------------------------------------

def test_period_frames():
    df, current, previous = load_example()
    comparison = compare_periods(
        df["order_date"], calendar_period(Granularity.MONTH, "2014-02-01"), ComparisonMode.PREVIOUS_PERIOD
    )
    cur, prev = period_frames(df, comparison)
    assert len(cur) == len(current) == 4 and len(prev) == len(previous) == 3


def test_monthly_trend_keeps_gap_months():
    df, _, _ = load_example()
    april = df.iloc[[0]].assign(order_date=pd.Timestamp("2014-04-03"))
    trend = monthly_trend(pd.concat([df, april]))
    assert trend["month"].dt.month.tolist() == [1, 2, 3, 4]
    march = trend.iloc[2]
    assert march["revenue"] == 0 and march["orders"] == 0
    assert math.isnan(march["margin"]) and math.isnan(march["aov"])
    jan = trend.iloc[0]
    assert (jan["revenue"], jan["orders"], jan["margin"]) == (400, 2, pytest.approx(0.125))


def test_monthly_orders_add_up_to_total():
    df, _, _ = load_example()
    assert monthly_trend(df)["orders"].sum() == compute_kpis(df).orders


def test_monthly_trend_empty():
    df, _, _ = load_example()
    assert monthly_trend(df.iloc[0:0]).empty
