# Dow: SEC EDGAR + EPA ECHO aggregation demo

Collects SEC EDGAR filer data and the Exhibit 21 subsidiary list for the Dow family, searches
EPA ECHO for facilities, and merges them into one DuckDB database with provenance on every link.

## How the CIK mapping really works

A **CIK identifies one SEC registrant**, not a corporate family. Subsidiaries do **not** inherit
their parent's CIK.

- **Dow Inc. (CIK 1751788)** and **The Dow Chemical Company (TDCC)** each have their own CIK and
  file one *combined* 10-K as co-registrants (the same accession number appears under both).
  TDCC is wholly owned by Dow Inc. but is itself an SEC registrant.
- **Most subsidiaries have no CIK at all.** They appear only as names in Exhibit 21 of the 10-K.
- Therefore facility-to-family linking is a **name match against Exhibit 21**, not a CIK lookup.
  This demo labels each link by strength instead of pretending it is exact.

| Tier | Meaning | Needs review |
|---|---|---|
| `ex21_exact` | Normalized facility name equals an Exhibit 21 entity | No |
| `ex21_prefix` | Facility name starts with an Exhibit 21 entity name | Yes |
| `token_only` | Contains a seed token (e.g. "DOW CHEMICAL") but matches no Exhibit 21 entity | Yes |

Reports show penalties **per tier**, never one blended total.

## Run

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name you@example.com"
python -m dow.run          # collect + merge, writes out/dow.duckdb and CSVs
streamlit run app.py       # explore
pytest                     # logic tests (synthetic fixtures, no network)
```

## Status

- Merge and parsing logic is unit-tested with a fictional parent. **The live EDGAR and ECHO calls
  have not been run yet.** On first run, check that the Exhibit 21 file is found (the script prints
  the file list if not) and that the TDCC CIK in `dow/config.py` resolves to the expected name.
- ECHO returns what it holds under a facility's registered name. Facilities operated through
  joint ventures or renamed entities will be missed or land in `token_only`.
- Next: TRI parent-company fields as a second, independent link; GLEIF parent relationships;
  a review UI to accept or reject `ex21_prefix` and `token_only` links.

## Caveats

ECHO violations and penalties are agency-reported and may be alleged, pending, appealed or
settled without admission. Exhibit 21 is a point-in-time list, so every link carries its filing date.
