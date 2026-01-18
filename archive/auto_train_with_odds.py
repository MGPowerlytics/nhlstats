#!/usr/bin/env python3
"""
Automated pipeline to wait for OddsHarvester scraping, load data, and retrain model.
"""
import subprocess
import time
import sys
from pathlib import Path
import json


def check_scraping_complete(json_file, expected_min_games=100):
    """Check if scraping is complete by validating the JSON file."""
    if not Path(json_file).exists():
        return False, "File doesn't exist yet"
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if len(data) < expected_min_games:
            return False, f"Only {len(data)} games (expected >={expected_min_games})"
        
        return True, f"Found {len(data)} games"
    except json.JSONDecodeError:
        return False, "Invalid JSON (scraping still in progress)"
    except Exception as e:
        return False, f"Error: {e}"


def run_command(cmd, description):
    """Run a command and show output."""
    print(f"\n{'='*80}")
    print(f"🚀 {description}")
    print(f"{'='*80}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    
    print(f"\n✅ {description} completed successfully")
    return True


def main():
    json_file = "/mnt/data2/nhlstats/data/historical_odds/nhl_2023_2024.json"
    log_file = "/tmp/oddsharvest_2023_2024_new.log"
    
    print("="*80)
    print("🏒 NHL MODEL TRAINING PIPELINE WITH BETTING ODDS")
    print("="*80)
    print(f"\nWaiting for OddsHarvester to finish scraping...")
    print(f"JSON file: {json_file}")
    print(f"Log file: {log_file}")
    
    # Wait for scraping to complete
    check_interval = 60  # Check every minute
    max_wait = 3600  # Wait up to 1 hour
    waited = 0
    
    while waited < max_wait:
        complete, msg = check_scraping_complete(json_file, expected_min_games=100)
        
        if complete:
            print(f"\n✅ Scraping complete! {msg}")
            break
        
        print(f"⏳ {msg} - waiting {check_interval}s... (waited {waited}/{max_wait}s)")
        
        # Show last few log lines
        try:
            result = subprocess.run(
                f"tail -3 {log_file}",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                print(f"   Log: {result.stdout.strip().split(chr(10))[-1][:100]}")
        except:
            pass
        
        time.sleep(check_interval)
        waited += check_interval
    
    if waited >= max_wait:
        print(f"\n❌ Timeout waiting for scraping to complete after {max_wait}s")
        sys.exit(1)
    
    # Step 1: Load OddsHarvester data into DuckDB
    if not run_command(
        f"python load_odds_harvester_data.py {json_file}",
        "Loading OddsHarvester data into DuckDB"
    ):
        sys.exit(1)
    
    # Step 2: Regenerate training dataset
    if not run_command(
        "python build_training_dataset.py",
        "Regenerating training dataset with betting odds"
    ):
        sys.exit(1)
    
    # Step 3: Train model with hyperparameter tuning
    if not run_command(
        "python train_xgboost_hyperopt.py",
        "Training XGBoost model with hyperparameter tuning"
    ):
        sys.exit(1)
    
    print("\n" + "="*80)
    print("🎉 PIPELINE COMPLETE!")
    print("="*80)
    print("\nCheck the results in:")
    print("  - data/nhl_training_data.csv (updated dataset)")
    print("  - Trained model saved")
    print("  - Console output above for accuracy metrics")
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
