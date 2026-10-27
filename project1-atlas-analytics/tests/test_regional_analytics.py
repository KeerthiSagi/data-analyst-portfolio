"""Regional KPI, filter, trend, and insight checks for Phase 5A."""

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
from utils.regional_analytics import (
    aggregate_regional_performance,
    aggregate_regional_trends,
    build_regional_comparison,
    calculate_regional_kpis,
    calculate_regional_profitability,
    calculate_regional_revenue_share,
    default_trend_regions,
    filter_orders,
    generate_regional_insights,
)

PAGE_SOURCE = (ROOT / "pages" / "2_Regional_Logistics.py").read_text()
ANALYTICS_SOURCE = (ROOT / "utils" / "regional_analytics.py").read_text()


def _frame(rows):
    frame = pd.DataFrame(rows)
    frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    return frame


class RegionalKpiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.start = cls.df["Order_Date"].min().date()
        cls.end = cls.df["Order_Date"].max().date()
        cls.regions = sorted(cls.df["Region"].dropna().unique())
        cls.categories = sorted(cls.df["Category"].dropna().unique())
        cls.segments = sorted(cls.df["Segment"].dropna().unique())
        cls.performance = aggregate_regional_performance(cls.df)

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
        kpis = calculate_regional_kpis(self.df)
        orders = int(self.df["Order_ID"].nunique())

        self.assertAlmostEqual(kpis["revenue"], 12642905, places=2)
        self.assertAlmostEqual(kpis["profit"], 1467457.29, places=2)
        self.assertAlmostEqual(kpis["margin"], 11.61, places=2)
        self.assertEqual(kpis["orders"], 25035)
        self.assertEqual(orders, 25035)
        self.assertNotEqual(orders, len(self.df))
        self.assertAlmostEqual(kpis["aov"], 12642905 / 25035, places=2)

    def test_regional_revenue_and_profit_reconcile(self):
        self.assertAlmostEqual(self.performance["revenue"].sum(), 12642905, places=2)
        self.assertAlmostEqual(self.performance["profit"].sum(), 1467457.29, places=2)
        self.assertAlmostEqual(self.performance["revenue_share"].sum(), 100, places=2)
        self.assertEqual(len(self.performance), 13)
        self.assertEqual(set(self.performance["region"]), set(self.regions))
        for row in self.performance.to_dict("records"):
            subset = self.df.loc[self.df["Region"] == row["region"]]
            self.assertAlmostEqual(row["margin"], row["profit"] / row["revenue"] * 100, places=6)
            self.assertAlmostEqual(row["aov"], row["revenue"] / row["orders"], places=6)
            self.assertEqual(row["orders"], int(subset["Order_ID"].nunique()))
            self.assertEqual(row["line_items"], len(subset))

    def test_revenue_share_helper_matches_the_table(self):
        share = calculate_regional_revenue_share(self.performance["revenue"])
        self.assertTrue(share.round(6).equals(self.performance["revenue_share"].round(6)))

    def test_overlapping_orders_are_not_forced_to_the_total(self):
        frame = _frame(
            [
                {"Order_Date": "2014-02-01", "Order_ID": "A", "Sales": 10, "Profit": 4, "Region": "East", "Category": "Technology", "Segment": "Consumer"},
                {"Order_Date": "2014-02-01", "Order_ID": "A", "Sales": 15, "Profit": -2, "Region": "West", "Category": "Technology", "Segment": "Consumer"},
            ]
        )
        performance = aggregate_regional_performance(frame)
        self.assertEqual(int(performance["orders"].sum()), 2)
        self.assertEqual(int(frame["Order_ID"].nunique()), 1)
        self.assertNotEqual(int(performance["orders"].sum()), int(frame["Order_ID"].nunique()))

    def test_single_region_selection(self):
        central = self._filtered(regions=["Central"])
        performance = aggregate_regional_performance(central)
        kpis = calculate_regional_kpis(central)

        self.assertEqual(performance["region"].tolist(), ["Central"])
        self.assertAlmostEqual(float(performance["revenue_share"].iloc[0]), 100, places=4)
        self.assertAlmostEqual(kpis["revenue"], float(central["Sales"].sum()), places=2)
        self.assertEqual(kpis["orders"], int(central["Order_ID"].nunique()))
        insights = generate_regional_insights(performance, pd.DataFrame())
        text = " ".join(note["body"] for note in insights)
        self.assertIn("only region", text)
        self.assertNotIn("South", text)

    def test_empty_and_zero_revenue(self):
        empty = self._filtered(regions=[])
        self.assertTrue(empty.empty)
        empty_kpis = calculate_regional_kpis(empty)
        self.assertEqual(empty_kpis["orders"], 0)
        self.assertIsNone(empty_kpis["margin"])
        self.assertIsNone(empty_kpis["aov"])
        self.assertTrue(aggregate_regional_performance(empty).empty)
        empty_insights = generate_regional_insights(
            aggregate_regional_performance(empty),
            aggregate_regional_trends(empty, self.start, self.end),
        )
        self.assertIn("No transactions", empty_insights[0]["body"])

        zero = _frame(
            [
                {"Order_Date": "2014-03-01", "Order_ID": "Z", "Sales": 0, "Profit": -8, "Region": "Canada", "Category": "Furniture", "Segment": "Home Office"},
            ]
        )
        zero_kpis = calculate_regional_kpis(zero)
        zero_rows = aggregate_regional_performance(zero)
        self.assertIsNone(zero_kpis["margin"])
        self.assertEqual(zero_kpis["aov"], 0)
        self.assertTrue(pd.isna(zero_rows["margin"].iloc[0]))
        self.assertTrue(pd.isna(zero_rows["revenue_share"].iloc[0]))
        self.assertTrue(calculate_regional_revenue_share(zero_rows["revenue"]).isna().all())

    def test_negative_profit_is_preserved(self):
        frame = _frame(
            [
                {"Order_Date": "2014-04-01", "Order_ID": "A", "Sales": 100, "Profit": 25, "Region": "Central", "Category": "Office Supplies", "Segment": "Consumer"},
                {"Order_Date": "2014-04-02", "Order_ID": "B", "Sales": 80, "Profit": -40, "Region": "EMEA", "Category": "Office Supplies", "Segment": "Corporate"},
            ]
        )
        performance = aggregate_regional_performance(frame)
        emea = performance.loc[performance["region"] == "EMEA"].iloc[0]
        figure = build_regional_comparison(performance, "Profit")
        findings = calculate_regional_profitability(performance)
        text = " ".join(note["body"] for note in generate_regional_insights(performance, pd.DataFrame()))

        self.assertLess(float(emea["profit"]), 0)
        self.assertLess(float(emea["margin"]), 0)
        self.assertTrue(pd.isna(performance["profit_share"]).all())
        self.assertIn("#DC2626", list(figure.data[0].marker.color))
        self.assertIn("EMEA", text)
        self.assertIn("negative profit", text.lower())
        self.assertFalse(findings["profit_share_available"])
        self.assertEqual(findings["negative_profit"]["region"].tolist(), ["EMEA"])

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

    def test_margin_chart_does_not_share_an_axis_with_currency(self):
        figure = build_regional_comparison(self.performance, "Profit Margin")
        self.assertTrue(str(figure.layout.xaxis.ticksuffix).endswith("%"))
        self.assertNotIn("$", str(figure.layout.xaxis.tickformat or ""))

    def test_trends_use_bucket_margin_and_leave_gaps_empty(self):
        trends = aggregate_regional_trends(self.df, self.start, self.end, regions=["Central"])
        self.assertEqual(trends["grain"].iloc[0], "Monthly")
        january = trends.loc[trends["label"] == "Jan 2014"].iloc[0]
        central = self.df.loc[
            (self.df["Region"] == "Central")
            & (self.df["Order_Date"] >= "2014-01-01")
            & (self.df["Order_Date"] < "2014-02-01")
        ]
        self.assertAlmostEqual(float(january["revenue"]), float(central["Sales"].sum()), places=2)
        self.assertAlmostEqual(float(january["profit"]), float(central["Profit"].sum()), places=2)
        self.assertAlmostEqual(
            float(january["margin"]),
            float(central["Profit"].sum()) / float(central["Sales"].sum()) * 100,
            places=4,
        )

        gap = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 2, "Region": "West", "Category": "Furniture", "Segment": "Consumer"},
                {"Order_Date": "2014-01-03", "Order_ID": "B", "Sales": 0, "Profit": -4, "Region": "West", "Category": "Furniture", "Segment": "Consumer"},
            ]
        )
        trends = aggregate_regional_trends(gap, date(2014, 1, 1), date(2014, 1, 3), regions=["West"])
        self.assertEqual(trends["grain"].iloc[0], "Daily")
        missing = trends.loc[trends["period"] == pd.Timestamp("2014-01-02")].iloc[0]
        zero_revenue = trends.loc[trends["period"] == pd.Timestamp("2014-01-03")].iloc[0]
        self.assertTrue(pd.isna(missing["revenue"]))
        self.assertTrue(pd.isna(missing["margin"]))
        self.assertEqual(float(zero_revenue["revenue"]), 0)
        self.assertTrue(pd.isna(zero_revenue["margin"]))

    def test_default_trend_regions_are_top_five_by_revenue(self):
        defaults = default_trend_regions(self.performance)
        expected = self.performance.sort_values("revenue", ascending=False)["region"].head(5).tolist()
        self.assertEqual(defaults, expected)
        self.assertEqual(len(defaults), 5)

    def test_insights_use_calculated_leaders(self):
        trends = aggregate_regional_trends(
            self.df,
            self.start,
            self.end,
            regions=default_trend_regions(self.performance),
        )
        insights = generate_regional_insights(self.performance, trends)
        by_title = {note["title"]: note["body"] for note in insights}
        central_share = float(
            self.performance.loc[self.performance["region"] == "Central", "revenue_share"].iloc[0]
        )
        canada_margin = float(
            self.performance.loc[self.performance["region"] == "Canada", "margin"].iloc[0]
        )

        self.assertGreaterEqual(len(insights), 4)
        self.assertLessEqual(len(insights), 5)
        self.assertIn("Central", by_title["Revenue leadership"])
        self.assertIn(f"{central_share:.1f}%", by_title["Revenue leadership"])
        self.assertIn("Canada", by_title["Profitability leadership"])
        self.assertIn(f"{canada_margin:.2f}%", by_title["Profitability leadership"])
        self.assertIn("not the revenue leader", by_title["Profitability leadership"])
        self.assertIn("Revenue and profit alignment", by_title)
        self.assertIn("Regional concentration", by_title)
        self.assertIn("Southeast Asia", by_title["Profitability risk"])


class RegionalPageTests(unittest.TestCase):
    def test_page_uses_distinct_orders(self):
        self.assertIn("calculate_regional_kpis", PAGE_SOURCE)
        self.assertIn('("Order_ID", "nunique")', ANALYTICS_SOURCE)
        self.assertNotIn("len(filtered)", PAGE_SOURCE)
        self.assertNotIn("len(df)", ANALYTICS_SOURCE)
        self.assertNotIn('["Sales"].mean()', PAGE_SOURCE)
        self.assertIn("Regional Performance Intelligence", PAGE_SOURCE)
        self.assertIn("kpi_orders", PAGE_SOURCE)

    def test_page_starts(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Regional_Logistics.py"),
            default_timeout=120,
        )
        app.run()
        self.assertEqual(list(app.exception), [])
        text = " ".join((block.value or "") for block in app.markdown)
        headings = " ".join((block.value or "") for block in app.subheader)
        self.assertIn("Regional Performance Intelligence", text)
        self.assertIn("$12.64M", text)
        self.assertIn("11.61%", text)
        self.assertIn("25,035", text)
        self.assertIn("Regional Performance Comparison", headings)
        self.assertIn("Revenue Contribution by Region", headings)
        self.assertIn("Regional Profitability Health", headings)
        self.assertIn("Regional Performance Trends", headings)
        self.assertIn("Regional Business Insights", headings)


if __name__ == "__main__":
    unittest.main()
