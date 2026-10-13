"""
K Street Influence Tracker — multi-tab dashboard.
Run from project root: streamlit run dashboard/app.py
"""

import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "kstreet.duckdb"

st.set_page_config(page_title="K Street Influence Tracker", layout="wide")
st.title("K Street Influence Tracker")
st.caption("Open-source lobbying analytics · LDA + LobbyView + Congress.gov + MIT Election Lab")

if not DB_PATH.exists():
    st.warning("Database not found. Run the ingestion scripts first.")
    st.stop()

con = duckdb.connect(str(DB_PATH), read_only=True)


def q(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


@st.cache_data
def get_years():
    return q("SELECT DISTINCT filing_year FROM main_marts.mart_filing_bills ORDER BY 1 DESC")["filing_year"].tolist()


@st.cache_data
def get_issue_codes():
    return q("SELECT DISTINCT issue_code FROM main_marts.mart_filing_bills WHERE issue_code IS NOT NULL ORDER BY 1")["issue_code"].tolist()


@st.cache_data
def get_members():
    return q("""
        SELECT DISTINCT sponsor_name, state_po, district, chamber
        FROM main_marts.mart_filing_sponsor_district
        WHERE sponsor_name IS NOT NULL
        ORDER BY sponsor_name
    """)


@st.cache_data
def get_clients():
    return q("""
        SELECT DISTINCT client_name
        FROM main_marts.mart_influence
        WHERE client_name IS NOT NULL
        ORDER BY client_name
    """)["client_name"].tolist()


tab1, tab2, tab3 = st.tabs(["Issue Dashboard", "Member Profile", "Client Profile"])

# ===================== TAB 1: Issue Dashboard =====================
with tab1:
    st.header("Issue Dashboard")

    col1, col2 = st.columns(2)
    with col1:
        years = get_years()
        selected_years = st.multiselect("Year", years, default=years[:2] if years else [])
    with col2:
        issues = get_issue_codes()
        selected_issues = st.multiselect("Issue code", issues)

    year_filter = ""
    if selected_years:
        year_list = ",".join(str(y) for y in selected_years)
        year_filter = f"AND filing_year IN ({year_list})"

    issue_filter = ""
    if selected_issues:
        issue_list = ",".join(f"'{i}'" for i in selected_issues)
        issue_filter = f"AND issue_code IN ({issue_list})"

    st.subheader("Top Clients")
    try:
        top_clients = q(f"""
            SELECT
                client_name,
                SUM(year_spend) as total_spend,
                COUNT(DISTINCT filing_uuid) as filings,
                COUNT(DISTINCT bill_ref_normalized) as bills_mentioned
            FROM main_marts.mart_filing_bills
            WHERE 1=1 {year_filter} {issue_filter}
            GROUP BY 1
            ORDER BY 2 DESC NULLS LAST
            LIMIT 20
        """)
        st.dataframe(top_clients, use_container_width=True)
    except Exception as e:
        st.info(f"Could not load top clients: {e}")

    st.subheader("Top Targeted Members")
    try:
        top_members = q(f"""
            SELECT
                sponsor_name,
                state_po,
                district,
                chamber,
                COUNT(DISTINCT filing_uuid) as filings,
                COUNT(DISTINCT client_name) as clients,
                SUM(year_spend) as total_spend
            FROM main_marts.mart_filing_sponsor_district
            WHERE 1=1 {year_filter}
            GROUP BY 1, 2, 3, 4
            ORDER BY 5 DESC
            LIMIT 20
        """)
        st.dataframe(top_members, use_container_width=True)
    except Exception as e:
        st.info(f"Could not load targeted members: {e}")

    st.subheader("Spend Over Time")
    try:
        spend_time = q(f"""
            SELECT
                filing_year,
                SUM(year_spend) as total_spend,
                COUNT(DISTINCT client_name) as clients,
                COUNT(DISTINCT filing_uuid) as filings
            FROM main_marts.mart_filing_bills
            WHERE 1=1 {year_filter} {issue_filter}
            GROUP BY 1
            ORDER BY 1
        """)
        if not spend_time.empty:
            st.line_chart(spend_time.set_index("filing_year")[["total_spend"]])
            st.dataframe(spend_time, use_container_width=True)
    except Exception as e:
        st.info(f"Could not load spend over time: {e}")

# ===================== TAB 2: Member Profile =====================
with tab2:
    st.header("Member Profile")

    members = get_members()
    if members.empty:
        st.info("No sponsor data available. Run congress_sponsors.py and dbt run.")
    else:
        member_options = members["sponsor_name"].tolist()
        selected_member = st.selectbox("Select member", member_options)

        if selected_member:
            member_row = members[members["sponsor_name"] == selected_member].iloc[0]
            st.write(f"**{selected_member}** · {member_row['chamber']} · {member_row['state_po']}-{member_row['district']}")

            st.subheader("Bills Lobbied")
            try:
                bills = q(f"""
                    SELECT
                        bill_title,
                        bill_ref_normalized,
                        COUNT(DISTINCT client_name) as clients,
                        SUM(year_spend) as total_spend
                    FROM main_marts.mart_filing_sponsor_district
                    WHERE sponsor_name = '{selected_member.replace("'", "''")}'
                    GROUP BY 1, 2
                    ORDER BY 4 DESC NULLS LAST
                    LIMIT 25
                """)
                st.dataframe(bills, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load bills: {e}")

            st.subheader("Top Clients Targeting This Member")
            try:
                clients = q(f"""
                    SELECT
                        client_name,
                        COUNT(DISTINCT filing_uuid) as filings,
                        SUM(year_spend) as total_spend
                    FROM main_marts.mart_filing_sponsor_district
                    WHERE sponsor_name = '{selected_member.replace("'", "''")}'
                    GROUP BY 1
                    ORDER BY 3 DESC NULLS LAST
                    LIMIT 15
                """)
                st.dataframe(clients, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load clients: {e}")

            st.subheader("District Competitiveness")
            try:
                dist = q(f"""
                    SELECT
                        election_year,
                        winner_party,
                        two_party_margin,
                        competitiveness
                    FROM main_marts.mart_filing_sponsor_district
                    WHERE sponsor_name = '{selected_member.replace("'", "''")}'
                      AND election_year IS NOT NULL
                    ORDER BY election_year DESC
                    LIMIT 5
                """)
                if not dist.empty:
                    st.dataframe(dist, use_container_width=True)
                else:
                    st.info("No district competitiveness data for this member.")
            except Exception:
                st.info("District competitiveness not available.")

# ===================== TAB 3: Client Profile =====================
with tab3:
    st.header("Client Profile")

    clients = get_clients()
    if not clients:
        st.info("No client data available.")
    else:
        selected_client = st.selectbox("Select client", clients)

        if selected_client:
            st.subheader("Spend Over Time")
            try:
                spend = q(f"""
                    SELECT
                        filing_year,
                        SUM(total_spend) as total_spend,
                        SUM(filing_count) as filings
                    FROM main_marts.mart_influence
                    WHERE client_name = '{selected_client.replace("'", "''")}'
                    GROUP BY 1
                    ORDER BY 1
                """)
                if not spend.empty:
                    st.line_chart(spend.set_index("filing_year")[["total_spend"]])
                    st.dataframe(spend, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load spend: {e}")

            st.subheader("Issues Lobbied")
            try:
                issues_df = q(f"""
                    SELECT
                        issue_code,
                        COUNT(DISTINCT filing_uuid) as filings,
                        COUNT(DISTINCT bill_ref_normalized) as bills
                    FROM main_marts.mart_filing_bills
                    WHERE client_name = '{selected_client.replace("'", "''")}'
                      AND issue_code IS NOT NULL
                    GROUP BY 1
                    ORDER BY 2 DESC
                    LIMIT 15
                """)
                st.dataframe(issues_df, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load issues: {e}")

            st.subheader("Bills Mentioned")
            try:
                bills = q(f"""
                    SELECT
                        bill_ref_normalized,
                        bill_title,
                        COUNT(*) as mentions,
                        MAX(year_spend) as year_spend
                    FROM main_marts.mart_filing_bills
                    WHERE client_name = '{selected_client.replace("'", "''")}'
                    GROUP BY 1, 2
                    ORDER BY 3 DESC
                    LIMIT 20
                """)
                st.dataframe(bills, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load bills: {e}")

            st.subheader("Members Targeted")
            try:
                members_df = q(f"""
                    SELECT
                        sponsor_name,
                        state_po,
                        district,
                        chamber,
                        COUNT(DISTINCT filing_uuid) as filings
                    FROM main_marts.mart_filing_sponsor_district
                    WHERE client_name = '{selected_client.replace("'", "''")}'
                    GROUP BY 1, 2, 3, 4
                    ORDER BY 5 DESC
                    LIMIT 15
                """)
                st.dataframe(members_df, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load members: {e}")

st.divider()
st.caption("Data: LDA filings · LobbyView · Congress.gov · MIT Election Data Lab")