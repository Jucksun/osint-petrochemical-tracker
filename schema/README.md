# Database schema

One DuckDB file holds everything. `schema.sql` creates the RAG layer; the collectors in
`notebooks/dow-edgar-echo-demo/` create the structured tables.

| Table | What it holds |
|---|---|
| `filer`, `filing`, `ex21_entity` | SEC registrants, their 10-K filings, Exhibit 21 subsidiary names |
| `echo_facility`, `facility_link` | EPA facilities and how (and how confidently) each links to the company family |
| `document` | One row per source document or generated fact, with `source_url` so anyone can verify it |
| `chunk` | The text pieces a retriever searches, each tied to a `document`; `embedding` is empty until the embedding step |
| `source_run` | Which collector run produced what (for reproducibility) |

Rule: nothing goes into `chunk` without a `document` row that has a `source_url`. That is what
lets the future AI answer say where a claim came from.
