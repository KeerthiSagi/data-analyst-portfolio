"""Page 4: Investigation Report (shell)."""

from ui.components import empty_state, page_intro
from ui.state import get_context
from views.common import scope_cards


def render() -> None:
    ctx = get_context()
    page_intro(
        "Investigation Report",
        "A summary of the comparison, the largest positive and negative contributors, "
        "rule-based insights and CSV downloads.",
        ctx,
    )
    if not ctx.is_ready:
        return
    scope_cards(ctx)
    empty_state(
        "The report is not built yet",
        "Summary, top contributors, insights and CSV downloads will appear here.",
    )


render()
