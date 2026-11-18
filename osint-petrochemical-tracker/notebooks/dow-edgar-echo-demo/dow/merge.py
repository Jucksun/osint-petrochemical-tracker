"""Link ECHO facilities to the Dow family using Exhibit 21 names. Deterministic and explainable.

Important: a CIK identifies an SEC *registrant*, not a corporate family. Most subsidiaries have
no CIK. The family link comes from Exhibit 21 (a name list), so every link here is a NAME match,
tagged with how strong it is.
"""
import re

import pandas as pd

SUFFIX = re.compile(r"\b(INC|LLC|L L C|CORP|CORPORATION|CO|COMPANY|LP|L P|LTD|LIMITED|THE)\b")


def norm(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", str(s).upper())
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


TIER_RANK = {"ex21_exact": 1, "ex21_prefix": 2, "token_only": 3}


def link_facilities(echo_df: pd.DataFrame, ex21: pd.DataFrame, seed_tokens: list[str],
                    ultimate_cik: int) -> pd.DataFrame:
    """One row per matched facility: matched_entity, tier, needs_review, provenance."""
    ex = {norm(n): (n, a, u, d) for n, a, u, d in
          zip(ex21["name"], ex21["accession"], ex21["source_url"], ex21["as_of"])}
    tok = [(norm(t), re.compile(r"\b" + re.escape(norm(t)) + r"\b")) for t in seed_tokens]
    out = []
    for _, f in echo_df.iterrows():
        fn = norm(f["FacName"])
        hit = None
        if fn in ex:
            hit = ("ex21_exact", ex[fn])
        else:
            best = None
            for en, val in ex.items():
                if len(en) >= 10 and fn.startswith(en + " ") and (best is None or len(en) > len(best[0])):
                    best = (en, val)
            if best:
                hit = ("ex21_prefix", best[1])
        if hit:
            tier, (name, acc, url, as_of) = hit
            out.append({"RegistryID": f["RegistryID"], "matched_entity": name, "tier": tier,
                        "needs_review": tier != "ex21_exact", "ex21_accession": acc,
                        "ex21_url": url, "as_of": as_of, "ultimate_parent_cik": ultimate_cik})
        elif any(p.search(fn) for _, p in tok):
            out.append({"RegistryID": f["RegistryID"], "matched_entity": None, "tier": "token_only",
                        "needs_review": True, "ex21_accession": None, "ex21_url": None,
                        "as_of": None, "ultimate_parent_cik": ultimate_cik})
    return pd.DataFrame(out, columns=["RegistryID", "matched_entity", "tier", "needs_review",
                                      "ex21_accession", "ex21_url", "as_of", "ultimate_parent_cik"])


def summarize(echo_df: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """Facilities and penalties by confidence tier. Never report one blended total."""
    m = echo_df.merge(links, on="RegistryID", how="inner")
    cols = {"facilities": ("RegistryID", "nunique")}
    if "FacTotalPenalties" in m:
        cols["penalties"] = ("FacTotalPenalties", "sum")
    g = m.groupby("tier").agg(**cols).reset_index()
    g["rank"] = g["tier"].map(TIER_RANK)
    return g.sort_values("rank").drop(columns="rank")
