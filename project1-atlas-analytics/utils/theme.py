import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

from utils.palette import (
    ACCENT,
    ACCENT_HOVER,
    BACKGROUND,
    BORDER,
    CARD,
    CARD_RAISED,
    CATEGORICAL,
    CHART_HOVERLABEL,
    FONT_STACK,
    GRID,
    NEGATIVE,
    POSITIVE,
    SIDEBAR,
    TEXT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARNING,
)


# ============================================================
# ATLAS MIDNIGHT-BLUE DESIGN SYSTEM (shared with CAUSE)
#
# The native theme lives in .streamlit/config.toml. The CSS below adds what
# config cannot express (cards, headers, spacing) and repeats the core
# colors so the look holds even if another config takes precedence.
# ============================================================

COLORS = {
    "background": BACKGROUND,
    "sidebar": SIDEBAR,
    "surface": CARD,
    "surface_raised": CARD_RAISED,
    "primary": ACCENT,
    "text": TEXT,
    "muted": TEXT_SECONDARY,
    "border": BORDER,
    "positive": POSITIVE,
    "negative": NEGATIVE,
}


# ============================================================
# GLOBAL STREAMLIT THEME
# ============================================================

CSS = f"""
<style>
:root {{
  --atlas-bg: {BACKGROUND};
  --atlas-sidebar: {SIDEBAR};
  --atlas-card: {CARD};
  --atlas-card-raised: {CARD_RAISED};
  --atlas-border: {BORDER};
  --atlas-accent: {ACCENT};
  --atlas-accent-hover: {ACCENT_HOVER};
  --atlas-accent-soft: rgba(79, 140, 255, 0.14);
  --atlas-accent-tag: rgba(79, 140, 255, 0.18);
  --atlas-positive: {POSITIVE};
  --atlas-negative: {NEGATIVE};
  --atlas-warning: {WARNING};
  --atlas-text: {TEXT};
  --atlas-text-2: {TEXT_SECONDARY};
  --atlas-text-3: {TEXT_MUTED};
  --atlas-radius: 12px;
}}

/* ===================================================
   GLOBAL APP STYLING
=================================================== */

.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
  background: var(--atlas-bg);
  color: var(--atlas-text);
}}

.stApp {{
  overflow-x: hidden;
}}

.block-container {{
  max-width: 1400px;
  padding-top: 3.5rem !important;
  padding-bottom: 3rem !important;
  padding-left: 2.25rem !important;
  padding-right: 2.25rem !important;
}}

h1, h2, h3, h4 {{
  color: var(--atlas-text) !important;
  letter-spacing: -0.01em;
}}

h1 {{ font-size: 1.75rem !important; font-weight: 700 !important; }}
h2 {{ font-size: 1.28rem !important; font-weight: 700 !important; }}
h3 {{ font-size: 1.05rem !important; font-weight: 650 !important; }}

p {{
  color: var(--atlas-text-2);
}}

[data-testid="stMarkdownContainer"] strong {{
  color: var(--atlas-text);
}}


/* ===================================================
   SIDEBAR + PROJECT NAV
=================================================== */

[data-testid="stSidebar"] {{
  background: var(--atlas-sidebar);
  border-right: 1px solid var(--atlas-border);
}}

[data-testid="stSidebar"] > div:first-child {{
  padding-top: 0.85rem;
}}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  color: var(--atlas-text-2) !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 0.4rem;
}}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label p {{
  color: var(--atlas-text) !important;
  font-weight: 600;
  font-size: 0.84rem !important;
}}

[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  color: var(--atlas-text-3) !important;
}}

/* Curated page_link labels replace filename-based multipage nav. */
[data-testid="stSidebarNav"] {{
  display: none !important;
}}

.atlas-brand {{
  margin: 0 0 1rem 0;
  padding: 0 0 0.85rem 0;
  border-bottom: 1px solid var(--atlas-border);
}}

.atlas-brand-mark {{
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--atlas-text);
  letter-spacing: 0.12em;
  line-height: 1.3;
}}

.atlas-brand-mark .atlas-brand-accent {{
  color: var(--atlas-accent);
}}

.atlas-brand-tagline {{
  color: var(--atlas-text-2);
  font-size: 0.78rem;
  margin-top: 0.2rem;
  line-height: 1.4;
}}

.atlas-nav-label {{
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--atlas-text-2);
  margin: 0.15rem 0 0.45rem 0;
}}

.atlas-nav-divider {{
  height: 1px;
  background: var(--atlas-border);
  margin: 0.85rem 0 1rem 0;
}}

[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
  border-radius: 10px !important;
  padding: 0.45rem 0.65rem !important;
  margin-bottom: 0.15rem;
  border: 1px solid transparent !important;
  color: var(--atlas-text-2) !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  background: transparent !important;
}}

[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p,
[data-testid="stSidebar"] [data-testid="stPageLink"] a p,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span {{
  color: inherit !important;
}}

[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
  background-color: var(--atlas-accent-soft) !important;
  color: var(--atlas-text) !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink"] [aria-disabled="true"] a,
[data-testid="stSidebar"] a[aria-disabled="true"],
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][disabled] {{
  background-color: var(--atlas-accent-soft) !important;
  color: var(--atlas-accent-hover) !important;
  border: 1px solid rgba(79, 140, 255, 0.45) !important;
  opacity: 1 !important;
}}

.atlas-nav-fallback {{
  border-radius: 10px;
  padding: 0.45rem 0.65rem;
  margin-bottom: 0.15rem;
  border: 1px solid transparent;
  color: var(--atlas-text-2);
  font-weight: 600;
  font-size: 0.9rem;
}}

.atlas-nav-fallback.atlas-nav-current {{
  background-color: var(--atlas-accent-soft);
  color: var(--atlas-accent-hover);
  border: 1px solid rgba(79, 140, 255, 0.45);
}}


/* ===================================================
   STREAMLIT METRICS
=================================================== */

div[data-testid="stMetric"] {{
  background-color: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius);
  padding: 16px 18px;
}}

div[data-testid="stMetricLabel"] {{
  color: var(--atlas-text-2);
  font-size: 0.8rem;
  font-weight: 600;
}}

div[data-testid="stMetricValue"] {{
  color: var(--atlas-text);
  font-size: 1.55rem;
  font-weight: 700;
}}

div[data-testid="stMetricDelta"] {{
  font-size: 0.82rem;
}}


/* ===================================================
   CHART / TABLE CONTAINERS
=================================================== */

div[data-testid="stPlotlyChart"] {{
  background-color: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius);
  padding: 10px 10px 12px 10px;
  overflow: visible;
}}

div[data-testid="stDataFrame"],
div[data-testid="stDataFrameResizable"] {{
  background-color: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius);
  padding: 4px;
  overflow-x: auto;
}}

/* Table toolbar (search, download, fullscreen). */
[data-testid="stElementToolbar"] button {{
  color: var(--atlas-text-2);
}}

/* Bordered containers (export panels and other grouped controls). */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  border-color: var(--atlas-border);
}}


/* ===================================================
   FILTERS AND INPUTS
=================================================== */

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] {{
  border-radius: 10px !important;
  border-color: var(--atlas-border) !important;
  background-color: var(--atlas-card) !important;
  color: var(--atlas-text);
}}

div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"]:focus-within > div {{
  border-color: var(--atlas-accent) !important;
  box-shadow: 0 0 0 1px var(--atlas-accent) !important;
}}

div[data-testid="stDateInput"] input,
div[data-testid="stTextInput"] input {{
  border-radius: 10px;
  background-color: var(--atlas-card);
  color: var(--atlas-text);
}}

div[data-testid="stTextInput"] input::placeholder {{
  color: var(--atlas-text-3);
}}

/* Dropdown menus and the date-picker calendar. */
[data-baseweb="popover"] ul,
[data-baseweb="menu"],
[data-baseweb="popover"] [data-baseweb="calendar"] {{
  background-color: var(--atlas-card-raised) !important;
}}

span[data-baseweb="tag"],
[data-baseweb="tag"] {{
  background-color: var(--atlas-accent-tag) !important;
  color: var(--atlas-text) !important;
  border-radius: 6px !important;
}}

span[data-baseweb="tag"] span,
[data-baseweb="tag"] span {{
  color: var(--atlas-text) !important;
}}

/* Multiselect chips (Streamlit 1.65 marks them with data-tag). */
[data-testid="stMultiSelect"] [data-tag] {{
  background-color: var(--atlas-accent-tag) !important;
  border: 1px solid rgba(79, 140, 255, 0.35) !important;
  color: var(--atlas-text) !important;
  border-radius: 6px !important;
}}

[data-testid="stMultiSelect"] [data-tag] span,
[data-testid="stMultiSelect"] [data-tag] button {{
  color: var(--atlas-text) !important;
}}

div[data-testid="stRadio"] label {{
  font-weight: 600 !important;
}}

/* Segmented controls (metric pickers). */
[data-testid="stButtonGroup"] button {{
  background-color: var(--atlas-card);
  border-color: var(--atlas-border);
  color: var(--atlas-text-2);
}}

[data-testid="stButtonGroup"] button:hover {{
  border-color: var(--atlas-accent);
  color: var(--atlas-text);
}}

[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] {{
  background-color: var(--atlas-accent-tag);
  border-color: var(--atlas-accent);
  color: var(--atlas-text);
}}

[data-testid="stButtonGroup"] > div {{
  flex-wrap: wrap;
}}


/* ===================================================
   BUTTONS
=================================================== */

.stButton > button,
.stDownloadButton > button {{
  background-color: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: 10px;
  color: var(--atlas-text);
  font-weight: 600;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}}

.stButton > button:hover,
.stDownloadButton > button:hover {{
  border-color: var(--atlas-accent);
  color: var(--atlas-accent-hover);
  background-color: var(--atlas-accent-soft);
}}

.stDownloadButton > button[kind="primary"],
.stButton > button[kind="primary"],
.stDownloadButton > button[data-testid="stBaseButton-primary"],
.stButton > button[data-testid="stBaseButton-primary"],
button[kind="primary"] {{
  background-color: var(--atlas-accent) !important;
  border-color: var(--atlas-accent) !important;
  color: {BACKGROUND} !important;
}}

.stDownloadButton > button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {{
  background-color: var(--atlas-accent-hover) !important;
  border-color: var(--atlas-accent-hover) !important;
  color: {BACKGROUND} !important;
}}

.stDownloadButton > button[kind="primary"] p,
.stButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primary"] span {{
  color: {BACKGROUND} !important;
}}


/* ===================================================
   DASHBOARD HEADER
=================================================== */

.dashboard-eyebrow {{
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--atlas-accent);
  margin-top: 0;
  margin-bottom: 0.3rem;
  line-height: 1.5;
  text-transform: uppercase;
}}

.dashboard-title {{
  font-size: 1.85rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--atlas-text);
  line-height: 1.2;
  margin-top: 0;
  margin-bottom: 0.35rem;
}}

.dashboard-subtitle {{
  font-size: 0.98rem;
  font-weight: 400;
  color: var(--atlas-text-2);
  line-height: 1.55;
  margin-top: 0;
  margin-bottom: 1.25rem;
  max-width: 62rem;
}}

.section-nav {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem 0.65rem;
  margin: 0 0 1.1rem 0;
  padding: 0.65rem 0.85rem;
  background: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius);
  color: var(--atlas-text-3);
}}

.section-nav-label {{
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--atlas-text-2);
  margin-right: 0.25rem;
}}

.section-nav-link {{
  color: var(--atlas-accent) !important;
  font-size: 0.86rem;
  font-weight: 600;
  text-decoration: none !important;
}}

.section-nav-link:hover {{
  color: var(--atlas-accent-hover) !important;
  text-decoration: underline !important;
}}

.section-block {{
  margin: 1.35rem 0 0.85rem 0;
  padding-top: 0.85rem;
  border-top: 1px solid var(--atlas-border);
  scroll-margin-top: 4.5rem;
}}

.section-title {{
  font-size: 1.28rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--atlas-text);
  line-height: 1.25;
  margin: 0.15rem 0 0.35rem 0;
}}

.section-caption {{
  font-size: 0.88rem;
  color: var(--atlas-text-2);
  line-height: 1.5;
  margin: 0 0 0.35rem 0;
  max-width: 52rem;
}}

.export-panel {{
  background: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius);
  padding: 1rem 1.1rem 0.85rem 1.1rem;
  margin-bottom: 0.5rem;
}}


/* ===================================================
   KPI CARDS
=================================================== */

/* Equal-height KPI columns without clipping stretched containers. */
[data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) {{
  align-items: stretch !important;
}}

[data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > [data-testid="stColumn"] {{
  display: flex !important;
  flex-direction: column !important;
}}

[data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > [data-testid="stColumn"] > div {{
  flex: 1 1 auto !important;
  height: 100% !important;
}}

/* Streamlit border wrappers can clip children unless overflow is forced open. */
div[data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-kpi_"]),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.kpi-card-body),
div[data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-kpi_"]) > div,
div[data-testid="element-container"]:has([class*="st-key-kpi_"]),
div[data-testid="stMarkdownContainer"]:has(.kpi-card-body) {{
  overflow: visible !important;
  height: auto !important;
}}

[class*="st-key-kpi_"] {{
  background-color: var(--atlas-card) !important;
  border: 1px solid var(--atlas-border) !important;
  border-radius: var(--atlas-radius) !important;
  padding: 16px 16px 20px 16px !important;
  box-shadow: none !important;
  height: auto !important;
  min-height: 100% !important;
  overflow: visible !important;
  display: flex !important;
  flex-direction: column !important;
  box-sizing: border-box !important;
}}

.kpi-card-body {{
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1 1 auto;
  min-height: 0;
  overflow: visible;
  padding-bottom: 2px;
}}

.kpi-label-row {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}}

.kpi-label {{
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--atlas-text-2);
  text-transform: uppercase;
}}

.kpi-grain {{
  font-size: 0.66rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--atlas-text-3);
  text-transform: uppercase;
}}

.kpi-value {{
  font-size: clamp(1.35rem, 1.55vw, 1.7rem);
  font-weight: 700;
  color: var(--atlas-text);
  margin-top: 0.3rem;
  margin-bottom: 0;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}}

.kpi-comparison {{
  margin-top: 0.35rem;
  min-height: 2.4em;
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}}

.kpi-footer {{
  margin-top: 0.3rem;
  margin-bottom: 0;
  padding-bottom: 2px;
  font-size: 0.78rem;
  color: var(--atlas-text-3);
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
}}

.kpi-spark-empty {{
  min-height: 78px;
  display: flex;
  align-items: center;
  color: var(--atlas-text-3);
  font-size: 0.75rem;
  margin-top: 4px;
}}

[class*="st-key-sparkline_"] {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 2px 0 0 0 !important;
  border-radius: 0 !important;
  overflow: visible !important;
}}

[class*="st-key-sparkline_"] [data-testid="stPlotlyChart"] {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  border-radius: 0 !important;
  overflow: visible !important;
}}


/* ===================================================
   INSIGHT CARDS (CAUSE callout style)
=================================================== */

.insight-card {{
  background-color: var(--atlas-card);
  border: 1px solid var(--atlas-border);
  border-left: 3px solid var(--atlas-accent);
  border-radius: 10px;
  padding: 0.95rem 1.05rem;
  margin-bottom: 0.75rem;
  min-height: 132px;
}}

.insight-title {{
  color: var(--atlas-text);
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.3rem;
}}

.insight-body {{
  color: var(--atlas-text-2);
  font-size: 0.9rem;
  line-height: 1.55;
}}


/* ===================================================
   DIVIDERS / CAPTIONS / ALERTS / EXPANDERS
=================================================== */

hr {{
  border-color: var(--atlas-border) !important;
  opacity: 1;
  margin: 1.1rem 0 !important;
}}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
.stCaption {{
  color: var(--atlas-text-2);
  font-size: 0.8rem;
}}

div[data-testid="stAlert"] {{
  border-radius: var(--atlas-radius);
}}

[data-testid="stExpander"] details {{
  background: var(--atlas-card);
  border-color: var(--atlas-border);
  border-radius: var(--atlas-radius);
}}


/* ===================================================
   RESPONSIVE DESIGN
=================================================== */

@media (max-width: 768px) {{

  .block-container {{
    padding-top: 3.1rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }}

  .dashboard-title {{ font-size: 1.55rem; }}

  .dashboard-subtitle {{
    font-size: 0.9rem;
    margin-bottom: 1rem;
  }}

  .section-title {{ font-size: 1.12rem; }}

  [class*="st-key-kpi_"] {{
    padding: 14px 14px 18px 14px !important;
    height: auto !important;
  }}

  .kpi-value {{ font-size: 1.4rem; }}

  .section-nav {{ padding: 0.55rem 0.7rem; }}

  .insight-card {{ min-height: 0; }}
}}

@media (max-width: 640px) {{
  .dashboard-title {{ font-size: 1.45rem; }}
  .kpi-value {{ font-size: 1.4rem; }}
}}

@media (max-width: 430px) {{
  .dashboard-title {{ font-size: 1.35rem; }}
}}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


# ============================================================
# PLOTLY THEME + SHARED CHART HELPERS
# ============================================================

TEMPLATE_NAME = "atlas_dark"

PLOTLY_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
    "responsive": True,
    "scrollZoom": False,
}


def chart_margins(*, legend: bool = False, category_axis: str = "y") -> dict:
    """Readable Plotly margins. category_axis is the axis carrying labels."""

    bottom = 72 if category_axis == "x" else 48
    top = 56 if legend else 28
    left = 56 if category_axis == "y" else 48
    return dict(l=left, r=28, t=top, b=bottom, pad=4)


def bar_chart_sizing(n_categories: int, orientation: str = "h") -> dict:
    """Compact heights and wider gaps when few categories are present."""

    count = max(int(n_categories), 1)
    if orientation == "h":
        if count <= 3:
            height = 260
            bargap = 0.68
        elif count <= 6:
            height = max(300, 44 * count + 90)
            bargap = 0.42
        else:
            height = min(560, max(340, 36 * count + 100))
            bargap = 0.24
    else:
        height = 280 if count <= 3 else 320 if count <= 6 else 360
        bargap = 0.62 if count <= 3 else 0.42 if count <= 6 else 0.3
    return {"height": height, "bargap": bargap}


def _build_template() -> go.layout.Template:
    axis = dict(
        zeroline=False,
        automargin=True,
        gridcolor=GRID,
        zerolinecolor=BORDER,
        linecolor=BORDER,
        tickcolor=BORDER,
        tickfont=dict(color=TEXT_SECONDARY, size=11),
        title=dict(font=dict(color=TEXT_SECONDARY, size=12)),
    )
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, color=TEXT, size=12),
            title=dict(font=dict(size=14, color=TEXT), x=0, xanchor="left"),
            paper_bgcolor=CARD,
            plot_bgcolor=CARD,
            colorway=CATEGORICAL,
            margin=dict(l=48, r=28, t=48, b=64, pad=4),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(size=11, color=TEXT_SECONDARY),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                x=0,
            ),
            xaxis={**axis, "showgrid": False},
            yaxis={**axis, "showgrid": True},
            hoverlabel={**CHART_HOVERLABEL, "namelength": -1},
            hovermode="closest",
        )
    )


def apply_plotly_theme():
    pio.templates[TEMPLATE_NAME] = _build_template()
    pio.templates.default = TEMPLATE_NAME


# ============================================================
# INITIALIZE COMPLETE THEME
# ============================================================

def initialize_theme():
    apply_theme()
    apply_plotly_theme()
