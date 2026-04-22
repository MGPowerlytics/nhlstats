"""Governed PostgreSQL schema migration runner for the stats schema."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from sqlalchemy import text

from plugins.db_manager import DBManager


MIGRATION_FILENAME_PATTERN = re.compile(r"^(V\d+)__(.+)\.sql$")
DEFAULT_MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent / "migrations" / "stats_schema"
)
LEDGER_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
EXPECTED_STATS_TABLES = (
    "schema_migrations",
    "games",
    "teams",
    "mlb_games",
    "nfl_games",
    "epl_games",
    "ligue1_games",
    "tennis_games",
    "ncaab_games",
    "wncaab_games",
    "unrivaled_games",
    "cba_games",
    "unified_games",
    "game_odds",
    "diagnostic_results",
    "team_game_stats",
    "nba_team_game_stats_ext",
    "nhl_team_game_stats_ext",
    "mlb_team_game_stats_ext",
    "nfl_team_game_stats_ext",
    "soccer_team_game_stats_ext",
    "ncaab_team_game_stats_ext",
    "wncaab_team_game_stats_ext",
    "tennis_player_match_stats",
    "bet_reconciliation_audit",
    "placed_bets",
)


@dataclass(frozen=True)
class Migration:
    """A checked-in migration file."""

    version: str
    name: str
    path: Path
    checksum: str
    sql: str


class SchemaMigrationRunner:
    """Apply and verify the governed in-repo stats schema migration chain."""

    def __init__(
        self, db: DBManager, migrations_dir: Path | None = None, expected_tables: Sequence[str] | None = None
    ) -> None:
        self.db = db
        self.migrations_dir = Path(migrations_dir or DEFAULT_MIGRATIONS_DIR)
        self.expected_tables = tuple(expected_tables or EXPECTED_STATS_TABLES)

    def discover_migrations(self) -> List[Migration]:
        """Load migration metadata from disk in version order."""
        if not self.migrations_dir.exists():
            raise FileNotFoundError(f"Migration directory not found: {self.migrations_dir}")

        migrations: list[Migration] = []
        seen_versions: set[str] = set()
        for path in sorted(self.migrations_dir.glob("V*.sql")):
            match = MIGRATION_FILENAME_PATTERN.match(path.name)
            if not match:
                raise ValueError(f"Invalid migration filename: {path.name}")

            version, raw_name = match.groups()
            if version in seen_versions:
                raise ValueError(f"Duplicate migration version detected: {version}")

            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            migrations.append(
                Migration(
                    version=version,
                    name=raw_name.replace("_", " "),
                    path=path,
                    checksum=checksum,
                    sql=sql,
                )
            )
            seen_versions.add(version)

        if not migrations:
            raise ValueError(f"No migrations found in {self.migrations_dir}")

        return migrations

    def ensure_ledger(self) -> None:
        """Create the schema_migrations ledger if it does not yet exist."""
        self.db.execute(LEDGER_BOOTSTRAP_SQL)

    def list_applied_migrations(self) -> list[dict]:
        """Return applied migration rows ordered by version."""
        self.ensure_ledger()
        with self.db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT version, name, checksum, applied_at
                    FROM schema_migrations
                    ORDER BY version
                    """
                )
            ).mappings()
            return [dict(row) for row in rows]

    def apply(self) -> list[Migration]:
        """Apply all pending migrations exactly once."""
        self.ensure_ledger()
        migrations = self.discover_migrations()
        applied_versions = {
            row["version"]: row for row in self.list_applied_migrations()
        }
        applied_now: list[Migration] = []

        with self.db.engine.begin() as conn:
            conn.execute(text(LEDGER_BOOTSTRAP_SQL))
            for migration in migrations:
                existing = applied_versions.get(migration.version)
                if existing:
                    if existing["checksum"] != migration.checksum:
                        raise RuntimeError(
                            f"Checksum mismatch for {migration.version}: "
                            f"ledger={existing['checksum']} file={migration.checksum}"
                        )
                    continue

                self._execute_sql_script(conn, migration.sql)
                conn.execute(
                    text(
                        """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES (:version, :name, :checksum)
                        """
                    ),
                    {
                        "version": migration.version,
                        "name": migration.name,
                        "checksum": migration.checksum,
                    },
                )
                applied_versions[migration.version] = {
                    "version": migration.version,
                    "checksum": migration.checksum,
                }
                applied_now.append(migration)

        return applied_now

    def verify(self) -> dict:
        """Validate ledger state and required stats tables."""
        migrations = self.discover_migrations()
        applied_rows = self.list_applied_migrations()
        applied_by_version = {row["version"]: row for row in applied_rows}
        missing_versions = [
            migration.version
            for migration in migrations
            if migration.version not in applied_by_version
        ]
        checksum_mismatches = [
            migration.version
            for migration in migrations
            if migration.version in applied_by_version
            and applied_by_version[migration.version]["checksum"] != migration.checksum
        ]
        missing_tables = [
            table_name
            for table_name in self.expected_tables
            if not self.db.table_exists(table_name)
        ]

        return {
            "applied": applied_rows,
            "expected_versions": [migration.version for migration in migrations],
            "missing_versions": missing_versions,
            "checksum_mismatches": checksum_mismatches,
            "missing_tables": missing_tables,
        }

    def assert_verified(self) -> dict:
        """Raise when the current database state does not satisfy the migration contract."""
        status = self.verify()
        errors: list[str] = []
        if status["missing_versions"]:
            errors.append(f"Missing ledger versions: {', '.join(status['missing_versions'])}")
        if status["checksum_mismatches"]:
            errors.append(
                f"Checksum mismatches: {', '.join(status['checksum_mismatches'])}"
            )
        if status["missing_tables"]:
            errors.append(f"Missing tables: {', '.join(status['missing_tables'])}")
        if errors:
            raise RuntimeError("; ".join(errors))
        return status

    @staticmethod
    def _execute_sql_script(conn, sql_script: str) -> None:
        """Execute a simple SQL script composed of semicolon-delimited statements."""
        statements = _split_sql_statements(sql_script)
        for statement in statements:
            conn.execute(text(statement))


def _split_sql_statements(sql_script: str) -> list[str]:
    """Split a migration script into executable statements."""
    cleaned_lines = [
        line for line in sql_script.splitlines() if not line.strip().startswith("--")
    ]
    cleaned_sql = "\n".join(cleaned_lines)
    return [statement.strip() for statement in cleaned_sql.split(";") if statement.strip()]


def build_connection_string() -> str | None:
    """Allow CLI callers to override the SQLAlchemy connection string."""
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("apply", "verify", "inspect"),
        help="Command to run against the stats schema migration chain.",
    )
    parser.add_argument(
        "--migration-dir",
        default=str(DEFAULT_MIGRATIONS_DIR),
        help="Directory containing versioned SQL migrations.",
    )
    parser.add_argument(
        "--connection-string",
        default=build_connection_string(),
        help="Optional SQLAlchemy connection string override.",
    )
    return parser


def _format_applied_rows(rows: Iterable[dict]) -> str:
    lines = ["Applied migrations:"]
    for row in rows:
        lines.append(f"  {row['version']} | {row['applied_at']} | {row['name']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for apply, verify, and ledger inspection."""
    args = _build_parser().parse_args(argv)
    db = DBManager(connection_string=args.connection_string)
    runner = SchemaMigrationRunner(db=db, migrations_dir=Path(args.migration_dir))

    if args.command == "apply":
        applied_now = runner.apply()
        if applied_now:
            print(
                "Applied pending migrations: "
                + ", ".join(migration.version for migration in applied_now)
            )
        else:
            print("Applied pending migrations: none")
        print(_format_applied_rows(runner.list_applied_migrations()))
        return 0

    if args.command == "verify":
        status = runner.assert_verified()
        print("Verified stats schema migrations successfully.")
        print(_format_applied_rows(status["applied"]))
        print("Verified tables: " + ", ".join(runner.expected_tables))
        return 0

    applied_rows = runner.list_applied_migrations()
    print(_format_applied_rows(applied_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
