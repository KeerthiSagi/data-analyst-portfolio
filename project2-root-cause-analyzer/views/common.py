"""Pieces shared by the page modules."""

from __future__ import annotations

from cause.data import count_orders
from ui.components import kpi_card_html, kpi_row
from ui.filters import AnalysisContext


def scope_cards(ctx: AnalysisContext) -> None:
    """Order lines and distinct orders in each window (data coverage, not results)."""
    if ctx.comparison is None:
        return
    c = ctx.comparison
    kpi_row([
        kpi_card_html("Current period", c.current.label,
                      footnote=f"{c.current.start:%d %b %Y} – {c.current.end:%d %b %Y} · {c.current.days} days"),
        kpi_card_html("Comparison period", c.comparison.label,
                      footnote=f"{c.comparison.start:%d %b %Y} – {c.comparison.end:%d %b %Y} · {c.comparison.days} days"),
        kpi_card_html("Orders in scope", f"{count_orders(ctx.current):,} vs {count_orders(ctx.previous):,}",
                      footnote="Distinct orders, current vs comparison"),
        kpi_card_html("Order lines in scope", f"{len(ctx.current):,} vs {len(ctx.previous):,}",
                      footnote="Rows in the dataset, current vs comparison"),
    ])
