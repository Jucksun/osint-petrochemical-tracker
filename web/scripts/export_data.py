"""Export the DuckDB project database to the static JSON files the website serves.

    pip install duckdb zipcodes
    python web/scripts/export_data.py --db notebooks/dow-edgar-echo-demo/out/dow.duckdb

Writes web/public/data/{facilities,chunks,ex21,meta}.json. Re-run whenever the pipeline refreshes.

Coordinates: the ECHO export has no FacLat/FacLong columns, so each facility is placed at its ZIP
code centroid (geo = "zip", approximate). If FacLat/FacLong ever appear, they are used (geo = "echo").
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import duckdb

OUT = Path(__file__).resolve().parent.parent / "public" / "data"


def nn(v):
    """None for NaN/empty so JSON stays clean."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and not v.strip():
        return None
    return v


def zip_point(z):
    try:
        import zipcodes
    except ImportError:
        return None
    z = str(z or "")[:5]
    if len(z) != 5 or z in ("00000", "99999"):
        return None
    m = zipcodes.matching(z)
    if m and m[0].get("lat"):
        return float(m[0]["lat"]), float(m[0]["long"])
    return None


def spread(rid, lat, lon):
    """Tiny deterministic offset (<= ~1.5 km) so facilities sharing a ZIP do not stack exactly."""
    h = hashlib.sha1(str(rid).encode()).digest()
    return lat + (h[0] / 255 - 0.5) * 0.026, lon + (h[1] / 255 - 0.5) * 0.026


def num(v):
    v = nn(v)
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="notebooks/dow-edgar-echo-demo/out/dow.duckdb")
    a = ap.parse_args()
    con = duckdb.connect(a.db, read_only=True)
    OUT.mkdir(parents=True, exist_ok=True)

    df = con.execute("SELECT * FROM family_facilities").df()
    cols = set(df.columns)
    facs = []
    for r in df.to_dict("records"):
        rid = str(r["RegistryID"])
        lat = lon = geo = None
        if "FacLat" in cols and nn(r.get("FacLat")) is not None and nn(r.get("FacLong")) is not None:
            lat, lon, geo = float(r["FacLat"]), float(r["FacLong"]), "echo"
        else:
            p = zip_point(r.get("FacZip"))
            if p:
                (lat, lon), geo = spread(rid, *p), "zip"
        facs.append({
            "id": rid, "name": nn(r.get("FacName")), "street": nn(r.get("FacStreet")),
            "city": nn(r.get("FacCity")), "state": nn(r.get("FacState")),
            "zip": nn(r.get("FacZip")), "county": nn(r.get("FacCounty")),
            "lat": round(lat, 5) if lat is not None else None,
            "lon": round(lon, 5) if lon is not None else None, "geo": geo,
            "pen": num(r.get("FacTotalPenalties")) or 0, "actions": num(r.get("FacFormalActionCount")) or 0,
            "insp": num(r.get("FacInspectionCount")) or 0, "nc_qtrs": num(r.get("FacQtrsWithNC")),
            "status": nn(r.get("FacComplianceStatus")), "last_insp": nn(r.get("FacDateLastInspection")),
            "last_pen": nn(r.get("FacDateLastPenalty")), "sic": nn(r.get("FacSICDescs")),
            "tier": r["tier"], "entity": nn(r.get("matched_entity")), "review": bool(r["needs_review"]),
            "ex21_url": nn(r.get("ex21_url")), "as_of": nn(r.get("as_of")),
            "echo_url": f"https://echo.epa.gov/detailed-facility-report?fid={rid}",
        })

    chunks = [{"id": c, "type": t, "title": ti, "url": u, "entity": e, "text": x}
              for c, t, ti, u, e, x in con.execute(
                  "SELECT c.chunk_id, d.doc_type, d.title, d.source_url, d.entity_ref, c.text "
                  "FROM chunk c JOIN document d USING (doc_id) ORDER BY c.chunk_id").fetchall()]
    ex21 = [{"name": n, "jurisdiction": j} for n, j in
            con.execute("SELECT name, jurisdiction FROM ex21_entity").fetchall()]
    tiers = {}
    for f in facs:
        t = tiers.setdefault(f["tier"], {"facilities": 0, "penalties": 0})
        t["facilities"] += 1
        t["penalties"] += f["pen"]
    filers = [dict(zip(("cik", "name"), x)) for x in con.execute("SELECT cik, edgar_name FROM filer").fetchall()]
    tenk = con.execute("SELECT DISTINCT source_url, title FROM document WHERE doc_type='10-K' LIMIT 1").fetchone()
    meta = {
        "company": "Dow", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ex21_as_of": facs[0]["as_of"] if facs else None, "filers": filers,
        "tenk": {"url": tenk[0], "title": tenk[1]} if tenk else None,
        "counts": {"facilities": len(facs), "mapped": sum(1 for f in facs if f["lat"] is not None),
                   "chunks": len(chunks), "ex21_entities": len(ex21)},
        "tiers": tiers,
    }
    for name, obj in (("facilities", facs), ("chunks", chunks), ("ex21", ex21), ("meta", meta)):
        (OUT / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
    print(json.dumps(meta["counts"]), json.dumps(tiers))


if __name__ == "__main__":
    main()
