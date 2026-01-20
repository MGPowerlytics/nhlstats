# Email/SMS Notification System

## Overview

The betting system sends SMS notifications via email-to-SMS gateway (Verizon: 7244959219@vtext.com) using Gmail SMTP.

## Notification Types

### 1. Task Failure Notifications ⚠️
- **Trigger**: Any task in the DAG fails
- **Configured in**: DAG `default_args`
- **Method**: Airflow's built-in email system
- **Format**: Standard Airflow failure notification

### 2. Bet Placement Notifications 🎲
- **Trigger**: After `portfolio_optimized_betting` task places bets
- **Location**: Inside `place_portfolio_optimized_bets()` function
- **Format**: Single SMS with summary + top 5 bets
- **Example**:
  ```
  BETS PLACED 2026-01-19
  3 bets, $15.00 total

  1. Lakers $5
  2. Celtics $5
  3. Warriors $5
  ```

### 3. Daily Summary Notifications 📊
- **Trigger**: End of DAG run (after portfolio betting)
- **Task**: `send_daily_summary`
- **Format**: 3-part SMS series
- **Frequency**: Daily at 5 AM ET

#### Message 1: Account Status
```
DAILY SUMMARY 2026-01-19
Balance: $250.50
Portfolio: $275.25
Yesterday P/L: +$12.75
```

#### Message 2: Today's Bets
```
BETS TODAY: 3 placed
Total bet: $15.00

Top bets:
1. Lakers $5
2. Celtics $5
3. Warriors $5
```

#### Message 3: Additional Info
If >3 bets placed:
```
More bets:
4. Heat $5
5. Nets $5

+2 more bets
```

If ≤3 bets placed:
```
AVAILABLE TOMORROW
Cash: $250.50
Total value: $275.25

💰 Win!
```

## Technical Implementation

### Custom SMS Function
```python
def send_sms(to_number: str, subject: str, body: str) -> bool:
    """Send SMS via Verizon email gateway using Gmail SMTP."""
```

**Features:**
- Direct `smtplib` connection (bypasses Airflow email utility)
- Uses environment variables for credentials
- Returns `True`/`False` for success tracking
- Handles exceptions gracefully

### Environment Configuration
Set in `docker-compose.yaml`:
```yaml
AIRFLOW__SMTP__SMTP_HOST: 'smtp.gmail.com'
AIRFLOW__SMTP__SMTP_PORT: '587'
AIRFLOW__SMTP__SMTP_STARTTLS: 'true'
AIRFLOW__SMTP__SMTP_SSL: 'false'
AIRFLOW__SMTP__SMTP_USER: ${GMAIL_USER}
AIRFLOW__SMTP__SMTP_PASSWORD: ${GMAIL_APP_PASSWORD}
```

Set in `.env`:
```bash
GMAIL_USER=matthew.l.glover@gmail.com
GMAIL_APP_PASSWORD=vcvzmzvhdvbzcnkz
```

### Balance Tracking
Daily snapshots saved to enable P/L calculation:
```json
{
  "date": "2026-01-19",
  "balance": 250.50,
  "portfolio_value": 275.25,
  "timestamp": "2026-01-19T10:30:00"
}
```

**Location**: `data/portfolio/balance_YYYY-MM-DD.json`

## SMS Character Limits

- **Standard SMS**: 160 characters
- **Strategy**: Split into 3 messages with 2-second delays
- **Subject lines**: Short identifiers (e.g., "Daily Summary (1/3)")

## Testing

### Test Email Configuration
```bash
docker exec nhlstats-airflow-scheduler-1 python3 -c "
from multi_sport_betting_workflow import send_sms
send_sms('7244959219', 'Test', 'This is a test message')
"
```

### Test Daily Summary
```bash
docker exec $(docker ps -qf "name=scheduler") \
  airflow tasks test multi_sport_betting_workflow send_daily_summary 2026-01-19
```

## Troubleshooting

### Issue: Email Not Sending
1. Check environment variables are set:
   ```bash
   docker exec <scheduler> env | grep SMTP
   ```
2. Verify Gmail app password is valid
3. Check logs: `docker logs <scheduler> | grep -i "sms\|email"`

### Issue: Authentication Errors (530)
- **Cause**: Airflow's email utility has issues with Gmail SMTP
- **Solution**: Use custom `send_sms()` function (already implemented)

### Issue: Messages Out of Order
- **Cause**: Insufficient delay between sends
- **Solution**: Increase `time.sleep()` delays in code

## Future Enhancements

Potential improvements:
- [ ] Add position summary (open bets, potential winnings)
- [ ] Include win/loss record for the week
- [ ] Send alerts for large swings (>$50 P/L)
- [ ] Add market summary (# of opportunities vs bets placed)
- [ ] Include Kelly Criterion sizing info
