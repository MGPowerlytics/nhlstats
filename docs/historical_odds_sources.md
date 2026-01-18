# Free Historical NHL Betting Odds Sources

## ✅ Best Free Sources

### 1. **Odds Portal** (RECOMMENDED)
- **URL**: https://www.oddsportal.com/hockey/usa/nhl/results/
- **Coverage**: 2005-present, all NHL games
- **Data**: Opening/closing moneyline, puck line, totals
- **Format**: Web scraping required
- **Pros**: Most comprehensive free source, multiple sportsbooks
- **Cons**: Rate limiting, requires scraping

**Sample URL**: `https://www.oddsportal.com/hockey/usa/nhl-2023-2024/results/`

**Scraping Strategy**:
```python
# Navigate to season page
# Click "Next" through all pages
# Extract: Date, Teams, Final Score, Opening/Closing Odds
# Store: game_date, home_team, away_team, home_ml, away_ml, result
```

---

### 2. **Sports Reference (Hockey-Reference.com)**
- **URL**: https://www.hockey-reference.com/
- **Coverage**: Limited betting data (mostly game results)
- **Data**: Game results, scores, basic stats
- **Format**: HTML tables, easy to scrape
- **Pros**: Clean data, reliable, has game IDs
- **Cons**: No betting lines (but useful for matching games)

---

### 3. **Kaggle Datasets**
- **Search**: https://www.kaggle.com/search?q=nhl+betting+odds
- **Coverage**: Varies by dataset (usually 1-3 seasons)
- **Format**: CSV files (ready to use!)
- **Pros**: Clean, pre-processed, no scraping
- **Cons**: Limited coverage, may not be up-to-date

**Known Datasets**:
- "NHL Game Data" by martinellis (includes some odds)
- "Sports Betting Data" (multi-sport, includes NHL)
- Check regularly - users upload new datasets

---

### 4. **Sportsbook Review / SBR Odds**
- **URL**: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm
- **Coverage**: 2007-present
- **Format**: Excel files (downloadable!)
- **Data**: Opening/closing lines, results, multiple books
- **Pros**: FREE downloads, clean format, no scraping
- **Cons**: May require free account

**This is likely your BEST option - direct downloads!**

---

### 5. **BetExplorer**
- **URL**: https://www.betexplorer.com/hockey/usa/nhl/
- **Coverage**: 2010-present
- **Format**: Web scraping required
- **Pros**: Good mobile/API-friendly structure
- **Cons**: Rate limiting, CAPTCHA protection

---

### 6. **Pinnacle Historical Odds** (Discontinued)
- Pinnacle used to offer free historical odds API
- No longer available publicly
- Some archived datasets may exist on forums/GitHub

---

## 🛠️ Implementation Options

### Option A: Scrape Odds Portal (Most Data)

```python
import requests
from bs4 import BeautifulSoup
import time
import pandas as pd

def scrape_oddsportal_season(season='2023-2024'):
    """
    Scrape NHL odds from Odds Portal for a specific season.
    """
    base_url = f"https://www.oddsportal.com/hockey/usa/nhl-{season}/results/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    all_games = []
    page = 1
    
    while True:
        url = f"{base_url}#/page/{page}/"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            break
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find game rows
        games = soup.find_all('tr', class_='odd') + soup.find_all('tr', class_='even')
        
        if not games:
            break
        
        for game in games:
            # Extract game data (simplified)
            date = game.find('td', class_='table-time').text.strip()
            teams = game.find('td', class_='name').text.strip().split(' - ')
            odds = game.find_all('td', class_='odds-nowrp')
            
            game_data = {
                'date': date,
                'home_team': teams[0],
                'away_team': teams[1],
                'home_ml': odds[0].text if len(odds) > 0 else None,
                'away_ml': odds[1].text if len(odds) > 1 else None
            }
            all_games.append(game_data)
        
        page += 1
        time.sleep(2)  # Be polite, avoid rate limiting
    
    return pd.DataFrame(all_games)
```

---

### Option B: Download from Sportsbook Review (Easiest)

```python
import pandas as pd

# Direct download URLs (check site for current links)
seasons = {
    '2023-24': 'https://www.sportsbookreviewsonline.com/.../nhl-odds-2023-24.xlsx',
    '2022-23': 'https://www.sportsbookreviewsonline.com/.../nhl-odds-2022-23.xlsx',
    # ... etc
}

def download_sbr_odds(season):
    """
    Download pre-compiled odds from Sportsbook Review.
    """
    url = seasons[season]
    df = pd.read_excel(url)
    
    # Clean column names
    df.columns = ['date', 'rot', 'vh', 'team', 'final', 'open', 'close', 'ml']
    
    return df
```

---

### Option C: Use Kaggle Dataset (Quick Start)

```bash
# Install Kaggle CLI
pip install kaggle

# Set up credentials (~/.kaggle/kaggle.json)

# Download dataset
kaggle datasets download -d martinellis/nhl-game-data

# Unzip and use
unzip nhl-game-data.zip -d data/
```

---

## 📊 Data Format to Target

Your goal is to get data like this:

```csv
game_date,home_team,away_team,home_ml_open,away_ml_open,home_ml_close,away_ml_close,home_score,away_score
2024-01-15,TOR,BOS,-150,+130,-145,+125,4,3
2024-01-15,NYR,MTL,-200,+175,-210,+185,5,2
```

---

## 🔧 Integration with Your Database

Once you have historical odds CSV:

```python
import duckdb
import pandas as pd

def load_historical_odds(csv_path, db_path='data/nhlstats.duckdb'):
    """
    Load historical odds into database.
    """
    conn = duckdb.connect(db_path)
    
    # Create table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_betting_lines (
            game_date DATE,
            home_team VARCHAR,
            away_team VARCHAR,
            home_ml_open DECIMAL,
            away_ml_open DECIMAL,
            home_ml_close DECIMAL,
            away_ml_close DECIMAL,
            home_score INTEGER,
            away_score INTEGER,
            source VARCHAR,
            PRIMARY KEY (game_date, home_team, away_team)
        )
    """)
    
    # Load CSV
    df = pd.read_csv(csv_path)
    
    # Insert
    conn.execute("INSERT INTO historical_betting_lines SELECT * FROM df")
    
    print(f"✅ Loaded {len(df)} games with betting lines")
    conn.close()
```

---

## 🎯 Recommended Approach

**For your project, I recommend:**

1. **Start with Sportsbook Review** (if available):
   - Direct downloads, no scraping
   - Clean Excel format
   - Multiple seasons at once

2. **Supplement with Odds Portal**:
   - For recent games (2024-2025 season)
   - Scrape only what you need
   - Respect rate limits

3. **Validate with Kaggle**:
   - Cross-check data quality
   - Fill gaps in coverage

---

## ⚠️ Legal/Ethical Considerations

- **Terms of Service**: Check each site's ToS before scraping
- **Rate Limiting**: Add delays (2-5 seconds) between requests
- **User-Agent**: Use descriptive UA string
- **Attribution**: Credit data sources in your project
- **Commercial Use**: Most sites prohibit commercial use of scraped data

For personal/academic projects (like yours), scraping is generally acceptable with proper rate limiting.

---

## 📈 Expected Coverage

| Source | Seasons | Games | Ease |
|--------|---------|-------|------|
| **SBR** | 2007-2024 | ~20,000 | ⭐⭐⭐⭐⭐ Download |
| **Odds Portal** | 2005-2025 | ~25,000 | ⭐⭐⭐ Scraping |
| **Kaggle** | Varies | ~5,000 | ⭐⭐⭐⭐⭐ Download |

---

## 🚀 Quick Start Script

I'll create a script to fetch from the easiest source...
