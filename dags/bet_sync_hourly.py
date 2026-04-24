"""
Hourly DAG to sync placed bets from Kalshi API to PostgreSQL database.

This ensures the Financial Performance dashboard always has up-to-date data
without requiring manual sync button clicks.

Also updates real closing line values (CLV) for recently settled bets using
the last pre-close odds snapshot from game_odds.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def sync_bets_from_kalshi():
    """
    Sync bets from Kalshi API to the placed_bets table.

    This function wraps the bet_tracker sync function for use in an Airflow task.
    It fetches all placed bets from Kalshi and upserts them into PostgreSQL.

    Returns:
        Tuple[int, int]: (added_count, updated_count) of bets synced
    """
    import sys

    # Ensure plugins can be imported when running in Airflow
    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from bet_tracker import sync_bets_to_database

    try:
        result = sync_bets_to_database()
        # Ensure we always get a tuple back (defensive programming)
        if result is None:
            print("⚠️  sync_bets_to_database returned None, using (0, 0)")
            added, updated = 0, 0
        else:
            added, updated = result
        print(f"✅ Synced bets: {added} added, {updated} updated")
        return added, updated
    except Exception as e:
        print(f"❌ Failed to sync bets: {e}")
        raise


def sync_orders_from_kalshi():
    """Sync orders from Kalshi (resting + executed) into placed_bets.

    Complements ``sync_bets_from_kalshi`` (fills-only) so resting and
    just-placed orders show up in the database immediately.
    """
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from bet_tracker import sync_orders_to_database

    try:
        added, updated = sync_orders_to_database()
        print(f"✅ Synced orders: {added} added, {updated} updated")
        return added, updated
    except Exception as e:
        print(f"❌ Failed to sync orders: {e}")
        raise


def update_closing_lines():
    """Update real closing line values for recently settled bets.

    Finds bets with binary CLV (0.0 or 1.0 closing_line_prob — the old bug)
    and replaces with real market closing prices from game_odds.

    Returns:
        int: Number of bets updated with real closing prices.
    """
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from clv_tracker import update_real_closing_lines

    try:
        count = update_real_closing_lines()
        print(f"✅ Updated {count} bets with real closing prices")
        return count
    except Exception as e:
        # CLV failures must NOT block bet syncing — log and continue
        print(f"⚠️ CLV update failed (non-blocking): {e}")
        return 0


# Default arguments for the DAG
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# Create the DAG
with DAG(
    dag_id="bet_sync_hourly",
    default_args=default_args,
    description="Sync placed bets from Kalshi API to database hourly",
    schedule="@hourly",
    start_date=datetime(2026, 1, 22),
    catchup=False,
    max_active_runs=1,
    tags=["betting", "kalshi", "sync", "clv"],
) as dag:
    sync_task = PythonOperator(
        task_id="sync_bets_from_kalshi",
        python_callable=sync_bets_from_kalshi,
        retries=3,
        retry_delay=timedelta(minutes=5),
    )

    orders_task = PythonOperator(
        task_id="sync_orders_from_kalshi",
        python_callable=sync_orders_from_kalshi,
        retries=3,
        retry_delay=timedelta(minutes=5),
    )

    clv_task = PythonOperator(
        task_id="update_closing_lines",
        python_callable=update_closing_lines,
        retries=1,
        retry_delay=timedelta(minutes=2),
    )

    # Orders sync runs alongside fills sync; CLV depends on both being fresh.
    [sync_task, orders_task] >> clv_task
