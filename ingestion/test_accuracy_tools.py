import pandas as pd

from ingestion.db import init_db
from ingestion.embed import embed_missing
from ingestion.eval_retrieval import evaluate
from ingestion.score_review import compare_to_db, consensus, summarize, wilson
from test_ai_layer import fake_embed, make_db


def test_wilson_matches_known_values_and_is_wide_for_small_samples():
    lo, hi = wilson(7, 10)
    assert abs(lo - 0.397) < 0.005 and abs(hi - 0.892) < 0.005
    assert wilson(0, 0)[0] != wilson(0, 0)[0]            # nan for no data
    lo2, hi2 = wilson(70, 100)
    assert (hi2 - lo2) < (hi - lo)                       # more data, tighter range


def _sheet():
    rows = []
    for i in range(8):   # exact tier: 7 yes, 1 no (two reviewers agree on all)
        for who in ("a", "b"):
            rows.append({"RegistryID": f"e{i}", "tier": "ex21_exact", "verdict": "yes" if i < 7 else "no"})
    rows += [{"RegistryID": "p1", "tier": "token_only", "verdict": "yes"},
             {"RegistryID": "p1", "tier": "token_only", "verdict": "no"},      # reviewers disagree
             {"RegistryID": "p2", "tier": "token_only", "verdict": "Unsure"},
             {"RegistryID": "p3", "tier": "token_only", "verdict": ""},
             {"RegistryID": "p4", "tier": "token_only", "verdict": "N"}]
    return pd.DataFrame(rows)


def test_consensus_handles_duplicates_disputes_and_messy_typing():
    c = consensus(_sheet()).set_index("RegistryID")["outcome"]
    assert len(c) == 12 and c["e0"] == "yes" and c["e7"] == "no"
    assert c["p1"] == "disputed" and c["p2"] == "unsure" and c["p3"] == "unreviewed" and c["p4"] == "no"


def test_summarize_precision_and_strict_variant():
    s = summarize(_sheet()).set_index("tier")
    e, t = s.loc["ex21_exact"], s.loc["token_only"]
    assert e["yes"] == 7 and e["no"] == 1 and abs(e["precision"] - 7 / 8) < 1e-9
    assert e["ci_low"] < e["precision"] < e["ci_high"]
    assert t["disputed"] == 1 and t["unsure"] == 1 and t["no"] == 1 and t["precision"] == 0.0
    assert t["precision_if_unsure_wrong"] == 0.0


def test_compare_to_db_flags_regressions():
    con = init_db(":memory:")
    con.register("t", pd.DataFrame([{"RegistryID": "e0", "tier": "ex21_exact"},      # still linked (good)
                                    {"RegistryID": "e7", "tier": "ex21_exact"}]))    # verified WRONG, still linked
    con.execute("CREATE VIEW family_facilities AS SELECT * FROM t")
    r = compare_to_db(_sheet(), con)
    assert r["verified_wrong_still_linked"] == ["e7"] and "e1" in r["verified_correct_now_missing"]


def test_evaluate_compares_methods_on_known_answers():
    con = make_db()
    embed_missing(con, fake_embed, "ignored-name")
    from ingestion import llm
    embed_missing(con, fake_embed, llm.EMBED_MODEL)
    cases = [("fines", "Houston Texas facility"), ("compliance in michigan", "Lansing Michigan")]
    res = evaluate(con, cases, k=2, embed_fn=fake_embed)
    assert res["keyword"]["recall@k"] == 0.5 and res["semantic"]["recall@k"] == 1.0   # "fines" is never in the text
    assert res["hybrid"]["recall@k"] == 1.0 and 0 < res["hybrid"]["mrr"] <= 1.0
    assert res["keyword"]["missed"] == ["fines"]
