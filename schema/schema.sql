-- Shared database schema (DuckDB). Safe to run repeatedly.
-- Structured tables (filer, filing, ex21_entity, echo_facility, facility_link) are written by
-- notebooks/dow-edgar-echo-demo/dow/run.py. The tables below are the RAG layer on top of them.
-- No FOREIGN KEY constraints on purpose: DuckDB makes replacing rows with FKs painful.

CREATE TABLE IF NOT EXISTS source_run (
    run_id      VARCHAR PRIMARY KEY,
    source      VARCHAR NOT NULL,          -- 'sec_edgar', 'epa_echo', ...
    started_at  TIMESTAMP DEFAULT current_timestamp,
    params      VARCHAR                    -- JSON string of what was queried
);

-- One row per source document or per generated fact record. Provenance lives here.
CREATE TABLE IF NOT EXISTS document (
    doc_id         VARCHAR PRIMARY KEY,    -- hash of source_url + content, so edits become new rows
    source         VARCHAR NOT NULL,
    source_url     VARCHAR NOT NULL,       -- where a human can verify it
    doc_type       VARCHAR NOT NULL,       -- '10-K', 'exhibit_21', 'echo_facility_fact', ...
    title          VARCHAR,
    entity_ref     VARCHAR,                -- CIK, ECHO RegistryID, etc.
    published_date DATE,
    fetched_at     TIMESTAMP DEFAULT current_timestamp,
    content_sha256 VARCHAR NOT NULL,
    run_id         VARCHAR
);

-- The text pieces a RAG retriever searches. Every chunk traces back to a document row.
CREATE TABLE IF NOT EXISTS chunk (
    chunk_id        VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    chunk_index     INTEGER NOT NULL,
    text            VARCHAR NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    embedding       FLOAT[],               -- filled in later by the embedding step
    embedding_model VARCHAR                -- which model made it (vectors from different models can't mix)
);
