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

def fmt_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Format spend columns with $ and commas."""
    out = df.copy()
    for col in out.columns:
        if "spend" in col.lower():
            out[col] = out[col].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "")
    return out

@st.cache_data
def get_years():
    return q("SELECT DISTINCT filing_year FROM main_marts.mart_filing_bills ORDER BY 1 DESC")["filing_year"].tolist()


@st.cache_data
def get_issue_codes():
    return q("""
        SELECT
            i.issue_code,
            coalesce(d.issue_description, i.issue_code) as issue_label
        FROM (
            SELECT DISTINCT issue_code
            FROM main_marts.mart_filing_bills
            WHERE issue_code IS NOT NULL
        ) i
        LEFT JOIN main_staging.stg_issue_codes d
            ON i.issue_code = d.issue_code
        ORDER BY 2
    """)

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
        issues_df = get_issue_codes()
        issue_options = issues_df["issue_label"].tolist()
        selected_labels = st.multiselect("Issue", issue_options)
        selected_issues = issues_df.loc[
            issues_df["issue_label"].isin(selected_labels), "issue_code"
        ].tolist()

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
                MAX(year_spend) as annual_spend,
                COUNT(DISTINCT filing_uuid) as filings,
                COUNT(DISTINCT bill_ref_normalized) as bills_mentioned
            FROM main_marts.mart_filing_bills
            WHERE 1=1 {year_filter} {issue_filter}
            GROUP BY 1
            ORDER BY 2 DESC NULLS LAST
            LIMIT 20
        """)
        st.dataframe(fmt_spend(top_clients), use_container_width=True)
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
                COUNT(DISTINCT client_name) as clients
            FROM main_marts.mart_filing_sponsor_district
            WHERE 1=1 {year_filter}
            GROUP BY 1, 2, 3, 4
            ORDER BY 5 DESC
            LIMIT 20
        """)
        st.dataframe(fmt_spend(top_members), use_container_width=True)
    except Exception as e:
        st.info(f"Could not load targeted members: {e}")


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
                        s.bill_title,
                        s.bill_ref_normalized,
                        coalesce(d.issue_description, b.issue_code) as issue,
                        s.sponsor_party,
                        s.competitiveness,
                        s.two_party_margin,
                        COUNT(DISTINCT s.client_name) as clients
                    FROM main_marts.mart_filing_sponsor_district s
                    LEFT JOIN main_marts.mart_filing_bills b
                        ON s.bill_ref_normalized = b.bill_ref_normalized
                       AND s.filing_uuid = b.filing_uuid
                    LEFT JOIN main_staging.stg_issue_codes d
                        ON b.issue_code = d.issue_code
                    WHERE s.sponsor_name = '{selected_member.replace("'", "''")}'
                    GROUP BY 1, 2, 3, 4, 5, 6
                    ORDER BY 7 DESC
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
                        MAX(year_spend) as annual_spend
                    FROM main_marts.mart_filing_sponsor_district
                    WHERE sponsor_name = '{selected_member.replace("'", "''")}'
                    GROUP BY 1
                    ORDER BY 3 DESC NULLS LAST
                    LIMIT 15
                """)
                st.dataframe(fmt_spend(clients), use_container_width=True)
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
        client_search = st.text_input("Filter clients", "")
        if client_search:
            filtered = [c for c in clients if client_search.upper() in c.upper()]
        else:
            filtered = clients

        if not filtered:
            st.info("No clients match.")
            selected_clients = []
        else:
            selected_clients = st.multiselect("Select client(s)", filtered)

        if selected_clients:
            client_list = ",".join(
                f"'{c.replace(chr(39), chr(39)+chr(39))}'" for c in selected_clients
            )
            client_filter = f"AND client_name IN ({client_list})"

            st.subheader("Spend by Client")
            try:
                spend_df = q(f"""
                    WITH filing_spend AS (
                        SELECT
                            filing_uuid,
                            COALESCE(income, 0) + COALESCE(expenses, 0) as spend
                        FROM raw_filings
                    ),
                    client_filings AS (
                        SELECT DISTINCT
                            i.client_name,
                            i.filing_uuid
                        FROM main_marts.mart_filing_bills i
                        WHERE i.client_name IN ({client_list})
                    )
                    SELECT
                        cf.client_name,
                        COUNT(DISTINCT cf.filing_uuid) as filings,
                        SUM(fs.spend) as total_spend
                    FROM client_filings cf
                    LEFT JOIN filing_spend fs ON cf.filing_uuid = fs.filing_uuid
                    GROUP BY cf.client_name
                    ORDER BY 3 DESC NULLS LAST
                """)
                if not spend_df.empty:
                    total = pd.DataFrame([{
                        "client_name": "TOTAL",
                        "filings": spend_df["filings"].sum(),
                        "total_spend": spend_df["total_spend"].sum()
                    }])
                    display = pd.concat([spend_df, total], ignore_index=True)
                    st.dataframe(fmt_spend(display), use_container_width=True)
                else:
                    st.info("No spend data for selected clients.")
            except Exception as e:
                st.info(f"Could not load spend: {e}")

            st.subheader("Issues Lobbied")
            try:
                issues_df = q(f"""
                    SELECT
                        coalesce(d.issue_description, i.issue_code) as issue,
                        COUNT(DISTINCT i.filing_uuid) as filings,
                        COUNT(DISTINCT i.bill_ref_normalized) as bills
                    FROM main_marts.mart_filing_bills i
                    LEFT JOIN main_staging.stg_issue_codes d
                        ON i.issue_code = d.issue_code
                    WHERE 1=1 {client_filter}
                      AND i.issue_code IS NOT NULL
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
                        b.bill_ref_normalized,
                        b.bill_title,
                        coalesce(d.issue_description, b.issue_code) as issue,
                        s.sponsor_name,
                        s.sponsor_party,
                        s.competitiveness,
                        COUNT(*) as mentions
                    FROM main_marts.mart_filing_bills b
                    LEFT JOIN main_staging.stg_issue_codes d
                        ON b.issue_code = d.issue_code
                    LEFT JOIN main_marts.mart_filing_sponsor_district s
                        ON b.bill_ref_normalized = s.bill_ref_normalized
                    WHERE 1=1 AND b.client_name IN ({client_list})
                    GROUP BY 1, 2, 3, 4, 5, 6
                    ORDER BY 7 DESC
                    LIMIT 20
                """)
                st.dataframe(fmt_spend(bills), use_container_width=True)
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
                    WHERE 1=1 {client_filter}
                    GROUP BY 1, 2, 3, 4
                    ORDER BY 5 DESC
                    LIMIT 15
                """)
                st.dataframe(members_df, use_container_width=True)
            except Exception as e:
                st.info(f"Could not load members: {e}")

st.divider()
st.caption("Data: LDA filings · LobbyView · Congress.gov · MIT Election Data Lab")