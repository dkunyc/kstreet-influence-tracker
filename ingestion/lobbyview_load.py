"""
Load LobbyView client entity resolution data into DuckDB.

LobbyView provides the best public `lob_id` / client_uuid crosswalk for
deduplicating client names across LDA filings (Apple vs Apple Computer, etc.).

Two ways to get the data (both free):

1. Manual bulk download (recommended for full coverage):
   - Sign up at https://www.lobbyview.org
   - Download the "Client Level" or "Report Level" dataset
   - Place the CSV at data/lobbyview_clients.csv (or report_level.csv)
   - Run this script

2. Optional API (rate-limited, good for sampling):
   - Get a token from the LobbyView site after login
   - export LOBBYVIEW_TOKEN=your_token
   - pip install lobbyview
   - This script will fall back to a small API sample if no CSV is present

Citation (required for any public use):
Kim, In Song (2018). "LobbyView: Firm-level Lobbying & Congressional Bills Database."
Working paper: https://web.mit.edu/insong/www/pdf/lobbyview.pdf
"""

import os
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "kstreet.duckdb"

CLIENT_CSV = DATA_DIR / "clients_codebook" / "clients.csv"
REPORT_CSV = DATA_DIR / "reports_codebook" / "reports.csv"
BILLS_CSV = DATA_DIR / "bills_codebook" / "bills.csv"
ISSUE_TEXT_CSV = DATA_DIR / "issue_text_codebook" / "issue_text.csv"
ISSUES_CSV = DATA_DIR / "issues_codebook" / "issues.csv"
NETWORK_CSV = DATA_DIR / "network_codebook" / "network.csv"


def load_csv_to_table(con: duckdb.DuckDBPyConnection, path: Path, table: str) -> int:
    """Load a CSV into a DuckDB table if the file exists."""
    if not path.exists():
        return 0
    print(f"Loading {path.name} → {table}")
    df = pd.read_csv(path, low_memory=False)
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {count:,} rows")
    return count


def load_from_csv(con: duckdb.DuckDBPyConnection) -> int:
    """Load all available LobbyView codebooks."""
    total = 0
    total += load_csv_to_table(con, CLIENT_CSV, "raw_lobbyview_clients")
    total += load_csv_to_table(con, REPORT_CSV, "raw_lobbyview_reports")
    total += load_csv_to_table(con, BILLS_CSV, "raw_lobbyview_bills")
    total += load_csv_to_table(con, ISSUE_TEXT_CSV, "raw_lobbyview_issue_text")
    total += load_csv_to_table(con, ISSUES_CSV, "raw_lobbyview_issues")
    total += load_csv_to_table(con, NETWORK_CSV, "raw_lobbyview_network")
    return total

    if REPORT_CSV.exists():
        print(f"Loading report-level data from {REPORT_CSV}")
        df = pd.read_csv(REPORT_CSV, low_memory=False)
        con.execute("DROP TABLE IF EXISTS raw_lobbyview_reports")
        con.execute("CREATE TABLE raw_lobbyview_reports AS SELECT * FROM df")
        count = con.execute("SELECT COUNT(*) FROM raw_lobbyview_reports").fetchone()[0]
        print(f"Loaded {count:,} report records")
        return count

    return 0


def load_from_api_sample(con: duckdb.DuckDBPyConnection) -> int:
    """Optional: pull a small sample via the lobbyview package if token is set."""
    token = os.getenv("LOBBYVIEW_TOKEN")
    if not token:
        return 0

    try:
        from LobbyView import LobbyView  # type: ignore
    except ImportError:
        print("lobbyview package not installed. Run: pip install lobbyview")
        return 0

    print("Fetching small client sample via LobbyView API...")
    lv = LobbyView(token)
    # Pull a limited page of clients (API is rate-limited)
    result = lv.clients(page=1)
    if not result or not result.data:
        print("No data returned from API")
        return 0

    df = pd.DataFrame(result.data)
    con.execute("DROP TABLE IF EXISTS raw_lobbyview_clients")
    con.execute("CREATE TABLE raw_lobbyview_clients AS SELECT * FROM df")
    count = len(df)
    print(f"Loaded {count} client records from API sample")
    return count


def main():
    con = duckdb.connect(str(DB_PATH))

    loaded = load_from_csv(con)
    if loaded == 0:
        loaded = load_from_api_sample(con)

    if loaded == 0:
        print("\nNo LobbyView data found.")
        print("To proceed:")
        print("  1. Sign up free at https://www.lobbyview.org")
        print("  2. Download the Client Level dataset")
        print(f"  3. Save it as {CLIENT_CSV}")
        print("  4. Re-run this script")
        print("\nAlternatively set LOBBYVIEW_TOKEN and pip install lobbyview for a small API sample.")
    else:
        print(f"\nLobbyView data ready in DuckDB at {DB_PATH}")

    con.close()


if __name__ == "__main__":
    main()
