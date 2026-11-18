"""Ask a question in plain English. Answers come only from the stored records, with citations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, so `ingestion` imports

import duckdb
import streamlit as st

from dow.config import DB_PATH
from ingestion.ask import ask
from ingestion.llm import CHAT_MODEL, LLMUnavailable
from ingestion.search import highlight

st.set_page_config(page_title="Ask the records", layout="wide")
st.title("Ask the records")
st.caption(f"A small local model ({CHAT_MODEL}) reads the most relevant stored records and answers "
           "using only those, with numbered sources. It can be wrong, so check the sources. It reads "
           "a few passages at a time, so it cannot total or rank everything: use the dashboard "
           "tables for totals and rankings. Penalties are agency-reported and may be alleged or settled.")

try:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    n_vec = con.execute("SELECT count(*) FROM chunk WHERE embedding IS NOT NULL").fetchone()[0]
except Exception:
    st.info(f"No searchable text yet. Run: python -m ingestion.build_db --db {DB_PATH}")
    st.stop()
if n_vec == 0:
    st.info(f"No vectors yet, so search by meaning is off. Run: python -m ingestion.embed --db {DB_PATH} "
            "(close this app first). Until then you can still use the Search page.")
    st.stop()

q = st.text_input("Your question", placeholder="What penalties are recorded for the Texas facility?")
if st.button("Ask", type="primary") and q.strip():
    try:
        with st.spinner("Searching the records and writing an answer (can take a minute on CPU)..."):
            res = ask(con, q)
    except LLMUnavailable as e:
        st.error(str(e))
        st.stop()
    st.markdown(highlight(res["answer"], []))
    for w in res["warnings"]:
        st.warning(w)
    if res["sources"]:
        st.subheader("Sources")
        for i, s in enumerate(res["sources"], 1):
            with st.expander(f"[{i}] {s['title']}  ·  {s['doc_type']}"):
                st.markdown(highlight(s["text"], []))
                st.markdown(f"[Open source]({s['source_url']})")
