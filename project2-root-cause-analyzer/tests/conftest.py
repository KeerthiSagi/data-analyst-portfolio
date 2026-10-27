"""Shared fixtures: small hand-built frames that mimic the source schema."""

import pandas as pd
import pytest


def make_raw(rows):
    """Build a raw frame using the Global Superstore dot-style headers."""
    defaults = {
        "Customer.Name": "Pat Doe",
        "Ship.Mode": "Standard Class",
        "Order.Priority": "Medium",
        "Country": "United States",
        "State": "Kansas",
        "City": "Wichita",
        "Quantity": 1,
        "Discount": 0.0,
        "Sub.Category": "Chairs",
    }
    records = []
    for i, row in enumerate(rows, start=1):
        record = {"Row.ID": i, **defaults, **row}
        record.setdefault("Ship.Date", record["Order.Date"])
        records.append(record)
    return pd.DataFrame(records)


@pytest.fixture
def raw_orders():
    """Five rows, four transactions.

    * O-1 has two lines (one transaction).
    * O-2 is reused by two different customers on different dates
      (two transactions).
    * O-3 is a single line.
    """
    return make_raw(
        [
            {"Order.ID": "O-1", "Customer.ID": "C-1", "Order.Date": "2014-01-05",
             "Sales": 100, "Profit": 20, "Market": "US", "Region": "Central",
             "Category": "Furniture", "Segment": "Consumer"},
            {"Order.ID": "O-1", "Customer.ID": "C-1", "Order.Date": "2014-01-05",
             "Sales": 50, "Profit": -5, "Market": "US", "Region": "Central",
             "Category": "Technology", "Segment": "Consumer"},
            {"Order.ID": "O-2", "Customer.ID": "C-2", "Order.Date": "2014-02-10",
             "Sales": 80, "Profit": 8, "Market": "EU", "Region": "Central",
             "Category": "Office Supplies", "Segment": "Corporate"},
            {"Order.ID": "O-2", "Customer.ID": "C-3", "Order.Date": "2014-03-15",
             "Sales": 60, "Profit": 6, "Market": "EU", "Region": "North",
             "Category": "Office Supplies", "Segment": "Home Office"},
            {"Order.ID": "O-3", "Customer.ID": "C-1", "Order.Date": "2014-03-20",
             "Sales": 40, "Profit": 4, "Market": "US", "Region": "West",
             "Category": "Furniture", "Segment": "Consumer"},
        ]
    )
