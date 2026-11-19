"""Search stored records and ask questions about retrieved passages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, so `ingestion` imports

import duckdb
import streamlit as st

from dow.config import DB_PATH
from ingestion.ask import answer_sources
from ingestion.llm import CHAT_MODEL, EMBED_MODEL, LLMUnavailable
from ingestion.retrieve import semantic_search
from ingestion.search import highlight

st.set_page_config(page_title="Search records", layout="wide")
st.title("Search the records")
st.caption("Search the stored 10-K by meaning. Every result links to its source.")

try:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("SELECT 1 FROM chunk LIMIT 1")
except Exception:
    st.info("No searchable text yet. Run: python -m ingestion.build_db --db "
            f"{DB_PATH} --with-10k  (close this app first, then restart it).")
    st.stop()

q = st.text_input("Search", placeholder="e.g. wastewater treatment requirements")
k = st.slider("Results", 5, 30, 10)

search_key = ("semantic_10k", q.strip(), k)
if st.session_state.get("search_key") == search_key:
    results = st.session_state.get("search_results", [])
else:
    results = []
if q.strip() and st.session_state.get("search_key") != search_key:
    if con.execute(
        "SELECT count(*) FROM chunk c JOIN document d ON c.doc_id = d.doc_id "
        "WHERE c.embedding IS NOT NULL AND c.embedding_model = ? AND d.doc_type = ?",
        [EMBED_MODEL, "10-K"],
    ).fetchone()[0] == 0:
        st.info(f"No 10-K vectors for the current embedding model. Run: python -m ingestion.embed --db {DB_PATH}")
    else:
        try:
            with st.spinner("Searching the 10-K by meaning..."):
                results = semantic_search(con, q, k=k, doc_type="10-K")
        except LLMUnavailable as e:
            st.error(str(e))
            st.stop()

    st.session_state["search_key"] = search_key
    st.session_state["search_results"] = results

if q.strip():
    if not results:
        st.warning("No matches. Try a different search.")
    else:
        st.write(f"{len(results)} result(s)")
        for r in results:
            with st.container(border=True):
                st.markdown(f"**{r['title']}**  ·  `{r['doc_type']}`")
                excerpt = r.get("snippet", r["text"][:320])
                terms = r.get("terms", [])
                st.markdown(highlight(excerpt, terms))
                st.markdown(f"[Open source]({r['source_url']})")

if results:
    st.subheader("Ask about these results")
    question = st.text_input(
        "Question for the AI",
        placeholder="What do these sections say about wastewater treatment?",
        key="semantic_search_question",
    )
    if st.button("Ask about results", type="primary") and question.strip():
        try:
            with st.spinner(f"{CHAT_MODEL} is answering from the passages above..."):
                answer = answer_sources(question, results)
        except LLMUnavailable as e:
            st.error(str(e))
            st.stop()

        st.markdown(answer["answer"])
        for warning in answer["warnings"]:
            st.warning(warning)
