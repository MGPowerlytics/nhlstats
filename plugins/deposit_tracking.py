from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any
import pandas as pd
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
    except:
        pass

    # Ensure portfolio snapshots table exists with deposit tracking column
    ensure_portfolio_snapshots_table(db)


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

    # Convert datetime to date if needed
    if isinstance(deposit_date, datetime):
        deposit_date = deposit_date.date()

    # Check if deposit already exists for this date and type
    existing = db.fetch_df(
        """
        SELECT deposit_id FROM cash_deposits
        WHERE deposit_date = :date
        AND deposit_type = :type
        """,
        {"date": deposit_date, "type": deposit_type},
    )

    if not existing.empty:
        # Update existing
        deposit_id = int(existing.iloc[0]["deposit_id"])
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
        return deposit_id
    else:
        # Insert new (use execute for auto-commit, then fetch the ID)
        db.execute(
            """
            INSERT INTO cash_deposits (deposit_date, amount_dollars, deposit_type, notes)
            VALUES (:date, :amount, :type, :notes)
            """,
            {
                "date": deposit_date,
                "amount": amount_dollars,
                "type": deposit_type,
                "notes": notes,
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
            {"date": deposit_date, "type": deposit_type},
        )
        return int(result.iloc[0]["deposit_id"])


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

        balance_increase = curr["balance_dollars"] - prev["balance_dollars"]

        if balance_increase > 0:
            # Check for bet wins in this period
            # Query placed_bets for payouts between prev and curr timestamps
            total_bet_wins = 0.0
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
                        "prev_time": prev["snapshot_hour_utc"],
                        "curr_time": curr["snapshot_hour_utc"],
                    },
                )

                total_bet_wins = (
                    float(bet_wins.iloc[0]["total"]) if not bet_wins.empty else 0.0
                )
            except Exception as e:
                # If query fails (table doesn't exist, etc.), assume no bet wins
                print(f"⚠️  Could not check bet wins: {e}")
                total_bet_wins = 0.0

            # If balance increased more than bet wins, likely a deposit
            if balance_increase > total_bet_wins + 0.01:  # 1 cent tolerance
                deposit_amount = balance_increase - total_bet_wins
                detected_deposits.append(
                    {
                        "deposit_date": (
                            curr["snapshot_hour_utc"].date()
                            if isinstance(curr["snapshot_hour_utc"], datetime)
                            else curr["snapshot_hour_utc"]
                        ),
                        "amount_dollars": deposit_amount,
                    }
                )

    return detected_deposits


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
