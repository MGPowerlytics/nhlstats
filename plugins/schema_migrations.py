"""Governed PostgreSQL schema migration runner for the stats schema."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Literal, Sequence

from sqlalchemy import inspect, text

from plugins.db_manager import DBManager


MIGRATION_FILENAME_PATTERN = re.compile(r"^(V\d+)__(.+)\.sql$")
DOLLAR_QUOTE_PATTERN = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
DEFAULT_MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent / "migrations" / "stats_schema"
)
LEGACY_CHECKSUMS_BY_VERSION: dict[str, frozenset[str]] = {
    # Historical local runtimes recorded this earlier V008 checksum before the
    # checked-in chain expanded with later dashboard/model-health migrations.
    # Keep the exception narrow so checksum enforcement remains strict for every
    # other version while allowing governed forward-only recovery.
    "V008": frozenset(
        {"d615452bf1bca66261163a8d1563cabec020927167213e174b1f88472a78fcc8"}
    ),
}
LEDGER_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
RelationType = Literal["table", "view"]


@dataclass(frozen=True)
class ExpectedRelation:
    """A governed database relation and its required relation type."""

    name: str
    relation_type: RelationType


EXPECTED_DASHBOARD_SOURCE_TABLES = (
    "bet_recommendations",
    "portfolio_value_snapshots",
    "tennis_model_evaluations",
)
EXPECTED_DASHBOARD_VIEWS = (
    "dashboard_portfolio_v1",
    "dashboard_live_markets_v1",
    "dashboard_rankings_v1",
    "dashboard_calibration_v1",
    "dashboard_data_quality_v1",
    "dashboard_bet_detail_v1",
    "dashboard_tennis_predictions_v1",
    "dashboard_tennis_model_health_v1",
    "dashboard_mlb_model_health_v1",
)
EXPECTED_GOVERNED_READ_MODEL_VIEWS = (
    "governed_evidence_record_v1",
    "governed_recommendation_execution_link_v1",
    "governed_clv_evidence_envelope_v1",
    "sport_validation_state_v1",
    "governed_portfolio_risk_state_v1",
)
EXPECTED_VERSIONED_READ_MODEL_VIEWS = (
    *EXPECTED_DASHBOARD_VIEWS,
    *EXPECTED_GOVERNED_READ_MODEL_VIEWS,
)
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
    "mlb_player_game_batting_stats",
    "mlb_player_game_pitching_stats",
    "mlb_pitch_level_features",
    "mlb_player_rolling_features",
    "mlb_environment_features",
    "mlb_travel_features",
    "mlb_matchup_features",
    "mlb_market_signals",
    "mlb_model_predictions",
    "mlb_prop_predictions",
    "mlb_odds_snapshots",
    "bet_reconciliation_audit",
    "placed_bets",
    "elo_ratings",
    *EXPECTED_DASHBOARD_SOURCE_TABLES,
)
EXPECTED_STATS_RELATIONS = (
    *(
        ExpectedRelation(name=table_name, relation_type="table")
        for table_name in EXPECTED_STATS_TABLES
    ),
    *(
        ExpectedRelation(name=view_name, relation_type="view")
        for view_name in EXPECTED_VERSIONED_READ_MODEL_VIEWS
    ),
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
        self,
        db: DBManager,
        migrations_dir: Path | None = None,
        expected_tables: Sequence[str] | None = None,
        expected_views: Sequence[str] | None = None,
        expected_relations: (
            Sequence[ExpectedRelation | tuple[str, RelationType]] | None
        ) = None,
    ) -> None:
        self.db = db
        self.migrations_dir = Path(migrations_dir or DEFAULT_MIGRATIONS_DIR)
        self.expected_tables = tuple(expected_tables or EXPECTED_STATS_TABLES)
        default_views = (
            EXPECTED_VERSIONED_READ_MODEL_VIEWS
            if expected_tables is None and expected_relations is None
            else ()
        )
        self.expected_views = tuple(
            expected_views if expected_views is not None else default_views
        )
        self.expected_relations = self._build_expected_relations(
            expected_tables=self.expected_tables,
            expected_views=self.expected_views,
            expected_relations=expected_relations,
        )

    def discover_migrations(self) -> List[Migration]:
        """Load migration metadata from disk in version order."""
        if not self.migrations_dir.exists():
            raise FileNotFoundError(
                f"Migration directory not found: {self.migrations_dir}"
            )

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
                    if not self._checksums_match(
                        version=migration.version,
                        applied_checksum=existing["checksum"],
                        file_checksum=migration.checksum,
                    ):
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
            and not self._checksums_match(
                version=migration.version,
                applied_checksum=applied_by_version[migration.version]["checksum"],
                file_checksum=migration.checksum,
            )
        ]
        relation_checks = self._check_expected_relations()
        missing_relations = [
            check["name"] for check in relation_checks if check["actual_type"] is None
        ]
        wrong_relation_types = [
            check
            for check in relation_checks
            if check["actual_type"] is not None
            and check["actual_type"] != check["expected_type"]
        ]
        missing_tables = [
            check["name"]
            for check in relation_checks
            if check["expected_type"] == "table" and check["actual_type"] is None
        ]
        missing_views = [
            check["name"]
            for check in relation_checks
            if check["expected_type"] == "view" and check["actual_type"] is None
        ]

        return {
            "applied": applied_rows,
            "expected_versions": [migration.version for migration in migrations],
            "missing_versions": missing_versions,
            "checksum_mismatches": checksum_mismatches,
            "expected_relations": [
                {
                    "name": relation.name,
                    "expected_type": relation.relation_type,
                }
                for relation in self.expected_relations
            ],
            "relation_checks": relation_checks,
            "missing_relations": missing_relations,
            "missing_tables": missing_tables,
            "missing_views": missing_views,
            "wrong_relation_types": wrong_relation_types,
        }

    def assert_verified(self) -> dict:
        """Raise when the current database state does not satisfy the migration contract."""
        status = self.verify()
        errors: list[str] = []
        if status["missing_versions"]:
            errors.append(
                f"Missing ledger versions: {', '.join(status['missing_versions'])}"
            )
        if status["checksum_mismatches"]:
            errors.append(
                f"Checksum mismatches: {', '.join(status['checksum_mismatches'])}"
            )
        if status["missing_tables"]:
            errors.append(f"Missing tables: {', '.join(status['missing_tables'])}")
        if status["missing_views"]:
            errors.append(f"Missing views: {', '.join(status['missing_views'])}")
        if status["wrong_relation_types"]:
            wrong_type_messages = [
                (
                    f"{check['name']} expected {check['expected_type']} "
                    f"but found {check['actual_type']}"
                )
                for check in status["wrong_relation_types"]
            ]
            errors.append(f"Wrong relation types: {', '.join(wrong_type_messages)}")
        if errors:
            raise RuntimeError("; ".join(errors))
        return status

    @staticmethod
    def _build_expected_relations(
        *,
        expected_tables: Sequence[str],
        expected_views: Sequence[str],
        expected_relations: (
            Sequence[ExpectedRelation | tuple[str, RelationType]] | None
        ),
    ) -> tuple[ExpectedRelation, ...]:
        if expected_relations is None:
            return (
                *(
                    ExpectedRelation(name=table_name, relation_type="table")
                    for table_name in expected_tables
                ),
                *(
                    ExpectedRelation(name=view_name, relation_type="view")
                    for view_name in expected_views
                ),
            )

        normalized: list[ExpectedRelation] = []
        for relation in expected_relations:
            if isinstance(relation, ExpectedRelation):
                normalized.append(relation)
            else:
                name, relation_type = relation
                normalized.append(
                    ExpectedRelation(name=name, relation_type=relation_type)
                )
        return tuple(normalized)

    def _check_expected_relations(self) -> list[dict]:
        inspector = inspect(self.db.engine)
        table_names = set(inspector.get_table_names())
        view_names = set(inspector.get_view_names())
        relation_checks: list[dict] = []

        for relation in self.expected_relations:
            actual_type: RelationType | None
            if relation.name in table_names:
                actual_type = "table"
            elif relation.name in view_names:
                actual_type = "view"
            else:
                actual_type = None

            relation_checks.append(
                {
                    "name": relation.name,
                    "expected_type": relation.relation_type,
                    "actual_type": actual_type,
                }
            )

        return relation_checks

    @staticmethod
    def _checksums_match(
        *, version: str, applied_checksum: str, file_checksum: str
    ) -> bool:
        """Return True when a ledger checksum is compatible with a file checksum."""
        if applied_checksum == file_checksum:
            return True
        return applied_checksum in LEGACY_CHECKSUMS_BY_VERSION.get(version, frozenset())

    @staticmethod
    def _execute_sql_script(conn, sql_script: str) -> None:
        """Execute a simple SQL script composed of semicolon-delimited statements."""
        statements = _split_sql_statements(sql_script)
        for statement in statements:
            conn.execute(text(statement))


def _split_sql_statements(sql_script: str) -> list[str]:
    """Split a migration script without breaking quoted literals or comments."""
    statements: list[str] = []
    current: list[str] = []
    index = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_quote_tag: str | None = None

    while index < len(sql_script):
        char = sql_script[index]
        next_char = sql_script[index + 1] if index + 1 < len(sql_script) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                current.append(char)
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            if char == "\n":
                current.append(char)
            index += 1
            continue

        if dollar_quote_tag is not None:
            if sql_script.startswith(dollar_quote_tag, index):
                current.append(dollar_quote_tag)
                index += len(dollar_quote_tag)
                dollar_quote_tag = None
                continue
            current.append(char)
            index += 1
            continue

        if in_single_quote:
            current.append(char)
            if char == "'":
                if next_char == "'":
                    current.append(next_char)
                    index += 2
                    continue
                in_single_quote = False
            index += 1
            continue

        if in_double_quote:
            current.append(char)
            if char == '"':
                if next_char == '"':
                    current.append(next_char)
                    index += 2
                    continue
                in_double_quote = False
            index += 1
            continue

        if char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            in_single_quote = True
            current.append(char)
            index += 1
            continue

        if char == '"':
            in_double_quote = True
            current.append(char)
            index += 1
            continue

        if char == "$":
            match = DOLLAR_QUOTE_PATTERN.match(sql_script, index)
            if match:
                dollar_quote_tag = match.group(0)
                current.append(dollar_quote_tag)
                index = match.end()
                continue

        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    trailing_statement = "".join(current).strip()
    if trailing_statement:
        statements.append(trailing_statement)

    return statements


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
        verified_relations = [
            f"{relation.name} ({relation.relation_type})"
            for relation in runner.expected_relations
        ]
        print("Verified relations: " + ", ".join(verified_relations))
        return 0

    applied_rows = runner.list_applied_migrations()
    print(_format_applied_rows(applied_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
