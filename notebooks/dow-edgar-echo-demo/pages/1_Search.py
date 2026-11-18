"""Keyword search page. Streamlit shows it in the sidebar next to the main dashboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, so `ingestion` imports

import duckdb
import streamlit as st

from dow.config import DB_PATH
from ingestion.search import highlight, search

st.set_page_config(page_title="Search records", layout="wide")
st.title("Search the records")
st.caption("Searches the 10-K text and the EPA facility records we stored. Words match whole words. "
           'Use "quotes" for an exact phrase. Every result links to its source.')

try:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("SELECT 1 FROM chunk LIMIT 1")
except Exception:
    st.info("No searchable text yet. Run: python -m ingestion.build_db --db "
            f"{DB_PATH} --with-10k  (close this app first, then restart it).")
    st.stop()

types = {"Everything": None, "10-K filing text": "10-K", "EPA facility records": "echo_facility_fact"}
q = st.text_input("Search", placeholder='e.g. wastewater "legal proceedings" penalty')
c1, c2, c3 = st.columns(3)
kind = types[c1.selectbox("Search in", list(types))]
k = c2.slider("Results", 5, 30, 10)
match_all = c3.checkbox("Must contain every term")

if q.strip():
    results = search(con, q, k, kind, match_all)
    if not results:
        st.warning("No matches. Try fewer or simpler words.")
    st.write(f"{len(results)} result(s)")
    for r in results:
        with st.container(border=True):
            st.markdown(f"**{r['title']}**  ·  `{r['doc_type']}`  ·  "
                        f"{r['matched']}/{len(r['terms'])} terms")
            st.markdown(highlight(r["snippet"], r["terms"]))
            st.markdown(f"[Open source]({r['source_url']})")
else:
    st.write("Type something above to search.")
