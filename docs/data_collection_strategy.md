# HK Racing Data Collection Strategy

## Current Status

### HKJC Website Scraping
- **Challenge**: Modern HKJC website uses complex JavaScript/AJAX rendering
- **Coverage**: Current season + recent past (~2-3 years)
- **Status**: Scraper needs refinement to parse new HTML structure
- **Solution**: Update parser or use existing open-source scrapers as reference

### Historical Data Options

## Option 1: Start Collecting Now (Recommended)

**Strategy**: Begin daily collection, accumulate going forward

**Pros:**
- Free
- Builds proprietary dataset
- Captures real-time odds (valuable for Benter-style model)
- Own the data pipeline

**Cons:**
- Takes time to build history (need 2-5 years for meaningful models)
- Must maintain scraper as website changes

**Timeline:**
- Start now: January 2026
- 1 year: ~200 race days, ~1,600 races
- 2 years: ~400 race days, ~3,200 races  
- 3 years: ~600 race days, ~4,800 races ✓ (Minimum for Benter-style model)

## Option 2: Use Existing GitHub Datasets

**Sources:**
1. **eprochasson/horserace_data** (GitHub)
   - Coverage: 1979-2018 (39 years!)
   - Format: CSV files
   - Data: Results, horses, jockeys, trainers, dividends
   - URL: https://github.com/eprochasson/horserace_data

2. **j-csc/HK-Horse-Racing-Data-Scraper** (GitHub)
   - Working scraper to extract from HKJC
   - Can use as reference to fix our scraper
   - URL: https://github.com/j-csc/HK-Horse-Racing-Data-Scraper

**Pros:**
- Immediate access to 40+ years of data
- Can start modeling NOW
- Already structured and cleaned

**Cons:**
- Data ends in 2018 (8 years old)
- No recent data for current horses/jockeys
- Gap between 2018-2026

**Best Use:**
- Download historical data (1979-2018)
- Use for initial model development and backtesting
- Supplement with daily scraping (2026 onward)

## Option 3: Premium Data Services (Paid)

### Renavon
- **Coverage**: 1977-present
- **Format**: CSV, Excel, API access
- **Features**: Real-time odds, comprehensive fields
- **Cost**: Premium subscription
- **URL**: https://renavon.com

### HorseRaceDatabase
- **Coverage**: 1979-present
- **Format**: CSV, SQL, JSON, API (coming soon)
- **Features**: Sectional times from 2008+
- **Cost**: Subscription based
- **URL**: https://horseracedatabase.com

### Horsorion
- **Coverage**: 1980s-present
- **Format**: Structured datasets, custom options
- **Cost**: Professional/Standard/Custom plans
- **URL**: https://www.horsorion.com/data_plan/en/

**Pros:**
- Complete historical + current data
- Professional support and documentation
- Regular updates
- Clean, normalized data

**Cons:**
- Ongoing subscription cost
- Dependent on third party
- Less control over pipeline

## Recommended Approach

### Phase 1: Quick Start (This Week)
```bash
# Download GitHub historical dataset
git clone https://github.com/eprochasson/horserace_data
# Import 1979-2018 data into DuckDB
# Start initial exploratory analysis
```

### Phase 2: Fix Scraper (This Month)
```bash
# Reference working scrapers on GitHub
# Update our scraper for current HKJC website structure
# Begin daily collection (fills 2018-2026 gap over time)
```

### Phase 3: Model Development (Month 2-3)
```python
# Use historical data (1979-2018) for:
- Feature engineering (speed figures, form ratings)
- Basic logistic regression model
- Backtesting framework
- Validate Benter's approach

# Use daily scraping for:
- Current horses/jockeys/trainers
- Testing model on live data
- Refining predictions
```

### Phase 4: Production (Month 4+)
```python
# Full pipeline operational:
- Daily data collection at 7am
- ETL to DuckDB
- Model retraining weekly
- Live predictions
- (Optional) Automated betting if successful
```

## Implementation Steps

### Immediate (Today):
1. Download existing GitHub dataset
2. Import sample data to DuckDB
3. Run exploratory analysis

### This Week:
1. Study working scraper examples
2. Update our scraper with correct HTML parsing
3. Test with recent races
4. Set up automated daily collection

### Next Month:
1. Build feature engineering pipeline
2. Implement basic Benter model
3. Backtest on 1979-2018 data
4. Establish baseline accuracy

## Data Requirements for Benter Model

**Minimum**: 3-5 years of dense race data
**Optimal**: 10+ years

**Current Options**:
- **GitHub dataset**: 39 years (1979-2018) ✓✓✓
- **Daily scraping**: Builds over time
- **Combined**: Historical + current = Best

## Cost-Benefit Analysis

| Option | Cost | Time to Model | Data Quality | Control |
|--------|------|---------------|--------------|---------|
| GitHub + Scraping | $0 | 1-2 weeks | Good | Full |
| Premium Service | $50-200/mo | Immediate | Excellent | Limited |
| Scraping Only | $0 | 3-5 years | Good | Full |

**Recommendation**: GitHub historical + daily scraping = $0, best control, can start modeling in 2 weeks

## Next Steps

Would you like me to:
1. Download and import the GitHub historical dataset?
2. Fix the scraper to work with current HKJC website?
3. Set up the DuckDB schema and start loading data?
4. All of the above?

The fastest path to building a Benter-style model is **Option 1** (download historical data) + **Option 2** (fix scraper for daily updates).
