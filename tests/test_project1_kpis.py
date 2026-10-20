"""Core data and KPI checks for the executive sales dashboard."""

import ast
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.data_loader import load_superstore_data
APP_SOURCE = (ROOT / "app_kpi_dashboard.py").read_text()


def calculate_change(current, previous):
    """Same rule as app_kpi_dashboard.calculate_change."""
    if previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def previous_window(start_date, end_date, dataset_start):
    period_days = (end_date - start_date).days + 1
    previous_end = start_date - pd.Timedelta(days=1)
    previous_start = previous_end - pd.Timedelta(days=period_days - 1)
    covered = previous_start >= dataset_start
    return previous_start, previous_end, period_days, covered


def app_calculate_change():
    module = ast.parse(APP_SOURCE)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "calculate_change":
            namespace = {}
            exec(ast.get_source_segment(APP_SOURCE, node), namespace)
            return namespace["calculate_change"]
    raise AssertionError("calculate_change is missing from app_kpi_dashboard.py")


class DatasetValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_row_count_and_date_range(self):
        self.assertEqual(len(self.df), 51290)
        self.assertEqual(self.df["Order_Date"].min(), pd.Timestamp("2011-01-01"))
        self.assertEqual(self.df["Order_Date"].max(), pd.Timestamp("2014-12-31"))

    def test_published_totals(self):
        revenue = float(self.df["Sales"].sum())
        profit = float(self.df["Profit"].sum())
        orders = int(self.df["Order_ID"].nunique())

        self.assertEqual(revenue, 12642905)
        self.assertAlmostEqual(profit, 1467457.29, places=2)
        self.assertEqual(orders, 25035)
        self.assertNotEqual(orders, len(self.df))
        self.assertAlmostEqual(profit / revenue * 100, 11.61, places=2)

    def test_required_columns_have_no_missing_values(self):
        required = [
            "Order_Date",
            "Ship_Date",
            "Order_ID",
            "Sales",
            "Profit",
            "Region",
            "Category",
            "Segment",
        ]
        for column in required:
            self.assertEqual(int(self.df[column].isna().sum()), 0, column)

    def test_numeric_types_and_negative_profit_kept(self):
        for column in ["Sales", "Profit", "Quantity", "Discount", "Shipping_Cost"]:
            self.assertTrue(pd.api.types.is_numeric_dtype(self.df[column]), column)

        negative = self.df["Profit"] < 0
        self.assertEqual(int(negative.sum()), 12544)
        self.assertAlmostEqual(float(self.df.loc[negative, "Profit"].sum()), -920646.16, places=2)

    def test_identifiers_and_duplicates(self):
        self.assertEqual(int(self.df["Row_ID"].duplicated().sum()), 0)
        self.assertEqual(int(self.df.duplicated().sum()), 0)
        self.assertFalse(self.df["Order_ID"].astype(str).str.strip().eq("").any())

    def test_shipping_days_are_order_to_ship(self):
        expected = (self.df["Ship_Date"] - self.df["Order_Date"]).dt.days
        self.assertTrue(self.df["Shipping_Days"].equals(expected))
        self.assertEqual(int(self.df["Shipping_Days"].isna().sum()), 0)
        self.assertGreaterEqual(int(self.df["Shipping_Days"].min()), 0)
        self.assertLessEqual(int(self.df["Shipping_Days"].max()), 7)

    def test_category_and_region_values(self):
        self.assertEqual(
            set(self.df["Category"].unique()),
            {"Furniture", "Office Supplies", "Technology"},
        )
        self.assertEqual(
            set(self.df["Region"].unique()),
            {
                "Africa",
                "Canada",
                "Caribbean",
                "Central",
                "Central Asia",
                "EMEA",
                "East",
                "North",
                "North Asia",
                "Oceania",
                "South",
                "Southeast Asia",
                "West",
            },
        )


class KpiCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.dataset_start = cls.df["Order_Date"].min().date()

    def _slice(self, start, end, regions, categories):
        frame = self.df
        return frame[
            (frame["Order_Date"].dt.date >= start)
            & (frame["Order_Date"].dt.date <= end)
            & (frame["Region"].isin(regions))
            & (frame["Category"].isin(categories))
        ]

    def test_filters_reduce_revenue(self):
        full_revenue = float(self.df["Sales"].sum())
        subset = self._slice(
            date(2013, 1, 1),
            date(2013, 12, 31),
            ["Central"],
            ["Technology"],
        )
        self.assertGreater(len(subset), 0)
        self.assertLess(float(subset["Sales"].sum()), full_revenue)
        self.assertTrue(set(subset["Region"].unique()) <= {"Central"})
        self.assertTrue(set(subset["Category"].unique()) <= {"Technology"})

    def test_empty_filter_selection(self):
        empty = self._slice(
            date(2013, 1, 1),
            date(2013, 12, 31),
            [],
            ["Technology"],
        )
        self.assertTrue(empty.empty)

    def test_previous_window_is_equal_and_adjacent(self):
        start, end = date(2013, 1, 1), date(2013, 12, 31)
        previous_start, previous_end, period_days, covered = previous_window(
            start, end, self.dataset_start
        )

        self.assertTrue(covered)
        self.assertEqual(period_days, 365)
        self.assertEqual((previous_end - previous_start).days + 1, period_days)
        self.assertEqual(previous_end, start - timedelta(days=1))
        self.assertEqual(previous_start, date(2012, 1, 2))
        self.assertLess(previous_end, start)

    def test_full_history_has_no_complete_prior_period(self):
        start = self.df["Order_Date"].min().date()
        end = self.df["Order_Date"].max().date()
        _, _, _, covered = previous_window(start, end, self.dataset_start)
        self.assertFalse(covered)

    def test_margin_change_is_percentage_points(self):
        start, end = date(2013, 1, 1), date(2013, 12, 31)
        regions = sorted(self.df["Region"].unique())
        categories = sorted(self.df["Category"].unique())
        current = self._slice(start, end, regions, categories)

        previous_start, previous_end, _, covered = previous_window(
            start, end, self.dataset_start
        )
        self.assertTrue(covered)
        previous = self._slice(previous_start, previous_end, regions, categories)

        current_margin = current["Profit"].sum() / current["Sales"].sum() * 100
        previous_margin = previous["Profit"].sum() / previous["Sales"].sum() * 100
        margin_change = current_margin - previous_margin
        percent_change = calculate_change(current_margin, previous_margin)

        self.assertAlmostEqual(margin_change, 0.4666, places=3)
        self.assertNotAlmostEqual(margin_change, percent_change, places=3)

    def test_zero_denominator_and_app_function(self):
        app_change = app_calculate_change()
        for fn in (calculate_change, app_change):
            self.assertIsNone(fn(100, 0))
            self.assertIsNone(fn(100, None))
            self.assertAlmostEqual(fn(110, 100), 10)
            self.assertAlmostEqual(fn(-50, -100), 50)

    def test_dashboard_uses_order_id_and_point_margin(self):
        self.assertIn('filtered_df["Order_ID"].nunique()', APP_SOURCE)
        self.assertIn("margin_change = profit_margin - previous_margin", APP_SOURCE)
        self.assertIn("if previous_start >= dataset_start:", APP_SOURCE)
        self.assertNotIn("len(filtered_df)", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
