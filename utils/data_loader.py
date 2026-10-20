from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# DATA FILE LOCATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "Global_Superstore.xlsx"


# ============================================================
# LOAD AND PREPARE GLOBAL SUPERSTORE DATA
# ============================================================

@st.cache_data(show_spinner="Loading Global Superstore data...")
def load_superstore_data():

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Global Superstore dataset not found: {DATA_PATH}"
        )

    df = pd.read_excel(DATA_PATH)

    # --------------------------------------------------------
    # STANDARDIZE COLUMN NAMES
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "Order.Date": "Order_Date",
            "Ship.Date": "Ship_Date",
            "Order.ID": "Order_ID",
            "Customer.ID": "Customer_ID",
            "Customer.Name": "Customer_Name",
            "Product.ID": "Product_ID",
            "Product.Name": "Product_Name",
            "Sub.Category": "Sub_Category",
            "Ship.Mode": "Ship_Mode",
            "Shipping.Cost": "Shipping_Cost",
            "Order.Priority": "Order_Priority",
            "Row.ID": "Row_ID",
        }
    )

    # --------------------------------------------------------
    # VALIDATE REQUIRED COLUMNS
    # --------------------------------------------------------

    required_columns = [
        "Order_Date",
        "Ship_Date",
        "Order_ID",
        "Sales",
        "Profit",
        "Region",
        "Category",
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # CONVERT DATE COLUMNS
    # --------------------------------------------------------

    df["Order_Date"] = pd.to_datetime(
        df["Order_Date"],
        errors="coerce"
    )

    df["Ship_Date"] = pd.to_datetime(
        df["Ship_Date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # CONVERT NUMERIC COLUMNS
    # --------------------------------------------------------

    numeric_columns = [
        "Sales",
        "Profit",
        "Quantity",
        "Discount",
        "Shipping_Cost",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # --------------------------------------------------------
    # REMOVE INVALID RECORDS
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "Order_Date",
            "Order_ID",
            "Sales",
            "Profit",
        ]
    ).copy()

    # --------------------------------------------------------
    # DERIVED COLUMNS
    # --------------------------------------------------------

    df["Year"] = df["Order_Date"].dt.year

    df["Year_Month"] = (
        df["Order_Date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    # Days from order placement to shipment.
    # This is NOT customer delivery time.

    df["Shipping_Days"] = (
        df["Ship_Date"] - df["Order_Date"]
    ).dt.days

    # --------------------------------------------------------
    # SORT DATA
    # --------------------------------------------------------

    df = df.sort_values(
        "Order_Date"
    ).reset_index(drop=True)

    return df