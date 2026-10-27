import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio


# ============================================================
# MODERN SAAS ANALYTICS — DESIGN SYSTEM
# ============================================================

COLORS = {
    "background": "#F8FAFC",
    "surface": "#FFFFFF",
    "primary": "#4F46E5",
    "violet": "#8B5CF6",
    "indigo_light": "#EEF2FF",
    "text": "#0F172A",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "positive": "#10B981",
    "negative": "#DC2626",
    "sky": "#0EA5E9",
}


# ============================================================
# GLOBAL STREAMLIT THEME
# ============================================================

def apply_theme():

    st.markdown(
        """
        <style>

        /* ===================================================
           GLOBAL APP STYLING
        =================================================== */

        .stApp {
            background-color: #F8FAFC;
            color: #0F172A;
            overflow-x: hidden;
        }

        .block-container {
            max-width: 1440px;
            padding-top: 3.75rem !important;
            padding-bottom: 2.75rem !important;
            padding-left: 2.25rem !important;
            padding-right: 2.25rem !important;
        }

        h1, h2, h3 {
            color: #0F172A !important;
            letter-spacing: -0.4px;
        }

        h1 {
            font-size: 1.75rem !important;
            font-weight: 750 !important;
        }

        h2 {
            font-size: 1.28rem !important;
            font-weight: 700 !important;
        }

        h3 {
            font-size: 1.05rem !important;
            font-weight: 650 !important;
        }

        p {
            color: #475569;
        }


        /* ===================================================
           SIDEBAR + PROJECT NAV
        =================================================== */

        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0.85rem;
        }

        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            font-size: 0.95rem !important;
            font-weight: 700 !important;
            color: #0F172A !important;
            letter-spacing: -0.2px;
        }

        [data-testid="stSidebar"] label {
            color: #334155 !important;
            font-weight: 600;
            font-size: 0.84rem !important;
        }

        /* Curated page_link labels replace filename-based multipage nav. */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        .atlas-brand {
            margin: 0 0 1rem 0;
            padding: 0 0 0.85rem 0;
            border-bottom: 1px solid #E2E8F0;
        }

        .atlas-brand-mark {
            font-size: 1.05rem;
            font-weight: 800;
            color: #4F46E5;
            letter-spacing: -0.3px;
            line-height: 1.3;
        }

        .atlas-brand-tagline {
            color: #64748B;
            font-size: 0.78rem;
            margin-top: 0.2rem;
            line-height: 1.4;
        }

        .atlas-nav-label {
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 1.1px;
            text-transform: uppercase;
            color: #94A3B8;
            margin: 0.15rem 0 0.45rem 0;
        }

        .atlas-nav-divider {
            height: 1px;
            background: #E2E8F0;
            margin: 0.85rem 0 1rem 0;
        }

        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],
        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            border-radius: 10px !important;
            padding: 0.45rem 0.65rem !important;
            margin-bottom: 0.15rem;
            color: #334155 !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
        }

        [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
            background-color: #EEF2FF !important;
            color: #4338CA !important;
        }

        [data-testid="stSidebar"] [data-testid="stPageLink"] [aria-disabled="true"] a,
        [data-testid="stSidebar"] a[aria-disabled="true"] {
            background-color: #EEF2FF !important;
            color: #4338CA !important;
            border: 1px solid #C7D2FE !important;
        }

        .atlas-nav-fallback {
            border-radius: 10px;
            padding: 0.45rem 0.65rem;
            margin-bottom: 0.15rem;
            color: #334155;
            font-weight: 600;
            font-size: 0.9rem;
        }

        .atlas-nav-fallback.atlas-nav-current {
            background-color: #EEF2FF;
            color: #4338CA;
            border: 1px solid #C7D2FE;
        }


        /* ===================================================
           STREAMLIT METRICS
        =================================================== */

        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
        }

        div[data-testid="stMetricLabel"] {
            color: #64748B;
            font-size: 0.8rem;
            font-weight: 650;
        }

        div[data-testid="stMetricValue"] {
            color: #0F172A;
            font-size: 1.55rem;
            font-weight: 750;
        }

        div[data-testid="stMetricDelta"] {
            font-size: 0.82rem;
        }


        /* ===================================================
           CHART / TABLE CONTAINERS
        =================================================== */

        div[data-testid="stPlotlyChart"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 10px 10px 12px 10px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
            overflow: visible;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrameResizable"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 4px;
            overflow-x: auto;
        }


        /* ===================================================
           FILTERS AND INPUTS
        =================================================== */

        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border-color: #CBD5E1 !important;
            background-color: #FFFFFF;
        }

        div[data-baseweb="select"] > div:focus-within {
            border-color: #4F46E5 !important;
            box-shadow: 0 0 0 1px #4F46E5 !important;
        }

        span[data-baseweb="tag"] {
            background-color: #EEF2FF !important;
            color: #4338CA !important;
            border-radius: 6px !important;
        }

        span[data-baseweb="tag"] span {
            color: #4338CA !important;
        }

        div[data-testid="stDateInput"] input,
        div[data-testid="stTextInput"] input {
            border-radius: 10px;
            border-color: #CBD5E1;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #4F46E5;
            box-shadow: 0 0 0 1px #4F46E5;
        }

        div[data-testid="stRadio"] label {
            font-weight: 600 !important;
        }


        /* ===================================================
           BUTTONS
        =================================================== */

        .stButton > button,
        .stDownloadButton > button {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 10px;
            color: #334155;
            font-weight: 600;
            transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: #4F46E5;
            color: #4F46E5;
            background-color: #EEF2FF;
        }

        .stDownloadButton > button[kind="primary"],
        .stButton > button[kind="primary"],
        .stDownloadButton > button[data-testid="stBaseButton-primary"],
        .stButton > button[data-testid="stBaseButton-primary"],
        button[kind="primary"] {
            background-color: #4F46E5 !important;
            border-color: #4F46E5 !important;
            color: #FFFFFF !important;
        }

        .stDownloadButton > button[kind="primary"]:hover,
        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover {
            background-color: #4338CA !important;
            border-color: #4338CA !important;
            color: #FFFFFF !important;
        }

        span[data-baseweb="tag"],
        span[data-baseweb="tag"] span,
        [data-baseweb="tag"] {
            background-color: #EEF2FF !important;
            color: #4338CA !important;
        }


        /* ===================================================
           DASHBOARD HEADER
        =================================================== */

        .dashboard-eyebrow {
            display: block;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 1.35px;
            color: #4F46E5;
            margin-top: 0;
            margin-bottom: 0.55rem;
            line-height: 1.5;
            text-transform: uppercase;
        }

        .dashboard-title {
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.7px;
            color: #0F172A;
            line-height: 1.2;
            margin-top: 0;
            margin-bottom: 0.4rem;
        }

        .dashboard-subtitle {
            font-size: 0.92rem;
            font-weight: 400;
            color: #64748B;
            line-height: 1.55;
            margin-top: 0;
            margin-bottom: 1.35rem;
            max-width: 46rem;
        }

        .section-nav {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem 0.65rem;
            margin: 0 0 1.1rem 0;
            padding: 0.65rem 0.85rem;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
        }

        .section-nav-label {
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.9px;
            text-transform: uppercase;
            color: #94A3B8;
            margin-right: 0.25rem;
        }

        .section-nav-link {
            color: #4338CA !important;
            font-size: 0.86rem;
            font-weight: 650;
            text-decoration: none !important;
        }

        .section-nav-link:hover {
            color: #312E81 !important;
            text-decoration: underline !important;
        }

        .section-block {
            margin: 1.35rem 0 0.85rem 0;
            padding-top: 0.35rem;
            border-top: 1px solid #E2E8F0;
            scroll-margin-top: 4.5rem;
        }

        .section-title {
            font-size: 1.28rem;
            font-weight: 750;
            letter-spacing: -0.4px;
            color: #0F172A;
            line-height: 1.25;
            margin: 0.15rem 0 0.35rem 0;
        }

        .section-caption {
            font-size: 0.86rem;
            color: #64748B;
            line-height: 1.5;
            margin: 0 0 0.35rem 0;
            max-width: 52rem;
        }

        .export-panel {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 1rem 1.1rem 0.85rem 1.1rem;
            margin-bottom: 0.5rem;
        }


        /* ===================================================
           PREMIUM KPI CARDS
        =================================================== */

        /* Equal-height KPI columns without clipping stretched containers. */
        [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) {
            align-items: stretch !important;
        }

        [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > [data-testid="stColumn"] {
            display: flex !important;
            flex-direction: column !important;
        }

        [data-testid="stHorizontalBlock"]:has([class*="st-key-kpi_"]) > [data-testid="stColumn"] > div {
            flex: 1 1 auto !important;
            height: 100% !important;
        }

        /* Streamlit border wrappers can clip children unless overflow is forced open. */
        div[data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-kpi_"]),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.kpi-card-body),
        div[data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-kpi_"]) > div,
        div[data-testid="element-container"]:has([class*="st-key-kpi_"]),
        div[data-testid="stMarkdownContainer"]:has(.kpi-card-body) {
            overflow: visible !important;
            height: auto !important;
        }

        .st-key-kpi_revenue,
        .st-key-kpi_profit,
        .st-key-kpi_margin,
        .st-key-kpi_orders,
        .st-key-kpi_aov,
        .st-key-kpi_lines,
        .st-key-kpi_ship_cost,
        .st-key-kpi_ship_ratio,
        .st-key-kpi_ship_days,
        .st-key-kpi_same_day,
        [class*="st-key-kpi_"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 14px !important;
            padding: 16px 16px 22px 16px !important;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
            height: auto !important;
            min-height: 100% !important;
            overflow: visible !important;
            display: flex !important;
            flex-direction: column !important;
            box-sizing: border-box !important;
        }

        .st-key-kpi_revenue { border-top: 3px solid #4F46E5 !important; }
        .st-key-kpi_profit { border-top: 3px solid #10B981 !important; }
        .st-key-kpi_margin { border-top: 3px solid #8B5CF6 !important; }
        .st-key-kpi_orders { border-top: 3px solid #0EA5E9 !important; }
        .st-key-kpi_aov { border-top: 3px solid #0EA5E9 !important; }
        .st-key-kpi_lines { border-top: 3px solid #8B5CF6 !important; }
        .st-key-kpi_ship_cost { border-top: 3px solid #4F46E5 !important; }
        .st-key-kpi_ship_ratio { border-top: 3px solid #8B5CF6 !important; }
        .st-key-kpi_ship_days { border-top: 3px solid #0EA5E9 !important; }
        .st-key-kpi_same_day { border-top: 3px solid #10B981 !important; }

        .kpi-card-body {
            display: flex;
            flex-direction: column;
            gap: 0;
            flex: 1 1 auto;
            min-height: 0;
            overflow: visible;
            padding-bottom: 2px;
        }

        .kpi-label-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 8px;
        }

        .kpi-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.65px;
            color: #64748B;
            text-transform: uppercase;
        }

        .kpi-grain {
            font-size: 0.64rem;
            font-weight: 700;
            letter-spacing: 0.55px;
            color: #94A3B8;
            text-transform: uppercase;
        }

        .kpi-value {
            font-size: clamp(1.35rem, 1.55vw, 1.75rem);
            font-weight: 800;
            color: #0F172A;
            margin-top: 8px;
            margin-bottom: 0;
            letter-spacing: -0.7px;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }

        .kpi-comparison {
            margin-top: 8px;
            min-height: 2.4em;
            font-size: 0.78rem;
            font-weight: 700;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }

        .kpi-footer {
            margin-top: 8px;
            margin-bottom: 0;
            padding-bottom: 2px;
            font-size: 0.74rem;
            color: #64748B;
            line-height: 1.45;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .kpi-spark-empty {
            min-height: 78px;
            display: flex;
            align-items: center;
            color: #94A3B8;
            font-size: 0.75rem;
            margin-top: 4px;
        }

        [class*="st-key-sparkline_"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 2px 0 0 0 !important;
            border-radius: 0 !important;
            overflow: visible !important;
        }

        [class*="st-key-sparkline_"] [data-testid="stPlotlyChart"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 0 !important;
            border-radius: 0 !important;
            overflow: visible !important;
        }


        /* ===================================================
           EXECUTIVE INSIGHTS CARDS
        =================================================== */

        .insight-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 18px 18px 16px 18px;
            min-height: 132px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
        }

        .insight-title {
            color: #0F172A;
            font-size: 0.92rem;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .insight-body {
            color: #64748B;
            font-size: 0.86rem;
            line-height: 1.55;
        }


        /* ===================================================
           DIVIDERS / CAPTIONS / ALERTS
        =================================================== */

        hr {
            border-color: #E2E8F0 !important;
            opacity: 0.9;
            margin: 1.1rem 0 !important;
        }

        [data-testid="stCaptionContainer"] {
            color: #64748B;
            font-size: 0.8rem;
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
        }


        /* ===================================================
           RESPONSIVE DESIGN
        =================================================== */

        @media (max-width: 768px) {

            .block-container {
                padding-top: 3.1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }

            .dashboard-title {
                font-size: 1.55rem;
            }

            .dashboard-subtitle {
                font-size: 0.88rem;
                margin-bottom: 1rem;
            }

            .section-title {
                font-size: 1.12rem;
            }

            .st-key-kpi_revenue,
            .st-key-kpi_profit,
            .st-key-kpi_margin,
            .st-key-kpi_orders,
            .st-key-kpi_aov,
            .st-key-kpi_lines,
            .st-key-kpi_ship_cost,
            .st-key-kpi_ship_ratio,
            .st-key-kpi_ship_days,
            .st-key-kpi_same_day,
            [class*="st-key-kpi_"] {
                padding: 14px 14px 20px 14px !important;
                height: auto !important;
            }

            .kpi-value {
                font-size: 1.4rem;
            }

            .kpi-footer {
                margin-top: 8px;
            }

            .section-nav {
                padding: 0.55rem 0.7rem;
            }

        }

        @media (max-width: 430px) {
            .dashboard-title {
                font-size: 1.4rem;
            }
        }

        </style>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# PLOTLY THEME + SHARED CHART HELPERS
# ============================================================

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


def apply_plotly_theme():
    atlas = go.layout.Template()
    atlas.layout = go.Layout(
        font=dict(family="Inter, Source Sans Pro, sans-serif", color="#0F172A", size=12),
        title=dict(font=dict(size=14, color="#0F172A")),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        colorway=["#4F46E5", "#0EA5E9", "#10B981", "#8B5CF6", "#F59E0B", "#DC2626"],
        margin=dict(l=48, r=28, t=48, b=64, pad=4),
        legend=dict(
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#E2E8F0",
            borderwidth=0,
            font=dict(size=11, color="#475569"),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            automargin=True,
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B", size=11),
            title=dict(font=dict(color="#64748B", size=11)),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            zeroline=False,
            automargin=True,
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B", size=11),
            title=dict(font=dict(color="#64748B", size=11)),
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#E2E8F0",
            font=dict(color="#0F172A", size=12),
            align="left",
            namelength=-1,
        ),
        hovermode="closest",
    )
    pio.templates["atlas"] = atlas
    pio.templates.default = "plotly_white+atlas"


# ============================================================
# INITIALIZE COMPLETE THEME
# ============================================================

def initialize_theme():
    apply_theme()
    apply_plotly_theme()

