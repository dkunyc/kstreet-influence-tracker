"""
Ingest bill metadata from the Congress.gov API into DuckDB.

Usage:
    export CONGRESS_API_KEY=your_key   # free at https://api.congress.gov/sign-up/
    python ingestion/congress_bills.py --congresses 118 119

API docs: https://github.com/LibraryOfCongress/api.congress.gov
Rate limit: 5,000 requests/hour
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

API_BASE = "https://api.congress.gov/v3"
API_KEY = os.getenv("CONGRESS_API_KEY")
DB_PATH = Path(__file__).parent.parent / "data" / "kstreet.duckdb"
DB_PATH.parent.mkdir(exist_ok=True)

BILL_TYPES = ["hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"]


def get_session() -> requests.Session:
    if not API_KEY:
        raise ValueError("Set CONGRESS_API_KEY environment variable (free at https://api.congress.gov/sign-up/)")
    s = requests.Session()
    return s


def paginate_bills(session: requests.Session, congress: int, bill_type: str) -> Iterator[dict]:
    """Yield bill summary records for a given congress and type."""
    url = f"{API_BASE}/bill/{congress}/{bill_type}"
    params = {"api_key": API_KEY, "format": "json", "limit": 250, "offset": 0}

    while url:
        resp = session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("bills", [])

        next_url = data.get("pagination", {}).get("next")
        if not next_url:
            break
        # Keep the api_key on every page
        url = next_url
        params = {"api_key": API_KEY}
        time.sleep(0.2)

def ingest_bills(congresses):
    session = get_session()
    con = duckdb.connect(str(DB_PATH))

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_bills (
            congress INTEGER,
            bill_type VARCHAR,
            bill_number VARCHAR,
            title VARCHAR,
            origin_chamber VARCHAR,
            latest_action_date DATE,
            latest_action_text VARCHAR,
            update_date TIMESTAMP,
            url VARCHAR,
            PRIMARY KEY (congress, bill_type, bill_number)
        )
    """)

    total = 0
    for congress in congresses:
        for btype in BILL_TYPES:
            print(f"  {congress} / {btype.upper()}...")
            count = 0
            for bill in paginate_bills(session, congress, btype):
                con.execute("""
                    INSERT OR REPLACE INTO raw_bills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    bill.get("congress"),
                    bill.get("type"),
                    str(bill.get("number")),
                    bill.get("title"),
                    bill.get("originChamber"),
                    bill.get("latestAction", {}).get("actionDate"),
                    bill.get("latestAction", {}).get("text"),
                    bill.get("updateDate"),
                    bill.get("url"),
                ])
                count += 1
            print(f"    {count} bills")
            total += count

    print(f"\nDone. Total bills in raw_bills: {con.execute('SELECT COUNT(*) FROM raw_bills').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--congresses", type=int, nargs="+", default=[118, 119],
                        help="Congress numbers to ingest (e.g. 118 119)")
    args = parser.parse_args()
    ingest_bills(args.congresses)
