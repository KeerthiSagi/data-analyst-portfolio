"""Page 3: Revenue Driver Analysis (shell)."""

from ui.components import empty_state, page_intro
from ui.state import get_context
from views.common import scope_cards


def render() -> None:
    ctx = get_context()
    page_intro(
        "Revenue Driver Analysis",
        "Split the revenue change into order volume and average order value "
        "(Revenue = Orders × Average Order Value).",
        ctx,
    )
    if not ctx.is_ready:
        return
    scope_cards(ctx)
    empty_state(
        "Driver analysis is not built yet",
        "Volume and order-value effects, their trends and per-group breakdowns will appear here.",
    )


render()
