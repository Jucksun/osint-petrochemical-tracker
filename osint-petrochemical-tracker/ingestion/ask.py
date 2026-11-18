"""Answer a question using only retrieved chunks, with citations and automatic sanity checks.

This is retrieval-augmented generation (RAG). The model only sees the numbered sources we hand it.
Limits worth knowing: it reads a handful of passages, so it cannot total or rank across ALL records.
For "which facility has the most penalties" use the dashboard tables, not this.

    python -m ingestion.ask "What penalties are recorded for the Texas facility?" --db ...
"""
import argparse
import re

from . import llm
from .retrieve import hybrid_search

NO_ANSWER = "The sources do not say."

SYSTEM = (
    "You answer questions about petrochemical company records using ONLY the numbered sources "
    "provided. Cite every claim with its source number like [1] or [2][3]. If the sources do not "
    f"contain the answer, reply exactly: {NO_ANSWER} Never add facts from memory. Penalties and "
    "violations are agency-reported and may be alleged, pending, appealed or settled, so never say "
    "a company is guilty or committed wrongdoing. Where a source says a match is uncertain or needs "
    "review, say so. Be concise."
)


def build_messages(question: str, sources: list[dict]) -> list[dict]:
    block = "\n\n".join(f"[{i}] ({s['title']})\n{s['text']}" for i, s in enumerate(sources, 1))
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n{block}\n\nQuestion: {question}"}]


def check_answer(answer: str, sources: list[dict]) -> list[str]:
    """Cheap automatic checks. They catch some mistakes, not all, so a human still reads it."""
    if answer.strip().rstrip(".") == NO_ANSWER.rstrip("."):
        return []
    warnings = []
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    if not cited:
        warnings.append("The answer cites no sources. Treat it as unverified.")
    if any(n < 1 or n > len(sources) for n in cited):
        warnings.append("The answer cites a source number that does not exist.")
    corpus = " ".join(s["text"] for s in sources)
    for amt in sorted(set(re.findall(r"\$[\d,]+(?:\.\d+)?", answer))):
        if amt.rstrip(".,") not in corpus:
            warnings.append(f"The dollar amount {amt} does not appear in any source.")
    return warnings


def ask(con, question: str, k: int = 6, retrieve=None, chat_fn=None) -> dict:
    retrieve = retrieve or hybrid_search
    chat_fn = chat_fn or llm.chat
    sources = retrieve(con, question, k)
    if not sources:
        return {"answer": NO_ANSWER, "sources": [], "warnings": []}
    answer = chat_fn(build_messages(question, sources))
    return {"answer": answer, "sources": sources, "warnings": check_answer(answer, sources)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--db", default="out/dow.duckdb")
    a = ap.parse_args()
    import duckdb
    con = duckdb.connect(a.db, read_only=True)
    try:
        res = ask(con, a.question)
    except llm.LLMUnavailable as e:
        raise SystemExit(str(e))
    print("\n" + res["answer"])
    for w in res["warnings"]:
        print(f"\n  WARNING: {w}")
    print("\nSources:")
    for i, s in enumerate(res["sources"], 1):
        print(f"  [{i}] {s['title']}  {s['source_url']}")


if __name__ == "__main__":
    main()
