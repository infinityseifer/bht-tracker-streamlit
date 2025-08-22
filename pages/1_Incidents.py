# pages/1_Incidents.py
import io, re, time, csv
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Incidents Table", layout="wide")
st.title("📋 Incidents Table")

# --- Optional form links (edit or set in secrets) ---
form_dr_url  = st.secrets.get("form_dr_url",  "https://script.google.com/macros/s/AKfycbxUBFzrOUlgYlwqeVqnTzT072rNFxfsKCJQBZZ7xb8IxRLATl8KyPcIgRlkEVviWawp/exec")
form_bht_url = st.secrets.get("form_bht_url", "https://script.google.com/macros/s/AKfycbwAq1kgh96AI_Ne1GvoWSHLQq07giFZ2XRCfseK1UDjYGYXtCDJy0oOUVQ2EE52mGdU/exec")

# --- Sheet sources (ID or full link). Prefer secrets; fall back to known links/IDs. ---
DR_SHEET  = st.secrets.get("dr_csv_url",  "https://docs.google.com/spreadsheets/d/1AMMfzbKreprRrhzJwMeQq9_2spdEvDLfGtEYnEMyF_8/edit?gid=0#gid=0")
BHT_SHEET = st.secrets.get("bht_csv_url", "https://docs.google.com/spreadsheets/d/1SYlCYxERDcI-PaQggyTOPgw4Ll5JIHPhQhJcjnD5ih0/edit?gid=0#gid=0")

# --- Make toolbar buttons bigger ---
st.markdown("""
<style>
div.stButton > button {padding: 0.9rem 1.2rem; font-size: 1.05rem; border-radius: 12px;}
a[data-testid="stLinkButton"] {padding: 0.8rem 1.1rem !important; border-radius: 10px !important;}
</style>
""", unsafe_allow_html=True)

# ---------------- Google Sheet CSV loader ----------------
_GSHEET_RE    = re.compile(r"https?://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/")
_GSHEET_ID_RE = re.compile(r"^[A-Za-z0-9-_]{30,}$")
_GID_RE       = re.compile(r"[?&#]gid=(\d+)")

def _normalize_csv_url(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if _GSHEET_ID_RE.match(s):  # bare sheet ID
        return f"https://docs.google.com/spreadsheets/d/{s}/export?format=csv&gid=0"
    m = _GSHEET_RE.search(s)    # full Google Sheets URL
    if m:
        sheet_id = m.group(1)
        gid_m = _GID_RE.search(s)
        gid = gid_m.group(1) if gid_m else "0"
        if ("export?format=csv" in s) or ("output=csv" in s):
            return s
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    if s.lower().startswith(("http://", "https://")):  # direct CSV
        return s
    raise ValueError("Invalid sheet source. Provide a Google Sheet link/ID or a CSV URL.")

def _dedupe_cols(cols):
    seen, out = {}, []
    for c in cols:
        name = str(c).strip()
        if name in seen:
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            out.append(name)
    return out

@st.cache_data(ttl=300, show_spinner=False)
def load_csv(source: str, *, retries: int = 2, timeout: int = 30) -> pd.DataFrame:
    url = _normalize_csv_url(source)
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            head = r.content[:300].decode("utf-8", errors="replace").lower()
            if "<html" in head:
                raise RuntimeError("Received HTML (not CSV). Check sharing/publish settings and use an export URL or sheet ID.")
            buf = io.BytesIO(r.content)

            attempts = [
                dict(engine="c",      encoding="utf-8",     sep=",", quotechar='"', doublequote=True),
                dict(engine="c",      encoding="utf-8-sig", sep=",", quotechar='"', doublequote=True),
                dict(engine="python", encoding="utf-8",     sep=",", quotechar='"', doublequote=True, on_bad_lines="skip"),
                dict(engine="python", encoding="utf-8-sig", sep=",", quoting=csv.QUOTE_NONE, escapechar="\\", on_bad_lines="skip"),
                dict(engine="python", encoding="latin-1",   sep=",", quotechar='"', doublequote=True, on_bad_lines="skip"),
            ]
            last_parse = None
            for opts in attempts:
                try:
                    buf.seek(0)
                    df = pd.read_csv(buf, **opts)
                    df.columns = _dedupe_cols(df.columns)
                    return df
                except Exception as pe:
                    last_parse = pe
            raise last_parse or RuntimeError("Unable to parse CSV.")
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
            else:
                break
    raise last_err

# ---------------- Date helpers (internal-only __dt for filtering/sorting) ----------------
def to_naive_local(s: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
    try:
        if getattr(parsed.dt, "tz", None) is not None:
            parsed = parsed.dt.tz_convert("America/Chicago").dt.tz_localize(None)
    except Exception:
        try:
            parsed = parsed.dt.tz_localize(None)
        except Exception:
            pass
    return parsed

def add_unified_dt(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if df.empty: return None
    for c in candidates:
        if c in df.columns:
            s = to_naive_local(df[c])
            if s.notna().any():
                df["__dt"] = s
                return "__dt"
    return None

# ---------------- Generic per-tab UI ----------------
def init_state(prefix: str, df: pd.DataFrame, default_sort: str | None):
    s = st.session_state
    s.setdefault(f"{prefix}_show_filters", True)
    s.setdefault(f"{prefix}_show_sort", False)
    s.setdefault(f"{prefix}_sort_by", default_sort)
    s.setdefault(f"{prefix}_sort_dir", "desc")

def render_filters(prefix: str, df_in: pd.DataFrame, schema: str) -> pd.DataFrame:
    # Build a schema-aware but tolerant filter set; table will remain the RAW sheet columns.
    with st.container(border=True):
        st.markdown("**Filters**")
        left, right = st.columns([3, 2])

        # Date range (if we have parsed __dt)
        date_rg = None
        if "__dt" in df_in:
            with right:
                date_rg = st.date_input("Date range", value=(), key=f"{prefix}-daterange")

        with left:
            if schema == "DR":
                # --- FIXED: unique() first, THEN sorted ---
                last  = df_in["StudentLast"].astype(str) if "StudentLast" in df_in else pd.Series("", index=df_in.index, dtype=str)
                first = df_in["StudentFirst"].astype(str) if "StudentFirst" in df_in else pd.Series("", index=df_in.index, dtype=str)
                full = (last.fillna("") + ", " + first.fillna("")).str.replace(r"[,\s]+$", "", regex=True).str.strip()
                student_opts = ["All"] + sorted(full[full.ne("")].dropna().unique().tolist())

                sel_stu   = st.selectbox("Student (Last, First)", student_opts, key=f"{prefix}-student")
                sel_grade = st.selectbox("Grade", ["All"] + (sorted(df_in.get("Grade", pd.Series(dtype=str)).dropna().unique().tolist()) if "Grade" in df_in else []), key=f"{prefix}-grade")
                sel_major = st.selectbox("Major Behavior", ["All"] + (sorted(df_in.get("MajorProblemBehavior", pd.Series(dtype=str)).dropna().unique().tolist()) if "MajorProblemBehavior" in df_in else []), key=f"{prefix}-maj")
                sel_minor = st.selectbox("Minor Behavior", ["All"] + (sorted(df_in.get("MinorProblemBehavior", pd.Series(dtype=str)).dropna().unique().tolist()) if "MinorProblemBehavior" in df_in else []), key=f"{prefix}-minr")
                text = st.text_input("Search Narrative / Next Steps / Intervention", key=f"{prefix}-search")
            else:  # BHT
                stu_col = "StudentID" if "StudentID" in df_in else ("StudentInitial" if "StudentInitial" in df_in else None)
                sel_student = st.selectbox("Student", ["All"] + (sorted(df_in[stu_col].dropna().unique().tolist()) if stu_col else []), key=f"{prefix}-student")
                sel_role    = st.selectbox("Role", ["All"] + (sorted(df_in.get("Role", pd.Series(dtype=str)).dropna().unique().tolist()) if "Role" in df_in else []), key=f"{prefix}-role")
                sel_status  = st.selectbox("Status", ["All"] + (sorted(df_in.get("StudentStatus", pd.Series(dtype=str)).dropna().unique().tolist()) if "StudentStatus" in df_in else []), key=f"{prefix}-status")
                sel_concern = st.selectbox("Main Concern", ["All"] + (sorted(df_in.get("MainConcern", pd.Series(dtype=str)).dropna().unique().tolist()) if "MainConcern" in df_in else []), key=f"{prefix}-concern")
                sel_subject = st.selectbox("Subject", ["All"] + (sorted(df_in.get("BehaviorSubject", pd.Series(dtype=str)).dropna().unique().tolist()) if "BehaviorSubject" in df_in else []), key=f"{prefix}-subject")

                # ParentNotified boolean-ish mapping (for filtering only)
                pn = None
                if "ParentNotified" in df_in:
                    s = df_in["ParentNotified"].astype(str).str.strip().str.lower()
                    yes_like = {"y","yes","true","1","✓","✔","x"}
                    no_like  = {"n","no","false","0","✗","✕",""}
                    pn_bool = s.map(lambda x: True if x in yes_like else (False if x in no_like else None))
                    df_in = df_in.copy()
                    df_in["__pn_bool"] = pn_bool
                    pn = st.selectbox("Parent notified", ["All", True, False], key=f"{prefix}-pn")

                text = st.text_input("Search Observation / Additional Concern / Strength", key=f"{prefix}-search")

        # Build mask on a working copy
        dfw = df_in.copy()
        mask = pd.Series(True, index=dfw.index)

        if "__dt" in dfw and date_rg and len(date_rg) == 2:
            start, end = date_rg
            if pd.notna(dfw["__dt"]).any():
                dts = dfw["__dt"].dt.date
                mask &= (dts >= start) & (dts <= end)

        if schema == "DR":
            if "StudentLast" in dfw or "StudentFirst" in dfw:
                full2 = (dfw.get("StudentLast", pd.Series(index=dfw.index, dtype=str)).fillna("") + ", " +
                         dfw.get("StudentFirst", pd.Series(index=dfw.index, dtype=str)).fillna("")).str.replace(r"[,\s]+$", "", regex=True).str.strip()
                if sel_stu != "All": mask &= full2.eq(sel_stu)
            if "Grade" in dfw and sel_grade != "All": mask &= dfw["Grade"].eq(sel_grade)
            if "MajorProblemBehavior" in dfw and sel_major != "All": mask &= dfw["MajorProblemBehavior"].eq(sel_major)
            if "MinorProblemBehavior" in dfw and sel_minor != "All": mask &= dfw["MinorProblemBehavior"].eq(sel_minor)
            if text:
                t = text.lower()
                fields = [c for c in ["Narrative","NextSteps","TeacherIntervention","ProactiveConcern"] if c in dfw]
                if fields:
                    m = pd.Series(False, index=dfw.index)
                    for c in fields: m |= dfw[c].astype(str).str.lower().str.contains(t, na=False)
                    mask &= m
        else:
            stu_col = "StudentID" if "StudentID" in dfw else ("StudentInitial" if "StudentInitial" in dfw else None)
            if stu_col and sel_student != "All": mask &= dfw[stu_col].eq(sel_student)
            if "Role" in dfw and sel_role != "All": mask &= dfw["Role"].eq(sel_role)
            if "StudentStatus" in dfw and sel_status != "All": mask &= dfw["StudentStatus"].eq(sel_status)
            if "MainConcern" in dfw and sel_concern != "All": mask &= dfw["MainConcern"].eq(sel_concern)
            if "BehaviorSubject" in dfw and sel_subject != "All": mask &= dfw["BehaviorSubject"].eq(sel_subject)
            if "__pn_bool" in dfw and pn in (True, False): mask &= dfw["__pn_bool"].eq(pn)
            if text:
                t = text.lower()
                fields = [c for c in ["Observation","AdditionalConcern","StudentStrength","BehaviorData","BehaviorTime"] if c in dfw]
                if fields:
                    m = pd.Series(False, index=dfw.index)
                    for c in fields: m |= dfw[c].astype(str).str.lower().str.contains(t, na=False)
                    mask &= m

        # Controls
        c1, c2, _ = st.columns([1, 1, 6])
        if c1.button("Clear filters", key=f"{prefix}-clear"):
            st.cache_data.clear()
            st.rerun()
        if c2.button("Refresh data", key=f"{prefix}-refresh"):
            load_csv.clear()
            st.rerun()

    return dfw.loc[mask].copy()

def render_sort_controls(prefix: str, df_in: pd.DataFrame) -> tuple[str | None, bool]:
    with st.container(border=True):
        st.markdown("**Sort**")
        cols = ["__dt"] + [c for c in df_in.columns if c != "__dt"]
        disp_cols = ["Date/Time (parsed)"] + [c for c in df_in.columns if c != "__dt"]
        default = st.session_state.get(f"{prefix}_sort_by") or ("__dt" if "__dt" in df_in else (cols[1] if len(cols)>1 else cols[0]))
        idx = cols.index(default) if default in cols else 0
        c1, c2, c3 = st.columns([2, 1, 1])
        sel = c1.selectbox("Column", disp_cols, index=idx, key=f"{prefix}-sort-col")
        actual_col = cols[disp_cols.index(sel)]
        dir_choice = c2.radio("Direction", ["Descending","Ascending"], horizontal=True, key=f"{prefix}-sort-dir",
                              index=(0 if st.session_state.get(f"{prefix}_sort_dir","desc")=="desc" else 1))
        if c3.button("Apply sort", type="primary", key=f"{prefix}-apply-sort"):
            st.session_state[f"{prefix}_sort_by"] = actual_col
            st.session_state[f"{prefix}_sort_dir"] = "asc" if dir_choice=="Ascending" else "desc"
            st.rerun()
        return (st.session_state.get(f"{prefix}_sort_by"),
                st.session_state.get(f"{prefix}_sort_dir","desc")=="asc")

def render_tab(title: str, prefix: str, sheet_src: str, form_url: str | None, schema: str):
    st.subheader(title)
    if form_url:
        st.link_button(f"📝 Open {title} Form", form_url, type="primary", use_container_width=True)

    # Load raw sheet
    try:
        df_raw = load_csv(sheet_src)
    except Exception as e:
        st.error(f"Failed to load sheet for {title}.\n\n{e}")
        return

    if df_raw.empty:
        st.info(f"No rows in {title} yet.")
        return

    # Build internal parsed datetime column (not shown in table)
    if schema == "DR":
        add_unified_dt(df_raw, ["DateTime","Timestamp"])
    else:
        add_unified_dt(df_raw, ["Timestamp"])

    # State toggles
    init_state(prefix, df_raw, "__dt" if "__dt" in df_raw else (df_raw.columns[0] if len(df_raw.columns) else None))
    tb1, tb2, _ = st.columns([1, 1, 5])
    with tb1:
        if st.button("🔎 Filters", use_container_width=True, key=f"{prefix}-toggle-filters"):
            st.session_state[f"{prefix}_show_filters"] = not st.session_state[f"{prefix}_show_filters"]
    with tb2:
        if st.button("↕️ Sort", use_container_width=True, key=f"{prefix}-toggle-sort"):
            st.session_state[f"{prefix}_show_sort"] = not st.session_state[f"{prefix}_show_sort"]

    # Apply filters
    fdf = render_filters(prefix, df_raw, schema) if st.session_state[f"{prefix}_show_filters"] else df_raw.copy()

    # Sort controls
    if st.session_state[f"{prefix}_show_sort"]:
        sort_col, asc = render_sort_controls(prefix, fdf)
    else:
        sort_col, asc = (st.session_state.get(f"{prefix}_sort_by"), st.session_state.get(f"{prefix}_sort_dir","desc")=="asc")

    # Sort (do not show __dt in table)
    df_display = fdf.copy()
    if sort_col and sort_col in df_display.columns:
        try:
            df_display = df_display.sort_values(sort_col, ascending=asc, kind="mergesort")
        except Exception:
            pass

    # KPI: incident count
    k1, k2 = st.columns([1,5])
    k1.metric("Incidents", f"{len(df_display):,}")

    st.divider()

    # Clean up helper columns before displaying
    show_df = df_display.drop(columns=["__dt","__pn_bool"], errors="ignore")

    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ Download filtered CSV",
        data=show_df.to_csv(index=False),
        file_name=f"{prefix}_incidents_filtered.csv",
        mime="text/csv",
        key=f"{prefix}-dl",
        use_container_width=True
    )

# ---------- Tabs ----------
tab_dr, tab_bht = st.tabs(["🗂 DR", "🗂 BHT"])

with tab_dr:
    if form_dr_url:
        st.caption("DR form opens in a new tab.")
    render_tab(
        title="DR Records",
        prefix="dr",
        sheet_src=DR_SHEET,
        form_url=form_dr_url,
        schema="DR"
    )

with tab_bht:
    if form_bht_url:
        st.caption("BHT form opens in a new tab.")
    render_tab(
        title="BHT Records",
        prefix="bht",
        sheet_src=BHT_SHEET,
        form_url=form_bht_url,
        schema="BHT"
    )
