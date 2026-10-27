"""Phase 8 QA regression: independent reconciliation, isolation, export, layout."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_explorer import (
    COUNTRY_SCOPE_ALL,
    DEFAULT_VISIBLE_COLUMNS,
    PREVIEW_ROW_LIMIT,
    available_columns,
    calculate_explorer_kpis,
    filter_explorer_data,
    prepare_csv_export,
    prepare_display_frame,
    resolve_country_selection,
    search_explorer_data,
)
from utils.data_loader import load_superstore_data
from utils.executive_analytics import TREND_REVENUE, build_performance_bar, summarize_groups
from utils.logistics_analytics import (
    calculate_logistics_kpis,
    calculate_processing_intervals,
    filter_shipping_modes,
)
from utils.regional_analytics import calculate_regional_kpis, filter_orders
from utils.segment_analytics import aggregate_segment_performance, build_segment_comparison


class IndependentReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.independent = {
            "line_items": len(cls.df),
            "orders": int(cls.df["Order_ID"].nunique()),
            "revenue": float(cls.df["Sales"].sum()),
            "profit": float(cls.df["Profit"].sum()),
            "margin": float(cls.df["Profit"].sum()) / float(cls.df["Sales"].sum()) * 100,
            "shipping_cost": float(cls.df["Shipping_Cost"].sum()),
            "shipping_cost_ratio": float(cls.df["Shipping_Cost"].sum())
            / float(cls.df["Sales"].sum())
            * 100,
        }

    def test_published_totals_match_independent_pandas(self):
        self.assertEqual(self.independent["line_items"], 51_290)
        self.assertEqual(self.independent["orders"], 25_035)
        self.assertAlmostEqual(self.independent["revenue"], 12_642_905.0, places=0)
        self.assertAlmostEqual(self.independent["profit"], 1_467_457.29, places=2)
        self.assertAlmostEqual(self.independent["margin"], 11.61, places=2)
        self.assertAlmostEqual(self.independent["shipping_cost"], 1_352_815.70, places=2)
        self.assertAlmostEqual(self.independent["shipping_cost_ratio"], 10.70, places=2)

    def test_module_kpis_match_independent_totals(self):
        start = self.df["Order_Date"].min().date()
        end = self.df["Order_Date"].max().date()
        regions = sorted(self.df["Region"].dropna().unique())
        categories = sorted(self.df["Category"].dropna().unique())
        segments = sorted(self.df["Segment"].dropna().unique())
        modes = sorted(self.df["Ship_Mode"].dropna().unique())
        countries = sorted(self.df["Country"].dropna().unique())

        page = filter_orders(
            self.df,
            start=start,
            end=end,
            regions=regions,
            categories=categories,
            segments=segments,
        )
        explorer = filter_explorer_data(
            self.df,
            start=start,
            end=end,
            regions=regions,
            countries=resolve_country_selection(
                countries, scope=COUNTRY_SCOPE_ALL, selected=[]
            ),
            categories=categories,
            sub_categories=sorted(self.df["Sub_Category"].dropna().unique()),
            segments=segments,
            ship_modes=modes,
        )
        regional = calculate_regional_kpis(page)
        logistics = calculate_logistics_kpis(page)
        explorer_kpis = calculate_explorer_kpis(explorer)

        self.assertAlmostEqual(regional["revenue"], self.independent["revenue"], places=2)
        self.assertAlmostEqual(regional["profit"], self.independent["profit"], places=2)
        self.assertEqual(regional["orders"], self.independent["orders"])
        self.assertAlmostEqual(
            logistics["shipping_cost"], self.independent["shipping_cost"], places=4
        )
        self.assertAlmostEqual(
            logistics["shipping_cost_ratio"],
            self.independent["shipping_cost_ratio"],
            places=4,
        )
        self.assertEqual(explorer_kpis["line_items"], self.independent["line_items"])
        self.assertEqual(explorer_kpis["orders"], self.independent["orders"])


class LogisticsIsolationAndProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.start = cls.df["Order_Date"].min().date()
        cls.end = cls.df["Order_Date"].max().date()
        cls.regions = sorted(cls.df["Region"].dropna().unique())
        cls.categories = sorted(cls.df["Category"].dropna().unique())
        cls.segments = sorted(cls.df["Segment"].dropna().unique())
        cls.modes = sorted(cls.df["Ship_Mode"].dropna().unique())
        cls.filtered = filter_orders(
            cls.df,
            start=cls.start,
            end=cls.end,
            regions=cls.regions,
            categories=cls.categories,
            segments=cls.segments,
        )

    def test_shipping_mode_filter_does_not_change_regional_kpis(self):
        before = calculate_regional_kpis(self.filtered)
        _ = calculate_logistics_kpis(filter_shipping_modes(self.filtered, ["Same Day"]))
        after = calculate_regional_kpis(self.filtered)
        self.assertEqual(before, after)
        all_modes = calculate_logistics_kpis(filter_shipping_modes(self.filtered, self.modes))
        same_day = calculate_logistics_kpis(filter_shipping_modes(self.filtered, ["Same Day"]))
        self.assertNotEqual(all_modes["shipping_cost"], same_day["shipping_cost"])

    def test_processing_intervals_are_non_negative_and_complete(self):
        intervals = calculate_processing_intervals(self.df)
        self.assertEqual(int(intervals["interval_missing"].sum()), 0)
        self.assertEqual(int(intervals["interval_negative"].sum()), 0)
        self.assertEqual(int(intervals["interval_valid"].sum()), len(self.df))
        valid_days = intervals.loc[intervals["interval_valid"], "processing_days"]
        self.assertTrue((valid_days >= 0).all())
        self.assertTrue(
            (
                valid_days.values
                == self.df.loc[intervals["interval_valid"], "Shipping_Days"].astype(float).values
            ).all()
        )


class ExplorerExportAndSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_csv_export_includes_all_filtered_rows_not_preview(self):
        start = self.df["Order_Date"].min().date()
        end = self.df["Order_Date"].max().date()
        subset = filter_explorer_data(
            self.df,
            start=start,
            end=end,
            regions=["Central", "South", "West", "East", "North"],
            countries=resolve_country_selection(
                sorted(self.df["Country"].dropna().unique()),
                scope=COUNTRY_SCOPE_ALL,
                selected=[],
            ),
            categories=sorted(self.df["Category"].dropna().unique()),
            sub_categories=sorted(self.df["Sub_Category"].dropna().unique()),
            segments=sorted(self.df["Segment"].dropna().unique()),
            ship_modes=sorted(self.df["Ship_Mode"].dropna().unique()),
        )
        self.assertGreater(len(subset), PREVIEW_ROW_LIMIT)
        preview = prepare_display_frame(subset, DEFAULT_VISIBLE_COLUMNS, limit=PREVIEW_ROW_LIMIT)
        payload = prepare_csv_export(subset)
        exported = pd.read_csv(StringIO(payload.decode("utf-8")))
        self.assertEqual(len(exported), len(subset))
        self.assertEqual(preview["preview_rows"], PREVIEW_ROW_LIMIT)
        self.assertLess(preview["preview_rows"], len(exported))
        self.assertEqual(float(exported["Sales"].sum()), float(subset["Sales"].sum()))

    def test_search_is_case_insensitive_partial_and_scoped(self):
        sample = self.df["Customer_Name"].dropna().iloc[0]
        west = self.df[self.df["Region"] == "West"]
        hits = search_explorer_data(west, sample[:4].upper())
        self.assertGreater(len(hits), 0)
        self.assertTrue((hits["Region"] == "West").all())


class ChartLayoutRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_three_category_charts_use_compact_bars(self):
        segments = aggregate_segment_performance(self.df)
        segment_fig = build_segment_comparison(segments, "Revenue")
        self.assertEqual(len(segments), 3)
        self.assertEqual(segment_fig.layout.height, 260)
        self.assertGreaterEqual(float(segment_fig.layout.bargap), 0.65)
        self.assertGreaterEqual(int(segment_fig.layout.margin.b or 0), 48)

        categories = summarize_groups(self.df, "Category")
        category_fig = build_performance_bar(categories, TREND_REVENUE, "v")
        self.assertEqual(len(categories), 3)
        self.assertLessEqual(int(category_fig.layout.height), 300)
        self.assertGreaterEqual(float(category_fig.layout.bargap), 0.55)


class NavigationAndThemeContractTests(unittest.TestCase):
    def test_project1_navigation_excludes_project_2_and_3(self):
        from utils.navigation import PROJECT1_PAGES

        labels = [page["label"] for page in PROJECT1_PAGES]
        self.assertEqual(len(labels), 4)
        joined = " ".join(labels).lower()
        self.assertNotIn("root cause", joined)
        self.assertNotIn("data cleaner", joined)
        self.assertNotIn("project 2", joined)
        self.assertNotIn("project 3", joined)

    def test_pages_do_not_use_stretch_height_on_kpi_containers(self):
        sources = [
            (ROOT / "app_kpi_dashboard.py").read_text(),
            (ROOT / "pages" / "1_Segment_Performance.py").read_text(),
            (ROOT / "pages" / "2_Regional_Logistics.py").read_text(),
            (ROOT / "pages" / "3_Data_Explorer.py").read_text(),
        ]
        for source in sources:
            self.assertNotIn('height="stretch", gap="xxsmall"', source)


if __name__ == "__main__":
    unittest.main()
