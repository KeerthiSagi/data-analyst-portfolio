"""Filtering, search, KPI, quality, and CSV helpers for the Data Explorer page.

Repeated Order_ID values are expected for line-item data. Only exact duplicate
rows are treated as full-row duplicates.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd


DEFAULT_VISIBLE_COLUMNS = [
    "Order_ID",
    "Order_Date",
    "Customer_Name",
    "Product_Name",
    "Category",
    "Sub_Category",
    "Region",
    "Sales",
    "Profit",
    "Discount",
    "Ship_Mode",
]

SEARCH_COLUMNS = [
    "Order_ID",
    "Product_Name",
    "Customer_Name",
    "Customer_ID",
]

PREVIEW_ROW_LIMIT = 500
CSV_FILENAME = "atlas_filtered_superstore.csv"
COUNTRY_SCOPE_ALL = "All countries"
COUNTRY_SCOPE_SELECTED = "Select countries"


def available_columns(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    """Keep only columns that exist in the frame, in the requested order."""

    return [column for column in candidates if column in df.columns]


def resolve_country_selection(
    all_countries: list[str],
    *,
    scope: str,
    selected: list[str] | None,
) -> list[str] | None:
    """Map the compact Country UI to the values used by filter_explorer_data.

    All countries keeps filter semantics identical to selecting every country.
    Select countries passes the explicit multiselect values (possibly empty).
    """

    if all_countries is None:
        return None
    countries = list(all_countries)
    if not countries:
        return None
    if scope != COUNTRY_SCOPE_SELECTED:
        return countries
    return list(selected or [])


def filter_explorer_data(
    df: pd.DataFrame,
    *,
    start,
    end,
    regions,
    countries,
    categories,
    sub_categories,
    segments,
    ship_modes,
) -> pd.DataFrame:
    """Apply explorer filters without mutating the source frame."""

    if df.empty:
        return df.iloc[0:0].copy()

    mask = (df["Order_Date"].dt.date >= start) & (df["Order_Date"].dt.date <= end)
    if regions is not None and "Region" in df.columns:
        mask &= df["Region"].isin(regions)
    if countries is not None and "Country" in df.columns:
        mask &= df["Country"].isin(countries)
    if categories is not None and "Category" in df.columns:
        mask &= df["Category"].isin(categories)
    if sub_categories is not None and "Sub_Category" in df.columns:
        mask &= df["Sub_Category"].isin(sub_categories)
    if segments is not None and "Segment" in df.columns:
        mask &= df["Segment"].isin(segments)
    if ship_modes is not None and "Ship_Mode" in df.columns:
        mask &= df["Ship_Mode"].isin(ship_modes)
    return df.loc[mask].copy()


def search_explorer_data(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Case-insensitive partial match across available search fields.

    Search runs only on the provided frame. An empty query returns the frame
    unchanged. Missing search columns are skipped.
    """

    if df.empty:
        return df.iloc[0:0].copy()

    term = " ".join(str(query or "").split()).strip().lower()
    if not term:
        return df.copy()

    columns = available_columns(df, SEARCH_COLUMNS)
    if not columns:
        return df.iloc[0:0].copy()

    matches = pd.Series(False, index=df.index)
    for column in columns:
        values = df[column].astype(str).str.lower().str.contains(term, na=False, regex=False)
        matches |= values
    return df.loc[matches].copy()


def calculate_explorer_kpis(df: pd.DataFrame) -> dict:
    """Headline counts and totals for the current explorer view."""

    if df.empty:
        return {
            "line_items": 0,
            "orders": 0,
            "revenue": 0.0,
            "profit": 0.0,
        }

    return {
        "line_items": int(len(df)),
        "orders": int(df["Order_ID"].nunique()) if "Order_ID" in df.columns else 0,
        "revenue": float(df["Sales"].sum()) if "Sales" in df.columns else 0.0,
        "profit": float(df["Profit"].sum()) if "Profit" in df.columns else 0.0,
    }


def calculate_data_quality(df: pd.DataFrame) -> dict:
    """Quality summary for the currently filtered explorer view.

    Repeated Order_ID values are reported separately from exact full-row duplicates.
    """

    if df.empty:
        return {
            "total_records": 0,
            "total_columns": 0,
            "missing_by_column": pd.Series(dtype="int64"),
            "full_row_duplicates": 0,
            "repeated_order_ids": 0,
            "unique_orders": 0,
            "date_start": None,
            "date_end": None,
        }

    missing = df.isna().sum().sort_values(ascending=False)
    missing = missing.loc[missing > 0]
    unique_orders = int(df["Order_ID"].nunique()) if "Order_ID" in df.columns else 0
    repeated_order_ids = int(len(df) - unique_orders) if "Order_ID" in df.columns else 0
    date_start = None
    date_end = None
    if "Order_Date" in df.columns and df["Order_Date"].notna().any():
        date_start = pd.Timestamp(df["Order_Date"].min()).date()
        date_end = pd.Timestamp(df["Order_Date"].max()).date()

    return {
        "total_records": int(len(df)),
        "total_columns": int(df.shape[1]),
        "missing_by_column": missing.astype(int),
        "full_row_duplicates": int(df.duplicated().sum()),
        "repeated_order_ids": repeated_order_ids,
        "unique_orders": unique_orders,
        "date_start": date_start,
        "date_end": date_end,
    }


def prepare_display_frame(df: pd.DataFrame, columns: list[str], limit: int = PREVIEW_ROW_LIMIT):
    """Return a preview frame and metadata for the interactive table."""

    selected = available_columns(df, columns) or list(df.columns)
    total = int(len(df))
    preview = df.loc[:, selected].head(limit).copy()
    return {
        "preview": preview,
        "columns": selected,
        "total_rows": total,
        "preview_rows": int(len(preview)),
        "truncated": total > limit,
        "limit": limit,
    }


def prepare_csv_export(df: pd.DataFrame, columns: list[str] | None = None) -> bytes:
    """Serialize filtered rows to UTF-8 CSV without the DataFrame index.

    When columns is None, every column is exported. An explicit column list
    is only used when the caller requests a visible-columns export.
    """

    if df.empty:
        export = df.iloc[0:0].copy()
    elif columns is None:
        export = df.copy()
    else:
        selected = available_columns(df, columns) or list(df.columns)
        export = df.loc[:, selected].copy()

    buffer = StringIO()
    export.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")
