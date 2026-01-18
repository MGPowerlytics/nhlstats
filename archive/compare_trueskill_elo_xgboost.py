#!/usr/bin/env python3
"""
Compare TrueSkill vs Elo vs Glicko-2 vs OpenSkill vs XGBoost for NHL game prediction.

This script:
1. Calculates team-level ratings for each system
2. Compares predictive accuracy against all models
3. Evaluates which rating system is most predictive of wins
"""

import duckdb
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss, roc_curve
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
from pathlib import Path
import json
from datetime import datetime

# Import rating systems
from nhl_trueskill_ratings import NHLTrueSkill
from nhl_elo_rating import NHLEloRating
from nhl_glicko2_ratings import NHLGlicko2
from nhl_openskill_ratings import NHLOpenSkill


class ModelComparison:
    """Compare TrueSkill, Elo, and XGBoost predictions."""
    
    def __init__(self, db_path='data/nhlstats.duckdb'):
        self.conn = duckdb.connect(db_path)
        self.results = {}
        
    def build_trueskill_features(self):
        """
        Calculate team-level TrueSkill ratings for each game.
        Returns DataFrame with game_id, home_trueskill, away_trueskill.
        """
        print("\n" + "="*80)
        print("🎯 Building TrueSkill Features")
        print("="*80)
        
        # Initialize TrueSkill
        ts = NHLTrueSkill()
        ts.load_player_info()
        
        # Process all games chronologically
        ts.process_games()
        
        # Now get team ratings for each game
        games_query = """
        SELECT 
            game_id,
            game_date,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM games
        WHERE game_type = 2
        AND game_state = 'OFF'
        ORDER BY game_date, game_id
        """
        
        games_df = self.conn.execute(games_query).fetchdf()
        print(f"📊 Found {len(games_df)} games")
        
        # Calculate team TrueSkill for each game
        game_features = []
        
        for idx, game in games_df.iterrows():
            game_id = game['game_id']
            home_team = game['home_team_id']
            away_team = game['away_team_id']
            
            # Get players for each team in this game
            player_query = f"""
            SELECT player_id, team_id
            FROM player_game_stats
            WHERE game_id = '{game_id}'
            AND player_id IS NOT NULL
            """
            
            players = self.conn.execute(player_query).fetchdf()
            
            home_players = players[players['team_id'] == home_team]['player_id'].tolist()
            away_players = players[players['team_id'] == away_team]['player_id'].tolist()
            
            # Calculate team-level TrueSkill (average of player ratings)
            home_ratings = [ts.player_ratings[p].mu - 3 * ts.player_ratings[p].sigma 
                           for p in home_players if p in ts.player_ratings]
            away_ratings = [ts.player_ratings[p].mu - 3 * ts.player_ratings[p].sigma 
                           for p in away_players if p in ts.player_ratings]
            
            if len(home_ratings) == 0 or len(away_ratings) == 0:
                continue
            
            home_trueskill = np.mean(home_ratings)
            away_trueskill = np.mean(away_ratings)
            
            # Calculate win probability using logistic function
            trueskill_diff = home_trueskill - away_trueskill
            trueskill_prob = 1 / (1 + 10 ** (-trueskill_diff / 400))
            
            game_features.append({
                'game_id': game_id,
                'game_date': game['game_date'],
                'home_team_id': home_team,
                'away_team_id': away_team,
                'home_trueskill': home_trueskill,
                'away_trueskill': away_trueskill,
                'trueskill_diff': trueskill_diff,
                'trueskill_prob': trueskill_prob,
                'home_win': game['home_win']
            })
            
            if (idx + 1) % 500 == 0:
                print(f"  Processed {idx + 1}/{len(games_df)} games...")
        
        df = pd.DataFrame(game_features)
        print(f"✅ Built TrueSkill features for {len(df)} games")
        
        return df
    
    def build_elo_features(self):
        """
        Calculate Elo ratings for each game using existing system.
        Returns DataFrame with game_id, home_elo, away_elo.
        """
        print("\n" + "="*80)
        print("📈 Building Elo Features")
        print("="*80)
        
        elo = NHLEloRating(k_factor=20, home_advantage=100, initial_rating=1500)
        
        # Get games chronologically
        games_query = """
        SELECT 
            game_id,
            game_date,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM games
        WHERE game_type = 2
        AND game_state = 'OFF'
        ORDER BY game_date, game_id
        """
        
        games_df = self.conn.execute(games_query).fetchdf()
        
        # Map team IDs to team names (Elo uses names)
        teams_query = """
        SELECT DISTINCT home_team_id as team_id, home_team_name as team_name
        FROM games
        WHERE home_team_id IS NOT NULL
        UNION
        SELECT DISTINCT away_team_id as team_id, away_team_name as team_name
        FROM games
        WHERE away_team_id IS NOT NULL
        """
        teams_df = self.conn.execute(teams_query).fetchdf()
        team_name_map = dict(zip(teams_df['team_id'], teams_df['team_name']))
        
        game_features = []
        
        for idx, game in games_df.iterrows():
            home_team_name = team_name_map.get(game['home_team_id'], str(game['home_team_id']))
            away_team_name = team_name_map.get(game['away_team_id'], str(game['away_team_id']))
            
            # Get current Elo ratings
            home_elo_rating = elo.get_rating(home_team_name)
            away_elo_rating = elo.get_rating(away_team_name)
            
            # Predict
            elo_prob = elo.predict(home_team_name, away_team_name)
            
            game_features.append({
                'game_id': game['game_id'],
                'game_date': game['game_date'],
                'home_team_id': game['home_team_id'],
                'away_team_id': game['away_team_id'],
                'home_elo': home_elo_rating,
                'away_elo': away_elo_rating,
                'elo_diff': home_elo_rating - away_elo_rating + elo.home_advantage,
                'elo_prob': elo_prob,
                'home_win': game['home_win']
            })
            
            # Update Elo after prediction
            elo.update(home_team_name, away_team_name, home_won=(game['home_score'] > game['away_score']))
            
            if (idx + 1) % 500 == 0:
                print(f"  Processed {idx + 1}/{len(games_df)} games...")
        
        df = pd.DataFrame(game_features)
        print(f"✅ Built Elo features for {len(df)} games")
        
        return df
    
    def load_xgboost_predictions(self):
        """Load existing XGBoost predictions if available."""
        print("\n" + "="*80)
        print("🤖 Loading XGBoost Predictions")
        print("="*80)
        
        pred_file = Path('data/xgboost_predictions.csv')
        
        if pred_file.exists():
            df = pd.read_csv(pred_file)
            print(f"✅ Loaded {len(df)} XGBoost predictions")
            return df
        else:
            print("⚠️  No XGBoost predictions found")
            return None
    
    def evaluate_model(self, y_true, y_pred_proba, model_name):
        """Evaluate a model's predictions."""
        
        # Convert probabilities to binary predictions
        y_pred = (y_pred_proba >= 0.5).astype(int)
        
        # Calculate metrics
        accuracy = accuracy_score(y_true, y_pred)
        auc = roc_auc_score(y_true, y_pred_proba)
        logloss = log_loss(y_true, y_pred_proba)
        
        # Additional metrics
        correct = (y_pred == y_true).sum()
        total = len(y_true)
        
        results = {
            'model': model_name,
            'accuracy': accuracy,
            'auc': auc,
            'log_loss': logloss,
            'correct': int(correct),
            'total': int(total),
            'num_games': int(total)
        }
        
        self.results[model_name] = results
        
        return results
    
    def build_glicko2_features(self):
        """Calculate Glicko-2 ratings for each game."""
        print("\n" + "="*80)
        print("🎲 Building Glicko-2 Features")
        print("="*80)
        
        glicko = NHLGlicko2()
        glicko.load_player_info()
        glicko.process_games()
        
        # Get games and calculate team ratings
        games_query = """
        SELECT 
            game_id,
            game_date,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM games
        WHERE game_type = 2
        AND game_state = 'OFF'
        ORDER BY game_date, game_id
        """
        
        games_df = self.conn.execute(games_query).fetchdf()
        
        game_features = []
        
        for idx, game in games_df.iterrows():
            game_id = game['game_id']
            home_team = game['home_team_id']
            away_team = game['away_team_id']
            
            # Get players for teams
            player_query = f"""
            SELECT player_id, team_id
            FROM player_game_stats
            WHERE game_id = '{game_id}'
            AND player_id IS NOT NULL
            """
            
            players = self.conn.execute(player_query).fetchdf()
            home_players = players[players['team_id'] == home_team]['player_id'].tolist()
            away_players = players[players['team_id'] == away_team]['player_id'].tolist()
            
            if len(home_players) == 0 or len(away_players) == 0:
                continue
            
            # Calculate team ratings
            home_ratings = [glicko.player_ratings[p].mu - 2 * glicko.player_ratings[p].phi
                           for p in home_players if p in glicko.player_ratings]
            away_ratings = [glicko.player_ratings[p].mu - 2 * glicko.player_ratings[p].phi
                           for p in away_players if p in glicko.player_ratings]
            
            if len(home_ratings) == 0 or len(away_ratings) == 0:
                continue
            
            home_glicko = np.mean(home_ratings)
            away_glicko = np.mean(away_ratings)
            glicko_diff = home_glicko - away_glicko
            
            # Win probability using logistic function
            glicko_prob = 1 / (1 + 10 ** (-glicko_diff / 400))
            
            game_features.append({
                'game_id': game_id,
                'home_glicko': home_glicko,
                'away_glicko': away_glicko,
                'glicko_diff': glicko_diff,
                'glicko_prob': glicko_prob
            })
            
            if (idx + 1) % 500 == 0:
                print(f"  Processed {idx + 1}/{len(games_df)} games...")
        
        df = pd.DataFrame(game_features)
        print(f"✅ Built Glicko-2 features for {len(df)} games")
        
        return df
    
    def build_openskill_features(self):
        """Calculate OpenSkill ratings for each game."""
        print("\n" + "="*80)
        print("🔓 Building OpenSkill Features")
        print("="*80)
        
        openskill = NHLOpenSkill()
        openskill.load_player_info()
        openskill.process_games()
        
        # Get games and calculate team ratings
        games_query = """
        SELECT 
            game_id,
            game_date,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM games
        WHERE game_type = 2
        AND game_state = 'OFF'
        ORDER BY game_date, game_id
        """
        
        games_df = self.conn.execute(games_query).fetchdf()
        
        game_features = []
        
        for idx, game in games_df.iterrows():
            game_id = game['game_id']
            home_team = game['home_team_id']
            away_team = game['away_team_id']
            
            # Get players for teams
            player_query = f"""
            SELECT player_id, team_id
            FROM player_game_stats
            WHERE game_id = '{game_id}'
            AND player_id IS NOT NULL
            """
            
            players = self.conn.execute(player_query).fetchdf()
            home_players = players[players['team_id'] == home_team]['player_id'].tolist()
            away_players = players[players['team_id'] == away_team]['player_id'].tolist()
            
            if len(home_players) == 0 or len(away_players) == 0:
                continue
            
            # Calculate team ratings
            home_ratings = [openskill.player_ratings[p].mu - 3 * openskill.player_ratings[p].sigma
                           for p in home_players if p in openskill.player_ratings]
            away_ratings = [openskill.player_ratings[p].mu - 3 * openskill.player_ratings[p].sigma
                           for p in away_players if p in openskill.player_ratings]
            
            if len(home_ratings) == 0 or len(away_ratings) == 0:
                continue
            
            home_openskill = np.mean(home_ratings)
            away_openskill = np.mean(away_ratings)
            openskill_diff = home_openskill - away_openskill
            
            # Win probability using logistic function
            openskill_prob = 1 / (1 + 10 ** (-openskill_diff / 400))
            
            game_features.append({
                'game_id': game_id,
                'home_openskill': home_openskill,
                'away_openskill': away_openskill,
                'openskill_diff': openskill_diff,
                'openskill_prob': openskill_prob
            })
            
            if (idx + 1) % 500 == 0:
                print(f"  Processed {idx + 1}/{len(games_df)} games...")
        
        df = pd.DataFrame(game_features)
        print(f"✅ Built OpenSkill features for {len(df)} games")
        
        return df
    
    def compare_all_models(self):
        """Run full comparison of all models."""
        print("\n" + "="*80)
        print("🏒 NHL MODEL COMPARISON: TrueSkill vs Elo vs Glicko-2 vs OpenSkill")
        print("="*80)
        
        # Build features for all systems
        trueskill_df = self.build_trueskill_features()
        elo_df = self.build_elo_features()
        glicko2_df = self.build_glicko2_features()
        openskill_df = self.build_openskill_features()
        
        # Merge datasets
        df = trueskill_df.merge(
            elo_df[['game_id', 'home_elo', 'away_elo', 'elo_diff', 'elo_prob']],
            on='game_id',
            how='inner'
        )
        
        df = df.merge(
            glicko2_df[['game_id', 'home_glicko', 'away_glicko', 'glicko_diff', 'glicko_prob']],
            on='game_id',
            how='inner'
        )
        
        df = df.merge(
            openskill_df[['game_id', 'home_openskill', 'away_openskill', 'openskill_diff', 'openskill_prob']],
            on='game_id',
            how='inner'
        )
        
        print(f"\n📊 Combined dataset: {len(df)} games")
        
        # Split into train/test based on date
        split_date = df['game_date'].quantile(0.8)
        train_df = df[df['game_date'] <= split_date]
        test_df = df[df['game_date'] > split_date]
        
        print(f"📅 Train: {len(train_df)} games (up to {split_date})")
        print(f"📅 Test: {len(test_df)} games (after {split_date})")
        
        # Evaluate models on test set
        print("\n" + "="*80)
        print("📊 TEST SET EVALUATION")
        print("="*80)
        
        y_true = test_df['home_win'].values
        
        # TrueSkill
        print("\n1️⃣  Evaluating TrueSkill...")
        ts_results = self.evaluate_model(
            y_true, 
            test_df['trueskill_prob'].values, 
            'TrueSkill'
        )
        
        # Elo
        print("2️⃣  Evaluating Elo...")
        elo_results = self.evaluate_model(
            y_true, 
            test_df['elo_prob'].values, 
            'Elo'
        )
        
        # Glicko-2
        print("3️⃣  Evaluating Glicko-2...")
        glicko_results = self.evaluate_model(
            y_true,
            test_df['glicko_prob'].values,
            'Glicko-2'
        )
        
        # OpenSkill
        print("4️⃣  Evaluating OpenSkill...")
        openskill_results = self.evaluate_model(
            y_true,
            test_df['openskill_prob'].values,
            'OpenSkill'
        )
        
        # Load XGBoost if available
        xgb_df = self.load_xgboost_predictions()
        if xgb_df is not None:
            # Merge with test set
            test_with_xgb = test_df.merge(
                xgb_df[['game_id', 'xgb_prob']], 
                on='game_id', 
                how='inner'
            )
            
            if len(test_with_xgb) > 0:
                print("3️⃣  Evaluating XGBoost...")
                xgb_results = self.evaluate_model(
                    test_with_xgb['home_win'].values,
                    test_with_xgb['xgb_prob'].values,
                    'XGBoost'
                )
        
        # Print comparison table
        self.print_results_table()
        
        # Save results
        self.save_results()
        
        # Create visualizations
        self.plot_roc_curves(test_df)
        self.plot_calibration_curves(test_df)
        
        return df, self.results
    
    def print_results_table(self):
        """Print formatted comparison table."""
        print("\n" + "="*80)
        print("🏆 MODEL COMPARISON RESULTS")
        print("="*80)
        
        # Create DataFrame for pretty printing
        results_df = pd.DataFrame(self.results).T
        results_df = results_df.sort_values('auc', ascending=False)
        
        print("\n" + results_df.to_string())
        
        # Highlight winner
        best_model = results_df.index[0]
        best_auc = results_df.iloc[0]['auc']
        
        print("\n" + "="*80)
        print(f"🥇 WINNER: {best_model} with AUC = {best_auc:.4f}")
        print("="*80)
    
    def save_results(self):
        """Save results to JSON file."""
        output_file = Path('data/all_models_comparison_results.json')
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to {output_file}")
    
    def plot_roc_curves(self, test_df):
        """Plot ROC curves for all models."""
        plt.figure(figsize=(12, 8))
        
        y_true = test_df['home_win'].values
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        
        # TrueSkill
        fpr_ts, tpr_ts, _ = roc_curve(y_true, test_df['trueskill_prob'].values)
        auc_ts = self.results['TrueSkill']['auc']
        plt.plot(fpr_ts, tpr_ts, label=f'TrueSkill (AUC={auc_ts:.3f})', linewidth=2.5, color=colors[0])
        
        # Elo
        fpr_elo, tpr_elo, _ = roc_curve(y_true, test_df['elo_prob'].values)
        auc_elo = self.results['Elo']['auc']
        plt.plot(fpr_elo, tpr_elo, label=f'Elo (AUC={auc_elo:.3f})', linewidth=2.5, color=colors[1])
        
        # Glicko-2
        fpr_g2, tpr_g2, _ = roc_curve(y_true, test_df['glicko_prob'].values)
        auc_g2 = self.results['Glicko-2']['auc']
        plt.plot(fpr_g2, tpr_g2, label=f'Glicko-2 (AUC={auc_g2:.3f})', linewidth=2.5, color=colors[2])
        
        # OpenSkill
        fpr_os, tpr_os, _ = roc_curve(y_true, test_df['openskill_prob'].values)
        auc_os = self.results['OpenSkill']['auc']
        plt.plot(fpr_os, tpr_os, label=f'OpenSkill (AUC={auc_os:.3f})', linewidth=2.5, color=colors[3])
        
        # Random baseline
        plt.plot([0, 1], [0, 1], 'k--', label='Random (AUC=0.500)', linewidth=1.5)
        
        plt.xlabel('False Positive Rate', fontsize=13)
        plt.ylabel('True Positive Rate', fontsize=13)
        plt.title('ROC Curves: All Rating Systems', fontsize=15, fontweight='bold')
        plt.legend(fontsize=11, loc='lower right')
        plt.grid(alpha=0.3)
        
        output_file = Path('data/roc_comparison_all.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 ROC curve saved to {output_file}")
        
        plt.close()
    
    def plot_calibration_curves(self, test_df):
        """Plot calibration curves to check if probabilities are well-calibrated."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        axes = axes.flatten()
        
        y_true = test_df['home_win'].values
        bins = np.linspace(0, 1, 11)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        models = [
            ('trueskill_prob', 'TrueSkill', '#1f77b4'),
            ('elo_prob', 'Elo', '#ff7f0e'),
            ('glicko_prob', 'Glicko-2', '#2ca02c'),
            ('openskill_prob', 'OpenSkill', '#d62728')
        ]
        
        for idx, (col, name, color) in enumerate(models):
            probs = test_df[col].values
            calibration = []
            for i in range(len(bins) - 1):
                mask = (probs >= bins[i]) & (probs < bins[i+1])
                if mask.sum() > 0:
                    calibration.append(y_true[mask].mean())
                else:
                    calibration.append(np.nan)
            
            axes[idx].plot(bin_centers, calibration, 'o-', label=name, linewidth=2.5, color=color, markersize=8)
            axes[idx].plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=1.5)
            axes[idx].set_xlabel('Predicted Probability', fontsize=12)
            axes[idx].set_ylabel('Observed Frequency', fontsize=12)
            axes[idx].set_title(f'{name} Calibration', fontsize=14, fontweight='bold')
            axes[idx].legend(fontsize=11)
            axes[idx].grid(alpha=0.3)
            axes[idx].set_xlim(-0.05, 1.05)
            axes[idx].set_ylim(-0.05, 1.05)
        
        plt.tight_layout()
        
        output_file = Path('data/calibration_comparison_all.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Calibration curves saved to {output_file}")
        
        plt.close()


def main():
    """Run the comparison."""
    comparison = ModelComparison()
    df, results = comparison.compare_all_models()
    
    print("\n" + "="*80)
    print("✅ COMPARISON COMPLETE!")
    print("="*80)
    print("\nFiles generated:")
    print("  - data/all_models_comparison_results.json")
    print("  - data/roc_comparison_all.png")
    print("  - data/calibration_comparison_all.png")


if __name__ == '__main__':
    main()
