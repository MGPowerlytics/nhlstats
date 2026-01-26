import duckdb


def list_tables():
    conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)
    tables = conn.execute("SHOW TABLES").fetchall()
    print("Tables in DuckDB:")
    for t in tables:
        print(f"- {t[0]}")
        # Get count
        count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"  Count: {count}")
    conn.close()


if __name__ == "__main__":
    list_tables()
