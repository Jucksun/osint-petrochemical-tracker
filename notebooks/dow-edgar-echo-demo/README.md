# Dow: SEC EDGAR + EPA ECHO aggregation demo

Collects SEC EDGAR filer data and the Exhibit 21 subsidiary list for the Dow family, searches
EPA ECHO for facilities, and merges them into one DuckDB database with provenance on every link.

## How the CIK mapping really works

A **CIK identifies one SEC registrant**, not a corporate family. Subsidiaries do **not** inherit
their parent's CIK.

- **Dow Inc. (CIK 1751788)** and **The Dow Chemical Company (TDCC)** each have their own CIK and
  file one combined 10-K as co-registrants (the same accession number appears under both).
  TDCC is wholly owned by Dow Inc. but is itself an SEC registrant.
- **Most subsidiaries have no CIK at all.** They appear only as names in Exhibit 21 of the 10-K.
- Therefore facility-to-family linking is a **name match against Exhibit 21**, not a CIK lookup.
  This demo labels each link by strength instead of pretending it is exact.


