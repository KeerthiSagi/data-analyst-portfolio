"""Sparkline aggregation and KPI comparison checks for Phase 2."""

import ast
import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
from utils.kpi_metrics import (
    aggregate_kpi_trends,
    build_sparkline,
    format_headline_currency,
    format_period_comparison,
    prior_period_caption,
    resolve_frequency,
)

APP_SOURCE = (ROOT / "app_kpi_dashboard.py").read_text()
KPI_SOURCE = (ROOT / "utils" / "kpi_metrics.py").read_text()


def _orders(rows):
    return pd.DataFrame(rows)


class SparklineAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.dataset_start = cls.df["Order_Date"].min().date()
        cls.dataset_end = cls.df["Order_Date"].max().date()

    def _slice(self, start, end, regions, categories):
        frame = self.df
        return frame[
            (frame["Order_Date"].dt.date >= start)
            & (frame["Order_Date"].dt.date <= end)
            & (frame["Region"].isin(regions))
            & (frame["Category"].isin(categories))
        ]

    def test_full_dataset_revenue_and_profit_match_published_totals(self):
        trends = aggregate_kpi_trends(self.df, self.dataset_start, self.dataset_end)

        self.assertAlmostEqual(trends.revenue["value"].sum(skipna=True), 12642905, places=2)
        self.assertAlmostEqual(trends.profit["value"].sum(skipna=True), 1467457.29, places=2)
        self.assertEqual(int(self.df["Order_ID"].nunique()), 25035)
        self.assertAlmostEqual(
            self.df["Profit"].sum() / self.df["Sales"].sum() * 100,
            11.61,
            places=2,
        )

    def test_revenue_and_profit_sparklines_use_bucket_sums(self):
        start, end = date(2014, 1, 1), date(2014, 12, 31)
        subset = self._slice(start, end, sorted(self.df["Region"].unique()), ["Technology"])
        trends = aggregate_kpi_trends(subset, start, end)

        self.assertAlmostEqual(
            trends.revenue["value"].sum(skipna=True),
            float(subset["Sales"].sum()),
            places=2,
        )
        self.assertAlmostEqual(
            trends.profit["value"].sum(skipna=True),
            float(subset["Profit"].sum()),
            places=2,
        )
        self.assertTrue(trends.revenue["period"].is_monotonic_increasing)
        self.assertTrue(trends.profit["period"].is_monotonic_increasing)

    def test_margin_uses_aggregated_profit_over_revenue(self):
        frame = _orders(
            [
                {
                    "Order_Date": "2014-03-01",
                    "Order_ID": "A",
                    "Sales": 10.0,
                    "Profit": 8.0,
                },
                {
                    "Order_Date": "2014-03-01",
                    "Order_ID": "B",
                    "Sales": 90.0,
                    "Profit": 9.0,
                },
            ]
        )
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
        trends = aggregate_kpi_trends(frame, date(2014, 3, 1), date(2014, 3, 1))
        present = trends.margin.dropna(subset=["value"])

        self.assertEqual(len(present), 1)
        self.assertAlmostEqual(float(present["value"].iloc[0]), 17.0, places=6)
        line_average = ((frame["Profit"] / frame["Sales"]) * 100).mean()
        self.assertNotAlmostEqual(float(present["value"].iloc[0]), line_average, places=6)

    def test_orders_use_unique_ids_and_are_not_forced_to_the_total(self):
        frame = _orders(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 1},
                {"Order_Date": "2014-01-02", "Order_ID": "A", "Sales": 5, "Profit": -2},
                {"Order_Date": "2014-01-02", "Order_ID": "B", "Sales": 7, "Profit": 3},
            ]
        )
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
        trends = aggregate_kpi_trends(frame, date(2014, 1, 1), date(2014, 1, 2))
        daily_orders = [int(value) for value in trends.orders["value"].tolist()]

        self.assertEqual(daily_orders, [1, 2])
        self.assertEqual(int(frame["Order_ID"].nunique()), 2)
        self.assertNotEqual(sum(daily_orders), int(frame["Order_ID"].nunique()))

    def test_reporting_period_changes_frequency_and_values(self):
        regions = sorted(self.df["Region"].unique())
        categories = sorted(self.df["Category"].unique())
        year_2014 = self._slice(date(2014, 1, 1), date(2014, 12, 31), regions, categories)
        year_2013 = self._slice(date(2013, 1, 1), date(2013, 12, 31), regions, categories)
        june = self._slice(date(2014, 6, 1), date(2014, 6, 15), regions, categories)

        annual = aggregate_kpi_trends(year_2014, date(2014, 1, 1), date(2014, 12, 31))
        prior = aggregate_kpi_trends(year_2013, date(2013, 1, 1), date(2013, 12, 31))
        short = aggregate_kpi_trends(june, date(2014, 6, 1), date(2014, 6, 15))

        self.assertEqual(annual.frequency, "M")
        self.assertEqual(short.frequency, "D")
        self.assertFalse(
            annual.revenue["value"].reset_index(drop=True).equals(
                prior.revenue["value"].reset_index(drop=True)
            )
        )
        self.assertTrue(short.revenue["period"].dt.month.eq(6).all())
        self.assertTrue(annual.revenue["label"].str.contains("2014").all())

    def test_region_and_category_filters_change_sparklines(self):
        start, end = date(2014, 1, 1), date(2014, 3, 31)
        categories = sorted(self.df["Category"].unique())
        regions = sorted(self.df["Region"].unique())
        central = self._slice(start, end, ["Central"], categories)
        west = self._slice(start, end, ["West"], categories)
        technology = self._slice(start, end, regions, ["Technology"])
        furniture = self._slice(start, end, regions, ["Furniture"])

        central_trends = aggregate_kpi_trends(central, start, end)
        west_trends = aggregate_kpi_trends(west, start, end)
        technology_trends = aggregate_kpi_trends(technology, start, end)
        furniture_trends = aggregate_kpi_trends(furniture, start, end)

        self.assertEqual(central_trends.frequency, "W")
        self.assertNotAlmostEqual(
            central_trends.revenue["value"].sum(skipna=True),
            west_trends.revenue["value"].sum(skipna=True),
            places=2,
        )
        self.assertNotAlmostEqual(
            technology_trends.profit["value"].sum(skipna=True),
            furniture_trends.profit["value"].sum(skipna=True),
            places=2,
        )

        sample = central_trends.orders.dropna(subset=["value"]).iloc[0]
        week = central["Order_Date"].dt.to_period("W-SUN")
        sample_week = pd.Timestamp(sample["period"]).to_period("W-SUN")
        expected_orders = int(central.loc[week == sample_week, "Order_ID"].nunique())
        self.assertEqual(int(sample["value"]), expected_orders)

    def test_missing_buckets_are_empty_not_zero(self):
        frame = _orders(
            [
                {"Order_Date": "2014-05-01", "Order_ID": "A", "Sales": 12, "Profit": 3},
                {"Order_Date": "2014-05-03", "Order_ID": "B", "Sales": 8, "Profit": 1},
            ]
        )
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
        trends = aggregate_kpi_trends(frame, date(2014, 5, 1), date(2014, 5, 3))
        gap = trends.revenue.loc[trends.revenue["period"] == pd.Timestamp("2014-05-02"), "value"]

        self.assertEqual(len(trends.revenue), 3)
        self.assertTrue(pd.isna(gap.iloc[0]))
        self.assertNotEqual(gap.iloc[0], 0)

    def test_zero_revenue_margin_is_undefined(self):
        frame = _orders(
            [
                {"Order_Date": "2014-04-04", "Order_ID": "A", "Sales": 0, "Profit": -5},
            ]
        )
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
        trends = aggregate_kpi_trends(frame, date(2014, 4, 4), date(2014, 4, 4))

        self.assertTrue(pd.isna(trends.margin["value"].iloc[0]))
        self.assertEqual(float(trends.profit["value"].iloc[0]), -5)

    def test_negative_profit_sparkline_keeps_the_sign(self):
        frame = _orders(
            [
                {"Order_Date": "2014-02-01", "Order_ID": "A", "Sales": 40, "Profit": -25},
                {"Order_Date": "2014-02-10", "Order_ID": "B", "Sales": 15, "Profit": -5},
            ]
        )
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
        trends = aggregate_kpi_trends(frame, date(2014, 2, 1), date(2014, 2, 28))
        figure = build_sparkline(trends.profit, "profit")
        plotted = pd.Series(figure.data[0].y).dropna()

        self.assertLess(float(plotted.min()), 0)
        self.assertLess(float(figure.layout.yaxis.range[0]), float(plotted.min()))
        self.assertGreater(float(figure.layout.yaxis.range[1]), float(plotted.max()))
        self.assertFalse(figure.layout.xaxis.visible)
        self.assertFalse(figure.layout.yaxis.visible)
        self.assertFalse(figure.layout.showlegend)
        self.assertEqual(figure.data[0].line.color, "#10B981")

    def test_one_day_period_renders_a_single_marker(self):
        day = date(2014, 7, 8)
        subset = self.df[self.df["Order_Date"].dt.date == day]
        self.assertGreater(len(subset), 0)

        trends = aggregate_kpi_trends(subset, day, day)
        figure = build_sparkline(trends.revenue, "revenue")

        self.assertEqual(trends.frequency, "D")
        self.assertEqual(int(trends.revenue["value"].notna().sum()), 1)
        self.assertEqual(figure.data[0].mode, "markers")
        self.assertAlmostEqual(
            float(trends.revenue["value"].sum(skipna=True)),
            float(subset["Sales"].sum()),
            places=2,
        )
        for metric in ("profit", "margin", "orders"):
            self.assertIsNotNone(build_sparkline(getattr(trends, metric), metric))

    def test_empty_selection_does_not_invent_points(self):
        empty = self.df.iloc[0:0]
        trends = aggregate_kpi_trends(empty, date(2014, 1, 1), date(2014, 1, 10))

        self.assertTrue(trends.revenue["value"].isna().all())
        self.assertTrue(trends.orders["value"].isna().all())
        self.assertIsNone(build_sparkline(trends.revenue, "revenue"))
        self.assertEqual(len(trends.revenue), 10)

    def test_frequency_boundaries(self):
        self.assertEqual(resolve_frequency(1), "D")
        self.assertEqual(resolve_frequency(45), "D")
        self.assertEqual(resolve_frequency(46), "W")
        self.assertEqual(resolve_frequency(180), "W")
        self.assertEqual(resolve_frequency(181), "M")

    def test_sparkline_colors_and_real_hover_labels(self):
        trends = aggregate_kpi_trends(self.df, date(2014, 1, 1), date(2014, 12, 31))
        revenue_figure = build_sparkline(trends.revenue, "revenue")
        margin_figure = build_sparkline(trends.margin, "margin")
        orders_figure = build_sparkline(trends.orders, "orders")

        self.assertEqual(revenue_figure.data[0].line.color, "#4F46E5")
        self.assertEqual(margin_figure.data[0].line.color, "#8B5CF6")
        self.assertEqual(orders_figure.data[0].line.color, "#0EA5E9")
        self.assertIn("Jan 2014", trends.revenue["label"].tolist())
        self.assertFalse(revenue_figure.data[0].connectgaps)


class ComparisonCopyTests(unittest.TestCase):
    def test_percentage_and_point_copy(self):
        revenue, revenue_color = format_period_comparison(12.44)
        decline, decline_color = format_period_comparison(-3.24)
        margin, _ = format_period_comparison(1.46, unit=" pp")

        self.assertEqual(revenue, "▲ 12.4% vs prior period")
        self.assertEqual(revenue_color, "#059669")
        self.assertEqual(decline, "▼ 3.2% vs prior period")
        self.assertEqual(decline_color, "#DC2626")
        self.assertEqual(margin, "▲ 1.5 pp vs prior period")

    def test_missing_comparison_is_not_a_fake_zero(self):
        text, color = format_period_comparison(None, current=100, previous=0)
        self.assertEqual(text, "Comparison unavailable")
        self.assertNotIn("0.0%", text)
        self.assertEqual(color, "#94A3B8")
        self.assertEqual(
            prior_period_caption(date(2013, 1, 1), date(2013, 12, 31), False),
            "Comparison unavailable",
        )

    def test_negative_prior_profit_is_not_shown_as_growth(self):
        narrowed, narrowed_color = format_period_comparison(
            50,
            metric="profit",
            current=-50,
            previous=-100,
        )
        widened, _ = format_period_comparison(
            -50,
            metric="profit",
            current=-150,
            previous=-100,
        )
        recovered, _ = format_period_comparison(
            120,
            metric="profit",
            current=20,
            previous=-100,
        )

        self.assertEqual(narrowed, "▲ Loss narrowed by $50 vs prior period")
        self.assertEqual(narrowed_color, "#059669")
        self.assertNotIn("%", narrowed)
        self.assertEqual(widened, "▼ Loss widened by $50 vs prior period")
        self.assertNotIn("%", widened)
        self.assertEqual(recovered, "▲ Returned to profit vs prior period")
        self.assertNotIn("%", recovered)

    def test_prior_period_dates_are_exact(self):
        caption = prior_period_caption(date(2013, 1, 1), date(2013, 12, 31), True)
        self.assertEqual(caption, "Prior period: January 1, 2013 – December 31, 2013")

    def test_headline_currency_matches_published_scale(self):
        self.assertEqual(format_headline_currency(12642905), "$12.64M")
        self.assertEqual(format_headline_currency(1467457.29), "$1.47M")
        self.assertEqual(format_headline_currency(-2500), "-$2,500")


class DashboardWiringTests(unittest.TestCase):
    def test_app_uses_filtered_trends_and_keeps_phase_one_kpis(self):
        module = ast.parse(APP_SOURCE)
        self.assertIsNotNone(module)
        self.assertIn("aggregate_kpi_trends(filtered_df, start_date, end_date)", APP_SOURCE)
        self.assertIn('filtered_df["Order_ID"].nunique()', APP_SOURCE)
        self.assertIn("margin_change = profit_margin - previous_margin", APP_SOURCE)
        self.assertIn("if previous_start >= dataset_start:", APP_SOURCE)
        self.assertNotIn("len(filtered_df)", APP_SOURCE)
        self.assertNotIn("No prior-period data", APP_SOURCE)
        self.assertIn("Revenue & Profit Trends", APP_SOURCE)
        self.assertIn("Revenue Composition", APP_SOURCE)
        self.assertIn("Geographic Revenue Performance", APP_SOURCE)
        self.assertIn('("Order_ID", "nunique")', KPI_SOURCE)
        self.assertNotIn("len(df)", KPI_SOURCE)
        self.assertNotIn("len(work)", KPI_SOURCE)


if __name__ == "__main__":
    unittest.main()
