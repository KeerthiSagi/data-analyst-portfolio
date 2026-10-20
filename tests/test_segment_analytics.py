"""Customer segment KPI and filter checks for Phase 4A."""

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
from utils.segment_analytics import (
    aggregate_segment_performance,
    build_segment_comparison,
    calculate_segment_kpis,
    calculate_segment_profitability,
    calculate_segment_revenue_share,
    filter_orders,
    profitability_highlights,
)

PAGE_SOURCE = (ROOT / "pages" / "1_Segment_Performance.py").read_text()
ANALYTICS_SOURCE = (ROOT / "utils" / "segment_analytics.py").read_text()


def _frame(rows):
    frame = pd.DataFrame(rows)
    frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    return frame


class SegmentKpiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.start = cls.df["Order_Date"].min().date()
        cls.end = cls.df["Order_Date"].max().date()
        cls.regions = sorted(cls.df["Region"].dropna().unique())
        cls.categories = sorted(cls.df["Category"].dropna().unique())
        cls.segments = sorted(cls.df["Segment"].dropna().unique())

    def _filtered(self, **overrides):
        params = dict(
            start=self.start,
            end=self.end,
            regions=self.regions,
            categories=self.categories,
            segments=self.segments,
        )
        params.update(overrides)
        return filter_orders(self.df, **params)

    def test_full_dataset_kpis(self):
        kpis = calculate_segment_kpis(self.df)
        orders = int(self.df["Order_ID"].nunique())

        self.assertAlmostEqual(kpis["revenue"], 12642905, places=2)
        self.assertAlmostEqual(kpis["profit"], 1467457.29, places=2)
        self.assertAlmostEqual(kpis["margin"], 11.61, places=2)
        self.assertEqual(kpis["orders"], 25035)
        self.assertEqual(orders, 25035)
        self.assertNotEqual(orders, len(self.df))
        self.assertAlmostEqual(kpis["aov"], 12642905 / 25035, places=2)
        self.assertNotAlmostEqual(kpis["aov"], float(self.df["Sales"].mean()), places=2)

    def test_segment_revenue_and_profit_reconcile(self):
        performance = aggregate_segment_performance(self.df)

        self.assertAlmostEqual(performance["revenue"].sum(), 12642905, places=2)
        self.assertAlmostEqual(performance["profit"].sum(), 1467457.29, places=2)
        self.assertAlmostEqual(performance["revenue_share"].sum(), 100, places=2)
        self.assertEqual(
            set(performance["segment"]),
            {"Consumer", "Corporate", "Home Office"},
        )
        for row in performance.to_dict("records"):
            self.assertAlmostEqual(
                row["margin"],
                row["profit"] / row["revenue"] * 100,
                places=6,
            )
            self.assertAlmostEqual(row["aov"], row["revenue"] / row["orders"], places=6)
            self.assertEqual(
                row["orders"],
                int(self.df.loc[self.df["Segment"] == row["segment"], "Order_ID"].nunique()),
            )

    def test_revenue_share_helper_matches_the_table(self):
        performance = aggregate_segment_performance(self.df)
        share = calculate_segment_revenue_share(performance["revenue"])
        self.assertTrue(share.round(6).equals(performance["revenue_share"].round(6)))

    def test_aov_uses_distinct_orders_not_line_means(self):
        frame = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 2, "Segment": "Consumer", "Region": "Central", "Category": "Furniture"},
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 30, "Profit": 1, "Segment": "Consumer", "Region": "Central", "Category": "Furniture"},
            ]
        )
        kpis = calculate_segment_kpis(frame)
        self.assertEqual(kpis["orders"], 1)
        self.assertAlmostEqual(kpis["aov"], 40)
        self.assertNotAlmostEqual(kpis["aov"], float(frame["Sales"].mean()))

    def test_overlapping_orders_are_not_forced_to_the_total(self):
        frame = _frame(
            [
                {"Order_Date": "2014-02-01", "Order_ID": "A", "Sales": 10, "Profit": 4, "Segment": "Consumer", "Region": "East", "Category": "Technology"},
                {"Order_Date": "2014-02-01", "Order_ID": "A", "Sales": 15, "Profit": -2, "Segment": "Corporate", "Region": "East", "Category": "Technology"},
            ]
        )
        performance = aggregate_segment_performance(frame)
        self.assertEqual(int(performance["orders"].sum()), 2)
        self.assertEqual(int(frame["Order_ID"].nunique()), 1)
        self.assertNotEqual(int(performance["orders"].sum()), int(frame["Order_ID"].nunique()))

    def test_single_segment_selection(self):
        consumer = self._filtered(segments=["Consumer"])
        performance = aggregate_segment_performance(consumer)
        kpis = calculate_segment_kpis(consumer)

        self.assertEqual(performance["segment"].tolist(), ["Consumer"])
        self.assertAlmostEqual(float(performance["revenue_share"].iloc[0]), 100, places=4)
        self.assertAlmostEqual(kpis["revenue"], float(consumer["Sales"].sum()), places=2)
        self.assertEqual(kpis["orders"], int(consumer["Order_ID"].nunique()))

    def test_empty_and_zero_revenue(self):
        empty = self._filtered(segments=[])
        self.assertTrue(empty.empty)
        empty_kpis = calculate_segment_kpis(empty)
        self.assertEqual(empty_kpis["orders"], 0)
        self.assertIsNone(empty_kpis["margin"])
        self.assertIsNone(empty_kpis["aov"])
        self.assertTrue(aggregate_segment_performance(empty).empty)

        zero = _frame(
            [
                {"Order_Date": "2014-03-01", "Order_ID": "Z", "Sales": 0, "Profit": -8, "Segment": "Home Office", "Region": "South", "Category": "Furniture"},
            ]
        )
        zero_kpis = calculate_segment_kpis(zero)
        zero_rows = aggregate_segment_performance(zero)
        self.assertIsNone(zero_kpis["margin"])
        self.assertEqual(zero_kpis["aov"], 0)
        self.assertTrue(pd.isna(zero_rows["margin"].iloc[0]))
        self.assertTrue(pd.isna(zero_rows["revenue_share"].iloc[0]))
        self.assertTrue(calculate_segment_revenue_share(zero_rows["revenue"]).isna().all())

    def test_negative_profit_is_preserved(self):
        frame = _frame(
            [
                {"Order_Date": "2014-04-01", "Order_ID": "A", "Sales": 100, "Profit": 25, "Segment": "Consumer", "Region": "West", "Category": "Office Supplies"},
                {"Order_Date": "2014-04-02", "Order_ID": "B", "Sales": 80, "Profit": -40, "Segment": "Corporate", "Region": "West", "Category": "Office Supplies"},
            ]
        )
        performance = aggregate_segment_performance(frame)
        corporate = performance.loc[performance["segment"] == "Corporate"].iloc[0]
        figure = build_segment_comparison(performance, "Profit")
        findings = calculate_segment_profitability(performance)
        text = " ".join(note["body"] for note in profitability_highlights(performance))

        self.assertLess(float(corporate["profit"]), 0)
        self.assertLess(float(corporate["margin"]), 0)
        self.assertTrue(pd.isna(performance["profit_share"]).all())
        self.assertIn("#DC2626", list(figure.data[0].marker.color))
        self.assertIn("Corporate", text)
        self.assertIn("negative profit", text.lower())
        self.assertFalse(findings["profit_share_available"])

    def test_date_region_category_and_segment_filters(self):
        full_revenue = float(self.df["Sales"].sum())
        year = self._filtered(start=date(2014, 1, 1), end=date(2014, 12, 31))
        central = self._filtered(regions=["Central"])
        technology = self._filtered(categories=["Technology"])
        home = self._filtered(segments=["Home Office"])

        self.assertLess(float(year["Sales"].sum()), full_revenue)
        self.assertLess(float(central["Sales"].sum()), full_revenue)
        self.assertLess(float(technology["Sales"].sum()), full_revenue)
        self.assertLess(float(home["Sales"].sum()), full_revenue)
        self.assertTrue(set(central["Region"].unique()) <= {"Central"})
        self.assertTrue(set(technology["Category"].unique()) <= {"Technology"})
        self.assertTrue(set(home["Segment"].unique()) <= {"Home Office"})
        self.assertGreater(len(year), 0)
        self.assertGreater(len(central), 0)

    def test_margin_chart_does_not_share_an_axis_with_currency(self):
        performance = aggregate_segment_performance(self.df)
        figure = build_segment_comparison(performance, "Profit Margin")
        self.assertTrue(str(figure.layout.xaxis.ticksuffix).endswith("%"))
        self.assertNotIn("$", str(figure.layout.xaxis.tickformat or ""))


class SegmentPageTests(unittest.TestCase):
    def test_page_uses_distinct_orders_for_aov(self):
        self.assertIn("calculate_segment_kpis", PAGE_SOURCE)
        self.assertIn('("Order_ID", "nunique")', ANALYTICS_SOURCE)
        self.assertNotIn("len(filtered)", PAGE_SOURCE)
        self.assertNotIn("len(df)", ANALYTICS_SOURCE)
        self.assertNotIn('["Sales"].mean()', PAGE_SOURCE)
        self.assertNotIn('["Sales"].mean()', ANALYTICS_SOURCE)

    def test_page_starts(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            str(ROOT / "pages" / "1_Segment_Performance.py"),
            default_timeout=120,
        )
        app.run()
        self.assertEqual(list(app.exception), [])
        text = " ".join((block.value or "") for block in app.markdown)
        self.assertIn("Customer Segment Intelligence", text)
        self.assertIn("$12.64M", text)
        self.assertIn("11.61%", text)


if __name__ == "__main__":
    unittest.main()
