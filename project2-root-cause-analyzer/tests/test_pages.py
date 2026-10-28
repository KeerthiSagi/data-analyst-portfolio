"""End-to-end checks of the four analytical pages (real dataset, Streamlit AppTest)."""

import io

import pandas as pd
import pytest

from tests.test_app import APP, HAVE_DATA, page_title, sidebar_multiselect, warnings

pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="Global Superstore dataset not found")


@pytest.fixture
def app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(APP, default_timeout=90).run()


def ok(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def charts(at):
    return at.get("plotly_chart")


def card_text(at) -> str:
    return " ".join(m.value for m in at.markdown if 'class="cause-grid"' in m.value)


def callout_titles(at) -> list[str]:
    return [m.value.split('cause-callout-title">')[1].split("<")[0]
            for m in at.markdown if 'class="cause-callout' in m.value]


# ------------------------------------------------------------------
# Overview
# ------------------------------------------------------------------

def test_overview_kpis_and_charts(app):
    ok(app)
    text = card_text(app)
    for label in ["Total revenue", "Total profit", "Distinct orders", "Profit margin"]:
        assert label in text
    assert " pp" in text                       # margin change in percentage points
    assert len(charts(app)) == 3               # trend, market, category
    assert len(app.dataframe) == 1             # segment table
    assert "Contribution, not causation" in callout_titles(app)


def test_overview_respects_filters(app):
    before = card_text(app)
    sidebar_multiselect(app, "Market").set_value(["EU"]).run()
    ok(app)
    assert card_text(app) != before


def test_overview_empty_state(app):
    sidebar_multiselect(app, "Market").set_value(["US"]).run()
    sidebar_multiselect(app, "Region").set_value(["US · Central"]).run()
    sidebar_multiselect(app, "Market").set_value(["EU"]).run()   # region now conflicts -> no data
    ok(app)
    assert any("No orders match" in w for w in warnings(app))
    assert not charts(app)


# ------------------------------------------------------------------
# Investigation
# ------------------------------------------------------------------

@pytest.mark.parametrize("metric", ["Revenue", "Profit", "Orders", "Profit Margin"])
def test_investigation_metrics(app, metric):
    app.switch_page("views/investigation.py").run()
    app.segmented_control(key="inv_metric").set_value(metric).run()
    ok(app)
    assert len(charts(app)) == 1 and len(app.dataframe) == 1
    if metric == "Orders":
        assert "Allocated orders" in callout_titles(app)
    if metric == "Profit Margin":
        assert "Rate effect" in card_text(app) and "Mix effect" in card_text(app)


def test_investigation_drill_down(app):
    app.switch_page("views/investigation.py").run()
    app.selectbox(key="inv_secondary").set_value("Category").run()
    assert len(app.dataframe) == 2                     # main + combinations
    app.selectbox(key="inv_parent_Market").set_value("EU").run()
    ok(app)
    assert len(charts(app)) == 2                       # main + drill waterfall
    assert any("Drill-down: EU by Category" in m.value for m in app.markdown)
    assert "EU · change" in card_text(app)


def test_secondary_cleared_when_it_matches_primary(app):
    app.switch_page("views/investigation.py").run()
    app.selectbox(key="inv_secondary").set_value("Category").run()
    app.selectbox(key="inv_primary").set_value("Category").run()
    ok(app)
    assert app.selectbox(key="inv_secondary").value == "None"


def test_investigation_not_comparable(app):
    app.sidebar.segmented_control[0].set_value("Month").run()
    app.sidebar.selectbox[0].set_value("2011-01-01").run()
    app.switch_page("views/investigation.py").run()
    ok(app)
    assert not charts(app)
    assert any("No comparison available" in m.value for m in app.markdown)


# ------------------------------------------------------------------
# Revenue drivers
# ------------------------------------------------------------------

def test_revenue_drivers_page(app):
    app.switch_page("views/revenue_drivers.py").run()
    ok(app)
    text = card_text(app)
    for label in ["Revenue", "Distinct orders", "Average order value", "Order volume effect", "Order value effect"]:
        assert label in text
    assert len(charts(app)) == 5    # bridge, 3 trends, group effects
    app.selectbox(key="drv_dimension").set_value("Customer Segment").run()
    ok(app)
    assert "How to read group effects" in callout_titles(app)


# ------------------------------------------------------------------
# Report and persistence
# ------------------------------------------------------------------

def test_report_uses_investigation_settings(app):
    app.switch_page("views/investigation.py").run()
    app.segmented_control(key="inv_metric").set_value("Profit").run()
    app.selectbox(key="inv_primary").set_value("Category").run()
    app.switch_page("views/report.py").run()
    ok(app)
    assert app.segmented_control(key="inv_metric").value == "Profit"
    assert app.selectbox(key="inv_primary").value == "Category"
    assert any("CAUSE investigation report: Profit" in m.value for m in app.markdown)
    assert len(app.get("download_button")) == 4


def test_settings_persist_back_to_investigation(app):
    app.switch_page("views/report.py").run()
    app.segmented_control(key="inv_metric").set_value("Orders").run()
    app.switch_page("views/overview.py").run()
    app.switch_page("views/investigation.py").run()
    assert app.segmented_control(key="inv_metric").value == "Orders"


def test_filters_persist_into_report(app):
    sidebar_multiselect(app, "Category").set_value(["Furniture"]).run()
    app.switch_page("views/report.py").run()
    ok(app)
    summary = next(m.value for m in app.markdown if "**Filters:**" in m.value)
    assert "Category: Furniture" in summary


@pytest.mark.parametrize("path", ["views/overview.py", "views/investigation.py",
                                  "views/revenue_drivers.py", "views/report.py"])
def test_no_stray_magic_output(app, path):
    # Streamlit "magic" renders bare expression results; none should leak onto a page.
    app.switch_page(path).run()
    ok(app)
    assert not [m.value for m in app.markdown if m.value.strip() in ("None", "null")]
