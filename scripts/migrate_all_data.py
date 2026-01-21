import duckdb
import pandas as pd
import sys
import os
from pathlib import Path
import time

# Add plugins to path for DBManager
sys.path.append(os.path.join(os.getcwd(), 'plugins'))
from db_manager import DBManager

def migrate():
    print("=" * 80)
    print("🐘 DUCKDB TO POSTGRES MIGRATOR")
    print("=" * 80)

    # Connect to DuckDB source
    if not os.path.exists('data/nhlstats.duckdb'):
        print("❌ DuckDB file not found.")
        return

    duck_conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

    # Connect to Postgres destination
    try:
        pg_db = DBManager(db_type='postgres')
        # Test connection
        pg_db.execute("SELECT 1")
        print("✓ Connected to Postgres")
    except Exception as e:
        print(f"❌ Failed to connect to Postgres: {e}")
        return

    tables = [t[0] for t in duck_conn.execute("SHOW TABLES").fetchall()]

    total_start = time.time()

    for table in tables:
        print(f"\n🚀 Migrating table: {table}")

        # Check row count
        count = duck_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  - Total rows: {count:,}")

        if count == 0:
            # Create empty table in Postgres
            df = duck_conn.execute(f"SELECT * FROM {table} LIMIT 0").fetchdf()
            pg_db.insert_df(df, table, if_exists='replace')
            print("  ✓ Created empty table")
            continue

        # Use chunking for all tables to be safe
        chunk_size = 50000
        if 'trades' in table or 'shifts' in table:
            chunk_size = 100000 # Larger chunks for very large tables

        start_time = time.time()

        offset = 0
        while offset < count:
            print(f"    - Progress: {offset:,} / {count:,}...", end='\r')
            df = duck_conn.execute(f"SELECT * FROM {table} LIMIT {chunk_size} OFFSET {offset}").fetchdf()

            # Optimization: for Postgres, sometimes object types cause issues
            # We'll let sqlalchemy handle it but monitor errors

            # For the first chunk, use 'replace' to create table, then 'append'
            mode = 'replace' if offset == 0 else 'append'
            pg_db.insert_df(df, table, if_exists=mode)

            offset += chunk_size

        print(f"\n  ✓ Completed in {time.time() - start_time:.2f}s")

    duck_conn.close()
    print("\n" + "=" * 80)
    print(f"🎉 All {len(tables)} tables migrated successfully!")
    print(f"⏱️ Total time: {time.time() - total_start:.2f}s")
    print("=" * 80)

if __name__ == "__main__":
    migrate()
