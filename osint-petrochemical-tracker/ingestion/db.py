"""Open the project database and make sure the RAG tables exist."""
from pathlib import Path

import duckdb

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"


def init_db(path: str = "out/dow.duckdb") -> duckdb.DuckDBPyConnection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    con.execute(SCHEMA_SQL.read_text())
    return con
