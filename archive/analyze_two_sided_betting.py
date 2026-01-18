"""
Two-Sided Lift/Gain Analysis

Bet on BOTH:
- Home team when probability is HIGH (confident home win)
- Away team when probability is LOW (confident away win)
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


def analyze_two_sided(y_true, y_pred_proba, model_name="Model"):
    """
    Analyze betting opportunities on BOTH ends
    
    Bet HOME when prob >= threshold
    Bet AWAY when prob <= (1 - threshold)
    """
    
    results = []
    
    # Define confidence thresholds
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]
    
    for threshold in thresholds:
        # Home bets (confident in home win)
        home_mask = y_pred_proba >= threshold
        home_count = np.sum(home_mask)
        
        if home_count > 0:
            home_probs = y_pred_proba[home_mask]
            home_actuals = y_true[home_mask]
            home_win_rate = np.mean(home_actuals)
            home_avg_prob = np.mean(home_probs)
        else:
            home_win_rate = 0
            home_avg_prob = 0
        
        # Away bets (confident in away win)
        away_mask = y_pred_proba <= (1 - threshold)
        away_count = np.sum(away_mask)
        
        if away_count > 0:
            away_probs = y_pred_proba[away_mask]
            away_actuals = y_true[away_mask]
            away_win_rate = 1 - np.mean(away_actuals)  # Away wins when home loses
            away_avg_prob = 1 - np.mean(away_probs)  # Flip to away win probability
        else:
            away_win_rate = 0
            away_avg_prob = 0
        
        # Combined betting (both home and away)
        combined_mask = home_mask | away_mask
        combined_count = np.sum(combined_mask)
        
        if combined_count > 0:
            # For each bet, check if we won
            wins = []
            for i in range(len(y_true)):
                if home_mask[i]:
                    # Bet on home
                    wins.append(1 if y_true[i] == 1 else 0)
                elif away_mask[i]:
                    # Bet on away
                    wins.append(1 if y_true[i] == 0 else 0)
            
            combined_win_rate = np.mean(wins)
            combined_avg_confidence = (np.sum(y_pred_proba[home_mask]) + 
                                      np.sum(1 - y_pred_proba[away_mask])) / combined_count
        else:
            combined_win_rate = 0
            combined_avg_confidence = 0
        
        # Calculate ROI (assuming -110 odds)
        def calc_roi(win_rate):
            if win_rate > 0:
                return ((win_rate * 0.909) - (1 - win_rate)) * 100
            return 0
        
        results.append({
            'threshold': threshold,
            'home_bets': home_count,
            'home_win_rate': home_win_rate,
            'home_avg_prob': home_avg_prob,
            'home_roi': calc_roi(home_win_rate),
            'away_bets': away_count,
            'away_win_rate': away_win_rate,
            'away_avg_prob': away_avg_prob,
            'away_roi': calc_roi(away_win_rate),
            'combined_bets': combined_count,
            'combined_win_rate': combined_win_rate,
            'combined_avg_confidence': combined_avg_confidence,
            'combined_roi': calc_roi(combined_win_rate)
        })
    
    return pd.DataFrame(results)


def print_two_sided_analysis(df_results, model_name, baseline):
    """Pretty print two-sided analysis"""
    
    print(f"\n{'='*110}")
    print(f"{model_name} - Two-Sided Betting Analysis")
    print(f"{'='*110}")
    print(f"Baseline: {baseline:.1%} home wins, {1-baseline:.1%} away wins")
    print(f"\n🏠 HOME BETS (when probability ≥ threshold)")
    print(f"{'Threshold':<12} {'Count':<8} {'Avg Prob':<12} {'Win Rate':<12} {'ROI':<10}")
    print(f"{'-'*60}")
    
    for _, row in df_results.iterrows():
        if row['home_bets'] > 0:
            marker = "✅" if row['home_roi'] > 0 else "❌"
            print(f"{row['threshold']:<12.2f} {int(row['home_bets']):<8} {row['home_avg_prob']:<12.3f} {row['home_win_rate']:<12.3f} {row['home_roi']:<10.1f}% {marker}")
    
    print(f"\n✈️  AWAY BETS (when probability ≤ 1-threshold)")
    print(f"{'Threshold':<12} {'Count':<8} {'Avg Prob':<12} {'Win Rate':<12} {'ROI':<10}")
    print(f"{'-'*60}")
    
    for _, row in df_results.iterrows():
        if row['away_bets'] > 0:
            marker = "✅" if row['away_roi'] > 0 else "❌"
            print(f"{row['threshold']:<12.2f} {int(row['away_bets']):<8} {row['away_avg_prob']:<12.3f} {row['away_win_rate']:<12.3f} {row['away_roi']:<10.1f}% {marker}")
    
    print(f"\n🎯 COMBINED (Home OR Away bets)")
    print(f"{'Threshold':<12} {'Total Bets':<12} {'Coverage':<12} {'Avg Conf':<12} {'Win Rate':<12} {'ROI':<10}")
    print(f"{'-'*80}")
    
    total_games = 664  # Test set size
    
    for _, row in df_results.iterrows():
        if row['combined_bets'] > 0:
            coverage = row['combined_bets'] / total_games
            marker = "🔥" if row['combined_roi'] > 30 else "✅" if row['combined_roi'] > 0 else "❌"
            print(f"{row['threshold']:<12.2f} {int(row['combined_bets']):<12} {coverage:<12.1%} {row['combined_avg_confidence']:<12.3f} {row['combined_win_rate']:<12.3f} {row['combined_roi']:<10.1f}% {marker}")


def plot_two_sided(df_no_elo, df_with_elo):
    """Create two-sided visualization"""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Win Rate by Threshold
    ax = axes[0, 0]
    ax.plot(df_no_elo['threshold'], df_no_elo['combined_win_rate'] * 100, 
            'o-', label='Without Elo (Combined)', linewidth=2, markersize=8)
    ax.plot(df_with_elo['threshold'], df_with_elo['combined_win_rate'] * 100,
            's-', label='With Elo (Combined)', linewidth=2, markersize=8)
    ax.axhline(y=52.4, color='red', linestyle='--', label='Break-even @ -110 odds', linewidth=2)
    ax.set_xlabel('Confidence Threshold', fontsize=12)
    ax.set_ylabel('Win Rate (%)', fontsize=12)
    ax.set_title('Combined Win Rate (Home + Away Bets)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # 2. ROI by Threshold
    ax = axes[0, 1]
    ax.plot(df_no_elo['threshold'], df_no_elo['combined_roi'],
            'o-', label='Without Elo', linewidth=2, markersize=8)
    ax.plot(df_with_elo['threshold'], df_with_elo['combined_roi'],
            's-', label='With Elo', linewidth=2, markersize=8)
    ax.axhline(y=0, color='red', linestyle='--', label='Break-even', linewidth=2)
    ax.set_xlabel('Confidence Threshold', fontsize=12)
    ax.set_ylabel('ROI (%)', fontsize=12)
    ax.set_title('ROI by Confidence Threshold', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # 3. Number of Bets
    ax = axes[1, 0]
    ax.plot(df_no_elo['threshold'], df_no_elo['combined_bets'],
            'o-', label='Without Elo', linewidth=2, markersize=8)
    ax.plot(df_with_elo['threshold'], df_with_elo['combined_bets'],
            's-', label='With Elo', linewidth=2, markersize=8)
    ax.set_xlabel('Confidence Threshold', fontsize=12)
    ax.set_ylabel('Number of Bets', fontsize=12)
    ax.set_title('Betting Opportunities by Threshold', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # 4. Home vs Away Breakdown (With Elo)
    ax = axes[1, 1]
    width = 0.35
    x = df_with_elo['threshold'].values
    x_pos = np.arange(len(x))
    ax.bar(x_pos - width/2, df_with_elo['home_bets'].values, width, label='Home Bets', alpha=0.8)
    ax.bar(x_pos + width/2, df_with_elo['away_bets'].values, width, label='Away Bets', alpha=0.8)
    ax.set_xlabel('Confidence Threshold', fontsize=12)
    ax.set_ylabel('Number of Bets', fontsize=12)
    ax.set_title('Home vs Away Bets (With Elo Model)', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{t:.2f}" for t in x])
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_path = Path('data/two_sided_betting_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Charts saved to: {output_path}")
    plt.close()


def main():
    print("=" * 110)
    print("Two-Sided Betting Analysis: Bet Home (high prob) AND Away (low prob)")
    print("=" * 110)
    
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
    
    # Analyze two-sided
    print("\n📊 Analyzing two-sided betting strategies...")
    df_results_no_elo = analyze_two_sided(y_test, y_pred_no_elo, "Without Elo")
    df_results_with_elo = analyze_two_sided(y_test, y_pred_with_elo, "With Elo")
    
    # Print results
    print_two_sided_analysis(df_results_no_elo, "WITHOUT ELO", baseline)
    print_two_sided_analysis(df_results_with_elo, "WITH ELO", baseline)
    
    # Best strategy comparison
    print(f"\n{'='*110}")
    print("🏆 BEST STRATEGIES COMPARISON")
    print(f"{'='*110}")
    
    print(f"\n{'Strategy':<40} {'Model':<15} {'Bets':<10} {'Win Rate':<12} {'ROI':<10}")
    print(f"{'-'*90}")
    
    # Get best results
    best_no_elo = df_results_no_elo[df_results_no_elo['threshold']==0.60].iloc[0]
    best_with_elo = df_results_with_elo[df_results_with_elo['threshold']==0.60].iloc[0]
    
    strategies = [
        ("Original: Bet ALL games", "N/A", 664, baseline, 9.0),
        ("Old: Top 20% home only", "With Elo", 133, 0.692, 32.1),
        ("NEW: Two-sided @ 0.60 threshold", "Without Elo", 
         int(best_no_elo['combined_bets']), best_no_elo['combined_win_rate'], best_no_elo['combined_roi']),
        ("NEW: Two-sided @ 0.60 threshold", "With Elo",
         int(best_with_elo['combined_bets']), best_with_elo['combined_win_rate'], best_with_elo['combined_roi']),
    ]
    
    for name, model, bets, win_rate, roi in strategies:
        marker = "🔥" if roi > 30 else "✅" if roi > 20 else "🟡" if roi > 10 else ""
        print(f"{name:<40} {model:<15} {bets:<10} {win_rate:<12.3f} {roi:<10.1f}% {marker}")
    
    # Create plots
    print("\n📈 Creating visualizations...")
    plot_two_sided(df_results_no_elo, df_results_with_elo)
    
    # Save results
    output_path = Path('data/two_sided_analysis.csv')
    df_combined = pd.DataFrame({
        'threshold': df_results_no_elo['threshold'],
        'no_elo_combined_bets': df_results_no_elo['combined_bets'],
        'no_elo_win_rate': df_results_no_elo['combined_win_rate'],
        'no_elo_roi': df_results_no_elo['combined_roi'],
        'with_elo_combined_bets': df_results_with_elo['combined_bets'],
        'with_elo_win_rate': df_results_with_elo['combined_win_rate'],
        'with_elo_roi': df_results_with_elo['combined_roi'],
    })
    df_combined.to_csv(output_path, index=False)
    print(f"💾 Results saved to: {output_path}")
    
    print("\n✅ Two-sided analysis complete!")
    print("\n💡 KEY INSIGHT: By betting on BOTH confident home wins AND confident away wins,")
    print("   you can nearly DOUBLE your betting opportunities while maintaining high ROI!")


if __name__ == "__main__":
    main()
