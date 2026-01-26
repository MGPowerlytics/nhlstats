"""
NHL Elo Parameter Tuning with Recency Weighting
Tests different parameters to optimize prediction accuracy.
"""

import duckdb
import numpy as np
from datetime import datetime
from collections import defaultdict
import sys


class NHLEloRatingTunable:
    """NHL Elo Rating with configurable parameters and recency weighting"""

    def __init__(
        self,
        k_factor=20,
        home_advantage=100,
        initial_rating=1500,
        recency_weight=0.0,
        season_reversion=0.35,
    ):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.recency_weight = recency_weight  # 0 = no weighting, 0.1-0.3 typical
        self.season_reversion = season_reversion
        self.ratings = defaultdict(lambda: initial_rating)
        self.game_dates = defaultdict(lambda: None)  # Track last game date per team

    def get_rating(self, team):
        return self.ratings[team]

    def expected_score(self, rating_a, rating_b):
        """Calculate expected score using logistic function"""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def predict(self, home_team, away_team):
        """Predict probability of home team winning"""
        home_rating = self.ratings[home_team] + self.home_advantage
        away_rating = self.ratings[away_team]
        return self.expected_score(home_rating, away_rating)

    def update(self, home_team, away_team, home_won, game_date=None):
        """Update ratings after a game with optional recency weighting"""
        home_rating = self.ratings[home_team]
        away_rating = self.ratings[away_team]

        # Calculate expected scores
        home_expected = self.expected_score(
            home_rating + self.home_advantage, away_rating
        )

        # Actual scores
        home_actual = 1.0 if home_won else 0.0
        away_actual = 1.0 - home_actual

        # Apply recency weighting if enabled
        k_factor = self.k_factor
        if self.recency_weight > 0 and game_date:
            # Boost k-factor for teams that haven't played recently
            for team in [home_team, away_team]:
                if self.game_dates[team]:
                    days_since = (game_date - self.game_dates[team]).days
                    if days_since > 7:  # More than a week since last game
                        k_factor *= 1 + self.recency_weight

        # Update ratings
        home_change = k_factor * (home_actual - home_expected)
        away_change = k_factor * (away_actual - (1 - home_expected))

        self.ratings[home_team] += home_change
        self.ratings[away_team] += away_change

        # Track game dates
        if game_date:
            self.game_dates[home_team] = game_date
            self.game_dates[away_team] = game_date

        return {
            "home_change": home_change,
            "away_change": away_change,
            "home_rating": self.ratings[home_team],
            "away_rating": self.ratings[away_team],
        }

    def apply_season_reversion(self, regression_factor=0.35):
        """Regress ratings toward mean between seasons"""
        mean_rating = self.initial_rating
        for team in self.ratings:
            self.ratings[team] = (
                self.ratings[team] * (1 - regression_factor)
                + mean_rating * regression_factor
            )


def evaluate_parameters(
    k_factor,
    home_advantage,
    recency_weight,
    season_reversion,
    test_season="2025",
    use_recent_only=False,
):
    """Evaluate Elo parameters on historical data"""

    conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)

    # Filter out exhibition teams and duplicates
    exhibition_teams = (
        "CAN",
        "USA",
        "ATL",
        "MET",
        "CEN",
        "PAC",
        "SWE",
        "FIN",
        "EIS",
        "MUN",
        "SCB",
        "KLS",
        "KNG",
        "MKN",
        "HGS",
        "MAT",
        "MCD",
    )

    games = conn.execute(
        """
        WITH ranked_games AS (
            SELECT game_date, home_team_abbrev, away_team_abbrev,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_won,
                   season,
                   ROW_NUMBER() OVER (
                       PARTITION BY game_date, home_team_abbrev, away_team_abbrev
                       ORDER BY game_id
                   ) as rn
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
              AND home_team_abbrev NOT IN ?
              AND away_team_abbrev NOT IN ?
        )
        SELECT game_date, home_team_abbrev, away_team_abbrev, home_won, season
        FROM ranked_games
        WHERE rn = 1
        ORDER BY game_date, home_team_abbrev
    """,
        [exhibition_teams, exhibition_teams],
    ).fetchall()
    conn.close()

    if use_recent_only:
        # Only use last 120 games for rapid iteration
        games = games[-120:]

    elo = NHLEloRatingTunable(
        k_factor=k_factor,
        home_advantage=home_advantage,
        recency_weight=recency_weight,
        season_reversion=season_reversion,
    )

    # Track predictions
    predictions = []
    test_predictions = []

    last_season = None

    for game in games:
        game_date, home, away, home_won, season = game

        # Convert date if needed
        if isinstance(game_date, str):
            game_date = datetime.strptime(game_date, "%Y-%m-%d").date()

        # Apply season reversion
        if last_season and season != last_season:
            elo.apply_season_reversion(season_reversion)
        last_season = season

        # Make prediction
        pred_prob = elo.predict(home, away)
        pred_result = 1 if pred_prob > 0.5 else 0

        # Store prediction
        is_correct = pred_result == home_won

        if str(season) == test_season:
            test_predictions.append(
                {
                    "prob": pred_prob,
                    "actual": home_won,
                    "correct": is_correct,
                    "home": home,
                    "away": away,
                    "date": game_date,
                }
            )

        predictions.append(
            {"prob": pred_prob, "actual": home_won, "correct": is_correct}
        )

        # Update ratings with this result
        elo.update(home, away, home_won, game_date)

    # Calculate metrics
    overall_accuracy = np.mean([p["correct"] for p in predictions])

    if test_predictions:
        test_accuracy = np.mean([p["correct"] for p in test_predictions])

        # Brier score (lower is better)
        brier = np.mean([(p["prob"] - p["actual"]) ** 2 for p in test_predictions])

        # Log loss (lower is better)
        log_loss = -np.mean(
            [
                p["actual"] * np.log(p["prob"] + 1e-10)
                + (1 - p["actual"]) * np.log(1 - p["prob"] + 1e-10)
                for p in test_predictions
            ]
        )

        # Calibration by decile
        [p["prob"] for p in test_predictions]
        [p["actual"] for p in test_predictions]

        return {
            "overall_accuracy": overall_accuracy,
            "test_accuracy": test_accuracy,
            "test_games": len(test_predictions),
            "brier_score": brier,
            "log_loss": log_loss,
            "test_predictions": test_predictions,
        }

    return {
        "overall_accuracy": overall_accuracy,
        "test_accuracy": None,
        "test_games": 0,
    }


def grid_search():
    """Test multiple parameter combinations"""

    print("=" * 80)
    print("NHL ELO PARAMETER TUNING - GRID SEARCH")
    print("=" * 80)
    print("\nTesting parameters on 2025 season (current)...")
    print()

    # Parameter grid
    k_factors = [10, 15, 20, 25, 30]
    home_advantages = [50, 75, 100, 125]
    recency_weights = [0.0, 0.1, 0.2, 0.3]
    season_reversions = [0.25, 0.35, 0.45]

    results = []

    total_tests = (
        len(k_factors)
        * len(home_advantages)
        * len(recency_weights)
        * len(season_reversions)
    )
    test_num = 0

    print(f"Running {total_tests} parameter combinations...\n")

    for k in k_factors:
        for ha in home_advantages:
            for rw in recency_weights:
                for sr in season_reversions:
                    test_num += 1

                    if test_num % 20 == 0:
                        print(
                            f"Progress: {test_num}/{total_tests} ({test_num / total_tests * 100:.0f}%)"
                        )

                    result = evaluate_parameters(k, ha, rw, sr, test_season="2025")

                    if result["test_accuracy"] is not None:
                        results.append(
                            {
                                "k_factor": k,
                                "home_advantage": ha,
                                "recency_weight": rw,
                                "season_reversion": sr,
                                "accuracy": result["test_accuracy"],
                                "brier": result["brier_score"],
                                "log_loss": result["log_loss"],
                                "games": result["test_games"],
                            }
                        )

    # Sort by accuracy
    results.sort(key=lambda x: (-x["accuracy"], x["brier"]))

    # Display top 10
    print("\n" + "=" * 80)
    print("TOP 10 PARAMETER COMBINATIONS")
    print("=" * 80)
    print(
        f"\n{'Rank':<5} {'K':>4} {'HA':>5} {'RW':>5} {'SR':>5} {'Acc':>7} {'Brier':>7} {'LogLoss':>8}"
    )
    print("-" * 80)

    for i, r in enumerate(results[:10], 1):
        print(
            f"{i:<5} {r['k_factor']:>4} {r['home_advantage']:>5} "
            f"{r['recency_weight']:>5.2f} {r['season_reversion']:>5.2f} "
            f"{r['accuracy']:>7.1%} {r['brier']:>7.4f} {r['log_loss']:>8.4f}"
        )

    # Show current parameters
    print("\n" + "=" * 80)
    print("CURRENT PARAMETERS vs BEST")
    print("=" * 80)

    current = evaluate_parameters(10, 50, 0.0, 0.35, test_season="2025")
    best = results[0]

    print("\nCurrent (k=10, ha=50, rw=0.0, sr=0.35):")
    print(f"  Accuracy: {current['test_accuracy']:.1%}")
    print(f"  Brier:    {current['brier_score']:.4f}")
    print(f"  LogLoss:  {current['log_loss']:.4f}")

    print(
        f"\nBest (k={best['k_factor']}, ha={best['home_advantage']}, "
        f"rw={best['recency_weight']:.2f}, sr={best['season_reversion']:.2f}):"
    )
    print(f"  Accuracy: {best['accuracy']:.1%}")
    print(f"  Brier:    {best['brier']:.4f}")
    print(f"  LogLoss:  {best['log_loss']:.4f}")

    improvement = (
        (best["accuracy"] - current["test_accuracy"]) / current["test_accuracy"] * 100
    )
    print(f"\n  Improvement: {improvement:+.1f}%")

    return results


def quick_test():
    """Quick test with recommended parameters"""

    print("=" * 80)
    print("QUICK PARAMETER TEST")
    print("=" * 80)

    configs = [
        {"name": "Current", "k": 10, "ha": 50, "rw": 0.0, "sr": 0.35},
        {"name": "Higher K", "k": 25, "ha": 50, "rw": 0.0, "sr": 0.35},
        {"name": "Higher HA", "k": 10, "ha": 100, "rw": 0.0, "sr": 0.35},
        {"name": "Recency 0.2", "k": 10, "ha": 50, "rw": 0.2, "sr": 0.35},
        {"name": "Combined", "k": 25, "ha": 100, "rw": 0.2, "sr": 0.35},
    ]

    print(
        f"\n{'Config':<15} {'K':>4} {'HA':>5} {'RW':>5} {'SR':>5} {'Acc':>7} {'Brier':>7}"
    )
    print("-" * 80)

    for cfg in configs:
        result = evaluate_parameters(
            cfg["k"], cfg["ha"], cfg["rw"], cfg["sr"], test_season="2025"
        )

        print(
            f"{cfg['name']:<15} {cfg['k']:>4} {cfg['ha']:>5} "
            f"{cfg['rw']:>5.2f} {cfg['sr']:>5.2f} "
            f"{result['test_accuracy']:>7.1%} {result['brier_score']:>7.4f}"
        )


if __name__ == "__main__":
    if "--quick" in sys.argv:
        quick_test()
    else:
        grid_search()
