#!/usr/bin/env python3
"""
Monitor pool usage in real-time
Shows how many tasks are using the duckdb_writer pool
"""

import subprocess
import time
import sys
from datetime import datetime

def run_command(cmd):
    """Run a command and return output"""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout, result.returncode

def check_pool_slots():
    """Check current pool usage"""
    cmd = "docker compose exec -T airflow-scheduler airflow pools list 2>/dev/null"
    stdout, _ = run_command(cmd)
    
    for line in stdout.split('\n'):
        if 'duckdb_writer' in line:
            # Parse: pool_name | slots | description
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                return parts[1]  # Return slots info like "0/1" or "1/1"
    return "unknown"

def check_running_tasks():
    """Check for running load_into_duckdb tasks"""
    # This checks for any task instances in running state
    cmd = """docker compose exec -T airflow-scheduler airflow tasks states-for-dag-run nhl_daily_download $(date +%Y-%m-%d) 2>/dev/null | grep load_into_duckdb || echo 'no tasks found'"""
    stdout, _ = run_command(cmd)
    return stdout.strip()

def main():
    print("🔍 Pool Usage Monitor")
    print("=" * 70)
    print("Monitoring 'duckdb_writer' pool (Ctrl+C to stop)\n")
    
    try:
        while True:
            timestamp = datetime.now().strftime("%H:%M:%S")
            slots = check_pool_slots()
            tasks = check_running_tasks()
            
            print(f"[{timestamp}] Pool slots: {slots:10s} | Tasks: {tasks[:50]}")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")

if __name__ == "__main__":
    main()
