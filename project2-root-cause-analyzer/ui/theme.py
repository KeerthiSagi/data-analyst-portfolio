"""Midnight-blue design tokens, page CSS, and the Plotly template.

The native theme lives in .streamlit/config.toml. The CSS here only adds
what config cannot express (cards, typography, spacing) and repeats the
core colors so the look holds even if another config takes precedence.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ------------------------------------------------------------------
# Tokens
# ------------------------------------------------------------------

BACKGROUND = "#080F20"
SIDEBAR = "#0D1930"
CARD = "#142440"
CARD_RAISED = "#1A2D4F"
BORDER = "#253B5B"
ACCENT = "#4F8CFF"
POSITIVE = "#34D399"
NEGATIVE = "#FB7185"
WARNING = "#FBBF24"
TEXT = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#7C8DA6"
GRID = "rgba(148, 163, 184, 0.12)"

# Fixed categorical order (validated dark steps from the dataviz reference
# palette; slot 1 is the brand accent). Assign in order, never cycle.
CATEGORICAL = [ACCENT, "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]

# Neutral for "comparison period" / totals in charts.
NEUTRAL = "#64748B"

FONT_STACK = (
    '"Inter", "Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    "Roboto, Helvetica, Arial, sans-serif"
)

# ------------------------------------------------------------------
# Plotly
# ------------------------------------------------------------------

TEMPLATE_NAME = "cause_dark"


def _build_template() -> go.layout.Template:
    axis = dict(
        gridcolor=GRID,
        zerolinecolor=BORDER,
        linecolor=BORDER,
        tickcolor=BORDER,
        tickfont=dict(color=TEXT_SECONDARY, size=12),
        title=dict(font=dict(color=TEXT_SECONDARY, size=12)),
        automargin=True,
    )
    return go.layout.Template(
        layout=dict(
            # Explicit card colour: Streamlit fills transparent chart
            # backgrounds with its own theme colours.
            paper_bgcolor=CARD,
            plot_bgcolor=CARD,
            font=dict(family=FONT_STACK, color=TEXT, size=13),
            title=dict(font=dict(size=15, color=TEXT), x=0, xanchor="left"),
            colorway=CATEGORICAL,
            xaxis={**axis, "showgrid": False},
            yaxis={**axis, "showgrid": True},
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color=TEXT_SECONDARY, size=12),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            hoverlabel=dict(
                bgcolor=SIDEBAR,
                bordercolor=BORDER,
                font=dict(color=TEXT, family=FONT_STACK, size=12),
            ),
            hovermode="x unified",
            margin=dict(l=8, r=8, t=40, b=8),
            bargap=0.35,
        )
    )


pio.templates[TEMPLATE_NAME] = _build_template()


def style_figure(fig: go.Figure, height: int = 360) -> go.Figure:
    """Apply the CAUSE template and standard sizing to a figure.

    Backgrounds are also set directly on the figure: Streamlit fills in any
    background the figure itself leaves unset, ignoring template values.
    """
    fig.update_layout(template=TEMPLATE_NAME, height=height, paper_bgcolor=CARD, plot_bgcolor=CARD)
    return fig


# Passed to st.plotly_chart: hide the Plotly logo and keep the toolbar lean.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
}


# ------------------------------------------------------------------
# Page CSS
# ------------------------------------------------------------------

CSS = f"""
<style>
:root {{
  --cause-bg: {BACKGROUND};
  --cause-sidebar: {SIDEBAR};
  --cause-card: {CARD};
  --cause-card-raised: {CARD_RAISED};
  --cause-border: {BORDER};
  --cause-accent: {ACCENT};
  --cause-positive: {POSITIVE};
  --cause-negative: {NEGATIVE};
  --cause-warning: {WARNING};
  --cause-text: {TEXT};
  --cause-text-2: {TEXT_SECONDARY};
  --cause-text-3: {TEXT_MUTED};
}}

/* ---------- Surfaces ---------- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
  background: var(--cause-bg);
  color: var(--cause-text);
}}
[data-testid="stSidebar"] {{
  background: var(--cause-sidebar);
  border-right: 1px solid var(--cause-border);
}}
.block-container {{
  padding-top: 3.5rem;
  padding-bottom: 3rem;
  max-width: 1400px;
}}

/* ---------- Typography ---------- */
h1, h2, h3, h4 {{ color: var(--cause-text); letter-spacing: -0.01em; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: var(--cause-text-2); }}

/* ---------- Section cards (containers created by components.section) ---------- */
[class*="st-key-cause-section"] {{
  background: var(--cause-card);
  border-color: var(--cause-border) !important;
  border-radius: 12px;
  padding: 1.1rem 1.2rem 0.6rem 1.2rem;
}}

/* ---------- Inputs (backup for the native theme) ---------- */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {{
  background-color: var(--cause-card);
  border-color: var(--cause-border);
}}
[data-baseweb="popover"] ul, [data-baseweb="menu"] {{
  background-color: var(--cause-card-raised);
}}
[data-baseweb="tag"] {{
  background-color: rgba(79, 140, 255, 0.18) !important;
  color: var(--cause-text) !important;
}}
[data-baseweb="tag"] span {{ color: var(--cause-text) !important; }}

/* ---------- Expander ---------- */
[data-testid="stExpander"] details {{
  background: var(--cause-card);
  border-color: var(--cause-border);
}}

/* ---------- Custom components ---------- */
.cause-eyebrow {{
  color: var(--cause-accent);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}}
.cause-title {{
  font-size: 1.85rem;
  font-weight: 700;
  line-height: 1.2;
  margin: 0 0 0.35rem 0;
  color: var(--cause-text);
}}
.cause-subtitle {{
  color: var(--cause-text-2);
  font-size: 0.98rem;
  max-width: 62rem;
  margin: 0;
}}
.cause-header {{ margin-bottom: 1.25rem; }}

.cause-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.9rem;
  margin: 0.25rem 0 1rem 0;
}}
.cause-card {{
  background: var(--cause-card);
  border: 1px solid var(--cause-border);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  min-width: 0;
}}
.cause-kpi-label {{
  color: var(--cause-text-2);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.cause-kpi-value {{
  color: var(--cause-text);
  font-size: 1.7rem;
  font-weight: 700;
  line-height: 1.25;
  margin-top: 0.3rem;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}}
.cause-kpi-delta {{
  font-size: 0.86rem;
  margin-top: 0.35rem;
  font-variant-numeric: tabular-nums;
}}
.cause-kpi-foot {{
  color: var(--cause-text-3);
  font-size: 0.78rem;
  margin-top: 0.3rem;
}}
.cause-tone-positive {{ color: var(--cause-positive); }}
.cause-tone-negative {{ color: var(--cause-negative); }}
.cause-tone-neutral  {{ color: var(--cause-text-2); }}
.cause-tone-caution  {{ color: var(--cause-warning); }}

.cause-card.cause-flag {{ border-color: rgba(251, 191, 36, 0.55); }}
.cause-badge {{
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  margin-left: 0.4rem;
  vertical-align: middle;
  background: rgba(251, 191, 36, 0.14);
  color: var(--cause-warning);
}}

.cause-callout {{
  background: var(--cause-card);
  border: 1px solid var(--cause-border);
  border-left: 3px solid var(--cause-accent);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0;
}}
.cause-callout.positive {{ border-left-color: var(--cause-positive); }}
.cause-callout.negative {{ border-left-color: var(--cause-negative); }}
.cause-callout.caution  {{ border-left-color: var(--cause-warning); }}
.cause-callout-title {{ font-weight: 600; color: var(--cause-text); margin-bottom: 0.2rem; }}
.cause-callout-body  {{ color: var(--cause-text-2); font-size: 0.93rem; line-height: 1.5; }}

.cause-empty {{
  background: var(--cause-card);
  border: 1px dashed var(--cause-border);
  border-radius: 12px;
  padding: 2rem 1.5rem;
  text-align: center;
}}
.cause-empty-title {{ font-weight: 600; font-size: 1.05rem; color: var(--cause-text); }}
.cause-empty-body  {{ color: var(--cause-text-2); margin-top: 0.35rem; font-size: 0.93rem; }}

.cause-chips {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.15rem 0 1rem 0; }}
.cause-chip {{
  background: var(--cause-card);
  border: 1px solid var(--cause-border);
  border-radius: 999px;
  padding: 0.22rem 0.7rem;
  font-size: 0.8rem;
  color: var(--cause-text-2);
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.cause-chip b {{ color: var(--cause-text); font-weight: 600; }}
.cause-chip.period b {{ color: var(--cause-accent); }}

.cause-brand {{
  display: flex; align-items: baseline; gap: 0.5rem;
  margin: 0.1rem 0 0.2rem 0;
}}
.cause-brand-name {{ font-weight: 800; font-size: 1.15rem; letter-spacing: 0.12em; color: var(--cause-text); }}
.cause-brand-tag {{ color: var(--cause-text-2); font-size: 0.78rem; }}
.cause-side-label {{
  color: var(--cause-text-2);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 0.9rem 0 0.25rem 0;
}}
.cause-side-meta {{ color: var(--cause-text-3); font-size: 0.76rem; line-height: 1.45; }}

@media (max-width: 640px) {{
  .cause-title {{ font-size: 1.45rem; }}
  .cause-kpi-value {{ font-size: 1.4rem; }}
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
}}
</style>
"""
