# Architecture

```
SEC EDGAR ─┐                                   ┌─> Streamlit dashboard
           ├─> collectors ─> DuckDB (tables) ──┤
EPA ECHO ──┘   (dow/*.py)         │            └─> RAG tool (later)
                                  v
                       ingestion/ turns rows + filing text
                       into document + chunk tables
                                  v
                       embeddings (later) -> retrieval -> local LLM answer with citations
```

## Build order
1. **Collect** structured data (done in demo; live calls still need a first run).
2. **Store** it in one database with provenance (this folder's schema).
3. **Chunk** text into `document` / `chunk` rows (done: `ingestion/`).
4. **Retrieve**: start with keyword search, then add embeddings.
5. **Answer**: a small local model summarizes only the retrieved chunks and cites `source_url`.

## Decisions
- **DuckDB** over Postgres for now: one file, no server, already used by the demo. Revisit if
  several people need to write at the same time.
- **Embeddings come last.** Retrieval quality depends on clean chunks and good links first.
- **Link confidence travels with the data.** Fact text says how a facility was matched.
