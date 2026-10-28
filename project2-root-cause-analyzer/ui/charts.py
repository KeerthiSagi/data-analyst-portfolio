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


# ------------------------------------------------------------------
# Phase 4 chart builders (figures only; data comes from ui/chart_data.py)
# ------------------------------------------------------------------

REVENUE_COLOR = theme.CATEGORICAL[0]   # blue
PROFIT_COLOR = theme.CATEGORICAL[1]    # orange
SECOND_COLOR = theme.CATEGORICAL[1]


def _shade_windows(fig: go.Figure, ctx: AnalysisContext) -> None:
    if ctx.comparison is not None:
        _shade(fig, ctx.comparison.comparison.start, ctx.comparison.comparison.end, theme.NEUTRAL)
        _shade(fig, ctx.comparison.current.start, ctx.comparison.current.end, theme.ACCENT)


def windows_caption(ctx: AnalysisContext, base: str) -> str:
    if ctx.comparison is None:
        return base
    c = ctx.comparison
    return (f"{base} Blue shading: current period ({c.current.label}). "
            f"Grey shading: comparison period ({c.comparison.label}).")


def trend_chart(trend: pd.DataFrame, ctx: AnalysisContext, series: list[tuple[str, str, str]],
                money: bool = True, percent: bool = False) -> go.Figure:
    """Line chart of monthly series. `series` = [(column, name, color)]."""
    fig = go.Figure()
    fmt = "$%{y:,.0f}" if money else ("%{y:.1%}" if percent else "%{y:,.0f}")
    for col, name, color in series:
        fig.add_scatter(
            x=trend["month"], y=trend[col], name=name, mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=5, color=color),
            connectgaps=False,
            hovertemplate=f"{name}: {fmt}<extra></extra>",
        )
    _shade_windows(fig, ctx)
    fig.update_layout(
        showlegend=len(series) > 1,
        hovermode="x unified",
        xaxis=dict(hoverformat="%b %Y"),
        yaxis=dict(tickprefix="$" if money else "", tickformat=".0%" if percent else ",.0f",
                   zeroline=True),
    )
    return fig


def grouped_bars(df: pd.DataFrame, label_col: str, series: list[tuple[str, str, str]],
                 horizontal: bool = True, money: bool = True) -> go.Figure:
    """Grouped bars, one bar per series per group, in the frame's row order."""
    fig = go.Figure()
    labels = df[label_col].astype(str).tolist()
    for col, name, color in series:
        values = df[col].tolist()
        kwargs = dict(name=name, marker=dict(color=color, cornerradius=4),
                      hovertemplate=f"%{{{'y' if horizontal else 'x'}}}<br>{name}: "
                                    + ("$%{" + ("x" if horizontal else "y") + ":,.0f}" if money
                                       else "%{" + ("x" if horizontal else "y") + ":,.1f}")
                                    + "<extra></extra>")
        if horizontal:
            fig.add_bar(y=labels, x=values, orientation="h", **kwargs)
        else:
            fig.add_bar(x=labels, y=values, **kwargs)
    axis = dict(tickprefix="$" if money else "", tickformat=",.0f", zeroline=True,
                zerolinecolor=theme.TEXT_MUTED, showgrid=True)
    if horizontal:
        fig.update_layout(barmode="group", hovermode="closest", xaxis=axis,
                          yaxis=dict(autorange="reversed", showgrid=False))
    else:
        fig.update_layout(barmode="group", hovermode="closest", yaxis=axis)
    return fig


def waterfall_chart(steps: pd.DataFrame, metric_label: str, money: bool = True,
                    decimals: int = 0) -> go.Figure:
    """Plotly waterfall from chart_data.waterfall_steps-style frames."""
    fmt = f",.{decimals}f"
    prefix = "$" if money else ""

    def text(v, kind):
        sign = "+" if kind == "increase" and v > 0 else ("−" if v < 0 else "")
        return f"{sign}{prefix}{abs(v):{fmt}}"

    fig = go.Figure(go.Waterfall(
        x=steps["label"],
        measure=steps["measure"],
        y=steps["value"],
        text=[text(v, k) for v, k in zip(steps["value"], steps["kind"])],
        textposition="outside",
        textfont=dict(color=theme.TEXT_SECONDARY, size=11),
        cliponaxis=False,
        connector=dict(line=dict(color=theme.BORDER, width=1)),
        increasing=dict(marker=dict(color=theme.POSITIVE)),
        decreasing=dict(marker=dict(color=theme.NEGATIVE)),
        totals=dict(marker=dict(color=theme.ACCENT)),
        hovertemplate="%{x}<br>" + metric_label + ": %{text}<extra></extra>",
    ))
    fig.update_layout(
        showlegend=False, hovermode="closest",
        yaxis=dict(tickprefix=prefix, tickformat=",.0f"),
        xaxis=dict(tickangle=-30 if len(steps) > 6 else 0),
        margin=dict(t=30),
    )
    return fig


def effects_chart(long: pd.DataFrame, colors: dict[str, str], unit: str,
                  money: bool = False) -> go.Figure:
    """Diverging horizontal stacked bars of effects per group (pp or $)."""
    fig = go.Figure()
    groups = list(dict.fromkeys(long["group"]))
    for effect, color in colors.items():
        part = long[long["effect"] == effect].set_index("group").reindex(groups)
        hover = ("%{y}<br>" + effect + ": " + ("$%{x:,.0f}" if money else "%{x:+.2f} " + unit)
                 + "<extra></extra>")
        fig.add_bar(y=groups, x=part["value"], name=effect, orientation="h",
                    marker=dict(color=color, cornerradius=3), hovertemplate=hover)
    fig.update_layout(
        barmode="relative", hovermode="closest",
        yaxis=dict(autorange="reversed", showgrid=False),
        xaxis=dict(title=unit if not money else None, tickprefix="$" if money else "",
                   tickformat=",.0f" if money else "+.1f", zeroline=True,
                   zerolinecolor=theme.TEXT_MUTED, showgrid=True),
    )
    return fig
