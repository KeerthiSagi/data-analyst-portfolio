"""Data Explorer filtering, search, export, and quality checks for Phase 6."""

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
    COUNTRY_SCOPE_SELECTED,
    CSV_FILENAME,
    DEFAULT_VISIBLE_COLUMNS,
    SEARCH_COLUMNS,
    available_columns,
    calculate_data_quality,
    calculate_explorer_kpis,
    filter_explorer_data,
    prepare_csv_export,
    prepare_display_frame,
    resolve_country_selection,
    search_explorer_data,
)
from utils.data_loader import load_superstore_data

PAGE_SOURCE = (ROOT / "pages" / "3_Data_Explorer.py").read_text()
UTIL_SOURCE = (ROOT / "utils" / "data_explorer.py").read_text()


def _frame(rows):
    frame = pd.DataFrame(rows)
    if "Order_Date" in frame.columns:
        frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    return frame


def _all_filter_args(df: pd.DataFrame, **overrides):
    params = dict(
        start=df["Order_Date"].min().date(),
        end=df["Order_Date"].max().date(),
        regions=sorted(df["Region"].dropna().unique()) if "Region" in df.columns else None,
        countries=sorted(df["Country"].dropna().unique()) if "Country" in df.columns else None,
        categories=sorted(df["Category"].dropna().unique()) if "Category" in df.columns else None,
        sub_categories=(
            sorted(df["Sub_Category"].dropna().unique()) if "Sub_Category" in df.columns else None
        ),
        segments=sorted(df["Segment"].dropna().unique()) if "Segment" in df.columns else None,
        ship_modes=sorted(df["Ship_Mode"].dropna().unique()) if "Ship_Mode" in df.columns else None,
    )
    params.update(overrides)
    return params


class ExplorerFullDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.filtered = filter_explorer_data(cls.df, **_all_filter_args(cls.df))
        cls.kpis = calculate_explorer_kpis(cls.filtered)

    def test_full_dataset_record_count(self):
        self.assertEqual(len(self.df), 51_290)
        self.assertEqual(self.kpis["line_items"], 51_290)

    def test_unique_order_count(self):
        self.assertEqual(self.kpis["orders"], 25_035)
        self.assertEqual(self.kpis["orders"], int(self.df["Order_ID"].nunique()))
        self.assertNotEqual(self.kpis["orders"], len(self.df))

    def test_revenue_reconciliation(self):
        self.assertAlmostEqual(self.kpis["revenue"], float(self.df["Sales"].sum()), places=2)
        self.assertAlmostEqual(self.kpis["revenue"], 12_642_905.0, places=0)

    def test_profit_reconciliation(self):
        self.assertAlmostEqual(self.kpis["profit"], float(self.df["Profit"].sum()), places=2)
        self.assertAlmostEqual(self.kpis["profit"], 1_467_457.29, places=2)


class ExplorerFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_date_filtering(self):
        result = filter_explorer_data(
            self.df,
            **_all_filter_args(
                self.df,
                start=date(2014, 1, 1),
                end=date(2014, 1, 31),
            ),
        )
        self.assertTrue((result["Order_Date"].dt.date >= date(2014, 1, 1)).all())
        self.assertTrue((result["Order_Date"].dt.date <= date(2014, 1, 31)).all())
        expected = self.df[
            (self.df["Order_Date"].dt.date >= date(2014, 1, 1))
            & (self.df["Order_Date"].dt.date <= date(2014, 1, 31))
        ]
        self.assertEqual(len(result), len(expected))

    def test_region_filtering(self):
        result = filter_explorer_data(self.df, **_all_filter_args(self.df, regions=["West"]))
        self.assertTrue((result["Region"] == "West").all())
        self.assertEqual(len(result), int((self.df["Region"] == "West").sum()))

    def test_country_filtering(self):
        self.assertIn("Country", self.df.columns)
        country = sorted(self.df["Country"].dropna().unique())[0]
        result = filter_explorer_data(self.df, **_all_filter_args(self.df, countries=[country]))
        self.assertTrue((result["Country"] == country).all())
        self.assertEqual(len(result), int((self.df["Country"] == country).sum()))

    def test_country_scope_all_matches_full_list(self):
        countries = sorted(self.df["Country"].dropna().unique().tolist())
        resolved = resolve_country_selection(
            countries,
            scope=COUNTRY_SCOPE_ALL,
            selected=[],
        )
        self.assertEqual(resolved, countries)
        all_scope = filter_explorer_data(self.df, **_all_filter_args(self.df, countries=resolved))
        self.assertEqual(len(all_scope), len(self.df))

    def test_country_scope_selected_can_be_empty(self):
        countries = sorted(self.df["Country"].dropna().unique().tolist())
        resolved = resolve_country_selection(
            countries,
            scope=COUNTRY_SCOPE_SELECTED,
            selected=[],
        )
        self.assertEqual(resolved, [])
        empty = filter_explorer_data(self.df, **_all_filter_args(self.df, countries=resolved))
        self.assertTrue(empty.empty)

    def test_category_filtering(self):
        result = filter_explorer_data(
            self.df, **_all_filter_args(self.df, categories=["Technology"])
        )
        self.assertTrue((result["Category"] == "Technology").all())

    def test_sub_category_filtering(self):
        result = filter_explorer_data(
            self.df, **_all_filter_args(self.df, sub_categories=["Phones"])
        )
        self.assertTrue((result["Sub_Category"] == "Phones").all())
        self.assertGreater(len(result), 0)

    def test_segment_filtering(self):
        result = filter_explorer_data(
            self.df, **_all_filter_args(self.df, segments=["Consumer"])
        )
        self.assertTrue((result["Segment"] == "Consumer").all())

    def test_shipping_mode_filtering(self):
        result = filter_explorer_data(
            self.df, **_all_filter_args(self.df, ship_modes=["Same Day"])
        )
        self.assertTrue((result["Ship_Mode"] == "Same Day").all())

    def test_combined_filters(self):
        result = filter_explorer_data(
            self.df,
            **_all_filter_args(
                self.df,
                start=date(2013, 1, 1),
                end=date(2013, 12, 31),
                regions=["Central"],
                categories=["Furniture"],
                segments=["Corporate"],
                ship_modes=["Standard Class"],
            ),
        )
        self.assertTrue((result["Region"] == "Central").all())
        self.assertTrue((result["Category"] == "Furniture").all())
        self.assertTrue((result["Segment"] == "Corporate").all())
        self.assertTrue((result["Ship_Mode"] == "Standard Class").all())
        self.assertTrue((result["Order_Date"].dt.year == 2013).all())


class ExplorerSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_case_insensitive_search(self):
        sample = self.df["Customer_Name"].dropna().iloc[0]
        upper = search_explorer_data(self.df, sample.upper())
        lower = search_explorer_data(self.df, sample.lower())
        self.assertEqual(len(upper), len(lower))
        self.assertGreater(len(upper), 0)

    def test_partial_search(self):
        order_id = str(self.df["Order_ID"].iloc[0])
        partial = order_id[: max(4, len(order_id) // 2)]
        result = search_explorer_data(self.df, partial)
        self.assertGreater(len(result), 0)
        self.assertTrue(
            result["Order_ID"].astype(str).str.contains(partial, case=False, regex=False).any()
            | result["Product_Name"].astype(str).str.contains(partial, case=False, regex=False).any()
            | result["Customer_Name"].astype(str).str.contains(partial, case=False, regex=False).any()
            | result["Customer_ID"].astype(str).str.contains(partial, case=False, regex=False).any()
        )

    def test_empty_search_results(self):
        result = search_explorer_data(self.df, "zzz-no-match-atlas-xyz-999")
        self.assertTrue(result.empty)
        kpis = calculate_explorer_kpis(result)
        self.assertEqual(kpis["line_items"], 0)
        self.assertEqual(kpis["orders"], 0)
        self.assertEqual(kpis["revenue"], 0.0)

    def test_missing_search_columns(self):
        frame = _frame(
            [
                {"Order_Date": "2014-01-01", "Sales": 10, "Profit": 1, "Region": "West"},
                {"Order_Date": "2014-01-02", "Sales": 20, "Profit": 2, "Region": "East"},
            ]
        )
        result = search_explorer_data(frame, "West")
        self.assertTrue(result.empty)

    def test_search_respects_filtered_dataset(self):
        filtered = filter_explorer_data(self.df, **_all_filter_args(self.df, regions=["West"]))
        name = filtered["Customer_Name"].dropna().iloc[0]
        east_only = filter_explorer_data(self.df, **_all_filter_args(self.df, regions=["East"]))
        hidden = search_explorer_data(east_only, name)
        # Name may also exist in East; assert search never expands beyond the filter frame.
        self.assertLessEqual(len(hidden), len(east_only))
        self.assertTrue(hidden.empty or (hidden["Region"] == "East").all())
        west_hits = search_explorer_data(filtered, name)
        self.assertTrue((west_hits["Region"] == "West").all())

    def test_whitespace_tolerant_search(self):
        sample = self.df["Product_Name"].dropna().iloc[0]
        padded = f"  {sample}  "
        result = search_explorer_data(self.df, padded)
        self.assertGreater(len(result), 0)


class ExplorerColumnAndEmptyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_column_selection(self):
        selected = available_columns(self.df, DEFAULT_VISIBLE_COLUMNS)
        self.assertEqual(selected, DEFAULT_VISIBLE_COLUMNS)
        display = prepare_display_frame(self.df, selected, limit=25)
        self.assertEqual(list(display["preview"].columns), selected)
        self.assertEqual(display["preview_rows"], 25)
        self.assertTrue(display["truncated"])
        self.assertEqual(display["total_rows"], len(self.df))

    def test_column_selection_skips_missing(self):
        selected = available_columns(self.df, DEFAULT_VISIBLE_COLUMNS + ["Does_Not_Exist"])
        self.assertNotIn("Does_Not_Exist", selected)

    def test_empty_datasets(self):
        empty = self.df.iloc[0:0].copy()
        filtered = filter_explorer_data(empty, **_all_filter_args(self.df))
        searched = search_explorer_data(empty, "anything")
        kpis = calculate_explorer_kpis(empty)
        quality = calculate_data_quality(empty)
        export = prepare_csv_export(empty)
        decoded = export.decode("utf-8")

        self.assertTrue(filtered.empty)
        self.assertTrue(searched.empty)
        self.assertEqual(kpis["line_items"], 0)
        self.assertEqual(kpis["orders"], 0)
        self.assertEqual(kpis["revenue"], 0.0)
        self.assertEqual(quality["total_records"], 0)
        self.assertEqual(quality["full_row_duplicates"], 0)
        self.assertEqual(quality["repeated_order_ids"], 0)
        self.assertIn("Order_ID", decoded)
        self.assertEqual(len(pd.read_csv(StringIO(decoded))), 0)


class ExplorerCsvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()

    def test_csv_export_row_count(self):
        subset = filter_explorer_data(self.df, **_all_filter_args(self.df, regions=["Canada"]))
        payload = prepare_csv_export(subset)
        exported = pd.read_csv(StringIO(payload.decode("utf-8")))
        self.assertEqual(len(exported), len(subset))
        self.assertEqual(list(exported.columns), list(subset.columns))

    def test_csv_export_preserves_values(self):
        subset = self.df.head(20).copy()
        payload = prepare_csv_export(subset)
        exported = pd.read_csv(StringIO(payload.decode("utf-8")))
        self.assertEqual(float(exported["Sales"].sum()), float(subset["Sales"].sum()))
        self.assertEqual(float(exported["Profit"].sum()), float(subset["Profit"].sum()))
        self.assertListEqual(exported["Order_ID"].tolist(), subset["Order_ID"].astype(str).tolist())

    def test_csv_export_all_columns_by_default(self):
        payload = prepare_csv_export(self.df.head(5))
        exported = pd.read_csv(StringIO(payload.decode("utf-8")))
        self.assertEqual(list(exported.columns), list(self.df.columns))

    def test_csv_visible_columns_option(self):
        columns = available_columns(self.df, ["Order_ID", "Sales", "Profit"])
        payload = prepare_csv_export(self.df.head(5), columns=columns)
        exported = pd.read_csv(StringIO(payload.decode("utf-8")))
        self.assertEqual(list(exported.columns), columns)


class ExplorerQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = load_superstore_data()
        cls.quality = calculate_data_quality(cls.df)

    def test_missing_value_summary(self):
        self.assertEqual(self.quality["total_records"], len(self.df))
        self.assertEqual(self.quality["total_columns"], self.df.shape[1])
        expected_missing = self.df.isna().sum()
        expected_missing = expected_missing.loc[expected_missing > 0]
        pd.testing.assert_series_equal(
            self.quality["missing_by_column"].astype(int),
            expected_missing.astype(int),
            check_names=False,
        )

    def test_full_row_duplicate_detection(self):
        self.assertEqual(self.quality["full_row_duplicates"], int(self.df.duplicated().sum()))
        self.assertEqual(self.quality["full_row_duplicates"], 0)

        frame = _frame(
            [
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 1},
                {"Order_Date": "2014-01-01", "Order_ID": "A", "Sales": 10, "Profit": 1},
                {"Order_Date": "2014-01-02", "Order_ID": "B", "Sales": 5, "Profit": 2},
            ]
        )
        quality = calculate_data_quality(frame)
        self.assertEqual(quality["full_row_duplicates"], 1)

    def test_repeated_order_id_handling(self):
        self.assertEqual(self.quality["unique_orders"], 25_035)
        self.assertEqual(self.quality["repeated_order_ids"], len(self.df) - 25_035)
        self.assertGreater(self.quality["repeated_order_ids"], 0)
        self.assertEqual(self.quality["full_row_duplicates"], 0)
        self.assertNotEqual(self.quality["repeated_order_ids"], self.quality["full_row_duplicates"])
        self.assertEqual(self.quality["date_start"], date(2011, 1, 1))
        self.assertEqual(self.quality["date_end"], date(2014, 12, 31))


class ExplorerPageContractTests(unittest.TestCase):
    def test_page_uses_utilities_and_export(self):
        self.assertIn("filter_explorer_data", PAGE_SOURCE)
        self.assertIn("search_explorer_data", PAGE_SOURCE)
        self.assertIn("calculate_explorer_kpis", PAGE_SOURCE)
        self.assertIn("calculate_data_quality", PAGE_SOURCE)
        self.assertIn("prepare_csv_export", PAGE_SOURCE)
        self.assertIn("Download Filtered Data", PAGE_SOURCE)
        self.assertIn("Download Visible Columns Only", PAGE_SOURCE)
        self.assertIn("Reset Filters", PAGE_SOURCE)
        self.assertIn("Data Quality Overview", PAGE_SOURCE)
        self.assertIn("CSV_FILENAME", PAGE_SOURCE)
        self.assertEqual(CSV_FILENAME, "atlas_filtered_superstore.csv")
        self.assertIn("COUNTRY_SCOPE_ALL", PAGE_SOURCE)
        self.assertIn("resolve_country_selection", PAGE_SOURCE)
        self.assertIn("render_project_nav", PAGE_SOURCE)
        self.assertNotIn("default=countries", PAGE_SOURCE)

    def test_utilities_document_duplicate_distinction(self):
        self.assertIn("full-row duplicates", UTIL_SOURCE.lower().replace("_", "-") or UTIL_SOURCE)
        self.assertIn("Repeated Order_ID", UTIL_SOURCE)
        for name in SEARCH_COLUMNS:
            self.assertIn(name, UTIL_SOURCE)


class ExistingAnalyticsRegressionTests(unittest.TestCase):
    def test_existing_analytics_modules_importable(self):
        from utils import executive_analytics, logistics_analytics, regional_analytics, segment_analytics
        from utils.kpi_metrics import aggregate_kpi_trends

        self.assertTrue(callable(segment_analytics.calculate_segment_kpis))
        self.assertTrue(callable(regional_analytics.calculate_regional_kpis))
        self.assertTrue(callable(logistics_analytics.calculate_logistics_kpis))
        self.assertTrue(callable(executive_analytics.summarize_groups))
        self.assertTrue(callable(aggregate_kpi_trends))

    def test_existing_pages_still_present(self):
        self.assertTrue((ROOT / "pages" / "1_Segment_Performance.py").exists())
        self.assertTrue((ROOT / "pages" / "2_Regional_Logistics.py").exists())
        self.assertTrue((ROOT / "app_kpi_dashboard.py").exists())


if __name__ == "__main__":
    unittest.main()
