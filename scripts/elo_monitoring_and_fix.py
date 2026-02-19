#!/usr/bin/env python3
"""
Elo Monitoring and Fix Script.
Run this daily to ensure Elo ratings are correct and log changes.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import default_db


class EloMonitor:
    """Monitor and fix Elo ratings for all sports."""

    def __init__(self, send_alerts=False):
        self.send_alerts = send_alerts
        self.results = {}
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def check_sport_elo(self, sport: str):
        """Check Elo ratings for a specific sport."""
        print(f"\n🔍 Checking {sport.upper()} Elo ratings...")

        result = {
            'sport': sport,
            'timestamp': self.timestamp,
            'status': 'unknown',
            'issues': [],
            'changes': [],
            'stats': {}
        }

        # 1. Check if Elo file exists
        csv_path = f"data/{sport}_current_elo_ratings.csv"
        if not os.path.exists(csv_path):
            result['issues'].append(f"Elo file not found: {csv_path}")
            result['status'] = 'error'
            print(f"  ❌ Elo file not found: {csv_path}")
            self.results[sport] = result
            return result

        # 2. Load current ratings
        try:
            df = pd.read_csv(csv_path)
            current_ratings = dict(zip(df['team'], df['rating']))
            result['stats']['current_teams'] = len(current_ratings)
            print(f"  Loaded {len(current_ratings)} current ratings")
        except Exception as e:
            result['issues'].append(f"Failed to load Elo file: {e}")
            result['status'] = 'error'
            print(f"  ❌ Failed to load Elo file: {e}")
            self.results[sport] = result
            return result

        # 3. Check data quality
        issues = self._check_elo_quality(sport, current_ratings)
        result['issues'].extend(issues)

        if issues:
            result['status'] = 'warning'
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            result['status'] = 'ok'
            print(f"  ✅ Elo ratings look good")

        # 4. Check for recent changes (compare with yesterday)
        yesterday_file = self._get_yesterday_elo_file(sport)
        if yesterday_file and os.path.exists(yesterday_file):
            try:
                yesterday_df = pd.read_csv(yesterday_file)
                yesterday_ratings = dict(zip(yesterday_df['team'], yesterday_df['rating']))

                changes = self._compare_ratings(current_ratings, yesterday_ratings)
                result['changes'] = changes
                result['stats']['yesterday_teams'] = len(yesterday_ratings)

                if changes:
                    print(f"  📈 Found {len(changes)} rating changes since yesterday")
                    # Log top changes
                    for change in changes[:3]:
                        print(f"    {change['team']}: {change['old']:.1f} → {change['new']:.1f} ({change['change']:+.1f})")
            except Exception as e:
                result['issues'].append(f"Failed to compare with yesterday: {e}")
                print(f"  ⚠️  Could not compare with yesterday: {e}")

        # 5. Check probability variance (for team sports)
        if sport in ['nhl', 'nba', 'mlb', 'nfl', 'ncaab']:
            variance_issue = self._check_probability_variance(sport, current_ratings)
            if variance_issue:
                result['issues'].append(variance_issue)
                result['status'] = 'warning'
                print(f"  ⚠️  {variance_issue}")

        self.results[sport] = result
        return result

    def _check_elo_quality(self, sport: str, ratings: dict) -> list:
        """Check Elo rating quality."""
        issues = []

        if not ratings:
            issues.append("No ratings found")
            return issues

        # Check rating range
        ratings_list = list(ratings.values())
        min_rating = min(ratings_list)
        max_rating = max(ratings_list)
        rating_range = max_rating - min_rating

        # Expected ranges by sport
        expected_ranges = {
            'nhl': 200,  # NHL should have ~200 point range
            'nba': 300,  # NBA should have ~300 point range
            'mlb': 250,  # MLB should have ~250 point range
            'nfl': 200,  # NFL should have ~200 point range
            'ncaab': 400,  # NCAAB should have large range
        }

        if sport in expected_ranges:
            expected = expected_ranges[sport]
            if rating_range < expected * 0.5:  # Less than 50% of expected
                issues.append(f"Rating range too narrow: {rating_range:.1f} (expected ~{expected})")

        # Check for teams clustered around 1500
        near_1500 = sum(1 for r in ratings_list if 1490 < r < 1510)
        pct_near_1500 = near_1500 / len(ratings_list) * 100

        if pct_near_1500 > 50:  # More than 50% near 1500
            issues.append(f"Too many teams clustered near 1500: {pct_near_1500:.1f}%")

        return issues

    def _check_probability_variance(self, sport: str, ratings: dict) -> str:
        """Check if Elo probabilities have reasonable variance."""
        if len(ratings) < 2:
            return "Not enough teams to check variance"

        # Sample some matchups
        teams = list(ratings.keys())
        sample_size = min(20, len(teams))
        probabilities = []

        for i in range(sample_size):
            for j in range(i+1, sample_size):
                home = teams[i]
                away = teams[j]

                # Simple Elo probability calculation
                home_rating = ratings[home] + 50  # Home advantage
                away_rating = ratings[away]
                diff = away_rating - home_rating
                prob = 1 / (1 + 10 ** (diff / 400))
                probabilities.append(prob)

        if not probabilities:
            return "Could not calculate probabilities"

        prob_range = max(probabilities) - min(probabilities)

        # Expected probability ranges
        expected_ranges = {
            'nhl': 0.3,  # 30% range expected
            'nba': 0.4,  # 40% range expected
            'mlb': 0.35, # 35% range expected
            'nfl': 0.3,  # 30% range expected
            'ncaab': 0.5, # 50% range expected
        }

        if sport in expected_ranges:
            expected = expected_ranges[sport]
            if prob_range < expected * 0.3:  # Less than 30% of expected
                return f"Probability range too narrow: {prob_range:.2f} (expected ~{expected})"

        return ""

    def _get_yesterday_elo_file(self, sport: str) -> str:
        """Get path to yesterday's Elo file if it exists."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        # Check for backup files
        backup_dir = "data/elo_backups"
        if os.path.exists(backup_dir):
            pattern = f"{sport}_current_elo_ratings_{yesterday}*.csv"
            import glob
            files = glob.glob(os.path.join(backup_dir, pattern))
            if files:
                return sorted(files)[-1]  # Get most recent

        return None

    def _compare_ratings(self, current: dict, previous: dict) -> list:
        """Compare current and previous ratings."""
        changes = []
        all_teams = set(list(current.keys()) + list(previous.keys()))

        for team in all_teams:
            old = previous.get(team, 1500)
            new = current.get(team, 1500)
            change = new - old

            if abs(change) > 0.1:  # Only log meaningful changes
                changes.append({
                    'team': team,
                    'old': float(old),
                    'new': float(new),
                    'change': float(change),
                    'in_current': team in current,
                    'in_previous': team in previous
                })

        # Sort by absolute change
        changes.sort(key=lambda x: abs(x['change']), reverse=True)
        return changes

    def backup_current_elo(self, sport: str):
        """Backup current Elo file."""
        csv_path = f"data/{sport}_current_elo_ratings.csv"
        if not os.path.exists(csv_path):
            return False

        backup_dir = "data/elo_backups"
        os.makedirs(backup_dir, exist_ok=True)

        backup_path = os.path.join(backup_dir, f"{sport}_current_elo_ratings_{self.timestamp}.csv")

        try:
            import shutil
            shutil.copy2(csv_path, backup_path)
            print(f"  💾 Backed up to {backup_path}")
            return True
        except Exception as e:
            print(f"  ❌ Failed to backup: {e}")
            return False

    def generate_report(self):
        """Generate monitoring report."""
        report = {
            'timestamp': self.timestamp,
            'sports_checked': list(self.results.keys()),
            'results': self.results,
            'summary': self._generate_summary()
        }

        # Save report
        report_dir = "data/elo_reports"
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"elo_monitoring_report_{self.timestamp}.json")

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📊 Report saved to {report_path}")

        # Print summary
        print("\n" + "=" * 80)
        print("ELO MONITORING SUMMARY")
        print("=" * 80)

        for sport, result in self.results.items():
            status_icon = "✅" if result['status'] == 'ok' else "⚠️" if result['status'] == 'warning' else "❌"
            print(f"{status_icon} {sport.upper():6s}: {result['status']:7s} - {len(result.get('issues', []))} issues")

        print("\n" + "=" * 80)

        return report_path

    def _generate_summary(self):
        """Generate summary statistics."""
        total_sports = len(self.results)
        ok_sports = sum(1 for r in self.results.values() if r['status'] == 'ok')
        warning_sports = sum(1 for r in self.results.values() if r['status'] == 'warning')
        error_sports = sum(1 for r in self.results.values() if r['status'] == 'error')

        total_issues = sum(len(r.get('issues', [])) for r in self.results.values())
        total_changes = sum(len(r.get('changes', [])) for r in self.results.values())

        return {
            'total_sports': total_sports,
            'ok_sports': ok_sports,
            'warning_sports': warning_sports,
            'error_sports': error_sports,
            'total_issues': total_issues,
            'total_changes': total_changes
        }

    def send_alert_if_needed(self):
        """Send alert email if issues found."""
        if not self.send_alerts:
            return

        issues_found = False
        alert_body = "Elo Monitoring Alert\\n\\n"

        for sport, result in self.results.items():
            if result['status'] in ['warning', 'error'] and result.get('issues'):
                issues_found = True
                alert_body += f"{sport.upper()} ({result['status']}):\\n"
                for issue in result['issues']:
                    alert_body += f"  • {issue}\\n"
                alert_body += "\\n"

        if issues_found:
            # Send email alert
            self._send_email_alert(alert_body)

    def _send_email_alert(self, body: str):
        """Send email alert."""
        # This is a placeholder - implement based on your email setup
        print(f"📧 Would send alert email:\\n{body}")
        # Implement email sending logic here


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    print("=" * 80)
    print("ELO RATING MONITORING AND FIX")
    print("=" * 80)

    try:
        # Initialize monitor
        monitor = EloMonitor(send_alerts=False)

        # Check all sports
        sports = ['nhl', 'nba', 'mlb', 'nfl', 'ncaab', 'wncaab', 'tennis']

        for sport in sports:
            # Backup current file
            monitor.backup_current_elo(sport)

            # Check Elo ratings
            monitor.check_sport_elo(sport)

        # Generate report
        report_path = monitor.generate_report()

        # Send alerts if needed
        monitor.send_alert_if_needed()

        print(f"\n✅ Monitoring complete. Report: {report_path}")

        # Check if NHL needs fixing (our main issue)
        nhl_result = monitor.results.get('nhl', {})
        if nhl_result.get('status') in ['warning', 'error']:
            print("\n⚠️  NHL Elo ratings need attention!")
            print("   Run: python scripts/fix_elo_for_all_sports.py")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
