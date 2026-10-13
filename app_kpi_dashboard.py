import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration (Wide layout matches BI tools)
st.set_page_config(page_title="Executive KPI Dashboard", layout="wide")

st.title("📊 Executive KPI Dashboard")
st.markdown("Use the sidebar filters to dynamically slice operational performance metrics.")

# 2. Dataset Generation (Clean synthetic enterprise data)
@st.cache_data
def load_data():
    dates = pd.date_range(start="2026-01-01", periods=12, freq="ME")
    regions = ["North", "South", "West", "East"]
    categories = ["Technology", "Furniture", "Office Supplies"]
    
    rows = []
    for d in dates:
        for r in regions:
            for c in categories:
                # Deterministic synthetic values for realism
                sales = 1200 + (len(r) * 150) + (len(c) * 80)
                profit = sales * 0.22
                orders = int(sales / 55)
                rows.append({
                    "Order_Date": d,
                    "Region": r,
                    "Category": c,
                    "Sales": sales,
                    "Profit": profit,
                    "Orders": orders
                })
    return pd.DataFrame(rows)

df = load_data()

# 3. Sidebar Interactive Filters
st.sidebar.header("🎯 Dashboard Filters")

all_regions = sorted(df["Region"].unique().tolist())
selected_regions = st.sidebar.multiselect(
    "Select Regions:",
    options=all_regions,
    default=all_regions
)

all_categories = sorted(df["Category"].unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Select Categories:",
    options=all_categories,
    default=all_categories
)

# Apply filters
filtered_df = df[
    (df["Region"].isin(selected_regions)) & 
    (df["Category"].isin(selected_categories))
]

# 4. Top-Line KPI Cards
st.subheader("📈 High-Level Performance")

total_sales = filtered_df["Sales"].sum() if not filtered_df.empty else 0
total_profit = filtered_df["Profit"].sum() if not filtered_df.empty else 0
total_orders = filtered_df["Orders"].sum() if not filtered_df.empty else 0
profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue", f"${total_sales:,.2f}")
col2.metric("Total Profit", f"${total_profit:,.2f}")
col3.metric("Profit Margin", f"{profit_margin:.1f}%")
col4.metric("Total Orders", f"{total_orders:,}")

st.divider()

# 5. Interactive Visualization Grid
if filtered_df.empty:
    st.warning("⚠️ No data available for the selected filters. Please select at least one region and category.")
else:
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Monthly Sales Trend")
        trend_df = filtered_df.groupby("Order_Date")["Sales"].sum().reset_index()
        fig_trend = px.line(
            trend_df,
            x="Order_Date",
            y="Sales",
            markers=True,
            labels={"Order_Date": "Month", "Sales": "Revenue ($)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with chart_col2:
        st.subheader("Profit Breakdown by Category")
        cat_df = filtered_df.groupby("Category")["Profit"].sum().reset_index()
        fig_bar = px.bar(
            cat_df,
            x="Category",
            y="Profit",
            color="Category",
            text_auto=".2s",
            labels={"Profit": "Total Profit ($)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_bar, use_container_width=True)