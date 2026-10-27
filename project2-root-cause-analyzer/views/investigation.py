"""Page 2: Root Cause Investigation (shell)."""

from ui.components import empty_state, page_intro
from ui.state import get_context
from views.common import scope_cards


def render() -> None:
    ctx = get_context()
    page_intro(
        "Root Cause Investigation",
        "Find which markets, regions, categories and segments account for a metric's change, "
        "and drill into combinations of them.",
        ctx,
    )
    if not ctx.is_ready:
        return
    scope_cards(ctx)
    empty_state(
        "Contribution analysis is not built yet",
        "Metric selector, contribution charts by dimension, two-level drill-down, waterfall "
        "and generated findings will appear here.",
    )


render()
