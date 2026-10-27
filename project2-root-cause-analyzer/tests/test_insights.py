import re

import pytest

from cause.contribution import additive_contribution, margin_decomposition
from cause.decomposition import RevenueDecomposition, decompose_revenue
from cause.insights import (
    CAUSATION_NOTE,
    Finding,
    contributor_findings,
    driver_finding,
    format_change,
    format_pp,
    format_value,
    generate_findings,
    headline_finding,
    is_significant,
    margin_findings,
    significant_changes,
    top_contributors,
)
from cause.metrics import Metric, MetricChange, compare_kpis, compute_kpis
from tests.hand_example import load_example

CAUSAL_PATTERN = re.compile(r"\b(caused|causes|because|due to|root cause|proves?|confirmed)\b", re.I)


def all_findings():
    _, cur, prev = load_example()
    changes = compare_kpis(compute_kpis(cur), compute_kpis(prev))
    contributions = [
        additive_contribution(cur, prev, "Category", "revenue"),
        additive_contribution(cur, prev, "Category", "profit"),
        additive_contribution(cur, prev, "Category", "orders"),
        margin_decomposition(cur, prev, "Category"),
    ]
    return generate_findings(changes, "Feb 2014 vs Jan 2014 (previous month)",
                             contributions, decompose_revenue(cur, prev))


# ------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------

def test_formatting():
    assert format_value(Metric.REVENUE, -1234.4) == "-$1,234"
    assert format_value(Metric.REVENUE, 1234.6, signed=True) == "+$1,235"
    assert format_value(Metric.MARGIN, 0.1234) == "12.3%"
    assert format_value(Metric.ORDERS, 3.0) == "3"
    assert format_value(Metric.ORDERS, 1.5, signed=True) == "+1.5"
    assert format_change(Metric.MARGIN, -2.5) == "-2.5 pp"
    assert format_pp(float("nan")) == "n/a"


# ------------------------------------------------------------------
# Significance
# ------------------------------------------------------------------

def test_significance_thresholds():
    assert is_significant(MetricChange(Metric.REVENUE, 100, 110))
    assert not is_significant(MetricChange(Metric.REVENUE, 100, 109))
    assert is_significant(MetricChange(Metric.MARGIN, 0.10, 0.09))       # -1.0 pp
    assert not is_significant(MetricChange(Metric.MARGIN, 0.10, 0.095))  # -0.5 pp
    assert is_significant(MetricChange(Metric.PROFIT, -50, 20))          # negative base
    assert not is_significant(MetricChange(Metric.PROFIT, 0, 0))


def test_significant_changes_hand_example():
    _, cur, prev = load_example()
    changes = compare_kpis(compute_kpis(cur), compute_kpis(prev))
    flagged = significant_changes(changes)
    assert Metric.REVENUE in flagged and Metric.MARGIN in flagged
    assert Metric.PROFIT not in flagged   # profit is unchanged at 50


# ------------------------------------------------------------------
# Contributors
# ------------------------------------------------------------------

def test_top_contributors_directions():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Category", "revenue")
    assert top_contributors(res, 3, "negative")["category"].tolist() == ["Furniture"]
    assert top_contributors(res, 3, "positive")["category"].tolist() == ["Office Supplies", "Technology"]
    assert top_contributors(res, 1, "positive")["category"].tolist() == ["Office Supplies"]
    with pytest.raises(ValueError):
        top_contributors(res, 3, "sideways")


def test_contributor_findings_use_computed_numbers():
    _, cur, prev = load_example()
    findings = contributor_findings(additive_contribution(cur, prev, "Category", "revenue"))
    text = " ".join(f.detail for f in findings)
    assert "Furniture -$150 (moved against the net change" in text
    assert "Office Supplies +$200 (200% of the net change)" in text
    assert "Net change: +$100" in text


def test_small_net_change_shows_offset_finding_without_net_shares():
    _, cur, prev = load_example()
    findings = contributor_findings(additive_contribution(cur, prev, "Category", "profit"))
    kinds = {f.category for f in findings}
    assert "offset" in kinds
    assert "of the net change)" not in " ".join(f.detail for f in findings)


def test_order_findings_are_labelled_allocated():
    _, cur, prev = load_example()
    findings = contributor_findings(additive_contribution(cur, prev, "Category", "orders"))
    assert any("orders (allocated)" in f.detail for f in findings)


def test_concentration_finding():
    _, cur, prev = load_example()
    res = additive_contribution(cur, prev, "Customer Segment", "revenue")
    # Corporate -200, Home Office +200, Consumer +100 -> no group >= 50% of gross 500
    assert not any(f.category == "concentration" for f in contributor_findings(res))
    res = additive_contribution(cur, prev, "Region", "revenue")
    # US · Central is the only mover
    assert any(f.category == "concentration" for f in contributor_findings(res))


def test_margin_findings():
    _, cur, prev = load_example()
    (finding,) = margin_findings(margin_decomposition(cur, prev, "Category"))
    assert "12.5%" in finding.detail and "10.0%" in finding.detail
    assert "-2.5 pp" in finding.detail
    assert "Rate effect" in finding.detail and "-0.8 pp" in finding.detail
    assert "Mix effect" in finding.detail and "-1.7 pp" in finding.detail
    assert "revenue shifting" in finding.detail   # mix is the larger component


def test_margin_not_comparable_finding():
    _, cur, prev = load_example()
    (finding,) = margin_findings(margin_decomposition(cur, prev.iloc[0:0], "Category"))
    assert finding.tone == "caution"


def test_driver_finding():
    _, cur, prev = load_example()
    f = driver_finding(decompose_revenue(cur, prev))
    assert "Volume effect: +$183" in f.detail and "order value effect: -$83" in f.detail
    assert "order volume accounts for the larger part" in f.detail
    assert driver_finding(RevenueDecomposition(5, 5, 1, 1)).title == "No revenue change"


def test_headline_finding():
    f = headline_finding(MetricChange(Metric.PROFIT, -100, 50), "Q1 vs Q4")
    assert "n/a: comparison value is negative" in f.detail
    f = headline_finding(MetricChange(Metric.MARGIN, 0.125, 0.10), "Feb vs Jan")
    assert "-2.5 pp" in f.detail and "%" in f.detail


# ------------------------------------------------------------------
# Orchestration and wording
# ------------------------------------------------------------------

def test_generate_findings_order_and_content():
    findings = all_findings()
    assert all(isinstance(f, Finding) for f in findings)
    assert findings[0].category == "headline"
    assert findings[-1].category == "driver"


def test_not_comparable_returns_only_data_notes():
    findings = generate_findings({}, "Jan 2011 vs Dec 2010", comparable=False,
                                 data_notes=["Comparison period is outside the data range."])
    assert [f.category for f in findings] == ["data", "data"]


def test_no_causal_language():
    texts = [f.title + " " + f.detail for f in all_findings()]
    for text in texts:
        assert not CAUSAL_PATTERN.search(text), text
    # The disclaimer itself is the only place causation is discussed.
    assert "not confirmed root causes" in CAUSATION_NOTE
