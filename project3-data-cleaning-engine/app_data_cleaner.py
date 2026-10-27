import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Automated Data Cleaner", layout="wide")

st.title("🧽 Automated Data Cleaning & Profiling Engine")
st.markdown("Upload any messy CSV dataset to analyze data health anomalies and process clean variations instantly.")

# 1. File Upload
uploaded_file = st.file_uploader("Upload Your Dirty CSV File Below", type=["csv"])

if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    st.subheader("📋 Initial Data Profile & Diagnostics")
    total_rows = len(df_raw)
    total_cols = len(df_raw.columns)
    missing_cells = df_raw.isnull().sum().sum()
    duplicate_rows = df_raw.duplicated().sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Rows", f"{total_rows}")
    col2.metric("Total Columns", f"{total_cols}")
    col3.metric("Missing Value Cells", f"{missing_cells}", delta="- Action Required" if missing_cells > 0 else "Clean")
    col4.metric("Duplicate Rows Found", f"{duplicate_rows}", delta="- Action Required" if duplicate_rows > 0 else "Clean")

    st.write("**Raw Data Preview (First 5 Rows):**")
    st.dataframe(df_raw.head(), use_container_width=True)

    st.divider()

    # 2. Cleaning Controls
    st.subheader("⚙️ Automated Cleaning Controls")
    clean_duplicates = st.checkbox("Remove Exact Duplicate Rows", value=True)
    clean_missing = st.selectbox(
        "Missing Values Treatment Strategy:",
        ["Keep as is", "Drop rows with missing values", "Fill numerical columns with mean value"]
    )

    df_clean = df_raw.copy()

    if clean_duplicates:
        df_clean = df_clean.drop_duplicates()
        
    if clean_missing == "Drop rows with missing values":
        df_clean = df_clean.dropna()
    elif clean_missing == "Fill numerical columns with mean value":
        num_cols = df_clean.select_dtypes(include=['number']).columns
        for col in num_cols:
            df_clean[col] = df_clean[col].fillna(df_clean[col].mean())

    st.subheader("✨ Cleaned Output Preview")
    st.dataframe(df_clean.head(), use_container_width=True)

    # 3. Export Cleaned CSV
    buffer = io.StringIO()
    df_clean.to_csv(buffer, index=False)
    csv_bytes = buffer.getvalue()

    st.download_button(
        label="📥 Download Perfectly Cleaned CSV File",
        data=csv_bytes,
        file_name="cleaned_dataset.csv",
        mime="text/csv"
    )
else:
    st.info("💡 Upload a CSV file above to initiate data cleaning algorithms.")