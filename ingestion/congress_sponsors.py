"""
Fetch bill sponsors from Congress.gov for bills that appear in matched filings.

Only pulls detail records for bills we already extracted from LDA text,
so the API load stays small.

Usage:
    export CONGRESS_API_KEY=your_key
    python ingestion/congress_sponsors.py
"""

import os
import time
from pathlib import Path

import duckdb
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.congress.gov/v3"
API_KEY = os.getenv("CONGRESS_API_KEY")
DB_PATH = Path(__file__).parent.parent / "data" / "kstreet.duckdb"


def get_session() -> requests.Session:
    if not API_KEY:
        raise ValueError("Set CONGRESS_API_KEY")
    s = requests.Session()
    return s


def fetch_sponsors_for_matched_bills():
    if not DB_PATH.exists():
        print("Database not found. Run prior ingestion steps first.")
        return

    con = duckdb.connect(str(DB_PATH))

    # Bills that were successfully matched from filings
    matched = con.execute("""
        SELECT DISTINCT congress, bill_type, bill_number
        FROM raw_bills
        WHERE congress = 118
        LIMIT 300
    """).fetchall()

    if not matched:
        print("No matched bills found. Run dbt after Congress.gov + LDA ingestion first.")
        con.close()
        return

    print(f"Fetching sponsors for {len(matched)} matched bills...")

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_bill_sponsors (
            congress INTEGER,
            bill_type VARCHAR,
            bill_number VARCHAR,
            bioguide_id VARCHAR,
            full_name VARCHAR,
            party VARCHAR,
            state VARCHAR,
            district INTEGER,
            PRIMARY KEY (congress, bill_type, bill_number, bioguide_id)
        )
    """)

    session = get_session()
    loaded = 0

    for congress, btype, number in matched:
        url = f"{API_BASE}/bill/{congress}/{btype.lower()}/{number}"
        params = {"api_key": API_KEY, "format": "json"}
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json().get("bill", {})
            sponsors = data.get("sponsors", [])
            for s in sponsors:
                con.execute("""
                    INSERT OR REPLACE INTO raw_bill_sponsors
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    congress,
                    btype,
                    number,
                    s.get("bioguideId"),
                    s.get("fullName"),
                    s.get("party"),
                    s.get("state"),
                    s.get("district"),
                ])
                loaded += 1
        except Exception as e:
            print(f"  Error on {congress}/{btype}/{number}: {e}")
        time.sleep(0.15)

    print(f"Loaded {loaded} sponsor records")
    con.close()


if __name__ == "__main__":
    fetch_sponsors_for_matched_bills()
