"""
Lift/Gain Analysis Comparison: Elo vs Glicko-2 for NHL
Evaluates prediction quality across probability deciles for 2025 season.
"""

import duckdb
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import datetime

class NHLEloRating:
    """Simple Elo with optimized parameters"""
    def __init__(self, k_factor=10, home_advantage=50, recency_weight=0.2):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.recency_weight = recency_weight
        self.ratings = defaultdict(lambda: 1500)
        self.last_game_date = {}
        
    def expected_score(self, rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        
    def predict(self, home_team, away_team):
        home_rating = self.ratings[home_team] + self.home_advantage
        away_rating = self.ratings[away_team]
        return self.expected_score(home_rating, away_rating)
        
    def update(self, home_team, away_team, home_won, game_date=None):
        home_rating = self.ratings[home_team]
        away_rating = self.ratings[away_team]
        
        home_expected = self.expected_score(
            home_rating + self.home_advantage, 
            away_rating
        )
        
        k_factor = self.k_factor
        if self.recency_weight > 0 and game_date:
            for team in [home_team, away_team]:
                if team in self.last_game_date:
                    days_since = (game_date - self.last_game_date[team]).days
                    if days_since > 5:
                        k_factor *= (1 + self.recency_weight * min(days_since / 7, 1.0))
        
        home_actual = 1.0 if home_won else 0.0
        home_change = k_factor * (home_actual - home_expected)
        away_change = k_factor * ((1-home_actual) - (1-home_expected))
        
        self.ratings[home_team] += home_change
        self.ratings[away_team] += away_change
        
        if game_date:
            self.last_game_date[home_team] = game_date
            self.last_game_date[away_team] = game_date
            
    def apply_season_reversion(self, factor=0.45):
        for team in self.ratings:
            self.ratings[team] = self.ratings[team] * (1-factor) + 1500 * factor


class Glicko2Rating:
    """Simplified Glicko-2 implementation"""
    def __init__(self, tau=0.5):
        self.tau = tau
        self.ratings = defaultdict(lambda: {'rating': 1500, 'rd': 350, 'sigma': 0.06})
        
    def g(self, rd):
        return 1 / np.sqrt(1 + 3 * rd**2 / (np.pi**2))
        
    def E(self, rating, opp_rating, opp_rd):
        return 1 / (1 + np.exp(-self.g(opp_rd) * (rating - opp_rating)))
        
    def predict(self, home_team, away_team, home_advantage=50):
        home_r = self.ratings[home_team]['rating'] + home_advantage
        away_r = self.ratings[away_team]['rating']
        away_rd = self.ratings[away_team]['rd']
        return self.E(home_r, away_r, away_rd)
        
    def update(self, home_team, away_team, home_won):
        # Simplified update - just adjust ratings
        home_r = self.ratings[home_team]
        away_r = self.ratings[away_team]
        
        prob = self.E(home_r['rating'], away_r['rating'], away_r['rd'])
        actual = 1.0 if home_won else 0.0
        
        # Simple rating adjustment
        k = 20 * self.g(away_r['rd'])
        home_r['rating'] += k * (actual - prob)
        away_r['rating'] -= k * (actual - prob)
        
        # Gradually decrease uncertainty
        home_r['rd'] = max(30, home_r['rd'] * 0.999)
        away_r['rd'] = max(30, away_r['rd'] * 0.999)


def calculate_lift_gain(predictions, actuals, n_deciles=10):
    """Calculate lift and gain metrics by probability decile"""
    
    df = pd.DataFrame({
        'pred': predictions,
        'actual': actuals
    })
    
    # Sort by prediction descending
    df = df.sort_values('pred', ascending=False).reset_index(drop=True)
    
    # Assign deciles (1=highest confidence, 10=lowest)
    df['decile'] = pd.qcut(df['pred'], n_deciles, labels=False, duplicates='drop') + 1
    
    # Calculate metrics per decile
    results = []
    total_wins = df['actual'].sum()
    total_games = len(df)
    baseline_rate = total_wins / total_games
    
    cumulative_wins = 0
    cumulative_games = 0
    
    for decile in sorted(df['decile'].unique()):
        decile_data = df[df['decile'] == decile]
        
        wins = decile_data['actual'].sum()
        games = len(decile_data)
        win_rate = wins / games if games > 0 else 0
        
        cumulative_wins += wins
        cumulative_games += games
        
        lift = win_rate / baseline_rate if baseline_rate > 0 else 0
        gain_pct = (cumulative_wins / total_wins * 100) if total_wins > 0 else 0
        coverage_pct = (cumulative_games / total_games * 100)
        
        avg_prob = decile_data['pred'].mean()
        
        results.append({
            'decile': decile,
            'games': games,
            'wins': wins,
            'win_rate': win_rate,
            'avg_prob': avg_prob,
            'lift': lift,
            'cumulative_wins': cumulative_wins,
            'cumulative_games': cumulative_games,
            'gain_pct': gain_pct,
            'coverage_pct': coverage_pct
        })
    
    return pd.DataFrame(results)


def evaluate_system(system_name, rating_system):
    """Evaluate a rating system on historical data"""
    
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    
    exhibition_teams = ('CAN', 'USA', 'ATL', 'MET', 'CEN', 'PAC', 
                       'SWE', 'FIN', 'EIS', 'MUN', 'SCB', 'KLS', 
                       'KNG', 'MKN', 'HGS', 'MAT', 'MCD')
    
    games = conn.execute("""
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
    """, [exhibition_teams, exhibition_teams]).fetchall()
    conn.close()
    
    # Separate by season
    season_2025_preds = []
    season_2025_actuals = []
    all_preds = []
    all_actuals = []
    
    last_season = None
    
    for game in games:
        game_date, home, away, home_won, season = game
        
        if isinstance(game_date, str):
            game_date = datetime.strptime(game_date, '%Y-%m-%d').date()
        
        # Apply season reversion
        if last_season and season != last_season:
            if hasattr(rating_system, 'apply_season_reversion'):
                rating_system.apply_season_reversion(0.45)
        last_season = season
        
        # Predict
        pred = rating_system.predict(home, away)
        
        # Store for 2025 season analysis
        if str(season) == '2025':
            season_2025_preds.append(pred)
            season_2025_actuals.append(home_won)
        
        all_preds.append(pred)
        all_actuals.append(home_won)
        
        # Update
        if hasattr(rating_system, 'last_game_date'):
            rating_system.update(home, away, home_won, game_date)
        else:
            rating_system.update(home, away, home_won)
    
    # Calculate metrics
    results = {
        'system': system_name,
        'all_games': len(all_preds),
        'all_accuracy': np.mean([1 if (p > 0.5) == a else 0 for p, a in zip(all_preds, all_actuals)]),
        'all_brier': np.mean([(p - a)**2 for p, a in zip(all_preds, all_actuals)]),
        'season_2025_games': len(season_2025_preds),
        'season_2025_accuracy': np.mean([1 if (p > 0.5) == a else 0 for p, a in zip(season_2025_preds, season_2025_actuals)]),
        'season_2025_brier': np.mean([(p - a)**2 for p, a in zip(season_2025_preds, season_2025_actuals)]),
        'season_2025_lift_gain': calculate_lift_gain(season_2025_preds, season_2025_actuals),
        'all_lift_gain': calculate_lift_gain(all_preds, all_actuals)
    }
    
    return results


def main():
    print("=" * 80)
    print("NHL RATING SYSTEM COMPARISON: ELO vs GLICKO-2")
    print("=" * 80)
    print("\nEvaluating on 2025 season (current) + all historical data...")
    print()
    
    # Evaluate Elo
    print("Running Elo (optimized)...")
    elo = NHLEloRating(k_factor=10, home_advantage=50, recency_weight=0.2)
    elo_results = evaluate_system("Elo", elo)
    
    # Evaluate Glicko-2
    print("Running Glicko-2...")
    glicko = Glicko2Rating(tau=0.5)
    glicko_results = evaluate_system("Glicko-2", glicko)
    
    # Compare overall performance
    print("\n" + "=" * 80)
    print("OVERALL PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"\n{'Metric':<25} {'Elo':>15} {'Glicko-2':>15} {'Winner':>15}")
    print("-" * 80)
    
    metrics = [
        ('All Games', 'all_games', 'higher'),
        ('All Accuracy', 'all_accuracy', 'higher'),
        ('All Brier Score', 'all_brier', 'lower'),
        ('2025 Games', 'season_2025_games', 'higher'),
        ('2025 Accuracy', 'season_2025_accuracy', 'higher'),
        ('2025 Brier Score', 'season_2025_brier', 'lower'),
    ]
    
    for label, key, better in metrics:
        elo_val = elo_results[key]
        glicko_val = glicko_results[key]
        
        if 'accuracy' in key.lower():
            elo_str = f"{elo_val:.1%}"
            glicko_str = f"{glicko_val:.1%}"
        elif 'brier' in key.lower():
            elo_str = f"{elo_val:.4f}"
            glicko_str = f"{glicko_val:.4f}"
        else:
            elo_str = f"{elo_val:,}"
            glicko_str = f"{glicko_val:,}"
        
        if better == 'higher':
            winner = "Elo" if elo_val > glicko_val else "Glicko-2" if glicko_val > elo_val else "Tie"
        else:
            winner = "Elo" if elo_val < glicko_val else "Glicko-2" if glicko_val < elo_val else "Tie"
        
        print(f"{label:<25} {elo_str:>15} {glicko_str:>15} {winner:>15}")
    
    # 2025 Season Lift/Gain Analysis
    print("\n" + "=" * 80)
    print("2025 SEASON - LIFT/GAIN ANALYSIS BY DECILE")
    print("=" * 80)
    
    for system_name, results in [("ELO", elo_results), ("GLICKO-2", glicko_results)]:
        print(f"\n{system_name}")
        print("-" * 80)
        df = results['season_2025_lift_gain']
        
        print(f"{'Decile':<8} {'Games':>7} {'Wins':>6} {'WinRate':>8} {'AvgProb':>8} {'Lift':>6} {'Gain%':>7} {'Cover%':>7}")
        print("-" * 80)
        
        for _, row in df.iterrows():
            print(f"{int(row['decile']):<8} {int(row['games']):>7} {int(row['wins']):>6} "
                  f"{row['win_rate']:>7.1%} {row['avg_prob']:>7.1%} "
                  f"{row['lift']:>6.2f} {row['gain_pct']:>6.1f}% {row['coverage_pct']:>6.1f}%")
    
    # Head-to-head by decile
    print("\n" + "=" * 80)
    print("HEAD-TO-HEAD: LIFT COMPARISON BY DECILE (2025 Season)")
    print("=" * 80)
    
    elo_lg = elo_results['season_2025_lift_gain']
    glicko_lg = glicko_results['season_2025_lift_gain']
    
    print(f"\n{'Decile':<8} {'Elo Lift':>10} {'Glicko Lift':>12} {'Elo WR':>10} {'Glicko WR':>12} {'Winner':>12}")
    print("-" * 80)
    
    for i in range(len(elo_lg)):
        elo_row = elo_lg.iloc[i]
        glicko_row = glicko_lg.iloc[i]
        
        winner = "Elo" if elo_row['lift'] > glicko_row['lift'] else "Glicko-2" if glicko_row['lift'] > elo_row['lift'] else "Tie"
        
        print(f"{int(elo_row['decile']):<8} {elo_row['lift']:>10.2f} {glicko_row['lift']:>12.2f} "
              f"{elo_row['win_rate']:>9.1%} {glicko_row['win_rate']:>11.1%} {winner:>12}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    elo_wins = sum(1 for i in range(len(elo_lg)) if elo_lg.iloc[i]['lift'] > glicko_lg.iloc[i]['lift'])
    glicko_wins = sum(1 for i in range(len(glicko_lg)) if glicko_lg.iloc[i]['lift'] > elo_lg.iloc[i]['lift'])
    
    print(f"\nDecile Wins (by lift):")
    print(f"  Elo:      {elo_wins} deciles")
    print(f"  Glicko-2: {glicko_wins} deciles")
    
    print(f"\nOverall Winner: ", end="")
    if elo_results['season_2025_accuracy'] > glicko_results['season_2025_accuracy']:
        print("✅ ELO")
        print(f"  Advantage: +{(elo_results['season_2025_accuracy'] - glicko_results['season_2025_accuracy'])*100:.2f}% accuracy")
    elif glicko_results['season_2025_accuracy'] > elo_results['season_2025_accuracy']:
        print("✅ GLICKO-2")
        print(f"  Advantage: +{(glicko_results['season_2025_accuracy'] - elo_results['season_2025_accuracy'])*100:.2f}% accuracy")
    else:
        print("🤝 TIE")


if __name__ == '__main__':
    main()
