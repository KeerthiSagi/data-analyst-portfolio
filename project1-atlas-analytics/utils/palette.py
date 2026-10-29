"""ATLAS midnight-blue color tokens, shared with CAUSE (Project 2).

Plain constants with no Streamlit import, so the analytics modules can use
them for chart colors and tests can import them directly.
"""

from __future__ import annotations


# ------------------------------------------------------------------
# Surfaces and text
# ------------------------------------------------------------------

BACKGROUND = "#080F20"
SIDEBAR = "#0D1930"
CARD = "#142440"
CARD_RAISED = "#1A2D4F"
BORDER = "#253B5B"
ACCENT = "#4F8CFF"
ACCENT_HOVER = "#7FAEFF"
POSITIVE = "#34D399"
NEGATIVE = "#FB7185"
WARNING = "#FBBF24"
TEXT = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#7C8DA6"

# Chart scaffolding: faint gridlines, a visible zero line.
GRID = "rgba(148, 163, 184, 0.12)"
ZEROLINE = "#3A5276"

# Neutral mark for "no signal" bars (e.g. segments with no losses).
NEUTRAL_MARK = "#64748B"

FONT_STACK = (
    '"Inter", "Source Sans 3", "Source Sans Pro", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI", Roboto, Helvetica, Arial, sans-serif'
)


# ------------------------------------------------------------------
# Categorical order (same as CAUSE). Assign in order, never cycle.
# ------------------------------------------------------------------

CATEGORICAL = [
    ACCENT,     # blue
    "#D95926",  # orange
    "#199E70",  # teal green
    "#C98500",  # amber
    "#D55181",  # pink
    "#008300",  # green
    "#9085E9",  # lavender
    "#E66767",  # salmon
]

# Metric identity colors. Green and red stay reserved for good/bad deltas.
REVENUE_COLOR = CATEGORICAL[0]
PROFIT_COLOR = CATEGORICAL[1]
MARGIN_COLOR = CATEGORICAL[6]
ORDERS_COLOR = CATEGORICAL[2]
SHIP_COST_COLOR = CATEGORICAL[6]
SHIP_RATIO_COLOR = CATEGORICAL[3]
SHIP_DAYS_COLOR = CATEGORICAL[2]

# Five extra region colors so all 13 regions keep a distinct, fixed color.
# Checked on the card surface: contrast >= 3:1, distinct from the base eight.
REGION_EXTRA = ["#3FD0DC", "#F2A7D8", "#D3D660", "#C4BFFF", "#6B7A90"]


# ------------------------------------------------------------------
# Plotly layout pieces used by every chart builder
# ------------------------------------------------------------------

CHART_FONT = dict(family=FONT_STACK, color=TEXT, size=13)

CHART_HOVERLABEL = dict(
    bgcolor=SIDEBAR,
    bordercolor=BORDER,
    font=dict(family=FONT_STACK, color=TEXT, size=12),
    align="left",
)

