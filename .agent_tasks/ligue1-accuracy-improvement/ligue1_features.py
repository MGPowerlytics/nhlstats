"""
Feature engineering for Ligue1 prediction improvement.
Extracts features from CSV data and creates enhanced dataset.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

def load_ligue1_data(data_dir="data/ligue1"):
    """Load and combine all Ligue1 CSV files."""
    csv_files = sorted(Path(data_dir).glob("F1_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    df_list = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        df['source_file'] = csv_file.name
        df_list.append(df)

    df = pd.concat(df_list, ignore_index=True)

    # Parse date
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
    df = df.sort_values('Date').reset_index(drop=True)

    print(f"Loaded {len(df)} games")
    return df

def compute_team_form(df, window=5):
    """Compute rolling form features for each team."""
    results = []

    # Process each game chronologically
    for idx, game in df.iterrows():
        home = game['HomeTeam']
        away = game['AwayTeam']
        date = game['Date']

        # Get historical games for each team (before this game)
        home_history = df[(df['Date'] < date) &
                        ((df['HomeTeam'] == home) | (df['AwayTeam'] == home))]
        away_history = df[(df['Date'] < date) &
                        ((df['HomeTeam'] == away) | (df['AwayTeam'] == away))]

        def calc_form(hist, team):
            if len(hist) == 0:
                return {'win_rate': 0.5, 'avg_goals_for': 1.0, 'avg_goals_against': 1.0}

            recent = hist.tail(window)
            wins = 0
            goals_for = []
            goals_against = []

            for _, g in recent.iterrows():
                if g['HomeTeam'] == team:
                    gf = g['FTHG']
                    ga = g['FTAG']
                else:
                    gf = g['FTAG']
                    ga = g['FTHG']

                goals_for.append(gf)
                goals_against.append(ga)

                if gf > ga:
                    wins += 1
                elif gf == ga:
                    wins += 0.5

            return {
                'win_rate': wins / len(recent),
                'avg_goals_for': np.mean(goals_for),
                'avg_goals_against': np.mean(goals_against),
            }

        home_form = calc_form(home_history, home)
        away_form = calc_form(away_history, away)

        results.append({
            'game_id': idx,
            'home_form': home_form['win_rate'],
            'away_form': away_form['win_rate'],
            'home_goals_for_avg': home_form['avg_goals_for'],
            'home_goals_against_avg': home_form['avg_goals_against'],
            'away_goals_for_avg': away_form['avg_goals_for'],
            'away_goals_against_avg': away_form['avg_goals_against'],
        })

    return pd.DataFrame(results)

def extract_match_features(df):
    """Extract features from match data."""
    features = []

    for idx, game in df.iterrows():
        # Shot-based features
        hs = game.get('HS', 0)
        as_ = game.get('AS', 0)
        hst = game.get('HST', 0)
        ast = game.get('AST', 0)

        # Discipline features
        hf = game.get('HF', 0)
        af = game.get('AF', 0)
        hy = game.get('HY', 0)
        ay = game.get('AY', 0)
        hr = game.get('HR', 0)
        ar = game.get('AR', 0)

        # Corner features
        hc = game.get('HC', 0)
        ac = game.get('AC', 0)

        features.append({
            'game_id': idx,
            'shot_diff': hs - as_ if not pd.isna(hs) and not pd.isna(as_) else 0,
            'shot_on_target_diff': hst - ast if not pd.isna(hst) and not pd.isna(ast) else 0,
            'shot_accuracy_home': hst / hs if hs > 0 else 0,
            'shot_accuracy_away': ast / as_ if as_ > 0 else 0,
            'foul_diff': af - hf if not pd.isna(hf) and not pd.isna(af) else 0,
            'yellow_diff': ay - hy if not pd.isna(hy) and not pd.isna(ay) else 0,
            'red_diff': ar - hr if not pd.isna(hr) and not pd.isna(ar) else 0,
            'corner_diff': hc - ac if not pd.isna(hc) and not pd.isna(ac) else 0,
            'total_shots': (hs + as_) if not pd.isna(hs) and not pd.isna(as_) else 0,
            'total_corners': (hc + ac) if not pd.isna(hc) and not pd.isna(ac) else 0,
        })

    return pd.DataFrame(features)

def compute_bookmaker_probs(df):
    """Compute consensus bookmaker probabilities from odds."""
    probs = []

    for idx, game in df.iterrows():
        # Use average odds
        avg_h = game.get('AvgH', 0)
        avg_d = game.get('AvgD', 0)
        avg_a = game.get('AvgA', 0)

        if avg_h > 0 and avg_d > 0 and avg_a > 0:
            # Convert odds to implied probability
            inv_h = 1 / avg_h
            inv_d = 1 / avg_d
            inv_a = 1 / avg_a
            total = inv_h + inv_d + inv_a

            probs.append({
                'game_id': idx,
                'bookmaker_prob_home': inv_h / total,
                'bookmaker_prob_draw': inv_d / total,
                'bookmaker_prob_away': inv_a / total,
            })
        else:
            probs.append({
                'game_id': idx,
                'bookmaker_prob_home': 0.4,
                'bookmaker_prob_draw': 0.25,
                'bookmaker_prob_away': 0.35,
            })

    return pd.DataFrame(probs)

if __name__ == "__main__":
    print("Loading Ligue1 data...")
    df = load_ligue1_data()

    print("Computing team form...")
    form_df = compute_team_form(df)

    print("Extracting match features...")
    match_features = extract_match_features(df)

    print("Computing bookmaker probabilities...")
    bookmaker_df = compute_bookmaker_probs(df)

    # Merge all features
    result = pd.concat([
        df.reset_index(drop=True),
        form_df.iloc[:, 1:],
        match_features.iloc[:, 1:],
        bookmaker_df.iloc[:, 1:]
    ], axis=1)

    print(f"Created dataset with {len(result)} rows and {len(result.columns)} columns")

    # Save
    output_path = "ligue1_features.csv"
    result.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")

    print("\nFirst few rows:")
    print(result.head())
    print("\nColumns:", result.columns.tolist())
