import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Root Cause Diagnostic Tool", layout="wide")

st.title("🚨 Metric Drop: Root-Cause Analysis Tool")
st.markdown("**Scenario:** Weekly checkout conversion rate suddenly dropped from **15% to 5%**. Investigate the breakdown below to find the root cause.")

# 1. Incident Data Generation
@st.cache_data
def load_incident_data():
    data = {
        "Device": ["Desktop", "Desktop", "Mobile", "Mobile", "Tablet", "Tablet"],
        "OS": ["Windows", "macOS", "iOS", "Android", "iOS", "Android"],
        "Traffic_Source": ["Google Search", "Direct", "Paid Ads", "Paid Ads", "Google Search", "Direct"],
        "Attempts": [2000, 1800, 4000, 3500, 600, 500],
        "Successes": [150, 160, 40, 75, 30, 28]  # Catastrophic drop on Mobile iOS: 40/4000 = 1%
    }
    df = pd.DataFrame(data)
    df["Conversion_Rate (%)"] = round((df["Successes"] / df["Attempts"]) * 100, 2)
    return df

df_incident = load_incident_data()

# 2. Executive Alert Box
st.error("⚠️ CRITICAL ALERT: Global E-Commerce Conversion Rate dropped significantly this week.")

# 3. High-Level Variable Isolations
st.subheader("Step 1: Isolate by System & Environment Variables")
col1, col2 = st.columns(2)

with col1:
    st.write("**Conversion Rate by Device Type**")
    device_df = df_incident.groupby("Device")[["Attempts", "Successes"]].sum().reset_index()
    device_df["Conversion_Rate (%)"] = (device_df["Successes"] / device_df["Attempts"]) * 100
    fig_device = px.bar(device_df, x="Device", y="Conversion_Rate (%)", color="Device", text_auto=".1f", template="plotly_white")
    st.plotly_chart(fig_device, use_container_width=True)

with col2:
    st.write("**Conversion Rate by Operating System (OS)**")
    os_df = df_incident.groupby("OS")[["Attempts", "Successes"]].sum().reset_index()
    os_df["Conversion_Rate (%)"] = (os_df["Successes"] / os_df["Attempts"]) * 100
    fig_os = px.bar(os_df, x="OS", y="Conversion_Rate (%)", color="OS", text_auto=".1f", template="plotly_white")
    st.plotly_chart(fig_os, use_container_width=True)

st.divider()

# 4. Deep Drill-Down Matrix
st.subheader("Step 2: Granular Performance Breakdown Matrix")
st.dataframe(df_incident.sort_values(by="Conversion_Rate (%)"), use_container_width=True)

# 5. Analytical Recommendation
st.subheader("🔎 Analytical Finding & Recommendation")
st.info(
    "**Root Cause Confirmed:** Mobile devices running **iOS** experienced a conversion drop down to **1.0%**, "
    "while Android and Desktop remain stable at normal baselines (~15%).\n\n"
    "**Action Item for Engineering:** Inspect the latest iOS build deployed this week for checkout UI failure."
)