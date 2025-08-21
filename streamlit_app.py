# streamlit_app.py
import re, io, csv, time
import requests
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="BHT Tracker Home", layout="wide")

# --- BIG buttons ---
st.markdown("""
<style>
div.stButton > button {padding: 1.1rem 1.4rem; font-size: 1.1rem; border-radius: 12px;}
a[data-testid="stLinkButton"] {padding: 1rem 1.25rem !important; font-size: 1.1rem; border-radius: 12px !important; display:block; text-align:center;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<script>
window.addEventListener('load', () => {
  if (!document.querySelector('base')) {
    const base = document.createElement('base');
    base.setAttribute('href','/');
    document.head.appendChild(base);
  }
});
</script>
""", unsafe_allow_html=True)


st.title("🏫 BHT Tracker")

# === 1) Links to Google Apps Script forms ===
form_dr  = st.secrets.get("form_dr_url",  "https://script.google.com/macros/s/AKfycbxUBFzrOUlgYlwqeVqnTzT072rNFxfsKCJQBZZ7xb8IxRLATl8KyPcIgRlkEVviWawp/exec")
form_bht = st.secrets.get("form_bht_url", "https://script.google.com/macros/s/AKfycbwRNLUX3Jf4AgVvcd1MHD4v9ibrd8CdAuInfh5qq-3yCoRZadP0IyGCJv8_AaVxUgNA/exec")

col1, col2 = st.columns(2)
with col1:
    st.link_button("📝 Open DR Form",  form_dr,  type="primary", use_container_width=True)
with col2:
    st.link_button("📝 Open BHT Form", form_bht, type="primary", use_container_width=True)

st.divider()
st.subheader("Navigate")

# === 2) Multipage navigation ===
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📋 Incidents Table", use_container_width=True):
        st.switch_page("pages/1_Incidents.py")
with c2:
    if st.button("📈 Trends & Insights", use_container_width=True):
        st.switch_page("pages/2_Trends.py")
with c3:
    if st.button("⚙️ Admin / EDA", use_container_width=True):
        st.switch_page("pages/3_Admin.py")

# -------------------------
# CSV helpers (for other pages)
# -------------------------

GSHEET_RE    = re.compile(r"https?://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/")
GSHEET_ID_RE = re.compile(r"^[A-Za-z0-9-_]{30,}$")  # rough length guard for bare IDs
GID_RE       = re.compile(r"[?&#]gid=(\d+)")

def normalize_csv_url(url_or_id: str) -> str:
    """
    Accepts:
      - Bare Google Sheet ID
      - Google Sheets 'edit' URL
      - Already-exported CSV URLs (pub?output=csv or export?format=csv)
      - Any other http(s) CSV URL
    Returns a URL that should yield a CSV.
    """
    s = (url_or_id or "").strip()
    if GSHEET_ID_RE.match(s):
        return f"https://docs.google.com/spreadsheets/d/{s}/export?format=csv&gid=0"

    m = GSHEET_RE.search(s)
    if m:
        sheet_id = m.group(1)
        gid_match = GID_RE.search(s)
        gid = gid_match.group(1) if gid_match else "0"
        if ("export?format=csv" in s) or ("output=csv" in s):
            return s
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    if s.lower().startswith(("http://", "https://")):
        return s

    raise ValueError("CSV URL appears invalid. If this is a Google Sheet, pass the link or bare Sheet ID.")

@st.cache_data(ttl=300, show_spinner=False)
def load_csv_from_url_robust(url_or_id: str, *, retries: int = 2, timeout: int = 30) -> pd.DataFrame:
    url = normalize_csv_url(url_or_id)
    last_err = None

    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()

            head = r.content[:400].decode("utf-8", errors="replace").lower()
            if "<html" in head:
                raise RuntimeError(
                    "Received HTML instead of CSV. If this is a Google Sheet, ensure share/public settings and use an export CSV URL."
                )

            raw = r.content
            buf = io.BytesIO(raw)

            parse_attempts = [
                dict(encoding="utf-8", engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="error", low_memory=False),
                dict(encoding="utf-8", engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="skip",  low_memory=False),
                dict(encoding="utf-8-sig", engine="python", sep=",", quoting=csv.QUOTE_NONE, escapechar="\\", on_bad_lines="skip", low_memory=False),
                dict(encoding="latin-1", engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="skip", low_memory=False),
            ]
            last_parse_err = None
            for opts in parse_attempts:
                try:
                    buf.seek(0)
                    df = pd.read_csv(buf, **opts)
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
                except Exception as pe:
                    last_parse_err = pe
            raise last_parse_err or RuntimeError("Unable to parse CSV with any strategy.")
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
            else:
                break

    raise last_err

# -------------------------
# Altair helpers (stop version warning + guard empties)
# -------------------------

def st_vl(chart: alt.Chart):
    """
    Render an Altair chart via st.vega_lite_chart after removing $schema.
    This silences the Vega-Lite version mismatch warning.
    """
    spec = chart.to_dict()
    spec.pop("$schema", None)

    # Inline named datasets if present (rare, but avoids extra warnings)
    if "data" in spec and isinstance(spec["data"], dict) and "name" in spec["data"] and "datasets" in spec:
        name = spec["data"]["name"]
        spec["data"] = {"values": spec["datasets"].get(name, [])}
        spec.pop("datasets", None)

    st.vega_lite_chart(spec, use_container_width=True)

def safe_altair_chart(df: pd.DataFrame, build_chart_fn, empty_msg="No data to chart."):
    if df is None or df.empty:
        st.caption(empty_msg)
        return
    chart = build_chart_fn(df)
    if chart is None:
        st.caption(empty_msg)
        return
    st_vl(chart)  # use wrapper instead of st.altair_chart

# --- Example builders you can copy into pages/* as needed ---
def chart_counts(df: pd.DataFrame):
    col = "some_col"
    if col not in df.columns:
        return None
    vc = (df[col].astype("string").str.strip()
          .replace("", pd.NA).dropna()
          .value_counts().reset_index())
    if vc.empty:
        return None
    vc.columns = ["value", "n"]
    return alt.Chart(vc).mark_bar().encode(
        y=alt.Y("value:N", sort="-x", title="Value"),
        x=alt.X("n:Q", title="Count", scale=alt.Scale(zero=True)),
        tooltip=["value:N", "n:Q"]
    ).properties(height=300, title="Counts")

def chart_weekly(df: pd.DataFrame):
    col = "timestamp"  # change to your real timestamp col
    if col not in df.columns:
        return None
    s = pd.to_datetime(df[col], errors="coerce").dropna()
    if s.empty:
        return None
    weekly = (s.dt.to_period("W")
                .apply(lambda r: r.start_time)
                .value_counts()
                .rename_axis("week")
                .reset_index(name="n")
                .sort_values("week"))
    if weekly.empty:
        return None
    return alt.Chart(weekly).mark_line(point=True).encode(
        x=alt.X("week:T", title="Week"),
        y=alt.Y("n:Q", title="Count", scale=alt.Scale(zero=True)),
        tooltip=["week:T", "n:Q"]
    ).properties(height=300, title="Weekly submissions")

# (No charts rendered on the home page; helpers are imported/used by pages/*)
def render_chart(chart, df, prefix="chart"):
    key = f"{prefix}-{hash(tuple(df.columns))}-{df.shape}"
    st.altair_chart(chart, use_container_width=True, key=key)

try:
    alt.renderers.set_embed_options(vegaLiteVersion="5.14.0")  # match your console warning
except Exception:
    pass
