import io
from datetime import datetime

import pandas as pd
import pytest

from cause.metrics import Metric
from cause.report import (
    InvestigationSettings,
    contribution_frame,
    findings_frame,
    investigation_contribution_frame,
    kpi_comparison_frame,
    report_markdown,
    run_investigation,
    to_csv_bytes,
)
from tests.hand_example import load_example
from tests.test_insights import CAUSAL_PATTERN

LABEL = "Feb 2014 vs Jan 2014 (previous month)"


def run(metric=Metric.REVENUE, primary="category", secondary=None, parent=None):
    _, cur, prev = load_example()
    return run_investigation(cur, prev, InvestigationSettings(metric, primary, secondary, parent), LABEL)


def roundtrip(frame):
    return pd.read_csv(io.BytesIO(to_csv_bytes(frame)))


# ------------------------------------------------------------------
# Settings and investigation
# ------------------------------------------------------------------

def test_settings_validation():
    with pytest.raises(ValueError):
        InvestigationSettings(Metric.AOV, "category")
    with pytest.raises(ValueError):
        InvestigationSettings(Metric.REVENUE, "category", "category")


def test_run_investigation_main_and_findings():
    r = run()
    assert r.main.total_change == 100
    assert r.drill is None and r.combinations is None
    assert r.headline.metric is Metric.REVENUE
    assert r.findings[0].finding.category == "headline" and r.findings[0].metric == "Revenue"
    assert any(f.finding.category == "driver" for f in r.findings)
    assert all(not CAUSAL_PATTERN.search(f.finding.detail) for f in r.findings)


def test_run_investigation_drill_down():
    r = run(primary="market", secondary="category", parent="US")
    assert r.drill is not None and r.drill_scope == "Market = US → Category"
    us_change = r.main.table.set_index("market").loc["US", "change"]
    assert r.drill.total_change == pytest.approx(us_change)
    assert any(f.scope == r.drill_scope for f in r.findings)


def test_run_investigation_unknown_parent_reports_error():
    r = run(primary="market", secondary="category", parent="Mars")
    assert r.drill is None and "no data" in r.drill_error


def test_run_investigation_combinations():
    r = run(primary="market", secondary="category")
    assert r.combinations is not None
    assert abs(r.combinations.reconciliation_error) < 1e-9


def test_run_investigation_margin():
    r = run(metric=Metric.MARGIN)
    assert r.main.change_pp == pytest.approx(-2.5)
    assert any(f.finding.category == "margin" for f in r.findings)
    assert not any(f.finding.category == "driver" for f in r.findings)


# ------------------------------------------------------------------
# CSV exports
# ------------------------------------------------------------------

def test_kpi_csv_values_and_types():
    out = roundtrip(kpi_comparison_frame(run().changes)).set_index("metric")
    assert list(out.columns) == ["unit", "previous_value", "current_value", "absolute_change",
                                 "pct_change", "pp_change", "note"]
    assert out.loc["Revenue", "previous_value"] == 400 and out.loc["Revenue", "current_value"] == 500
    assert out.loc["Revenue", "pct_change"] == pytest.approx(25.0)
    assert out.loc["Orders", "absolute_change"] == 1
    assert out.loc["Profit Margin", "previous_value"] == pytest.approx(12.5)
    assert out.loc["Profit Margin", "pp_change"] == pytest.approx(-2.5)
    assert pd.isna(out.loc["Profit Margin", "pct_change"])
    for col in ["previous_value", "current_value", "absolute_change", "pct_change", "pp_change"]:
        assert pd.api.types.is_numeric_dtype(out[col])


def test_contribution_csv_matches_engine():
    r = run()
    out = roundtrip(contribution_frame(r.main)).set_index("group")
    assert out.loc["Furniture", "contribution"] == -150
    assert out.loc["Office Supplies", "share_of_net_change_pct"] == pytest.approx(200.0)
    assert out.loc["Furniture", "share_of_total_movement_pct"] == pytest.approx(-37.5)
    assert out["contribution"].sum() == pytest.approx(r.main.total_change)
    assert set(out["dimension"]) == {"Category"} and set(out["metric"]) == {"Revenue"}
    assert pd.api.types.is_numeric_dtype(out["contribution"])


def test_orders_csv_labels_allocation():
    out = roundtrip(contribution_frame(run(metric=Metric.ORDERS).main)).set_index("group")
    assert "Allocated" in out["basis"].iloc[0]
    assert out.loc["Technology", "distinct_orders_current"] == 2
    assert out["contribution"].sum() == pytest.approx(1)


def test_margin_csv_columns():
    out = roundtrip(contribution_frame(run(metric=Metric.MARGIN).main)).set_index("group")
    assert out.loc["Furniture", "contribution_pp"] == pytest.approx(-7.0)
    assert out.loc["Furniture", "rate_effect_pp"] == pytest.approx(-1.75)
    assert out["contribution_pp"].sum() == pytest.approx(-2.5)
    assert "contribution" not in out.columns   # no unlabelled sums of margins


def test_investigation_csv_stacks_scopes():
    r = run(primary="market", secondary="category", parent="US")
    out = roundtrip(investigation_contribution_frame(r))
    assert set(out["scope"]) == {"All groups", "Market = US → Category"}


def test_findings_csv():
    r = run()
    out = roundtrip(findings_frame(r.findings))
    assert list(out.columns) == ["finding_type", "tone", "title", "finding_text", "metric", "scope"]
    assert len(out) == len(r.findings)
    assert "Category" in set(out["scope"])


def test_findings_csv_empty():
    assert list(findings_frame([]).columns)[:2] == ["finding_type", "tone"]


# ------------------------------------------------------------------
# Readable report
# ------------------------------------------------------------------

def test_report_markdown():
    r = run()
    md = report_markdown(r, [("Market", "All markets")], [("Currency", "USD assumed.")],
                         datetime(2026, 10, 28, 9, 30))
    assert md.startswith("# CAUSE Investigation Report")
    assert "Generated 28 Oct 2026 09:30" in md
    assert LABEL in md
    assert "| Revenue | $400 | $500 | +$100 (+25.0%) |" in md
    assert "| Profit Margin | 12.5% | 10.0% | -2.5 pp |" in md
    assert "Office Supplies: +$200" in md and "Furniture: -$150" in md
    assert "not confirmed root causes" in md and "USD assumed." in md
