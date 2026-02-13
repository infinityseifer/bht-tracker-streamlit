# pages/3_Admin.py
import re, io, csv, time
import numpy as np
import pandas as pd
import requests
import streamlit as st
import urllib.parse as _url
import altair as alt

# ---------------- UI polish ----------------
st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
[data-testid="stHeader"] { background: none !important; }
div[data-testid="stMetric"]{ border: none !important; background: transparent !important; box-shadow: none !important; padding: 0 !important; }
div[role="radiogroup"] > label{
  border: 1px solid rgba(49,51,63,.10) !important; background: transparent !important; box-shadow: none !important;
  border-radius: 999px !important; padding: .25rem .75rem !important; margin-right: .35rem !important; margin-bottom: .35rem !important;
}
[data-testid="stDataFrame"] div[role="table"]{ border: none !important; box-shadow: none !important; border-radius: 0 !important; }
main, section.main, .block-container { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Admin / EDA")

# --------- Altair theme ----------
def _bht_theme():
    return {
        "config": {
            "view": {"strokeWidth": 0},
            "axis": {"grid": True, "tickSize": 3, "labelFontSize": 12, "titleFontSize": 12},
            "legend": {"labelFontSize": 12, "titleFontSize": 12},
            "title": {"fontSize": 16, "anchor": "start"},
        }
    }
alt.themes.register("bht_theme", _bht_theme)
alt.themes.enable("bht_theme")

# --------- Build a CSV link from your Sheet + tab name ----------
def sheet_url_to_csv(url_or_id: str, tab_name: str) -> str:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9-_]{30,}", s):
        return f"https://docs.google.com/spreadsheets/d/{s}/gviz/tq?tqx=out:csv&sheet={_url.quote(tab_name)}"
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9-_]+)", s)
    if m:
        sheet_id = m.group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={_url.quote(tab_name)}"
    return s

DR_SHEET_TAB = "DR_Responses"
DR_EDIT_URL  = "https://docs.google.com/spreadsheets/d/1AMMfzbKreprRrhzJwMeQq9_2spdEvDLfGtEYnEMyF_8/edit?gid=0#gid=0"
DR_CSV_SOURCE = sheet_url_to_csv(DR_EDIT_URL, DR_SHEET_TAB)
st.caption(f"Using DR source: {DR_CSV_SOURCE}")

# --------- Robust CSV loader ----------
@st.cache_data(ttl=300, show_spinner=False)
def load_csv_from_url(url: str, *, retries: int = 2, timeout: int = 30) -> pd.DataFrame:
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            raw = r.content.replace(b"\x00", b"")
            head = raw[:400].decode("utf-8", errors="replace").lower()
            if "<html" in head:
                raise RuntimeError(
                    "Received HTML instead of CSV. Make the sheet public or Publish to web → CSV, "
                    "and use the CSV/export link."
                )
            buf = io.BytesIO(raw)
            tries = [
                dict(encoding="utf-8",     engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="error", low_memory=False),
                dict(encoding="utf-8",     engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="skip",  low_memory=False),
                dict(encoding="utf-8-sig", engine="python", sep=",", quoting=csv.QUOTE_NONE, escapechar="\\", on_bad_lines="skip", low_memory=False),
                dict(encoding="latin-1",   engine="python", sep=",", quotechar='"', doublequote=True, on_bad_lines="skip",  low_memory=False),
            ]
            for opts in tries:
                try:
                    buf.seek(0)
                    df = pd.read_csv(buf, **opts)
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
                except Exception:
                    pass
            # Fallback manual reader
            text = raw.decode("utf-8", errors="replace")
            lines = [ln for ln in text.splitlines() if ln.strip()]
            rows = [row for row in csv.reader(lines) if any(str(c).strip() for c in row)]
            if not rows:
                raise RuntimeError("No rows found in CSV.")
            header = [str(c).strip() for c in rows[0]]
            data = rows[1:]
            width = len(header)
            data = [(r + [""]*(width-len(r)))[:width] for r in data]
            df = pd.DataFrame(data, columns=header)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"Failed to load DR data: {last_err}")

# --------- Load data ----------
try:
    df = load_csv_from_url(DR_CSV_SOURCE)
except Exception as e:
    st.error(f"Failed to load DR data:\n\n{e}")
    st.stop()

# Deduplicate duplicate-named columns
if df.columns.duplicated().any():
    st.warning("Duplicate column names detected; keeping the first occurrence of each.")
    df = df.loc[:, ~df.columns.duplicated()]

# --------- Basic checks & cleanup ----------
need = {"StudentLast", "StudentFirst"}
if not need.issubset(df.columns):
    missing = sorted(list(need - set(df.columns)))
    st.error(f"Missing required columns on DR sheet: {missing}")
    st.stop()

has_grade = "Grade" in df.columns
_dt_col = next((c for c in ["DateTime", "Timestamp", "Date", "SubmittedAt"] if c in df.columns), None)

df["StudentLast"]  = df["StudentLast"].astype("string").str.strip()
df["StudentFirst"] = df["StudentFirst"].astype("string").str.strip()
if has_grade:
    df["Grade"] = df["Grade"].astype("string").str.strip()
if _dt_col:
    df["_dt"] = pd.to_datetime(df[_dt_col], errors="coerce")
else:
    df["_dt"] = pd.NaT
    
df["_name"] = (df["StudentLast"].astype("string").str.strip() + ", " +
               df["StudentFirst"].astype("string").str.strip())


# --------- Sidebar filters (NO DATE FILTER) ----------
with st.sidebar:
    st.header("🔎 Filters")
    # Grade filter
    grade_sel = []
    if has_grade:
        grades = sorted([g for g in df["Grade"].dropna().unique()])
        grade_sel = st.multiselect("Grade", options=grades, default=[])
    # Staff filter
    _teacher_col  = next((c for c in ["TeacherName","Teacher","Staff","Referrer"] if c in df.columns), None)
    staff_sel = []
    if _teacher_col:
        staff_opts = sorted([t for t in df[_teacher_col].astype("string").dropna().unique()])
        staff_sel = st.multiselect("Referrer", options=staff_opts, default=[])

# Apply filters to an analytics copy (no date filtering)
fdf = df.copy()
if has_grade and grade_sel:
    fdf = fdf[fdf["Grade"].isin(grade_sel)]
if _teacher_col and staff_sel:
    fdf = fdf[fdf[_teacher_col].isin(staff_sel)]

# --------- Helpers ----------
def _col(df_in, candidates):
    """Return the first existing column from a list of candidate names, else None."""
    for c in candidates:
        if c in df_in.columns:
            return c
    return None


def _vc(df_in, col, top=15, split_multi=False):
    if col not in df_in.columns:
        return pd.DataFrame(columns=["value","n"])
    s = df_in[col].astype("string").str.strip()
    if split_multi:
        s = s.str.replace(",", ";")
        s = s.str.split(";").explode().astype("string").str.strip()
    s = s.replace("", pd.NA).dropna()
    if s.empty:
        return pd.DataFrame(columns=["value","n"])
    vc = s.value_counts().reset_index()
    vc.columns = ["value", "n"]
    return vc.head(top)

def _bar(vc: pd.DataFrame, title: str, y_title="Value"):
    if vc is None or vc.empty:
        return None
    return (
        alt.Chart(vc)
        .mark_bar()
        .encode(
            y=alt.Y("value:N", sort="-x", title=y_title),
            x=alt.X("n:Q", title="Count", scale=alt.Scale(zero=True)),
            tooltip=["value:N", "n:Q"],
        )
        .properties(height=300, title=title)
    )

def _line_by_freq(s: pd.Series, freq_label: str, title_prefix="Referrals"):
    s = pd.to_datetime(s, errors="coerce").dropna()
    if s.empty:
        return None
    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    freq = freq_map.get(freq_label, "W")
    grp = s.groupby(s.dt.to_period(freq)).size().sort_index()
    grouped = grp.rename_axis("period").reset_index(name="n")
    grouped["period"] = grouped["period"].dt.start_time
    if grouped.empty:
        return None
    title = f"{title_prefix} — {freq_label}"
    return (
        alt.Chart(grouped)
        .mark_line(point=True)
        .encode(
            x=alt.X("period:T", title="Date"),
            y=alt.Y("n:Q", title="Count", scale=alt.Scale(zero=True)),
            tooltip=["period:T", "n:Q"],
        )
        .properties(height=300, title=title)
    )

def _stack_by_grade(df_in, cat_col, title):
    if cat_col not in df_in.columns or "Grade" not in df_in.columns:
        return None
    tmp = (
        df_in[[cat_col, "Grade"]]
        .astype("string")
        .apply(lambda c: c.str.strip())
        .replace("", pd.NA)
        .dropna()
    )
    if tmp.empty:
        return None
    tmp = tmp.assign(**{cat_col: tmp[cat_col].str.replace(",", ";").str.split(";")}).explode(cat_col)
    tmp[cat_col] = tmp[cat_col].astype("string").str.strip()
    grp = tmp.groupby([cat_col, "Grade"]).size().reset_index(name="n")
    if grp.empty:
        return None
    return (
        alt.Chart(grp)
        .mark_bar()
        .encode(
            y=alt.Y(f"{cat_col}:N", sort="-x", title=cat_col),
            x=alt.X("n:Q", title="Count", stack="zero"),
            color=alt.Color("Grade:N", title="Grade"),
            tooltip=[cat_col, "Grade", "n"],
        )
        .properties(height=320, title=title)
    )

def _heatmap_day_hour(s: pd.Series, title="Referrals by day & hour"):
    s = pd.to_datetime(s, errors="coerce").dropna()
    if s.empty:
        return None
    dd = pd.DataFrame({"_dt": s})
    dd["_dow"]  = dd["_dt"].dt.day_name().str[:3]
    dd["_hour"] = dd["_dt"].dt.hour
    heat = dd.groupby(["_dow","_hour"]).size().reset_index(name="n")
    if heat.empty:
        return None
    order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    return (
        alt.Chart(heat)
        .mark_rect()
        .encode(
            x=alt.X("_hour:O", title="Hour of day"),
            y=alt.Y("_dow:N", title="Day of week", sort=order),
            color=alt.Color("n:Q", title="Count"),
            tooltip=["_dow:N", "_hour:O", "n:Q"],
        )
        .properties(height=300, title=title)
    )

def _render_top2(title: str, vc: pd.DataFrame, fallback_caption: str):
    st.markdown(f"**Top 2 – {title}**")
    if vc is None or vc.empty:
        st.caption(fallback_caption)
        return
    items = vc.head(2).to_dict("records")
    cols = st.columns(2)
    for i, rec in enumerate(items):
        label = str(rec["value"]) if pd.notna(rec["value"]) else "—"
        count = int(rec["n"]) if pd.notna(rec["n"]) else 0
        cols[i].metric(label, count)

# --------- Counts & flags (full dataset; independent of filters) ----------
threshold = st.number_input("Flag threshold (referrals ≥)", min_value=1, value=3, step=1, help="Flags are computed from the full dataset.")
counts = (
    df.groupby(["StudentLast", "StudentFirst"], dropna=False)
      .size()
      .reset_index(name="ReferralCount")
)
latest = (
    df.groupby(["StudentLast", "StudentFirst"], dropna=False)["_dt"]
      .max()
      .reset_index(name="LastReferral")
)

if has_grade:
    def most_frequent(s):
        s = s.dropna().astype(str)
        return s.mode().iat[0] if not s.mode().empty else ""
    grades = (
        df.groupby(["StudentLast", "StudentFirst"], dropna=False)["Grade"]
          .apply(most_frequent)
          .reset_index(name="GradeMostFreq")
    )
else:
    grades = pd.DataFrame({"StudentLast": [], "StudentFirst": [], "GradeMostFreq": []})

summary = counts.merge(latest, on=["StudentLast", "StudentFirst"], how="left") \
               .merge(grades, on=["StudentLast", "StudentFirst"], how="left")
summary["Flag3Plus"] = np.where(summary["ReferralCount"] >= int(threshold), "Y", "")
summary["Name"] = summary["StudentLast"] + ", " + summary["StudentFirst"]
summary = summary.sort_values(["ReferralCount", "Name"], ascending=[False, True])
flagged = summary[summary["ReferralCount"] >= int(threshold)].copy()

# --------- Column picks ----------
_behavior_col = next((c for c in ["IncidentType","MainConcern","Behavior","ProblemBehavior"] if c in df.columns), None)
_teacher_col  = next((c for c in ["TeacherName","Teacher","Staff","Referrer"] if c in df.columns), None)
_grade_col    = "Grade" if "Grade" in df.columns else None
_interv_col   = next((c for c in ["ClassroomInterventions","Classroom Intervention","TeacherIntervention","Interventions"] if c in df.columns), None)
_location_col = next((c for c in ["Location","Setting","BehaviorSubject"] if c in df.columns), None)
_proactive_col = next((c for c in ["ProactiveConcerns","Proactive Concern","ProactiveConcern","Proactive"] if c in df.columns), None)
_minor_col = next((c for c in ["MinorProblemBehavior","Minor Problem","MinorBehavior","Minor"] if c in df.columns), None)
_major_col = next((c for c in ["MajorProblemBehavior","Major Problem","MajorBehavior","Major"] if c in df.columns), None)
_sel_col = next((c for c in ["SELCompetency","SEL Competency","SEL Area","SEL Domain"] if c in df.columns), None)

# ============================== LAYOUT (tabs) ==============================
tab_overview, tab_analytics, tab_narrative, tab_flags, tab_raw = st.tabs(
    ["Overview", "Analytics", "Narrative", "Flags", "Raw Data"]
)

with tab_overview:
    st.subheader("At a glance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total referrals", f"{len(df):,}")
    unique_students = df[["StudentLast","StudentFirst"]].dropna().drop_duplicates().shape[0]
    latest_dt = df["_dt"].dropna().max()
    c2.metric("Unique students", f"{unique_students:,}")
    c3.metric("Last referral", latest_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(latest_dt) else "—")

    st.divider()
    st.markdown("**Top 2 responses** (respects sidebar filters)")
    grid1 = st.columns(2)
    with grid1[0]:
        if has_grade: _render_top2("Grades", _vc(fdf, "Grade", top=2, split_multi=False), "No grade data.")
        if _interv_col: _render_top2("Teacher interventions", _vc(fdf, _interv_col, top=2, split_multi=True), "No intervention data.")
    with grid1[1]:
        if _proactive_col: _render_top2("Proactive concerns", _vc(fdf, _proactive_col, top=2, split_multi=True), "No proactive data.")
        if _sel_col: _render_top2("SEL competency", _vc(fdf, _sel_col, top=2, split_multi=True), "No SEL data.")

    grid2 = st.columns(2)
    with grid2[0]:
        if _minor_col: _render_top2("Minor problems", _vc(fdf, _minor_col, top=2, split_multi=True), "No minor problem data.")
    with grid2[1]:
        if _major_col: _render_top2("Major problems", _vc(fdf, _major_col, top=2, split_multi=True), "No major problem data.")

with tab_analytics:
    st.subheader("📊 Trends & distributions")
    granularity = st.radio("Time grain", ["Daily", "Weekly", "Monthly"], index=1, horizontal=True)
    ch = _line_by_freq(fdf["_dt"], granularity, title_prefix="Referrals")
    if ch: st.altair_chart(ch, use_container_width=True)
    else:  st.caption("No usable dates to chart.")

    c1, c2 = st.columns(2)
    with c1:
        if _grade_col:
            vc = _vc(fdf, _grade_col, top=20)
            ch = _bar(vc, "Referrals by grade", "Grade")
            if ch: st.altair_chart(ch, use_container_width=True)
            else:  st.caption("No grade data.")
        if _behavior_col:
            vc = _vc(fdf, _behavior_col, top=15, split_multi=True)
            ch = _bar(vc, "Top behaviors (multi-select supported)")
            if ch: st.altair_chart(ch, use_container_width=True)
            else:  st.caption("No behavior data.")
    with c2:
        if _teacher_col:
            vc = _vc(fdf, _teacher_col, top=12)
            ch = _bar(vc, "Top referrers", "Staff")
            if ch: st.altair_chart(ch, use_container_width=True)
            else:  st.caption("No referrer data.")
        if _location_col:
            vc = _vc(fdf, _location_col, top=12)
            ch = _bar(vc, "Top locations", "Location")
            if ch: st.altair_chart(ch, use_container_width=True)
            else:  st.caption("No location data.")

    if _behavior_col and has_grade:
        st.markdown("**Behaviors by grade (stacked)**")
        ch = _stack_by_grade(fdf, _behavior_col, "Behaviors by grade")
        if ch: st.altair_chart(ch, use_container_width=True)
        else:  st.caption("No data to stack by grade.")

    st.markdown("**When do referrals happen?**")
    ch = _heatmap_day_hour(fdf["_dt"])
    if ch: st.altair_chart(ch, use_container_width=True)
    else:  st.caption("No day/hour data.")

    if _interv_col:
        st.markdown("**Classroom interventions (multi-select)**")
        vc = _vc(fdf, _interv_col, top=20, split_multi=True)
        ch = _bar(vc, "Interventions used", "Intervention")
        if ch: st.altair_chart(ch, use_container_width=True)
        else:  st.caption("No interventions recorded.")
        
with tab_narrative:
    st.subheader("🧾 Student Narrative")

    # Column picks we’ll reuse
    
    # Prefer Homeroom Teacher; fall back to other likely columns
    teacher_col = _col(df, [
        "Homeroom Teacher", "HomeroomTeacher", "HRTeacher",
        "Teacher/POC", "POC", "TeacherName", "Teacher", "Staff", "Referrer"
    ])

    main_col     = _col(df, ["IncidentType","MainConcern","Behavior","ProactiveConcern","ProblemBehavior"])
    addl_col     = _col(df, ["AdditionalConcern","SecondaryConcern"])
    location_col = _col(df, ["Location","Setting","BehaviorSubject"])
    # Observation / free text possibilities
    note_col     = _col(df, ["Observation","Notes","Description","Narrative","Details"])
    # Interventions (single combined) or tiered
    interv_col   = _col(df, ["ClassroomInterventions","TeacherIntervention","Interventions"])
    tier1_col    = _col(df, ["TierOne","Tier 1","Tier I"])
    tier2_col    = _col(df, ["TierTwo","Tier 2","Tier II"])
    tier3_col    = _col(df, ["TierThree","Tier 3","Tier III"])

    # Student picker
    student_list = sorted([n for n in df["_name"].dropna().unique() if n and n != ", "])
    if not student_list:
        st.info("No student names found.")
        st.stop()

    student = st.selectbox("Choose a student", student_list, index=0, key="narr_student")

    # Filter to that student & sort by datetime if present
    sdf = df[df["_name"] == student].copy()
    sdf = sdf.sort_values("_dt") if "_dt" in sdf.columns else sdf

    # Quick search within this student's entries
    q = st.text_input("Search this student's entries (optional)")
    if q:
        qlow = q.lower()
        # Build a combined text column to search
        search_cols = [c for c in [note_col, main_col, addl_col, location_col, teacher_col, interv_col,
                                   tier1_col, tier2_col, tier3_col] if c]
        if search_cols:
            sdf = sdf[sdf[search_cols].astype(str).apply(lambda row: qlow in (" | ".join(row)).lower(), axis=1)]

    if sdf.empty:
        st.caption("No matching entries for this student.")
        st.stop()

    # Render as a simple timeline
    st.markdown(f"**Entries for:** {student}  &nbsp;&nbsp; _(total {len(sdf)})_")
    st.divider()

    parts = []
    for _, r in sdf.iterrows():
        dt_str = ""
        if "_dt" in r and pd.notna(r["_dt"]):
            try:
                dt_str = pd.to_datetime(r["_dt"]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                dt_str = str(r.get("_dt", "")) or ""

        # Collect fields for display
        teacher = str(r.get(teacher_col, "")) if teacher_col else ""
        main    = str(r.get(main_col, "")) if main_col else ""
        addl    = str(r.get(addl_col, "")) if addl_col else ""
        loc     = str(r.get(location_col, "")) if location_col else ""
        note    = str(r.get(note_col, "")) if note_col else ""

        # Interventions summary (prefer combined; else join tiers)
        interv = ""
        if interv_col:
            interv = str(r.get(interv_col, "")) or ""
        else:
            tiers = [str(r.get(tier1_col,"") or ""), str(r.get(tier2_col,"") or ""), str(r.get(tier3_col,"") or "")]
            tiers = [t for t in tiers if t]
            interv = "; ".join(tiers)

        # Pretty card
        st.markdown(
            f"""
<div style="border-left:4px solid #e5e7eb; padding:8px 12px; margin:8px 0;">
  <div style="font-weight:600;">{dt_str or "—"}</div>
    <div style="color:#4b5563; margin-top:2px;">
      <b>Homeroom teacher:</b> {teacher or "—"} &nbsp;&nbsp;
      <b>Location:</b> {loc or "—"}
    </div>

  <div style="margin-top:6px;">
    <b>Main concern:</b> {main or "—"}<br/>
    {"<b>Additional:</b> " + addl if addl else ""}
  </div>
  <div style="margin-top:6px;">
    <b>Interventions:</b> {interv or "—"}
  </div>
  {"<div style='margin-top:6px; white-space:pre-wrap;'><b>Observation:</b> " + (note or "—") + "</div>" if note_col else ""}
</div>
""",
            unsafe_allow_html=True
        )

        # For downloadable narrative text
        line = []
        if dt_str: line.append(f"[{dt_str}]")
        if teacher: line.append(f"Staff: {teacher}")
        if loc: line.append(f"Location: {loc}")
        if main: line.append(f"Main: {main}")
        if addl: line.append(f"Additional: {addl}")
        if interv: line.append(f"Interventions: {interv}")
        if note: line.append(f"Observation: {note}")
        parts.append(" | ".join(line))

    # Download compiled narrative
    compiled = ("\n".join(parts)).encode("utf-8")
    st.download_button(
        "Download narrative (.txt)",
        data=compiled,
        file_name=f"{student.replace(',','').replace(' ','_')}_narrative.txt",
        mime="text/plain"
    )


with tab_flags:
    st.subheader("🚩 Students flagged")
    st.caption(f"Students with ≥ {int(threshold)} referrals (computed from the full dataset).")

    left, right = st.columns([1,3])
    left.metric("Flagged students", len(flagged))
    right.metric("Total unique students", summary.shape[0])

    st.dataframe(
        flagged[["Name", "GradeMostFreq", "ReferralCount", "LastReferral", "Flag3Plus"]],
        hide_index=True, use_container_width=True
    )

    csv_bytes = flagged.to_csv(index=False).encode("utf-8")
    st.download_button("Download flagged CSV", data=csv_bytes, file_name="flagged_referrals.csv", mime="text/csv")

    with st.expander("See all students"):
        st.dataframe(
            summary[["Name", "GradeMostFreq", "ReferralCount", "LastReferral", "Flag3Plus"]],
            hide_index=True, use_container_width=True
        )

with tab_raw:
    st.subheader("Raw DR data (filtered view)")
    st.caption("This table reflects the sidebar filters (Grade / Referrer).")
    st.dataframe(fdf, use_container_width=True, hide_index=True)
