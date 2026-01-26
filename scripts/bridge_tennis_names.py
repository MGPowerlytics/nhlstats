import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
from db_manager import default_db
from naming_resolver import NamingResolver


def bridge_tennis():
    print("🎾 Performing Comprehensive Tennis Name Bridging...")

    # 1. Get all known Elo names from DB
    query = "SELECT canonical_name FROM canonical_mappings WHERE sport='TENNIS' AND source_system='elo'"
    elo_names = [r[0] for r in default_db.fetch_df(query).values.tolist()]
    elo_names = [n[0] if isinstance(n, list) else n for n in elo_names]
    print(f"  ✓ Loaded {len(elo_names)} Elo canonical names.")

    # 2. Get all external athlete names currently in game_odds (from The Odds API)
    query = """
        SELECT DISTINCT outcome_name
        FROM game_odds
        WHERE outcome_name NOT IN ('home', 'away', 'draw')
    """
    ext_results = default_db.fetch_df(query).values.tolist()
    ext_names = [n[0] for n in ext_results]
    print(f"  ✓ Loaded {len(ext_names)} external names to bridge.")
    if ext_names:
        print(f"  [DEBUG] Sample external names: {ext_names[:5]}")

    matches = 0
    for ext_name in ext_names:
        # Example ext_name: "Carlos Alcaraz"
        parts = ext_name.split()
        if len(parts) < 2:
            continue

        last = parts[-1]
        first_initial = parts[0][0]

        # Search for "Last Initial." or "Last I." in elo_names
        target = None
        for elo_name in elo_names:
            # Elo format: "Alcaraz C."
            if elo_name.startswith(last) and elo_name.endswith(f" {first_initial}."):
                target = elo_name
                break

        if target:
            print(f"    🔗 Mapping: '{ext_name}' -> '{target}'")
            NamingResolver.add_mapping("TENNIS", "the_odds_api", ext_name, target)
            NamingResolver.add_mapping("TENNIS", "kalshi", ext_name, target)
            # Also map the short version (just last name) if it's in Kalshi
            NamingResolver.add_mapping("TENNIS", "kalshi", last, target)
            matches += 1

    print(f"✅ Successfully bridged {matches} tennis names.")


if __name__ == "__main__":
    bridge_tennis()
