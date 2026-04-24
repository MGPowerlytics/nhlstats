from plugins.elo.base_elo_rating import StandardEloRating


class WNCAABEloRating(StandardEloRating):
    """Women's NCAA Basketball Elo Rating System."""

    # Inherits default __init__ and update from StandardEloRating


def calculate_current_elo_ratings():
    from wncaab_games import WNCAABGames

    wncaab = WNCAABGames()
    df = wncaab.load_games()
    elo = WNCAABEloRating()
    # Sort by date
    df = df.sort_values("date")
    last_season = None
    for _, game in df.iterrows():
        # Season reversion for college rosters
        current_season = game.get("season")
        if current_season and current_season != last_season:
            if last_season is not None:
                # Revert towards mean
                for t in elo.ratings:
                    elo.ratings[t] = 0.65 * elo.ratings[t] + 0.35 * 1500
            last_season = current_season
        # Win = 1 if home score > away score
        h_score = game["home_score"]
        a_score = game["away_score"]
        neutral = game["neutral"]
        if h_score > a_score:
            res = 1.0
        else:
            res = 0.0
        elo.update(game["home_team"], game["away_team"], res, is_neutral=neutral)
    return elo


if __name__ == "__main__":
    elo = calculate_current_elo_ratings()
    print("Top 10 WNCAAB Teams:")
    ranked = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (t, r) in enumerate(ranked, 1):
        print(f"{i}. {t}: {r:.1f}")
