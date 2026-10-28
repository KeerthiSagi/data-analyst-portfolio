import math

import numpy as np
import pandas as pd
import pytest

from cause.contribution import additive_contribution, margin_decomposition
from cause.decomposition import RevenueDecomposition, decompose_revenue, decompose_revenue_by
from cause.metrics import KPIs, Metric, MetricChange, compare_kpis, compute_kpis
from ui.chart_data import (
    contribution_display,
    driver_display,
    driver_effects_long,
    driver_waterfall_steps,
    group_performance,
    kpi_display,
    loss_making,
    margin_display,
    margin_effects_long,
    waterfall_gap,
    waterfall_steps,
)
from tests.hand_example import load_example


def changes():
    _, cur, prev = load_example()
    return compare_kpis(compute_kpis(cur), compute_kpis(prev))


# ------------------------------------------------------------------
# KPI cards
# ------------------------------------------------------------------

def test_kpi_display_revenue():
    k = kpi_display(changes()[Metric.REVENUE], "Jan 2014", "Total revenue")
    assert (k.label, k.value, k.delta, k.tone) == ("Total revenue", "$500", "+$100 (+25.0%)", "positive")
    assert k.footnote == "$400 in Jan 2014"
    assert k.flagged


def test_kpi_display_margin_uses_pp():
    k = kpi_display(changes()[Metric.MARGIN], "Jan 2014")
    assert (k.value, k.delta, k.tone) == ("10.0%", "-2.5 pp", "negative")
    assert k.footnote == "12.5% in Jan 2014"


def test_kpi_display_flat_profit_not_flagged():
    k = kpi_display(changes()[Metric.PROFIT], "Jan 2014")
    assert k.delta == "$0 (0.0%)" and k.tone == "neutral" and not k.flagged


def test_kpi_display_negative_baseline():
    k = kpi_display(MetricChange(Metric.PROFIT, -200, 100), "Q1")
    assert k.delta == "+$300 (% change n/a)" and k.tone == "positive"


def test_kpi_display_zero_revenue_margin():
    k = kpi_display(compare_kpis(KPIs(0, 0, 0, 0), KPIs(100, 10, 1, 1))[Metric.MARGIN], "Q1")
    assert k.value == "n/a" and k.tone == "caution"


# ------------------------------------------------------------------
# Group performance
# ------------------------------------------------------------------

def test_group_performance_hand_example():
    _, cur, prev = load_example()
    t = group_performance(cur, prev, "category").set_index("category")
    assert t.index.tolist() == ["Office Supplies", "Furniture", "Technology"] or \
        t["revenue_current"].is_monotonic_decreasing
    assert t.loc["Furniture", "revenue_current"] == 150 and t.loc["Furniture", "revenue_previous"] == 300
    assert t.loc["Furniture", "margin_current"] == pytest.approx(0.10)
    assert t.loc["Furniture", "margin_change_pp"] == pytest.approx((0.10 - 40 / 300) * 100)
    assert t.loc["Furniture", "revenue_pct_change"] == pytest.approx(-0.5)
    assert math.isnan(t.loc["Office Supplies", "margin_previous"])   # no revenue then
    assert math.isnan(t.loc["Office Supplies", "revenue_pct_change"])


def test_group_performance_empty():
    df, _, _ = load_example()
    assert group_performance(df.iloc[0:0], df.iloc[0:0], "market").empty


def test_loss_making():
    _, cur, _ = load_example()
    cur = cur.copy()
    assert loss_making(cur, "category").empty
    cur.loc[cur["category"] == "Technology", "profit"] = -40
    out = loss_making(cur, "category")
    assert out["category"].tolist() == ["Technology"] and out["profit"].iloc[0] == -80


# ------------------------------------------------------------------
# Contribution tables and waterfalls
# ------------------------------------------------------------------

@pytest.mark.parametrize("metric", ["revenue", "profit", "orders"])
def test_waterfall_reconciles(metric):
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", metric)
    steps = waterfall_steps(res)
    assert steps["measure"].tolist()[0] == "absolute" and steps["measure"].tolist()[-1] == "total"
    assert steps["value"].iloc[0] == res.total_previous
    assert steps["value"].iloc[-1] == res.total_current
    assert abs(waterfall_gap(steps)) < 1e-9


def test_waterfall_folds_small_groups_into_other():
    # 4 groups with max_groups=2 -> 2 kept + "Other (2 groups)"
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, ["Category", "Customer Segment"], "revenue")
    assert len(res.table) == 4
    steps = waterfall_steps(res, max_groups=2)
    labels = steps["label"].tolist()
    assert labels[-2] == "Other (2 groups)" and len(steps) == 5
    assert abs(waterfall_gap(steps)) < 1e-9


def test_waterfall_does_not_fold_a_single_extra_group():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", "revenue")   # 3 groups
    assert not any(steps.startswith("Other") for steps in waterfall_steps(res, max_groups=2)["label"])


def test_contribution_display_percent_units_and_actual_orders():
    _, cur, prev = load_example()
    t = contribution_display(additive_contribution(cur, prev, "Category", "orders")).set_index("Group")
    assert t.loc["Furniture", "Change"] == -1
    assert t.loc["Technology", "Actual orders (current)"] == 2
    rev = contribution_display(additive_contribution(cur, prev, "Category", "revenue")).set_index("Group")
    assert rev.loc["Office Supplies", "% of net change"] == pytest.approx(200.0)
    assert rev.loc["Furniture", "% change"] == pytest.approx(-50.0)


def test_margin_display_and_effects():
    _, cur, prev = load_example()
    res = margin_decomposition(cur, prev, "Category")
    t = margin_display(res).set_index("Group")
    assert t.loc["Furniture", "Contribution (pp)"] == pytest.approx(-7.0)
    assert t.loc["Furniture", "Margin (current) %"] == pytest.approx(10.0)
    long = margin_effects_long(res)
    assert set(long["effect"]) == {"Rate effect", "Mix effect"}
    assert long["value"].sum() == pytest.approx(res.change_pp)
    furn = long[long["group"] == "Furniture"].set_index("effect")["value"]
    assert furn["Rate effect"] == pytest.approx(-1.75) and furn["Mix effect"] == pytest.approx(-5.25)


# ------------------------------------------------------------------
# Revenue drivers
# ------------------------------------------------------------------

def test_driver_waterfall_reconciles():
    _, cur, prev = load_example()
    steps = driver_waterfall_steps(decompose_revenue(cur, prev))
    assert steps["label"].tolist() == ["Previous revenue", "Order volume effect", "Order value effect", "Current revenue"]
    assert steps["value"].tolist()[0] == 400 and steps["value"].tolist()[-1] == 500
    assert abs(waterfall_gap(steps)) < 1e-9


def test_driver_waterfall_with_no_previous_orders():
    steps = driver_waterfall_steps(RevenueDecomposition(0, 300, 0, 3))
    assert steps["value"].tolist() == [0, 300, 0, 300]
    assert abs(waterfall_gap(steps)) < 1e-9


def test_driver_display_and_long():
    _, cur, prev = load_example()
    table = decompose_revenue_by(cur, prev, "Category")
    disp = driver_display(table, "category").set_index("Group")
    assert disp.loc["Technology", "Volume effect"] == pytest.approx(87.5)
    assert disp.loc["Technology", "AOV effect"] == pytest.approx(-37.5)
    long = driver_effects_long(table, "category")
    assert len(long) == 2 * len(table)
    per_group = long.groupby("group")["value"].sum()
    assert per_group["Technology"] == pytest.approx(50)
