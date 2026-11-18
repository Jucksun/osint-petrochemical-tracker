"""End-to-end: EDGAR (filers, 10-K, Exhibit 21) + ECHO -> linked DuckDB + CSVs in out/.

    export SEC_USER_AGENT="Your Name you@example.com"
    python -m dow.run [--max-queries 40] [--include-inactive]
"""
import argparse

import duckdb

from . import echo, edgar
from .config import (DB_PATH, EXTRA_CIKS, OUT_DIR, SEED_CIKS, SEED_TOKENS, STATE_NAMES,
                     ULTIMATE_PARENT_CIK)
from .merge import link_facilities, norm, summarize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=40,
                    help="cap on per-subsidiary ECHO searches (be polite to the API)")
    ap.add_argument("--include-inactive", action="store_true")
    a = ap.parse_args()

    ciks = SEED_CIKS + EXTRA_CIKS
    filers, filings, ex21 = edgar.collect(ciks)
    print(filers[["cik", "edgar_name"]].to_string(index=False))
    if not filers["edgar_name"].str.upper().str.contains("DOW|UNION CARBIDE").all():
        raise SystemExit("A seed CIK does not look like a Dow-family registrant. Fix config.py.")
    if ex21.empty:
        raise SystemExit("No Exhibit 21 retrieved; cannot map subsidiaries.")
    print(f"\n{len(ex21)} Exhibit 21 entities from accession {ex21['accession'].iloc[0]}")
    same = filings["accession"].nunique() == 1 and len(filings) > 1
    print("Combined filing (one accession, several CIKs):", same)

    us = ex21[ex21["jurisdiction"].str.upper().str.strip().isin(STATE_NAMES)]
    queries = list(dict.fromkeys(SEED_TOKENS + [norm(n) for n in us["name"]]))
    queries = queries[:len(SEED_TOKENS) + a.max_queries]
    print(f"Running {len(queries)} ECHO searches...")
    fac = echo.collect(queries, active_only=not a.include_inactive)
    if fac.empty:
        raise SystemExit("ECHO returned nothing.")

    links = link_facilities(fac, ex21, SEED_TOKENS, ULTIMATE_PARENT_CIK)
    summary = summarize(fac, links)
    print("\nFacilities and penalties by link confidence:")
    print(summary.to_string(index=False))

    con = duckdb.connect(str(DB_PATH))
    for name, df in [("filer", filers), ("filing", filings), ("ex21_entity", ex21),
                     ("echo_facility", fac), ("facility_link", links)]:
        con.register("t", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM t")
        con.unregister("t")
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
    con.execute("""CREATE OR REPLACE VIEW family_facilities AS
                   SELECT f.*, l.matched_entity, l.tier, l.needs_review, l.ex21_accession,
                          l.ex21_url, l.as_of, l.ultimate_parent_cik
                   FROM echo_facility f JOIN facility_link l USING (RegistryID)""")
    print(f"\nWrote {DB_PATH} and CSVs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
