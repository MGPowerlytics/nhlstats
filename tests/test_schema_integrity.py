import pytest
from plugins.db_manager import default_db
from plugins.bet_tracker import create_bets_table
from plugins.bet_loader import BetLoader


@pytest.fixture(scope="function", autouse=True)
def setup_schema():
    """Create schema for integrity tests."""
    # Create bet tables directly using existing functions
    create_bets_table(default_db)
    # Materialize bet_recommendations explicitly for the SQLite-backed test DB
    loader = BetLoader(db_manager=default_db)
    loader._ensure_table()


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


def test_create_bets_table_uses_governed_chain_for_postgres(monkeypatch):
    """PostgreSQL placed_bets creation should route through the migration ledger."""
    import plugins.bet_tracker as bet_tracker_module

    calls = []

    class RunnerStub:
        def __init__(self, db) -> None:
            assert db is fake_db
            calls.append("init")

        def apply(self):
            calls.append("apply")
            return []

        def assert_verified(self):
            calls.append("verify")
            return {}

    class FakeDB:
        class Engine:
            class Dialect:
                name = "postgresql"

            dialect = Dialect()

        engine = Engine()

        def execute(self, _sql):
            raise AssertionError(
                "PostgreSQL placed_bets setup should not use helper-owned DDL"
            )

    fake_db = FakeDB()
    monkeypatch.setattr(bet_tracker_module, "SchemaMigrationRunner", RunnerStub)

    bet_tracker_module.create_bets_table(fake_db)

    assert calls == ["init", "apply", "verify"]


def test_create_bets_table_keeps_sqlite_compatibility():
    """Local/test SQLite paths may still materialize a compatibility table."""

    class FakeDB:
        class Engine:
            class Dialect:
                name = "sqlite"

            dialect = Dialect()

        engine = Engine()

        def __init__(self) -> None:
            self.executed = []

        def execute(self, sql):
            self.executed.append(sql)

    fake_db = FakeDB()

    create_bets_table(fake_db)

    assert len(fake_db.executed) == 1
    assert "CREATE TABLE placed_bets" in fake_db.executed[0]


@pytest.mark.skip(
    reason="unified_games PK constraint only enforced in production PostgreSQL, not in test SQLite"
)
def test_unified_games_has_primary_key():
    """Verify unified_games has a PK."""
    # Check if unified_games table exists first
    check_query = """
        SELECT table_name FROM information_schema.tables
        WHERE table_name = 'unified_games';
    """
    check_df = default_db.fetch_df(check_query)
    if check_df.empty:
        pytest.skip("unified_games table not created in test environment")

    query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'unified_games'
          AND constraint_type = 'PRIMARY KEY';
    """
    df = default_db.fetch_df(query)
    assert not df.empty, "unified_games table is missing a Primary Key constraint"


@pytest.mark.skip(
    reason="game_odds PK constraint only enforced in production PostgreSQL, not in test SQLite"
)
def test_game_odds_has_primary_key():
    """Verify game_odds has a PK."""
    # Check if game_odds table exists first
    check_query = """
        SELECT table_name FROM information_schema.tables
        WHERE table_name = 'game_odds';
    """
    check_df = default_db.fetch_df(check_query)
    if check_df.empty:
        pytest.skip("game_odds table not created in test environment")

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


@pytest.mark.skip(
    reason="game_odds FK constraint only enforced in production PostgreSQL, not in test SQLite"
)
def test_game_odds_has_foreign_key_to_unified_games():
    """Verify game_odds has an FK to unified_games."""
    # Check if game_odds table exists first
    check_query = """
        SELECT table_name FROM information_schema.tables
        WHERE table_name = 'game_odds';
    """
    check_df = default_db.fetch_df(check_query)
    if check_df.empty:
        pytest.skip("game_odds table not created in test environment")

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
