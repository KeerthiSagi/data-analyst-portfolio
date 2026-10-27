"""Phase 3 checks for executive trends, breakdowns, and insights."""

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
from utils.executive_analytics import (
    TREND_BOTH,
    TREND_MARGIN,
    TREND_PROFIT,
    build_executive_insights,
    build_performance_bar,
    build_trend_figure,
    discount_margin_bands,
    summarize_groups,
    trend_frame,
)
from utils.kpi_metrics import aggregate_kpi_trends

APP_SOURCE = (ROOT / "app_kpi_dashboard.py").read_text()
ANALYTICS_SOURCE = (ROOT / "utils" / "executive_analytics.py").read_text()


def _frame(rows):
    frame = pd.DataFrame(rows)
    frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    return frame


class ExecutiveAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_full_dataset_totals_and_reconciliations(self):
        categories = summarize_groups(self.df, "Category")
        regions = summarize_groups(self.df, "Region")
        trends = aggregate_kpi_trends(self.df, date(2011, 1, 1), date(2014, 12, 31))
        series = trend_frame(trends)

        self.assertAlmostEqual(float(self.df["Sales"].sum()), 12642905, places=2)
        self.assertAlmostEqual(float(self.df["Profit"].sum()), 1467457.29, places=2)
        self.assertAlmostEqual(categories["revenue"].sum(), 12642905, places=2)
        self.assertAlmostEqual(categories["profit"].sum(), 1467457.29, places=2)
        self.assertAlmostEqual(regions["revenue"].sum(), 12642905, places=2)
        self.assertAlmostEqual(regions["profit"].sum(), 1467457.29, places=2)
        self.assertAlmostEqual(categories["revenue_share"].sum(), 100, places=2)
        self.assertAlmostEqual(regions["revenue_share"].sum(), 100, places=2)
        self.assertAlmostEqual(series["revenue"].sum(skipna=True), 12642905, places=2)
        self.assertAlmostEqual(series["profit"].sum(skipna=True), 1467457.29, places=2)
        self.assertEqual(int(self.df["Order_ID"].nunique()), 25035)

    def test_margin_uses_aggregated_values(self):
        frame = _frame(
            [
                {"Order_Date": "2014-03-01", "Order_ID": "A", "Sales": 10.0, "Profit": 8.0, "Category": "Furniture", "Region": "Central", "Discount": 0.0},
                {"Order_Date": "2014-03-01", "Order_ID": "B", "Sales": 90.0, "Profit": 9.0, "Category": "Furniture", "Region": "Central", "Discount": 0.0},
            ]
        )
        summary = summarize_groups(frame, "Category")
        line_average = ((frame["Profit"] / frame["Sales"]) * 100).mean()

        self.assertAlmostEqual(float(summary["margin"].iloc[0]), 17.0, places=6)
        self.assertNotAlmostEqual(float(summary["margin"].iloc[0]), line_average, places=6)

        trends = aggregate_kpi_trends(frame, date(2014, 3, 1), date(2014, 3, 1))
        series = trend_frame(trends)
        self.assertAlmostEqual(float(series["margin"].iloc[0]), 17.0, places=6)

    def test_zero_revenue_margin_is_unavailable(self):
        frame = _frame(
            [
                {"Order_Date": "2014-04-04", "Order_ID": "A", "Sales": 0.0, "Profit": -5.0, "Category": "Furniture", "Region": "East", "Discount": 0.5},
            ]
        )
        summary = summarize_groups(frame, "Category")
        trends = aggregate_kpi_trends(frame, date(2014, 4, 4), date(2014, 4, 4))
        series = trend_frame(trends)

        self.assertTrue(pd.isna(summary["margin"].iloc[0]))
        self.assertTrue(pd.isna(series["margin"].iloc[0]))
        self.assertEqual(float(series["profit"].iloc[0]), -5.0)
        self.assertIsNone(build_trend_figure(trends, TREND_MARGIN))

    def test_filters_change_category_and_region_results(self):
        start, end = date(2014, 1, 1), date(2014, 3, 31)
        window = self.df[
            (self.df["Order_Date"].dt.date >= start)
            & (self.df["Order_Date"].dt.date <= end)
        ]
        central = window[window["Region"] == "Central"]
        west = window[window["Region"] == "West"]
        technology = window[window["Category"] == "Technology"]
        furniture = window[window["Category"] == "Furniture"]

        self.assertNotAlmostEqual(
            summarize_groups(central, "Category")["revenue"].sum(),
            summarize_groups(west, "Category")["revenue"].sum(),
            places=2,
        )
        self.assertNotAlmostEqual(
            summarize_groups(technology, "Region")["profit"].sum(),
            summarize_groups(furniture, "Region")["profit"].sum(),
            places=2,
        )

        june = self.df[
            (self.df["Order_Date"].dt.date >= date(2014, 6, 1))
            & (self.df["Order_Date"].dt.date <= date(2014, 6, 10))
        ]
        june_trends = aggregate_kpi_trends(june, date(2014, 6, 1), date(2014, 6, 10))
        june_series = trend_frame(june_trends)
        self.assertEqual(june_trends.frequency, "D")
        self.assertEqual(len(june_series), 10)
        self.assertAlmostEqual(
            float(june_series["revenue"].sum(skipna=True)),
            float(june["Sales"].sum()),
            places=2,
        )

    def test_negative_profit_regions_are_ranked_and_colored(self):
        frame = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 100.0, "Profit": 40.0, "Category": "Technology", "Region": "North", "Discount": 0.0},
                {"Order_Date": "2014-01-02", "Order_ID": "B", "Sales": 80.0, "Profit": -25.0, "Category": "Furniture", "Region": "South", "Discount": 0.4},
            ]
        )
        regions = summarize_groups(frame, "Region")
        figure = build_performance_bar(regions, TREND_PROFIT, "h")
        names = list(figure.data[0].y)

        self.assertEqual(names, ["South", "North"])
        self.assertIn("#DC2626", list(figure.data[0].marker.color))
        self.assertLess(float(regions.loc[regions["name"] == "South", "profit"].iloc[0]), 0)

    def test_dual_axis_keeps_revenue_and_profit_apart(self):
        trends = aggregate_kpi_trends(self.df, date(2014, 1, 1), date(2014, 12, 31))
        figure = build_trend_figure(trends, TREND_BOTH)

        self.assertEqual(figure.data[0].name, "Revenue")
        self.assertEqual(figure.data[0].line.color, "#4F46E5")
        self.assertEqual(figure.data[1].name, "Profit")
        self.assertEqual(figure.data[1].line.color, "#10B981")
        self.assertEqual(figure.data[1].yaxis, "y2")
        self.assertEqual(figure.layout.yaxis2.overlaying, "y")
        self.assertFalse(figure.data[0].connectgaps)

        margin_figure = build_trend_figure(trends, TREND_MARGIN)
        self.assertEqual(margin_figure.data[0].line.color, "#8B5CF6")
        self.assertTrue(str(margin_figure.layout.yaxis.ticksuffix).endswith("%"))


class ExecutiveInsightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def _insights(self, frame, **kwargs):
        defaults = dict(
            comparison_ready=False,
            revenue_change=None,
            margin_change=None,
            prior_window=None,
            discount_bands=discount_margin_bands(frame),
        )
        defaults.update(kwargs)
        return build_executive_insights(
            categories=summarize_groups(frame, "Category"),
            regions=summarize_groups(frame, "Region"),
            **defaults,
        )

    def test_full_dataset_insights_use_real_values(self):
        insights = self._insights(self.df)
        text = " ".join(item.body for item in insights)

        self.assertGreaterEqual(len(insights), 3)
        self.assertLessEqual(len(insights), 5)
        self.assertIn("Technology accounts for 37.5% of revenue", text)
        self.assertIn("Furniture contributes 32.5% of revenue", text)
        self.assertIn("6.94% margin is 7.1 percentage points below Technology", text)
        self.assertIn("Central generates 22.3% of revenue", text)
        self.assertIn("Southeast Asia has the lowest profit margin at 2.02%", text)
        self.assertIn("not evidence that the discount caused the difference", text)
        self.assertNotIn("Versus", text)

    def test_period_insight_respects_availability(self):
        hidden = self._insights(
            self.df,
            comparison_ready=False,
            revenue_change=26.3,
            margin_change=-0.2,
            prior_window="January 1, 2013 – December 31, 2013",
        )
        shown = self._insights(
            self.df,
            comparison_ready=True,
            revenue_change=26.3,
            margin_change=-0.2,
            prior_window="January 1, 2013 – December 31, 2013",
        )
        hidden_text = " ".join(item.body for item in hidden)
        shown_text = " ".join(item.body for item in shown)

        self.assertNotIn("26.3%", hidden_text)
        self.assertIn("Versus January 1, 2013 – December 31, 2013", shown_text)
        self.assertIn("revenue is 26.3% higher", shown_text)
        self.assertIn("0.2 percentage points lower", shown_text)
        self.assertIn("different directions", shown_text)

    def test_single_category_and_region_do_not_invent_peers(self):
        technology = self.df[self.df["Category"] == "Technology"]
        central = self.df[self.df["Region"] == "Central"]
        category_text = " ".join(item.body for item in self._insights(technology))
        region_text = " ".join(item.body for item in self._insights(central))

        self.assertIn("only Technology", category_text)
        self.assertNotIn("Furniture contributes", category_text)
        self.assertIn("only Central", region_text)
        self.assertNotIn("Southeast Asia", region_text)

    def test_negative_profit_is_called_a_loss(self):
        frame = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 100.0, "Profit": 10.0, "Category": "Technology", "Region": "North", "Discount": 0.0},
                {"Order_Date": "2014-01-02", "Order_ID": "B", "Sales": 200.0, "Profit": -40.0, "Category": "Furniture", "Region": "South", "Discount": 0.0},
            ]
        )
        text = " ".join(item.body for item in self._insights(frame, discount_bands=None))

        self.assertIn("Furniture recorded negative profit", text)
        self.assertIn("South", text)
        self.assertIn("negative profit", text)
        self.assertNotIn("caused", text.lower())

    def test_missing_discount_column_skips_the_association(self):
        frame = self.df.drop(columns=["Discount"])
        titles = [item.title for item in self._insights(frame)]
        self.assertNotIn("Discount and margin", titles)


class DashboardPreservationTests(unittest.TestCase):
    def test_kpi_cards_and_section_titles_remain(self):
        self.assertIn("aggregate_kpi_trends(filtered_df, start_date, end_date)", APP_SOURCE)
        self.assertIn('chart_key="sparkline_revenue"', APP_SOURCE)
        self.assertIn('filtered_df["Order_ID"].nunique()', APP_SOURCE)
        self.assertIn("Revenue & Profit Trends", APP_SOURCE)
        self.assertIn("Revenue Composition", APP_SOURCE)
        self.assertIn("Geographic Revenue Performance", APP_SOURCE)
        self.assertNotIn("len(filtered_df)", APP_SOURCE)
        self.assertNotIn("len(df)", ANALYTICS_SOURCE)
        self.assertNotIn("app_root_cause", ANALYTICS_SOURCE)
        self.assertNotIn("app_data_cleaner", ANALYTICS_SOURCE)

    def test_application_starts(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app_kpi_dashboard.py"), default_timeout=120)
        app.run()
        self.assertEqual(list(app.exception), [])
        text = " ".join((block.value or "") for block in app.markdown)
        captions = " ".join((block.value or "") for block in app.caption)
        self.assertIn("Technology accounts for 37.5% of revenue", text)
        self.assertIn("Share of revenue:", captions)
        self.assertIn("$12.64M", text)
        self.assertIn("25,035", text)


if __name__ == "__main__":
    unittest.main()
