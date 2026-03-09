"""
Updated update_elo_ratings function for Airflow DAG.
This version uses unified_games table and includes proper logging.
"""


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
            previous_ratings = dict(zip(df["team"], df["rating"]))
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
            ORDER BY game_date
        """
        games_df = default_db.fetch_df(query)
        print(f"  Loaded {len(games_df)} NBA games from unified_games")

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=100)

        # Map full team names to abbreviations
        nba_team_mapping = {
            "Atlanta Hawks": "ATL",
            "Boston Celtics": "BOS",
            "Brooklyn Nets": "BKN",
            "Charlotte Hornets": "CHA",
            "Chicago Bulls": "CHI",
            "Cleveland Cavaliers": "CLE",
            "Dallas Mavericks": "DAL",
            "Denver Nuggets": "DEN",
            "Detroit Pistons": "DET",
            "Golden State Warriors": "GSW",
            "Houston Rockets": "HOU",
            "Indiana Pacers": "IND",
            "Los Angeles Clippers": "LAC",
            "Los Angeles Lakers": "LAL",
            "Memphis Grizzlies": "MEM",
            "Miami Heat": "MIA",
            "Milwaukee Bucks": "MIL",
            "Minnesota Timberwolves": "MIN",
            "New Orleans Pelicans": "NOP",
            "New York Knicks": "NYK",
            "Oklahoma City Thunder": "OKC",
            "Orlando Magic": "ORL",
            "Philadelphia 76ers": "PHI",
            "Phoenix Suns": "PHX",
            "Portland Trail Blazers": "POR",
            "Sacramento Kings": "SAC",
            "San Antonio Spurs": "SAS",
            "Toronto Raptors": "TOR",
            "Utah Jazz": "UTA",
            "Washington Wizards": "WAS",
            "LA Clippers": "LAC",
            "LA Lakers": "LAL",
        }

        last_date = None
        for _, game in games_df.iterrows():
            # Map team names
            home_full = game["home_team"]
            away_full = game["away_team"]
            home_team = nba_team_mapping.get(home_full, home_full)
            away_team = nba_team_mapping.get(away_full, away_full)

            # Season detection
            game_date = game["game_date"]
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 120:  # NBA offseason
                    print(f"📅 New NBA season detected at {current_date}")
                    elo.apply_season_reversion(0.4)

            last_date = current_date
            elo.update(home_team, away_team, game["home_win"])

    elif sport == "nhl":
        from elo import get_elo_class
        from db_manager import default_db

        # FIXED: Use unified_games instead of games table
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
        nhl_team_mapping = {
            "Anaheim Ducks": "ANA",
            "Arizona Coyotes": "ARI",
            "Boston Bruins": "BOS",
            "Buffalo Sabres": "BUF",
            "Calgary Flames": "CGY",
            "Carolina Hurricanes": "CAR",
            "Chicago Blackhawks": "CHI",
            "Colorado Avalanche": "COL",
            "Columbus Blue Jackets": "CBJ",
            "Dallas Stars": "DAL",
            "Detroit Red Wings": "DET",
            "Edmonton Oilers": "EDM",
            "Florida Panthers": "FLA",
            "Los Angeles Kings": "LAK",
            "Minnesota Wild": "MIN",
            "Montreal Canadiens": "MTL",
            "Nashville Predators": "NSH",
            "New Jersey Devils": "NJD",
            "New York Islanders": "NYI",
            "New York Rangers": "NYR",
            "Ottawa Senators": "OTT",
            "Philadelphia Flyers": "PHI",
            "Pittsburgh Penguins": "PIT",
            "San Jose Sharks": "SJS",
            "Seattle Kraken": "SEA",
            "St. Louis Blues": "STL",
            "Tampa Bay Lightning": "TBL",
            "Toronto Maple Leafs": "TOR",
            "Utah Hockey Club": "UTA",
            "Vancouver Canucks": "VAN",
            "Vegas Golden Knights": "VGK",
            "Washington Capitals": "WSH",
            "Winnipeg Jets": "WPG",
            "Montréal Canadiens": "MTL",
            "Utah Mammoth": "UTA",
        }

        last_date = None
        for _, game in games_df.iterrows():
            # Map team names to abbreviations
            home_full = game["home_team_name"]
            away_full = game["away_team_name"]
            home_team = nhl_team_mapping.get(home_full, home_full)
            away_team = nhl_team_mapping.get(away_full, away_full)

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

    elif sport == "mlb":
        from elo import get_elo_class
        from db_manager import default_db

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=50)

        # FIXED: Use unified_games instead of mlb_games
        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   home_score, away_score
            FROM unified_games
            WHERE sport = 'MLB'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        df = default_db.fetch_df(query)
        if df.empty:
            print("No MLB games found in database")
            return

        for _, row in df.iterrows():
            home_team = row["home_team"]
            away_team = row["away_team"]
            home_score = row["home_score"]
            away_score = row["away_score"]
            # Check for valid scores (not None, NaN, or inf)
            if not is_valid_score(home_score) or not is_valid_score(away_score):
                continue
            home_won = home_score > away_score
            elo.update(
                home_team,
                away_team,
                home_won,
                home_score=home_score,
                away_score=away_score,
            )

    elif sport == "nfl":
        from elo import get_elo_class
        from db_manager import default_db

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=65)

        # FIXED: Use unified_games instead of nfl_games
        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   home_score, away_score
            FROM unified_games
            WHERE sport = 'NFL'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        df = default_db.fetch_df(query)
        if df.empty:
            print("No NFL games found in database")
            return

        for _, row in df.iterrows():
            home_team = row["home_team"]
            away_team = row["away_team"]
            home_score = row["home_score"]
            away_score = row["away_score"]
            # Check for valid scores (not None, NaN, or inf)
            if not is_valid_score(home_score) or not is_valid_score(away_score):
                continue
            home_won = home_score > away_score
            elo.update(
                home_team,
                away_team,
                home_won,
                home_score=home_score,
                away_score=away_score,
            )

    # ... similar fixes for other sports (epl, ligue1, ncaab, wncaab, tennis, cba, unrivaled)

    # Save ratings to CSV
    if sport == "tennis":
        Path("data").mkdir(parents=True, exist_ok=True)
        with open("data/atp_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for player in sorted(elo.atp_ratings.keys()):
                f.write(f"{player},{elo.atp_ratings[player]:.2f}\n")

        with open("data/wta_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for player in sorted(elo.wta_ratings.keys()):
                f.write(f"{player},{elo.wta_ratings[player]:.2f}\n")
    elif sport in [
        "nba",
        "nhl",
        "mlb",
        "nfl",
        "epl",
        "ligue1",
        "ncaab",
        "wncaab",
        "unrivaled",
        "cba",
    ]:
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
            print(f"\n📊 {sport.upper()} Elo Rating Changes:")
            print("=" * 50)

            common_teams = set(valid_ratings.keys()) & set(previous_ratings.keys())
            new_teams = set(valid_ratings.keys()) - set(previous_ratings.keys())
            removed_teams = set(previous_ratings.keys()) - set(valid_ratings.keys())

            print(
                f"  Teams: {len(valid_ratings)} total ({len(common_teams)} updated, {len(new_teams)} new, {len(removed_teams)} removed)"
            )

            if common_teams:
                changes = []
                for team in common_teams:
                    old = previous_ratings[team]
                    new = valid_ratings[team]
                    change = new - old
                    changes.append((team, old, new, change))

                # Sort by absolute change
                changes.sort(key=lambda x: abs(x[3]), reverse=True)

                if changes:
                    avg_change = sum(c[3] for c in changes) / len(changes)
                    max_increase = max(c[3] for c in changes)
                    max_decrease = min(c[3] for c in changes)

                    print(f"  Average change: {avg_change:+.2f}")
                    print(f"  Maximum increase: {max_increase:+.2f}")
                    print(f"  Maximum decrease: {max_decrease:+.2f}")

                    print(f"\n  Top 3 increases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change > 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

                    print(f"\n  Top 3 decreases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change < 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

        with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for team in sorted(valid_ratings.keys()):
                f.write(f"{team},{valid_ratings[team]:.2f}\n")

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
