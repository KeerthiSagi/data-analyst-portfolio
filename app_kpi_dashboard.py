import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 1. Page Configuration
st.set_page_config(
    page_title="Executive Enterprise KPI Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Executive Enterprise Performance Dashboard")
st.markdown(
    "Interactive business intelligence portal tracking financial performance, "
    "customer segments, and margin health across global operations."
)

# 2. Comprehensive Enterprise Dataset Generator
@st.cache_data
def generate_enterprise_data():
    np.random.seed(42)
    n_rows = 1200
    
    date_range = pd.date_range(start="2025-01-01", end="2026-03-31", freq="D")
    dates = np.random.choice(date_range, size=n_rows)
    
    regions = ["North America", "Europe", "Asia-Pacific", "Latin America"]
    categories = {
        "Technology": ["Phones", "Laptops", "Accessories", "Printers"],
        "Furniture": ["Chairs", "Bookcases", "Tables", "Furnishings"],
        "Office Supplies": ["Storage", "Art", "Appliances", "Binders"]
    }
    segments = ["Consumer", "Corporate", "Home Office"]
    ship_modes = ["Standard Class", "Second Class", "First Class", "Same Day"]

    records = []
    for i in range(n_rows):
        region = np.random.choice(regions)
        cat = np.random.choice(list(categories.keys()))
        sub_cat = np.random.choice(categories[cat])
        segment = np.random.choice(segments)
        ship_mode = np.random.choice(ship_modes)
        
        # Realistic business financial mechanics
        base_price = np.random.uniform(20, 800)
        quantity = np.random.randint(1, 9)
        discount = np.random.choice([0.0, 0.1, 0.2, 0.3, 0.5], p=[0.5, 0.2, 0.15, 0.1, 0.05])
        
        sales = round(base_price * quantity * (1 - discount), 2)
        # Margin erodes aggressively when high discounts are applied
        profit_rate = np.random.uniform(0.15, 0.35) - (discount * 0.6)
        profit = round(sales * profit_rate, 2)
        
        records.append({
            "Order_Date": dates[i],
            "Region": region,
            "Category": cat,
            "Sub_Category": sub_cat,
            "Segment": segment,
            "Ship_Mode": ship_mode,
            "Sales": sales,
            "Profit": profit,
            "Discount": discount,
            "Quantity": quantity
        })
        
    df = pd.DataFrame(records)
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    df["Year_Month"] = df["Order_Date"].dt.to_period("M").dt.to_timestamp()
    return df

df = generate_enterprise_data()

# 3. Dynamic Filter Panel
st.sidebar.header("🎯 Filter Controls")

# Date range selection
min_date = df["Order_Date"].min().date()
max_date = df["Order_Date"].max().date()
selected_date_range = st.sidebar.date_input(
    "Select Order Date Window:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Multi-select filters
all_regions = sorted(df["Region"].unique().tolist())
selected_regions = st.sidebar.multiselect("Regions:", options=all_regions, default=all_regions)

all_segments = sorted(df["Segment"].unique().tolist())
selected_segments = st.sidebar.multiselect("Customer Segments:", options=all_segments, default=all_segments)

all_categories = sorted(df["Category"].unique().tolist())
selected_categories = st.sidebar.multiselect("Categories:", options=all_categories, default=all_categories)

# Apply filters safely
if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
    start_d, end_d = selected_date_range
else:
    start_d, end_d = min_date, max_date

filtered_df = df[
    (df["Order_Date"].dt.date >= start_d) &
    (df["Order_Date"].dt.date <= end_d) &
    (df["Region"].isin(selected_regions)) &
    (df["Segment"].isin(selected_segments)) &
    (df["Category"].isin(selected_categories))
]

# 4. Top-Line KPI Scorecards with Period-over-Period Deltas
st.subheader("📈 High-Level Executive Scorecards")

if filtered_df.empty:
    st.warning("⚠️ No data matches the selected filters. Please adjust the filters in the sidebar.")
else:
    total_sales = filtered_df["Sales"].sum()
    total_profit = filtered_df["Profit"].sum()
    total_orders = len(filtered_df)
    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0

    # Calculate MoM deltas using the latest two months in filtered data
    monthly_trend = filtered_df.groupby("Year_Month")[["Sales", "Profit"]].sum().reset_index()
    if len(monthly_trend) >= 2:
        prev_month_sales = monthly_trend.iloc[-2]["Sales"]
        curr_month_sales = monthly_trend.iloc[-1]["Sales"]
        sales_delta = ((curr_month_sales - prev_month_sales) / prev_month_sales) * 100

        prev_month_profit = monthly_trend.iloc[-2]["Profit"]
        curr_month_profit = monthly_trend.iloc[-1]["Profit"]
        profit_delta = ((curr_month_profit - prev_month_profit) / prev_month_profit) * 100
        sales_delta_str = f"{sales_delta:+.1f}% MoM"
        profit_delta_str = f"{profit_delta:+.1f}% MoM"
    else:
        sales_delta_str = "N/A"
        profit_delta_str = "N/A"

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Revenue", f"${total_sales:,.2f}", delta=sales_delta_str)
    kpi2.metric("Total Profit", f"${total_profit:,.2f}", delta=profit_delta_str)
    kpi3.metric("Profit Margin", f"{profit_margin:.1f}%")
    kpi4.metric("Average Order Value (AOV)", f"${avg_order_value:,.2f}")

    st.divider()

    # 5. Core Analytical Visualizations
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Monthly Revenue Trajectory")
        trend_agg = filtered_df.groupby("Year_Month")["Sales"].sum().reset_index()
        fig_trend = px.line(
            trend_agg,
            x="Year_Month",
            y="Sales",
            markers=True,
            labels={"Year_Month": "Month", "Sales": "Revenue ($)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with row1_col2:
        st.subheader("Profitability by Customer Segment")
        segment_agg = filtered_df.groupby("Segment")[["Sales", "Profit"]].sum().reset_index()
        fig_seg = px.bar(
            segment_agg,
            x="Segment",
            y=["Sales", "Profit"],
            barmode="group",
            labels={"value": "Total ($)", "variable": "Financial Metric"},
            template="plotly_white"
        )
        st.plotly_chart(fig_seg, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("Discount vs. Profit Erosion Diagnostic")
        fig_scatter = px.scatter(
            filtered_df,
            x="Discount",
            y="Profit",
            color="Category",
            size="Quantity",
            hover_data=["Sub_Category", "Region"],
            labels={"Discount": "Discount Rate (0.0 = 0%, 0.5 = 50%)", "Profit": "Net Profit ($)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with row2_col2:
        st.subheader("Sub-Category Performance Breakdown")
        subcat_agg = filtered_df.groupby("Sub_Category")["Sales"].sum().sort_values(ascending=True).reset_index()
        fig_subcat = px.bar(
            subcat_agg,
            x="Sales",
            y="Sub_Category",
            orientation="h",
            labels={"Sales": "Total Revenue ($)", "Sub_Category": "Sub-Category"},
            template="plotly_white"
        )
        st.plotly_chart(fig_subcat, use_container_width=True)