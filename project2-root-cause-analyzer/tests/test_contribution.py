import math

import numpy as np
import pandas as pd
import pytest

from cause import config
from cause.contribution import (
    additive_contribution,
    allocate_orders,
    contribution_analysis,
    drill_down,
    margin_decomposition,
    reconciliation_checks,
    resolve_dimensions,
)
from cause.metrics import Metric
from tests.hand_example import load_example

TOL = 1e-9


def by(table, column):
    return table.set_index(column)


# ------------------------------------------------------------------
# Dimensions
# ------------------------------------------------------------------

def test_resolve_dimensions_labels_and_columns():
    assert resolve_dimensions("Region") == ["market_region"]
    assert resolve_dimensions(["Customer Segment", "category"]) == ["segment", "category"]


@pytest.mark.parametrize("bad", ["Country", ["Market", "market"], []])
def test_resolve_dimensions_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        resolve_dimensions(bad)


def test_aov_is_not_a_contribution_metric():
    _, cur, prev = load_example()
    with pytest.raises(ValueError, match="ratio"):
        contribution_analysis(cur, prev, "Category", Metric.AOV)


def test_margin_rejected_by_additive_function():
    _, cur, prev = load_example()
    with pytest.raises(ValueError, match="not additive"):
        additive_contribution(cur, prev, "Category", Metric.MARGIN)


# ------------------------------------------------------------------
# Revenue and profit
# ------------------------------------------------------------------

def test_revenue_contribution_hand_example():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", "revenue")
    t = by(res.table, "category")
    assert t.loc["Furniture", "change"] == -150
    assert t.loc["Technology", "change"] == 50
    assert t.loc["Office Supplies", "change"] == 200
    assert (res.total_previous, res.total_current, res.total_change) == (400, 500, 100)
    assert abs(res.reconciliation_error) < TOL
    assert res.shares_reliable
    assert t.loc["Office Supplies", "share_of_net"] == pytest.approx(2.0)
    assert t.loc["Furniture", "share_of_net"] == pytest.approx(-1.5)
    assert t.loc["Furniture", "share_of_gross"] == pytest.approx(-150 / 400)
    assert t.loc["Furniture", "pct_change"] == pytest.approx(-0.5)
    assert math.isnan(t.loc["Office Supplies", "pct_change"])   # new group, no baseline
    # Sorted by size of change
    assert res.table["category"].tolist() == ["Office Supplies", "Furniture", "Technology"]


def test_profit_contribution_with_zero_net_change_suppresses_shares():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", "profit")
    t = by(res.table, "category")
    assert (t.loc["Furniture", "change"], t.loc["Technology", "change"],
            t.loc["Office Supplies", "change"]) == (-25, 10, 15)
    assert res.total_change == 0
    assert abs(res.reconciliation_error) < TOL
    assert not res.shares_reliable
    assert res.table["share_of_net"].isna().all()
    assert t.loc["Furniture", "share_of_gross"] == pytest.approx(-0.5)
    assert any("offset" in n for n in res.notes)


def test_small_net_change_threshold():
    # Net -95 vs gross 205 (46%) keeps shares; net +5 vs gross 305 (1.6%) drops them.
    _, cur, prev = load_example()
    cur = cur.copy()
    cur.loc[cur["category"] == "Office Supplies", "sales"] = 5   # revenue 305 vs 400 (net -95)
    res = additive_contribution(cur, prev, "Category", "revenue")
    assert res.total_change == -95
    assert res.shares_reliable
    cur.loc[cur["category"] == "Office Supplies", "sales"] = 105  # net +5 of gross 205
    res = additive_contribution(cur, prev, "Category", "revenue")
    assert res.total_change == 5 and not res.shares_reliable


def test_negative_profit_groups():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, ["Category", "Customer Segment"], "profit")
    assert abs(res.reconciliation_error) < TOL
    row = res.table[(res.table["category"] == "Technology") & (res.table["segment"] == "Consumer")]
    # previous 10, current -10 + 30 = 20
    assert float(row["change"].iloc[0]) == 10


def test_market_qualified_regions_stay_separate():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Region", "revenue")
    t = by(res.table, "market_region")
    assert set(t.index) == {"US · Central", "EU · Central"}
    assert t.loc["US · Central", "change"] == 100
    assert t.loc["EU · Central", "change"] == 0


def test_missing_dimension_values_are_kept():
    _, cur, prev = load_example()
    cur = cur.copy()
    cur.loc[cur.index[0], "category"] = np.nan
    res = additive_contribution(cur, prev, "Category", "revenue")
    assert config.MISSING_LABEL in set(res.table["category"])
    assert abs(res.reconciliation_error) < TOL


# ------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------

def test_allocated_orders_hand_example():
    _, cur, prev = load_example()
    p = by(allocate_orders(prev, "Category"), "category")
    c = by(allocate_orders(cur, "Category"), "category")
    assert p["allocated_orders"].to_dict() == {"Furniture": 1.5, "Technology": 0.5}
    assert c["allocated_orders"].to_dict() == {"Furniture": 0.5, "Office Supplies": 1.0, "Technology": 1.5}
    assert p["allocated_orders"].sum() == 2 and c["allocated_orders"].sum() == 3
    # Distinct counts overlap and do not add up to the total.
    assert c["distinct_orders"].to_dict() == {"Furniture": 1, "Office Supplies": 1, "Technology": 2}
    assert c["distinct_orders"].sum() == 4


def test_order_contribution_reconciles_and_is_labelled():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", "orders")
    t = by(res.table, "category")
    assert t.loc["Furniture", "change"] == -1
    assert t.loc["Technology", "change"] == 1
    assert t.loc["Office Supplies", "change"] == 1
    assert (res.total_previous, res.total_current) == (2, 3)
    assert abs(res.reconciliation_error) < TOL
    assert "Allocated orders" in res.basis
    assert any("overlap" in n for n in res.notes)
    assert t.loc["Technology", "distinct_orders_current"] == 2


def test_hierarchical_allocation_matches_parent():
    # One order touches (A, s1), (A, s2) and (B, s1).
    df = pd.DataFrame({
        config.ORDER_KEY_COLUMN: ["k1", "k1", "k1", "k2"],
        "category": ["A", "A", "B", "B"],
        "segment": ["s1", "s2", "s1", "s2"],
    })
    pair = allocate_orders(df, ["category", "segment"]).set_index(["category", "segment"])["allocated_orders"]
    assert pair.to_dict() == {("A", "s1"): 0.25, ("A", "s2"): 0.25, ("B", "s1"): 0.5, ("B", "s2"): 1.0}
    assert pair.sum() == 2
    single = allocate_orders(df, "category").set_index("category")["allocated_orders"]
    assert pair.groupby(level=0).sum().to_dict() == single.to_dict() == {"A": 0.5, "B": 1.5}


def test_allocation_on_empty_frame():
    df, _, _ = load_example()
    assert allocate_orders(df.iloc[0:0], "Market").empty


# ------------------------------------------------------------------
# Margin rate / mix
# ------------------------------------------------------------------

def test_margin_decomposition_hand_example():
    _, cur, prev = load_example()
    res = margin_decomposition(cur, prev, "Category")
    assert res.margin_previous == pytest.approx(0.125)
    assert res.margin_current == pytest.approx(0.10)
    assert res.change_pp == pytest.approx(-2.5)
    t = by(res.table, "category")
    expected = {
        "Furniture": (-7.0, -5.25, -1.75),
        "Technology": (1.5, 0.583333333, 0.916666667),
        "Office Supplies": (3.0, 3.0, 0.0),
    }
    for group, (contrib, mix, rate) in expected.items():
        assert t.loc[group, "contribution_pp"] == pytest.approx(contrib)
        assert t.loc[group, "mix_effect_pp"] == pytest.approx(mix)
        assert t.loc[group, "rate_effect_pp"] == pytest.approx(rate, abs=1e-9)
    assert res.rate_effect_pp == pytest.approx(-0.833333333)
    assert res.mix_effect_pp == pytest.approx(-1.666666667)
    assert abs(res.reconciliation_error) < TOL
    assert abs(res.split_error) < TOL
    assert t.loc["Furniture", "margin_change_pp"] == pytest.approx((0.10 - 40 / 300) * 100)
    assert math.isnan(t.loc["Office Supplies", "margin_previous"])
    assert any("no revenue in one period" in n for n in res.notes)


def test_rate_matches_midpoint_formula_when_revenue_in_both_periods():
    _, cur, prev = load_example()
    t = by(margin_decomposition(cur, prev, "Category").table, "category")
    row = t.loc["Technology"]
    midpoint_rate = (
        (row["margin_current"] - row["margin_previous"])
        * (row["revenue_share_previous"] + row["revenue_share_current"]) / 2 * 100
    )
    assert row["rate_effect_pp"] == pytest.approx(midpoint_rate)


def test_margin_with_zero_revenue_period_is_not_comparable():
    _, cur, prev = load_example()
    res = margin_decomposition(cur, prev.iloc[0:0], "Category")
    assert not res.comparable
    assert math.isnan(res.change_pp)
    assert any("undefined" in n for n in res.notes)
    assert res.reconciliation_error == 0.0


def test_margin_group_with_profit_but_no_revenue():
    # A zero-sales line with a loss (exists in the real data).
    _, cur, prev = load_example()
    cur = cur.copy()
    cur.loc[cur["category"] == "Office Supplies", "sales"] = 0
    res = margin_decomposition(cur, prev, "Category")
    assert res.comparable
    assert abs(res.reconciliation_error) < TOL
    assert abs(res.split_error) < TOL


def test_margin_uses_negative_profit_correctly():
    _, cur, prev = load_example()
    cur = cur.copy()
    cur["profit"] = -cur["profit"]
    res = margin_decomposition(cur, prev, "Market")
    assert res.margin_current == pytest.approx(-0.10)
    assert res.change_pp == pytest.approx(-22.5)
    assert abs(res.reconciliation_error) < TOL


# ------------------------------------------------------------------
# Empty periods
# ------------------------------------------------------------------

def test_empty_previous_period():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev.iloc[0:0], "Category", "revenue")
    assert res.total_previous == 0 and res.total_change == 500
    assert abs(res.reconciliation_error) < TOL
    assert res.table["pct_change"].isna().all()
    assert any("comparison period has no data" in n for n in res.notes)


def test_both_periods_empty():
    _, cur, prev = load_example()
    for metric in ("revenue", "profit", "orders"):
        res = additive_contribution(cur.iloc[0:0], prev.iloc[0:0], "Market", metric)
        assert res.table.empty and res.total_change == 0 and res.reconciliation_error == 0


# ------------------------------------------------------------------
# Drill-down
# ------------------------------------------------------------------

@pytest.mark.parametrize("metric", ["revenue", "profit", "orders"])
def test_two_dimension_table_reconciles_to_single_dimension(metric):
    _, cur, prev = load_example()
    single = by(additive_contribution(cur, prev, "Category", metric).table, "category")["change"]
    pair = additive_contribution(cur, prev, ["Category", "Customer Segment"], metric)
    assert abs(pair.reconciliation_error) < TOL
    rolled = pair.table.groupby("category")["change"].sum()
    pd.testing.assert_series_equal(rolled.sort_index(), single.sort_index(), check_names=False)


@pytest.mark.parametrize("metric", ["revenue", "profit", "orders"])
def test_drill_down_reconciles_to_parent_row(metric):
    _, cur, prev = load_example()
    parent = by(additive_contribution(cur, prev, "Market", metric).table, "market")
    child = drill_down(cur, prev, "Market", "US", "Category", metric)
    assert child.total_change == pytest.approx(parent.loc["US", "change"])
    assert abs(child.reconciliation_error) < TOL
    assert "market" not in child.table.columns


def test_drill_down_margin_within_parent():
    _, cur, prev = load_example()
    res = drill_down(cur, prev, "Market", "US", "Category", "margin")
    # US: previous 30/200 = 15%, current 35/300 = 11.67%
    assert res.margin_previous == pytest.approx(0.15)
    assert res.margin_current == pytest.approx(35 / 300)
    assert abs(res.reconciliation_error) < TOL


def test_drill_down_unknown_parent():
    _, cur, prev = load_example()
    with pytest.raises(ValueError, match="no data"):
        drill_down(cur, prev, "Market", "Mars", "Category", "revenue")


def test_reconciliation_checks_all_zero():
    _, cur, prev = load_example()
    checks = reconciliation_checks(cur, prev)
    assert len(checks) == (4 + 6) * 4
    assert checks["reconciliation_error"].abs().max() < TOL
    assert checks["rate_mix_error"].abs().max() < TOL
