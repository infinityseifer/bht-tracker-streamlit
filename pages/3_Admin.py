# pages/3_Admin.py
import io, requests, pandas as pd, streamlit as st
from io import StringIO

st.set_page_config(page_title="Admin / EDA", layout="wide")
st.title("⚙️ Admin / Quick EDA")

st.subheader("Upload CSV")
file = st.file_uploader("Drop a CSV", type=["csv"])
if file:
    df = pd.read_csv(file)
    st.caption(f"{len(df):,} rows, {df.shape[1]} columns")
    c1,c2,c3 = st.columns(3)
    c1.metric("Rows", f"{len(df):,}")
    c2.metric("Columns", f"{df.shape[1]:,}")
    c3.metric("Missing cells", f"{df.isna().sum().sum():,}")

    st.subheader("Schema")
    st.dataframe(pd.DataFrame({"column": df.columns,
                               "dtype": [str(x) for x in df.dtypes],
                               "missing": df.isna().sum().values}),
                 use_container_width=True)

    # simple numeric peek
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        st.subheader("Numeric summary")
        st.dataframe(df[num_cols].describe().T)

    # download cleaned
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="eda_export.csv", mime="text/csv")
else:
    st.info("Upload a CSV to analyze.")

st.divider()
st.subheader("Embedded submissions (optional)")
st.caption("Publish your Sheets to the web (CSV or HTML) and paste the embed links below.")
dr_embed  = st.text_input("DR embed URL (optional)",  value="")
bht_embed = st.text_input("BHT embed URL (optional)", value="")
h = st.slider("Embed height (px)", 400, 1200, 720)
if dr_embed:
    st.markdown("**DR Submissions**")
    st.components.v1.iframe(dr_embed, height=h, scrolling=True)
if bht_embed:
    st.markdown("**BHT Submissions**")
    st.components.v1.iframe(bht_embed, height=h, scrolling=True)
