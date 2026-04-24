import pytest
from plugins.ev_accuracy_report import print_ev_report


def test_print_ev_report_no_crash():
    """Ensure print_ev_report doesn't crash with various result formats."""
    # 1. No data case
    results_no_data = {"status": "no_data", "message": "No settled bets found"}
    print_ev_report(results_no_data)

    # 2. Basic success case
    results_success = {
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "total_bets": 10,
        "total_staked": 100.0,
        "total_profit": 10.0,
        "overall_roi": 0.1,
        "avg_predicted_ev": 0.05,
        "calibration": {"mean_abs_error": 0.02, "is_overconfident": False},
        "by_sport": {
            "NBA": {
                "num_bets": 5,
                "total_staked": 50.0,
                "total_profit": 5.0,
                "actual_roi": 0.1,
                "avg_predicted_ev": 0.05,
                "calibration_error": -0.05,
            }
        },
        "by_confidence": {
            "HIGH": {
                "num_bets": 5,
                "total_staked": 50.0,
                "total_profit": 5.0,
                "actual_roi": 0.1,
                "avg_predicted_ev": 0.05,
                "calibration_error": -0.05,
            }
        },
        "by_sport_confidence": {
            "NBA": {
                "HIGH": {
                    "num_bets": 5,
                    "total_staked": 50.0,
                    "total_profit": 5.0,
                    "actual_roi": 0.1,
                }
            }
        },
        "ev_buckets": [
            {
                "range": "0-5%",
                "num_bets": 10,
                "total_staked": 100.0,
                "actual_roi": 0.1,
                "predicted_ev": 0.05,
                "calibration_error": -0.05,
            }
        ],
        "weekly_trend": [
            {"week": "2026-W01", "num_bets": 10, "staked": 100.0, "roi": 0.1}
        ],
    }
    print_ev_report(results_success)


if __name__ == "__main__":
    test_print_ev_report_no_crash()
