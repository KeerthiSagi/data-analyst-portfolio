print("Starting Global Superstore validation...")

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

print("Total Revenue:", round(df["Sales"].sum(), 2))
print("Total Profit:", round(df["Profit"].sum(), 2))
print("Unique Orders:", df["Order_ID"].nunique())

print("\nDATA LOADED SUCCESSFULLY!")