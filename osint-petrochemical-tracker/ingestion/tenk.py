"""Download the latest 10-K from SEC EDGAR, turn it into plain text, and store it as chunks.

Needs SEC_USER_AGENT set ("Your Name you@example.com"). Small duplicate of the SEC fetch code in
dow/edgar.py on purpose, so this package does not depend on the notebooks folder.
"""
import os
import re
import time

import requests
from lxml import html as lh

from .documents import add_document

BLOCK = {"p", "div", "tr", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table"}
CELL = {"td", "th"}


def tenk_url(cik, accession: str, primary_doc: str) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{primary_doc}")


def fetch_html(url: str) -> str:
    ua = os.getenv("SEC_USER_AGENT", "")
    if not ua:
        raise RuntimeError("Set SEC_USER_AGENT='Your Name you@example.com' (SEC requires it).")
    time.sleep(0.2)
    r = requests.get(url, headers={"User-Agent": ua}, timeout=120)
    r.raise_for_status()
    return r.content.decode("utf-8", errors="ignore")


def html_to_text(raw: str) -> str:
    """Readable text from a filing. Drops hidden XBRL data and keeps paragraph breaks."""
    raw = re.sub(r"^\s*<\?xml[^>]*\?>", "", raw)
    root = lh.fromstring(raw)
    for el in list(root.iter()):
        t = el.tag.lower() if isinstance(el.tag, str) else ""
        style = (el.get("style") or "").replace(" ", "").lower() if t else ""
        if t in ("script", "style", "ix:header") or "display:none" in style:
            if el.getparent() is not None:
                el.drop_tree()
    for el in root.iter():
        t = el.tag.lower() if isinstance(el.tag, str) else ""
        if t in BLOCK:
            el.text = "\n" + (el.text or "")
            el.tail = "\n" + (el.tail or "")
        elif t in CELL:
            el.tail = " " + (el.tail or "")
    text = root.text_content().replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_10k(con, fetch=None):
    """Add the most recent 10-K in the `filing` table. Returns (doc_id, was_new, n_chunks)."""
    fetch = fetch or fetch_html
    row = con.execute("SELECT cik, accession, filing_date, primary_doc FROM filing "
                      "ORDER BY filing_date DESC LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("The filing table is empty. Run python -m dow.run first.")
    cik, accession, filed, primary = row
    url = tenk_url(cik, accession, primary)
    text = html_to_text(fetch(url))
    doc_id, was_new = add_document(
        con, source="sec_edgar", source_url=url, doc_type="10-K", text=text,
        title=f"Dow 10-K filed {filed}", entity_ref=str(cik), published_date=str(filed),
        size=1500, overlap=200)
    n = con.execute("SELECT count(*) FROM chunk WHERE doc_id = ?", [doc_id]).fetchone()[0]
    return doc_id, was_new, n
