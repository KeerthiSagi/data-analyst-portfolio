"""CAUSE — Metric Drop Root Cause Analyzer (Streamlit entry point).

Run from this folder:            streamlit run app_root_cause.py
Or from the repository root:     streamlit run project2-root-cause-analyzer/app_root_cause.py
"""

import sys
from pathlib import Path

# Make cause/, ui/ and views/ importable however the app is launched.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st  # noqa: E402

from cause.data import DataSourceError, DataValidationError  # noqa: E402
from ui import theme  # noqa: E402
from ui.components import empty_state, methodology_section, page_header  # noqa: E402
from ui.state import load_data, render_sidebar  # noqa: E402

st.set_page_config(
    page_title="CAUSE · Root Cause Analyzer",
    page_icon=":material/troubleshoot:",
    layout="wide",
    initial_sidebar_state="auto",  # open on desktop, collapsed on phones
)
st.markdown(theme.CSS, unsafe_allow_html=True)

VIEWS = APP_DIR / "views"
PAGES = [
    # The default page is always served at "/".
    st.Page(VIEWS / "overview.py", title="Metric Overview", icon=":material/monitoring:", default=True),
    st.Page(VIEWS / "investigation.py", title="Root Cause Investigation", icon=":material/troubleshoot:",
            url_path="investigation"),
    st.Page(VIEWS / "revenue_drivers.py", title="Revenue Driver Analysis",
            icon=":material/stacked_line_chart:", url_path="revenue-drivers"),
    st.Page(VIEWS / "report.py", title="Investigation Report", icon=":material/summarize:",
            url_path="report"),
]

st.sidebar.markdown(
    '<div class="cause-brand"><span class="cause-brand-name">CAUSE</span>'
    '<span class="cause-brand-tag">Root cause analyzer</span></div>',
    unsafe_allow_html=True,
)
page = st.navigation(PAGES, position="sidebar")

try:
    loaded = load_data()
except (DataSourceError, DataValidationError) as exc:
    page_header("Dataset unavailable", "CAUSE needs the Global Superstore dataset to run.")
    empty_state("The dataset could not be loaded", str(exc))
    st.stop()

render_sidebar(loaded)
page.run()
st.space("medium")
methodology_section()
