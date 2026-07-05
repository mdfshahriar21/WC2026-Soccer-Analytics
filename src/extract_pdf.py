import pdfplumber
import pandas as pd
import re
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

# Name corrections for known PDF extraction merges
NAME_CORRECTIONS = {
    'FERNANDEZPARDO': 'FERNANDEZ PARDO',
    'THOMASASANTE': 'THOMAS ASANTE', 
    'OKONENGSTLER': 'OKON ENGSTLER',
    'WANBISSAKA': 'WAN BISSAKA',
    'GANNONDOAK': 'GANNON DOAK',
}

def fix_player_name(name):
    """Fix known name merging issues from PDF extraction"""
    # Check full name against corrections dict
    parts = name.strip().split()
    corrected = []
    for part in parts:
        corrected.append(NAME_CORRECTIONS.get(part, part))
    return ' '.join(corrected)

load_dotenv('/home/mystic31/WC2026-Soccer-Analytics/.env')
def clean_player_name(name):
    """Remove extra spaces and standardise player name for merging"""
    return ' '.join(name.strip().split())

def prepare_for_merge(df):
    """Ensure jersey_number and player_name are clean strings; returns empty DataFrame if input is empty."""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df['jersey_number'] = df['jersey_number'].astype(str).str.strip()
    df['player_name'] = df['player_name'].astype(str).apply(clean_player_name)
    return df
# Debug – print the password (remove this after testing)
print("DB_PASSWORD:", os.getenv('DB_PASSWORD'))
print("DB_USER:", os.getenv('DB_USER'))
print("DB_PASSWORD length:", len(os.getenv('DB_PASSWORD', '')))

# Build connection string from environment variables
CONN_STRING = os.getenv('DATABASE_URL')
# ====================================================
# DEBUG MODE
# ====================================================
#DEBUG = True

# ====================================================
# COLUMN DEFINITIONS (same as before)
# ====================================================

IN_POSSESSION_COLS = [
    'jersey_number', 'player_name',
    'passes_attempted', 'passes_completed', 'pass_completion_pct',
    'switches_of_play', 'crosses_attempted', 'crosses_completed',
    'line_breaks_attempted', 'line_breaks_completed', 'line_break_completion_pct',
    'ball_progressions', 'take_ons', 'step_ins', 'attempts_at_goal', 'goals'
]

OUT_OF_POSSESSION_COLS = [
    'jersey_number', 'player_name',
    'tackles_made', 'tackles_won',
    'blocks', 'interceptions', 'pressing_direct', 'pressing_indirect',
    'duels_won_aerial', 'duels_won_physical', 'possession_contests_won',
    'clearances', 'loose_ball_receptions', 'pushing_on',
    'pushing_on_into_pressing', 'possession_regains', 'possession_interrupted'
]

PHYSICAL_COLS = [
    'jersey_number', 'player_name',
    'total_distance_m', 'zone_1_0_7_kmh_m', 'zone_2_7_15_kmh_m',
    'zone_3_15_20_kmh_m', 'zone_4_20_25_kmh_m', 'zone_5_25_plus_kmh_m',
    'high_speed_runs_zone_3', 'sprints_zone_4_and_5', 'top_speed_kmh'
]

# ====================================================
# HELPERS – match metadata extraction
# ====================================================

def extract_match_metadata(first_page_text):
    """Extract match_code_str, date, venue, home_team, away_team, stage, scores."""
    meta = {
        'match_code_str': None,
        'match_date': None,
        'venue': None,
        'home_team': None,
        'away_team': None,
        'home_score': None,
        'away_score': None,
        'stage': None,
    }
    lines = first_page_text.split('\n')
    if not lines:
        return meta

    # Match Code / Stage: "Group A - Match 1"
    stage_pattern = re.compile(r'Group\s*([A-Z])\s*[-–]\s*Match\s*(\d+)', re.IGNORECASE)
    for line in lines:
        m = stage_pattern.search(line)
        if m:
            meta['stage'] = f"Group {m.group(1).upper()} Match {m.group(2)}"
            meta['match_code_str'] = f"{m.group(1).upper()}{m.group(2)}"
            break

    # Date and venue: "11 June 2026 - Mexico City Stadium - 13:00"
    # We'll extract date and venue from first line that looks like that.
    date_venue_pattern = re.compile(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*[-–]\s*(.+?)(?:\s*[-–]\s*\d{1,2}:\d{2})?$')
    for line in lines:
        m = date_venue_pattern.search(line)
        if m:
            meta['match_date'] = m.group(1).strip()
            meta['venue'] = m.group(2).strip()
            break

    # Teams and scores: might be in the first page as well.
    # We can also get them from the table headings, but we'll try to parse from title.
    # Usually the PDF filename contains "MEX-V-RSA" etc. We'll parse from filename later.
    # Alternatively, we can get teams from the 'In Possession - Distributions [Team]' headings.
    # For now, we'll set them later from the team_data keys.
    return meta

def find_heading_pages(pdf, pattern):
    results = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            match = re.search(pattern, text)
            if match:
                team = match.group(1).strip()
                results.append((team, i))
    return results

# ====================================================
# STATS PARSERS (unchanged)
# ====================================================

def parse_in_possession_stats(tokens):
    if len(tokens) != 14:
        if len(tokens) < 14:
            tokens += [''] * (14 - len(tokens))
        else:
            tokens = tokens[:14]
    return tokens

def parse_out_of_possession_stats(tokens):
    # Remove standalone slash tokens
    tokens = [t for t in tokens if t != '/']

    # If the first token contains a slash (e.g., "0/0"), split it
    if tokens and '/' in tokens[0]:
        parts = tokens[0].split('/')
        if len(parts) == 2:
            tokens = [parts[0], parts[1]] + tokens[1:]
        else:
            # fallback: treat as made only
            tokens = [parts[0]] + tokens[1:]

    # Now tokens should be [made, won, 13 stats...]
    if len(tokens) < 15:
        tokens += [''] * (15 - len(tokens))
    else:
        tokens = tokens[:15]

    try:
        made = int(str(tokens[0])) if str(tokens[0]).isdigit() else 0
    except:
        made = 0
    try:
        won = int(str(tokens[1])) if str(tokens[1]).isdigit() else 0
    except:
        won = 0

    rest = tokens[2:15]  # exactly 13 stats
    return [made, won] + rest

def parse_physical_stats(tokens):
    """
    Parse physical stats tokens. First attempts the private‑use character mapping.
    If that fails (most values are None), fall back to regex extraction of numbers.
    Returns a list of 9 floats (or None for missing values).
    """
    def convert_token(tok):
        if not tok:
            return None
        digits = []
        for ch in tok:
            code = ord(ch)
            # Map private‑use characters to digits/decimal
            if 0xE071 <= code <= 0xE07A:
                digits.append(str(code - 0xE071))
            elif code == 0xE094:
                digits.append('.')
        num_str = ''.join(digits)
        if num_str == '' or num_str == '.':
            return None
        try:
            return float(num_str)
        except ValueError:
            return None

    # First, try the mapping approach
    mapped = [convert_token(tok) for tok in tokens]
    # Count how many are not None
    valid_count = sum(1 for x in mapped if x is not None)
    if valid_count >= 5:
        # Mapping worked reasonably well; pad/trim to 9
        if len(mapped) < 9:
            mapped += [None] * (9 - len(mapped))
        else:
            mapped = mapped[:9]
        return mapped

    # Fallback: join tokens and extract all numbers using regex
    text = ' '.join(tokens)
    # Find all floating point numbers (including integers)
    numbers = re.findall(r'(\d+\.?\d*)', text)
    if not numbers:
        return [None] * 9
    # Convert to float and take first 9
    nums = [float(n) for n in numbers[:9]]
    if len(nums) < 9:
        nums += [None] * (9 - len(nums))
    return nums

# ====================================================
# GENERIC EXTRACTOR (unchanged)
# ====================================================

def extract_generic(pdf, page_index, columns, stats_parser_func, table_name="", num_stats=None):
    # Allow override of number of stat tokens
    if num_stats is None:
        num_stats = len(columns) - 2

    page = pdf.pages[page_index]
    text = page.extract_text()
    if not text:
        return pd.DataFrame(columns=columns)

    lines = text.split('\n')
    MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']

    # Step 1: Build merged lines, filtering out date headers early
    merged_lines = []
    current_line = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        if len(tokens) < 2:
            continue

        # 🔴 CRITICAL: Filter date lines BEFORE merge logic
        if (tokens[0].isdigit() and tokens[1] in MONTH_NAMES):
            continue   # skip "11 June 2026", "13 June 2026", etc.

        # Now handle player rows and continuations
        if tokens[0].isdigit():
            # Starting a new player row
            if current_line is not None:
                merged_lines.append(current_line)
            current_line = line
        else:
            # Continuation line (part of previous player's name)
            if current_line is not None:
                current_line += " " + line
            else:
                # Shouldn't happen, but just in case
                current_line = line

    # Don't forget the last line
    if current_line is not None:
        merged_lines.append(current_line)

    # Step 2: Process merged lines
    rows = []
    # num_stats is now set above

    for line in merged_lines:
        tokens = line.split()
        if len(tokens) < 2:
            continue
        if not tokens[0].isdigit():
            continue

        # Additional safety: skip any remaining month lines (unlikely)
        if len(tokens) > 1 and tokens[1] in MONTH_NAMES:
            continue

        if len(tokens) < 1 + num_stats:
            continue

        stats_tokens = tokens[-num_stats:]
        name_tokens = tokens[1:-num_stats] if num_stats > 0 else tokens[1:]
        if not name_tokens:
            continue
        name = ' '.join(name_tokens)

        parsed_stats = stats_parser_func(stats_tokens)
        if parsed_stats is None or len(parsed_stats) == 0:
            continue

        row = [tokens[0], name] + parsed_stats
        if len(row) != len(columns):
            if len(row) < len(columns):
                row += [''] * (len(columns) - len(row))
            else:
                row = row[:len(columns)]
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)

    if DEBUG and not df.empty:
        print(f"\nDEBUG: First row of {table_name}:")
        for col in df.columns:
            print(f"  {col}: {df.iloc[0][col]}")
    
    if table_name == "out_of_possession":
        print("\n--- First 5 merged lines for out_of_possession ---")
        for line in merged_lines[:5]:
            print(line)
        print("--- end ---")

    # Post‑processing: convert numeric columns
    for col in df.columns:
        if col in ['jersey_number', 'player_name']:
            continue
        if col in ['tackles_made', 'tackles_won']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            continue
        if col in ['pass_completion_pct', 'line_break_completion_pct']:
            df[col] = df[col].astype(str).str.replace('%', '', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    print(f"{table_name} extracted {len(df)} rows from page {page_index}")

    return df
# ====================================================
# PROCESS ONE PDF – now returns match_meta and player_df
# ====================================================

def process_one_pdf(pdf_path):
    base = os.path.basename(pdf_path)
    match_code_match = re.search(r'PMSR-M(\d+)-', base)
    match_code = f"M{match_code_match.group(1)}" if match_code_match else None
    if not match_code:
        print(f"Warning: Could not extract match_code from {base}, skipping.")
        return pd.DataFrame(), {}

    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text()
        meta = extract_match_metadata(first_page_text)
        meta['match_code'] = match_code

        # Locate table pages
        in_pages = find_heading_pages(pdf, r'(?i)In Possession - Distributions\s+(.+)')
        out_pages = find_heading_pages(pdf, r'(?i)Out of Possession\s+(.+)')
        phys_pages = find_heading_pages(pdf, r'(?i)Physical Data\s+(.+)')

        print(f"In pages: {in_pages}")
        print(f"Out pages: {out_pages}")
        print(f"Phys pages: {phys_pages}")

        team_data = {}

        for team, page in in_pages:
            team_data.setdefault(team, {})['in'] = extract_generic(
                pdf, page, IN_POSSESSION_COLS, parse_in_possession_stats, "in_possession", num_stats=14
            )

        for team, page in out_pages:
            team_data.setdefault(team, {})['out'] = extract_generic(
                pdf, page, OUT_OF_POSSESSION_COLS, parse_out_of_possession_stats, "out_of_possession", num_stats=16
            )

        for team, page in phys_pages:
            team_data.setdefault(team, {})['phys'] = extract_generic(
                pdf, page, PHYSICAL_COLS, parse_physical_stats, "physical", num_stats=9
            )

        # Determine home/away teams
        teams = list(team_data.keys())
        if len(teams) >= 2:
            meta['home_team'] = teams[0]
            meta['away_team'] = teams[1]
        else:
            meta['home_team'] = teams[0] if teams else None
            meta['away_team'] = None

        # Merge per team
        all_teams_dfs = []
        for team, dfs in team_data.items():
            print(f"\n--- Merging data for team: {team} ---")

            # Clean each component
            in_df = prepare_for_merge(dfs.get('in', pd.DataFrame()))
            out_df = prepare_for_merge(dfs.get('out', pd.DataFrame()))
            phys_df = prepare_for_merge(dfs.get('phys', pd.DataFrame()))

            # Debug: show shapes and columns
            print(f"in_df shape: {in_df.shape}, columns: {in_df.columns.tolist()}")
            print(f"out_df shape: {out_df.shape}, columns: {out_df.columns.tolist() if not out_df.empty else 'empty'}")
            print(f"phys_df shape: {phys_df.shape}, columns: {phys_df.columns.tolist() if not phys_df.empty else 'empty'}")

            # Start with in_possession if available
            if not in_df.empty:
                combined = in_df
            else:
                combined = out_df if not out_df.empty else phys_df

            # If combined is empty, skip
            if combined.empty:
                print(f"Skipping {team} – no data found.")
                continue

            # Merge out_of_possession
            if not out_df.empty:
                print("Attempting to merge out_df...")
                # Show first few rows of out_df to compare keys
                print("out_df head (jersey_number, player_name):")
                print(out_df[['jersey_number', 'player_name']].head())

                combined = combined.merge(
                    out_df,
                    on=['jersey_number', 'player_name'],
                    how='outer',
                    suffixes=('', '_out')
                )
                # Drop duplicate columns with _out suffix
                out_dup_cols = [col for col in combined.columns if col.endswith('_out')]
                if out_dup_cols:
                    combined = combined.drop(columns=out_dup_cols, errors='ignore')
                print(f"After merging out: shape {combined.shape}")
                print(f"Columns now: {combined.columns.tolist()}")
                # Check if tackles_made exists and has values
                if 'tackles_made' in combined.columns:
                    print(f"tackles_made present. First 5 values:\n{combined['tackles_made'].head()}")
                else:
                    print("WARNING: tackles_made NOT found after merge!")

            # Merge physical
            if not phys_df.empty:
                print("Attempting to merge phys_df...")
                combined = combined.merge(
                    phys_df,
                    on=['jersey_number', 'player_name'],
                    how='outer',
                    suffixes=('', '_phys')
                )
                phys_dup_cols = [col for col in combined.columns if col.endswith('_phys')]
                if phys_dup_cols:
                    combined = combined.drop(columns=phys_dup_cols, errors='ignore')
                print(f"After merging phys: shape {combined.shape}")
                print(f"Columns now: {combined.columns.tolist()}")

            # Debug: show a sample row with key out-of-possession columns
            print(f"Sample row after all merges for {team}:")
            sample_cols = ['jersey_number', 'player_name', 'tackles_made', 'tackles_won', 'blocks', 'interceptions']
            if all(c in combined.columns for c in sample_cols):
                print(combined[sample_cols].head(3))
            else:
                print("Some out-of-possession columns missing. Available columns:")
                print(combined.columns.tolist())

            combined['team'] = team
            all_teams_dfs.append(combined)

        if not all_teams_dfs:
            return pd.DataFrame(), meta

        final_df = pd.concat(all_teams_dfs, ignore_index=True)
        print(f"\nFinal merged DataFrame shape: {final_df.shape}")
        print("Sample rows (first 3):")
        print(final_df.head(3))
        print("Columns with out-of-possession stats (check if not null):")
        out_cols = ['tackles_made', 'tackles_won', 'blocks', 'interceptions', 'pressing_direct', 'pressing_indirect',
                    'duels_won_aerial', 'duels_won_physical', 'possession_contests_won', 'clearances',
                    'loose_ball_receptions', 'pushing_on', 'pushing_on_into_pressing',
                    'possession_regains', 'possession_interrupted']
        for col in out_cols:
            if col in final_df.columns:
                print(f"{col}: {final_df[col].notna().sum()} non-null out of {len(final_df)}")
            else:
                print(f"{col}: column missing!")

        # Save running CSV export
        csv_path = "data/player_stats_export.csv"
        df.to_csv(csv_path, mode='a', header=not os.path.exists(csv_path), index=False)

        return final_df, meta
# ====================================================
# LOAD TO POSTGRES – with match upsert
# ====================================================

def upsert_match(conn, meta):
    cur = conn.cursor()
    match_code = meta.get('match_code')
    if not match_code:
        raise ValueError("match_code is required")

    cur.execute("""
        INSERT INTO matches (match_code, match_date, venue, home_team, away_team, home_score, away_score, stage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_code) DO UPDATE SET
            match_date = EXCLUDED.match_date,
            venue = EXCLUDED.venue,
            home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            stage = EXCLUDED.stage
    """, (
        match_code,
        meta.get('match_date'),
        meta.get('venue'),
        meta.get('home_team'),
        meta.get('away_team'),
        meta.get('home_score'),
        meta.get('away_score'),
        meta.get('stage')
    ))
    conn.commit()
    return match_code

from psycopg2.extras import execute_values

from psycopg2.extras import execute_values

def load_player_stats(conn, df, match_code, table_name="player_stats"):
    if df.empty:
        return

    # Add match_code column
    df['match_code'] = match_code

    # Define target column order (matches PostgreSQL columns, excluding 'id')
    target_cols = [
        'match_code', 'team', 'jersey_number', 'player_name',
        'passes_attempted', 'passes_completed', 'pass_completion_pct',
        'switches_of_play', 'crosses_attempted', 'crosses_completed',
        'line_breaks_attempted', 'line_breaks_completed', 'line_break_completion_pct',
        'ball_progressions', 'take_ons', 'step_ins', 'attempts_at_goal', 'goals',
        'tackles_made', 'tackles_won', 'blocks', 'interceptions',
        'pressing_direct', 'pressing_indirect', 'duels_won_aerial', 'duels_won_physical',
        'possession_contests_won', 'clearances', 'loose_ball_receptions',
        'pushing_on', 'pushing_on_into_pressing', 'possession_regains', 'possession_interrupted',
        'total_distance_m', 'zone_1_0_7_kmh_m', 'zone_2_7_15_kmh_m',
        'zone_3_15_20_kmh_m', 'zone_4_20_25_kmh_m', 'zone_5_25_plus_kmh_m',
        'high_speed_runs_zone_3', 'sprints_zone_4_and_5', 'top_speed_kmh'
    ]

    # Ensure all target columns exist (add missing ones)
    for col in target_cols:
        if col not in df.columns:
            df[col] = None

    # Reorder DataFrame to match target_cols and drop duplicates
    df_final = df[target_cols].copy()
    df_final = df_final.drop_duplicates(subset=['match_code', 'team', 'jersey_number'], keep='first')
    df_final = df_final.reset_index(drop=True)

    # Convert pandas NA/NaN to None for PostgreSQL
    df_final = df_final.astype(object).where(pd.notnull(df_final), None)

    # Convert to list of tuples
    values = [tuple(row) for row in df_final.to_numpy()]

    # Build ON CONFLICT UPDATE clause (exclude unique key columns)
    set_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in target_cols if col not in ('match_code', 'team', 'jersey_number')])
    conflict_clause = f"""
        ON CONFLICT (match_code, team, jersey_number) 
        DO UPDATE SET {set_clause}
    """

    # Insert using execute_values
    from psycopg2.extras import execute_values
    cur = conn.cursor()
    insert_sql = f"""
        INSERT INTO {table_name} ({', '.join(target_cols)})
        VALUES %s
        {conflict_clause}
    """
    execute_values(cur, insert_sql, values)
    conn.commit()
    cur.close()
    print(f"Inserted/updated {len(df)} rows for match_code {match_code}")

# ====================================================
# MAIN
# ====================================================

if __name__ == "__main__":
    # Folder containing all match report PDFs
    FOLDER_PATH = "data"
    DEBUG = False

    # Clear CSV export at start of each full run
    csv_path = "data/player_stats_export.csv"
    if os.path.exists(csv_path):
        os.remove(csv_path)

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))

    # Iterate over all PDF files in the folder
    for filename in os.listdir(FOLDER_PATH):
        if not filename.lower().endswith('.pdf'):
            continue
        pdf_path = os.path.join(FOLDER_PATH, filename)
        print(f"\n--- Processing {filename} ---")

        df, meta = process_one_pdf(pdf_path)
        if df.empty:
            print(f"No data extracted from {filename}, skipping.")
            continue

        match_code = upsert_match(conn, meta)
        print(f"Match code: {match_code}")
        load_player_stats(conn, df, match_code)
        print(f"Loaded {len(df)} rows for {filename}.")

    conn.close()