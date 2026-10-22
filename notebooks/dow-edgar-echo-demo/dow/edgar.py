"""SEC EDGAR: filer identity, latest 10-K, and the Exhibit 21 subsidiary list."""
import re
import time
from io import StringIO

import pandas as pd
import requests

from .config import SEC_USER_AGENT


def _get(url: str):
    if not SEC_USER_AGENT:
        raise RuntimeError("Set SEC_USER_AGENT='Your Name you@example.com' (SEC requires it).")
    time.sleep(0.2)  # stay well under SEC's 10 requests/second limit
    r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r


def submissions(cik: int) -> dict:
    return _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()


def latest_10k(sub: dict) -> dict | None:
    rec = sub["filings"]["recent"]
    for i, form in enumerate(rec["form"]):
        if form == "10-K":
            return {"accession": rec["accessionNumber"][i], "filing_date": rec["filingDate"][i],
                    "primary_doc": rec["primaryDocument"][i]}
    return None


def find_exhibit21_url(cik: int, accession: str) -> str:
    nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}"
    items = _get(f"{base}/index.json").json()["directory"]["item"]
    names = [it["name"] for it in items]
    for n in names:
        if re.search(r"ex[-_]?21", n, re.I) and n.lower().endswith((".htm", ".html")):
            return f"{base}/{n}"
    raise RuntimeError(f"No Exhibit 21 file found in {base}. Files: {names}")


def parse_exhibit21(html: str) -> pd.DataFrame:
    """Return columns name, jurisdiction from an Exhibit 21 HTML table."""
    rows = []
    for t in pd.read_html(StringIO(html)):
        for _, r in t.iterrows():
            cells = [str(c).strip() for c in r.tolist()
                     if str(c).strip() and str(c).strip().lower() != "nan"]
            cells = list(dict.fromkeys(cells))  # merged cells repeat
            if len(cells) < 2:
                continue
            if re.search(r"jurisdiction|name of subsidiary|subsidiar", cells[0] + cells[-1], re.I):
                continue
            rows.append({"name": cells[0], "jurisdiction": cells[-1]})
    return pd.DataFrame(rows, columns=["name", "jurisdiction"]).drop_duplicates()


def collect(ciks: list[int]):
    """Return (filers, filings, ex21) DataFrames for the given registrant CIKs."""
    filers, filings, ex21 = [], [], pd.DataFrame()
    for cik in ciks:
        sub = submissions(cik)
        filers.append({"cik": cik, "edgar_name": sub["name"], "sic": sub.get("sic"),
                       "sic_description": sub.get("sicDescription"),
                       "former_names": "; ".join(f["name"] for f in sub.get("formerNames", []))})
        k = latest_10k(sub)
        if k:
            filings.append({"cik": cik, **k})
    filings = pd.DataFrame(filings)
    if not filings.empty:
        # Combined filings appear under several CIKs with the SAME accession number.
        first = filings.sort_values("filing_date").iloc[-1]
        url = find_exhibit21_url(int(first["cik"]), first["accession"])
        ex21 = parse_exhibit21(_get(url).text)
        ex21["source_url"], ex21["accession"] = url, first["accession"]
        ex21["as_of"] = first["filing_date"]
    return pd.DataFrame(filers), filings, ex21
