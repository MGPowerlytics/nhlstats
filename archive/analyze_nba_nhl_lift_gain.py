#!/usr/bin/env python3
"""
Lift/Gain Analysis for NBA and NHL Elo Ratings by Decile.

Shows which confidence levels (deciles) are most profitable for betting.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json


def calculate_lift_gain_by_decile(df, prob_col='elo_prob', actual_col='home_win'):
    """
    Calculate lift and gain statistics by probability decile.
    
    Returns DataFrame with decile-level metrics.
    """
    df = df.copy()
    
    # Create deciles based on predicted probability
    df['decile'] = pd.qcut(df[prob_col], q=10, labels=False, duplicates='drop') + 1
    
    results = []
    
    for decile in sorted(df['decile'].unique()):
        decile_df = df[df['decile'] == decile]
        
        n_games = len(decile_df)
        n_wins = decile_df[actual_col].sum()
        win_rate = n_wins / n_games if n_games > 0 else 0
        
        # Baseline (overall win rate)
        baseline = df[actual_col].mean()
        
        # Lift = actual win rate / baseline win rate
        lift = win_rate / baseline if baseline > 0 else 0
        
        # Average predicted probability in this decile
        avg_prob = decile_df[prob_col].mean()
        min_prob = decile_df[prob_col].min()
        max_prob = decile_df[prob_col].max()
        
        # Cumulative gain
        cumulative_games = len(df[df['decile'] <= decile])
        cumulative_wins = df[df['decile'] <= decile][actual_col].sum()
        cumulative_pct = cumulative_games / len(df)
        gain = (cumulative_wins / df[actual_col].sum()) if df[actual_col].sum() > 0 else 0
        
        results.append({
            'decile': decile,
            'n_games': n_games,
            'n_wins': int(n_wins),
            'win_rate': win_rate,
            'baseline': baseline,
            'lift': lift,
            'avg_prob': avg_prob,
            'min_prob': min_prob,
            'max_prob': max_prob,
            'cumulative_pct': cumulative_pct,
            'gain': gain
        })
    
    return pd.DataFrame(results)


def plot_lift_gain_comparison(nba_deciles, nhl_deciles, output_dir='data'):
    """Create comprehensive lift/gain comparison charts."""
    output_dir = Path(output_dir)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Lift by Decile
    ax1 = axes[0, 0]
    ax1.bar(nba_deciles['decile'] - 0.2, nba_deciles['lift'], width=0.4, 
            label='NBA', alpha=0.8, color='#FDB927')
    ax1.bar(nhl_deciles['decile'] + 0.2, nhl_deciles['lift'], width=0.4,
            label='NHL', alpha=0.8, color='#C8102E')
    ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5, label='Baseline')
    ax1.set_xlabel('Probability Decile', fontsize=12)
    ax1.set_ylabel('Lift', fontsize=12)
    ax1.set_title('Lift by Decile: NBA vs NHL', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(alpha=0.3, axis='y')
    ax1.set_xticks(range(1, 11))
    
    # Plot 2: Win Rate by Decile
    ax2 = axes[0, 1]
    ax2.plot(nba_deciles['decile'], nba_deciles['win_rate'] * 100, 
             'o-', linewidth=2.5, markersize=8, label='NBA', color='#FDB927')
    ax2.plot(nhl_deciles['decile'], nhl_deciles['win_rate'] * 100,
             's-', linewidth=2.5, markersize=8, label='NHL', color='#C8102E')
    ax2.axhline(y=nba_deciles['baseline'].iloc[0] * 100, color='#FDB927', 
                linestyle='--', linewidth=1, alpha=0.5, label='NBA Baseline')
    ax2.axhline(y=nhl_deciles['baseline'].iloc[0] * 100, color='#C8102E',
                linestyle='--', linewidth=1, alpha=0.5, label='NHL Baseline')
    ax2.set_xlabel('Probability Decile', fontsize=12)
    ax2.set_ylabel('Win Rate (%)', fontsize=12)
    ax2.set_title('Actual Win Rate by Decile', fontsize=14, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3)
    ax2.set_xticks(range(1, 11))
    
    # Plot 3: Cumulative Gain
    ax3 = axes[1, 0]
    ax3.plot(nba_deciles['cumulative_pct'] * 100, nba_deciles['gain'] * 100,
             'o-', linewidth=2.5, markersize=8, label='NBA', color='#FDB927')
    ax3.plot(nhl_deciles['cumulative_pct'] * 100, nhl_deciles['gain'] * 100,
             's-', linewidth=2.5, markersize=8, label='NHL', color='#C8102E')
    ax3.plot([0, 100], [0, 100], 'k--', linewidth=1, alpha=0.5, label='Random')
    ax3.set_xlabel('% of Games (sorted by confidence)', fontsize=12)
    ax3.set_ylabel('% of Wins Captured', fontsize=12)
    ax3.set_title('Cumulative Gain Chart', fontsize=14, fontweight='bold')
    ax3.legend(fontsize=11)
    ax3.grid(alpha=0.3)
    ax3.set_xlim(0, 100)
    ax3.set_ylim(0, 100)
    
    # Plot 4: Predicted vs Actual Probability
    ax4 = axes[1, 1]
    ax4.scatter(nba_deciles['avg_prob'] * 100, nba_deciles['win_rate'] * 100,
                s=nba_deciles['n_games'], alpha=0.6, label='NBA', color='#FDB927')
    ax4.scatter(nhl_deciles['avg_prob'] * 100, nhl_deciles['win_rate'] * 100,
                s=nhl_deciles['n_games'], alpha=0.6, label='NHL', marker='s', color='#C8102E')
    ax4.plot([0, 100], [0, 100], 'k--', linewidth=1, alpha=0.5, label='Perfect Calibration')
    ax4.set_xlabel('Predicted Probability (%)', fontsize=12)
    ax4.set_ylabel('Actual Win Rate (%)', fontsize=12)
    ax4.set_title('Calibration by Decile (size = # games)', fontsize=14, fontweight='bold')
    ax4.legend(fontsize=11)
    ax4.grid(alpha=0.3)
    ax4.set_xlim(0, 100)
    ax4.set_ylim(0, 100)
    
    plt.tight_layout()
    
    output_file = output_dir / 'nba_nhl_lift_gain_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"📊 Saved chart: {output_file}")
    
    plt.close()


def print_decile_tables(nba_deciles, nhl_deciles):
    """Print formatted decile tables for both sports."""
    
    print("\n" + "=" * 100)
    print("🏀 NBA ELO - LIFT/GAIN BY DECILE")
    print("=" * 100)
    print(f"{'Decile':<8} {'Prob Range':<20} {'Games':<8} {'Wins':<8} {'Win%':<10} {'Lift':<10} {'Gain':<10}")
    print("-" * 100)
    
    for _, row in nba_deciles.iterrows():
        prob_range = f"{row['min_prob']:.3f}-{row['max_prob']:.3f}"
        print(f"{int(row['decile']):<8} {prob_range:<20} {row['n_games']:<8} "
              f"{row['n_wins']:<8} {row['win_rate']*100:>8.1f}% {row['lift']:>9.2f} "
              f"{row['gain']*100:>9.1f}%")
    
    print("\n" + "=" * 100)
    print("🏒 NHL ELO - LIFT/GAIN BY DECILE")
    print("=" * 100)
    print(f"{'Decile':<8} {'Prob Range':<20} {'Games':<8} {'Wins':<8} {'Win%':<10} {'Lift':<10} {'Gain':<10}")
    print("-" * 100)
    
    for _, row in nhl_deciles.iterrows():
        prob_range = f"{row['min_prob']:.3f}-{row['max_prob']:.3f}"
        print(f"{int(row['decile']):<8} {prob_range:<20} {row['n_games']:<8} "
              f"{row['n_wins']:<8} {row['win_rate']*100:>8.1f}% {row['lift']:>9.2f} "
              f"{row['gain']*100:>9.1f}%")


def analyze_betting_value(deciles_df, sport_name):
    """Analyze which deciles provide betting value."""
    print(f"\n" + "=" * 80)
    print(f"💰 {sport_name} BETTING VALUE BY DECILE")
    print("=" * 80)
    
    for _, row in deciles_df.iterrows():
        decile = int(row['decile'])
        win_rate = row['win_rate']
        avg_prob = row['avg_prob']
        lift = row['lift']
        n_games = row['n_games']
        
        # Calculate expected value (simplified)
        # Assume odds reflect implied probability
        # EV = (win_rate * payout) - (loss_rate * stake)
        # If we bet when our prob > market prob, we have edge
        
        edge = win_rate - avg_prob
        edge_pct = (edge / avg_prob * 100) if avg_prob > 0 else 0
        
        recommendation = ""
        if lift > 1.1:
            recommendation = "✅ STRONG BET"
        elif lift > 1.05:
            recommendation = "✓ Good"
        elif lift < 0.95:
            recommendation = "❌ AVOID"
        elif lift < 0.90:
            recommendation = "⛔ VERY BAD"
        else:
            recommendation = "~ Neutral"
        
        print(f"Decile {decile}: Win Rate {win_rate*100:.1f}% (predicted {avg_prob*100:.1f}%) "
              f"| Lift {lift:.2f} | Edge {edge_pct:+.1f}% | {recommendation}")


def main():
    """Run lift/gain analysis for NBA and NHL."""
    print("=" * 100)
    print("📊 LIFT/GAIN ANALYSIS: NBA vs NHL ELO")
    print("=" * 100)
    
    # Generate NBA predictions (re-run to get full prediction set)
    print("\n🏀 Generating NBA Elo predictions...")
    from nba_elo_rating import load_nba_games_from_json, NBAEloRating
    
    nba_games = load_nba_games_from_json()
    
    if len(nba_games) == 0:
        print("❌ No NBA games found!")
        return
    
    # Split and predict
    split_idx = int(len(nba_games) * 0.8)
    nba_train = nba_games.iloc[:split_idx].copy()
    nba_test = nba_games.iloc[split_idx:].copy()
    
    nba_elo = NBAEloRating(k_factor=20, home_advantage=100)
    
    # Train
    for _, game in nba_train.iterrows():
        prob = nba_elo.predict(game['home_team'], game['away_team'])
        nba_elo.update(game['home_team'], game['away_team'], game['home_win'])
    
    # Test predictions
    nba_test_preds = []
    for _, game in nba_test.iterrows():
        prob = nba_elo.predict(game['home_team'], game['away_team'])
        nba_test_preds.append(prob)
        nba_elo.update(game['home_team'], game['away_team'], game['home_win'])
    
    nba_test['elo_prob'] = nba_test_preds
    
    # Generate NHL predictions
    print("\n🏒 Generating NHL Elo predictions...")
    from nhl_elo_rating import NHLEloRating
    import duckdb
    
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    
    nhl_games_query = """
    SELECT 
        game_id,
        game_date,
        home_team_name,
        away_team_name,
        home_score,
        away_score,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
    FROM games
    WHERE game_type = 2
    AND game_state = 'OFF'
    AND home_score IS NOT NULL
    AND away_score IS NOT NULL
    ORDER BY game_date, game_id
    """
    
    nhl_games = conn.execute(nhl_games_query).fetchdf()
    conn.close()
    
    print(f"✅ Loaded {len(nhl_games)} NHL games")
    
    # Split and predict
    split_idx = int(len(nhl_games) * 0.8)
    nhl_train = nhl_games.iloc[:split_idx].copy()
    nhl_test = nhl_games.iloc[split_idx:].copy()
    
    nhl_elo = NHLEloRating(k_factor=20, home_advantage=100)
    
    # Train
    for _, game in nhl_train.iterrows():
        prob = nhl_elo.predict(game['home_team_name'], game['away_team_name'])
        nhl_elo.update(game['home_team_name'], game['away_team_name'], game['home_win'])
    
    # Test predictions
    nhl_test_preds = []
    for _, game in nhl_test.iterrows():
        prob = nhl_elo.predict(game['home_team_name'], game['away_team_name'])
        nhl_test_preds.append(prob)
        nhl_elo.update(game['home_team_name'], game['away_team_name'], game['home_win'])
    
    nhl_test['elo_prob'] = nhl_test_preds
    
    # Calculate decile statistics
    print("\n📊 Calculating decile statistics...")
    nba_deciles = calculate_lift_gain_by_decile(nba_test, 'elo_prob', 'home_win')
    nhl_deciles = calculate_lift_gain_by_decile(nhl_test, 'elo_prob', 'home_win')
    
    # Print tables
    print_decile_tables(nba_deciles, nhl_deciles)
    
    # Analyze betting value
    analyze_betting_value(nba_deciles, "NBA")
    analyze_betting_value(nhl_deciles, "NHL")
    
    # Create visualizations
    print("\n📈 Creating visualizations...")
    plot_lift_gain_comparison(nba_deciles, nhl_deciles)
    
    # Save decile data
    nba_deciles.to_csv('data/nba_elo_deciles.csv', index=False)
    nhl_deciles.to_csv('data/nhl_elo_deciles.csv', index=False)
    
    print("\n💾 Files saved:")
    print("   - data/nba_elo_deciles.csv")
    print("   - data/nhl_elo_deciles.csv")
    print("   - data/nba_nhl_lift_gain_comparison.png")
    
    # Summary comparison
    print("\n" + "=" * 100)
    print("📊 SUMMARY: NBA vs NHL")
    print("=" * 100)
    
    nba_top_decile = nba_deciles.iloc[-1]
    nhl_top_decile = nhl_deciles.iloc[-1]
    
    print(f"\nTop Decile (Highest Confidence):")
    print(f"  NBA: {nba_top_decile['win_rate']*100:.1f}% win rate, {nba_top_decile['lift']:.2f}x lift, {nba_top_decile['n_games']} games")
    print(f"  NHL: {nhl_top_decile['win_rate']*100:.1f}% win rate, {nhl_top_decile['lift']:.2f}x lift, {nhl_top_decile['n_games']} games")
    
    nba_bottom_decile = nba_deciles.iloc[0]
    nhl_bottom_decile = nhl_deciles.iloc[0]
    
    print(f"\nBottom Decile (Lowest Confidence):")
    print(f"  NBA: {nba_bottom_decile['win_rate']*100:.1f}% win rate, {nba_bottom_decile['lift']:.2f}x lift")
    print(f"  NHL: {nhl_bottom_decile['win_rate']*100:.1f}% win rate, {nhl_bottom_decile['lift']:.2f}x lift")
    
    print("\n" + "=" * 100)
    print("✅ LIFT/GAIN ANALYSIS COMPLETE!")
    print("=" * 100)


if __name__ == '__main__':
    main()
