"""Page 1: Metric Overview (shell; KPIs and trends are added in the next phase)."""

from ui.charts import scope_caption, scope_chart, show_chart
from ui.components import empty_state, page_intro, section
from ui.state import get_context
from views.common import scope_cards


def render() -> None:
    ctx = get_context()
    page_intro(
        "Metric Overview",
        "Revenue, profit, orders and margin for the selected period, compared with the "
        "comparison period, plus monthly trends.",
        ctx,
    )
    if not ctx.is_ready:
        return
    scope_cards(ctx)
    with section("Data in scope", scope_caption(ctx)):
        if ctx.filtered.empty:
            empty_state("No data for these filters", "Widen or reset the filters in the sidebar.")
        else:
            show_chart(scope_chart(ctx), height=300, key="overview_scope")
    empty_state(
        "KPI cards and trends are not built yet",
        "Revenue, profit, orders and margin comparisons, monthly trends and notable-change "
        "highlights will appear here.",
    )


render()
