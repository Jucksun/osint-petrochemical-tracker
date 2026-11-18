"""Store documents and their chunks. Re-adding identical content is a no-op."""
import hashlib

from .chunking import chunk_text


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def add_document(con, *, source: str, source_url: str, doc_type: str, text: str,
                 title: str | None = None, entity_ref: str | None = None,
                 published_date: str | None = None, run_id: str | None = None,
                 size: int = 1200, overlap: int = 150) -> tuple[str, bool]:
    """Insert a document and its chunks. Returns (doc_id, was_new)."""
    content_sha = _sha(text)
    doc_id = _sha(f"{source_url}|{content_sha}")[:20]
    exists = con.execute("SELECT 1 FROM document WHERE doc_id = ?", [doc_id]).fetchone()
    if exists:
        return doc_id, False
    con.execute(
        """INSERT INTO document (doc_id, source, source_url, doc_type, title, entity_ref,
                                 published_date, content_sha256, run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [doc_id, source, source_url, doc_type, title, entity_ref, published_date,
         content_sha, run_id])
    for i, (a, b, piece) in enumerate(chunk_text(text, size, overlap)):
        con.execute(
            "INSERT INTO chunk (chunk_id, doc_id, chunk_index, text, char_start, char_end) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [f"{doc_id}-{i}", doc_id, i, piece, a, b])
    return doc_id, True
