"""EPA ECHO facility name search."""
import time

import pandas as pd
import requests

BASE = "https://echodata.epa.gov/echo/echo_rest_services"
NUMERIC = ["FacLat", "FacLong", "FacTotalPenalties", "FacInspectionCount",
           "FacFormalActionCount", "FacQtrsWithNC"]


def search_name(name: str, active_only=True, limit=500) -> pd.DataFrame:
    params = {"output": "JSON", "p_fn": name, "responseset": 100}
    if active_only:
        params["p_act"] = "Y"
    r = requests.get(f"{BASE}.get_facilities", params=params, timeout=60)
    r.raise_for_status()
    res = r.json()["Results"]
    if "Error" in res:
        raise RuntimeError(res["Error"].get("ErrorMessage", "ECHO error"))
    qid, total = res["QueryID"], int(res.get("QueryRows", 0))
    rows, page = [], 1
    while len(rows) < min(total, limit):
        r = requests.get(f"{BASE}.get_qid",
                         params={"qid": qid, "pageno": page, "output": "JSON"}, timeout=60)
        r.raise_for_status()
        facs = r.json()["Results"].get("Facilities", [])
        if not facs:
            break
        rows += facs
        page += 1
    df = pd.DataFrame(rows[:limit])
    df["source_query"] = name
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    for c in NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[$,]", "", regex=True),
                                  errors="coerce")
    return df


def collect(queries: list[str], active_only=True) -> pd.DataFrame:
    frames = []
    for q in queries:
        try:
            frames.append(search_name(q, active_only))
        except Exception as e:  # one bad query should not sink the run
            print(f"ECHO query {q!r} failed: {e}")
        time.sleep(0.3)
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="RegistryID")  # first query wins
    return clean(df)
