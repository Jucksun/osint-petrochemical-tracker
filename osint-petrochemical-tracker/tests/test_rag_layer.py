"""Fictional data only (Examplechem), so nothing real is invented."""
import pandas as pd

from ingestion.chunking import chunk_text
from ingestion.db import init_db
from ingestion.documents import add_document
from ingestion.facts import facility_fact_text, load_facility_facts


def test_chunks_cover_text_and_respect_size():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(20))
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(c[2]) <= 500 for c in chunks)
    assert chunks[0][0] == 0 and chunks[-1][1] == len(text)


def test_chunk_text_always_terminates_on_unbroken_text():
    assert len(chunk_text("x" * 5000, size=500, overlap=100)) >= 10


def test_add_document_is_idempotent_and_versioned():
    con = init_db(":memory:")
    kw = dict(source="sec_edgar", source_url="https://x/10k", doc_type="10-K")
    d1, new1 = add_document(con, text="Alpha. " * 400, **kw)
    d2, new2 = add_document(con, text="Alpha. " * 400, **kw)
    d3, new3 = add_document(con, text="Beta. " * 400, **kw)
    assert (new1, new2, new3) == (True, False, True)
    assert d1 == d2 != d3
    assert con.execute("SELECT count(*) FROM document").fetchone()[0] == 2


def test_fact_text_is_cautious_and_cites_link_strength():
    t = facility_fact_text({"RegistryID": "9", "FacName": "EXAMPLECHEM TEXAS OPERATIONS LP",
                            "FacCity": "Houston", "FacState": "TX", "FacTotalPenalties": 1500.0,
                            "FacFormalActionCount": 2, "tier": "ex21_prefix",
                            "matched_entity": "Examplechem Texas Operations LP",
                            "as_of": "2026-02-01", "needs_review": True})
    assert "alleged, pending" in t and "ex21_prefix" in t and "Needs human review" in t
    assert "$1,500" in t


def test_load_facility_facts_end_to_end():
    con = init_db(":memory:")
    df = pd.DataFrame([{"RegistryID": "1", "FacName": "EXAMPLECHEM A", "FacTotalPenalties": 10.0,
                        "tier": "token_only", "matched_entity": None, "needs_review": True}])
    con.register("t", df)
    con.execute("CREATE VIEW family_facilities AS SELECT * FROM t")
    assert load_facility_facts(con) == 1
    assert load_facility_facts(con) == 0  # rerun adds nothing
    url, text = con.execute("SELECT d.source_url, c.text FROM chunk c JOIN document d USING (doc_id)").fetchone()
    assert url.endswith("fid=1") and "EXAMPLECHEM A" in text
