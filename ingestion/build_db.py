"""Create the database and load RAG-ready text from whatever the collectors already produced.

    python -m ingestion.build_db --db notebooks/dow-edgar-echo-demo/out/dow.duckdb
    python -m ingestion.build_db --db ... --with-10k     # also downloads the 10-K text from SEC

Close the Streamlit dashboard before running this: it writes to the database file.
"""
import argparse

from .db import init_db
from .facts import load_facility_facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="out/dow.duckdb")
    ap.add_argument("--with-10k", action="store_true",
                    help="download and store the latest 10-K text (needs SEC_USER_AGENT)")
    a = ap.parse_args()
    con = init_db(a.db)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "family_facilities" in tables:
        print(f"Added {load_facility_facts(con)} new facility records.")
    else:
        print("No family_facilities view yet. Run the collectors first (python -m dow.run).")
    if a.with_10k:
        from .tenk import load_10k
        doc_id, was_new, n = load_10k(con)
        print(f"10-K {'added' if was_new else 'was already loaded'}: {n} chunks.")
    docs, chunks = con.execute("SELECT (SELECT count(*) FROM document), "
                               "(SELECT count(*) FROM chunk)").fetchone()
    print(f"Database now holds {docs} documents and {chunks} chunks.")


if __name__ == "__main__":
    main()
