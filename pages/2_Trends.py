# pages/2_Trends.py
import io, re, time, csv
import requests
import pandas as pd
import streamlit as st
import altair as alt
from pandas.api.types import is_datetime64_any_dtype, is_datetime64tz_dtype


def show_bar_counts(df: pd.DataFrame, col: str, title: str, top: int = 15):
    if df.empty or col not in df.columns:
        st.caption(f"No data for {col}")
        return
    ser = df[col].astype(str)
    ser = ser[ser.str.strip().ne("")]  # drop blanks
    vc = ser.value_counts().head(top).reset_index()
    if vc.empty:
        st.caption(f"No data for {col}")
        return
    vc.columns = [col, "n"]
    chart = (
        alt.Chart(vc)
        .mark_bar()
        .encode(
            y=alt.Y(f"{col}:N", sort="-x", title=col),
            x=alt.X("n:Q", title="Count", scale=alt.Scale(zero=True, nice=True)),
            tooltip=[alt.Tooltip(f"{col}:N", title=col), alt.Tooltip("n:Q", title="Count")],
        )
        .properties(height=300, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

def show_weekly_counts(df: pd.DataFrame, date_col: str, color_col: str | None = None, title: str = "Weekly count"):
    if df.empty or date_col not in df.columns:
        st.caption("No dated rows to chart.")
        return
    d = df.dropna(subset=[date_col]).copy()
    if d.empty:
        st.caption("No dated rows to chart.")
        return
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.dropna(subset=[date_col])
    if d.empty:
        st.caption("No dated rows to chart.")
        return
    d["week"] = d[date_col].dt.to_period("W").apply(lambda r: r.start_time)
    group_cols = ["week"] + ([color_col] if color_col and color_col in d.columns else [])
    agg = d.groupby(group_cols).size().reset_index(name="n")
    if agg.empty:
        st.caption("No data after grouping.")
        return
    base = alt.Chart(agg).mark_line(point=True).encode(
        x=alt.X("week:T", title="Week"),
        y=alt.Y("n:Q", title="Count", scale=alt.Scale(zero=True, nice=True)),
        tooltip=group_cols + ["n"]
    ).properties(height=300, title=title)
    if color_col and color_col in agg.columns:
        base = base.encode(color=f"{color_col}:N")
    st.altair_chart(base, use_container_width=True)



st.set_page_config(page_title="Trends", layout="wide")
st.title("📈 Trends & Insights")

# Optional: quick cache reset while iterating
top = st.columns([1,6])
with top[0]:
    if st.button("↻ Clear data cache"):
        st.cache_data.clear()
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

# ---- Sources (can be bare Sheet IDs or full links) ----
DR_CSV  = st.secrets.get("dr_csv_url",  "https://docs.google.com/spreadsheets/d/1AMMfzbKreprRrhzJwMeQq9_2spdEvDLfGtEYnEMyF_8/edit?gid=0#gid=0")
BHT_CSV = st.secrets.get("bht_csv_url", "https://docs.google.com/spreadsheets/d/1SYlCYxERDcI-PaQggyTOPgw4Ll5JIHPhQhJcjnD5ih0/edit?gid=0#gid=0")

# ---------------- Robust CSV loader ----------------
_GSHEET_RE    = re.compile(r"https?://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/")
_GSHEET_ID_RE = re.compile(r"^[A-Za-z0-9-_]{30,}$")
_GID_RE       = re.compile(r"[?&#]gid=(\d+)")

def _normalize_csv_url(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if _GSHEET_ID_RE.match(s):  # bare ID
        return f"https://docs.google.com/spreadsheets/d/{s}/export?format=csv&gid=0"
    m = _GSHEET_RE.search(s)    # full Google Sheets URL
    if m:
        sheet_id = m.group(1)
        gid_m = _GID_RE.search(s)
        gid = gid_m.group(1) if gid_m else "0"
        if ("export?format=csv" in s) or ("output=csv" in s):
            return s
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    if s.lower().startswith(("http://", "https://")):  # regular CSV URL
        return s
    raise ValueError("Invalid CSV source. Paste a Google Sheet link/ID or a direct CSV URL.")

def _dedupe_cols(cols):
    seen, out = {}, []
    for c in cols:
        k = str(c).strip()
        if k in seen:
            seen[k] += 1
            k = f"{k}_{seen[str(c).strip()]}"
        else:
            seen[k] = 0
        out.append(k)
    return out

@st.cache_data(ttl=300, show_spinner=False)
def load_csv(source: str, *, retries: int = 2, timeout: int = 30) -> pd.DataFrame:
    url = _normalize_csv_url(source)
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            head = r.content[:400].decode("utf-8", errors="replace").lower()
            if "<html" in head:
                raise RuntimeError(
                    "Received HTML instead of CSV. If this is a Google Sheet, ensure sharing is correct and use an export URL or bare Sheet ID."
                )
            buf = io.BytesIO(r.content)
            attempts = [
                dict(engine="c",      encoding="utf-8",     sep=",", quotechar='"',  doublequote=True),
                dict(engine="c",      encoding="utf-8-sig", sep=",", quotechar='"',  doublequote=True),
                dict(engine="python", encoding="utf-8",     sep=",", quotechar='"',  doublequote=True, on_bad_lines="skip"),
                dict(engine="python", encoding="utf-8-sig", sep=",", quoting=csv.QUOTE_NONE, escapechar="\\", on_bad_lines="skip"),
                dict(engine="python", encoding="utf-8-sig", sep=";", quotechar='"',  doublequote=True, on_bad_lines="skip"),
                dict(engine="python", encoding="latin-1",   sep=",", quotechar='"',  doublequote=True, on_bad_lines="skip"),
                dict(engine="python", encoding="latin-1",   sep="\t", quotechar='"', doublequote=True, on_bad_lines="skip"),
            ]
            last_parse_err = None
            for opts in attempts:
                try:
                    buf.seek(0)
                    df = pd.read_csv(buf, **opts)
                    df.columns = _dedupe_cols(df.columns)
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

# ---------------- Datetime helpers ----------------
LOCAL_TZ = "America/Chicago"
DATE_CANDIDATES = ["DateTime", "Timestamp", "Submitted At", "date", "Date", "Created", "Created At"]

def _to_local_naive(s: pd.Series) -> pd.Series:
    """
    Convert a Series of timestamps to tz-naive *local* time (America/Chicago).
    - tz-aware → convert to local tz, then drop tz
    - tz-naive → localize to local tz, then drop tz
    Non-parsable values become NaT.
    """
    parsed = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
    if is_datetime64tz_dtype(parsed):
        parsed = parsed.dt.tz_convert(LOCAL_TZ)
    elif is_datetime64_any_dtype(parsed):
        # naive → localize to local tz
        parsed = parsed.dt.tz_localize(LOCAL_TZ, nonexistent="NaT", ambiguous="NaT")
    else:
        return pd.Series(pd.NaT, index=s.index)
    return parsed.dt.tz_localize(None)

def add_unified_datetime(df: pd.DataFrame) -> str | None:
    """
    Create a unified datetime column '__dt' by trying common date columns,
    normalizing everything to tz-naive local (America/Chicago).
    """
    if df.empty:
        return None

    frames = []
    for c in DATE_CANDIDATES:
        if c in df.columns:
            try:
                frames.append(_to_local_naive(df[c]).rename(c))
            except Exception:
                pass

    if frames:
        tmp = pd.concat(frames, axis=1)
        # Take the first non-NaT across candidates
        df["__dt"] = tmp.bfill(axis=1).iloc[:, 0]
        if df["__dt"].notna().any():
            return "__dt"

    # Fallback: scan any column that yields enough datetimes
    best = None
    for c in df.columns:
        if c.startswith("__"):
            continue
        try:
            s = _to_local_naive(df[c])
            if s.notna().sum() >= max(5, int(0.2 * len(df))):
                best = s if best is None else best.fillna(s)
        except Exception:
            continue

    if best is not None and best.notna().any():
        df["__dt"] = best
        return "__dt"

    df.drop(columns=["__dt"], errors="ignore")
    return None

def categorical_columns(df: pd.DataFrame, max_unique: int = 30) -> list[str]:
    cats = []
    for c in df.columns:
        if c.startswith("__"):
            continue
        if df[c].dtype == "object" or pd.api.types.is_categorical_dtype(df[c]):
            nunq = df[c].nunique(dropna=True)
            if 1 < nunq <= max_unique:
                cats.append(c)
    return cats

# ---------------- Load + prep ----------------
def safe_load(name: str, src: str) -> pd.DataFrame:
    if not src:
        return pd.DataFrame()
    try:
        df = load_csv(src)
        return df
    except Exception as e:
        st.error(f"Could not load {name} sheet.")
        st.code(str(e)[:1200], language="text")
        return pd.DataFrame()

dr  = safe_load("DR",  DR_CSV)
bht = safe_load("BHT", BHT_CSV)

if not dr.empty:  dr = dr.copy();  dr["__source"] = "DR"
if not bht.empty: bht = bht.copy(); bht["__source"] = "BHT"

combined = pd.concat([d for d in [dr, bht] if not d.empty], ignore_index=True) if (not dr.empty or not bht.empty) else pd.DataFrame()

if combined.empty:
    st.info("No data to chart yet.")
    st.stop()

# Build unified datetime for all 3 datasets (tz-normalized & tz-naive)
for d in (dr, bht, combined):
    if not d.empty:
        add_unified_datetime(d)

# ---------------- UI controls ----------------
dataset = st.radio(
    "Dataset", ["Combined (DR+BHT)", "DR only", "BHT only"],
    horizontal=True, key="tr-ds"
)
df_src = combined if dataset.startswith("Combined") else dr if dataset.startswith("DR") else bht

if df_src.empty:
    st.info("Selected dataset is empty.")
    st.stop()

dt_col = "__dt" if "__dt" in df_src.columns else None
if not dt_col or df_src[dt_col].notna().sum() == 0:
    st.warning("No recognizable date column found to build trends.")
else:
    c1, c2, c3, c4 = st.columns([1.1, 1.1, 1.2, 6])
    with c1:
        freq_label = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"], index=1, key="tr-freq")
    with c2:
        ma_enabled = st.checkbox("Moving Avg", value=True, key="tr-ma-on")
    with c3:
        ma_window = st.number_input("Window", min_value=2, max_value=28, value=7, step=1, key="tr-ma-win")

    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}
    freq = freq_map[freq_label]

    # Date range filter (NO re-parsing; __dt is already tz-naive local)
    min_d = df_src[dt_col].min()
    max_d = df_src[dt_col].max()
    r1, r2, _ = st.columns([1.2, 1.2, 5])
    with r1:
        start = st.date_input("Start", value=min_d.date() if pd.notna(min_d) else None, key="tr-start")
    with r2:
        end   = st.date_input("End",   value=max_d.date() if pd.notna(max_d) else None, key="tr-end")

    m = pd.Series(True, index=df_src.index)
    if start and end:
        dts = df_src[dt_col].dt.date
        m &= (dts >= start) & (dts <= end)
    dfx = df_src.loc[m].copy()

    # Group by time + source
    grp = (
        dfx.dropna(subset=[dt_col])
           .groupby([pd.Grouper(key=dt_col, freq=freq), "__source"])
           .size().reset_index(name="__count")
    )

    if grp.empty:
        st.info("No rows in the selected date range.")
    else:
        # Moving average per source
        if ma_enabled:
            grp = (grp.sort_values([dt_col, "__source"])
                      .groupby("__source", group_keys=False)
                      .apply(lambda g: g.assign(__ma=g["__count"].rolling(ma_window, min_periods=1).mean()))
                   )
        # Line chart colored by source
        base = alt.Chart(grp).encode(
            x=alt.X(f"{dt_col}:T", title=f"{freq_label}"),
            y=alt.Y("__count:Q", title="Submissions"),
            color=alt.Color("__source:N", title="Source"),
            tooltip=[alt.Tooltip(f"{dt_col}:T", title="Date"), "__source:N", "__count:Q"]
        )
        line = base.mark_line(point=True)
        layers = [line]
        if ma_enabled:
            ma = alt.Chart(grp).mark_line(strokeDash=[4,3]).encode(
                x=alt.X(f"{dt_col}:T"),
                y=alt.Y("__ma:Q", title="Moving Avg"),
                color="__source:N",
                tooltip=[alt.Tooltip(f"{dt_col}:T", title="Date"), "__source:N", "__ma:Q"]
            )
            layers.append(ma)
        st.subheader(f"{freq_label} submissions by source")
        st.altair_chart(alt.layer(*layers).properties(height=320), use_container_width=True)

# ---------------- Category views ----------------
st.markdown("---")
cat_candidates = [c for c in ["Grade","MajorProblemBehavior","MinorProblemBehavior","MainConcern","StudentStatus"] if c in df_src.columns]
auto_cats = [c for c in categorical_columns(df_src) if c not in cat_candidates]
cat_options = cat_candidates + auto_cats

if cat_options:
    c1, c2 = st.columns([2,1])
    with c1:
        cat = st.selectbox("View top categories", cat_options, key="tr-cat")
    with c2:
        topk = st.number_input("Top N", min_value=5, max_value=30, value=15, step=1, key="tr-topk")

    vc = (
        df_src[cat].astype(str)
        .value_counts()
        .head(int(topk))
        .rename_axis(cat).reset_index(name="__freq")
    )
    st.subheader(f"Top {int(topk)} for {cat}")
    bar = alt.Chart(vc).mark_bar().encode(
        x=alt.X("__freq:Q", title="Count"),
        y=alt.Y(f"{cat}:N", sort="-x", title=cat),
        tooltip=[f"{cat}:N", "__freq:Q"]
    ).properties(height=320)
    st.altair_chart(bar, use_container_width=True)

    if "__dt" in df_src.columns and df_src["__dt"].notna().any():
        freq_label2 = st.selectbox("Category trend frequency", ["Weekly","Monthly","Daily"], index=0, key="tr-cat-freq")
        freq2 = {"Daily":"D","Weekly":"W","Monthly":"MS"}[freq_label2]

        top_vals = df_src[cat].astype(str).value_counts().head(6).index.tolist()
        dft = df_src.copy()
        dft[cat] = dft[cat].astype(str).where(dft[cat].astype(str).isin(top_vals), other="Other")

        grp2 = (
            dft.dropna(subset=["__dt"])
               .groupby([pd.Grouper(key="__dt", freq=freq2), cat])
               .size().reset_index(name="__count")
        )
        st.subheader(f"{cat}: {freq_label2} stacked counts")
        area = alt.Chart(grp2).mark_area().encode(
            x=alt.X("__dt:T", title=f"{freq_label2}"),
            y=alt.Y("__count:Q", title="Submissions"),
            color=alt.Color(f"{cat}:N", title=cat),
            tooltip=[alt.Tooltip("__dt:T", title="Date"), f"{cat}:N", "__count:Q"]
        ).properties(height=340)
        st.altair_chart(area, use_container_width=True)
else:
    st.info("No suitable categorical columns found for category charts.")
