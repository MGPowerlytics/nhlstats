from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from plugins.db_manager import DBManager, default_db
from plugins.portfolio_snapshots import ensure_portfolio_snapshots_table


@dataclass(frozen=True)
class CashDeposit:
    """A cash deposit record."""

    deposit_id: int
    deposit_date: date
    amount_dollars: float
    deposit_type: str  # 'initial', 'detected', 'manual'
    notes: Optional[str]
    created_at_utc: datetime


@dataclass
class DepositParams:
    """Parameters for creating or updating a deposit.

    Groups related primitive parameters to avoid Primitive Obsession.
    """

    deposit_date: date
    amount_dollars: float
    deposit_type: str = "detected"
    notes: Optional[str] = None


def ensure_cash_deposits_table(db: DBManager = default_db) -> None:
    """Create the cash_deposits table if needed."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cash_deposits (
            deposit_id SERIAL PRIMARY KEY,
            deposit_date DATE NOT NULL,
            amount_dollars DOUBLE PRECISION NOT NULL,
            deposit_type VARCHAR(20) NOT NULL,
            notes TEXT,
            created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Create index on deposit_date for faster queries
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_cash_deposits_date ON cash_deposits(deposit_date)"
        )
    except Exception:
        pass

    # Ensure portfolio snapshots table exists with deposit tracking column
    ensure_portfolio_snapshots_table(db)


def _normalize_deposit_date(deposit_date: date | datetime) -> date:
    """Convert datetime to date if needed.

    Args:
        deposit_date: Date or datetime of the deposit

    Returns:
        Normalized date object
    """
    if isinstance(deposit_date, datetime):
        return deposit_date.date()
    return deposit_date


def _get_existing_deposit_id(
    db: DBManager, deposit_date: date, deposit_type: str
) -> Optional[int]:
    """Check if a deposit already exists for the given date and type.

    Args:
        db: Database manager
        deposit_date: Date of the deposit
        deposit_type: Type of deposit

    Returns:
        Existing deposit ID if found, None otherwise
    """
    existing = db.fetch_df(
        """
        SELECT deposit_id FROM cash_deposits
        WHERE deposit_date = :date
        AND deposit_type = :type
        """,
        {"date": deposit_date, "type": deposit_type},
    )

    if not existing.empty:
        return int(existing.iloc[0]["deposit_id"])
    return None


def _update_existing_deposit(
    db: DBManager, deposit_id: int, amount_dollars: float, notes: Optional[str]
) -> None:
    """Update an existing deposit record.

    Args:
        db: Database manager
        deposit_id: ID of the deposit to update
        amount_dollars: New amount in dollars
        notes: Optional notes about the deposit
    """
    db.execute(
        """
        UPDATE cash_deposits
        SET amount_dollars = :amount,
            notes = :notes,
            created_at_utc = CURRENT_TIMESTAMP
        WHERE deposit_id = :id
        """,
        {"amount": amount_dollars, "notes": notes, "id": deposit_id},
    )


def _insert_new_deposit(
    db: DBManager,
    params: DepositParams,
) -> int:
    """Insert a new deposit record and return its ID.

    Args:
        db: Database manager
        params: Deposit parameters

    Returns:
        ID of the newly created deposit
    """
    db.execute(
        """
        INSERT INTO cash_deposits (deposit_date, amount_dollars, deposit_type, notes)
        VALUES (:date, :amount, :type, :notes)
        """,
        {
            "date": params.deposit_date,
            "amount": params.amount_dollars,
            "type": params.deposit_type,
            "notes": params.notes,
        },
    )

    # Fetch the newly created deposit_id
    result = db.fetch_df(
        """
        SELECT deposit_id FROM cash_deposits
        WHERE deposit_date = :date AND deposit_type = :type
        ORDER BY created_at_utc DESC
        LIMIT 1
        """,
        {"date": params.deposit_date, "type": params.deposit_type},
    )
    return int(result.iloc[0]["deposit_id"])


def upsert_deposit(
    *,
    deposit_date: date | datetime,
    amount_dollars: float,
    deposit_type: str = "detected",
    notes: Optional[str] = None,
    db: DBManager = default_db,
) -> int:
    """Insert or update a deposit record.

    Args:
        deposit_date: Date of the deposit
        amount_dollars: Amount in dollars
        deposit_type: Type of deposit ('initial', 'detected', 'manual')
        notes: Optional notes about the deposit
        db: Database manager

    Returns:
        deposit_id: ID of the inserted/updated deposit
    """
    ensure_cash_deposits_table(db)

    # Normalize date input
    normalized_date = _normalize_deposit_date(deposit_date)

    # Create deposit parameters object
    params = DepositParams(
        deposit_date=normalized_date,
        amount_dollars=amount_dollars,
        deposit_type=deposit_type,
        notes=notes,
    )

    # Check for existing deposit
    existing_id = _get_existing_deposit_id(db, normalized_date, deposit_type)

    if existing_id is not None:
        # Update existing deposit
        _update_existing_deposit(db, existing_id, amount_dollars, notes)
        return existing_id
    else:
        # Insert new deposit
        return _insert_new_deposit(db, params)


def calculate_total_deposits(
    *, up_to_date: Optional[date | datetime] = None, db: DBManager = default_db
) -> float:
    """Calculate total deposits up to a given date.

    Args:
        up_to_date: Calculate deposits up to this date (inclusive). If None, use all deposits.
        db: Database manager

    Returns:
        Total deposits in dollars
    """
    ensure_cash_deposits_table(db)

    if up_to_date is None:
        result = db.fetch_df(
            "SELECT COALESCE(SUM(amount_dollars), 0.0) as total FROM cash_deposits"
        )
    else:
        if isinstance(up_to_date, datetime):
            up_to_date = up_to_date.date()

        result = db.fetch_df(
            """
            SELECT COALESCE(SUM(amount_dollars), 0.0) as total
            FROM cash_deposits
            WHERE deposit_date <= :date
            """,
            {"date": up_to_date},
        )

    return float(result.iloc[0]["total"])


def detect_new_deposits(
    snapshots: List[Dict[str, Any]], *, db: DBManager = default_db
) -> List[Dict[str, Any]]:
    """Detect new deposits by comparing balance changes.

    Logic:
    - If balance increases between snapshots WITHOUT corresponding bet wins,
      it's likely a deposit
    - balance_increase = balance(t) - balance(t-1)
    - bet_wins = sum of payouts between t-1 and t
    - if balance_increase > bet_wins: deposit = balance_increase - bet_wins

    Args:
        snapshots: List of dicts with 'snapshot_hour_utc' and 'balance_dollars'
        db: Database manager

    Returns:
        List of detected deposits with 'deposit_date' and 'amount_dollars'
    """
    detected_deposits = []

    # Sort by time
    snapshots_sorted = sorted(snapshots, key=lambda x: x["snapshot_hour_utc"])

    for i in range(1, len(snapshots_sorted)):
        prev = snapshots_sorted[i - 1]
        curr = snapshots_sorted[i]

        balance_increase = _calculate_balance_increase(prev, curr)

        if balance_increase > 0:
            total_bet_wins = _get_bet_wins_in_period(
                db, prev["snapshot_hour_utc"], curr["snapshot_hour_utc"]
            )

            # If balance increased more than bet wins, likely a deposit
            if balance_increase > total_bet_wins + 0.01:  # 1 cent tolerance
                deposit_amount = balance_increase - total_bet_wins
                deposit_record = _create_deposit_record(curr, deposit_amount)
                detected_deposits.append(deposit_record)

    return detected_deposits


def _calculate_balance_increase(
    prev_snapshot: Dict[str, Any], curr_snapshot: Dict[str, Any]
) -> float:
    """Calculate balance increase between two snapshots.

    Args:
        prev_snapshot: Previous snapshot dictionary
        curr_snapshot: Current snapshot dictionary

    Returns:
        Balance increase (positive if balance increased)
    """
    return curr_snapshot["balance_dollars"] - prev_snapshot["balance_dollars"]


def _get_bet_wins_in_period(
    db: DBManager, start_time: datetime, end_time: datetime
) -> float:
    """Get total bet wins in a time period.

    Args:
        db: Database manager
        start_time: Start of time period
        end_time: End of time period

    Returns:
        Total bet wins in dollars (0.0 if query fails)
    """
    try:
        bet_wins = db.fetch_df(
            """
            SELECT COALESCE(SUM(payout_dollars), 0.0) as total
            FROM placed_bets
            WHERE settled_date > :prev_time
            AND settled_date <= :curr_time
            AND status = 'won'
            """,
            {
                "prev_time": start_time,
                "curr_time": end_time,
            },
        )

        return float(bet_wins.iloc[0]["total"]) if not bet_wins.empty else 0.0
    except Exception as e:
        # If query fails (table doesn't exist, etc.), assume no bet wins
        print(f"⚠️  Could not check bet wins: {e}")
        return 0.0


def _create_deposit_record(
    snapshot: Dict[str, Any], deposit_amount: float
) -> Dict[str, Any]:
    """Create a deposit record dictionary from snapshot data.

    Args:
        snapshot: Snapshot dictionary with 'snapshot_hour_utc'
        deposit_amount: Deposit amount in dollars

    Returns:
        Deposit record dictionary
    """
    snapshot_time = snapshot["snapshot_hour_utc"]
    deposit_date = (
        snapshot_time.date() if isinstance(snapshot_time, datetime) else snapshot_time
    )

    return {
        "deposit_date": deposit_date,
        "amount_dollars": deposit_amount,
    }


def calculate_net_profit(
    current_portfolio_value: float, *, db: DBManager = default_db
) -> float:
    """Calculate true net profit accounting for deposits.

    Net Profit = Current Portfolio Value - Total Deposits

    Args:
        current_portfolio_value: Current value of portfolio (cash + open positions)
        db: Database manager

    Returns:
        Net profit in dollars (negative = loss)
    """
    total_deposits = calculate_total_deposits(db=db)
    return current_portfolio_value - total_deposits


def initialize_starting_deposit(
    *,
    deposit_date: date | datetime,
    amount_dollars: float,
    notes: Optional[str] = None,
    db: DBManager = default_db,
) -> int:
    """Record the initial deposit into Kalshi.

    Args:
        deposit_date: Date of initial deposit (e.g., Jan 18, 2026)
        amount_dollars: Initial deposit amount (e.g., $100)
        notes: Optional notes
        db: Database manager

    Returns:
        deposit_id: ID of the initial deposit record
    """
    return upsert_deposit(
        deposit_date=deposit_date,
        amount_dollars=amount_dollars,
        deposit_type="initial",
        notes=notes or "Initial Kalshi deposit",
        db=db,
    )
