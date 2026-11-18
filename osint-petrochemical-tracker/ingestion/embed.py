"""Turn chunks into vectors so we can search by meaning.

    python -m ingestion.embed --db notebooks/dow-edgar-echo-demo/out/dow.duckdb

Safe to rerun: only chunks without a vector (or with a vector from a different model) are done.
Vectors from different models cannot be compared, which is why the model name is stored too.
"""
import argparse

import numpy as np

from . import llm


def _unit(v) -> list[float]:
    a = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(a)
    return (a / n if n else a).tolist()


def embed_missing(con, embed_fn=None, model: str | None = None, batch: int = 32) -> int:
    embed_fn = embed_fn or llm.embed
    model = model or llm.EMBED_MODEL
    todo = con.execute("SELECT chunk_id, text FROM chunk WHERE embedding IS NULL "
                       "OR embedding_model IS DISTINCT FROM ? ORDER BY chunk_id", [model]).fetchall()
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        vecs = embed_fn([t for _, t in part])
        for (cid, _), v in zip(part, vecs):
            con.execute("UPDATE chunk SET embedding = ?, embedding_model = ? WHERE chunk_id = ?",
                        [_unit(v), model, cid])
        print(f"  embedded {min(i + batch, len(todo))}/{len(todo)}")
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="out/dow.duckdb")
    a = ap.parse_args()
    import duckdb
    con = duckdb.connect(a.db)
    try:
        print(f"Embedded {embed_missing(con)} chunks with {llm.EMBED_MODEL}.")
    except llm.LLMUnavailable as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
