"""
Load MIT Election Data + Science Lab district-level U.S. House returns.

The constituency-level file (district results, not precinct) is the practical
join target for lobbying analysis. Precinct data exists but is multi-GB.

Download the latest "U.S. House 1976–2024" file from:
  https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IG0UN2

Save it as data/medsl_house_district.csv (or .tab) and run this script.

Citation:
MIT Election Data and Science Lab, 2017, "U.S. House 1976–2024",
https://doi.org/10.7910/DVN/IG0UN2, Harvard Dataverse
"""

from pathlib import Path

import duckdb
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "kstreet.duckdb"

HOUSE_CSV = DATA_DIR / "medsl_house_district" / "medsl_house_district.csv"
HOUSE_TAB = DATA_DIR / "medsl_house_district" / "medsl_house_district.tab"


def load_house_returns():
    path = HOUSE_CSV if HOUSE_CSV.exists() else HOUSE_TAB if HOUSE_TAB.exists() else None
    if path is None:
        print("No MEDSL House district file found.")
        return 0

    print(f"Loading {path}")
    # Try comma first (common for .tab files from Dataverse), then tab
    df = pd.read_csv(path, low_memory=False, sep=",")
    if len(df.columns) == 1:
        print("  Single column — retrying as tab-separated")
        df = pd.read_csv(path, low_memory=False, sep="\t")

    print(f"  Columns: {list(df.columns)[:8]}...")
    print(f"  Rows: {len(df):,}")

    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS raw_medsl_house")
    con.execute("CREATE TABLE raw_medsl_house AS SELECT * FROM df")
    count = con.execute("SELECT COUNT(*) FROM raw_medsl_house").fetchone()[0]
    print(f"Loaded {count:,} rows into raw_medsl_house")
    con.close()
    return count

if __name__ == "__main__":
    load_house_returns()
