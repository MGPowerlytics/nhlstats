#!/usr/bin/env python3
"""
Comprehensive analysis of backtest results showing betting edge and profitability.
"""

import pandas as pd
import sys

def main():
    # Load backtest results
    df = pd.read_csv('/mnt/data2/nhlstats/data/backtest_results_20260118.csv')

    print(f"\n{'='*80}")
    print(f"📊 COMPREHENSIVE BETTING PERFORMANCE ANALYSIS")
    print(f"{'='*80}\n")

    print(f"Total Games Analyzed: {len(df)}")
    print(f"Date Range: {df['date'].min()[:10]} to {df['date'].max()[:10]}")

    # Overall Elo performance
    elo_df = df[df['elo_prob'].notna()].copy()
    accuracy = elo_df['elo_correct'].mean()
    brier = ((elo_df['elo_prob'] - elo_df['home_won'].astype(float)) ** 2).mean()

    print(f"\n🎯 ELO RATING PERFORMANCE:")
    print(f"  Total Predictions: {len(elo_df)}")
    print(f"  Overall Accuracy: {accuracy:.1%}")
    print(f"  Brier Score: {brier:.4f} (lower is better)")

    # Confidence-based analysis
    print(f"\n📈 PERFORMANCE BY CONFIDENCE LEVEL:")

    confidence_bins = [
        ('Very High (>75%)', 0.75, 1.0),
        ('High (70-75%)', 0.70, 0.75),
        ('Medium (60-70%)', 0.60, 0.70),
        ('Low (50-60%)', 0.50, 0.60),
    ]

    for label, low, high in confidence_bins:
        mask = (elo_df['elo_prob'] >= low) & (elo_df['elo_prob'] < high)
        subset = elo_df[mask]
        if len(subset) > 0:
            acc = subset['elo_correct'].mean()
            avg_prob = subset['elo_prob'].mean()
            print(f"  {label:20} | Games: {len(subset):2} | Accuracy: {acc:5.1%} | Avg Prob: {avg_prob:.1%}")

    # Per-sport breakdown
    print(f"\n🏀 SPORT-BY-SPORT BREAKDOWN:")

    for sport in sorted(elo_df['sport'].unique()):
        sport_df = elo_df[elo_df['sport'] == sport]
        acc = sport_df['elo_correct'].mean()
        brier_sport = ((sport_df['elo_prob'] - sport_df['home_won'].astype(float)) ** 2).mean()

        # High confidence games for this sport
        high_conf = sport_df[sport_df['elo_prob'] > 0.70]
        high_acc = high_conf['elo_correct'].mean() if len(high_conf) > 0 else 0

        print(f"\n  {sport}:")
        print(f"    Games: {len(sport_df)}")
        print(f"    Accuracy: {acc:.1%}")
        print(f"    Brier: {brier_sport:.4f}")
        print(f"    High Confidence (>70%): {len(high_conf)} games @ {high_acc:.1%}")

    # Simulated betting performance
    print(f"\n{'='*80}")
    print(f"💰 SIMULATED BETTING PERFORMANCE")
    print(f"{'='*80}")
    print(f"\nAssuming:")
    print(f"  - $100 flat bet per game")
    print(f"  - American odds conversion")
    print(f"  - Only bet when Elo confidence > 65%")
    print(f"  - Hypothetical market odds match implied probabilities\n")

    # Filter to betting-worthy games
    betting_df = elo_df[elo_df['elo_prob'] > 0.65].copy()

    # Calculate implied odds and profit/loss
    def elo_to_american_odds(prob):
        """Convert probability to American odds."""
        if prob > 0.5:
            return -100 * prob / (1 - prob)
        else:
            return 100 * (1 - prob) / prob

    def calculate_profit(won, elo_prob):
        """Calculate profit from $100 bet."""
        if won:
            if elo_prob > 0.5:
                # Favorite: win less
                return 100 / (elo_prob / (1 - elo_prob))
            else:
                # Underdog: win more
                return 100 * ((1 - elo_prob) / elo_prob)
        else:
            return -100

    betting_df['profit'] = betting_df.apply(
        lambda row: calculate_profit(row['elo_correct'], row['elo_prob']),
        axis=1
    )

    total_bets = len(betting_df)
    wins = betting_df['elo_correct'].sum()
    losses = total_bets - wins
    total_profit = betting_df['profit'].sum()
    roi = (total_profit / (total_bets * 100)) * 100

    print(f"Total Bets Placed: {total_bets}")
    print(f"Wins: {wins} ({wins/total_bets:.1%})")
    print(f"Losses: {losses} ({losses/total_bets:.1%})")
    print(f"Total Wagered: ${total_bets * 100:,.0f}")
    print(f"Total Profit/Loss: ${total_profit:,.2f}")
    print(f"ROI: {roi:+.1f}%")

    # Best and worst bets
    print(f"\n🎯 BEST BETS (Highest Win):")
    best = betting_df.nlargest(5, 'profit')
    for _, row in best.iterrows():
        result = "✓" if row['elo_correct'] else "✗"
        print(f"  {result} {row['sport']:6} | {row['home_team'][:15]:15} @ {row['elo_prob']:.1%} | "
              f"Profit: ${row['profit']:+.2f}")

    print(f"\n💸 WORST BETS (Losses):")
    worst = betting_df.nsmallest(5, 'profit')
    for _, row in worst.iterrows():
        result = "✓" if row['elo_correct'] else "✗"
        print(f"  {result} {row['sport']:6} | {row['home_team'][:15]:15} @ {row['elo_prob']:.1%} | "
              f"Profit: ${row['profit']:+.2f}")

    # Kelly Criterion analysis
    print(f"\n{'='*80}")
    print(f"📐 KELLY CRITERION ANALYSIS")
    print(f"{'='*80}\n")

    print("Kelly Criterion recommends betting fraction of bankroll based on edge:")
    print("  f* = (bp - q) / b")
    print("  where b = odds, p = win prob, q = 1-p\n")

    # For high-confidence bets
    high_edge_df = elo_df[elo_df['elo_prob'] > 0.70].copy()

    if len(high_edge_df) > 0:
        avg_prob = high_edge_df['elo_prob'].mean()
        win_rate = high_edge_df['elo_correct'].mean()

        # Assuming fair odds for demonstration
        avg_odds = (1 / avg_prob) - 1  # Decimal odds - 1
        kelly_fraction = ((avg_odds * win_rate) - (1 - win_rate)) / avg_odds

        print(f"High Confidence Bets (>70%):")
        print(f"  Average Elo Probability: {avg_prob:.1%}")
        print(f"  Actual Win Rate: {win_rate:.1%}")
        print(f"  Edge: {(win_rate - (1-avg_prob)) * 100:+.1f} percentage points")
        print(f"  Kelly Fraction: {kelly_fraction:.1%} of bankroll")

        if kelly_fraction > 0:
            print(f"  ✅ Positive expected value - Kelly says BET!")
        else:
            print(f"  ⚠️ Negative expected value - Kelly says PASS")

    print(f"\n{'='*80}")
    print(f"🎓 KEY INSIGHTS:")
    print(f"{'='*80}\n")

    # Calculate key metrics
    nba_acc = elo_df[elo_df['sport'] == 'NBA']['elo_correct'].mean()
    nhl_acc = elo_df[elo_df['sport'] == 'NHL']['elo_correct'].mean() if 'NHL' in elo_df['sport'].values else 0
    high_conf_acc = elo_df[elo_df['elo_prob'] > 0.70]['elo_correct'].mean()

    print(f"1. NBA predictions are {nba_acc:.1%} accurate - this is EXCELLENT")
    print(f"2. NHL predictions are {nhl_acc:.1%} accurate - needs improvement")
    print(f"3. High confidence (>70%) bets are {high_conf_acc:.1%} accurate")
    print(f"4. Overall ROI of {roi:+.1f}% suggests system has {'+EDGE' if roi > 0 else 'NO EDGE'}")

    if roi > 5:
        print(f"\n✅ STRONG POSITIVE ROI - System appears profitable!")
    elif roi > 0:
        print(f"\n⚠️ Slightly positive but close to breakeven")
    else:
        print(f"\n❌ Negative ROI - needs tuning or more data")

    print(f"\n💡 RECOMMENDATIONS:")
    if nba_acc > 0.70:
        print(f"  ✓ Focus on NBA - showing strong edge")
    if nhl_acc < 0.50:
        print(f"  ⚠️ Avoid NHL for now - below 50% accuracy")
    print(f"  ✓ Only bet high confidence games (>70%)")
    print(f"  ✓ Use Kelly Criterion for position sizing")
    print(f"  ✓ Track at least 100 bets before drawing final conclusions")

    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    main()
