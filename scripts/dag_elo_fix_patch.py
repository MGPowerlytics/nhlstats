#!/usr/bin/env python3
"""
Patch for DAG to fix Elo ratings and add logging.
This shows what changes need to be made to the update_elo_ratings function.
"""

DAG_FIX = '''
# ============================================================================
# FIXED update_elo_ratings FUNCTION WITH LOGGING
# ============================================================================

def update_elo_ratings(sport, **context):
    """Calculate current Elo ratings for a sport with proper logging."""
    print(f"📊 Updating {sport.upper()} Elo ratings...")

    # Load previous ratings for comparison
    previous_ratings = {}
    csv_path = f"data/{sport}_current_elo_ratings.csv"
    if os.path.exists(csv_path):
        try:
            import pandas as pd
            df = pd.read_csv(csv_path)
            previous_ratings = dict(zip(df['team'], df['rating']))
            print(f"  Loaded {len(previous_ratings)} previous ratings from {csv_path}")
        except Exception as e:
            print(f"  ⚠️  Could not load previous ratings: {e}")

    SPORTS_CONFIG[sport]

    # Import sport-specific modules
    if sport == "nba":
        from elo import get_elo_class
        from db_manager import default_db

        # FIXED: Use unified_games instead of nba_games
        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM unified_games
            WHERE sport = 'NBA'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date, game_id
        """
        games_df = default_db.fetch_df(query)
        print(f"  Loaded {len(games_df)} NBA games from unified_games")

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=100)
        for _, game in games_df.iterrows():
            elo.update(game["home_team"], game["away_team"], game["home_win"])

    elif sport == "nhl":
        from elo import get_elo_class
        from db_manager import default_db

        # FIXED: Use unified_games instead of games table
        # Map full team names to abbreviations
        query = """
            SELECT
                game_date,
                home_team_name,
                away_team_name,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM unified_games
            WHERE sport = 'NHL'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND home_team_name IS NOT NULL
              AND away_team_name IS NOT NULL
            ORDER BY game_date
        """

        games_df = default_db.fetch_df(query)
        print(f"  Loaded {len(games_df)} NHL games from unified_games")

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

        # Team name to abbreviation mapping
        team_mapping = {
            'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
            'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
            'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ',
            'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
            'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
            'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD',
            'New York Islanders': 'NYI', 'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
            'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS',
            'Seattle Kraken': 'SEA', 'St. Louis Blues': 'STL', 'Tampa Bay Lightning': 'TBL',
            'Toronto Maple Leafs': 'TOR', 'Utah Hockey Club': 'UTA', 'Vancouver Canucks': 'VAN',
            'Vegas Golden Knights': 'VGK', 'Washington Capitals': 'WSH', 'Winnipeg Jets': 'WPG',
            'Montréal Canadiens': 'MTL', 'Utah Mammoth': 'UTA',
        }

        last_date = None
        for _, game in games_df.iterrows():
            # Map team names to abbreviations
            home_full = game["home_team_name"]
            away_full = game["away_team_name"]
            home_team = team_mapping.get(home_full, home_full)
            away_team = team_mapping.get(away_full, away_full)

            game_date = game["game_date"]
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:
                    print(f"📅 New NHL season detected at {current_date}")
                    elo.apply_season_reversion(0.45)

            last_date = current_date
            elo.update(
                home_team,
                away_team,
                game["home_win"],
                game_date=current_date,
            )

    # ... similar fixes for other sports (MLB, NFL, etc.)

    # Save ratings to CSV
    if sport == "tennis":
        Path("data").mkdir(parents=True, exist_ok=True)
        with open("data/atp_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\\n")
            for player in sorted(elo.atp_ratings.keys()):
                f.write(f"{player},{elo.atp_ratings[player]:.2f}\\n")

        with open("data/wta_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\\n")
            for player in sorted(elo.wta_ratings.keys()):
                f.write(f"{player},{elo.wta_ratings[player]:.2f}\\n")
    elif sport in ["nba", "nhl", "mlb", "nfl", "epl", "ligue1", "ncaab", "wncaab", "unrivaled", "cba"]:
        Path(f"data/{sport}_current_elo_ratings.csv").parent.mkdir(
            parents=True, exist_ok=True
        )
        # Filter out NaN values before saving
        valid_ratings = {
            team: rating
            for team, rating in elo.ratings.items()
            if is_valid_score(rating)
        }

        # LOGGING: Compare with previous ratings
        if previous_ratings:
            print(f"\\n📊 {sport.upper()} Elo Rating Changes:")
            print("=" * 50)

            common_teams = set(valid_ratings.keys()) & set(previous_ratings.keys())
            new_teams = set(valid_ratings.keys()) - set(previous_ratings.keys())
            removed_teams = set(previous_ratings.keys()) - set(valid_ratings.keys())

            print(f"  Teams: {len(valid_ratings)} total ({len(common_teams)} updated, {len(new_teams)} new, {len(removed_teams)} removed)")

            if common_teams:
                changes = []
                for team in common_teams:
                    old = previous_ratings[team]
                    new = valid_ratings[team]
                    change = new - old
                    changes.append((team, old, new, change))

                # Sort by absolute change
                changes.sort(key=lambda x: abs(x[3]), reverse=True)

                avg_change = sum(c[3] for c in changes) / len(changes)
                max_increase = max(c[3] for c in changes)
                max_decrease = min(c[3] for c in changes)

                print(f"  Average change: {avg_change:+.2f}")
                print(f"  Maximum increase: {max_increase:+.2f}")
                print(f"  Maximum decrease: {max_decrease:+.2f}")

                print(f"\\n  Top 3 increases:")
                for team, old, new, change in changes[:3]:
                    if change > 0:
                        print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")

                print(f"\\n  Top 3 decreases:")
                for team, old, new, change in changes[:3]:
                    if change < 0:
                        print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")

        with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\\n")
            for team in sorted(valid_ratings.keys()):
                f.write(f"{team},{valid_ratings[team]:.2f}\\n")

    # Push to XCom (filter NaN values to prevent JSON serialization errors)
    if sport == "tennis":
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings",
            value={"ATP": dict(elo.atp_ratings), "WTA": dict(elo.wta_ratings)},
        )
        total_players = len(elo.atp_ratings) + len(elo.wta_ratings)
        print(
            f"✓ {sport.upper()} Elo ratings updated: {total_players} players (ATP: {len(elo.atp_ratings)}, WTA: {len(elo.wta_ratings)})"
        )
    else:
        # Filter out any NaN or invalid values before XCom push
        valid_ratings = {
            team: rating
            for team, rating in elo.ratings.items()
            if is_valid_score(rating)
        }
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings", value=valid_ratings
        )
        print(f"✓ {sport.upper()} Elo ratings updated: {len(valid_ratings)} teams")
'''

print("=" * 80)
print("DAG ELO FIX PATCH")
print("=" * 80)
print("\nThis patch needs to be applied to the update_elo_ratings function in:")
print("  dags/multi_sport_betting_workflow.py")
print("\nKey changes:")
print("1. Uses unified_games table instead of sport-specific tables")
print("2. Adds logging to show rating changes")
print("3. For NHL: Maps full team names to abbreviations")
print("4. Loads previous ratings for comparison")
print("\nFull patch code:")
print(DAG_FIX)
