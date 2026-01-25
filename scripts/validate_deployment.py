#!/usr/bin/env python3
"""
Deployment Validation Script for Multi-Sport Betting System.

Validates that all critical components are functional after deployment.
Run this script after any deployment to ensure system integrity.
"""

import sys
import os
from pathlib import Path
import time
import subprocess
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class DeploymentValidator:
    """Validates deployment of multi-sport betting system."""

    def __init__(self):
        self.results = []
        self.start_time = datetime.now()

    def log_result(self, test_name, passed, message=None):
        """Log test result."""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.results.append(result)

        status = "✅ PASS" if passed else "❌ FAIL"
        output = f"{status}: {test_name}"
        if message:
            output += f" - {message}"
        print(output)

        return passed

    def check_docker_services(self):
        """Check that all Docker services are running."""
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=project_root
            )

            if result.returncode != 0:
                return self.log_result(
                    "docker_services_running",
                    False,
                    f"Docker compose ps failed: {result.stderr}"
                )

            services = json.loads(result.stdout)
            running_services = [s for s in services if "running" in s.get("State", "").lower()]

            if len(running_services) < 5:  # Minimum expected services
                return self.log_result(
                    "docker_services_running",
                    False,
                    f"Only {len(running_services)} services running (expected at least 5)"
                )

            return self.log_result(
                "docker_services_running",
                True,
                f"{len(running_services)} services running"
            )

        except Exception as e:
            return self.log_result(
                "docker_services_running",
                False,
                f"Exception checking Docker services: {e}"
            )

    def check_database_connectivity(self):
        """Test PostgreSQL database connectivity."""
        try:
            from plugins.db_manager import get_engine

            engine = get_engine()
            result = engine.execute("SELECT 1 as test, version() as pg_version").fetchone()

            if result[0] != 1:
                return self.log_result("database_connectivity", False, "Test query failed")

            return self.log_result(
                "database_connectivity",
                True,
                f"PostgreSQL {result[1].split()[1]} connected"
            )

        except Exception as e:
            return self.log_result(
                "database_connectivity",
                False,
                f"Database connection failed: {e}"
            )

    def check_critical_tables(self):
        """Check that critical database tables exist."""
        try:
            from plugins.db_manager import get_engine

            engine = get_engine()

            critical_tables = [
                'unified_games',
                'placed_bets',
                'portfolio_value_snapshots',
                'bet_recommendations'
            ]

            missing_tables = []
            for table in critical_tables:
                result = engine.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
                    (table,)
                ).fetchone()

                if not result[0]:
                    missing_tables.append(table)

            if missing_tables:
                return self.log_result(
                    "critical_tables_exist",
                    False,
                    f"Missing tables: {', '.join(missing_tables)}"
                )

            return self.log_result(
                "critical_tables_exist",
                True,
                f"All {len(critical_tables)} critical tables exist"
            )

        except Exception as e:
            return self.log_result(
                "critical_tables_exist",
                False,
                f"Error checking tables: {e}"
            )

    def check_elo_engines(self):
        """Test that all Elo rating engines can be initialized."""
        try:
            from plugins.elo import (
                NBAEloRating, NHLEloRating, MLBEloRating, NFLEloRating,
                EPLEloRating, Ligue1EloRating, NCAABEloRating,
                WNCAABEloRating, TennisEloRating
            )

            elo_classes = [
                (NBAEloRating, "NBA"),
                (NHLEloRating, "NHL"),
                (MLBEloRating, "MLB"),
                (NFLEloRating, "NFL"),
                (EPLEloRating, "EPL"),
                (Ligue1EloRating, "Ligue1"),
                (NCAABEloRating, "NCAAB"),
                (WNCAABEloRating, "WNCAAB"),
                (TennisEloRating, "Tennis")
            ]

            failed_engines = []
            for elo_class, sport_name in elo_classes:
                try:
                    instance = elo_class()
                    # Quick functionality test
                    if sport_name == "Tennis":
                        prob = instance.predict_team("TestPlayerA", "TestPlayerB")
                    else:
                        prob = instance.predict("TestTeamA", "TestTeamB")

                    if not (0 <= prob <= 1):
                        failed_engines.append(f"{sport_name} (invalid probability)")

                except Exception as e:
                    failed_engines.append(f"{sport_name} ({str(e)})")

            if failed_engines:
                return self.log_result(
                    "elo_engines_initialized",
                    False,
                    f"Failed engines: {', '.join(failed_engines)}"
                )

            return self.log_result(
                "elo_engines_initialized",
                True,
                f"All {len(elo_classes)} Elo engines initialized"
            )

        except Exception as e:
            return self.log_result(
                "elo_engines_initialized",
                False,
                f"Error initializing Elo engines: {e}"
            )

    def check_dag_parsing(self):
        """Test that Airflow DAGs parse successfully."""
        try:
            # Try to import the main DAG
            from dags.multi_sport_betting_workflow import dag, SPORTS_CONFIG

            if dag is None:
                return self.log_result("dag_parsing", False, "Main DAG is None")

            if not hasattr(dag, 'dag_id'):
                return self.log_result("dag_parsing", False, "DAG missing dag_id")

            if dag.dag_id != 'multi_sport_betting_workflow':
                return self.log_result("dag_parsing", False, f"Wrong DAG ID: {dag.dag_id}")

            # Check SPORTS_CONFIG
            if not isinstance(SPORTS_CONFIG, dict):
                return self.log_result("dag_parsing", False, "SPORTS_CONFIG is not a dict")

            expected_sports = 9
            if len(SPORTS_CONFIG) != expected_sports:
                return self.log_result(
                    "dag_parsing",
                    False,
                    f"SPORTS_CONFIG has {len(SPORTS_CONFIG)} sports (expected {expected_sports})"
                )

            return self.log_result(
                "dag_parsing",
                True,
                f"DAG '{dag.dag_id}' parsed successfully with {len(SPORTS_CONFIG)} sports"
            )

        except Exception as e:
            return self.log_result(
                "dag_parsing",
                False,
                f"DAG parsing failed: {e}"
            )

    def check_file_permissions(self):
        """Check critical file permissions."""
        critical_files = [
            project_root / "kalshkey",
            project_root / "docker-compose.yaml",
            project_root / "requirements.txt"
        ]

        missing_files = []
        for file_path in critical_files:
            if not file_path.exists():
                missing_files.append(file_path.name)

        if missing_files:
            return self.log_result(
                "file_permissions",
                False,
                f"Missing critical files: {', '.join(missing_files)}"
            )

        # Check kalshkey permissions (should be 600)
        kalshkey_path = project_root / "kalshkey"
        if kalshkey_path.exists():
            stat = os.stat(kalshkey_path)
            if stat.st_mode & 0o777 != 0o600:
                return self.log_result(
                    "file_permissions",
                    False,
                    f"kalshkey has insecure permissions {oct(stat.st_mode & 0o777)} (should be 600)"
                )

        return self.log_result(
            "file_permissions",
            True,
            "Critical files exist with appropriate permissions"
        )

    def check_service_health(self):
        """Check health of critical services."""
        services_to_check = [
            ("Airflow Scheduler", "http://localhost:8974/health", 30),
            ("Airflow Webserver", "http://localhost:8080/health", 30),
        ]

        import requests

        healthy_services = []
        unhealthy_services = []

        for service_name, url, timeout in services_to_check:
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    healthy_services.append(service_name)
                else:
                    unhealthy_services.append(f"{service_name} (HTTP {response.status_code})")
            except Exception as e:
                unhealthy_services.append(f"{service_name} ({str(e)})")

        if unhealthy_services:
            return self.log_result(
                "service_health",
                False,
                f"Unhealthy services: {', '.join(unhealthy_services)}"
            )

        return self.log_result(
            "service_health",
            True,
            f"All {len(services_to_check)} services healthy"
        )

    def run_all_checks(self):
        """Run all deployment validation checks."""
        print("=" * 70)
        print("DEPLOYMENT VALIDATION - Multi-Sport Betting System")
        print("=" * 70)
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Project root: {project_root}")
        print()

        checks = [
            self.check_docker_services,
            self.check_database_connectivity,
            self.check_critical_tables,
            self.check_elo_engines,
            self.check_dag_parsing,
            self.check_file_permissions,
            self.check_service_health,
        ]

        for check in checks:
            check()
            time.sleep(1)  # Brief pause between checks

        # Summary
        print()
        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)

        print(f"Tests passed: {passed}/{total} ({passed/total*100:.1f}%)")
        print(f"Duration: {(datetime.now() - self.start_time).total_seconds():.1f} seconds")
        print()

        # Failed tests
        failed_tests = [r for r in self.results if not r['passed']]
        if failed_tests:
            print("FAILED TESTS:")
            for test in failed_tests:
                print(f"  • {test['test']}: {test['message']}")
            print()

        # Overall status
        if passed == total:
            print("✅ DEPLOYMENT VALIDATION PASSED")
            return True
        else:
            print(f"❌ DEPLOYMENT VALIDATION FAILED ({total - passed} tests failed)")
            print("
Recommended actions:")
            print("1. Check Docker container logs: docker compose logs")
            print("2. Verify database connection settings")
            print("3. Check file permissions and configurations")
            print("4. Review the failed tests above for specific issues")
            return False

def main():
    """Main entry point."""
    validator = DeploymentValidator()
    success = validator.run_all_checks()

    # Write results to file
    results_file = project_root / "deployment_validation_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'results': validator.results,
            'summary': {
                'passed': sum(1 for r in validator.results if r['passed']),
                'total': len(validator.results)
            }
        }, f, indent=2)

    print(f"
Detailed results saved to: {results_file}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
