#!/usr/bin/env python3
"""
Dashboard Connection Diagnostic Tool
Run this before starting the dashboard to verify everything is configured correctly.
"""

import sys
import os
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / 'plugins'))

def check_postgres_container():
    """Check if PostgreSQL container is running."""
    import subprocess
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=postgres', '--format', '{{.Status}}'],
            capture_output=True,
            text=True
        )
        if 'Up' in result.stdout and 'healthy' in result.stdout:
            print('✓ PostgreSQL container is running and healthy')
            return True
        else:
            print('✗ PostgreSQL container is not running or not healthy')
            print(f'  Status: {result.stdout.strip()}')
            return False
    except Exception as e:
        print(f'✗ Error checking Docker: {e}')
        return False

def check_environment_variables():
    """Check environment variables."""
    print('\n=== Environment Variables ===')
    vars_to_check = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
    all_set = True
    for var in vars_to_check:
        value = os.getenv(var)
        if value:
            # Hide password
            display_value = '***' if 'PASSWORD' in var else value
            print(f'✓ {var} = {display_value}')
        else:
            print(f'⚠ {var} = not set (will use default)')
            all_set = False

    if not all_set:
        print('\nNote: Missing variables will use defaults:')
        print('  POSTGRES_HOST=localhost')
        print('  POSTGRES_PORT=5432')
        print('  POSTGRES_DB=airflow')
        print('  POSTGRES_USER=airflow')
        print('  POSTGRES_PASSWORD=airflow')

    return True

def check_database_connection():
    """Test database connection."""
    print('\n=== Database Connection ===')
    try:
        from db_manager import default_db
        print(f'Connection string: {default_db.connection_string.replace("airflow:airflow", "airflow:***")}')

        # Test connection
        result = default_db.fetch_df('SELECT 1 as test')
        print('✓ Database connection successful!')
        return True
    except Exception as e:
        print(f'✗ Database connection failed: {e}')
        return False

def check_tables():
    """Check if required tables exist."""
    print('\n=== Required Tables ===')
    try:
        from db_manager import default_db
        tables = ['unified_games', 'placed_bets', 'bet_recommendations', 'portfolio_value_snapshots']
        all_exist = True

        for table in tables:
            if default_db.table_exists(table):
                count = default_db.fetch_df(f'SELECT COUNT(*) as count FROM {table}').iloc[0]['count']
                print(f'✓ {table}: {count} rows')
            else:
                print(f'✗ {table}: does not exist')
                all_exist = False

        return all_exist
    except Exception as e:
        print(f'✗ Error checking tables: {e}')
        return False

def check_dependencies():
    """Check Python dependencies."""
    print('\n=== Python Dependencies ===')
    deps = ['streamlit', 'pandas', 'psycopg2', 'sqlalchemy', 'plotly']
    all_installed = True

    for dep in deps:
        try:
            __import__(dep)
            print(f'✓ {dep}')
        except ImportError:
            print(f'✗ {dep} - not installed')
            all_installed = False

    return all_installed

def main():
    print('=' * 70)
    print('Dashboard Connection Diagnostic Tool')
    print('=' * 70)

    checks = {
        'PostgreSQL Container': check_postgres_container(),
        'Environment Variables': check_environment_variables(),
        'Database Connection': check_database_connection(),
        'Required Tables': check_tables(),
        'Python Dependencies': check_dependencies(),
    }

    print('\n' + '=' * 70)
    print('Summary')
    print('=' * 70)

    for check, passed in checks.items():
        status = '✓ PASS' if passed else '✗ FAIL'
        print(f'{status}: {check}')

    all_passed = all(checks.values())

    print('\n' + '=' * 70)
    if all_passed:
        print('✓ All checks passed! Dashboard should work.')
        print('\nTo start the dashboard:')
        print('  ./run_dashboard.sh')
        print('  OR')
        print('  streamlit run dashboard_app.py')
    else:
        print('✗ Some checks failed. Please fix the issues above.')
        print('\nCommon solutions:')
        print('  1. Start PostgreSQL: docker compose up -d postgres')
        print('  2. Set env vars: export POSTGRES_HOST=localhost')
        print('  3. Install deps: pip install -r requirements_dashboard.txt')
    print('=' * 70)

    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
