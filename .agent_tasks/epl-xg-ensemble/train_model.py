"""Train the EPL ensemble model with xg features."""
import os
import sys
sys.path.insert(0, '/mnt/data2/nhlstats')
os.environ['POSTGRES_HOST'] = '172.20.0.2'

from plugins.elo.epl_ensemble import EPLEnsembleModel

m = EPLEnsembleModel(auto_train=False)
print("Training from CSVs...")
m.train_from_csvs(data_dir='data/epl')
m.save()
print(f"Fitted: {m.is_trained}")
print(f"Features ({len(m.features)}): {m.features}")
print(f"Coefs shape: {m.model.coef_.shape}")
print("Model saved to:", m.artifact_path)
