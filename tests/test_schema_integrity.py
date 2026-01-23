import pytest
from plugins.db_manager import default_db
from plugins.database_schema_manager import DatabaseSchemaManager
from plugins.bet_tracker import create_bets_table
from plugins.bet_loader import BetLoader

@pytest.fixture(scope="function", autouse=True)
def setup_schema():
    """Create schema for integrity tests."""
    manager = DatabaseSchemaManager(default_db)
    manager.create_unified_tables()
    create_bets_table(default_db)
    # Instantiate BetLoader to create bet_recommendations table
    BetLoader(db_manager=default_db)

def test_placed_bets_has_primary_key():
    """
    Test that the placed_bets table has a primary key constraint.
    This ensures data integrity and idempotency for bet tracking.
    """
    # Query to check for primary key on placed_bets
    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'placed_bets'
          AND constraint_type = 'PRIMARY KEY';
    """
    df = default_db.fetch_df(query)

    # Assert that at least one row is returned (meaning a PK exists)
    assert not df.empty, "placed_bets table is missing a Primary Key constraint"

def test_unified_games_has_primary_key():
    """Verify unified_games has a PK."""
    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'unified_games'
          AND constraint_type = 'PRIMARY KEY';
    """
    df = default_db.fetch_df(query)
    assert not df.empty, "unified_games table is missing a Primary Key constraint"

def test_game_odds_has_primary_key():
    """Verify game_odds has a PK."""
    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'game_odds'
          AND constraint_type = 'PRIMARY KEY';
    """
    df = default_db.fetch_df(query)
    assert not df.empty, "game_odds table is missing a Primary Key constraint"

def test_bet_recommendations_has_primary_key():
    """Verify bet_recommendations has a PK."""
    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'bet_recommendations'
          AND constraint_type = 'PRIMARY KEY';
    """
    df = default_db.fetch_df(query)
    assert not df.empty, "bet_recommendations table is missing a Primary Key constraint"

def test_game_odds_has_foreign_key_to_unified_games():
    """Verify game_odds has an FK to unified_games."""
    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'game_odds'
          AND constraint_type = 'FOREIGN KEY';
    """
    df = default_db.fetch_df(query)
    # This is a bit loose, it checks for ANY FK. Ideally we check the specific one.
    # But for TDD "Red" phase, this is enough if it fails (assuming no FKs exist).
    assert not df.empty, "game_odds table is missing Foreign Key constraints"
