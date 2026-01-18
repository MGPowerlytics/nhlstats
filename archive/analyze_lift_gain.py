"""
Lift/Gain Analysis by Probability Decile

Identify which probability ranges are most profitable for betting
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import roc_auc_score
import matplotlib.pyplot as plt
from pathlib import Path


def train_test_split_temporal(df, train_frac=0.7, val_frac=0.15):
    """Split data by date"""
    df_sorted = df.sort_values('game_date')
    n = len(df_sorted)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df_sorted.iloc[:train_end], df_sorted.iloc[train_end:val_end], df_sorted.iloc[val_end:]


def prepare_features(df, include_elo=True):
    """Prepare feature matrix"""
    exclude = ['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win']
    if not include_elo:
        exclude.extend(['home_elo', 'away_elo', 'elo_diff', 'elo_prob'])
    feature_cols = [col for col in df.columns if col not in exclude and df[col].dtype in [np.float64, np.int64]]
    return df[feature_cols].fillna(0), df['home_win'].values, feature_cols


def train_model(X_train, y_train, X_val, y_val):
    """Train XGBoost"""
    params = {
        'max_depth': 3, 'learning_rate': 0.01, 'n_estimators': 150,
        'objective': 'binary:logistic', 'eval_metric': 'auc', 'random_state': 42,
        'min_child_weight': 10, 'subsample': 0.7, 'colsample_bytree': 0.99,
        'gamma': 4.8, 'reg_alpha': 0.19, 'reg_lambda': 0.01
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_val, y_val)], verbose=False)
    return model


def analyze_by_decile(y_true, y_pred_proba, model_name="Model"):
    """Analyze predictions by probability decile"""
    
    # Create deciles
    deciles = pd.qcut(y_pred_proba, q=10, labels=False, duplicates='drop')
    
    results = []
    
    for decile in sorted(np.unique(deciles)):
        mask = deciles == decile
        
        # Get predictions in this decile
        probs = y_pred_proba[mask]
        actuals = y_true[mask]
        
        count = len(probs)
        avg_prob = np.mean(probs)
        min_prob = np.min(probs)
        max_prob = np.max(probs)
        actual_rate = np.mean(actuals)
        
        # Lift = actual rate / baseline rate
        baseline = np.mean(y_true)
        lift = actual_rate / baseline if baseline > 0 else 0
        
        # Expected wins vs actual wins
        expected_wins = np.sum(probs)
        actual_wins = np.sum(actuals)
        
        results.append({
            'decile': decile + 1,  # 1-indexed
            'count': count,
            'min_prob': min_prob,
            'max_prob': max_prob,
            'avg_prob': avg_prob,
            'actual_rate': actual_rate,
            'lift': lift,
            'expected_wins': expected_wins,
            'actual_wins': actual_wins,
            'calibration_error': abs(avg_prob - actual_rate)
        })
    
    df_results = pd.DataFrame(results)
    
    # Calculate cumulative gains (starting from highest confidence)
    df_results = df_results.sort_values('avg_prob', ascending=False)
    df_results['cumulative_count'] = df_results['count'].cumsum()
    df_results['cumulative_actual_wins'] = df_results['actual_wins'].cumsum()
    df_results['cumulative_coverage'] = df_results['cumulative_count'] / len(y_true)
    df_results['cumulative_precision'] = df_results['cumulative_actual_wins'] / df_results['cumulative_count']
    
    return df_results.sort_values('decile')


def print_decile_analysis(df_results, model_name, baseline):
    """Pretty print decile analysis"""
    
    print(f"\n{'='*90}")
    print(f"{model_name} - Decile Analysis")
    print(f"{'='*90}")
    print(f"Baseline (overall home win rate): {baseline:.1%}")
    print(f"\n{'Decile':<8} {'Range':<20} {'Count':<8} {'Avg Prob':<10} {'Actual':<10} {'Lift':<8} {'Cal Error':<10}")
    print(f"{'-'*90}")
    
    for _, row in df_results.iterrows():
        decile_num = int(row['decile'])
        prob_range = f"{row['min_prob']:.3f} - {row['max_prob']:.3f}"
        count = int(row['count'])
        avg_prob = row['avg_prob']
        actual = row['actual_rate']
        lift = row['lift']
        cal_error = row['calibration_error']
        
        # Color coding for lift
        if lift > 1.2:
            marker = "🟢"
        elif lift > 1.0:
            marker = "🟡"
        elif lift > 0.8:
            marker = "🟠"
        else:
            marker = "🔴"
        
        print(f"{decile_num:<8} {prob_range:<20} {count:<8} {avg_prob:<10.3f} {actual:<10.3f} {lift:<8.2f} {cal_error:<10.3f} {marker}")
    
    print(f"{'-'*90}")
    
    # Summary stats
    high_conf = df_results[df_results['avg_prob'] >= 0.6]
    low_conf = df_results[df_results['avg_prob'] <= 0.4]
    
    if len(high_conf) > 0:
        print(f"\n📈 HIGH CONFIDENCE (≥60%):")
        print(f"   Games: {int(high_conf['count'].sum())} ({high_conf['count'].sum() / df_results['count'].sum():.1%})")
        print(f"   Avg probability: {high_conf['avg_prob'].mean():.3f}")
        print(f"   Actual win rate: {(high_conf['actual_wins'].sum() / high_conf['count'].sum()):.1%}")
        print(f"   Lift: {(high_conf['actual_wins'].sum() / high_conf['count'].sum()) / baseline:.2f}x")
    
    if len(low_conf) > 0:
        print(f"\n📉 LOW CONFIDENCE (≤40%):")
        print(f"   Games: {int(low_conf['count'].sum())} ({low_conf['count'].sum() / df_results['count'].sum():.1%})")
        print(f"   Avg probability: {low_conf['avg_prob'].mean():.3f}")
        print(f"   Actual win rate: {(low_conf['actual_wins'].sum() / low_conf['count'].sum()):.1%}")
        print(f"   Lift: {(low_conf['actual_wins'].sum() / low_conf['count'].sum()) / baseline:.2f}x")


def print_betting_strategy(df_results, baseline):
    """Print betting strategy recommendations"""
    
    print(f"\n{'='*90}")
    print("🎯 BETTING STRATEGY RECOMMENDATIONS")
    print(f"{'='*90}")
    
    # Sort by descending probability to simulate betting on most confident
    df_sorted = df_results.sort_values('avg_prob', ascending=False).reset_index(drop=True)
    
    print(f"\n{'Strategy':<30} {'Games':<10} {'Coverage':<12} {'Win Rate':<12} {'Lift':<10} {'ROI Est':<10}")
    print(f"{'-'*90}")
    
    strategies = [
        ("Only bet top decile", 1),
        ("Bet top 2 deciles", 2),
        ("Bet top 3 deciles (≥70%)", 3),
        ("Bet top 4 deciles", 4),
        ("Bet top 5 deciles (≥50%)", 5),
        ("Bet ALL games", 10),
    ]
    
    for strategy_name, num_deciles in strategies:
        subset = df_sorted.head(num_deciles)
        
        games = int(subset['count'].sum())
        coverage = subset['count'].sum() / df_results['count'].sum()
        actual_wins = subset['actual_wins'].sum()
        win_rate = actual_wins / games if games > 0 else 0
        lift = win_rate / baseline if baseline > 0 else 0
        
        # ROI estimate assuming -110 odds (need 52.4% to break even)
        break_even = 0.524
        if win_rate > break_even:
            roi = ((win_rate * 0.909) - (1 - win_rate)) * 100  # Win $0.909, lose $1
        else:
            roi = -((1 - win_rate) - (win_rate * 0.909)) * 100
        
        marker = "✅" if roi > 0 else "❌"
        
        print(f"{strategy_name:<30} {games:<10} {coverage:<12.1%} {win_rate:<12.1%} {lift:<10.2f} {roi:<10.1f}% {marker}")
    
    print(f"\n💡 Note: ROI assumes -110 odds (bet $110 to win $100). Actual odds vary.")


def plot_lift_chart(df_results_no_elo, df_results_with_elo, baseline):
    """Create lift chart visualization"""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Lift by Decile
    ax = axes[0, 0]
    x = df_results_no_elo['decile']
    ax.plot(x, df_results_no_elo['lift'], 'o-', label='Without Elo', linewidth=2, markersize=8)
    ax.plot(x, df_results_with_elo['lift'], 's-', label='With Elo', linewidth=2, markersize=8)
    ax.axhline(y=1.0, color='red', linestyle='--', label='Baseline (1.0x)')
    ax.set_xlabel('Probability Decile', fontsize=12)
    ax.set_ylabel('Lift (Actual / Baseline)', fontsize=12)
    ax.set_title('Lift by Probability Decile', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(range(1, 11))
    
    # 2. Actual vs Predicted Win Rate
    ax = axes[0, 1]
    ax.plot(df_results_no_elo['avg_prob'], df_results_no_elo['actual_rate'], 'o-', 
            label='Without Elo', linewidth=2, markersize=8)
    ax.plot(df_results_with_elo['avg_prob'], df_results_with_elo['actual_rate'], 's-', 
            label='With Elo', linewidth=2, markersize=8)
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', alpha=0.5)
    ax.set_xlabel('Predicted Probability', fontsize=12)
    ax.set_ylabel('Actual Win Rate', fontsize=12)
    ax.set_title('Calibration: Predicted vs Actual', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # 3. Cumulative Gains
    ax = axes[1, 0]
    # Sort by descending probability
    df_no_sorted = df_results_no_elo.sort_values('avg_prob', ascending=False)
    df_with_sorted = df_results_with_elo.sort_values('avg_prob', ascending=False)
    
    ax.plot(df_no_sorted['cumulative_coverage'] * 100, 
            df_no_sorted['cumulative_precision'] * 100,
            'o-', label='Without Elo', linewidth=2, markersize=8)
    ax.plot(df_with_sorted['cumulative_coverage'] * 100, 
            df_with_sorted['cumulative_precision'] * 100,
            's-', label='With Elo', linewidth=2, markersize=8)
    ax.axhline(y=baseline * 100, color='red', linestyle='--', label=f'Baseline ({baseline:.1%})')
    ax.axhline(y=52.4, color='orange', linestyle='--', label='Break-even @ -110 odds (52.4%)', alpha=0.7)
    ax.set_xlabel('% of Games Covered (starting from highest confidence)', fontsize=12)
    ax.set_ylabel('Win Rate (%)', fontsize=12)
    ax.set_title('Cumulative Gains Curve', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # 4. Games by Decile
    ax = axes[1, 1]
    x = df_results_no_elo['decile']
    width = 0.35
    ax.bar(x - width/2, df_results_no_elo['count'], width, label='Without Elo', alpha=0.8)
    ax.bar(x + width/2, df_results_with_elo['count'], width, label='With Elo', alpha=0.8)
    ax.set_xlabel('Probability Decile', fontsize=12)
    ax.set_ylabel('Number of Games', fontsize=12)
    ax.set_title('Game Distribution by Decile', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xticks(range(1, 11))
    
    plt.tight_layout()
    
    # Save
    output_path = Path('data/lift_gain_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Charts saved to: {output_path}")
    
    plt.close()


def main():
    print("=" * 90)
    print("Lift/Gain Analysis by Probability Decile")
    print("=" * 90)
    
    # Load data
    print("\n📂 Loading data...")
    df = pd.read_csv('data/nhl_training_data_with_elo.csv')
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Split
    train_df, val_df, test_df = train_test_split_temporal(df)
    print(f"   Test set: {len(test_df)} games")
    
    # Train both models
    print("\n🤖 Training models...")
    
    # Without Elo
    X_train_no, y_train, _ = prepare_features(train_df, include_elo=False)
    X_val_no, y_val, _ = prepare_features(val_df, include_elo=False)
    X_test_no, y_test, _ = prepare_features(test_df, include_elo=False)
    model_no_elo = train_model(X_train_no, y_train, X_val_no, y_val)
    
    # With Elo
    X_train_with, _, _ = prepare_features(train_df, include_elo=True)
    X_val_with, _, _ = prepare_features(val_df, include_elo=True)
    X_test_with, _, _ = prepare_features(test_df, include_elo=True)
    model_with_elo = train_model(X_train_with, y_train, X_val_with, y_val)
    
    # Predictions
    y_pred_no_elo = model_no_elo.predict_proba(X_test_no)[:, 1]
    y_pred_with_elo = model_with_elo.predict_proba(X_test_with)[:, 1]
    
    print("   ✅ Models trained")
    
    # Baseline
    baseline = np.mean(y_test)
    
    # Analyze deciles
    print("\n📊 Analyzing predictions by decile...")
    df_results_no_elo = analyze_by_decile(y_test, y_pred_no_elo, "Without Elo")
    df_results_with_elo = analyze_by_decile(y_test, y_pred_with_elo, "With Elo")
    
    # Print results
    print_decile_analysis(df_results_no_elo, "WITHOUT ELO", baseline)
    print_decile_analysis(df_results_with_elo, "WITH ELO", baseline)
    
    # Betting strategies
    print_betting_strategy(df_results_no_elo, baseline)
    print_betting_strategy(df_results_with_elo, baseline)
    
    # Create visualizations
    print("\n📈 Creating visualizations...")
    plot_lift_chart(df_results_no_elo, df_results_with_elo, baseline)
    
    # Save detailed results
    output_path = Path('data/decile_analysis.csv')
    
    df_combined = pd.DataFrame({
        'decile': df_results_no_elo['decile'],
        'no_elo_count': df_results_no_elo['count'],
        'no_elo_avg_prob': df_results_no_elo['avg_prob'],
        'no_elo_actual_rate': df_results_no_elo['actual_rate'],
        'no_elo_lift': df_results_no_elo['lift'],
        'with_elo_count': df_results_with_elo['count'],
        'with_elo_avg_prob': df_results_with_elo['avg_prob'],
        'with_elo_actual_rate': df_results_with_elo['actual_rate'],
        'with_elo_lift': df_results_with_elo['lift'],
    })
    
    df_combined.to_csv(output_path, index=False)
    print(f"💾 Detailed results saved to: {output_path}")
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
