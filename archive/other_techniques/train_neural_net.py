"""
Train Neural Network model for NHL game prediction using PyTorch.
Deep learning approach with multiple hidden layers.
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report
import json
from pathlib import Path


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
    X = X.fillna(0)  # Replace NaN with 0
    
    return X, y


def train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=100, patience=10):
    """Train neural network with early stopping"""
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    best_val_loss = float('inf')
    patience_counter = 0
    best_model_state = None
    
    train_losses = []
    val_losses = []
    
    for epoch in range(num_epochs):
        # Training
        model.train()
        train_loss = 0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            
            optimizer.zero_grad()
            outputs = model(X_batch).squeeze()
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        train_losses.append(train_loss)
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                outputs = model(X_batch).squeeze()
                loss = criterion(outputs, y_batch)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        val_losses.append(val_loss)
        
        # Early stopping check
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1
        
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1}/{num_epochs} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
        if patience_counter >= patience:
            print(f"  Early stopping at epoch {epoch+1}")
            break
    
    # Restore best model
    model.load_state_dict(best_model_state)
    return model


def evaluate_model(model, data_loader, device):
    """Evaluate model and return predictions"""
    model.eval()
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for X_batch, y_batch in data_loader:
            X_batch = X_batch.to(device)
            outputs = model(X_batch).squeeze()
            all_preds.extend(outputs.cpu().numpy())
            all_labels.extend(y_batch.numpy())
    
    return np.array(all_preds), np.array(all_labels)


def main():
    print("🏒 Training Neural Network Model for NHL Game Prediction\n")
    
    # Load data
    print("Loading training data...")
    X, y = load_data()
    print(f"  Dataset: {len(X)} games, {X.shape[1]} features")
    print(f"  Home win rate: {y.mean():.1%}\n")
    
    # Split data: 70% train, 15% validation, 15% test
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.1765, random_state=42)
    
    print(f"Train set: {len(X_train)} games")
    print(f"Val set:   {len(X_val)} games")
    print(f"Test set:  {len(X_test)} games\n")
    
    # Standardize features
    print("Standardizing features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Convert to PyTorch tensors
    X_train_tensor = torch.FloatTensor(X_train_scaled)
    y_train_tensor = torch.FloatTensor(y_train.values)
    X_val_tensor = torch.FloatTensor(X_val_scaled)
    y_val_tensor = torch.FloatTensor(y_val.values)
    X_test_tensor = torch.FloatTensor(X_test_scaled)
    y_test_tensor = torch.FloatTensor(y_test.values)
    
    # Create data loaders
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
    test_dataset = TensorDataset(X_test_tensor, y_test_tensor)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    test_loader = DataLoader(test_dataset, batch_size=32)
    
    # Initialize model
    print("Initializing neural network...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"  Using device: {device}")
    
    model = NHLNet(
        input_dim=X_train.shape[1],
        hidden_dims=[128, 64, 32],
        dropout=0.3
    )
    
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
    
    # Train model
    print("\nTraining model...")
    model = train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=100, patience=15)
    
    # Evaluate on all sets
    print("\nEvaluating model...")
    
    train_pred, train_labels = evaluate_model(model, train_loader, device)
    val_pred, val_labels = evaluate_model(model, val_loader, device)
    test_pred, test_labels = evaluate_model(model, test_loader, device)
    
    train_auc = roc_auc_score(train_labels, train_pred)
    val_auc = roc_auc_score(val_labels, val_pred)
    test_auc = roc_auc_score(test_labels, test_pred)
    
    test_pred_binary = (test_pred > 0.5).astype(int)
    test_acc = accuracy_score(test_labels, test_pred_binary)
    
    print(f"\n📊 Model Performance:")
    print(f"  Train AUC: {train_auc:.4f}")
    print(f"  Val AUC:   {val_auc:.4f}")
    print(f"  Test AUC:  {test_auc:.4f}")
    print(f"  Overfit:   {abs(train_auc - val_auc):.4f}\n")
    
    print(f"Test Set Results:")
    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Baseline Acc:  {test_labels.mean():.4f} (always predict home win)")
    print(f"  Improvement:   {(test_acc - test_labels.mean()):.4f}\n")
    
    print("Classification Report:")
    print(classification_report(test_labels, test_pred_binary, target_names=['Away Win', 'Home Win']))
    
    # Save model and results
    output_dir = Path(__file__).parent
    
    # Save PyTorch model
    model_path = output_dir / "neural_net_model.pt"
    torch.save({
        'model_state_dict': model.state_dict(),
        'input_dim': X_train.shape[1],
        'scaler_mean': scaler.mean_,
        'scaler_scale': scaler.scale_
    }, model_path)
    print(f"\n✅ Model saved to {model_path}")
    
    # Save results
    results = {
        'model': 'Neural Network',
        'architecture': {
            'input_dim': int(X_train.shape[1]),
            'hidden_dims': [128, 64, 32],
            'dropout': 0.3,
            'optimizer': 'Adam',
            'learning_rate': 0.001
        },
        'train_auc': float(train_auc),
        'val_auc': float(val_auc),
        'test_auc': float(test_auc),
        'test_accuracy': float(test_acc),
        'baseline_accuracy': float(test_labels.mean()),
        'num_games': len(X),
        'num_features': X.shape[1]
    }
    
    results_path = output_dir / "neural_net_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {results_path}")


if __name__ == "__main__":
    main()
