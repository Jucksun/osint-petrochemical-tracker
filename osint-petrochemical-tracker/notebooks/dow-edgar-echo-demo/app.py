import duckdb
import streamlit as st

from dow.config import DB_PATH

st.set_page_config(page_title="Dow: EDGAR + ECHO", layout="wide")
st.title("Dow family: SEC EDGAR registrants and EPA ECHO facilities")
st.caption("Links are name matches against the Exhibit 21 subsidiary list, tagged by strength. "
           "ECHO penalties are agency-reported and may be alleged, pending or settled.")

con = duckdb.connect(str(DB_PATH), read_only=True)

st.subheader("SEC registrants (each has its own CIK)")
st.dataframe(con.execute("SELECT * FROM filer").df(), use_container_width=True)
st.dataframe(con.execute("SELECT cik, accession, filing_date FROM filing").df(), use_container_width=True)

df = con.execute("SELECT * FROM family_facilities").df()
tiers = st.sidebar.multiselect("Link confidence", ["ex21_exact", "ex21_prefix", "token_only"],
                               default=["ex21_exact", "ex21_prefix"])
view = df[df["tier"].isin(tiers)]

c1, c2, c3 = st.columns(3)
c1.metric("Facilities shown", len(view))
if "FacTotalPenalties" in view:
    c2.metric("Penalties (selected tiers)", f"${view['FacTotalPenalties'].sum():,.0f}")
c3.metric("Needing review", int(view["needs_review"].sum()))

st.subheader("By link confidence")
if "FacTotalPenalties" in df:
    st.dataframe(df.groupby("tier").agg(facilities=("RegistryID", "nunique"),
                                        penalties=("FacTotalPenalties", "sum")).reset_index(),
                 use_container_width=True)

if {"FacLat", "FacLong"} <= set(view.columns):
    st.map(view.dropna(subset=["FacLat", "FacLong"]), latitude="FacLat", longitude="FacLong")

cols = [c for c in ["FacName", "matched_entity", "tier", "FacCity", "FacState",
                    "FacComplianceStatus", "FacFormalActionCount", "FacTotalPenalties",
                    "ex21_accession", "as_of", "RegistryID"] if c in view.columns]
st.dataframe(view[cols], use_container_width=True)
