print("Starting Global Superstore validation...")

import pandas as pd

from utils.data_loader import load_superstore_data

df = load_superstore_data()

print("\nDATASET INFORMATION")
print("=" * 40)

print("Total Rows:", len(df))
print("Total Columns:", len(df.columns))

print("\nDate Range:")
print("Start:", df["Order_Date"].min())
print("End:", df["Order_Date"].max())

print("\nBUSINESS METRICS")
print("=" * 40)

revenue = round(float(df["Sales"].sum()), 2)
profit = round(float(df["Profit"].sum()), 2)
orders = int(df["Order_ID"].nunique())
margin = profit / revenue * 100

print("Total Revenue:", revenue)
print("Total Profit:", profit)
print("Unique Orders:", orders)
print("Profit Margin %:", round(margin, 2))

assert len(df) == 51290, len(df)
assert df["Order_Date"].min() == pd.Timestamp("2011-01-01")
assert df["Order_Date"].max() == pd.Timestamp("2014-12-31")
assert revenue == 12642905
assert profit == 1467457.29
assert orders == 25035
assert orders != len(df)
assert round(margin, 2) == 11.61

print("\nDATA LOADED SUCCESSFULLY!")