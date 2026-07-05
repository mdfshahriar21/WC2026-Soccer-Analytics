# WC2026 Player Analytics

An end-to-end data pipeline and interactive dashboard analyzing player performance across FIFA World Cup 2026 matches — built to demonstrate automated PDF data extraction, relational database design, and live data visualization.

## What It Does

FIFA publishes detailed post-match performance reports (PMSR) as PDFs for every World Cup match — covering in-possession distribution stats, out-of-possession defensive actions, and physical performance data (distance, speed, sprints) for every player.

This project automatically extracts that data, structures it into a relational database, and surfaces it through an interactive dashboard with tournament-wide leaderboards.

**Currently tracking:** 47 of 64 matches, 884 unique players, updated daily as new matches are played.
  
## The Pipeline

```
FIFA Match PDFs
      ↓
PDF Text Extraction (pdfplumber)
      ↓
Regex-based Row Parsing & Data Cleaning
      ↓
PostgreSQL Database (normalized schema)
      ↓
Streamlit Dashboard (live queries)
```

## Tech Stack

- **Python** — extraction, parsing, data cleaning
- **pdfplumber** — PDF text extraction
- **PostgreSQL** — relational data storage
- **psycopg2** — database connectivity
- **Streamlit** — interactive web dashboard
- **Plotly** — data visualization
- **Git/GitHub** — version control

## Dashboard Insights

The live dashboard surfaces five tournament-wide leaderboards:

- **⚡ Most Dangerous** — combined attempts at goal + goals scored
- **🏃 Endurance King** — average distance covered per match (km)
- **💨 Speed Star** — highest recorded top speed (km/h)
- **🛡️ Best Defender** — combined tackles won, interceptions, blocks, and clearances
- **🎯 Standout Passer** — highest pass completion percentage (minimum 100 attempts to filter low-volume outliers)

## Engineering Challenges Solved

This project involved real-world data engineering problems beyond simple API consumption:

**PDF Parsing at Scale**
FIFA's match reports are text-based but inconsistently formatted. Built custom regex-based parsing to handle multi-word player names, compound surnames that wrap across lines (e.g., "Nicolas DE LA CRUZ"), and date/header lines that could be mistaken for player data.

**Data Integrity Validation**
Discovered and fixed a token-count mismatch bug where the out-of-possession tackles column (formatted as "X / Y" in source PDFs) was silently misaligning every subsequent column. Built systematic validation queries to catch null values, duplicate records, and physically impossible values (e.g., sprint speeds exceeding human limits) before they reached the dashboard.

**Schema Design**
Designed a normalized schema separating match metadata from player statistics, using `match_code` extracted directly from filenames as a reliable foreign key — avoiding fragile manual ID assignment.

## Known Limitations

- Currently covers 47 of 64 total matches (updated as the tournament progresses)
- Defensive Score reflects total volume of defensive actions, not efficiency — a player under sustained defensive pressure may rank highly without necessarily being the "best" defender in a qualitative sense
- Out-of-possession data parsing was fixed mid-tournament; matches processed before the fix were reloaded to ensure consistency

## Running Locally

```bash
# Clone the repo
git clone https://github.com/mdfshahriar21/WC2026-Soccer-Analytics.git
cd WC2026-Soccer-Analytics

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Configure environment variables
# Create a .env file with:
# DATABASE_URL=your_postgresql_connection_string

# Run the dashboard
streamlit run src/app.py
```

## Project Structure

```
WC2026-Soccer-Analytics/
├── src/
│   ├── extract_pdf.py    # PDF extraction and database loading pipeline
│   └── app.py             # Streamlit dashboard
├── requirements.txt
├── .gitignore
└── README.md
```

## Author

Hi! This is Mohammad Fahim Shahriar and I am a Systems Engineer in the Automotive industry working with Autonomous solutions and I love soccer. I built this as a hands-on project applying data engineering practices — Python, SQL, automated parsing, and validation — to a live, real-world dataset during the 2026 World Cup. Hope you found my insights useful!

Connect on [LinkedIn](https://www.linkedin.com/in/mohammad-fahim-shahriar/) | [GitHub](https://github.com/mdfshahriar21)