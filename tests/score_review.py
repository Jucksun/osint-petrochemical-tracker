"""Score the filled-in review sheet: how often is each link tier actually right?

    python -m ingestion.score_review out/review_sheet.csv --db notebooks/dow-edgar-echo-demo/out/dow.duckdb

Several people can review the same rows: put all their sheets in one CSV (or pass several files).
Rows are grouped by RegistryID. If reviewers disagree (one yes, one no) the row counts as "disputed"
and is NOT scored, so go settle it. "unsure" rows are reported but not counted as right or wrong.

Precision = of the links we made, how many were correct. It says nothing about links we MISSED
(that is recall, which needs a different check: see the notes in the project guide).
"""
import argparse
import math

import pandas as pd

Z = 1.96  # 95% confidence
ALIASES = {"y": "yes", "yes": "yes", "n": "no", "no": "no", "unsure": "unsure", "?": "unsure", "u": "unsure"}


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    """Confidence interval for a proportion. Honest about small samples: 7 of 10 is 40% to 89%."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def consensus(df: pd.DataFrame) -> pd.DataFrame:
    """One row per facility with a single outcome: yes, no, unsure, disputed or unreviewed."""
    v = df.copy()
    v["verdict"] = v["verdict"].fillna("").astype(str).str.strip().str.lower().map(lambda x: ALIASES.get(x, ""))
    rows = []
    for rid, g in v.groupby("RegistryID", sort=False):
        votes = set(g["verdict"]) - {"", "unsure"}
        if len(votes) > 1:
            outcome = "disputed"
        elif votes:
            outcome = votes.pop()
        elif "unsure" in set(g["verdict"]):
            outcome = "unsure"
        else:
            outcome = "unreviewed"
        rows.append({"RegistryID": str(rid), "tier": g["tier"].iloc[0], "outcome": outcome})
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    c = consensus(df)
    out = []
    for tier, g in c.groupby("tier"):
        n = g["outcome"].value_counts()
        yes, no, unsure = int(n.get("yes", 0)), int(n.get("no", 0)), int(n.get("unsure", 0))
        scored = yes + no
        lo, hi = wilson(yes, scored)
        out.append({"tier": tier, "rows": len(g), "yes": yes, "no": no, "unsure": unsure,
                    "disputed": int(n.get("disputed", 0)), "unreviewed": int(n.get("unreviewed", 0)),
                    "precision": yes / scored if scored else float("nan"),
                    "ci_low": lo, "ci_high": hi,
                    "precision_if_unsure_wrong": yes / (scored + unsure) if scored + unsure else float("nan")})
    return pd.DataFrame(out)


def compare_to_db(df: pd.DataFrame, con) -> dict:
    """After changing the matching rules and re-running the pipeline: did anything we verified break?"""
    now = {str(r[0]) for r in con.execute("SELECT RegistryID FROM family_facilities").fetchall()}
    c = consensus(df)
    lost = c[(c["outcome"] == "yes") & ~c["RegistryID"].isin(now)]["RegistryID"].tolist()
    false_left = c[(c["outcome"] == "no") & c["RegistryID"].isin(now)]["RegistryID"].tolist()
    return {"verified_correct_now_missing": lost, "verified_wrong_still_linked": false_left}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="+", help="filled-in review CSV file(s)")
    ap.add_argument("--db", default=None, help="also check the verified rows against this database")
    a = ap.parse_args()
    df = pd.concat([pd.read_csv(p, dtype=str).fillna("") for p in a.sheets], ignore_index=True)
    s = summarize(df)
    show = s.copy()
    for c in ("precision", "ci_low", "ci_high", "precision_if_unsure_wrong"):
        show[c] = show[c].map(lambda x: "n/a" if pd.isna(x) else f"{x:.0%}")
    print("\nHow often each link tier was right (95% confidence interval = plausible true range):\n")
    print(show.to_string(index=False))
    print("\nSmall samples give wide ranges. Do not quote the single percentage without the range.")
    if a.db:
        import duckdb
        r = compare_to_db(df, duckdb.connect(a.db, read_only=True))
        print(f"\nVerified-correct links now missing: {len(r['verified_correct_now_missing'])}")
        print(f"Verified-wrong links still present: {len(r['verified_wrong_still_linked'])}")


if __name__ == "__main__":
    main()
