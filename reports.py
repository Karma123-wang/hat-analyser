"""Report builders for the HAT analyser: PDF (reportlab + matplotlib),
PowerPoint (native, editable charts) and interactive Excel (formulas + native charts)."""
import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analysis as A

PRE_C, POST_C = "#90A4AE", "#1565C0"
RESP_C = {"Yes": "#2E7D32", "Not Sure": "#F9A825", "No": "#C62828"}

SECTIONS = {
    "kpis": "Key figures",
    "pre_post": "Pre vs Post 'Yes' % by question",
    "change": "Change in 'Yes' % by question",
    "themes": "Results by theme",
    "mix": "Overall response mix",
    "pre": "Pre-test responses by question",
    "post": "Post-test responses by question",
    "students": "Student progress (matched students)",
    "groups": "Results by gender and class",
    "table": "Summary table",
}


def default_options(note):
    return {
        "title": "HAT Questionnaire Analysis",
        "subtitle": "Pre-Test vs Post-Test Comparison",
        "organisation": "",
        "prepared_by": "",
        "report_date": date.today().strftime("%d %B %Y"),
        "intro": "",
        "findings": note,
        "recommendations": "",
        "sections": list(SECTIONS),
        "show_names": False,
    }


# ------------------------------------------------------------------ data bundle
def build_bundle(pre, post, qsel):
    qc = list(qsel["Question"])
    comp = A.comparison_table(pre, post, qsel)
    matched, _, _ = A.paired_scores(pre, post, qc)
    mix = {}
    for t in ("Pre", "Post"):
        tot = sum(comp[f"{t} {r}"].sum() for r in A.RESPONSES)
        mix[t] = {r: comp[f"{t} {r}"].sum() / tot * 100 if tot else 0 for r in A.RESPONSES}
    return {
        "pre": pre, "post": post, "questions": qsel, "qcols": qc,
        "comp": comp, "themes": A.theme_table(comp),
        "pre_tbl": A.response_table(pre, qsel), "post_tbl": A.response_table(post, qsel),
        "matched": matched, "stats": A.paired_test(matched) if len(matched) else None,
        "by_gender": A.subgroup_table(pre, post, qc, "Gender"),
        "by_class": A.subgroup_table(pre, post, qc, "Class"),
        "mix": mix, "note": A.summary_note(comp, len(pre), len(post)),
        "n_pre": len(pre), "n_post": len(post),
    }


def kpi_list(b):
    c, m = b["comp"], b["matched"]
    pre_avg, post_avg = c["Pre Yes %"].mean(), c["Post Yes %"].mean()
    k = [("Pre-test avg 'Yes'", f"{pre_avg:.1f}%"),
         ("Post-test avg 'Yes'", f"{post_avg:.1f}%"),
         ("Change", f"{post_avg - pre_avg:+.1f} pts"),
         ("Questions improved", f"{(c['Yes % Change'] > 0).sum()} / {len(c)}")]
    if len(m):
        k.append(("Students improved", f"{(m['Change'] > 0).sum()} / {len(m)}"))
    return k


def stats_text(b):
    s = b["stats"]
    if not s:
        return ""
    sig = "statistically significant" if s["w_p"] < 0.05 else "not statistically significant"
    return (f"Among {s['n']} students matched by name, the mean score rose from {s['mean_pre']:.1f} to "
            f"{s['mean_post']:.1f} (out of {2 * len(b['qcols'])}), a mean gain of {s['mean_diff']:+.1f}. "
            f"Paired t-test p = {s['t_p']:.2g}; Wilcoxon signed-rank p = {s['w_p']:.2g}. "
            f"The change is {sig} (p < 0.05). Effect size (Cohen's d) = {s['cohen_d']:.2f}.")


def _fmt(v):
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else f"{v:.1f}"
    return str(v)


def _labels(df):
    return (df["Q#"] + " · " + df["Question"]).tolist()


def summary_table_df(b):
    c = b["comp"]
    cols = ["Q#", "Question", "Pre Yes", "Pre Not Sure", "Pre No", "Pre Yes %",
            "Post Yes", "Post Not Sure", "Post No", "Post Yes %", "Yes % Change"]
    t = c[cols].copy()
    avg = t[cols[2:]].mean().round(1)
    return pd.concat([t, pd.DataFrame([{"Q#": "AVG", "Question": "Overall mean", **avg}])], ignore_index=True)


# ------------------------------------------------------------------ matplotlib charts
def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)


def chart_pre_post(b):
    c = b["comp"]
    lab = _labels(c)[::-1]
    y = np.arange(len(lab))
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(lab) + 1))
    pre, post = c["Pre Yes %"].values[::-1], c["Post Yes %"].values[::-1]
    ax.barh(y + 0.2, pre, 0.4, color=PRE_C, label="Pre-test")
    ax.barh(y - 0.2, post, 0.4, color=POST_C, label="Post-test")
    for i, (a, p) in enumerate(zip(pre, post)):
        ax.text(a + 0.8, i + 0.2, f"{a:.0f}%", va="center", fontsize=6.5)
        ax.text(p + 0.8, i - 0.2, f"{p:.0f}%", va="center", fontsize=6.5)
    ax.set_yticks(y, lab)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% answering Yes", fontsize=8)
    ax.legend(fontsize=8, loc="lower right")
    _style(ax)
    return _png(fig)


def chart_change(b):
    c = b["comp"].sort_values("Yes % Change")
    lab = _labels(c)
    v = c["Yes % Change"].values
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(lab) + 1))
    ax.barh(lab, v, color=[RESP_C["Yes"] if x > 0 else RESP_C["No"] for x in v])
    for i, x in enumerate(v):
        ax.text(x + (0.4 if x >= 0 else -0.4), i, f"{x:+.1f}", va="center",
                ha="left" if x >= 0 else "right", fontsize=7)
    ax.axvline(0, color="#555", lw=0.8)
    ax.set_xlabel("Change in 'Yes' % (percentage points)", fontsize=8)
    _style(ax)
    return _png(fig)


def chart_themes(b):
    t = b["themes"]
    x = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.bar(x - 0.2, t["Pre Yes %"], 0.4, color=PRE_C, label="Pre-test")
    ax.bar(x + 0.2, t["Post Yes %"], 0.4, color=POST_C, label="Post-test")
    for i, (a, p) in enumerate(zip(t["Pre Yes %"], t["Post Yes %"])):
        ax.text(i - 0.2, a + 1, f"{a:.0f}%", ha="center", fontsize=7)
        ax.text(i + 0.2, p + 1, f"{p:.0f}%", ha="center", fontsize=7)
    ax.set_xticks(x, [s.replace(" & ", " &\n") for s in t["Theme"]], fontsize=7.5)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Average 'Yes' %", fontsize=8)
    ax.legend(fontsize=8)
    _style(ax)
    return _png(fig)


def chart_mix(b):
    fig, ax = plt.subplots(figsize=(7, 2.4))
    tests = ["Pre", "Post"]
    left = np.zeros(2)
    for r in A.RESPONSES:
        v = np.array([b["mix"][t][r] for t in tests])
        ax.barh(["Pre-test", "Post-test"], v, left=left, color=RESP_C[r], label=r)
        for i, val in enumerate(v):
            if val > 5:
                ax.text(left[i] + val / 2, i, f"{val:.1f}%", ha="center", va="center", color="white", fontsize=8)
        left += v
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.legend(ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=False)
    _style(ax)
    return _png(fig)


def chart_stacked(tbl):
    lab = _labels(tbl)
    fig, ax = plt.subplots(figsize=(9, 0.36 * len(lab) + 1))
    left = np.zeros(len(lab))
    for r in A.RESPONSES:
        v = tbl[f"{r} %"].values
        ax.barh(lab, v, left=left, color=RESP_C[r], label=r)
        for i, val in enumerate(v):
            if val >= 7:
                ax.text(left[i] + val / 2, i, f"{val:.0f}%", ha="center", va="center", color="white", fontsize=6.5)
        left += v
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.legend(ncol=3, fontsize=8, loc="lower center", bbox_to_anchor=(0.4, 1.0), frameon=False)
    _style(ax)
    return _png(fig)


def chart_students(b):
    m = b["matched"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.6), gridspec_kw={"width_ratios": [1.3, 1]})
    for _, r in m.iterrows():
        col = RESP_C["Yes"] if r["Change"] > 0 else RESP_C["No"] if r["Change"] < 0 else "#999"
        a1.plot([0, 1], [r["Score % (Pre)"], r["Score % (Post)"]], "-o", color=col, alpha=0.5, lw=0.8, ms=3)
    a1.plot([0, 1], [m["Score % (Pre)"].mean(), m["Score % (Post)"].mean()], "-o", color="black", lw=2.5,
            label="Mean")
    a1.set_xticks([0, 1], ["Pre-test", "Post-test"])
    a1.set_ylabel("Score %", fontsize=8)
    a1.set_title("Each student's score (green = improved)", fontsize=9)
    a1.legend(fontsize=8)
    _style(a1)
    counts = m["Direction"].value_counts().reindex(["Improved", "No change", "Declined"]).fillna(0)
    a2.pie(counts, labels=[f"{k}\n{int(v)}" for k, v in counts.items()], startangle=90,
           colors=[RESP_C["Yes"], "#BDBDBD", RESP_C["No"]], wedgeprops=dict(width=0.45),
           textprops=dict(fontsize=8))
    a2.set_title("Students by direction of change", fontsize=9)
    return _png(fig)


# ------------------------------------------------------------------ PDF
def build_pdf(b, o):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle, KeepTogether)

    buf = io.BytesIO()
    W = A4[0] - 3.6 * cm
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=o["title"])
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, textColor=colors.HexColor("#0D47A1"))
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#0D47A1"), spaceBefore=10)
    P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=10, leading=14)
    SM = ParagraphStyle("sm", parent=P, fontSize=8, leading=10)
    sec = set(o["sections"])

    def para(text):
        return [Paragraph(line.replace("&", "&amp;").replace("<", "&lt;"), P)
                for line in str(text).split("\n") if line.strip()]

    def img(png, max_h=21 * cm):
        im = Image(png)
        ratio = im.imageHeight / im.imageWidth
        w = W
        h = w * ratio
        if h > max_h:
            h, w = max_h, max_h / ratio
        im.drawWidth, im.drawHeight = w, h
        return im

    def table(df, col_w=None, font=8):
        data = [[Paragraph(f"<b>{c}</b>", SM) for c in df.columns]]
        for row in df.itertuples(index=False):
            data.append([Paragraph(_fmt(v), SM) for v in row])
        t = Table(data, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F2FD")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B0BEC5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ]))
        return t

    s = [Paragraph(o["title"], H1)]
    if o["subtitle"]:
        s.append(Paragraph(o["subtitle"], ParagraphStyle("st", parent=P, fontSize=13, alignment=1)))
    meta = " · ".join(x for x in [o["organisation"], o["prepared_by"] and f"Prepared by: {o['prepared_by']}",
                                  o["report_date"]] if x)
    if meta:
        s.append(Paragraph(meta, ParagraphStyle("meta", parent=SM, alignment=1, textColor=colors.grey)))
    s.append(Paragraph(f"Pre-test n = {b['n_pre']} · Post-test n = {b['n_post']} · {len(b['qcols'])} questions",
                       ParagraphStyle("n", parent=SM, alignment=1, textColor=colors.grey)))
    s.append(Spacer(1, 10))

    if "kpis" in sec:
        k = kpi_list(b)
        cells = [[Paragraph(f"<font size=16 color='#0D47A1'><b>{v}</b></font><br/><font size=8>{lab}</font>",
                            ParagraphStyle("k", parent=P, alignment=1, leading=18)) for lab, v in k]]
        kt = Table(cells, colWidths=[W / len(k)] * len(k))
        kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#90CAF9")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90CAF9")),
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F9FF")),
                                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        s += [kt, Spacer(1, 8)]
    if o["intro"].strip():
        s += [Paragraph("Introduction", H2)] + para(o["intro"])
    if o["findings"].strip():
        s += [Paragraph("Key findings", H2)] + para(o["findings"])
    if "pre_post" in sec:
        s += [KeepTogether([Paragraph(SECTIONS["pre_post"], H2), img(chart_pre_post(b))])]
    if "change" in sec:
        s += [KeepTogether([Paragraph(SECTIONS["change"], H2), img(chart_change(b))])]
    if "themes" in sec:
        s += [KeepTogether([Paragraph(SECTIONS["themes"], H2), img(chart_themes(b)),
                            table(b["themes"], [W * .46, W * .18, W * .18, W * .18])])]
    if "mix" in sec:
        s += [KeepTogether([Paragraph(SECTIONS["mix"], H2), img(chart_mix(b))])]
    for key, tb in (("pre", "pre_tbl"), ("post", "post_tbl")):
        if key in sec:
            s += [KeepTogether([Paragraph(SECTIONS[key], H2), img(chart_stacked(b[tb]))])]
    if "students" in sec and len(b["matched"]):
        block = [Paragraph(SECTIONS["students"], H2), img(chart_students(b))] + para(stats_text(b))
        s += [KeepTogether(block)]
        if o["show_names"]:
            m = b["matched"].sort_values("Change", ascending=False)[
                ["Name", "Gender", "Class", "Score % (Pre)", "Score % (Post)", "Change %"]]
            s += [Spacer(1, 6), table(m, [W * .34, W * .12, W * .1, W * .15, W * .15, W * .14])]
    if "groups" in sec:
        s += [KeepTogether([Paragraph(SECTIONS["groups"], H2), table(b["by_gender"]), Spacer(1, 6),
                            table(b["by_class"])])]
    if "table" in sec:
        t = summary_table_df(b)
        w = [W * .06, W * .28] + [W * .062] * 8 + [W * .164]
        s += [PageBreak(), Paragraph(SECTIONS["table"], H2), table(t, w)]
    if o["recommendations"].strip():
        s += [Paragraph("Recommendations", H2)] + para(o["recommendations"])

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.8 * cm, 1 * cm, o["title"])
        canvas.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ------------------------------------------------------------------ PowerPoint (native editable charts)
def build_pptx(b, o):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    NAVY = RGBColor(0x0D, 0x47, 0xA1)
    rgb = lambda h: RGBColor.from_string(h.lstrip("#"))
    sec = set(o["sections"])

    def textbox(slide, text, x, y, w, h, size=14, bold=False, color=None, align=None):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, line in enumerate(str(text).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size, p.font.bold = Pt(size), bold
            if color:
                p.font.color.rgb = color
            if align is not None:
                p.alignment = align
        return tb

    def new_slide(title):
        s = prs.slides.add_slide(blank)
        bar = s.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.12))
        bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
        textbox(s, title, 0.5, 0.3, 12.3, 0.7, 26, True, NAVY)
        textbox(s, o["title"] + (f" · {o['organisation']}" if o["organisation"] else ""),
                0.5, 7.0, 12.3, 0.35, 9, color=RGBColor(0x88, 0x88, 0x88))
        return s

    def style_chart(ch, legend=True, pct_axis=True, max_v=100):
        ch.font.size = Pt(10)
        ch.has_legend = legend
        if legend:
            ch.legend.position = XL_LEGEND_POSITION.TOP
            ch.legend.include_in_layout = False
        if pct_axis:
            ax = ch.value_axis
            ax.maximum_scale, ax.minimum_scale = max_v, 0
            ax.has_major_gridlines = False
            ax.tick_labels.font.size = Pt(9)

    def bar_chart(slide, cats, series, kind, x, y, w, h, colors_, labels=True, fmt='0"%"', stacked=False, **kw):
        cd = CategoryChartData()
        cd.categories = cats
        for name, vals in series:
            cd.add_series(name, [round(float(v), 1) for v in vals])
        gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
        ch = gf.chart
        for sr, col in zip(ch.plots[0].series, colors_):
            sr.format.fill.solid(); sr.format.fill.fore_color.rgb = rgb(col)
        pl = ch.plots[0]
        pl.gap_width = 60
        if stacked:
            pl.overlap = 100
        if labels:
            pl.has_data_labels = True
            dl = pl.data_labels
            dl.number_format, dl.number_format_is_linked = fmt, False
            dl.font.size = Pt(8)
            if stacked:
                dl.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        ch.category_axis.tick_labels.font.size = Pt(9)
        if kind in (XL_CHART_TYPE.BAR_CLUSTERED, XL_CHART_TYPE.BAR_STACKED_100, XL_CHART_TYPE.BAR_STACKED):
            ch.category_axis.reverse_order = True
        style_chart(ch, **kw)
        return ch

    def table_slide(title, df, col_w=None, font=10):
        s = new_slide(title)
        rows, cols = df.shape[0] + 1, df.shape[1]
        h = min(6.2, 0.3 * rows)
        t = s.shapes.add_table(rows, cols, Inches(0.5), Inches(1.1), Inches(12.3), Inches(h)).table
        for j, c in enumerate(df.columns):
            t.cell(0, j).text = str(c)
            if col_w:
                t.columns[j].width = Inches(col_w[j])
        for i, row in enumerate(df.itertuples(index=False), start=1):
            for j, v in enumerate(row):
                t.cell(i, j).text = _fmt(v)
        for i in range(rows):
            for j in range(cols):
                for p in t.cell(i, j).text_frame.paragraphs:
                    p.font.size = Pt(font)
        return s

    # title slide
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
    W_ = RGBColor(0xFF, 0xFF, 0xFF)
    textbox(s, o["title"], 0.8, 2.3, 11.7, 1.2, 40, True, W_)
    textbox(s, o["subtitle"], 0.8, 3.5, 11.7, 0.7, 22, False, W_)
    meta = "\n".join(x for x in [o["organisation"], o["prepared_by"] and f"Prepared by: {o['prepared_by']}",
                                 o["report_date"]] if x)
    textbox(s, meta, 0.8, 4.6, 11.7, 1.5, 14, False, RGBColor(0xBB, 0xDE, 0xFB))

    if "kpis" in sec or o["findings"].strip():
        s = new_slide("Key findings")
        k = kpi_list(b)
        if "kpis" in sec:
            w = 12.3 / len(k)
            for i, (lab, v) in enumerate(k):
                box = s.shapes.add_shape(5, Inches(0.5 + i * w + 0.08), Inches(1.2), Inches(w - 0.16), Inches(1.3))
                box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE3, 0xF2, 0xFD); box.line.fill.background()
                tf = box.text_frame
                tf.paragraphs[0].text = v
                tf.paragraphs[0].font.size, tf.paragraphs[0].font.bold = Pt(26), True
                tf.paragraphs[0].font.color.rgb = NAVY
                p = tf.add_paragraph(); p.text = lab; p.font.size = Pt(11)
                p.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        if o["findings"].strip():
            textbox(s, o["findings"], 0.6, 2.9, 12.1, 3.8, 15)
    if o["intro"].strip():
        s = new_slide("Introduction")
        textbox(s, o["intro"], 0.6, 1.2, 12.1, 5.5, 16)

    c = b["comp"]
    if "pre_post" in sec:
        s = new_slide(SECTIONS["pre_post"])
        bar_chart(s, _labels(c), [("Pre-test", c["Pre Yes %"]), ("Post-test", c["Post Yes %"])],
                  XL_CHART_TYPE.BAR_CLUSTERED, 0.4, 1.0, 12.5, 6.0, [PRE_C, POST_C])
    if "change" in sec:
        s = new_slide(SECTIONS["change"])
        cs = c.sort_values("Yes % Change", ascending=False)
        ch = bar_chart(s, _labels(cs), [("Change (pts)", cs["Yes % Change"])], XL_CHART_TYPE.BAR_CLUSTERED,
                       0.4, 1.0, 12.5, 6.0, [RESP_C["Yes"]], fmt='+0.0;-0.0', legend=False, pct_axis=False)
        for i, v in enumerate(cs["Yes % Change"]):
            if v < 0:
                pt = ch.plots[0].series[0].points[i]
                pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(RESP_C["No"])
    if "themes" in sec:
        t = b["themes"]
        s = new_slide(SECTIONS["themes"])
        bar_chart(s, list(t["Theme"]), [("Pre-test", t["Pre Yes %"]), ("Post-test", t["Post Yes %"])],
                  XL_CHART_TYPE.COLUMN_CLUSTERED, 0.4, 1.0, 8.2, 5.9, [PRE_C, POST_C])
        lines = "\n".join(f"{r.Theme}: {r.Change:+.1f} pts" for r in t.itertuples())
        textbox(s, "Change by theme\n" + lines, 8.9, 1.6, 4.1, 4.5, 13)
    if "mix" in sec:
        s = new_slide(SECTIONS["mix"])
        bar_chart(s, ["Pre-test", "Post-test"],
                  [(r, [b["mix"]["Pre"][r], b["mix"]["Post"][r]]) for r in A.RESPONSES],
                  XL_CHART_TYPE.BAR_STACKED_100, 0.8, 1.3, 11.7, 4.0, [RESP_C[r] for r in A.RESPONSES],
                  fmt='0.0"%"', stacked=True, pct_axis=False)
    for key, tb in (("pre", "pre_tbl"), ("post", "post_tbl")):
        if key in sec:
            tbl = b[tb]
            s = new_slide(SECTIONS[key])
            bar_chart(s, _labels(tbl), [(r, tbl[f"{r} %"]) for r in A.RESPONSES], XL_CHART_TYPE.BAR_STACKED_100,
                      0.4, 1.0, 12.5, 6.0, [RESP_C[r] for r in A.RESPONSES], stacked=True, pct_axis=False)
    if "students" in sec and len(b["matched"]):
        m = b["matched"]
        s = new_slide(SECTIONS["students"])
        counts = m["Direction"].value_counts().reindex(["Improved", "No change", "Declined"]).fillna(0)
        cd = CategoryChartData(); cd.categories = list(counts.index); cd.add_series("Students", list(counts.values))
        ch = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(0.5), Inches(1.1), Inches(5.2), Inches(5.0), cd).chart
        for i, col in enumerate([RESP_C["Yes"], "#BDBDBD", RESP_C["No"]]):
            p = ch.plots[0].series[0].points[i]; p.format.fill.solid(); p.format.fill.fore_color.rgb = rgb(col)
        ch.plots[0].has_data_labels = True
        ch.plots[0].data_labels.show_value = True
        ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
        bar_chart(s, ["Mean score %"], [("Pre-test", [m["Score % (Pre)"].mean()]),
                                        ("Post-test", [m["Score % (Post)"].mean()])],
                  XL_CHART_TYPE.COLUMN_CLUSTERED, 6.0, 1.1, 3.4, 4.0, [PRE_C, POST_C], fmt='0.0"%"')
        textbox(s, stats_text(b), 9.6, 1.3, 3.4, 5.0, 12)
        if o["show_names"]:
            mm = m.sort_values("Change", ascending=False)[
                ["Name", "Gender", "Class", "Score % (Pre)", "Score % (Post)", "Change %"]]
            for i in range(0, len(mm), 16):
                table_slide(f"Student scores ({i + 1}–{min(i + 16, len(mm))})", mm.iloc[i:i + 16],
                            [4.3, 1.6, 1.4, 1.7, 1.7, 1.6], 10)
    if "groups" in sec:
        s = new_slide(SECTIONS["groups"])
        for j, (df, by) in enumerate(((b["by_gender"], "Gender"), (b["by_class"], "Class"))):
            bar_chart(s, list(df[by].astype(str)), [("Pre-test", df["Pre mean score %"].fillna(0)),
                                                    ("Post-test", df["Post mean score %"].fillna(0))],
                      XL_CHART_TYPE.COLUMN_CLUSTERED, 0.4 + j * 6.3, 1.1, 6.1, 5.7, [PRE_C, POST_C], fmt='0.0"%"')
    if "table" in sec:
        t = summary_table_df(b)
        w = [0.6, 3.5] + [0.82] * 9
        table_slide(SECTIONS["table"] + " (1/2)", t.iloc[:9], w, 10)
        table_slide(SECTIONS["table"] + " (2/2)", t.iloc[9:], w, 10)
    if o["recommendations"].strip():
        s = new_slide("Recommendations")
        textbox(s, o["recommendations"], 0.6, 1.2, 12.1, 5.5, 16)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ Excel (interactive)
def build_excel(b, o):
    """Raw data sheets + formula-driven summary + native Excel charts.
    Editing an answer in a raw sheet recalculates every table and chart."""
    buf = io.BytesIO()
    wb_opts = {"in_memory": True}
    pre, post, q = b["pre"], b["post"], b["questions"]
    qcols = b["qcols"]
    n_q = len(qcols)
    with pd.ExcelWriter(buf, engine="xlsxwriter", engine_kwargs={"options": wb_opts}) as xw:
        wb = xw.book
        db = wb.add_worksheet("Dashboard")   # first tab
        xw.sheets["Dashboard"] = db
        F = {
            "title": wb.add_format({"bold": True, "font_size": 18, "font_color": "#0D47A1"}),
            "sub": wb.add_format({"italic": True, "font_color": "#555555"}),
            "h": wb.add_format({"bold": True, "bg_color": "#E3F2FD", "border": 1, "text_wrap": True,
                                "valign": "vcenter", "align": "center"}),
            "txt": wb.add_format({"border": 1, "text_wrap": True, "valign": "vcenter"}),
            "int": wb.add_format({"border": 1, "align": "center"}),
            "pct": wb.add_format({"border": 1, "num_format": "0.0%", "align": "center"}),
            "chg": wb.add_format({"border": 1, "num_format": "+0.0%;-0.0%;0.0%", "align": "center", "bold": True}),
            "kv": wb.add_format({"bold": True, "font_size": 20, "font_color": "#0D47A1", "align": "center",
                                 "bg_color": "#F5F9FF", "border": 1, "num_format": "0.0%"}),
            "kvn": wb.add_format({"bold": True, "font_size": 20, "font_color": "#0D47A1", "align": "center",
                                  "bg_color": "#F5F9FF", "border": 1}),
            "kvc": wb.add_format({"bold": True, "font_size": 20, "font_color": "#2E7D32", "align": "center",
                                  "bg_color": "#F5F9FF", "border": 1, "num_format": "+0.0%;-0.0%"}),
            "kl": wb.add_format({"align": "center", "font_color": "#555555", "bg_color": "#F5F9FF", "border": 1,
                                 "text_wrap": True}),
            "wrap": wb.add_format({"text_wrap": True, "valign": "top"}),
        }

        # ---------- raw data sheets (Excel tables with filters)
        def raw_sheet(df, name):
            cols = ["Serial No.", "Name", "Gender", "Class"] + qcols
            d = df[cols].copy()
            if not o["show_names"]:
                d["Name"] = [f"Student {i + 1}" for i in range(len(d))]
            d.to_excel(xw, sheet_name=name, index=False, startrow=1, header=False)
            ws = xw.sheets[name]
            hdr = ["Serial No.", "Name", "Gender", "Class"] + list(q["Q#"])
            ws.add_table(0, 0, len(d), len(cols) - 1,
                         {"columns": [{"header": h} for h in hdr], "style": "Table Style Medium 2",
                          "name": name.replace("-", "").replace(" ", "_")})
            ws.data_validation(1, 4, max(len(d), 1) + 200, 3 + n_q,
                               {"validate": "list", "source": A.RESPONSES})
            ws.conditional_format(1, 4, len(d) + 200, 3 + n_q,
                                  {"type": "cell", "criteria": "==", "value": '"Yes"',
                                   "format": wb.add_format({"bg_color": "#C8E6C9"})})
            ws.conditional_format(1, 4, len(d) + 200, 3 + n_q,
                                  {"type": "cell", "criteria": "==", "value": '"No"',
                                   "format": wb.add_format({"bg_color": "#FFCDD2"})})
            ws.conditional_format(1, 4, len(d) + 200, 3 + n_q,
                                  {"type": "cell", "criteria": "==", "value": '"Not Sure"',
                                   "format": wb.add_format({"bg_color": "#FFF9C4"})})
            ws.set_column(0, 0, 9); ws.set_column(1, 1, 26); ws.set_column(2, 3, 10)
            ws.set_column(4, 3 + n_q, 9)
            ws.freeze_panes(1, 2)
            return len(d)

        from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell
        n_pre = raw_sheet(pre, "Pre-test data")
        n_post = raw_sheet(post, "Post-test data")
        last = 1 + max(n_pre, n_post) + 200   # allow extra rows to be added

        # ---------- Summary sheet (formulas)
        ws = wb.add_worksheet("Summary")
        hdr = ["Q#", "Question", "Theme", "Pre Yes", "Pre Not Sure", "Pre No", "Pre Total", "Pre Yes %",
               "Post Yes", "Post Not Sure", "Post No", "Post Total", "Post Yes %", "Yes % Change"]
        ws.write_row(0, 0, hdr, F["h"])
        comp = b["comp"]
        for i, r in enumerate(q.itertuples()):
            row = i + 1
            col = xl_col_to_name(4 + i)
            ws.write(row, 0, q["Q#"].iloc[i], F["int"])
            ws.write(row, 1, r.Short, F["txt"])
            ws.write(row, 2, r.Theme, F["txt"])
            for k, (sheet, base) in enumerate((("Pre-test data", 3), ("Post-test data", 8))):
                rng = f"'{sheet}'!${col}$2:${col}${last}"
                pfx = "Pre" if k == 0 else "Post"
                for j, resp in enumerate(A.RESPONSES):
                    ws.write_formula(row, base + j, f'=COUNTIF({rng},"{resp}")', F["int"],
                                     int(comp.iloc[i][f"{pfx} {resp}"]))
                tot_cell = xl_rowcol_to_cell(row, base + 3)
                ws.write_formula(row, base + 3, f"=SUM({xl_rowcol_to_cell(row, base)}:{xl_rowcol_to_cell(row, base + 2)})",
                                 F["int"], int(comp.iloc[i][f"{pfx} Total"]))
                ws.write_formula(row, base + 4, f"=IF({tot_cell}>0,{xl_rowcol_to_cell(row, base)}/{tot_cell},0)",
                                 F["pct"], comp.iloc[i][f"{pfx} Yes %"] / 100)
            ws.write_formula(row, 13, f"={xl_rowcol_to_cell(row, 12)}-{xl_rowcol_to_cell(row, 7)}", F["chg"],
                             comp.iloc[i]["Yes % Change"] / 100)
        avg_row = n_q + 1
        avg_vals = comp[["Pre Yes", "Pre Not Sure", "Pre No", "Pre Total", "Pre Yes %", "Post Yes",
                         "Post Not Sure", "Post No", "Post Total", "Post Yes %", "Yes % Change"]].mean().values
        ws.write(avg_row, 0, "AVG", F["h"]); ws.write(avg_row, 1, "Overall mean", F["h"]); ws.write(avg_row, 2, "", F["h"])
        for j in range(3, 14):
            c = xl_col_to_name(j)
            fmt = F["pct"] if j in (7, 12) else F["chg"] if j == 13 else wb.add_format(
                {"border": 1, "align": "center", "num_format": "0.0", "bold": True})
            v = float(avg_vals[j - 3]) / (100 if j in (7, 12, 13) else 1)
            ws.write_formula(avg_row, j, f"=AVERAGE({c}2:{c}{n_q + 1})", fmt, v)
        ws.conditional_format(1, 13, n_q, 13, {"type": "3_color_scale", "min_color": "#F8696B",
                                               "mid_color": "#FFEB84", "max_color": "#63BE7B"})
        ws.conditional_format(1, 7, n_q, 7, {"type": "data_bar", "bar_color": "#90A4AE", "bar_solid": True,
                                             "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})
        ws.conditional_format(1, 12, n_q, 12, {"type": "data_bar", "bar_color": "#64B5F6", "bar_solid": True,
                                               "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})
        ws.autofilter(0, 0, n_q, 13)
        ws.set_column(0, 0, 6); ws.set_column(1, 1, 40); ws.set_column(2, 2, 24); ws.set_column(3, 13, 10)
        ws.set_row(0, 32)
        ws.freeze_panes(1, 2)

        # Theme table (formulas)
        tr = n_q + 4
        ws.write_row(tr, 1, ["Theme", "", "", "", "", "", "Pre Yes %", "", "", "", "", "Post Yes %", "Change"], F["h"])
        themes = list(dict.fromkeys(q["Theme"]))
        for i, th in enumerate(themes):
            r = tr + 1 + i
            ws.write(r, 1, th, F["txt"])
            pre_v = b["themes"].set_index("Theme").loc[th]
            ws.write_formula(r, 7, f'=AVERAGEIF($C$2:$C${n_q + 1},$B{r + 1},H$2:H${n_q + 1})', F["pct"],
                             pre_v["Pre Yes %"] / 100)
            ws.write_formula(r, 12, f'=AVERAGEIF($C$2:$C${n_q + 1},$B{r + 1},M$2:M${n_q + 1})', F["pct"],
                             pre_v["Post Yes %"] / 100)
            ws.write_formula(r, 13, f"=M{r + 1}-H{r + 1}", F["chg"], pre_v["Change"] / 100)
        th_first, th_last = tr + 1, tr + len(themes)

        # Overall mix (formulas)
        mr = th_last + 3
        ws.write_row(mr, 1, ["Overall response mix", "Yes", "Not Sure", "No"], F["h"])
        for k, (lab, base) in enumerate((("Pre-test", 3), ("Post-test", 8))):
            r = mr + 1 + k
            ws.write(r, 1, lab, F["txt"])
            tot = f"SUM({xl_col_to_name(base + 3)}2:{xl_col_to_name(base + 3)}{n_q + 1})"
            for j in range(3):
                cc = xl_col_to_name(base + j)
                ws.write_formula(r, 2 + j, f"=SUM({cc}2:{cc}{n_q + 1})/{tot}", F["pct"],
                                 b["mix"]["Pre" if k == 0 else "Post"][A.RESPONSES[j]] / 100)

        # ---------- Dashboard sheet with native charts
        db.activate()
        db.hide_gridlines(2)
        db.set_landscape(); db.fit_to_pages(1, 0); db.set_paper(9)
        db.set_column(0, 0, 2); db.set_column(1, 12, 13)
        db.write(1, 1, o["title"], F["title"])
        meta = " · ".join(x for x in [o["subtitle"], o["organisation"],
                                      o["prepared_by"] and f"Prepared by: {o['prepared_by']}", o["report_date"]] if x)
        db.write(2, 1, meta, F["sub"])
        # KPI tiles linked to Summary
        kpis = [("Pre-test avg 'Yes'", f"=Summary!H{avg_row + 1}", F["kv"], avg_vals[4] / 100),
                ("Post-test avg 'Yes'", f"=Summary!M{avg_row + 1}", F["kv"], avg_vals[9] / 100),
                ("Change", f"=Summary!N{avg_row + 1}", F["kvc"], avg_vals[10] / 100),
                ("Questions improved", f'=COUNTIF(Summary!N2:N{n_q + 1},">0")&" / {n_q}"', F["kvn"],
                 f"{(comp['Yes % Change'] > 0).sum()} / {n_q}"),
                ("Students (pre / post)", f"=COUNTA('Pre-test data'!B2:B{last})&\" / \"&COUNTA('Post-test data'!B2:B{last})",
                 F["kvn"], f"{n_pre} / {n_post}")]
        for i, (lab, f, fmt, val) in enumerate(kpis):
            c0 = 1 + i * 2
            db.merge_range(4, c0, 4, c0 + 1, "", fmt)
            db.write_formula(4, c0, f, fmt, val)
            db.merge_range(5, c0, 5, c0 + 1, lab, F["kl"])
        db.set_row(4, 36)
        if o["findings"].strip():
            db.merge_range(7, 1, 10, 10, o["findings"], F["wrap"])

        def series(chart, name, col, color, cats=None):
            chart.add_series({
                "name": name,
                "categories": cats or ["Summary", 1, 1, n_q, 1],
                "values": ["Summary", 1, col, n_q, col],
                "fill": {"color": color}, "gap": 60,
                "data_labels": {"value": True, "num_format": "0%", "font": {"size": 7}},
            })

        ch = wb.add_chart({"type": "bar"})
        series(ch, "Pre-test", 7, PRE_C); series(ch, "Post-test", 12, POST_C)
        ch.set_title({"name": "'Yes' % by question: Pre vs Post", "name_font": {"size": 12}})
        ch.set_x_axis({"min": 0, "max": 1, "num_format": "0%", "major_gridlines": {"visible": False}})
        ch.set_y_axis({"reverse": True, "num_font": {"size": 8}})
        ch.set_legend({"position": "top"})
        ch.set_size({"width": 760, "height": 620})
        db.insert_chart(12, 1, ch)

        ch2 = wb.add_chart({"type": "bar"})
        ch2.add_series({"name": "Change", "categories": ["Summary", 1, 1, n_q, 1],
                        "values": ["Summary", 1, 13, n_q, 13], "fill": {"color": RESP_C["Yes"]},
                        "invert_if_negative": True, "invert_if_negative_color": RESP_C["No"], "gap": 50,
                        "data_labels": {"value": True, "num_format": "+0.0%;-0.0%", "font": {"size": 7}}})
        ch2.set_title({"name": "Change in 'Yes' % (Post − Pre)", "name_font": {"size": 12}})
        ch2.set_x_axis({"num_format": "0%", "major_gridlines": {"visible": False}})
        ch2.set_y_axis({"reverse": True, "num_font": {"size": 8}})
        ch2.set_legend({"none": True})
        ch2.set_size({"width": 560, "height": 620})
        db.insert_chart(12, 8, ch2, {"x_offset": 20})

        ch3 = wb.add_chart({"type": "column"})
        for name, col, colr in (("Pre-test", 7, PRE_C), ("Post-test", 12, POST_C)):
            ch3.add_series({"name": name, "categories": ["Summary", th_first, 1, th_last, 1],
                            "values": ["Summary", th_first, col, th_last, col], "fill": {"color": colr},
                            "data_labels": {"value": True, "num_format": "0%", "font": {"size": 8}}})
        ch3.set_title({"name": "Average 'Yes' % by theme", "name_font": {"size": 12}})
        ch3.set_y_axis({"min": 0, "max": 1, "num_format": "0%", "major_gridlines": {"visible": False}})
        ch3.set_legend({"position": "top"})
        ch3.set_size({"width": 760, "height": 360})
        db.insert_chart(44, 1, ch3)

        ch4 = wb.add_chart({"type": "bar", "subtype": "percent_stacked"})
        for j, resp in enumerate(A.RESPONSES):
            ch4.add_series({"name": resp, "categories": ["Summary", mr + 1, 1, mr + 2, 1],
                            "values": ["Summary", mr + 1, 2 + j, mr + 2, 2 + j], "fill": {"color": RESP_C[resp]},
                            "gap": 50, "data_labels": {"value": True, "num_format": "0.0%",
                                                       "font": {"size": 9, "color": "white"}}})
        ch4.set_title({"name": "Overall response mix", "name_font": {"size": 12}})
        ch4.set_y_axis({"reverse": True})
        ch4.set_legend({"position": "bottom"})
        ch4.set_size({"width": 560, "height": 360})
        db.insert_chart(44, 8, ch4, {"x_offset": 20})
        db.write(64, 1, "Tip: edit answers in the 'Pre-test data' / 'Post-test data' sheets (drop-down lists) — "
                        "the Summary tables, KPI tiles and all charts update automatically. Use the filter "
                        "arrows on the data sheets to explore.", F["sub"])

        # ---------- Pre / post analysis sheets with stacked charts
        for key, tb, sheet in (("pre", "pre_tbl", "Pre-test analysis"), ("post", "post_tbl", "Post-test analysis")):
            t = b[tb]
            w2 = wb.add_worksheet(sheet)
            w2.write_row(0, 0, ["Q#", "Question", "Yes %", "Not Sure %", "No %"], F["h"])
            base = 3 if key == "pre" else 8
            for i, r in enumerate(t.itertuples()):
                w2.write(i + 1, 0, r._1, F["int"])
                w2.write(i + 1, 1, r.Question, F["txt"])
                tot = xl_rowcol_to_cell(i + 1, base + 3)
                for j, resp in enumerate(A.RESPONSES):
                    w2.write_formula(i + 1, 2 + j, f"=IF(Summary!{tot}>0,Summary!{xl_rowcol_to_cell(i + 1, base + j)}"
                                                   f"/Summary!{tot},0)", F["pct"], t.iloc[i][f"{resp} %"] / 100)
            w2.set_column(0, 0, 6); w2.set_column(1, 1, 40); w2.set_column(2, 4, 11)
            c5 = wb.add_chart({"type": "bar", "subtype": "percent_stacked"})
            for j, resp in enumerate(A.RESPONSES):
                c5.add_series({"name": resp, "categories": [sheet, 1, 1, n_q, 1],
                               "values": [sheet, 1, 2 + j, n_q, 2 + j], "fill": {"color": RESP_C[resp]},
                               "gap": 40, "data_labels": {"value": True, "num_format": "0%",
                                                          "font": {"size": 7, "color": "white"}}})
            c5.set_title({"name": f"{sheet.split()[0]}: responses by question", "name_font": {"size": 12}})
            c5.set_y_axis({"reverse": True, "num_font": {"size": 8}})
            c5.set_legend({"position": "top"})
            c5.set_size({"width": 820, "height": 600})
            w2.insert_chart(0, 6, c5)

        # ---------- Student progress (formulas from raw data)
        m = b["matched"]
        if len(m):
            sp = wb.add_worksheet("Student progress")
            hdr = ["Name", "Gender", "Class", "Score (Pre)", "Score (Post)", "Change", "Direction"]
            mm = m.sort_values("Change", ascending=False).reset_index(drop=True)
            if not o["show_names"]:
                mm["Name"] = [f"Student {i + 1}" for i in range(len(mm))]
            for i, r in mm.iterrows():
                sp.write(i + 1, 0, r["Name"]); sp.write(i + 1, 1, r["Gender"]); sp.write(i + 1, 2, r["Class"])
                sp.write_number(i + 1, 3, r["Score % (Pre)"] / 100)
                sp.write_number(i + 1, 4, r["Score % (Post)"] / 100)
                sp.write_formula(i + 1, 5, f"=E{i + 2}-D{i + 2}", None, r["Change %"] / 100)
                sp.write_formula(i + 1, 6, f'=IF(F{i + 2}>0,"Improved",IF(F{i + 2}<0,"Declined","No change"))',
                                 None, r["Direction"])
            sp.add_table(0, 0, len(mm), 6, {"columns": [{"header": h} for h in hdr],
                                            "style": "Table Style Medium 9", "name": "Progress"})
            pf = wb.add_format({"num_format": "0.0%"})
            sp.set_column(0, 0, 26); sp.set_column(1, 2, 10); sp.set_column(3, 4, 12, pf)
            sp.set_column(5, 5, 10, wb.add_format({"num_format": "+0.0%;-0.0%;0.0%"})); sp.set_column(6, 6, 12)
            sp.conditional_format(1, 5, len(mm), 5, {"type": "data_bar", "bar_color": "#63BE7B",
                                                     "bar_negative_color": "#F8696B", "bar_solid": True})
            s = b["stats"]
            sp.write(1, 8, "Direction", F["h"]); sp.write(1, 9, "Students", F["h"])
            for i, d in enumerate(["Improved", "No change", "Declined"]):
                sp.write(2 + i, 8, d, F["txt"])
                sp.write_formula(2 + i, 9, f'=COUNTIF(G2:G{len(mm) + 1},"{d}")', F["int"],
                                 int((mm["Direction"] == d).sum()))
            pie = wb.add_chart({"type": "doughnut"})
            pie.add_series({"name": "Students", "categories": ["Student progress", 2, 8, 4, 8],
                            "values": ["Student progress", 2, 9, 4, 9], "data_labels": {"value": True},
                            "points": [{"fill": {"color": RESP_C["Yes"]}}, {"fill": {"color": "#BDBDBD"}},
                                       {"fill": {"color": RESP_C["No"]}}]})
            pie.set_title({"name": "Students by direction of change", "name_font": {"size": 12}})
            pie.set_size({"width": 420, "height": 300})
            sp.insert_chart(6, 8, pie)
            if s:
                sp.write(22, 8, stats_text(b), F["sub"])
        # notes sheet
        nt = wb.add_worksheet("Notes")
        nt.set_column(0, 0, 110, F["wrap"])
        rows = [("Title", o["title"]), ("Subtitle", o["subtitle"]), ("Organisation", o["organisation"]),
                ("Prepared by", o["prepared_by"]), ("Date", o["report_date"]), ("Introduction", o["intro"]),
                ("Key findings", o["findings"]), ("Recommendations", o["recommendations"]),
                ("Method", "Scores: Yes = 2, Not Sure = 1, No = 0. 'Yes %' = Yes ÷ answered. "
                           "Change = Post Yes % − Pre Yes % (percentage points).")]
        rr = 0
        for k, v in rows:
            if v:
                nt.write(rr, 0, k, wb.add_format({"bold": True, "font_color": "#0D47A1"}))
                nt.write(rr + 1, 0, v)
                rr += 3
    return buf.getvalue()


# ------------------------------------------------------------------ Word (.docx)
def build_docx(b, o, font="Times New Roman", body_pt=12):
    """Word report: body text Times New Roman 12 pt regular, headings bold (same font, black)."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec_ = doc.sections[0]
    sec_.page_width, sec_.page_height = Cm(21), Cm(29.7)        # A4
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec_, side, Cm(2.5))
    text_w = Cm(16)
    BLACK = RGBColor(0, 0, 0)

    def set_font(style_or_run, size=None, bold=None):
        f = style_or_run.font
        f.name = font
        if size:
            f.size = Pt(size)
        if bold is not None:
            f.bold = bold
        f.color.rgb = BLACK
        el = style_or_run.element
        rpr = el.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts"); rpr.insert(0, rfonts)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            rfonts.attrib.pop(qn(a), None)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(a), font)

    st = doc.styles
    set_font(st["Normal"], body_pt, False)
    st["Normal"].paragraph_format.space_after = Pt(6)
    st["Normal"].paragraph_format.line_spacing = 1.15
    for name, size in (("Title", 18), ("Heading 1", 14), ("Heading 2", 12)):
        set_font(st[name], size, True)
        st[name].font.italic = False
        pf = st[name].paragraph_format
        pf.space_before, pf.space_after, pf.keep_with_next = Pt(12), Pt(6), True
    # remove the Title style's bottom border line
    tp = st["Title"].element.pPr
    if tp is not None:
        for bd in tp.findall(qn("w:pBdr")):
            tp.remove(bd)
    sec = set(o["sections"])

    def para(text, bold=False, align=None, size=None, italic=False):
        for line in str(text).split("\n"):
            if line.strip():
                p = doc.add_paragraph()
                r = p.add_run(line.strip())
                r.bold, r.italic = bold, italic
                if size:
                    r.font.size = Pt(size)
                if align is not None:
                    p.alignment = align
                p.paragraph_format.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY

    def bullets(text):
        for line in str(text).split("\n"):
            if line.strip():
                doc.add_paragraph(line.strip().lstrip("-•* ").strip(), style="List Bullet")

    def picture(png, width=text_w):
        doc.add_picture(png, width=width)
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    def shade(cell, hex_):
        tcpr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_)
        tcpr.append(sh)

    def table(df, widths_cm=None, size=10):
        t = doc.add_table(rows=1, cols=len(df.columns))
        t.style = "Table Grid"
        t.autofit = False
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, c in enumerate(df.columns):
            cell = t.rows[0].cells[j]
            cell.text = ""
            r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(size)
            shade(cell, "D9E2F3")
        for row in df.itertuples(index=False):
            cells = t.add_row().cells
            for j, v in enumerate(row):
                txt = _fmt(v)
                r = cells[j].paragraphs[0].add_run(txt); r.font.size = Pt(size)
        # header repeats on each page
        trpr = t.rows[0]._tr.get_or_add_trPr()
        h = OxmlElement("w:tblHeader"); h.set(qn("w:val"), "true"); trpr.append(h)
        for row in t.rows:
            for j, cell in enumerate(row.cells):
                cell.paragraphs[0].paragraph_format.space_after = Pt(0)
                cell.paragraphs[0].paragraph_format.line_spacing = 1.0
                if widths_cm:
                    cell.width = Cm(widths_cm[j])
        if widths_cm:
            for j, col in enumerate(t.columns):
                col.width = Cm(widths_cm[j])
            grid = t._tbl.tblGrid
            for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
                gc.set(qn("w:w"), str(int(widths_cm[j] * 567)))
        doc.add_paragraph()
        return t

    # ---- title block
    p = doc.add_paragraph(o["title"], style="Title"); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if o["subtitle"]:
        para(o["subtitle"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    for line in [o["organisation"], o["prepared_by"] and f"Prepared by: {o['prepared_by']}", o["report_date"]]:
        if line:
            para(line, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(f"Pre-test n = {b['n_pre']} | Post-test n = {b['n_post']} | {len(b['qcols'])} questions",
         align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)

    if "kpis" in sec:
        doc.add_heading("Key Figures", level=1)
        k = kpi_list(b)
        table(pd.DataFrame([[v for _, v in k]], columns=[lab for lab, _ in k]), [16 / len(k)] * len(k), 11)
    if o["intro"].strip():
        doc.add_heading("Introduction", level=1); para(o["intro"])
    if o["findings"].strip():
        doc.add_heading("Key Findings", level=1); para(o["findings"])

    doc.add_heading("Results", level=1)
    if "pre_post" in sec:
        doc.add_heading(SECTIONS["pre_post"], level=2); picture(chart_pre_post(b))
    if "change" in sec:
        doc.add_heading(SECTIONS["change"], level=2); picture(chart_change(b))
    if "themes" in sec:
        doc.add_heading(SECTIONS["themes"], level=2); picture(chart_themes(b))
        table(b["themes"], [7, 3, 3, 3], 11)
    if "mix" in sec:
        doc.add_heading(SECTIONS["mix"], level=2); picture(chart_mix(b), Cm(13))
    for key, tb in (("pre", "pre_tbl"), ("post", "post_tbl")):
        if key in sec:
            doc.add_heading(SECTIONS[key], level=2); picture(chart_stacked(b[tb]))
    if "students" in sec and len(b["matched"]):
        doc.add_heading(SECTIONS["students"], level=2); picture(chart_students(b)); para(stats_text(b))
        if o["show_names"]:
            m = b["matched"].sort_values("Change", ascending=False)[
                ["Name", "Gender", "Class", "Score % (Pre)", "Score % (Post)", "Change %"]]
            table(m, [5.2, 2, 1.6, 2.4, 2.4, 2.4], 10)
    if "groups" in sec:
        doc.add_heading(SECTIONS["groups"], level=2)
        table(b["by_gender"], None, 11); table(b["by_class"], None, 11)
    if "table" in sec:
        doc.add_heading(SECTIONS["table"], level=2)
        table(summary_table_df(b), [1.2, 4.4] + [1.15] * 8 + [1.2], 9)
    if o["recommendations"].strip():
        doc.add_heading("Recommendations", level=1); bullets(o["recommendations"])
    doc.add_heading("Method", level=1)
    para("Responses were scored Yes = 2, Not Sure = 1 and No = 0. 'Yes %' is the share of students answering "
         "Yes to each question. Change is Post-test Yes % minus Pre-test Yes %, in percentage points. Students "
         "were matched by name for the paired comparison (paired t-test and Wilcoxon signed-rank test).")

    # footer with page number
    fp = sec_.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run(f"{o['title']} — Page "); r.font.size = Pt(9); r.font.name = font
    r2 = fp.add_run(); r2.font.size = Pt(9); r2.font.name = font
    for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt
        r2._r.append(e)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
