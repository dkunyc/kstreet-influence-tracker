"""
LDA API ingestion script → DuckDB raw tables.

Usage:
    export LDA_API_KEY=your_key
    python ingestion/lda_ingest.py --years 5

API docs: https://lda.gov/api/redoc/v1/
"""

import os
import time
import argparse
from pathlib import Path
from typing import Iterator

import duckdb
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://lda.gov/api/v1"  # prefer lda.gov; lda.senate.gov sunsets 2026-06-30
API_KEY = os.getenv("LDA_API_KEY")
DB_PATH = Path(__file__).parent.parent / "data" / "kstreet.duckdb"
DB_PATH.parent.mkdir(exist_ok=True)


def get_session() -> requests.Session:
    if not API_KEY:
        raise ValueError("Set LDA_API_KEY environment variable (free key at lda.gov)")
    s = requests.Session()
    s.headers.update({"Authorization": f"Token {API_KEY}"})
    return s


def paginate(session: requests.Session, endpoint: str, params=None) -> Iterator[dict]:
    """Yield all results from a paginated LDA endpoint."""
    url = f"{API_BASE}/{endpoint}/"
    params = params or {}
    params["page_size"] = 100

    while url:
        for attempt in range(3):
            try:
                resp = session.get(url, params=params, timeout=60)
                resp.raise_for_status()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                print(f"    Timeout/connection error (attempt {attempt+1}/3): {e}")
                if attempt == 2:
                    raise
                time.sleep(5)
        data = resp.json()
        yield from data.get("results", [])
        url = data.get("next")
        params = None  # next URL already contains query string
        time.sleep(0.25)  # be nice to the API


def ingest_filings(years: int = 5):
    session = get_session()
    con = duckdb.connect(str(DB_PATH))

    # Create raw table if not exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_filings (
            filing_uuid VARCHAR PRIMARY KEY,
            filing_type VARCHAR,
            filing_year INTEGER,
            filing_period VARCHAR,
            income DOUBLE,
            expenses DOUBLE,
            dt_posted TIMESTAMP,
            registrant_name VARCHAR,
            client_name VARCHAR,
            raw_json JSON
        )
    """)

    print(f"Ingesting filings for last {years} years...")
    count = 0
    for year in range(2025 - years + 1, 2026):  # adjust as needed
        print(f"  Year {year}...")
        for filing in paginate(session, "filings", {"filing_year": year}):
            con.execute("""
                INSERT OR REPLACE INTO raw_filings
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                filing.get("filing_uuid"),
                filing.get("filing_type"),
                filing.get("filing_year"),
                filing.get("filing_period"),
                filing.get("income"),
                filing.get("expenses"),
                filing.get("dt_posted"),
                filing.get("registrant", {}).get("name") if isinstance(filing.get("registrant"), dict) else None,
                filing.get("client", {}).get("name") if isinstance(filing.get("client"), dict) else None,
                filing,  # store full JSON for later parsing
            ])
            count += 1
            if count % 500 == 0:
                print(f"    {count} filings loaded...")

    print(f"Done. Total filings in raw_filings: {con.execute('SELECT COUNT(*) FROM raw_filings').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5, help="Number of years to pull")
    args = parser.parse_args()
    ingest_filings(args.years)
