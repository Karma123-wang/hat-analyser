# HAT Pre/Post Test Analyser (Streamlit)

Analyses the HAT questionnaire workbook (sheets `pre-test` and `post-test`).

Tabs: Summary (pre vs post), Pre-test, Post-test, Student progress (matched by name, paired t-test + Wilcoxon), Download (Excel/CSV).

## Run locally
    pip install -r requirements.txt
    streamlit run app.py

## Deploy on Streamlit Community Cloud
1. Push this folder (app.py, analysis.py, requirements.txt, data/) to a GitHub repo.
2. On share.streamlit.io → New app → pick the repo, branch, and `app.py` → Deploy.

The file in `data/` loads by default; users can upload a new workbook from the sidebar.
Remove `data/` before pushing if the repo is public (it contains student names).
