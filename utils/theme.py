import streamlit as st
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
    "negative": "#EF4444",
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
        }

        /* Fix dashboard header being cut off */

        .block-container {
            max-width: 1500px;
            padding-top: 4.5rem !important;
            padding-bottom: 3rem !important;
            padding-left: 2.5rem !important;
            padding-right: 2.5rem !important;
        }

        /* General typography */

        h1, h2, h3 {
            color: #0F172A !important;
            letter-spacing: -0.5px;
        }

        h1 {
            font-size: 2rem !important;
            font-weight: 750 !important;
        }

        h2 {
            font-size: 1.45rem !important;
            font-weight: 700 !important;
        }

        h3 {
            font-size: 1.1rem !important;
            font-weight: 650 !important;
        }

        p {
            color: #475569;
        }


        /* ===================================================
           SIDEBAR
        =================================================== */

        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        [data-testid="stSidebar"] h2 {
            font-size: 1.1rem !important;
            font-weight: 700 !important;
            color: #0F172A !important;
        }

        [data-testid="stSidebar"] label {
            color: #334155 !important;
            font-weight: 500;
        }

        /* Sidebar navigation */

        [data-testid="stSidebarNav"] {
            padding-top: 0.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #E2E8F0;
        }

        [data-testid="stSidebarNav"] a {
            border-radius: 9px;
            transition: background-color 0.2s ease;
        }

        [data-testid="stSidebarNav"] a:hover {
            background-color: #EEF2FF;
        }


        /* ===================================================
           STREAMLIT METRICS
        =================================================== */

        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
        }

        div[data-testid="stMetricLabel"] {
            color: #64748B;
            font-size: 0.85rem;
            font-weight: 600;
        }

        div[data-testid="stMetricValue"] {
            color: #0F172A;
            font-size: 1.9rem;
            font-weight: 750;
        }

        div[data-testid="stMetricDelta"] {
            font-size: 0.85rem;
        }


        /* ===================================================
           CHART CONTAINERS
        =================================================== */

        div[data-testid="stPlotlyChart"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 15px;
            box-shadow: 0 4px 18px rgba(15, 23, 42, 0.035);
            overflow: hidden;
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
        }

        span[data-baseweb="tag"] {
            background-color: #EEF2FF !important;
            color: #4338CA !important;
            border-radius: 6px !important;
        }

        span[data-baseweb="tag"] span {
            color: #4338CA !important;
        }

        /* Date input */

        div[data-testid="stDateInput"] input {
            border-radius: 10px;
            border-color: #CBD5E1;
        }


        /* ===================================================
           BUTTONS
        =================================================== */

        .stButton > button {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 10px;
            color: #334155;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: #4F46E5;
            color: #4F46E5;
            background-color: #EEF2FF;
        }


        /* ===================================================
           DASHBOARD HEADER
        =================================================== */

        .dashboard-eyebrow {
            display: block;
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: #4F46E5;
            margin-top: 0;
            margin-bottom: 12px;
            line-height: 1.6;
            text-transform: uppercase;
        }

        .dashboard-title {
            font-size: 2.3rem;
            font-weight: 800;
            letter-spacing: -1px;
            color: #0F172A;
            line-height: 1.25;
            margin-top: 0;
            margin-bottom: 8px;
        }

        .dashboard-subtitle {
            font-size: 0.95rem;
            font-weight: 400;
            color: #64748B;
            line-height: 1.6;
            margin-top: 0;
            margin-bottom: 28px;
        }


        /* ===================================================
           PREMIUM KPI CARDS
        =================================================== */

        .kpi-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 18px;
            padding: 24px;
            min-height: 165px;
            box-shadow: 0 5px 20px rgba(15, 23, 42, 0.045);
            transition: transform 0.2s ease,
                        box-shadow 0.2s ease;
        }

        .kpi-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        }

        .kpi-label {
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.7px;
            color: #64748B;
            text-transform: uppercase;
        }

        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
            color: #0F172A;
            margin-top: 14px;
            letter-spacing: -1px;
            line-height: 1.2;
        }

        .kpi-footer {
            margin-top: 14px;
            font-size: 0.78rem;
            color: #64748B;
            line-height: 1.4;
        }

        /* KPI accent colors */

        .kpi-indigo {
            border-top: 4px solid #4F46E5;
        }

        .kpi-green {
            border-top: 4px solid #10B981;
        }

        .kpi-violet {
            border-top: 4px solid #8B5CF6;
        }

        .kpi-sky {
            border-top: 4px solid #0EA5E9;
        }


        /* ===================================================
           EXECUTIVE INSIGHTS CARDS
        =================================================== */

        .insight-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 22px;
            min-height: 140px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.035);
            transition: transform 0.2s ease;
        }

        .insight-card:hover {
            transform: translateY(-2px);
        }

        .insight-title {
            color: #0F172A;
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .insight-body {
            color: #64748B;
            font-size: 0.87rem;
            line-height: 1.6;
        }


        /* ===================================================
           DIVIDERS
        =================================================== */

        hr {
            border-color: #E2E8F0 !important;
            opacity: 0.8;
        }


        /* ===================================================
           CAPTIONS
        =================================================== */

        [data-testid="stCaptionContainer"] {
            color: #94A3B8;
            font-size: 0.8rem;
        }


        /* ===================================================
           RESPONSIVE DESIGN
        =================================================== */

        @media (max-width: 768px) {

            .block-container {
                padding-top: 3.5rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }

            .dashboard-title {
                font-size: 1.8rem;
            }

            .kpi-card {
                min-height: 145px;
                padding: 18px;
            }

            .kpi-value {
                font-size: 1.6rem;
            }

        }

        </style>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# PLOTLY THEME
# ============================================================

def apply_plotly_theme():
    pio.templates.default = "plotly_white"


# ============================================================
# INITIALIZE COMPLETE THEME
# ============================================================

def initialize_theme():
    apply_theme()
    apply_plotly_theme()