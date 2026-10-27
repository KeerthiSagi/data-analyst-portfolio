"""Configuration: data location, column schema, and analysis dimensions."""

from __future__ import annotations

from pathlib import Path

# ------------------------------------------------------------------
# Data location
# ------------------------------------------------------------------
# Resolution order (first match wins):
#   1. An explicit path passed to the loader
#   2. The CAUSE_DATA_PATH environment variable
#   3. project2-root-cause-analyzer/data/Global_Superstore.xlsx
#      (drop the file here to run Project 2 on its own)
#   4. The shared copy in Project 1 (read-only, never modified)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH_ENV_VAR = "CAUSE_DATA_PATH"
DATASET_FILENAME = "Global_Superstore.xlsx"

LOCAL_DATA_PATH = PROJECT_ROOT / "data" / DATASET_FILENAME
SHARED_DATA_PATH = (
    PROJECT_ROOT.parent / "project1-atlas-analytics" / "data" / DATASET_FILENAME
)
DEFAULT_DATA_PATHS: tuple[Path, ...] = (LOCAL_DATA_PATH, SHARED_DATA_PATH)

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# ------------------------------------------------------------------
# Column schema
# ------------------------------------------------------------------
# Source headers are matched after normalising (lowercase, letters and
# digits only), so "Order.ID", "Order ID" and "order_id" all map to
# "order_id".

COLUMN_ALIASES: dict[str, str] = {
    "orderid": "order_id",
    "customerid": "customer_id",
    "customername": "customer_name",
    "orderdate": "order_date",
    "shipdate": "ship_date",
    "shipmode": "ship_mode",
    "orderpriority": "order_priority",
    "sales": "sales",
    "profit": "profit",
    "quantity": "quantity",
    "discount": "discount",
    "shippingcost": "shipping_cost",
    "market": "market",
    "region": "region",
    "country": "country",
    "state": "state",
    "city": "city",
    "category": "category",
    "subcategory": "sub_category",
    "segment": "segment",
    "productid": "product_id",
    "productname": "product_name",
    "rowid": "row_id",
}

REQUIRED_COLUMNS: tuple[str, ...] = (
    "order_id",
    "customer_id",
    "order_date",
    "sales",
    "profit",
    "market",
    "region",
    "category",
    "segment",
)

NUMERIC_COLUMNS: tuple[str, ...] = ("sales", "profit", "quantity", "discount", "shipping_cost")
DATE_COLUMNS: tuple[str, ...] = ("order_date", "ship_date")

# Columns that make up one transaction (see data.build_order_key).
ORDER_KEY_COLUMNS: tuple[str, ...] = ("order_id", "customer_id", "order_date")
ORDER_KEY_COLUMN = "order_key"

# Attributes that should be identical on every row of a single order.
# Used to check that the composite key identifies one transaction.
ORDER_LEVEL_ATTRIBUTES: tuple[str, ...] = (
    "ship_date",
    "ship_mode",
    "order_priority",
    "market",
    "region",
    "country",
    "state",
    "city",
    "segment",
    "customer_name",
)

MISSING_LABEL = "(Missing)"

# ------------------------------------------------------------------
# Analysis dimensions
# ------------------------------------------------------------------
# Region names repeat across markets ("Central" exists in US, EU and
# LATAM), so the Region dimension uses a market-qualified label such as
# "US · Central". The raw value stays available in the "region" column.

MARKET_REGION_COLUMN = "market_region"

DIMENSIONS: dict[str, str] = {
    "Market": "market",
    "Region": MARKET_REGION_COLUMN,
    "Category": "category",
    "Customer Segment": "segment",
}
