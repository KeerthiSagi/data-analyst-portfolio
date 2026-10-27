"""Phase 7 UI/UX polish contracts for Project 1 navigation and chrome."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.navigation import PROJECT1_PAGES, render_page_header, render_project_nav, render_sidebar_brand


class NavigationContractTests(unittest.TestCase):
    def test_project1_pages_cover_four_surfaces(self):
        labels = [page["label"] for page in PROJECT1_PAGES]
        self.assertEqual(
            labels,
            [
                "Executive Overview",
                "Segment Performance",
                "Regional Performance",
                "Data Explorer",
            ],
        )
        paths = [page["path"] for page in PROJECT1_PAGES]
        self.assertTrue((ROOT / paths[0]).exists())
        for path in paths[1:]:
            self.assertTrue((ROOT / path).exists())

    def test_pages_use_shared_navigation(self):
        sources = [
            (ROOT / "app_kpi_dashboard.py").read_text(),
            (ROOT / "pages" / "1_Segment_Performance.py").read_text(),
            (ROOT / "pages" / "2_Regional_Logistics.py").read_text(),
            (ROOT / "pages" / "3_Data_Explorer.py").read_text(),
        ]
        for source in sources:
            self.assertIn("render_sidebar_brand", source)
            self.assertIn("render_project_nav", source)
            self.assertIn("render_page_header", source)

    def test_theme_defines_atlas_plotly_and_nav_chrome(self):
        theme = (ROOT / "utils" / "theme.py").read_text()
        self.assertIn("plotly_white+atlas", theme)
        self.assertIn("atlas-brand", theme)
        self.assertIn("section-nav", theme)
        self.assertTrue(callable(render_sidebar_brand))
        self.assertTrue(callable(render_project_nav))
        self.assertTrue(callable(render_page_header))

    def test_regional_page_keeps_both_sections_visible(self):
        source = (ROOT / "pages" / "2_Regional_Logistics.py").read_text()
        self.assertIn("render_section_nav", source)
        self.assertIn("regional-performance", source)
        self.assertIn("shipping-logistics", source)
        self.assertIn("Regional Performance Intelligence", source)
        self.assertIn("SHIPPING", source)
        self.assertIn("LOGISTICS INTELLIGENCE", source)
        self.assertIn("calculate_logistics_kpis", source)


if __name__ == "__main__":
    unittest.main()
