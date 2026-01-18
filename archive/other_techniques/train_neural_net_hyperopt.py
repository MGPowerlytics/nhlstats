"""
Train Neural Network model for NHL game prediction using PyTorch with Hyperopt.
Deep learning approach with hyperparameter optimization.
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report
from hyperopt import hp, fmin, tpe, Trials, STATUS_OK
import json
from pathlib import Path
import time


class NHLNet(nn.Module):
    """Neural network for NHL game prediction"""
    
    def __init__(self, input_dim, hidden_dims=[128, 64, 32], dropout=0.3):
        super(NHLNet, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        # Output layer
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)


def load_data():
    """Load and preprocess training data"""
    data_path = Path(__file__).parent.parent / "data" / "nhl_training_data.csv"
    df = pd.read_csv(data_path)
    
    # Separate features and target
    X = df.drop(['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win'], axis=1)
    y = df['home_win']
    
    # Handle NaN and infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)
    
    return X, y


def train_model(model, train_loader, val_loader, device, lr=0.001, weight_decay=0, epochs=50, patience=10):
    """Train the neural network with early stopping"""
    
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    
    best_val_loss = float('inf')
    patience_counter = 0
    best_model_state = None
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0.0
        
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X).squeeze()
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X).squeeze()
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
        
        train_loss /= len(train_loader)
        val_loss /= len(val_loader)
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
    
    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    return model


def evaluate_model(model, data_loader, device):
    """Evaluate model and return predictions"""
    model.eval()
    predictions = []
    
    with torch.no_grad():
        for batch_X, _ in data_loader:
            batch_X = batch_X.to(device)
            outputs = model(batch_X).squeeze()
            predictions.extend(outputs.cpu().numpy())
    
    return np.array(predictions)


def objective(params, X_train_scaled, y_train, X_val_scaled, y_val, device, trial_num):
    """Objective function for hyperopt"""
    
    print(f"\n{'='*60}")
    print(f"Trial {trial_num + 1}/30")
    print(f"{'='*60}")
    
    # Extract hyperparameters
    hidden_1 = int(params['hidden_1'])
    hidden_2 = int(params['hidden_2'])
    hidden_3 = int(params['hidden_3'])
    dropout = params['dropout']
    lr = params['lr']
    weight_decay = params['weight_decay']
    batch_size = int(params['batch_size'])
    
    print(f"Hyperparameters: Hidden=[{hidden_1}, {hidden_2}, {hidden_3}], "
          f"Dropout={dropout:.3f}, LR={lr:.6f}, WD={weight_decay:.6f}, BS={batch_size}")
    
    hidden_dims = [hidden_1, hidden_2, hidden_3]
    
    # Create data loaders
    X_train_tensor = torch.FloatTensor(X_train_scaled)
    y_train_tensor = torch.FloatTensor(y_train.values)
    X_val_tensor = torch.FloatTensor(X_val_scaled)
    y_val_tensor = torch.FloatTensor(y_val.values)
    
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Initialize and train model
    input_dim = X_train_scaled.shape[1]
    model = NHLNet(input_dim=input_dim, hidden_dims=hidden_dims, dropout=dropout)
    model = model.to(device)
    
    model = train_model(model, train_loader, val_loader, device, 
                       lr=lr, weight_decay=weight_decay, epochs=50, patience=10)
    
    # Evaluate
    train_preds = evaluate_model(model, train_loader, device)
    val_preds = evaluate_model(model, val_loader, device)
    
    train_auc = roc_auc_score(y_train, train_preds)
    val_auc = roc_auc_score(y_val, val_preds)
    
    # Custom loss: penalize overfitting
    loss = 1 - (val_auc - abs(train_auc - val_auc))
    
    print(f"Train AUC: {train_auc:.4f}, Val AUC: {val_auc:.4f}, Loss: {loss:.4f}")
    
    return {
        'loss': loss,
        'status': STATUS_OK,
        'train_auc': train_auc,
        'val_auc': val_auc
    }


def main():
    print("🏒 Training Neural Network with Hyperparameter Optimization\n")
    
    # Load data
    print("Loading training data...")
    X, y = load_data()
    print(f"  Dataset: {len(X)} games, {X.shape[1]} features")
    print(f"  Home win rate: {y.mean():.1%}\n")
    
    # Split data
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)
    
    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}\n")
    
    # Standardize
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # Search space
    space = {
        'hidden_1': hp.quniform('hidden_1', 64, 256, 16),
        'hidden_2': hp.quniform('hidden_2', 32, 128, 16),
        'hidden_3': hp.quniform('hidden_3', 16, 64, 8),
        'dropout': hp.uniform('dropout', 0.1, 0.5),
        'lr': hp.loguniform('lr', np.log(0.0001), np.log(0.01)),
        'weight_decay': hp.loguniform('weight_decay', np.log(1e-6), np.log(1e-3)),
        'batch_size': hp.choice('batch_size', [32, 64, 128])
    }
    
    # Hyperparameter optimization
    print("\n" + "="*60)
    print("HYPERPARAMETER OPTIMIZATION (30 trials)")
    print("="*60)
    
    trials = Trials()
    trial_counter = [0]
    
    def objective_wrapper(params):
        result = objective(params, X_train_scaled, y_train, X_val_scaled, y_val, device, trial_counter[0])
        trial_counter[0] += 1
        return result
    
    best = fmin(
        fn=objective_wrapper,
        space=space,
        algo=tpe.suggest,
        max_evals=30,
        trials=trials,
        verbose=0
    )
    
    # Get best trial
    best_trial = trials.best_trial
    best_result = best_trial['result']
    
    # Reconstruct best params
    batch_sizes = [32, 64, 128]
    best_params = {
        'hidden_1': int(best['hidden_1']),
        'hidden_2': int(best['hidden_2']),
        'hidden_3': int(best['hidden_3']),
        'dropout': best['dropout'],
        'lr': best['lr'],
        'weight_decay': best['weight_decay'],
        'batch_size': batch_sizes[best['batch_size']]
    }
    
    print("\n" + "="*60)
    print("🎯 BEST HYPERPARAMETERS")
    print("="*60)
    for key, val in best_params.items():
        if isinstance(val, float):
            print(f"  {key}: {val:.6f}")
        else:
            print(f"  {key}: {val}")
    print(f"\n  Best Val AUC: {best_result['val_auc']:.4f}")
    print(f"  Train AUC: {best_result['train_auc']:.4f}")
    print(f"  Overfit: {abs(best_result['train_auc'] - best_result['val_auc']):.4f}")
    
    # Train final model
    print("\n" + "="*60)
    print("TRAINING FINAL MODEL")
    print("="*60 + "\n")
    
    hidden_dims = [best_params['hidden_1'], best_params['hidden_2'], best_params['hidden_3']]
    
    # Create loaders
    X_train_tensor = torch.FloatTensor(X_train_scaled)
    y_train_tensor = torch.FloatTensor(y_train.values)
    X_val_tensor = torch.FloatTensor(X_val_scaled)
    y_val_tensor = torch.FloatTensor(y_val.values)
    X_test_tensor = torch.FloatTensor(X_test_scaled)
    y_test_tensor = torch.FloatTensor(y_test.values)
    
    batch_size = best_params['batch_size']
    train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor), batch_size=batch_size, shuffle=False)
    
    # Train
    input_dim = X_train.shape[1]
    model = NHLNet(input_dim=input_dim, hidden_dims=hidden_dims, dropout=best_params['dropout'])
    model = model.to(device)
    
    start_time = time.time()
    model = train_model(model, train_loader, val_loader, device,
                       lr=best_params['lr'], weight_decay=best_params['weight_decay'], 
                       epochs=100, patience=15)
    training_time = time.time() - start_time
    
    # Evaluate
    train_preds = evaluate_model(model, train_loader, device)
    val_preds = evaluate_model(model, val_loader, device)
    test_preds = evaluate_model(model, test_loader, device)
    
    train_auc = roc_auc_score(y_train, train_preds)
    val_auc = roc_auc_score(y_val, val_preds)
    test_auc = roc_auc_score(y_test, test_preds)
    
    test_pred_binary = (test_preds > 0.5).astype(int)
    test_accuracy = accuracy_score(y_test, test_pred_binary)
    baseline_accuracy = y_test.mean()
    
    print("\n" + "="*60)
    print("📊 FINAL MODEL PERFORMANCE")
    print("="*60)
    print(f"  Train AUC: {train_auc:.4f}")
    print(f"  Val AUC:   {val_auc:.4f}")
    print(f"  Test AUC:  {test_auc:.4f}")
    print(f"  Overfit:   {train_auc - val_auc:.4f}")
    print(f"\n  Test Accuracy: {test_accuracy:.4f}")
    print(f"  Baseline:      {baseline_accuracy:.4f}")
    print(f"  Improvement:   {test_accuracy - baseline_accuracy:.4f}")
    print(f"\n  Training time: {training_time:.1f}s")
    
    print(f"\nClassification Report:")
    print(classification_report(y_test, test_pred_binary, target_names=['Away Win', 'Home Win']))
    
    # Save
    output_dir = Path(__file__).parent
    model_path = output_dir / "neural_net_hyperopt_model.pt"
    results_path = output_dir / "neural_net_hyperopt_results.json"
    
    torch.save({
        'model_state_dict': model.state_dict(),
        'scaler': scaler,
        'input_dim': input_dim,
        'hidden_dims': hidden_dims,
        'dropout': best_params['dropout'],
        'best_params': best_params
    }, model_path)
    
    results = {
        'train_auc': float(train_auc),
        'val_auc': float(val_auc),
        'test_auc': float(test_auc),
        'test_accuracy': float(test_accuracy),
        'baseline_accuracy': float(baseline_accuracy),
        'training_time': float(training_time),
        'n_games': len(X),
        'best_params': best_params
    }
    
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Model saved to {model_path}")
    print(f"✅ Results saved to {results_path}")


if __name__ == "__main__":
    main()
