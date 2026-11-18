"""HAT Questionnaire Analyser — Pre-Test vs Post-Test (Streamlit app)."""
import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analysis as A

st.set_page_config(page_title="HAT Pre/Post Test Analyser", page_icon="📊", layout="wide")

COLORS = {"Yes": "#2e7d32", "Not Sure": "#f9a825", "No": "#c62828",
          "Pre": "#90a4ae", "Post": "#1565c0"}
DEFAULT_FILE = Path(__file__).parent / "data" / "HAT_PRE_AND_POST_TEST.xlsx"

# ---------------------------------------------------------------- data
st.sidebar.title("📊 HAT Analyser")
upload = st.sidebar.file_uploader("Upload pre/post test workbook (.xlsx)", type=["xlsx"])
st.sidebar.caption("Workbook needs a **pre-test** and a **post-test** sheet with columns: "
                   "Serial No., Name, Gender, Class, then one column per question (Yes / Not Sure / No).")


@st.cache_data
def load(file_bytes):
    return A.load_workbook(io.BytesIO(file_bytes))


if upload is not None:
    raw = upload.getvalue()
    source = upload.name
elif DEFAULT_FILE.exists():
    raw = DEFAULT_FILE.read_bytes()
    source = DEFAULT_FILE.name + " (sample)"
else:
    st.info("⬅️ Upload the HAT pre/post test Excel workbook to begin.")
    st.stop()

try:
    pre_all, post_all, questions = load(raw)
except Exception as e:
    st.error(f"Could not read the workbook: {e}")
    st.stop()

qcols = list(questions["Question"])

# ---------------------------------------------------------------- filters
st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
genders = sorted(set(pre_all["Gender"]) | set(post_all["Gender"]))
classes = sorted(set(pre_all["Class"]) | set(post_all["Class"]))
sel_g = st.sidebar.multiselect("Gender", genders, default=genders)
sel_c = st.sidebar.multiselect("Class", classes, default=classes)
themes = list(dict.fromkeys(questions["Theme"]))
sel_t = st.sidebar.multiselect("Question theme", themes, default=themes)


def filt(df):
    return df[df["Gender"].isin(sel_g) & df["Class"].isin(sel_c)]


pre, post = filt(pre_all), filt(post_all)
qsel = questions[questions["Theme"].isin(sel_t)]
if pre.empty or post.empty or qsel.empty:
    st.warning("No data for the selected filters.")
    st.stop()

st.title("HAT Questionnaire Analysis: Pre-Test vs Post-Test")
st.caption(f"Source: {source} · Pre-test n = {len(pre)} · Post-test n = {len(post)} · "
           f"{len(qsel)} questions")


# ---------------------------------------------------------------- helpers
def stacked_bar(tbl, title):
    long = tbl.melt(id_vars=["Q#", "Question"], value_vars=[f"{r} %" for r in A.RESPONSES],
                    var_name="Response", value_name="Percent")
    long["Response"] = long["Response"].str.replace(" %", "", regex=False)
    long["Label"] = long["Q#"] + " · " + long["Question"]
    fig = px.bar(long, y="Label", x="Percent", color="Response", orientation="h",
                 color_discrete_map=COLORS, text=long["Percent"].map(lambda v: f"{v:.0f}%" if v >= 6 else ""),
                 category_orders={"Label": list(dict.fromkeys(long["Label"])), "Response": A.RESPONSES})
    fig.update_layout(title=title, barmode="stack", height=max(420, 32 * len(tbl)),
                      xaxis_title="% of students", yaxis_title="", legend_title="",
                      legend=dict(orientation="h", y=1.05), margin=dict(l=10, r=10, t=70, b=10))
    fig.update_yaxes(autorange="reversed")
    return fig


def single_test_tab(df, name):
    tbl = A.response_table(df, qsel)
    scored = A.add_scores(df, list(qsel["Question"]))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", len(df))
    c2.metric("Average 'Yes' %", f"{tbl['Yes %'].mean():.1f}%")
    c3.metric("Average 'Not Sure' %", f"{tbl['Not Sure %'].mean():.1f}%")
    c4.metric("Average 'No' %", f"{tbl['No %'].mean():.1f}%")

    st.plotly_chart(stacked_bar(tbl, f"{name}: responses by question"), use_container_width=True)

    a, b = st.columns(2)
    with a:
        fig = px.histogram(scored, x="Score %", nbins=10, color_discrete_sequence=[COLORS["Post" if name == "Post-test" else "Pre"]])
        fig.update_layout(title="Distribution of student scores (Yes=2, Not Sure=1, No=0)",
                          xaxis_title="Score %", yaxis_title="Students", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        g = scored.groupby(["Gender", "Class"])["Score %"].mean().round(1).reset_index()
        fig = px.bar(g, x="Class", y="Score %", color="Gender", barmode="group", text="Score %")
        fig.update_layout(title="Mean score % by class and gender", height=350, yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Response table")
    show = tbl[["Q#", "Question", "Theme", "Yes", "Not Sure", "No", "Total", "Yes %", "Not Sure %", "No %"]]
    st.dataframe(show, hide_index=True, use_container_width=True)

    with st.expander("Student-level scores"):
        st.dataframe(scored[["Serial No.", "Name", "Gender", "Class", "Yes count", "Score", "Score %"]]
                     .sort_values("Score %", ascending=False), hide_index=True, use_container_width=True)
    return tbl


# ---------------------------------------------------------------- tabs
tab_sum, tab_pre, tab_post, tab_stu, tab_dl = st.tabs(
    ["📈 Summary (Pre vs Post)", "📝 Pre-test", "✅ Post-test", "👥 Student progress", "⬇️ Download"])

comp = A.comparison_table(pre, post, qsel)
matched, un_pre, un_post = A.paired_scores(pre, post, list(qsel["Question"]))

with tab_sum:
    pre_avg, post_avg = comp["Pre Yes %"].mean(), comp["Post Yes %"].mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pre-test avg 'Yes'", f"{pre_avg:.1f}%")
    c2.metric("Post-test avg 'Yes'", f"{post_avg:.1f}%", f"{post_avg - pre_avg:+.1f} pts")
    c3.metric("Questions improved", f"{(comp['Yes % Change'] > 0).sum()} / {len(comp)}")
    if len(matched):
        c4.metric("Students improved", f"{(matched['Change'] > 0).sum()} / {len(matched)}")

    st.info(A.summary_note(comp, len(pre), len(post)))

    lab = comp["Q#"] + " · " + comp["Question"]
    fig = go.Figure()
    fig.add_bar(y=lab, x=comp["Pre Yes %"], name="Pre-test", orientation="h", marker_color=COLORS["Pre"],
                text=comp["Pre Yes %"].map("{:.0f}%".format))
    fig.add_bar(y=lab, x=comp["Post Yes %"], name="Post-test", orientation="h", marker_color=COLORS["Post"],
                text=comp["Post Yes %"].map("{:.0f}%".format))
    fig.update_layout(title="'Yes' % by question: Pre vs Post", barmode="group",
                      height=max(480, 44 * len(comp)), xaxis_title="% answering Yes", xaxis_range=[0, 100],
                      legend=dict(orientation="h", y=1.04), margin=dict(l=10, r=10, t=70, b=10))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    a, b = st.columns(2)
    with a:
        srt = comp.sort_values("Yes % Change")
        fig = px.bar(srt, x="Yes % Change", y=srt["Q#"] + " · " + srt["Question"], orientation="h",
                     text=srt["Yes % Change"].map("{:+.1f}".format),
                     color=srt["Yes % Change"] > 0, color_discrete_map={True: COLORS["Yes"], False: COLORS["No"]})
        fig.update_layout(title="Change in 'Yes' % (percentage points)", showlegend=False,
                          yaxis_title="", height=max(420, 30 * len(comp)))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        th = A.theme_table(comp)
        fig = go.Figure()
        fig.add_bar(x=th["Theme"], y=th["Pre Yes %"], name="Pre-test", marker_color=COLORS["Pre"])
        fig.add_bar(x=th["Theme"], y=th["Post Yes %"], name="Post-test", marker_color=COLORS["Post"])
        fig.update_layout(title="Average 'Yes' % by theme", barmode="group", yaxis_range=[0, 100],
                          height=420, legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(th, hide_index=True, use_container_width=True)

    # overall response mix
    tot = pd.DataFrame({
        "Test": ["Pre-test"] * 3 + ["Post-test"] * 3,
        "Response": A.RESPONSES * 2,
        "Count": [comp[f"Pre {r}"].sum() for r in A.RESPONSES] + [comp[f"Post {r}"].sum() for r in A.RESPONSES]})
    tot["Percent"] = tot["Count"] / tot.groupby("Test")["Count"].transform("sum") * 100
    fig = px.bar(tot, x="Test", y="Percent", color="Response", color_discrete_map=COLORS,
                 text=tot["Percent"].map("{:.1f}%".format), category_orders={"Response": A.RESPONSES})
    fig.update_layout(title="Overall response mix (all questions)", height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Summary table")
    cols = ["Q#", "Question", "Pre Yes", "Pre Not Sure", "Pre No", "Pre Total", "Pre Yes %",
            "Post Yes", "Post Not Sure", "Post No", "Post Total", "Post Yes %", "Yes % Change"]
    avg = comp[cols[2:]].mean().round(1)
    table = pd.concat([comp[cols], pd.DataFrame([{"Q#": "AVG", "Question": "Overall mean", **avg}])],
                      ignore_index=True)
    st.dataframe(table.style.background_gradient(subset=["Yes % Change"], cmap="RdYlGn"),
                 hide_index=True, use_container_width=True)

    for by in ["Gender", "Class"]:
        st.markdown(f"**Mean score % by {by.lower()}**")
        st.dataframe(A.subgroup_table(pre, post, list(qsel["Question"]), by), hide_index=True,
                     use_container_width=True)

with tab_pre:
    pre_tbl = single_test_tab(pre, "Pre-test")

with tab_post:
    post_tbl = single_test_tab(post, "Post-test")

with tab_stu:
    st.subheader("Matched students (same name in both tests)")
    if matched.empty:
        st.warning("No students could be matched by name between the two sheets.")
    else:
        res = A.paired_test(matched)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Matched students", len(matched))
        c2.metric("Improved", int((matched["Change"] > 0).sum()))
        c3.metric("No change", int((matched["Change"] == 0).sum()))
        c4.metric("Declined", int((matched["Change"] < 0).sum()))
        if res:
            sig = "statistically significant" if res["w_p"] < 0.05 else "not statistically significant"
            st.success(
                f"Mean score rose from **{res['mean_pre']:.1f}** to **{res['mean_post']:.1f}** "
                f"(out of {2 * len(qsel)}), a mean gain of **{res['mean_diff']:+.1f}** (SD {res['sd_diff']:.1f}). "
                f"Paired t-test: t = {res['t']:.2f}, p = {res['t_p']:.2g}. "
                f"Wilcoxon signed-rank: p = {res['w_p']:.2g} — the change is **{sig}** (p < 0.05). "
                f"Effect size (Cohen's d) = {res['cohen_d']:.2f}.")
        a, b = st.columns(2)
        with a:
            fig = go.Figure()
            for _, r in matched.iterrows():
                fig.add_trace(go.Scatter(x=["Pre-test", "Post-test"], y=[r["Score % (Pre)"], r["Score % (Post)"]],
                                         mode="lines+markers", name=r["Name"], showlegend=False,
                                         line=dict(color=COLORS["Yes"] if r["Change"] > 0 else
                                                   COLORS["No"] if r["Change"] < 0 else "#999", width=1),
                                         opacity=0.6, hovertemplate=r["Name"] + ": %{y:.1f}%<extra></extra>"))
            fig.update_layout(title="Each student's score % (green = improved, red = declined)",
                              yaxis_title="Score %", height=450)
            st.plotly_chart(fig, use_container_width=True)
        with b:
            fig = px.histogram(matched, x="Change %", nbins=15, color_discrete_sequence=[COLORS["Post"]])
            fig.add_vline(x=0, line_dash="dash")
            fig.update_layout(title="Distribution of score change (percentage points)",
                              yaxis_title="Students", height=450)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(matched.sort_values("Change", ascending=False), hide_index=True, use_container_width=True)
    if un_pre or un_post:
        with st.expander("Unmatched names (check spelling)"):
            st.write("Only in pre-test:", un_pre or "—")
            st.write("Only in post-test:", un_post or "—")

with tab_dl:
    st.subheader("Download analysis as Excel")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"Summary": [A.summary_note(comp, len(pre), len(post))]}).to_excel(xw, sheet_name="Summary note", index=False)
        table.to_excel(xw, sheet_name="Summary table", index=False)
        A.theme_table(comp).to_excel(xw, sheet_name="By theme", index=False)
        pre_tbl.to_excel(xw, sheet_name="Pre-test analysis", index=False)
        post_tbl.to_excel(xw, sheet_name="Post-test analysis", index=False)
        if not matched.empty:
            matched.to_excel(xw, sheet_name="Student progress", index=False)
    st.download_button("⬇️ Download Excel report", buf.getvalue(),
                       file_name="HAT_pre_post_analysis.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("⬇️ Download summary table (CSV)", table.to_csv(index=False).encode(),
                       file_name="HAT_summary.csv", mime="text/csv")
