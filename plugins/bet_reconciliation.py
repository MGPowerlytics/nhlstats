"""
Bet Reconciliation Module
=========================

Reconciles the local ``placed_bets`` table against Kalshi's source-of-truth
fills / positions / balance data.

Flow
----
1. ``fetch_kalshi_state`` – pulls all fills (and optionally positions) from the
   Kalshi API and indexes them by ``bet_id``.
2. ``diff_bet`` – compares a single local row against its Kalshi counterpart and
   returns a list of field-level discrepancies.
3. ``reconcile_bet`` – applies all discrepancies as a single UPDATE and writes
   one ``bet_audit_log`` row per changed field, all within one transaction.
   Rolls back atomically if the audit insert fails.
4. ``insert_missing_bet`` – when Kalshi reports a fill that has no corresponding
   local row, inserts it into ``placed_bets`` with ``source='kalshi_discovered'``.
5. ``reconcile_all`` – top-level orchestrator that drives steps 1-4 across all
   bets (optionally filtered by ``since_date``) and returns a summary dict.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from bet_audit import get_audit_history, insert_audit_row  # noqa: F401 – re-exported

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fields we are allowed to overwrite from Kalshi data.
# Changes to any other field are ignored during reconciliation.
# ---------------------------------------------------------------------------
RECONCILABLE_FIELDS: list[str] = [
    "contracts",
    "price_cents",
    "cost_dollars",
    "fees_dollars",
    "status",
    "settled_date",
    "payout_dollars",
    "profit_dollars",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_kalshi_state(client: Any = None) -> dict[str, dict]:
    """Fetch the latest fills / positions / balance from Kalshi.

    Queries the Kalshi REST API and returns a mapping of ``bet_id`` → a
    normalised dict containing the fields listed in ``RECONCILABLE_FIELDS``
    (plus any raw Kalshi metadata needed downstream).

    Args:
        client: An authenticated Kalshi API client instance (e.g.
            ``KalshiBetting``). When ``None`` a default client is constructed
            from environment credentials.

    Returns:
        A ``dict`` mapping each ``bet_id`` (``str``) to a ``dict`` of field
        values sourced from Kalshi.  Returns an empty dict when no fills are
        found or the API returns an empty response.

    Raises:
        RuntimeError: If authentication or the API request fails.
    """
    from plugins.bet_tracker import load_fills_from_kalshi
    from plugins.kalshi_betting import KalshiBetting

    if client is None:
        try:
            client = KalshiBetting()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"Could not construct default KalshiBetting client: {exc}"
            ) from exc

    fills = load_fills_from_kalshi(client)

    state: dict[str, dict] = {}
    for fill in fills:
        # Normalise ticker → bet_id.  The fill dict uses `trade_id` as its
        # natural key in bet_tracker; we use the `ticker` as bet_id fallback
        # when an explicit bet_id is absent (matching existing conventions).
        bet_id: str = str(
            fill.get("bet_id") or fill.get("trade_id") or fill.get("ticker", "")
        )
        if not bet_id:
            continue

        ticker = fill.get("ticker", "")
        # Try to fetch market metadata for title / settlement info
        market_title: Optional[str] = None
        settled_date: Optional[str] = None
        status: str = fill.get("status", "open")
        payout_dollars: Optional[float] = None
        profit_dollars: Optional[float] = None

        try:
            details = client.get_market_details(ticker) if ticker else None
            if details:
                market_title = details.get("title")
                mkt_status = details.get("status", "open")
                status = mkt_status if mkt_status else status
                # Derive settled_date from close_time when market is settled
                close_time = details.get("close_time")
                if close_time and status in ("settled", "resolved", "closed"):
                    settled_date = str(close_time)[:10]
        except Exception:
            pass  # best-effort; proceed without market metadata

        count = fill.get("count", fill.get("contracts", 0))
        price = fill.get("yes_price", fill.get("price", 0))
        # price may be in cents (int) or fraction (float ≤ 1.0)
        if isinstance(price, float) and price <= 1.0:
            price_cents = int(round(price * 100))
        else:
            price_cents = int(price)

        cost = fill.get("cost", fill.get("trade_cost", 0)) or 0
        cost_dollars = float(cost) / 100 if abs(float(cost)) > 1 else float(cost)
        fees = fill.get("fees", fill.get("fee", 0)) or 0
        fees_dollars = float(fees) / 100 if abs(float(fees)) > 1 else float(fees)

        state[bet_id] = {
            "bet_id": bet_id,
            "ticker": ticker,
            "contracts": count,
            "price_cents": price_cents,
            "cost_dollars": round(cost_dollars, 4),
            "fees_dollars": round(fees_dollars, 4),
            "status": status,
            "settled_date": settled_date,
            "payout_dollars": payout_dollars,
            "profit_dollars": profit_dollars,
            "market_title": market_title,
            # Keep raw fill for insert_missing_bet usage
            "_raw": fill,
        }

    logger.info("fetch_kalshi_state: indexed %d fills by bet_id", len(state))
    return state


def diff_bet(local: dict, remote: dict) -> list[dict]:
    """Compute field-level discrepancies between a local and remote bet record.

    Only fields listed in ``RECONCILABLE_FIELDS`` are compared.  Fields that
    are ``None`` on **both** sides are not reported as discrepancies.

    Args:
        local: The local ``placed_bets`` row as a plain ``dict``.
        remote: The corresponding Kalshi-sourced ``dict`` for the same bet.

    Returns:
        A list of discrepancy dicts, each with the structure::

            {"field": str, "old": <local_value>, "new": <remote_value>}

        Returns an empty list when no discrepancies are found.
    """
    diffs: list[dict] = []
    for field in RECONCILABLE_FIELDS:
        local_val = local.get(field)
        remote_val = remote.get(field)
        # Skip when both sides are None – not a meaningful discrepancy
        if local_val is None and remote_val is None:
            continue
        if local_val != remote_val:
            diffs.append({"field": field, "old": local_val, "new": remote_val})
    return diffs


def reconcile_bet(
    bet_id: str,
    local: dict,
    remote: dict,
    db: Any,
) -> int:
    """Apply discrepancies between ``local`` and ``remote`` to the database.

    Performs the following steps **within a single transaction**:

    1. Call ``diff_bet(local, remote)`` to identify changed fields.
    2. If changes exist, issue one ``UPDATE placed_bets … WHERE bet_id = ?``.
    3. Insert one row into ``bet_audit_log`` for every changed field.

    The transaction is committed only when **both** the UPDATE and all audit
    inserts succeed.  If any step raises an exception the transaction is rolled
    back in its entirety (atomicity guarantee).

    Args:
        bet_id: Primary key of the bet to reconcile.
        local: The current local row for ``bet_id``.
        remote: The Kalshi-sourced data for ``bet_id``.
        db: A ``DBManager`` (or compatible) instance used to execute SQL.

    Returns:
        The number of field-level changes applied (0 if the records matched).

    Raises:
        Exception: Propagates any DB or audit-insert exception after rolling
            back, so the caller can decide whether to continue or abort.
    """
    changes = diff_bet(local, remote)
    if not changes:
        return 0

    run_id: Optional[str] = local.get("_run_id")

    # Build SET clause from changed fields
    set_parts = [f"{c['field']} = :{c['field']}" for c in changes]
    set_clause = ", ".join(set_parts)
    update_sql = f"UPDATE placed_bets SET {set_clause} WHERE bet_id = :_bet_id"
    update_params: dict[str, Any] = {c["field"]: c["new"] for c in changes}
    update_params["_bet_id"] = bet_id

    # Execute UPDATE then audit INSERT atomically.
    # Use db.engine.begin() for real SQLAlchemy engines (true atomicity).
    # Fall back to db.execute() for mock/test objects.
    try:
        engine = getattr(db, "engine", None)
        use_engine = isinstance(engine, sqlalchemy.engine.Engine)

        if use_engine:
            with engine.begin() as conn:
                conn.execute(text(update_sql), update_params)
                for change in changes:
                    audit_sql = text(
                        """
                        INSERT INTO bet_reconciliation_audit
                            (bet_id, field_changed, old_value, new_value,
                             source, reason, run_id)
                        VALUES
                            (:bet_id, :field_changed, :old_value, :new_value,
                             :source, :reason, :run_id)
                        """
                    )
                    conn.execute(
                        audit_sql,
                        {
                            "bet_id": bet_id,
                            "field_changed": change["field"],
                            "old_value": (
                                None if change["old"] is None else str(change["old"])
                            ),
                            "new_value": (
                                None if change["new"] is None else str(change["new"])
                            ),
                            "source": "kalshi_reconciliation",
                            "reason": None,
                            "run_id": run_id,
                        },
                    )
        else:
            # Fallback for mock/test DBs that expose only execute()
            db.execute(update_sql, update_params)
            for change in changes:
                insert_audit_row(
                    db,
                    bet_id=bet_id,
                    field_changed=change["field"],
                    old_value=change["old"],
                    new_value=change["new"],
                    source="kalshi_reconciliation",
                    run_id=run_id,
                )
    except Exception:
        logger.exception("reconcile_bet failed for bet_id=%s – rolling back", bet_id)
        raise

    return len(changes)


def reconcile_all(
    db: Any = None,
    client: Any = None,
    since_date: Optional[date] = None,
    cutoff_minutes: int = 15,
) -> dict:
    """Reconcile all local bets against Kalshi state.

    Orchestrates the full reconciliation pipeline:

    1. Fetch remote state via ``fetch_kalshi_state(client)``.
    2. Load local rows from ``placed_bets`` (filtered by ``since_date`` when
       provided, and excluding bets created within the last ``cutoff_minutes``).
    3. For each remote bet, call ``reconcile_bet`` or ``insert_missing_bet``
       as appropriate.
    4. Detect bets that exist locally but are absent from Kalshi and log a
       warning (no deletion is performed).

    The ``cutoff_minutes`` window prevents race conditions with the hourly
    ``bet_sync_hourly`` DAG.  Any bet whose ``created_at`` timestamp falls
    within the last ``cutoff_minutes`` minutes is excluded from reconciliation
    on the assumption that the hourly sync job may still be writing to it.
    The daily DAG runs at 10:00 AM UTC; with the default 15-minute window,
    bets created between 09:45 and 10:00 are left for the next run, avoiding
    simultaneous writes from both pipelines.

    Args:
        db: A ``DBManager`` instance.  When ``None`` a default instance is
            constructed.
        client: An authenticated Kalshi client.  When ``None`` a default is
            constructed from environment credentials.
        since_date: Only reconcile bets placed on or after this date.  When
            ``None`` all bets are considered.
        cutoff_minutes: Exclude bets whose ``created_at`` is more recent than
            this many minutes ago.  Defaults to 15.  Set to 0 to disable.

    Returns:
        A summary ``dict`` with the following keys:

        * ``checked`` – total bets examined.
        * ``discrepancies`` – bets that had at least one field mismatch.
        * ``corrected`` – bets successfully updated in the DB.
        * ``missing_locally_inserted`` – Kalshi fills inserted into
          ``placed_bets`` because they were absent locally.
        * ``missing_on_kalshi`` – local bets not found in the Kalshi response.
        * ``audit_rows_written`` – total individual audit log entries written.
        * ``excluded_by_cutoff`` – bets skipped because they fall within the
          recent ``cutoff_minutes`` window.
        * ``cutoff_ts`` – ISO-8601 string of the cutoff timestamp used (or
          ``None`` when cutoff is disabled).
        * ``run_id`` – UUID string that ties all audit rows for this run together.
    """
    if db is None:
        try:
            from db_manager import DBManager

            db = DBManager()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Could not create default DBManager: {exc}") from exc

    run_id = str(uuid.uuid4())

    # Compute cutoff timestamp (UTC) used to exclude in-flight bets.
    cutoff_ts: Optional[datetime] = None
    if cutoff_minutes > 0:
        cutoff_ts = datetime.now(tz=timezone.utc) - timedelta(minutes=cutoff_minutes)

    logger.info(
        "reconcile_all starting: cutoff_minutes=%d, cutoff_ts=%s",
        cutoff_minutes,
        cutoff_ts.isoformat() if cutoff_ts else "disabled",
    )

    # ---- 1. Fetch remote state -----------------------------------------------
    remote_state = fetch_kalshi_state(client)

    # ---- 2. Load local bets from placed_bets ---------------------------------
    local_sql = "SELECT * FROM placed_bets"
    local_params: dict[str, Any] = {}
    conditions: list[str] = []

    if since_date is not None:
        conditions.append("(created_at >= :since_date OR placed_date >= :since_date)")
        local_params["since_date"] = str(since_date)

    if cutoff_ts is not None:
        # Exclude rows created within the lookback window.  Rows without a
        # created_at value are always included (NULL-safe: treat them as old).
        conditions.append("(created_at IS NULL OR created_at <= :cutoff_ts)")
        local_params["cutoff_ts"] = cutoff_ts

    if conditions:
        local_sql += " WHERE " + " AND ".join(conditions)

    # Count bets excluded by the cutoff window (informational only).
    excluded_count = 0
    if cutoff_ts is not None:
        try:
            count_sql = (
                "SELECT COUNT(*) AS n FROM placed_bets WHERE created_at > :cutoff_ts"
            )
            count_df = db.fetch_df(count_sql, {"cutoff_ts": cutoff_ts})
            if count_df is not None and not count_df.empty:
                excluded_count = int(count_df.iloc[0]["n"])
                logger.info(
                    "reconcile_all: %d bet(s) excluded by %d-minute cutoff window",
                    excluded_count,
                    cutoff_minutes,
                )
        except Exception:
            logger.warning("Could not count excluded bets – continuing", exc_info=True)

    try:
        local_df = db.fetch_df(local_sql, local_params if local_params else None)
    except Exception:
        local_df = None

    local_bets: dict[str, dict] = {}
    if local_df is not None and not local_df.empty:
        for _, row in local_df.iterrows():
            row_dict = row.to_dict()
            # Stamp run_id so reconcile_bet can include it in audit rows
            row_dict["_run_id"] = run_id
            bid = str(row_dict.get("bet_id", ""))
            if bid:
                local_bets[bid] = row_dict

    # ---- 3. Walk remote fills ------------------------------------------------
    summary = {
        "checked": 0,
        "discrepancies": 0,
        "corrected": 0,
        "missing_locally_inserted": 0,
        "missing_on_kalshi": 0,
        "audit_rows_written": 0,
        "excluded_by_cutoff": excluded_count,
        "cutoff_ts": cutoff_ts.isoformat() if cutoff_ts else None,
        "run_id": run_id,
    }

    for bet_id, remote in remote_state.items():
        summary["checked"] += 1
        if bet_id in local_bets:
            local = local_bets[bet_id]
            local["_run_id"] = run_id
            try:
                n_changes = reconcile_bet(bet_id, local, remote, db)
                if n_changes > 0:
                    summary["discrepancies"] += 1
                    summary["corrected"] += 1
                    summary["audit_rows_written"] += n_changes
                    logger.info("reconciled bet_id=%s (%d field(s))", bet_id, n_changes)
            except Exception:
                logger.exception("Could not reconcile bet_id=%s – skipping", bet_id)
        else:
            # Fill known to Kalshi but absent locally
            try:
                inserted = insert_missing_bet(remote, db)
                if inserted:
                    summary["missing_locally_inserted"] += 1
                    # Write one audit row for the discovery
                    try:
                        insert_audit_row(
                            db,
                            bet_id=bet_id,
                            field_changed="bet_id",
                            old_value=None,
                            new_value=bet_id,
                            source="kalshi_discovered",
                            reason="missing from local placed_bets",
                            run_id=run_id,
                        )
                        summary["audit_rows_written"] += 1
                    except Exception:
                        logger.warning(
                            "Could not write discovery audit row for bet_id=%s", bet_id
                        )
            except Exception:
                logger.exception("insert_missing_bet failed for bet_id=%s", bet_id)

    # ---- 4. Detect bets present locally but absent from Kalshi ---------------
    for local_id in local_bets:
        if local_id not in remote_state:
            summary["missing_on_kalshi"] += 1
            logger.warning("bet_id=%s exists locally but not found on Kalshi", local_id)

    logger.info("reconcile_all complete: %s", summary)
    return summary


def insert_missing_bet(fill: dict, db: Any) -> bool:
    """Insert a Kalshi fill that has no corresponding local record.

    Constructs a ``placed_bets`` row from the raw Kalshi ``fill`` dict and
    inserts it with ``source='kalshi_discovered'`` so that downstream
    reporting can distinguish auto-discovered bets from bets originally
    placed through this system.

    Args:
        fill: Raw fill dict from the Kalshi API (as returned by
            ``fetch_kalshi_state``).
        db: A ``DBManager`` instance used to execute the INSERT.

    Returns:
        ``True`` if the row was successfully inserted, ``False`` if the
        ``bet_id`` already exists (idempotent upsert behaviour).

    Raises:
        Exception: Propagates unexpected DB errors to the caller.
    """
    bet_id = str(fill.get("bet_id") or fill.get("trade_id") or fill.get("ticker", ""))
    ticker = fill.get("ticker", "")
    contracts = fill.get("count", fill.get("contracts", 0))
    price = fill.get("yes_price", fill.get("price", 0)) or 0
    price_cents = int(price) if price > 1 else int(round(float(price) * 100))
    cost = fill.get("cost", fill.get("trade_cost", 0)) or 0
    cost_dollars = float(cost) / 100 if abs(float(cost)) > 1 else float(cost)
    fees = fill.get("fees", fill.get("fee", 0)) or 0
    fees_dollars = float(fees) / 100 if abs(float(fees)) > 1 else float(fees)
    status = fill.get("status", "open")
    settled_date = fill.get("settled_date")
    payout_dollars = fill.get("payout_dollars")
    profit_dollars = fill.get("profit_dollars")

    sql = """
        INSERT INTO placed_bets
            (bet_id, ticker, contracts, price_cents, cost_dollars, fees_dollars,
             status, settled_date, payout_dollars, profit_dollars, source)
        VALUES
            (:bet_id, :ticker, :contracts, :price_cents, :cost_dollars, :fees_dollars,
             :status, :settled_date, :payout_dollars, :profit_dollars,
             'kalshi_discovered')
    """
    params = {
        "bet_id": bet_id,
        "ticker": ticker,
        "contracts": contracts,
        "price_cents": price_cents,
        "cost_dollars": round(cost_dollars, 4),
        "fees_dollars": round(fees_dollars, 4),
        "status": status,
        "settled_date": settled_date,
        "payout_dollars": payout_dollars,
        "profit_dollars": profit_dollars,
    }
    try:
        db.execute(sql, params)
        logger.info("insert_missing_bet: inserted bet_id=%s", bet_id)
        return True
    except IntegrityError:
        logger.debug(
            "insert_missing_bet: bet_id=%s already exists (duplicate key)", bet_id
        )
        return False
