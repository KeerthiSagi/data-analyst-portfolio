"""A small two-period example with hand-calculated answers.

Previous period (Jan 2014)
  O-1 / C-1  US Central  Furniture   Consumer    sales 100  profit 20
  O-1 / C-1  US Central  Technology  Consumer    sales 100  profit 10   (same order)
  O-2 / C-2  EU Central  Furniture   Corporate   sales 200  profit 20
  -> revenue 400, profit 50, 2 orders, AOV 200, margin 12.5%

Current period (Feb 2014)
  O-3 / C-1  US Central  Furniture   Consumer    sales 150  profit 15
  O-3 / C-1  US Central  Technology  Consumer    sales  50  profit -10  (same order)
  O-4 / C-3  US Central  Technology  Consumer    sales 100  profit 30
  O-2 / C-4  EU Central  Office Sup. Home Office sales 200  profit 15   (reused Order ID)
  -> revenue 500, profit 50, 3 orders, AOV 166.67, margin 10.0%

Hand-calculated results
  Revenue by category:  Furniture -150, Technology +50, Office Supplies +200 (sum +100)
  Profit by category:   Furniture -25,  Technology +10, Office Supplies +15  (sum 0)
  Allocated orders by category:
      previous Furniture 1.5, Technology 0.5          (sum 2)
      current  Furniture 0.5, Technology 1.5, OS 1.0  (sum 3)
  Margin by category (pp): contribution / mix / rate
      Furniture       -7.00 / -5.25     / -1.75
      Technology      +1.50 / +0.583333 / +0.916667
      Office Supplies +3.00 / +3.00     /  0.00
      total           -2.50 / -1.666667 / -0.833333
  Revenue drivers: volume +183.333333, AOV -83.333333 (sum +100)
"""

from cause.data import prepare_dataset
from tests.conftest import make_raw

US = {"Market": "US", "Region": "Central"}
EU = {"Market": "EU", "Region": "Central"}

PREVIOUS_ROWS = [
    {"Order.ID": "O-1", "Customer.ID": "C-1", "Order.Date": "2014-01-05", **US,
     "Category": "Furniture", "Segment": "Consumer", "Sales": 100, "Profit": 20},
    {"Order.ID": "O-1", "Customer.ID": "C-1", "Order.Date": "2014-01-05", **US,
     "Category": "Technology", "Segment": "Consumer", "Sales": 100, "Profit": 10},
    {"Order.ID": "O-2", "Customer.ID": "C-2", "Order.Date": "2014-01-10", **EU,
     "Category": "Furniture", "Segment": "Corporate", "Sales": 200, "Profit": 20},
]
CURRENT_ROWS = [
    {"Order.ID": "O-3", "Customer.ID": "C-1", "Order.Date": "2014-02-02", **US,
     "Category": "Furniture", "Segment": "Consumer", "Sales": 150, "Profit": 15},
    {"Order.ID": "O-3", "Customer.ID": "C-1", "Order.Date": "2014-02-02", **US,
     "Category": "Technology", "Segment": "Consumer", "Sales": 50, "Profit": -10},
    {"Order.ID": "O-4", "Customer.ID": "C-3", "Order.Date": "2014-02-08", **US,
     "Category": "Technology", "Segment": "Consumer", "Sales": 100, "Profit": 30},
    {"Order.ID": "O-2", "Customer.ID": "C-4", "Order.Date": "2014-02-09", **EU,
     "Category": "Office Supplies", "Segment": "Home Office", "Sales": 200, "Profit": 15},
]


def load_example():
    """(full prepared frame, current rows, previous rows)."""
    df = prepare_dataset(make_raw(PREVIOUS_ROWS + CURRENT_ROWS)).data
    current = df[df["order_date"] >= "2014-02-01"]
    previous = df[df["order_date"] < "2014-02-01"]
    return df, current, previous
