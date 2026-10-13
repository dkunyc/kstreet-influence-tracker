
# kstreet-influence-tracker

##### Open-source pipeline and dashboard that answers: **who is lobbying on what, who are they targeting, and does it correlate with district competitiveness?**  Built as a portfolio project that mirrors the analytics work done at K Street firms. Uses only free/public data sources and open-source tools.


# K Street Influence Tracker

Open-source data pipeline + dashboard that tracks federal lobbying activity, entity-resolves clients, and joins it to bill outcomes and district-level election results.

Built as a portfolio piece that mirrors the analytics work done at K Street firms (BGR Analytics, FTP, etc.).

## What it does

1. Ingests Senate Lobbying Disclosure Act (LDA) filings via the public API
2. Resolves client names using LobbyView's `lob_id` / `client_uuid` crosswalk
3. Joins to Congress.gov bill metadata
4. Joins to MIT Election Data + Science Lab district-level House returns
5. Links bill sponsors to their district election outcomes
6. Serves a simple Streamlit dashboard and an analysis notebook

## Stack (all free / open source)

- **Ingestion**: Python + `requests`
- **Warehouse**: DuckDB
- **Transforms**: dbt-core
- **Dashboard**: Streamlit
- **Analysis**: Jupyter notebook
- **Orchestration**: GitHub Actions (monthly refresh)

## Quickstart

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Get a free LDA API key
#    https://lda.gov/api/register/

# 3. Run LDA ingestion (example: last 2 years)
export LDA_API_KEY=your_key_here
python ingestion/lda_ingest.py --years 2

# 4. (Recommended) Load LobbyView client crosswalk
#    Sign up free at https://www.lobbyview.org
#    Download the Client Level dataset and save as data/lobbyview_clients.csv
python ingestion/lobbyview_load.py

# 5. Ingest Congress.gov bill metadata
#    Get free key at https://api.congress.gov/sign-up/
export CONGRESS_API_KEY=your_key_here
python ingestion/congress_bills.py --congresses 118 119

# 6. Load MIT Election Lab district-level House returns
#    Download "U.S. House 1976–2024" from:
#    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IG0UN2
#    Save as data/medsl_house_district.csv
python ingestion/medsl_house.py

# 7. Fetch bill sponsors for matched filings
python ingestion/congress_sponsors.py

# 8. Run dbt
cd dbt_project
dbt deps
dbt run
dbt test

# 9. Launch dashboard
cd ../dashboard
streamlit run app.py
```

## Project layout

```
kstreet-influence-tracker/
├── ingestion/          # LDA API + LobbyView + Congress.gov + MEDSL loaders
├── dbt_project/        # dbt models (staging → intermediate → marts)
├── dashboard/          # Streamlit app
├── analysis/           # Jupyter notebook with one finding
└── .github/workflows/  # Scheduled refresh
```

## Data sources

| Source              | License / Access     | Notes                                      |
|---------------------|----------------------|--------------------------------------------|
| LDA API (lda.gov)   | Free key             | Authoritative filings since 1999          |
| LobbyView           | Free signup + download | Best client entity resolution (`lob_id`) |
| Congress.gov        | Free API key         | Bill metadata + sponsors                  |
| MIT Election Lab    | CC0                  | District-level House returns (1976–2024)  |

**Citation required for LobbyView:**  
Kim, In Song (2018). “LobbyView: Firm-level Lobbying & Congressional Bills Database.” Working paper available from https://web.mit.edu/insong/www/pdf/lobbyview.pdf

## Analysis

`analysis/finding_competitiveness.ipynb` asks: *Do clients mentioning specific bills disproportionately spend on sponsors from competitive House districts?*

Run it after the full pipeline has data:
```bash
cd analysis
jupyter notebook finding_competitiveness.ipynb
```

## Next steps

- [x] LDA ingestion
- [x] LobbyView crosswalk loader (CSV + optional API sample)
- [x] Congress.gov bill metadata + free-text bill reference extraction
- [x] MIT Election Lab district-level House returns + competitiveness mart
- [x] Bill sponsor → district election outcome join
- [x] Analysis notebook: spend concentration by district competitiveness
- [ ] Deploy dashboard

## License

MIT
