"""Free historical MLB odds source adapters."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

import pandas as pd

from plugins.mlb_modeling.features import stable_feature_hash


PRINCETON_HISTORICAL_SOURCE = "princeton_historical_sports_odds"
GITHUB_SPORTSBOOKREVIEW_SOURCE = "github_sportsbookreview_mlb_odds"
DEFAULT_FREE_HISTORICAL_ODDS_URL = "https://dss2.princeton.edu/data/246/"

_COLUMN_ALIASES = {
    "game_date": ("game_date", "date", "Date", "gameDate"),
    "home_team": ("home_team", "home", "Home", "home_name", "HomeTeam"),
    "away_team": ("away_team", "away", "Away", "away_name", "AwayTeam"),
    "home_score": ("home_score", "HomeScore", "home_final", "home_final_score"),
    "away_score": ("away_score", "AwayScore", "away_final", "away_final_score"),
    "home_open_ml": (
        "home_open_ml",
        "moneyline_open_home",
        "home_moneyline_open",
        "open_home_ml",
        "HomeOpenML",
        "open_ml_home",
    ),
    "away_open_ml": (
        "away_open_ml",
        "moneyline_open_away",
        "away_moneyline_open",
        "open_away_ml",
        "AwayOpenML",
        "open_ml_away",
    ),
    "home_close_ml": (
        "home_close_ml",
        "moneyline_close_home",
        "home_moneyline_close",
        "close_home_ml",
        "HomeCloseML",
        "close_ml_home",
    ),
    "away_close_ml": (
        "away_close_ml",
        "moneyline_close_away",
        "away_moneyline_close",
        "close_away_ml",
        "AwayCloseML",
        "close_ml_away",
    ),
    "commence_time": ("commence_time", "start_time", "StartTime", "game_time"),
}


def load_free_historical_mlb_odds(path: str) -> Any:
    """Load a free historical MLB odds file.

    Supported files are CSV, Excel, and JSON exports, including Princeton
    DSS-style historical sports odds files and GitHub-hosted SportsBookReview
    moneyline archives. The function reads only from the caller's provided
    path; it does not require any paid API.
    """
    source_path = Path(path)
    if source_path.suffix.lower() == ".json":
        return json.loads(source_path.read_text(encoding="utf-8"))
    if source_path.suffix.lower() in {".xls", ".xlsx"}:
        return pd.read_excel(source_path)
    return pd.read_csv(source_path)


def build_princeton_mlb_odds_snapshots(
    rows: Iterable[Mapping[str, Any]] | pd.DataFrame,
    *,
    source: str = PRINCETON_HISTORICAL_SOURCE,
    bookmaker_key: str = "consensus",
) -> List[dict[str, Any]]:
    """Build MLB odds snapshots from free Princeton-style odds rows."""
    frame = pd.DataFrame(rows).copy()
    normalized = _normalize_princeton_columns(frame)
    payloads: list[dict[str, Any]] = []
    for row in normalized.to_dict("records"):
        payloads.extend(
            _build_open_close_payloads(
                row=row,
                source=source,
                bookmaker_key=bookmaker_key,
            )
        )
    return payloads


def save_free_historical_mlb_odds(
    *,
    db: Any,
    path: str,
    source: str | None = None,
    bookmaker_key: str = "consensus",
) -> int:
    """Load a free historical MLB odds file and persist snapshots."""
    rows = load_free_historical_mlb_odds(path)
    if isinstance(rows, pd.DataFrame):
        payloads = build_princeton_mlb_odds_snapshots(
            rows,
            source=source or PRINCETON_HISTORICAL_SOURCE,
            bookmaker_key=bookmaker_key,
        )
    else:
        payloads = build_sportsbookreview_mlb_odds_snapshots(
            rows,
            source=source or GITHUB_SPORTSBOOKREVIEW_SOURCE,
        )
    for payload in payloads:
        upsert_mlb_odds_snapshot(db, payload)
    return len(payloads)


def build_sportsbookreview_mlb_odds_snapshots(
    rows: Mapping[str, Any],
    *,
    source: str = GITHUB_SPORTSBOOKREVIEW_SOURCE,
) -> List[dict[str, Any]]:
    """Build MLB odds snapshots from SportsBookReview-style JSON odds archives."""
    payloads: list[dict[str, Any]] = []
    for games in rows.values():
        for game in games:
            game_view = dict(game.get("gameView") or {})
            odds = dict(game.get("odds") or {})
            moneylines = odds.get("moneyline") or []
            home_team = str((game_view.get("homeTeam") or {}).get("fullName") or "")
            away_team = str((game_view.get("awayTeam") or {}).get("fullName") or "")
            if not home_team or not away_team:
                continue
            commence_time = _coerce_commence_time(
                game_view.get("startDate"),
                _coerce_date(game_view.get("startDate")),
            )
            game_date = commence_time.date()
            game_id = _game_id(game_date, home_team, away_team)
            source_event_id = str(game.get("id") or game_id)
            for moneyline in moneylines:
                sportsbook = str(moneyline.get("sportsbook") or "sportsbookreview")
                opening_line = moneyline.get("openingLine") or {}
                current_line = moneyline.get("currentLine") or {}
                payloads.extend(
                    _build_sportsbookreview_line_payloads(
                        source=source,
                        source_event_id=source_event_id,
                        game_id=game_id,
                        home_team=home_team,
                        away_team=away_team,
                        commence_time=commence_time,
                        sportsbook=sportsbook,
                        opening_line=opening_line,
                        current_line=current_line,
                        raw_payload=game,
                    )
                )
    return payloads


def upsert_mlb_odds_snapshot(db: Any, payload: Mapping[str, Any]) -> None:
    """Persist one MLB odds snapshot using the governed table."""
    db.execute(
        """
        INSERT INTO mlb_odds_snapshots (
            snapshot_id, source, sport, source_event_id, game_id, home_team,
            away_team, commence_time, requested_snapshot_at, source_snapshot_at,
            previous_snapshot_at, next_snapshot_at, snapshot_type, bookmaker_key,
            bookmaker_title, market_key, outcome_name, outcome_role,
            decimal_price, implied_probability, is_pregame, raw_payload
        ) VALUES (
            :snapshot_id, :source, :sport, :source_event_id, :game_id,
            :home_team, :away_team, CAST(:commence_time AS TIMESTAMP),
            CAST(:requested_snapshot_at AS TIMESTAMP),
            CAST(:source_snapshot_at AS TIMESTAMP),
            CAST(:previous_snapshot_at AS TIMESTAMP),
            CAST(:next_snapshot_at AS TIMESTAMP), :snapshot_type, :bookmaker_key,
            :bookmaker_title, :market_key, :outcome_name, :outcome_role,
            :decimal_price, :implied_probability, :is_pregame,
            CAST(:raw_payload AS JSONB)
        )
        ON CONFLICT (
            source, source_event_id, source_snapshot_at, snapshot_type,
            bookmaker_key, market_key, outcome_role
        ) DO UPDATE SET
            game_id = EXCLUDED.game_id,
            home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            commence_time = EXCLUDED.commence_time,
            bookmaker_title = EXCLUDED.bookmaker_title,
            outcome_name = EXCLUDED.outcome_name,
            decimal_price = EXCLUDED.decimal_price,
            implied_probability = EXCLUDED.implied_probability,
            raw_payload = EXCLUDED.raw_payload
        """,
        {
            **dict(payload),
            "snapshot_id": odds_snapshot_id(payload),
            "raw_payload": json.dumps(payload.get("raw_payload"), sort_keys=True),
        },
    )


def odds_snapshot_id(payload: Mapping[str, Any]) -> str:
    """Return deterministic primary key for an odds snapshot payload."""
    return stable_feature_hash(
        {
            "source": payload["source"],
            "source_event_id": payload["source_event_id"],
            "source_snapshot_at": payload["source_snapshot_at"],
            "snapshot_type": payload["snapshot_type"],
            "bookmaker_key": payload["bookmaker_key"],
            "market_key": payload["market_key"],
            "outcome_role": payload["outcome_role"],
        }
    )


def american_to_decimal(american_odds: float) -> float:
    """Convert American moneyline odds to decimal odds."""
    odds = float(american_odds)
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    if odds > 0:
        return round((odds / 100.0) + 1.0, 6)
    return round((100.0 / abs(odds)) + 1.0, 6)


def _normalize_princeton_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in frame.columns:
                renamed[alias] = canonical
                break
    normalized = frame.rename(columns=renamed)
    required = {
        "game_date",
        "home_team",
        "away_team",
        "home_open_ml",
        "away_open_ml",
        "home_close_ml",
        "away_close_ml",
    }
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(f"missing free MLB odds columns: {sorted(missing)}")
    return normalized


def _build_open_close_payloads(
    *,
    row: Mapping[str, Any],
    source: str,
    bookmaker_key: str,
) -> list[dict[str, Any]]:
    game_date = _coerce_date(row["game_date"])
    commence_time = _coerce_commence_time(row.get("commence_time"), game_date)
    open_snapshot = datetime.combine(
        game_date, time(0, 0), tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    close_snapshot = (commence_time - timedelta(minutes=1)).isoformat().replace(
        "+00:00", "Z"
    )
    commence_iso = commence_time.isoformat().replace("+00:00", "Z")
    home_team = str(row["home_team"])
    away_team = str(row["away_team"])
    game_id = _game_id(game_date, home_team, away_team)
    source_event_id = str(row.get("source_event_id") or game_id)
    specs = [
        ("open", "home", home_team, row["home_open_ml"], open_snapshot),
        ("open", "away", away_team, row["away_open_ml"], open_snapshot),
        ("close", "home", home_team, row["home_close_ml"], close_snapshot),
        ("close", "away", away_team, row["away_close_ml"], close_snapshot),
    ]
    payloads = []
    for snapshot_type, outcome_role, outcome_name, american_odds, snapshot_at in specs:
        if american_odds in (None, ""):
            continue
        american_value = float(american_odds)
        if american_value == 0:
            continue
        decimal_price = american_to_decimal(american_value)
        payloads.append(
            {
                "schema_version": "v1",
                "sport": "MLB",
                "payload_kind": "odds_snapshot",
                "source": source,
                "source_event_id": source_event_id,
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "commence_time": commence_iso,
                "requested_snapshot_at": None,
                "source_snapshot_at": snapshot_at,
                "previous_snapshot_at": None,
                "next_snapshot_at": None,
                "snapshot_type": snapshot_type,
                "bookmaker_key": bookmaker_key,
                "bookmaker_title": "Consensus",
                "market_key": "h2h",
                "outcome_name": outcome_name,
                "outcome_role": outcome_role,
                "decimal_price": decimal_price,
                "implied_probability": round(1.0 / decimal_price, 8),
                "is_pregame": True,
                "raw_payload": dict(row),
            }
        )
    return payloads


def _build_sportsbookreview_line_payloads(
    *,
    source: str,
    source_event_id: str,
    game_id: str,
    home_team: str,
    away_team: str,
    commence_time: datetime,
    sportsbook: str,
    opening_line: Mapping[str, Any],
    current_line: Mapping[str, Any],
    raw_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    commence_iso = commence_time.isoformat().replace("+00:00", "Z")
    open_snapshot = datetime.combine(
        commence_time.date(), time(0, 0), tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    close_snapshot = (commence_time - timedelta(minutes=1)).isoformat().replace(
        "+00:00", "Z"
    )
    specs = [
        ("open", "home", home_team, opening_line.get("homeOdds"), open_snapshot),
        ("open", "away", away_team, opening_line.get("awayOdds"), open_snapshot),
        ("close", "home", home_team, current_line.get("homeOdds"), close_snapshot),
        ("close", "away", away_team, current_line.get("awayOdds"), close_snapshot),
    ]
    payloads: list[dict[str, Any]] = []
    for snapshot_type, outcome_role, outcome_name, american_odds, snapshot_at in specs:
        if american_odds in (None, ""):
            continue
        american_value = float(american_odds)
        if american_value == 0:
            continue
        decimal_price = american_to_decimal(american_value)
        payloads.append(
            {
                "schema_version": "v1",
                "sport": "MLB",
                "payload_kind": "odds_snapshot",
                "source": source,
                "source_event_id": source_event_id,
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "commence_time": commence_iso,
                "requested_snapshot_at": None,
                "source_snapshot_at": snapshot_at,
                "previous_snapshot_at": None,
                "next_snapshot_at": None,
                "snapshot_type": snapshot_type,
                "bookmaker_key": sportsbook,
                "bookmaker_title": sportsbook.replace("_", " ").title(),
                "market_key": "h2h",
                "outcome_name": outcome_name,
                "outcome_role": outcome_role,
                "decimal_price": decimal_price,
                "implied_probability": round(1.0 / decimal_price, 8),
                "is_pregame": True,
                "raw_payload": dict(raw_payload),
            }
        )
    return payloads


def _game_id(game_date: date, home_team: str, away_team: str) -> str:
    home_slug = "".join(ch for ch in home_team.upper() if ch.isalnum())
    away_slug = "".join(ch for ch in away_team.upper() if ch.isalnum())
    return f"MLB_{game_date:%Y%m%d}_{home_slug}_{away_slug}"


def _coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _coerce_commence_time(value: Optional[Any], game_date: date) -> datetime:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return datetime.combine(game_date, time(23, 59), tzinfo=timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
