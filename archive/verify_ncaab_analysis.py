import sys
from pathlib import Path

# Add plugins to path
plugins_dir = Path('plugins')
sys.path.append(str(plugins_dir.absolute()))

# Ensure data dir exists
Path('data/ncaab').mkdir(parents=True, exist_ok=True)

try:
    from ncaab_games import NCAABGames
    # Download data first (short run)
    print("Downloading/Checking data...")
    ng = NCAABGames()
    # We rely on existing download or partial
    # ng.download_games() # This might take too long if full, but it's needed
    # We assume data is there or quick to check.
    # Actually, we should call download_games() to be sure
    ng.download_games()
    
    from lift_gain_analysis import analyze_sport
    
    print("Running analysis...")
    overall, season = analyze_sport('ncaab')
    
    if overall:
        print("Analysis Successful.")
        print("Top Decile Win Rate:", overall[ overall['decile'] == 0 ]['win_rate'].values[0])
    else:
        print("Analysis failed to produce results.")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
