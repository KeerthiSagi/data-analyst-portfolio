"""Plotly chart helpers that always use the CAUSE dark template."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cause.metrics import monthly_trend
from ui import theme
from ui.filters import AnalysisContext


def show_chart(fig: go.Figure, height: int = 360, key: str | None = None) -> None:
    """Render with the CAUSE template. theme=None stops Streamlit restyling it."""
    theme.style_figure(fig, height=height)
    st.plotly_chart(fig, theme=None, config=theme.PLOTLY_CONFIG, width="stretch", key=key)


def _shade(fig: go.Figure, start, end, color: str) -> None:
    fig.add_vrect(
        x0=pd.Timestamp(start) - pd.Timedelta(days=15),
        x1=pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(days=15),
        fillcolor=color,
        opacity=0.14,
        line_width=0,
        layer="below",
    )


def scope_chart(ctx: AnalysisContext) -> go.Figure:
    """Monthly orders for the filtered data, with both windows shaded."""
    trend = monthly_trend(ctx.filtered)
    fig = go.Figure()
    if not trend.empty:
        fig.add_bar(
            x=trend["month"],
            y=trend["orders"],
            name="Orders",
            marker=dict(color=theme.ACCENT, cornerradius=4),
            hovertemplate="%{x|%b %Y}<br>%{y:,} orders<extra></extra>",
        )
    if ctx.comparison is not None:
        c = ctx.comparison
        # Windows are named in the section caption (see scope_caption), not
        # as in-chart labels, which collide when the windows are narrow.
        _shade(fig, c.comparison.start, c.comparison.end, theme.NEUTRAL)
        _shade(fig, c.current.start, c.current.end, theme.ACCENT)
    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        yaxis_title="Distinct orders",
        xaxis=dict(range=[ctx.data_range[0] - pd.Timedelta(days=20), ctx.data_range[1] + pd.Timedelta(days=5)]),
    )
    return fig


def scope_caption(ctx: AnalysisContext) -> str:
    base = "Distinct orders per month for the current filters."
    if ctx.comparison is None:
        return base
    c = ctx.comparison
    return (f"{base} Blue shading marks the current period ({c.current.label}); "
            f"grey shading marks the comparison period ({c.comparison.label}).")
