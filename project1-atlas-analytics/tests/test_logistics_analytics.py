"""Shipping and logistics KPI checks for Phase 5B."""

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
from utils.logistics_analytics import (
    aggregate_processing_time,
    aggregate_regional_shipping_cost,
    aggregate_shipping_modes,
    aggregate_shipping_trends,
    calculate_logistics_kpis,
    calculate_processing_intervals,
    filter_shipping_modes,
    generate_logistics_insights,
)
from utils.regional_analytics import filter_orders

PAGE_SOURCE = (ROOT / "pages" / "2_Regional_Logistics.py").read_text()
ANALYTICS_SOURCE = (ROOT / "utils" / "logistics_analytics.py").read_text()


def _frame(rows):
    frame = pd.DataFrame(rows)
    frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    frame["Ship_Date"] = pd.to_datetime(frame["Ship_Date"])
    return frame


class LogisticsKpiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.start = cls.df["Order_Date"].min().date()
        cls.end = cls.df["Order_Date"].max().date()
        cls.regions = sorted(cls.df["Region"].dropna().unique())
        cls.categories = sorted(cls.df["Category"].dropna().unique())
        cls.segments = sorted(cls.df["Segment"].dropna().unique())
        cls.modes = sorted(cls.df["Ship_Mode"].dropna().unique())
        cls.kpis = calculate_logistics_kpis(cls.df)
        cls.mode_rows = aggregate_shipping_modes(cls.df)
        cls.region_rows = aggregate_regional_shipping_cost(cls.df)

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

    def test_full_dataset_shipping_cost_and_ratio(self):
        self.assertAlmostEqual(self.kpis["shipping_cost"], float(self.df["Shipping_Cost"].sum()), places=4)
        self.assertAlmostEqual(self.kpis["revenue"], float(self.df["Sales"].sum()), places=2)
        self.assertAlmostEqual(
            self.kpis["shipping_cost_ratio"],
            float(self.df["Shipping_Cost"].sum()) / float(self.df["Sales"].sum()) * 100,
            places=4,
        )
        self.assertEqual(self.kpis["orders"], int(self.df["Order_ID"].nunique()))
        self.assertNotEqual(self.kpis["orders"], len(self.df))

    def test_zero_revenue_ratio_is_undefined(self):
        frame = _frame(
            [
                {
                    "Order_Date": "2014-01-01",
                    "Ship_Date": "2014-01-02",
                    "Order_ID": "Z",
                    "Sales": 0,
                    "Profit": -1,
                    "Shipping_Cost": 5,
                    "Ship_Mode": "Standard Class",
                    "Region": "Central",
                    "Category": "Furniture",
                    "Segment": "Consumer",
                }
            ]
        )
        kpis = calculate_logistics_kpis(frame)
        self.assertIsNone(kpis["shipping_cost_ratio"])
        self.assertEqual(kpis["shipping_cost"], 5)

    def test_shipping_mode_aggregation(self):
        self.assertEqual(set(self.mode_rows["ship_mode"]), set(self.modes))
        self.assertAlmostEqual(
            float(self.mode_rows["shipping_cost"].sum()),
            float(self.df["Shipping_Cost"].sum()),
            places=4,
        )
        self.assertAlmostEqual(
            float(self.mode_rows["revenue"].sum()),
            float(self.df["Sales"].sum()),
            places=2,
        )
        for row in self.mode_rows.to_dict("records"):
            subset = self.df.loc[self.df["Ship_Mode"] == row["ship_mode"]]
            self.assertEqual(row["orders"], int(subset["Order_ID"].nunique()))
            self.assertAlmostEqual(
                row["shipping_cost_ratio"],
                float(subset["Shipping_Cost"].sum()) / float(subset["Sales"].sum()) * 100,
                places=4,
            )
            self.assertAlmostEqual(
                row["margin"],
                float(subset["Profit"].sum()) / float(subset["Sales"].sum()) * 100,
                places=4,
            )

    def test_regional_shipping_aggregation(self):
        self.assertAlmostEqual(
            float(self.region_rows["shipping_cost"].sum()),
            float(self.df["Shipping_Cost"].sum()),
            places=4,
        )
        for row in self.region_rows.to_dict("records"):
            subset = self.df.loc[self.df["Region"] == row["region"]]
            self.assertAlmostEqual(
                row["shipping_cost_ratio"],
                float(subset["Shipping_Cost"].sum()) / float(subset["Sales"].sum()) * 100,
                places=4,
            )

    def test_date_difference_and_same_day_rate(self):
        intervals = calculate_processing_intervals(self.df)
        expected_days = (self.df["Ship_Date"] - self.df["Order_Date"]).dt.days
        self.assertTrue(intervals["processing_days"].equals(expected_days.astype("float64")))
        self.assertEqual(int(intervals["interval_negative"].sum()), 0)
        self.assertEqual(int(intervals["interval_missing"].sum()), 0)
        self.assertAlmostEqual(
            self.kpis["avg_processing_days"],
            float(expected_days.mean()),
            places=6,
        )
        self.assertAlmostEqual(
            self.kpis["median_processing_days"],
            float(expected_days.median()),
            places=6,
        )
        self.assertAlmostEqual(
            self.kpis["same_day_rate"],
            float((expected_days == 0).mean() * 100),
            places=6,
        )

    def test_missing_and_negative_intervals_are_excluded(self):
        frame = _frame(
            [
                {
                    "Order_Date": "2014-01-01",
                    "Ship_Date": "2014-01-03",
                    "Order_ID": "A",
                    "Sales": 10,
                    "Profit": 2,
                    "Shipping_Cost": 1,
                    "Ship_Mode": "Second Class",
                    "Region": "East",
                    "Category": "Technology",
                    "Segment": "Consumer",
                },
                {
                    "Order_Date": "2014-01-02",
                    "Ship_Date": "2014-01-01",
                    "Order_ID": "B",
                    "Sales": 20,
                    "Profit": 1,
                    "Shipping_Cost": 2,
                    "Ship_Mode": "Second Class",
                    "Region": "East",
                    "Category": "Technology",
                    "Segment": "Consumer",
                },
                {
                    "Order_Date": "2014-01-03",
                    "Ship_Date": pd.NaT,
                    "Order_ID": "C",
                    "Sales": 30,
                    "Profit": 3,
                    "Shipping_Cost": 3,
                    "Ship_Mode": "Second Class",
                    "Region": "East",
                    "Category": "Technology",
                    "Segment": "Consumer",
                },
            ]
        )
        intervals = calculate_processing_intervals(frame)
        kpis = calculate_logistics_kpis(frame)
        summary = aggregate_processing_time(frame)

        self.assertEqual(int(intervals["interval_negative"].sum()), 1)
        self.assertEqual(int(intervals["interval_missing"].sum()), 1)
        self.assertEqual(int(intervals["interval_valid"].sum()), 1)
        self.assertEqual(kpis["avg_processing_days"], 2.0)
        self.assertEqual(kpis["negative_intervals"], 1)
        self.assertEqual(kpis["missing_intervals"], 1)
        self.assertEqual(summary["avg_processing_days"], 2.0)
        # Negative days are not coerced to zero.
        self.assertEqual(float(intervals.loc[intervals["interval_negative"], "processing_days"].iloc[0]), -1)

    def test_single_mode_and_empty_results(self):
        same_day = filter_shipping_modes(self.df, ["Same Day"])
        modes = aggregate_shipping_modes(same_day)
        kpis = calculate_logistics_kpis(same_day)
        self.assertEqual(modes["ship_mode"].tolist(), ["Same Day"])
        self.assertGreater(kpis["same_day_rate"], 90)

        empty = filter_shipping_modes(self.df, [])
        empty_kpis = calculate_logistics_kpis(empty)
        self.assertEqual(empty_kpis["orders"], 0)
        self.assertIsNone(empty_kpis["shipping_cost_ratio"])
        self.assertTrue(aggregate_shipping_modes(empty).empty)
        insights = generate_logistics_insights(
            aggregate_shipping_modes(empty),
            aggregate_regional_shipping_cost(empty),
            empty_kpis,
        )
        self.assertIn("No logistics results", insights[0]["title"])

    def test_page_filters_change_logistics_results(self):
        full_cost = self.kpis["shipping_cost"]
        year = calculate_logistics_kpis(
            self._filtered(start=date(2014, 1, 1), end=date(2014, 12, 31))
        )
        central = calculate_logistics_kpis(self._filtered(regions=["Central"]))
        technology = calculate_logistics_kpis(self._filtered(categories=["Technology"]))
        consumer = calculate_logistics_kpis(self._filtered(segments=["Consumer"]))

        self.assertLess(year["shipping_cost"], full_cost)
        self.assertLess(central["shipping_cost"], full_cost)
        self.assertLess(technology["shipping_cost"], full_cost)
        self.assertLess(consumer["shipping_cost"], full_cost)

    def test_trends_use_aggregated_ratios_and_leave_gaps(self):
        trends = aggregate_shipping_trends(self.df, self.start, self.end)
        self.assertEqual(trends["grain"].iloc[0], "Monthly")
        january = trends.loc[trends["label"] == "Jan 2014"].iloc[0]
        month = self.df.loc[
            (self.df["Order_Date"] >= "2014-01-01") & (self.df["Order_Date"] < "2014-02-01")
        ]
        self.assertAlmostEqual(float(january["shipping_cost"]), float(month["Shipping_Cost"].sum()), places=4)
        self.assertAlmostEqual(
            float(january["shipping_cost_ratio"]),
            float(month["Shipping_Cost"].sum()) / float(month["Sales"].sum()) * 100,
            places=4,
        )
        expected_days = (month["Ship_Date"] - month["Order_Date"]).dt.days
        self.assertAlmostEqual(float(january["avg_processing_days"]), float(expected_days.mean()), places=4)

        gap = _frame(
            [
                {
                    "Order_Date": "2014-01-01",
                    "Ship_Date": "2014-01-01",
                    "Order_ID": "A",
                    "Sales": 10,
                    "Profit": 2,
                    "Shipping_Cost": 1,
                    "Ship_Mode": "Same Day",
                    "Region": "West",
                    "Category": "Furniture",
                    "Segment": "Consumer",
                },
                {
                    "Order_Date": "2014-01-03",
                    "Ship_Date": "2014-01-04",
                    "Order_ID": "B",
                    "Sales": 0,
                    "Profit": -1,
                    "Shipping_Cost": 2,
                    "Ship_Mode": "First Class",
                    "Region": "West",
                    "Category": "Furniture",
                    "Segment": "Consumer",
                },
            ]
        )
        trends = aggregate_shipping_trends(gap, date(2014, 1, 1), date(2014, 1, 3))
        self.assertEqual(trends["grain"].iloc[0], "Daily")
        missing = trends.loc[trends["period"] == pd.Timestamp("2014-01-02")].iloc[0]
        zero_revenue = trends.loc[trends["period"] == pd.Timestamp("2014-01-03")].iloc[0]
        self.assertTrue(pd.isna(missing["shipping_cost"]))
        self.assertTrue(pd.isna(missing["shipping_cost_ratio"]))
        self.assertEqual(float(zero_revenue["shipping_cost"]), 2)
        self.assertTrue(pd.isna(zero_revenue["shipping_cost_ratio"]))

    def test_insights_use_calculated_values(self):
        insights = generate_logistics_insights(self.mode_rows, self.region_rows, self.kpis)
        by_title = {note["title"]: note["body"] for note in insights}
        self.assertGreaterEqual(len(insights), 4)
        self.assertLessEqual(len(insights), 5)
        self.assertIn("Standard Class", by_title["Shipping cost leader"])
        self.assertIn("Same Day", by_title["Shipping cost intensity"])
        self.assertIn("Same Day", by_title["Fastest order-to-shipment processing"])
        self.assertIn("Africa", by_title["Regional shipping exposure"])
        self.assertIn("Same Day", by_title["Same-day shipment rate"])
        joined = " ".join(by_title.values()).lower()
        self.assertNotIn("caused", joined)
        self.assertNotIn("delivery time", joined)


class LogisticsPageTests(unittest.TestCase):
    def test_page_preserves_phase_5a_and_labels_processing_correctly(self):
        self.assertIn("Regional Performance Intelligence", PAGE_SOURCE)
        self.assertIn("SHIPPING", PAGE_SOURCE)
        self.assertIn("LOGISTICS INTELLIGENCE", PAGE_SOURCE)
        self.assertIn("calculate_logistics_kpis", PAGE_SOURCE)
        self.assertIn("logistics section only", PAGE_SOURCE)
        self.assertIn("not delivery time", PAGE_SOURCE)
        self.assertIn("not subtracted", PAGE_SOURCE)
        self.assertIn("kpi_ship_cost", PAGE_SOURCE)
        self.assertNotIn("Delivery Time", PAGE_SOURCE)
        self.assertNotIn("len(filtered)", ANALYTICS_SOURCE)
        self.assertNotIn("adjusted profit", ANALYTICS_SOURCE.lower())

    def test_page_starts(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Regional_Logistics.py"),
            default_timeout=180,
        )
        app.run()
        self.assertEqual(list(app.exception), [])
        text = " ".join((block.value or "") for block in app.markdown)
        headings = " ".join((block.value or "") for block in app.subheader)
        self.assertIn("Regional Performance Intelligence", text)
        self.assertIn("$12.64M", text)
        self.assertIn("25,035", text)
        self.assertIn("SHIPPING", text)
        self.assertIn("Shipping Mode Performance", headings)
        self.assertIn("Regional Shipping Cost Analysis", headings)
        self.assertIn("Order-to-Shipment Processing Time", headings)
        self.assertIn("Shipping & Logistics Trends", headings)
        self.assertIn("Logistics Business Insights", headings)


if __name__ == "__main__":
    unittest.main()
