"""Create the database and load RAG-ready text from whatever the collectors already produced.

    python -m ingestion.build_db --db notebooks/dow-edgar-echo-demo/out/dow.duckdb
"""
import argparse

from .db import init_db
from .facts import load_facility_facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="out/dow.duckdb")
    a = ap.parse_args()
    con = init_db(a.db)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "family_facilities" in tables:
        print(f"Added {load_facility_facts(con)} new facility records.")
    else:
        print("No family_facilities view yet. Run the collectors first (python -m dow.run).")
    docs, chunks = con.execute("SELECT (SELECT count(*) FROM document), "
                               "(SELECT count(*) FROM chunk)").fetchone()
    print(f"Database now holds {docs} documents and {chunks} chunks.")


if __name__ == "__main__":
    main()
