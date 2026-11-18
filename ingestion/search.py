"""Keyword search over the chunk table. No extensions or models needed.

Ranking: chunks that contain more of your search terms come first; ties go to the chunk where the
terms appear most often. Terms match whole words ("pen" does not match "penalty"). Put a phrase in
double quotes to match it exactly: "legal proceedings" wastewater

    python -m ingestion.search 'wastewater "legal proceedings"' --db out/dow.duckdb
"""
import argparse
import re

STOP = {"a", "an", "and", "the", "of", "in", "on", "at", "to", "for", "is", "are", "was",
        "were", "by", "with", "or", "as", "it", "this", "that", "from", "be"}


def parse_query(q: str) -> list[list[str]]:
    """Each term is a list of words: a quoted phrase gives several words, a plain word gives one."""
    terms = [re.findall(r"[a-z0-9]+", p.lower()) for p in re.findall(r'"([^"]+)"', q)]
    rest = re.sub(r'"[^"]*"', " ", q).lower()
    terms += [[w] for w in re.findall(r"[a-z0-9]+", rest) if w not in STOP and len(w) > 1]
    return [t for t in terms if t]


def _pattern(words: list[str]) -> str:
    return r"\b" + r"\s+".join(words) + r"\b"


def search(con, query: str, k: int = 10, doc_type: str | None = None,
           match_all: bool = False) -> list[dict]:
    terms = parse_query(query)
    if not terms:
        return []
    pats = [_pattern(t) for t in terms]
    counts = ", ".join(f"len(regexp_extract_all(lower(c.text), ?)) AS n{i}" for i in range(len(pats)))
    hits = " + ".join(f"n{i}" for i in range(len(pats)))
    matched = " + ".join(f"CAST(n{i} > 0 AS INTEGER)" for i in range(len(pats)))
    sql = f"""
        WITH s AS (SELECT c.chunk_id, c.doc_id, c.chunk_index, c.text, {counts} FROM chunk c)
        SELECT s.chunk_id, s.text, d.title, d.doc_type, d.source_url, s.chunk_index,
               {matched} AS matched, {hits} AS hits
        FROM s JOIN document d ON d.doc_id = s.doc_id
        WHERE ({hits}) > 0 {"AND (" + matched + ") = " + str(len(pats)) if match_all else ""}
              {"AND d.doc_type = ?" if doc_type else ""}
        ORDER BY matched DESC, hits DESC, s.chunk_id
        LIMIT ?"""
    params = pats + ([doc_type] if doc_type else []) + [k]
    cols = ["chunk_id", "text", "title", "doc_type", "source_url", "chunk_index", "matched", "hits"]
    out = []
    for row in con.execute(sql, params).fetchall():
        r = dict(zip(cols, row))
        r["snippet"] = snippet(r["text"], terms)
        r["terms"] = terms
        out.append(r)
    return out


def snippet(text: str, terms: list[list[str]], width: int = 160) -> str:
    low = text.lower()
    pos = [m.start() for t in terms for m in [re.search(_pattern(t), low)] if m]
    if not pos:
        return text[: 2 * width]
    a = max(min(pos) - width, 0)
    b = min(min(pos) + width, len(text))
    return ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")


def highlight(text: str, terms: list[list[str]]) -> str:
    """Markdown-safe text with matched terms in bold. Escapes characters Streamlit would misread
    (a pair of $ signs would otherwise turn into a math formula)."""
    text = re.sub(r"([\\`*_#\[\]$<>])", r"\\\1", text)
    for t in terms:
        pat = r"\b" + r"\s+".join(re.escape(w) for w in t) + r"\b"
        text = re.sub(pat, lambda m: f"**{m.group(0)}**", text, flags=re.I)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--db", default="out/dow.duckdb")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--type", default=None, help="10-K or echo_facility_fact")
    a = ap.parse_args()
    import duckdb
    con = duckdb.connect(a.db, read_only=True)
    res = search(con, a.query, a.k, a.type)
    if not res:
        print("No matches.")
    for i, r in enumerate(res, 1):
        print(f"\n[{i}] {r['title']} ({r['doc_type']}) terms matched: {r['matched']}")
        print(f"    {r['snippet']}")
        print(f"    source: {r['source_url']}")


if __name__ == "__main__":
    main()
