"""Fixtures use a FICTIONAL parent ("Examplechem") so no real company data is invented."""
import pandas as pd

from dow.edgar import parse_exhibit21, latest_10k
from dow.merge import link_facilities, summarize

EX21_HTML = """<table>
<tr><td>Name of Subsidiary</td><td>Jurisdiction</td></tr>
<tr><td>Examplechem Holdings LLC</td><td>Delaware</td></tr>
<tr><td>Examplechem Texas Operations LP</td><td>Texas</td></tr>
<tr><td>Examplechem Europe BV</td><td>Netherlands</td></tr></table>"""


def ex21():
    df = parse_exhibit21(EX21_HTML)
    df["accession"], df["source_url"], df["as_of"] = "0000000000-26-000001", "https://x/ex21.htm", "2026-02-01"
    return df


def facilities():
    return pd.DataFrame([
        {"RegistryID": "1", "FacName": "EXAMPLECHEM TEXAS OPERATIONS LP", "FacTotalPenalties": 100.0},
        {"RegistryID": "2", "FacName": "EXAMPLECHEM TEXAS OPERATIONS - PLANT 2", "FacTotalPenalties": 50.0},
        {"RegistryID": "3", "FacName": "EXAMPLECHEM CLEANERS", "FacTotalPenalties": 7.0},
        {"RegistryID": "4", "FacName": "UNRELATED CORP", "FacTotalPenalties": 999.0},
        {"RegistryID": "5", "FacName": "EXAMPLECHEMICAL SUPPLY", "FacTotalPenalties": 3.0},
    ])


def test_parse_exhibit21_skips_header():
    df = parse_exhibit21(EX21_HTML)
    assert list(df["name"]) == ["Examplechem Holdings LLC", "Examplechem Texas Operations LP",
                                "Examplechem Europe BV"]
    assert df.loc[1, "jurisdiction"] == "Texas"


def test_tiers():
    links = link_facilities(facilities(), ex21(), ["EXAMPLECHEM"], 123).set_index("RegistryID")
    assert links.loc["1", "tier"] == "ex21_exact" and not links.loc["1", "needs_review"]
    assert links.loc["2", "tier"] == "ex21_prefix" and links.loc["2", "needs_review"]
    assert links.loc["3", "tier"] == "token_only"
    assert "4" not in links.index          # unrelated stays out
    assert "5" not in links.index          # word boundary: EXAMPLECHEMICAL != EXAMPLECHEM


def test_summary_keeps_tiers_separate():
    links = link_facilities(facilities(), ex21(), ["EXAMPLECHEM"], 123)
    s = summarize(facilities(), links).set_index("tier")
    assert s.loc["ex21_exact", "penalties"] == 100.0
    assert s.loc["token_only", "penalties"] == 7.0
    assert list(s.index) == ["ex21_exact", "ex21_prefix", "token_only"]


def test_latest_10k_picks_first_10k():
    sub = {"filings": {"recent": {"form": ["8-K", "10-K", "10-K"],
                                  "accessionNumber": ["a", "b", "c"],
                                  "filingDate": ["2026-03-01", "2026-02-01", "2025-02-01"],
                                  "primaryDocument": ["x", "y", "z"]}}}
    assert latest_10k(sub)["accession"] == "b"
