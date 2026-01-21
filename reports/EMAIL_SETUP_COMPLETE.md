# EMAIL/SMS NOTIFICATIONS SETUP

## What's Configured

✅ Airflow SMTP → Gmail (smtp.gmail.com:587)
✅ SMS notifications → **724-495-9219** (via 7244959219@vtext.com)
✅ Failure alerts enabled for all tasks
✅ Daily betting summary SMS after bets placed

## Setup Steps

### 1. Create Gmail App Password
- Go to https://myaccount.google.com/ → Security
- Enable 2-Step Verification (required)
- Generate App Password for "Airflow Betting System"
- Save the 16-character password

### 2. Create .env File
```bash
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

### 3. Restart Airflow
```bash
docker-compose down
docker-compose up -d
```

## Example SMS Messages

**Daily Bets (5 AM):**
```
BETS PLACED 2026-01-20
5 bets, $11.70 total

1. Sinner J. $3
2. Dimitrov G. $3
3. Baez S. $2
...
```

**Task Failure:**
```
Airflow alert: Task Failed
DAG: multi_sport_betting_workflow
Task: tennis_load_db
```

## Files Modified
- docker-compose.yaml (Gmail SMTP config)
- dags/multi_sport_betting_workflow.py (SMS notifications)
- .env.example (template created)

## Next: Create .env with your Gmail credentials!
