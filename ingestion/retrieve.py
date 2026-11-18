"""Find the chunks most relevant to a question: by meaning, by keywords, or both combined."""
import numpy as np

from . import llm
from .search import search as keyword_search, snippet


def semantic_search(con, query: str, k: int = 10, embed_fn=None, model: str | None = None,
                    doc_type: str | None = None) -> list[dict]:
    embed_fn = embed_fn or llm.embed
    model = model or llm.EMBED_MODEL
    sql = ("SELECT c.chunk_id, c.text, c.embedding, d.title, d.doc_type, d.source_url "
           "FROM chunk c JOIN document d ON d.doc_id = c.doc_id "
           "WHERE c.embedding IS NOT NULL AND c.embedding_model = ?"
           + (" AND d.doc_type = ?" if doc_type else ""))
    rows = con.execute(sql, [model] + ([doc_type] if doc_type else [])).fetchall()
    if not rows:
        return []
    m = np.asarray([r[2] for r in rows], dtype=np.float32)
    q = np.asarray(embed_fn([query])[0], dtype=np.float32)
    q = q / (np.linalg.norm(q) or 1.0)
    scores = m @ q  # stored vectors are unit length, so this is cosine similarity
    out = []
    for i in np.argsort(-scores)[:k]:
        cid, text, _, title, dtype, url = rows[i]
        out.append({"chunk_id": cid, "text": text, "title": title, "doc_type": dtype,
                    "source_url": url, "score": float(scores[i]), "snippet": text[:320]})
    return out


def hybrid_search(con, query: str, k: int = 6, embed_fn=None, model: str | None = None,
                  doc_type: str | None = None) -> list[dict]:
    """Reciprocal rank fusion: a chunk ranked well by EITHER method rises to the top, and a chunk
    ranked well by both rises further. Keywords catch exact names and numbers; meaning catches
    rewordings."""
    pool = max(k * 3, 15)
    kw = keyword_search(con, query, pool, doc_type)
    sem = semantic_search(con, query, pool, embed_fn, model, doc_type)
    fused: dict[str, dict] = {}
    for results in (kw, sem):
        for rank, r in enumerate(results):
            item = fused.setdefault(r["chunk_id"], {**r, "rrf": 0.0})
            item["rrf"] += 1.0 / (60 + rank + 1)
    ranked = sorted(fused.values(), key=lambda r: -r["rrf"])[:k]
    for r in ranked:
        r.setdefault("snippet", snippet(r["text"], r.get("terms", [])))
    return ranked
