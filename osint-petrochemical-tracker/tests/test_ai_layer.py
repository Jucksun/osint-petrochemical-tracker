"""Stand-in embedder and chat model, so no Ollama is needed. Fictional data only."""
import re

import numpy as np
import pytest
import requests

from ingestion import llm
from ingestion.ask import NO_ANSWER, ask, build_messages, check_answer
from ingestion.db import init_db
from ingestion.documents import add_document
from ingestion.embed import embed_missing
from ingestion.retrieve import hybrid_search, semantic_search
from ingestion.search import search

SYN = {"fines": "penalty", "penalties": "penalty", "fee": "penalty", "texas": "tx", "houston": "tx"}


def fake_embed(texts):
    """Words that mean the same thing land in the same slot, like a (very small) real model."""
    out = []
    for t in texts:
        v = np.zeros(64)
        for w in re.findall(r"[a-z]+", t.lower()):
            v[hash(SYN.get(w, w)) % 64] += 1
        out.append(v.tolist())
    return out


def make_db():
    con = init_db(":memory:")
    for url, title, text in [
        ("u1", "Texas plant", "Penalties recorded for the Houston Texas facility: $1,500."),
        ("u2", "Michigan plant", "Compliance status for the Lansing Michigan facility is good."),
        ("u3", "Annual report", "The company operates plants in several countries.")]:
        add_document(con, source="s", source_url=url, doc_type="t", title=title, text=text)
    return con


def test_embed_missing_stores_unit_vectors_and_is_rerunnable():
    con = make_db()
    assert embed_missing(con, fake_embed, "m1") == 3
    assert embed_missing(con, fake_embed, "m1") == 0
    v = con.execute("SELECT embedding FROM chunk LIMIT 1").fetchone()[0]
    assert abs(np.linalg.norm(v) - 1.0) < 1e-5
    assert embed_missing(con, fake_embed, "m2") == 3   # a different model means start over


def test_semantic_search_finds_rewordings_that_keyword_search_misses():
    con = make_db()
    embed_missing(con, fake_embed, "m1")
    assert search(con, "fines") == []                          # no chunk contains the word
    top = semantic_search(con, "fines in texas", 2, fake_embed, "m1")
    assert top[0]["title"] == "Texas plant"
    assert semantic_search(con, "fines", 2, fake_embed, "other-model") == []  # model mismatch ignored


def test_hybrid_rewards_chunks_found_by_both_methods():
    con = make_db()
    embed_missing(con, fake_embed, "m1")
    res = hybrid_search(con, "penalties texas", 3, fake_embed, "m1")
    assert res[0]["title"] == "Texas plant" and res[0]["rrf"] > res[-1]["rrf"]
    assert all("snippet" in r for r in res)


SRC = [{"title": "T", "text": "Penalties recorded: $1,500 for the facility."}]


def test_check_answer_flags_the_usual_failures():
    assert check_answer("Penalties were $1,500 [1].", SRC) == []
    assert check_answer(NO_ANSWER, SRC) == []
    assert any("cites no sources" in w for w in check_answer("Penalties were $1,500.", SRC))
    assert any("does not exist" in w for w in check_answer("Penalties were $1,500 [3].", SRC))
    assert any("$9,999" in w for w in check_answer("Penalties were $9,999 [1].", SRC))


def test_ask_uses_sources_and_skips_the_model_when_nothing_found():
    con = make_db()
    called = []
    res = ask(con, "x", retrieve=lambda c, q, k: [], chat_fn=lambda m: called.append(m))
    assert res["answer"] == NO_ANSWER and not called
    res = ask(con, "q", retrieve=lambda c, q, k: SRC, chat_fn=lambda m: "Penalties were $9,999 [1].")
    assert res["sources"] == SRC and res["warnings"]


def test_build_messages_numbers_sources_and_forbids_outside_facts():
    msgs = build_messages("What?", SRC)
    assert "[1] (T)" in msgs[1]["content"] and "Question: What?" in msgs[1]["content"]
    assert "ONLY" in msgs[0]["content"] and "guilty" in msgs[0]["content"]


def test_llm_errors_are_readable(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(llm.LLMUnavailable, match="ollama serve"):
        llm.embed(["x"])

    class R:
        status_code, text = 404, "model not found"
    monkeypatch.setattr(requests, "post", lambda *a, **k: R())
    with pytest.raises(llm.LLMUnavailable, match="ollama pull"):
        llm.chat([{"role": "user", "content": "hi"}])

    class OK:
        status_code = 200
        def json(self): return {"embeddings": [[1.0, 0.0]], "message": {"content": " hi "}}
    monkeypatch.setattr(requests, "post", lambda *a, **k: OK())
    assert llm.embed(["x"]) == [[1.0, 0.0]] and llm.chat([]) == "hi"
