
#Petrochemical OSINT starter, EPA ECHO
import requests
import pandas as pd
import streamlit as st

BASE = "https://echodata.epa.gov/echo/echo_rest_services"

st.set_page_config(page_title="Petrochem OSINT", layout="wide")
st.title("Petrochemical OSINT: EPA ECHO explorer")


company = st.sidebar.text_input("Facility / company name contains", "DOW CHEMICAL")
state = st.sidebar.text_input("State (2-letter, blank = all)", "MI").upper()
max_rows = st.sidebar.slider("Max facilities to load", 20, 500, 100, step=20)



@st.cache_data(ttl=3600, show_spinner="Querying EPA ECHO...")
def fetch_facilities(name: str, st_code: str, limit: int):
    params = {"output": "JSON", "p_fn": name, "p_act": "Y", "responseset": 100}
    if st_code:
        params["p_st"] = st_code

    # Step 1 run the search which returns a QueryID
    r = requests.get(f"{BASE}.get_facilities", params=params, timeout=30)
    r.raise_for_status()
    results = r.json()["Results"]
    if "Error" in results:
        raise RuntimeError(results["Error"].get("ErrorMessage", "ECHO error"))
    qid = results["QueryID"]
    total = int(results.get("QueryRows", 0))

    # Step 2 results using the QueryID
    rows, page = [], 1
    while len(rows) < min(total, limit):
        r = requests.get(
            f"{BASE}.get_qid",
            params={"qid": qid, "pageno": page, "output": "JSON"},
            timeout=30,
        )
        r.raise_for_status()
        facs = r.json()["Results"].get("Facilities", [])
        if not facs:
            break
        rows += facs
        page += 1
    return pd.DataFrame(rows[:limit]), total


try:
    df, total = fetch_facilities(company, state, max_rows)
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

if df.empty:
    st.warning("No facilities found. Try a shorter name like 'DOW' or clear the state.")
    st.stop()


# Field names below come from ECHO's facility search. If a column is missing,
numeric_cols = [
    "FacLat", "FacLong", "FacTotalPenalties", "FacInspectionCount",
    "FacFormalActionCount", "FacQtrsWithNC",
]
for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

 
st.caption(f"ECHO found {total} matching facilities; showing {len(df)}.")
m1, m2, m3 = st.columns(3)
m1.metric("Facilities loaded", len(df))
if "FacTotalPenalties" in df.columns:
    m2.metric("Total penalties", f"${df['FacTotalPenalties'].sum():,.0f}")
if "FacFormalActionCount" in df.columns:
    m3.metric("Formal enforcement actions", int(df["FacFormalActionCount"].sum()))


if {"FacLat", "FacLong"} <= set(df.columns):
    st.subheader("Facility locations")
    st.map(df.dropna(subset=["FacLat", "FacLong"]), latitude="FacLat", longitude="FacLong")


if {"FacName", "FacTotalPenalties"} <= set(df.columns):
    st.subheader("Top facilities by total penalties")
    top = df.nlargest(15, "FacTotalPenalties").set_index("FacName")["FacTotalPenalties"]
    st.bar_chart(top)


st.subheader("Facility table")
show = [
    c for c in [
        "FacName", "FacCity", "FacState", "FacComplianceStatus",
        "FacInspectionCount", "FacFormalActionCount", "FacQtrsWithNC",
        "FacTotalPenalties", "FacDateLastInspection", "RegistryID",
    ] if c in df.columns
]
st.dataframe(df[show], use_container_width=True)

with st.expander("Raw columns (for debugging field names)"):
    st.write(list(df.columns))
