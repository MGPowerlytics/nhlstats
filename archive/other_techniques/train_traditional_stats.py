"""
Traditional Statistical Methods for NHL Game Prediction

Instead of complex ML models, use classical statistical techniques:
1. Elo Rating System (chess-style ratings)
2. Bradley-Terry Model (pairwise comparisons)
3. Poisson Regression (goals scored prediction)
4. Logistic Regression (simple linear model with interactions)
5. Markov Chain Monte Carlo (Bayesian approach)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report, log_loss
from sklearn.preprocessing import StandardScaler
from scipy.stats import poisson
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')


class EloRatingSystem:
    """
    Elo rating system for NHL teams
    Each team has a rating that changes based on game outcomes
    """
    
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
        
    def get_rating(self, team):
        """Get current rating for a team"""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
    
    def expected_score(self, rating_a, rating_b):
        """Calculate expected score (probability of team A winning)"""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def update_ratings(self, home_team, away_team, home_won):
        """Update ratings after a game"""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        
        # Apply home advantage
        home_rating_adj = home_rating + self.home_advantage
        
        # Expected scores
        expected_home = self.expected_score(home_rating_adj, away_rating)
        expected_away = 1 - expected_home
        
        # Actual scores
        actual_home = 1.0 if home_won else 0.0
        actual_away = 1.0 - actual_home
        
        # Update ratings
        self.ratings[home_team] = home_rating + self.k_factor * (actual_home - expected_home)
        self.ratings[away_team] = away_rating + self.k_factor * (actual_away - expected_away)
        
        return expected_home
    
    def predict(self, home_team, away_team):
        """Predict probability of home team winning"""
        home_rating = self.get_rating(home_team) + self.home_advantage
        away_rating = self.get_rating(away_team)
        return self.expected_score(home_rating, away_rating)


class BradleyTerryModel:
    """
    Bradley-Terry model for pairwise comparisons
    Models team strength as exponential parameters
    """
    
    def __init__(self, home_advantage=0.3):
        self.team_strengths = {}
        self.home_advantage = home_advantage
        
    def fit(self, games_df):
        """Fit model using Maximum Likelihood Estimation"""
        teams = set(games_df['home_team_name'].unique()) | set(games_df['away_team_name'].unique())
        
        # Initialize team strengths
        self.team_strengths = {team: 1.0 for team in teams}
        
        # Iterative update using Newton-Raphson
        for iteration in range(50):
            old_strengths = self.team_strengths.copy()
            
            for team in teams:
                # Calculate wins and losses
                home_games = games_df[games_df['home_team_name'] == team]
                away_games = games_df[games_df['away_team_name'] == team]
                
                wins = home_games['home_win'].sum() + (1 - away_games['home_win']).sum()
                
                # Calculate denominator
                denom = 0
                for _, game in home_games.iterrows():
                    opponent = game['away_team_name']
                    strength_home = self.team_strengths[team] * np.exp(self.home_advantage)
                    strength_away = self.team_strengths[opponent]
                    denom += strength_home / (strength_home + strength_away)
                    
                for _, game in away_games.iterrows():
                    opponent = game['home_team_name']
                    strength_home = self.team_strengths[opponent] * np.exp(self.home_advantage)
                    strength_away = self.team_strengths[team]
                    denom += strength_away / (strength_home + strength_away)
                
                # Update strength
                if denom > 0:
                    self.team_strengths[team] = wins / denom
            
            # Normalize to prevent drift
            mean_strength = np.mean(list(self.team_strengths.values()))
            for team in teams:
                self.team_strengths[team] /= mean_strength
            
            # Check convergence
            max_change = max(abs(self.team_strengths[t] - old_strengths[t]) for t in teams)
            if max_change < 1e-6:
                print(f"  Bradley-Terry converged in {iteration + 1} iterations")
                break
    
    def predict(self, home_team, away_team):
        """Predict probability of home team winning"""
        if home_team not in self.team_strengths or away_team not in self.team_strengths:
            return 0.5  # No information
        
        strength_home = self.team_strengths[home_team] * np.exp(self.home_advantage)
        strength_away = self.team_strengths[away_team]
        
        return strength_home / (strength_home + strength_away)


class PoissonGoalsModel:
    """
    Poisson regression for goals scored
    Predict goals for each team, then calculate win probability
    """
    
    def __init__(self):
        self.home_model = PoissonRegressor(alpha=1.0, max_iter=1000)
        self.away_model = PoissonRegressor(alpha=1.0, max_iter=1000)
        self.team_attack = {}
        self.team_defense = {}
        self.home_advantage = 0.3
        self.scaler = StandardScaler()
        
    def fit(self, X_train, y_train, train_df):
        """Fit Poisson models for home and away goals"""
        # Simple approach: fit on feature data
        self.home_model.fit(X_train, train_df['home_score'].values)
        self.away_model.fit(X_train, train_df['away_score'].values)
    
    def predict_proba(self, X):
        """Predict probability of home win using Poisson distribution"""
        home_goals_pred = self.home_model.predict(X)
        away_goals_pred = self.away_model.predict(X)
        
        probs = []
        for home_lambda, away_lambda in zip(home_goals_pred, away_goals_pred):
            # Calculate probability that home scores more goals than away
            prob_home_win = 0.0
            
            # Sum over realistic goal totals (0 to 10 each)
            for h in range(11):
                for a in range(11):
                    if h > a:  # Home wins
                        prob_h = poisson.pmf(h, home_lambda)
                        prob_a = poisson.pmf(a, away_lambda)
                        prob_home_win += prob_h * prob_a
            
            probs.append(prob_home_win)
        
        return np.array(probs)


def load_data():
    """Load training data"""
    data_path = Path(__file__).parent.parent / "data" / "nhl_training_data.csv"
    
    if not data_path.exists():
        print(f"❌ Training data not found: {data_path}")
        print("Run build_training_dataset_v3.py first")
        return None
    
    df = pd.read_csv(data_path)
    print(f"✅ Loaded {len(df)} games with {len(df.columns)} columns")
    
    return df


def prepare_features(df):
    """Prepare feature matrix for models"""
    # Select only numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Exclude target and identifiers
    exclude_cols = ['home_win', 'home_score', 'away_score', 'game_id']
    feature_cols = [col for col in numeric_cols if col not in exclude_cols]
    
    X = df[feature_cols].fillna(0)
    y = df['home_win'].values
    
    return X, y, feature_cols


def train_test_split_temporal(df, train_frac=0.7, val_frac=0.15):
    """Split data by date (no shuffle for time series)"""
    df_sorted = df.sort_values('game_date')
    
    n = len(df_sorted)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    
    train = df_sorted.iloc[:train_end]
    val = df_sorted.iloc[train_end:val_end]
    test = df_sorted.iloc[val_end:]
    
    return train, val, test


def evaluate_model(name, predictions, actual):
    """Calculate evaluation metrics"""
    # Ensure probabilities are in [0, 1]
    predictions = np.clip(predictions, 0, 1)
    
    predicted_classes = (predictions >= 0.5).astype(int)
    
    accuracy = accuracy_score(actual, predicted_classes)
    auc = roc_auc_score(actual, predictions)
    logloss = log_loss(actual, predictions)
    
    baseline_accuracy = np.mean(actual)  # Always predict home win
    improvement = accuracy - baseline_accuracy
    
    return {
        'model': name,
        'accuracy': accuracy,
        'auc': auc,
        'log_loss': logloss,
        'baseline': baseline_accuracy,
        'improvement': improvement
    }


def main():
    print("=" * 60)
    print("Traditional Statistical Methods for NHL Prediction")
    print("=" * 60)
    
    # Load data
    df = load_data()
    if df is None:
        return
    
    # Split by date
    print("\n📊 Splitting data by date...")
    train_df, val_df, test_df = train_test_split_temporal(df)
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
    
    # Prepare features
    X_train, y_train, feature_cols = prepare_features(train_df)
    X_val, y_val, _ = prepare_features(val_df)
    X_test, y_test, _ = prepare_features(test_df)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    results = []
    
    # ========================================
    # 1. Elo Rating System
    # ========================================
    print("\n" + "=" * 60)
    print("1. ELO RATING SYSTEM")
    print("=" * 60)
    
    elo = EloRatingSystem(k_factor=20, home_advantage=100)
    
    # Train on training data
    elo_train_preds = []
    for _, row in train_df.iterrows():
        pred = elo.update_ratings(row['home_team_name'], row['away_team_name'], row['home_win'])
        elo_train_preds.append(pred)
    
    # Validate
    elo_val_preds = []
    for _, row in val_df.iterrows():
        pred = elo.predict(row['home_team_name'], row['away_team_name'])
        elo.update_ratings(row['home_team_name'], row['away_team_name'], row['home_win'])
        elo_val_preds.append(pred)
    
    # Test
    elo_test_preds = []
    for _, row in test_df.iterrows():
        pred = elo.predict(row['home_team_name'], row['away_team_name'])
        elo.update_ratings(row['home_team_name'], row['away_team_name'], row['home_win'])
        elo_test_preds.append(pred)
    
    elo_results = evaluate_model("Elo Rating", elo_test_preds, y_test)
    results.append(elo_results)
    
    print(f"Test Accuracy: {elo_results['accuracy']:.3f}")
    print(f"Test AUC: {elo_results['auc']:.3f}")
    print(f"Improvement over baseline: {elo_results['improvement']:.3f}")
    print(f"\nTop 5 teams by Elo rating:")
    for i, (team, rating) in enumerate(sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:5], 1):
        print(f"  {i}. {team}: {rating:.1f}")
    
    # ========================================
    # 2. Bradley-Terry Model
    # ========================================
    print("\n" + "=" * 60)
    print("2. BRADLEY-TERRY MODEL")
    print("=" * 60)
    
    bt = BradleyTerryModel(home_advantage=0.3)
    bt.fit(train_df)
    
    # Predict on test
    bt_test_preds = []
    for _, row in test_df.iterrows():
        pred = bt.predict(row['home_team_name'], row['away_team_name'])
        bt_test_preds.append(pred)
    
    bt_results = evaluate_model("Bradley-Terry", bt_test_preds, y_test)
    results.append(bt_results)
    
    print(f"Test Accuracy: {bt_results['accuracy']:.3f}")
    print(f"Test AUC: {bt_results['auc']:.3f}")
    print(f"Improvement over baseline: {bt_results['improvement']:.3f}")
    print(f"\nTop 5 teams by strength:")
    for i, (team, strength) in enumerate(sorted(bt.team_strengths.items(), key=lambda x: x[1], reverse=True)[:5], 1):
        print(f"  {i}. {team}: {strength:.3f}")
    
    # ========================================
    # 3. Logistic Regression (Simple)
    # ========================================
    print("\n" + "=" * 60)
    print("3. LOGISTIC REGRESSION (L2 Regularized)")
    print("=" * 60)
    
    lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    lr.fit(X_train_scaled, y_train)
    
    lr_test_preds = lr.predict_proba(X_test_scaled)[:, 1]
    
    lr_results = evaluate_model("Logistic Regression", lr_test_preds, y_test)
    results.append(lr_results)
    
    print(f"Test Accuracy: {lr_results['accuracy']:.3f}")
    print(f"Test AUC: {lr_results['auc']:.3f}")
    print(f"Improvement over baseline: {lr_results['improvement']:.3f}")
    
    # Top features
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'coefficient': lr.coef_[0]
    }).sort_values('coefficient', key=abs, ascending=False)
    
    print(f"\nTop 5 features:")
    for _, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']}: {row['coefficient']:.4f}")
    
    # ========================================
    # 4. Poisson Goals Model
    # ========================================
    print("\n" + "=" * 60)
    print("4. POISSON REGRESSION (Goals Model)")
    print("=" * 60)
    
    if 'home_score' in train_df.columns and 'away_score' in train_df.columns:
        poisson_model = PoissonGoalsModel()
        poisson_model.fit(X_train_scaled, y_train, train_df)
        
        poisson_test_preds = poisson_model.predict_proba(X_test_scaled)
        
        poisson_results = evaluate_model("Poisson Goals", poisson_test_preds, y_test)
        results.append(poisson_results)
        
        print(f"Test Accuracy: {poisson_results['accuracy']:.3f}")
        print(f"Test AUC: {poisson_results['auc']:.3f}")
        print(f"Improvement over baseline: {poisson_results['improvement']:.3f}")
    else:
        print("⚠️  Scores not available in dataset, skipping Poisson model")
    
    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 60)
    print("SUMMARY - All Models")
    print("=" * 60)
    
    results_df = pd.DataFrame(results).sort_values('auc', ascending=False)
    print(results_df.to_string(index=False))
    
    # Save results
    output_path = Path(__file__).parent / "traditional_stats_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {output_path}")
    
    # Best model
    best = results_df.iloc[0]
    print(f"\n🏆 Best Model: {best['model']}")
    print(f"   Test AUC: {best['auc']:.3f}")
    print(f"   Test Accuracy: {best['accuracy']:.3f}")
    print(f"   Improvement: +{best['improvement']:.1%}")


if __name__ == "__main__":
    main()
