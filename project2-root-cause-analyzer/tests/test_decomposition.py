import math

import pytest

from cause.decomposition import RevenueDecomposition, decompose_revenue, decompose_revenue_by
from tests.hand_example import load_example


def test_hand_example():
    _, cur, prev = load_example()
    d = decompose_revenue(cur, prev)
    assert (d.orders_previous, d.orders_current) == (2, 3)
    assert d.aov_previous == pytest.approx(200)
    assert d.aov_current == pytest.approx(500 / 3)
    assert d.volume_effect == pytest.approx(183.3333333)
    assert d.aov_effect == pytest.approx(-83.3333333)
    assert d.revenue_change == 100
    assert abs(d.residual) < 1e-9
    assert d.dominant_driver == "volume"


@pytest.mark.parametrize(
    "r0, n0, r1, n1",
    [
        (1_072_895.0, 2203, 1_481_251.0, 2994),
        (500.0, 4, 480.0, 6),
        (100.0, 10, 100.0, 10),
        (0.1, 1, 1e9, 123_457),
    ],
)
def test_exact_reconciliation(r0, n0, r1, n1):
    d = RevenueDecomposition(r0, r1, n0, n1)
    assert d.volume_effect + d.aov_effect == pytest.approx(r1 - r0, rel=1e-12, abs=1e-9)


def test_symmetric_when_periods_swap():
    a = RevenueDecomposition(400, 500, 2, 3)
    b = RevenueDecomposition(500, 400, 3, 2)
    assert a.volume_effect == pytest.approx(-b.volume_effect)
    assert a.aov_effect == pytest.approx(-b.aov_effect)


def test_no_orders_in_previous_period():
    d = RevenueDecomposition(0, 300, 0, 3)
    assert math.isnan(d.aov_previous)
    assert d.volume_effect == 300 and d.aov_effect == 0 and d.residual == 0
    assert any("comparison period has no orders" in n for n in d.notes)


def test_no_orders_in_current_period():
    d = RevenueDecomposition(300, 0, 3, 0)
    assert d.volume_effect == -300 and d.aov_effect == 0 and d.residual == 0
    assert any("current period has no orders" in n for n in d.notes)


def test_no_orders_either_period():
    d = RevenueDecomposition(0, 0, 0, 0)
    assert d.volume_effect == 0 and d.aov_effect == 0 and d.dominant_driver is None


def test_empty_frames():
    _, cur, prev = load_example()
    d = decompose_revenue(cur, prev.iloc[0:0])
    assert d.revenue_change == 500 and d.volume_effect == 500 and abs(d.residual) < 1e-9


def test_by_dimension_rows_reconcile_and_sum_to_total_revenue_change():
    _, cur, prev = load_example()
    t = decompose_revenue_by(cur, prev, "Category").set_index("category")
    assert ((t["volume_effect"] + t["aov_effect"] - t["revenue_change"]).abs() < 1e-9).all()
    assert t["revenue_change"].sum() == 100
    # Technology: previous 100 over 1 order, current 150 over 2 orders.
    assert t.loc["Technology", "orders_previous"] == 1
    assert t.loc["Technology", "orders_current"] == 2
    assert t.loc["Technology", "volume_effect"] == pytest.approx(1 * (100 + 75) / 2)
    assert t.loc["Technology", "aov_effect"] == pytest.approx(-25 * 1.5)
    # Office Supplies is new: the whole change is volume.
    assert t.loc["Office Supplies", "volume_effect"] == 200
    assert math.isnan(t.loc["Office Supplies", "aov_previous"])
