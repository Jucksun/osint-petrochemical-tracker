"""Does search find the right passage? Test keyword, meaning-based and hybrid search on questions
you wrote yourself, where you know the right answer.

Make a CSV with two columns:
    question,expected
    What penalties are recorded for the Houston plant?,Registry ID 110012345
    Does the filing mention wastewater permits?,wastewater permit
`expected` is a piece of text that MUST appear in a correct passage (a registry ID, a distinctive
phrase, a dollar amount). Write 20 or more, from the real records, BEFORE looking at what search returns.

    python -m ingestion.eval_retrieval questions.csv --db notebooks/dow-edgar-echo-demo/out/dow.duckdb

recall@k = share of questions where a correct passage appeared in the top k results.
MRR = average of 1/rank of the first correct passage (1.0 = always first, 0 = never found).
"""
import argparse

import pandas as pd

from . import llm
from .retrieve import hybrid_search, semantic_search
from .search import search


def _run(method, con, q, k, embed_fn):
    if method == "keyword":
        return search(con, q, k)
    if method == "semantic":
        return semantic_search(con, q, k, embed_fn)
    return hybrid_search(con, q, k, embed_fn)


def evaluate(con, cases: list[tuple[str, str]], k: int = 5, embed_fn=None,
             methods=("keyword", "semantic", "hybrid")) -> dict:
    out = {}
    for m in methods:
        ranks = []
        for q, exp in cases:
            hits = _run(m, con, q, k, embed_fn)
            ranks.append(next((i for i, h in enumerate(hits, 1) if exp.lower() in h["text"].lower()), None))
        n = len(cases)
        out[m] = {"recall@k": sum(r is not None for r in ranks) / n,
                  "mrr": sum(1 / r for r in ranks if r) / n,
                  "missed": [q for (q, _), r in zip(cases, ranks) if r is None]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", help="CSV with question and expected columns")
    ap.add_argument("--db", default="out/dow.duckdb")
    ap.add_argument("-k", type=int, default=5)
    a = ap.parse_args()
    import duckdb
    con = duckdb.connect(a.db, read_only=True)
    df = pd.read_csv(a.cases, dtype=str).fillna("")
    cases = list(zip(df["question"], df["expected"]))
    methods = ["keyword", "semantic", "hybrid"]
    try:
        res = evaluate(con, cases, a.k, methods=methods)
    except llm.LLMUnavailable:
        print("Ollama is not running, so only keyword search was tested.")
        res = evaluate(con, cases, a.k, methods=["keyword"])
    print(f"\n{len(cases)} questions, top {a.k} results\n")
    for m, r in res.items():
        print(f"{m:9s} recall@{a.k}: {r['recall@k']:.0%}   MRR: {r['mrr']:.2f}")
    for m, r in res.items():
        if r["missed"]:
            print(f"\nMissed by {m}:")
            for q in r["missed"]:
                print("  -", q)


if __name__ == "__main__":
    main()
