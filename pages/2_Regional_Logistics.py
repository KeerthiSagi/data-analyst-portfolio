import streamlit as st
import pandas as pd
import plotly.express as px

from utils.data_loader import load_superstore_data

st.set_page_config(page_title="Segment & Margin Health", page_icon="🔬", layout="wide")

# Persistent Midnight Navy / Slate Blue Theme
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #f8fafc;
        }
        [data-testid="stSidebar"] {
            background-color: #0b0f19;
            border-right: 1px solid #334155;
        }
        div[data-testid="stMetric"] {
            background-color: #1e293b;
            border: 1px solid #334155;
            padding: 16px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        div[data-testid="stMetricLabel"] { color: #94a3b8; font-size: 0.9rem; }
        div[data-testid="stMetricValue"] { color: #38bdf8; font-weight: 700; font-size: 1.7rem; }
        h1, h2, h3 { color: #f1f5f9 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🔬 Segment & Margin Health")
st.caption("Page 2 of 3 | Customer Segments, Discounting & Profit Erosion")

df = load_superstore_data()

st.sidebar.header("🎯 Segment Filter")
all_segments = sorted(df["Segment"].unique().tolist())
selected_seg = st.sidebar.multiselect("Segments", options=all_segments, default=all_segments)

filtered = df[df["Segment"].isin(selected_seg)]

if filtered.empty:
    st.warning("⚠️ No data available for the selected customer segment. Please select at least one segment from the sidebar.")
else:
    avg_disc = filtered["Discount"].mean() * 100
    avg_val = filtered["Sales"].mean()
    loss_orders = (filtered["Profit"] < 0).sum()
    loss_pct = (loss_orders / len(filtered) * 100) if len(filtered) > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Average Discount Applied", f"{avg_disc:.1f}%")
    c2.metric("Average Order Value (AOV)", f"${avg_val:,.2f}")
    c3.metric("Negative-Margin Orders", f"{loss_orders} ({loss_pct:.1f}%)")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Discount vs. Profit Margin Impact")
        fig_scatter = px.scatter(
            filtered, x="Discount", y="Profit", color="Category",
            size="Quantity", hover_data=["Sub_Category"],
            template="plotly_dark",
            color_discrete_sequence=["#38bdf8", "#60a5fa", "#f59e0b"]
        )
        fig_scatter.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        st.subheader("Net Profit by Sub-Category")
        subcat = filtered.groupby("Sub_Category")["Profit"].sum().sort_values().reset_index()
        fig_sub = px.bar(
            subcat, x="Profit", y="Sub_Category", orientation="h",
            template="plotly_dark", color="Profit", color_continuous_scale="Blues"
        )
        fig_sub.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_sub, use_container_width=True)