"""Data loading and analysis for the HAT Pre-Test / Post-Test questionnaire."""
import re
import numpy as np
import pandas as pd

RESPONSES = ["Yes", "Not Sure", "No"]
SCORE_MAP = {"Yes": 2, "Not Sure": 1, "No": 0}   # 2 = most positive answer
META_COLS = ["Serial No.", "Name", "Gender", "Class"]

# Short labels and themes for the 17 HAT questions (in sheet order)
SHORT_LABELS = [
    "Mental health as important as physical",
    "Know how to care for mental well-being",
    "Recognise effect of emotions",
    "Manage actions when upset/angry",
    "Healthy ways to manage stress",
    "Aware when feeling stressed",
    "Problem-solving skills are important",
    "Consider solutions before deciding",
    "Easy to share thoughts & feelings",
    "Understand how others think & feel",
    "Express feelings respectfully",
    "Knowledge to refuse alcohol/tobacco/drugs",
    "Substances affect relationships",
    "Substances affect physical & mental health",
    "Stand up for self respectfully",
    "Know personal strengths",
    "Replace negative thoughts",
]
THEMES = [
    "Mental health awareness", "Mental health awareness",
    "Emotions & stress", "Emotions & stress", "Emotions & stress", "Emotions & stress",
    "Problem solving", "Problem solving",
    "Communication & empathy", "Communication & empathy", "Communication & empathy",
    "Substance use", "Substance use", "Substance use",
    "Self-esteem & assertiveness", "Self-esteem & assertiveness", "Self-esteem & assertiveness",
]


def _find_sheet(sheets, keyword):
    for s in sheets:
        if keyword in s.lower().replace("-", "").replace("_", "").replace(" ", ""):
            return s
    return None


def _clean_answer(v):
    if pd.isna(v):
        return np.nan
    t = str(v).strip().lower()
    if t in ("yes", "y"):
        return "Yes"
    if t in ("no", "n"):
        return "No"
    if t.replace(" ", "") in ("notsure", "unsure", "dontknow", "don'tknow"):
        return "Not Sure"
    return np.nan


def clean_sheet(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {df.columns[0]: "Serial No.", df.columns[1]: "Name",
              df.columns[2]: "Gender", df.columns[3]: "Class"}
    df = df.rename(columns=rename)
    df = df[df["Name"].notna() & (df["Name"].astype(str).str.strip() != "")]
    df["Name"] = df["Name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    g = df["Gender"].astype(str).str.strip().str.title()
    df["Gender"] = g.where(g.isin(["Male", "Female"]), "Not recorded")
    df["Class"] = df["Class"].astype(str).str.strip().str.upper().replace({"NAN": "Not recorded"})
    qcols = [c for c in df.columns if c not in META_COLS]
    for c in qcols:
        df[c] = df[c].map(_clean_answer)
    return df.reset_index(drop=True), qcols


def load_workbook(file):
    xls = pd.ExcelFile(file)
    pre_name = _find_sheet(xls.sheet_names, "pre")
    post_name = _find_sheet(xls.sheet_names, "post")
    if not pre_name or not post_name:
        raise ValueError("Workbook must contain a 'pre-test' sheet and a 'post-test' sheet.")
    pre, qcols = clean_sheet(pd.read_excel(xls, pre_name))
    post, qcols_post = clean_sheet(pd.read_excel(xls, post_name))
    if len(qcols) != len(qcols_post):
        raise ValueError("Pre-test and post-test sheets have a different number of questions.")
    post = post.rename(columns=dict(zip(qcols_post, qcols)))
    questions = pd.DataFrame({
        "Q#": [f"Q{i+1}" for i in range(len(qcols))],
        "Question": qcols,
        "Short": SHORT_LABELS if len(qcols) == len(SHORT_LABELS) else [q[:45] for q in qcols],
        "Theme": THEMES if len(qcols) == len(THEMES) else ["All"] * len(qcols),
    })
    return pre, post, questions


def add_scores(df, qcols):
    df = df.copy()
    sc = df[qcols].apply(lambda s: s.map(SCORE_MAP))
    df["Yes count"] = (df[qcols] == "Yes").sum(axis=1)
    df["Score"] = sc.sum(axis=1)
    df["Score %"] = (df["Score"] / (2 * sc.notna().sum(axis=1)) * 100).round(1)
    return df


def response_table(df, questions):
    """Counts and % of Yes / Not Sure / No for each question."""
    rows = []
    for _, q in questions.iterrows():
        s = df[q["Question"]]
        n = int(s.notna().sum())
        row = {"Q#": q["Q#"], "Question": q["Short"], "Theme": q["Theme"]}
        for r in RESPONSES:
            c = int((s == r).sum())
            row[r] = c
            row[f"{r} %"] = round(c / n * 100, 1) if n else 0.0
        row["Total"] = n
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_table(pre, post, questions):
    a, b = response_table(pre, questions), response_table(post, questions)
    out = a[["Q#", "Question", "Theme"]].copy()
    for r in RESPONSES:
        out[f"Pre {r}"] = a[r]
    out["Pre Total"] = a["Total"]
    out["Pre Yes %"] = a["Yes %"]
    for r in RESPONSES:
        out[f"Post {r}"] = b[r]
    out["Post Total"] = b["Total"]
    out["Post Yes %"] = b["Yes %"]
    out["Yes % Change"] = ((b["Yes"] / b["Total"] - a["Yes"] / a["Total"]) * 100).round(1)
    out["Pre No %"] = a["No %"]
    out["Post No %"] = b["No %"]
    out["No % Change"] = (out["Post No %"] - out["Pre No %"]).round(1)
    return out


def theme_table(comp):
    g = comp.groupby("Theme", sort=False)[["Pre Yes %", "Post Yes %"]].mean().round(1)
    g["Change"] = (g["Post Yes %"] - g["Pre Yes %"]).round(1)
    return g.reset_index()


def paired_scores(pre, post, qcols):
    """Match students by name (case-insensitive) and compare total scores."""
    a, b = add_scores(pre, qcols), add_scores(post, qcols)
    a["key"] = a["Name"].str.lower()
    b["key"] = b["Name"].str.lower()
    m = a[["key", "Name", "Gender", "Class", "Score", "Score %", "Yes count"]].merge(
        b[["key", "Score", "Score %", "Yes count"]], on="key", suffixes=(" (Pre)", " (Post)"))
    m["Change"] = m["Score (Post)"] - m["Score (Pre)"]
    m["Change %"] = (m["Score % (Post)"] - m["Score % (Pre)"]).round(1)
    m["Direction"] = np.select([m["Change"] > 0, m["Change"] < 0], ["Improved", "Declined"], "No change")
    unmatched_pre = sorted(set(a["Name"][~a["key"].isin(m["key"])]))
    unmatched_post = sorted(set(b["Name"][~b["key"].isin(m["key"])]))
    return m.drop(columns="key"), unmatched_pre, unmatched_post


def paired_test(m):
    """Paired t-test and Wilcoxon signed-rank test on matched scores."""
    try:
        from scipy import stats
    except ImportError:
        return None
    x, y = m["Score (Pre)"], m["Score (Post)"]
    if len(m) < 3 or (y - x).abs().sum() == 0:
        return None
    t = stats.ttest_rel(y, x)
    w = stats.wilcoxon(y, x)
    d = (y - x)
    return {"n": len(m), "mean_pre": x.mean(), "mean_post": y.mean(),
            "mean_diff": d.mean(), "sd_diff": d.std(ddof=1),
            "cohen_d": d.mean() / d.std(ddof=1) if d.std(ddof=1) else np.nan,
            "t": t.statistic, "t_p": t.pvalue, "w": w.statistic, "w_p": w.pvalue}


def subgroup_table(pre, post, qcols, by):
    a, b = add_scores(pre, qcols), add_scores(post, qcols)
    ga = a.groupby(by)["Score %"].agg(["count", "mean"]).rename(columns={"count": "Pre n", "mean": "Pre mean score %"})
    gb = b.groupby(by)["Score %"].agg(["count", "mean"]).rename(columns={"count": "Post n", "mean": "Post mean score %"})
    out = ga.join(gb, how="outer").round(1)
    out["Change"] = (out["Post mean score %"] - out["Pre mean score %"]).round(1)
    return out.reset_index()


def summary_note(comp, n_pre, n_post):
    pre_avg, post_avg = comp["Pre Yes %"].mean(), comp["Post Yes %"].mean()
    ch = comp["Yes % Change"]
    best = comp.loc[ch.idxmax()]
    worst = comp.loc[ch.idxmin()]
    improved = int((ch > 0).sum())
    return (f"Post-test results (n = {n_post}) show an average 'Yes' response of {post_avg:.1f}%, "
            f"compared with {pre_avg:.1f}% in the pre-test (n = {n_pre}) — an overall change of "
            f"{post_avg - pre_avg:+.1f} percentage points. {improved} of {len(comp)} questions improved "
            f"(range {ch.min():+.1f} to {ch.max():+.1f}). The largest gain was {best['Q#']} "
            f"({best['Question']}, {best['Yes % Change']:+.1f}); the smallest was {worst['Q#']} "
            f"({worst['Question']}, {worst['Yes % Change']:+.1f}).")
