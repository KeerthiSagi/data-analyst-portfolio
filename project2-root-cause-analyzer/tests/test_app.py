"""End-to-end checks of the Streamlit shell using Streamlit's AppTest.

Uses the real dataset; skipped when it is not available.
"""

from pathlib import Path

import pytest

from cause.data import DataSourceError, resolve_data_path

try:
    resolve_data_path()
    HAVE_DATA = True
except DataSourceError:
    HAVE_DATA = False

pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="Global Superstore dataset not found")

APP = str(Path(__file__).resolve().parent.parent / "app_root_cause.py")
PAGES = {
    "views/overview.py": "Metric Overview",
    "views/investigation.py": "Root Cause Investigation",
    "views/revenue_drivers.py": "Revenue Driver Analysis",
    "views/report.py": "Investigation Report",
}


@pytest.fixture
def app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(APP, default_timeout=60).run()


def page_title(at) -> str:
    for m in at.markdown:
        if 'class="cause-title"' in m.value:
            return m.value.split('class="cause-title">')[1].split("<")[0]
    return ""


def sidebar_multiselect(at, label):
    return next(m for m in at.sidebar.multiselect if m.label == label)


def warnings(at) -> list[str]:
    return [w.value for w in at.warning]


def test_default_page_renders_without_errors(app):
    assert not app.exception and not app.error
    assert page_title(app) == "Metric Overview"
    assert [m.label for m in app.sidebar.multiselect] == ["Market", "Region", "Category", "Customer Segment"]
    assert app.sidebar.selectbox[0].value == "2014-10-01"   # latest full quarter
    assert any(e.label == "Methodology and limitations" for e in app.expander)


@pytest.mark.parametrize("path, title", list(PAGES.items()))
def test_every_page_renders(app, path, title):
    app.switch_page(path).run()
    assert not app.exception and not app.error
    assert page_title(app) == title


def test_filters_persist_across_pages(app):
    sidebar_multiselect(app, "Market").set_value(["EU", "US"]).run()
    sidebar_multiselect(app, "Category").set_value(["Technology"]).run()
    for path in PAGES:
        app.switch_page(path).run()
        assert sidebar_multiselect(app, "Market").value == ["EU", "US"]
        assert sidebar_multiselect(app, "Category").value == ["Technology"]
        chips = next(m.value for m in app.markdown if 'class="cause-chips"' in m.value)
        assert "EU, US" in chips and "Technology" in chips


def test_region_options_follow_market(app):
    sidebar_multiselect(app, "Market").set_value(["EU"]).run()
    assert sidebar_multiselect(app, "Region").options == ["EU · Central", "EU · North", "EU · South"]


def test_conflicting_region_is_kept_and_warned(app):
    sidebar_multiselect(app, "Market").set_value(["EU"]).run()
    sidebar_multiselect(app, "Region").set_value(["EU · North"]).run()
    sidebar_multiselect(app, "Market").set_value(["US"]).run()
    assert sidebar_multiselect(app, "Region").value == ["EU · North"]   # not silently removed
    assert any("outside the selected markets" in w for w in warnings(app))
    assert not app.exception


def test_reset_filters(app):
    sidebar_multiselect(app, "Category").set_value(["Furniture"]).run()
    app.sidebar.button[0].click().run()
    assert sidebar_multiselect(app, "Category").value == []


def test_period_selection_survives_switching_period_type(app):
    app.sidebar.segmented_control[0].set_value("Month").run()
    app.sidebar.selectbox[0].set_value("2013-06-01").run()
    app.sidebar.segmented_control[0].set_value("Year").run()
    app.sidebar.segmented_control[0].set_value("Month").run()
    assert app.sidebar.selectbox[0].value == "2013-06-01"


def test_not_comparable_period_warns(app):
    app.sidebar.segmented_control[0].set_value("Month").run()
    app.sidebar.selectbox[0].set_value("2011-01-01").run()
    assert any("outside the data range" in w for w in warnings(app))
    assert any("not available" in w for w in warnings(app))
    assert not app.exception


def test_year_over_year_label(app):
    app.sidebar.radio[0].set_value("Same period last year").run()
    chips = next(m.value for m in app.markdown if 'class="cause-chips"' in m.value)
    assert "Q4 2013" in chips and "same period last year" in chips


def test_custom_range(app):
    from datetime import date
    app.sidebar.segmented_control[0].set_value("Custom").run()
    app.sidebar.date_input[0].set_value((date(2014, 3, 10), date(2014, 3, 23))).run()
    chips = next(m.value for m in app.markdown if 'class="cause-chips"' in m.value)
    assert "24 Feb 2014 – 09 Mar 2014" in chips
    assert not app.exception
