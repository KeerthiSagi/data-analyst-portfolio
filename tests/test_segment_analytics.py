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
    aggregate_discount_profitability,
    aggregate_segment_performance,
    aggregate_segment_trends,
    assign_discount_band,
    build_segment_comparison,
    build_segment_insights,
    calculate_segment_kpis,
    loss_analysis_caption,
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
        headings = " ".join((block.value or "") for block in app.subheader)
        self.assertIn("Customer Segment Intelligence", text)
        self.assertIn("$12.64M", text)
        self.assertIn("11.61%", text)
        self.assertIn("Segment Loss Analysis", headings)
        self.assertIn("Discount & Profitability Analysis", headings)
        self.assertIn("Segment Performance Trends", headings)
        self.assertIn("Customer Segment Insights", headings)


class SegmentAdvancedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.start = cls.df["Order_Date"].min().date()
        cls.end = cls.df["Order_Date"].max().date()
        cls.regions = sorted(cls.df["Region"].dropna().unique())
        cls.categories = sorted(cls.df["Category"].dropna().unique())
        cls.segments = sorted(cls.df["Segment"].dropna().unique())
        cls.performance = aggregate_segment_performance(cls.df)
        cls.discount = aggregate_discount_profitability(cls.df)
        cls.trends = aggregate_segment_trends(cls.df, cls.start, cls.end)

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

    def test_negative_profit_lines_rates_and_loss_amounts(self):
        for row in self.performance.to_dict("records"):
            subset = self.df.loc[self.df["Segment"] == row["segment"]]
            losses = subset.loc[subset["Profit"] < 0]
            self.assertEqual(row["negative_line_items"], len(losses))
            self.assertAlmostEqual(row["negative_line_rate"], len(losses) / len(subset) * 100, places=6)
            self.assertAlmostEqual(row["loss_amount"], float(losses["Profit"].sum()), places=4)
            self.assertEqual(row["orders_with_loss_lines"], int(losses["Order_ID"].nunique()))
            self.assertAlmostEqual(row["average_discount"], float(subset["Discount"].mean()) * 100, places=6)
            self.assertAlmostEqual(row["revenue"], float(subset["Sales"].sum()), places=2)
            self.assertAlmostEqual(row["aov"], float(subset["Sales"].sum()) / subset["Order_ID"].nunique(), places=4)
        caption = loss_analysis_caption(self.performance)
        self.assertIn(r"\$477,357.41", caption)
        self.assertIn("still finish in profit", caption)

    def test_loss_lines_are_not_the_same_as_unprofitable_orders(self):
        frame = _frame(
            [
                {"Order_Date": "2014-05-01", "Order_ID": "A", "Sales": 20, "Profit": -5, "Discount": 0.2, "Segment": "Consumer", "Region": "East", "Category": "Furniture"},
                {"Order_Date": "2014-05-01", "Order_ID": "A", "Sales": 40, "Profit": 30, "Discount": 0.0, "Segment": "Consumer", "Region": "East", "Category": "Furniture"},
                {"Order_Date": "2014-05-02", "Order_ID": "B", "Sales": 15, "Profit": -10, "Discount": 0.4, "Segment": "Consumer", "Region": "East", "Category": "Furniture"},
            ]
        )
        performance = aggregate_segment_performance(frame)
        row = performance.iloc[0]
        self.assertEqual(int(row["negative_line_items"]), 2)
        self.assertAlmostEqual(float(row["loss_amount"]), -15)
        self.assertEqual(int(row["orders_with_loss_lines"]), 2)
        self.assertEqual(int(row["unprofitable_orders"]), 1)
        self.assertGreater(int(row["orders_with_loss_lines"]), int(row["unprofitable_orders"]))

    def test_discount_band_boundaries_and_aggregates(self):
        samples = [0.0, 0.05, 0.1, 0.1000001, 0.2, 0.25, 0.3, 0.3000001]
        expected = [">0%–10%", ">0%–10%", ">0%–10%", ">10%–20%", ">10%–20%", ">20%–30%", ">20%–30%", ">30%"]
        expected[0] = "0%"
        bands = assign_discount_band(pd.Series(samples)).astype(str).tolist()
        self.assertEqual(bands, expected)

        frame = _frame(
            [
                {"Order_Date": "2014-06-01", "Order_ID": "A", "Sales": 100, "Profit": 50, "Discount": 0.0, "Segment": "Corporate", "Region": "West", "Category": "Technology"},
                {"Order_Date": "2014-06-01", "Order_ID": "B", "Sales": 300, "Profit": -150, "Discount": 0.35, "Segment": "Corporate", "Region": "West", "Category": "Technology"},
                {"Order_Date": "2014-06-02", "Order_ID": "C", "Sales": 40, "Profit": 4, "Discount": 0.1, "Segment": "Home Office", "Region": "West", "Category": "Technology"},
            ]
        )
        discount = aggregate_discount_profitability(frame)
        corporate_high = discount.loc[
            (discount["segment"] == "Corporate") & (discount["band"] == ">30%")
        ].iloc[0]
        corporate_zero = discount.loc[
            (discount["segment"] == "Corporate") & (discount["band"] == "0%")
        ].iloc[0]
        self.assertAlmostEqual(float(corporate_high["revenue"]), 300)
        self.assertAlmostEqual(float(corporate_high["profit"]), -150)
        self.assertAlmostEqual(float(corporate_high["margin"]), -50)
        self.assertEqual(int(corporate_high["line_items"]), 1)
        self.assertAlmostEqual(float(corporate_zero["margin"]), 50)
        combined = discount.groupby("band")[["revenue", "profit"]].sum()
        high = combined.loc[">30%"]
        self.assertNotAlmostEqual(float(high["profit"]) / float(high["revenue"]) * 100, float(frame["Profit"].mean()))
        self.assertAlmostEqual(float(discount["revenue"].sum()), float(frame["Sales"].sum()), places=4)

    def test_full_discount_revenue_reconciles_and_margin_is_aggregate(self):
        self.assertAlmostEqual(float(self.discount["revenue"].sum()), float(self.df["Sales"].sum()), places=2)
        self.assertAlmostEqual(float(self.discount["profit"].sum()), float(self.df["Profit"].sum()), places=2)
        totals = self.discount.groupby("band")[["revenue", "profit", "line_items"]].sum()
        for band, row in totals.iterrows():
            if row["revenue"] == 0:
                continue
            subset = self.df.loc[assign_discount_band(self.df["Discount"]).astype(str) == band]
            self.assertAlmostEqual(float(row["revenue"]), float(subset["Sales"].sum()), places=2)
            self.assertAlmostEqual(float(row["profit"]), float(subset["Profit"].sum()), places=2)
            self.assertEqual(int(row["line_items"]), len(subset))

    def test_trends_use_bucket_margin_and_leave_gaps_empty(self):
        self.assertEqual(self.trends["grain"].iloc[0], "Monthly")
        january = self.trends.loc[
            (self.trends["segment"] == "Consumer") & (self.trends["label"] == "Jan 2014")
        ].iloc[0]
        consumer = self.df.loc[
            (self.df["Segment"] == "Consumer")
            & (self.df["Order_Date"] >= "2014-01-01")
            & (self.df["Order_Date"] < "2014-02-01")
        ]
        self.assertAlmostEqual(float(january["revenue"]), float(consumer["Sales"].sum()), places=2)
        self.assertAlmostEqual(float(january["profit"]), float(consumer["Profit"].sum()), places=2)
        self.assertAlmostEqual(
            float(january["margin"]),
            float(consumer["Profit"].sum()) / float(consumer["Sales"].sum()) * 100,
            places=4,
        )

        gap = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 2, "Discount": 0, "Segment": "Consumer", "Region": "East", "Category": "Furniture"},
                {"Order_Date": "2014-01-03", "Order_ID": "B", "Sales": 0, "Profit": -4, "Discount": 0, "Segment": "Consumer", "Region": "East", "Category": "Furniture"},
            ]
        )
        trends = aggregate_segment_trends(gap, date(2014, 1, 1), date(2014, 1, 3))
        self.assertEqual(trends["grain"].iloc[0], "Daily")
        missing = trends.loc[trends["period"] == pd.Timestamp("2014-01-02")].iloc[0]
        zero_revenue = trends.loc[trends["period"] == pd.Timestamp("2014-01-03")].iloc[0]
        self.assertTrue(pd.isna(missing["revenue"]))
        self.assertTrue(pd.isna(missing["margin"]))
        self.assertEqual(float(zero_revenue["revenue"]), 0)
        self.assertTrue(pd.isna(zero_revenue["margin"]))

    def test_single_segment_and_empty_advanced_results(self):
        consumer = self._filtered(segments=["Consumer"])
        performance = aggregate_segment_performance(consumer)
        discount = aggregate_discount_profitability(consumer)
        trends = aggregate_segment_trends(consumer, self.start, self.end)
        insights = build_segment_insights(performance, discount, trends)
        text = " ".join(note["body"] for note in insights)

        self.assertEqual(performance["segment"].tolist(), ["Consumer"])
        self.assertTrue(set(discount["segment"].unique()) <= {"Consumer"})
        self.assertTrue(set(trends["segment"].unique()) <= {"Consumer"})
        self.assertNotIn("Corporate", text)
        self.assertNotIn("Home Office", text)
        self.assertIn("only segment", text)

        empty = self._filtered(segments=[])
        empty_performance = aggregate_segment_performance(empty)
        empty_discount = aggregate_discount_profitability(empty)
        empty_trends = aggregate_segment_trends(empty, self.start, self.end)
        empty_insights = build_segment_insights(empty_performance, empty_discount, empty_trends)
        self.assertTrue(empty_performance.empty)
        self.assertTrue(empty_discount.empty)
        self.assertTrue(empty_trends.empty)
        self.assertIn("No transactions", empty_insights[0]["body"])

    def test_filters_change_loss_and_discount_results(self):
        full_lines = int(self.performance["negative_line_items"].sum())
        technology = aggregate_segment_performance(self._filtered(categories=["Technology"]))
        central = aggregate_segment_performance(self._filtered(regions=["Central"]))
        year = aggregate_discount_profitability(
            self._filtered(start=date(2014, 1, 1), end=date(2014, 12, 31))
        )
        self.assertLess(int(technology["negative_line_items"].sum()), full_lines)
        self.assertLess(int(central["negative_line_items"].sum()), full_lines)
        self.assertLess(float(year["revenue"].sum()), float(self.discount["revenue"].sum()))
        self.assertTrue(set(technology["segment"]) <= set(self.segments))

    def test_insights_use_calculated_leaders(self):
        insights = build_segment_insights(self.performance, self.discount, self.trends)
        by_title = {note["title"]: note["body"] for note in insights}
        consumer_share = float(
            self.performance.loc[self.performance["segment"] == "Consumer", "revenue_share"].iloc[0]
        )
        home_margin = float(
            self.performance.loc[self.performance["segment"] == "Home Office", "margin"].iloc[0]
        )

        self.assertGreaterEqual(len(insights), 4)
        self.assertLessEqual(len(insights), 5)
        self.assertIn("Consumer", by_title["Revenue leadership"])
        self.assertIn(f"{consumer_share:.1f}%", by_title["Revenue leadership"])
        self.assertIn("Home Office", by_title["Profitability leadership"])
        self.assertIn(f"{home_margin:.2f}%", by_title["Profitability leadership"])
        self.assertIn("observed association", by_title["Discount behavior"])
        self.assertIn("Loss exposure", by_title)
        self.assertNotIn("discount caused", " ".join(by_title.values()).lower())

    def test_material_trend_insight_uses_the_selected_segment(self):
        rows = []
        for month, sales in (("2013-12-01", 100), ("2014-12-01", 180)):
            rows.append(
                {
                    "Order_Date": month,
                    "Order_ID": month,
                    "Sales": sales,
                    "Profit": 10,
                    "Discount": 0,
                    "Segment": "Corporate",
                    "Region": "East",
                    "Category": "Furniture",
                }
            )
        frame = _frame(rows)
        performance = aggregate_segment_performance(frame)
        trends = aggregate_segment_trends(frame, date(2013, 1, 1), date(2014, 12, 31))
        insights = build_segment_insights(performance, pd.DataFrame(), trends)
        text = " ".join(note["body"] for note in insights)
        self.assertIn("Performance trend", {note["title"] for note in insights})
        self.assertIn("Corporate", text)
        self.assertIn("80.0% higher", text)
        self.assertNotIn("Consumer", text)


if __name__ == "__main__":
    unittest.main()
