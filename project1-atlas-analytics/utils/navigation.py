"""Shared Project 1 navigation and page chrome for ATLAS Analytics."""

from __future__ import annotations

import html

import streamlit as st


PROJECT1_PAGES = (
    {
        "key": "executive",
        "path": "app_kpi_dashboard.py",
        "label": "Executive Overview",
    },
    {
        "key": "segment",
        "path": "pages/1_Segment_Performance.py",
        "label": "Segment Performance",
    },
    {
        "key": "regional",
        "path": "pages/2_Regional_Logistics.py",
        "label": "Regional Performance",
    },
    {
        "key": "explorer",
        "path": "pages/3_Data_Explorer.py",
        "label": "Data Explorer",
    },
)


def render_sidebar_brand() -> None:
    """Render the ATLAS brand lockup above page navigation."""

    st.sidebar.markdown(
        """
        <div class="atlas-brand">
            <div class="atlas-brand-mark"><span class="atlas-brand-accent">◈</span> ATLAS</div>
            <div class="atlas-brand-tagline">Analytics · Global sales intelligence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_nav_fallback(current: str) -> None:
    """Plain labels used when page_link cannot resolve multipage targets."""

    for page in PROJECT1_PAGES:
        current_class = " atlas-nav-current" if page["key"] == current else ""
        st.sidebar.markdown(
            f'<div class="atlas-nav-fallback{current_class}">{html.escape(page["label"])}</div>',
            unsafe_allow_html=True,
        )


def render_project_nav(current: str) -> None:
    """Render Project 1 page links with clear labels.

    Uses Streamlit page_link when the multipage app entrypoint has registered
    the targets. Falls back to static labels under AppTest or other single-file
    runs so page smoke tests keep passing.
    """

    st.sidebar.markdown('<div class="atlas-nav-label">Project 1</div>', unsafe_allow_html=True)

    try:
        for page in PROJECT1_PAGES:
            st.sidebar.page_link(
                page["path"],
                label=page["label"],
                disabled=page["key"] == current,
            )
    except Exception:
        _render_nav_fallback(current)

    st.sidebar.markdown('<div class="atlas-nav-divider"></div>', unsafe_allow_html=True)


def render_page_header(*, eyebrow: str, title: str, subtitle: str) -> None:
    """Standard ATLAS page header: eyebrow, title, subtitle."""

    st.markdown(
        f"""
        <div class="dashboard-eyebrow">{html.escape(eyebrow)}</div>
        <div class="dashboard-title">{html.escape(title)}</div>
        <div class="dashboard-subtitle">{html.escape(subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_section_nav(items: list[tuple[str, str]]) -> None:
    """In-page section jump links for long dashboards."""

    links = " · ".join(
        f'<a class="section-nav-link" href="#{anchor}">{html.escape(label)}</a>'
        for anchor, label in items
    )
    st.markdown(
        f'<div class="section-nav"><span class="section-nav-label">On this page</span>{links}</div>',
        unsafe_allow_html=True,
    )


def render_section_header(*, anchor: str, eyebrow: str, title: str, caption: str | None = None) -> None:
    """Section divider with stable anchor for in-page navigation."""

    caption_html = (
        f'<div class="section-caption">{html.escape(caption)}</div>' if caption else ""
    )
    st.markdown(
        f"""
        <div class="section-block" id="{html.escape(anchor)}">
            <div class="dashboard-eyebrow">{html.escape(eyebrow)}</div>
            <div class="section-title">{html.escape(title)}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
