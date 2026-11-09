"""Turn structured ECHO + link rows into short text records a RAG tool can retrieve and cite.

Wording is deliberately cautious: ECHO penalties are agency-reported and may be alleged, pending,
appealed or settled. Name-match links are labelled with their strength.
"""
import pandas as pd

from .documents import add_document

ECHO_URL = "https://echo.epa.gov/detailed-facility-report?fid={}"


def _val(row, key):
    v = row.get(key)
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def facility_fact_text(row: dict) -> str:
    name, city, st = _val(row, "FacName"), _val(row, "FacCity"), _val(row, "FacState")
    parts = [f"EPA ECHO record for {name}"
             + (f" ({city}, {st})" if city and st else "")
             + f", Registry ID {row['RegistryID']}."]
    status = _val(row, "FacComplianceStatus")
    if status:
        parts.append(f"Compliance status: {status}.")
    actions = _val(row, "FacFormalActionCount")
    if actions is not None:
        parts.append(f"Formal enforcement actions on record: {int(actions)}.")
    pen = _val(row, "FacTotalPenalties")
    if pen is not None:
        parts.append(f"Penalties recorded in ECHO: ${pen:,.0f}. These are agency-reported and may "
                     "be alleged, pending, appealed or settled without admission.")
    ent, tier = _val(row, "matched_entity"), _val(row, "tier")
    if tier:
        link = f"Linked to the company family by a name match ({tier})"
        link += f" against Exhibit 21 entity '{ent}'" if ent else " on a name token only"
        if _val(row, "as_of"):
            link += f", Exhibit 21 as of {row['as_of']}"
        link += ". Needs human review." if row.get("needs_review") else "."
        parts.append(link)
    return " ".join(parts)


def load_facility_facts(con, view: str = "family_facilities") -> int:
    """Add one document per linked facility. Returns how many were new."""
    df = con.execute(f"SELECT * FROM {view}").df()
    new = 0
    for row in df.to_dict("records"):
        _, was_new = add_document(
            con, source="epa_echo", source_url=ECHO_URL.format(row["RegistryID"]),
            doc_type="echo_facility_fact", text=facility_fact_text(row),
            title=str(row.get("FacName")), entity_ref=str(row["RegistryID"]))
        new += was_new
    return new
