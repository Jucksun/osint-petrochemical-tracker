"""Make a CSV for people to verify matches by hand: a fixed random sample from each link tier.

    python -m ingestion.review_sheet --db notebooks/dow-edgar-echo-demo/out/dow.duckdb

Fill in `verdict` (yes / no / unsure), `evidence_link`, and `notes`. The sample is the same every
time (fixed seed), so everyone checks the same rows.
"""
import argparse
from pathlib import Path

import pandas as pd

from .facts import ECHO_URL

WANT = ["tier", "RegistryID", "FacName", "FacCity", "FacState", "matched_entity", "ex21_url"]


def make_sheet(con, per_tier: int = 10, seed: int = 42) -> pd.DataFrame:
    df = con.execute("SELECT * FROM family_facilities").df()
    parts = [g.sample(min(per_tier, len(g)), random_state=seed) for _, g in df.groupby("tier")]
    if not parts:
        return pd.DataFrame()
    s = pd.concat(parts)
    s["echo_url"] = [ECHO_URL.format(i) for i in s["RegistryID"]]
    cols = [c for c in WANT if c in s.columns] + ["echo_url"]
    s = s[cols].sort_values(["tier", "FacName"]).reset_index(drop=True)
    for c in ("verdict", "evidence_link", "notes", "checked_by"):
        s[c] = ""
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="out/dow.duckdb")
    ap.add_argument("--out", default=None)
    ap.add_argument("--per-tier", type=int, default=10)
    a = ap.parse_args()
    import duckdb
    con = duckdb.connect(a.db, read_only=True)
    sheet = make_sheet(con, a.per_tier)
    out = Path(a.out) if a.out else Path(a.db).parent / "review_sheet.csv"
    sheet.to_csv(out, index=False)
    print(f"Wrote {len(sheet)} rows to {out}")


if __name__ == "__main__":
    main()
