"""Fictional data only (Examplechem)."""
import pandas as pd

from ingestion.db import init_db
from ingestion.documents import add_document
from ingestion.review_sheet import make_sheet
from ingestion.search import highlight, parse_query, search
from ingestion.tenk import html_to_text, load_10k, tenk_url

FILING = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<div style="display:none"><ix:header>HIDDEN_XBRL_JUNK 0000012345</ix:header></div>
<div><span>Item&#160;3.</span> Legal Proceedings</div>
<p>Examplechem received a notice about wastewater permit limits at its Texas site.</p>
<table><tr><td>Penalty</td><td>$1,500</td></tr></table>
<script>var x = 'SCRIPT_JUNK';</script>
</body></html>"""


def test_html_to_text_drops_hidden_data_and_keeps_paragraphs():
    t = html_to_text(FILING)
    assert "HIDDEN_XBRL_JUNK" not in t and "SCRIPT_JUNK" not in t
    assert "Item 3. Legal Proceedings" in t
    assert "Legal Proceedings\n\nExamplechem received" in t
    assert "Penalty $1,500" in t


def test_tenk_url():
    assert tenk_url("1751788", "0001751788-26-000012", "dow-20251231.htm") == \
        "https://www.sec.gov/Archives/edgar/data/1751788/000175178826000012/dow-20251231.htm"


def test_load_10k_with_fake_fetch_is_idempotent():
    con = init_db(":memory:")
    con.execute("CREATE TABLE filing (cik BIGINT, accession VARCHAR, filing_date VARCHAR, primary_doc VARCHAR)")
    con.execute("INSERT INTO filing VALUES (1, '0000000001-26-000001', '2026-02-01', 'x.htm')")
    d1, new1, n1 = load_10k(con, fetch=lambda url: FILING)
    d2, new2, n2 = load_10k(con, fetch=lambda url: FILING)
    assert (new1, new2) == (True, False) and d1 == d2 and n1 == n2 >= 1


def test_parse_query_handles_phrases_and_stopwords():
    assert parse_query('wastewater "legal proceedings" of the') == [["legal", "proceedings"], ["wastewater"]]
    assert parse_query("the of and") == []


def _db():
    con = init_db(":memory:")
    add_document(con, source="s", source_url="u1", doc_type="10-K", title="Filing",
                 text="Wastewater permit limits were exceeded. " * 3)
    add_document(con, source="s", source_url="u2", doc_type="10-K", title="Other",
                 text="The company paid a wastewater fee.")
    add_document(con, source="s", source_url="u3", doc_type="echo_facility_fact", title="Fac",
                 text="Penalties recorded: $1,500 for the facility.")
    return con


def test_search_ranks_by_terms_matched_then_frequency():
    res = search(_db(), "wastewater permit")
    assert [r["title"] for r in res] == ["Filing", "Other"]
    assert res[0]["matched"] == 2 and res[1]["matched"] == 1


def test_search_match_all_and_type_filter_and_whole_words():
    con = _db()
    assert [r["title"] for r in search(con, "wastewater permit", match_all=True)] == ["Filing"]
    assert [r["title"] for r in search(con, "penalties", doc_type="echo_facility_fact")] == ["Fac"]
    assert search(con, "penalt") == []          # whole words only, no partial matches
    assert search(con, '"permit limits"')[0]["title"] == "Filing"
    assert search(con, "the of") == []


def test_highlight_escapes_dollar_signs_and_bolds_terms():
    out = highlight("Penalties recorded: $1,500 and $20 for wastewater.", [["wastewater"]])
    assert "\\$1,500" in out and "**wastewater**" in out and "$" not in out.replace("\\$", "")


def test_review_sheet_samples_each_tier_with_blank_columns():
    con = init_db(":memory:")
    rows = ([{"RegistryID": str(i), "FacName": f"A{i}", "tier": "ex21_exact", "matched_entity": "x"} for i in range(15)]
            + [{"RegistryID": f"t{i}", "FacName": f"T{i}", "tier": "token_only", "matched_entity": None} for i in range(3)])
    con.register("t", pd.DataFrame(rows))
    con.execute("CREATE VIEW family_facilities AS SELECT * FROM t")
    s = make_sheet(con, per_tier=10)
    assert (s["tier"] == "ex21_exact").sum() == 10 and (s["tier"] == "token_only").sum() == 3
    assert (s["verdict"] == "").all() and "echo_url" in s
    assert make_sheet(con, 10)["RegistryID"].tolist() == s["RegistryID"].tolist()  # same sample each time
