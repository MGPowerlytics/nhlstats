# Programmatic Sports Betting APIs: Legal Options & Considerations

## Executive Summary

**Critical Finding**: Most legal sports betting markets (especially US) **DO NOT** allow retail customers to place bets programmatically via API. However, several legitimate options exist for automated betting in specific jurisdictions.

---

## ⚠️ Legal & Compliance Warnings

### United States
- **NO retail API betting allowed** by DraftKings, FanDuel, BetMGM, Caesars
- Attempting to automate betting via scraping/bots **VIOLATES TERMS OF SERVICE**
- May result in: Account closure, fund forfeiture, potential legal action
- Only B2B partners with proper licensing can access betting APIs

### General Restrictions
- Most sportsbooks prohibit automated betting to prevent:
  - Market manipulation
  - Bot arbitrage
  - Fraud and money laundering
  - Responsible gambling violations
- KYC/AML requirements apply in all regulated markets

---

## 🟢 Legal Programmatic Betting Options

### 1. Betfair Exchange API ⭐ (BEST OPTION)

**Status**: ✅ Officially supports automated betting via API

#### Where It's Legal
| Region | Legal Status | Notes |
|--------|-------------|-------|
| UK, Ireland | ✅ Fully legal | Primary markets |
| Germany, Spain, Italy | ✅ Legal | Licensed operators |
| Sweden, Denmark | ✅ Legal | Regulated markets |
| Australia, New Zealand | ✅ Legal | Some restrictions |
| USA (New Jersey only) | ✅ Legal | Via FanDuel partnership |
| India | ⚠️ Mixed | State-level restrictions |
| Singapore, Hong Kong | ⚠️ Limited | Regulatory constraints |
| France | ❌ Restricted | Exchange betting limited |
| Middle East (UAE, Qatar, Saudi) | ❌ Banned | Gambling prohibited |
| Norway, Turkey | ❌ Banned | State monopolies |

#### API Features
```python
# Official Betfair API capabilities
- Place bets (back/lay)
- Cancel/update orders
- Market data streaming
- Historical data access
- Account balance management
- Real-time odds
```

#### Resources
- **Documentation**: https://developer.betfair.com/exchange-api/
- **Developer Program**: https://developer.betfair.com/
- **GitHub Examples**: https://github.com/betfair-datascientists/API

#### Advantages
✅ Official API support  
✅ Well-documented  
✅ Active developer community  
✅ Exchange model (bet against other users, not house)  
✅ No restrictions on bot trading  
✅ Historical data available  

#### Disadvantages
❌ Limited US availability (NJ only)  
❌ Exchange markets less liquid than traditional sportsbooks  
❌ Requires technical knowledge  
❌ Subject to commission charges  

---

### 2. Decentralized Crypto Betting Platforms

**Status**: ✅ Supports automated betting via smart contracts

#### How It Works
- **Blockchain-based**: Ethereum, Solana, Polygon
- **Smart contracts**: Automatic settlement
- **No KYC**: Anonymous betting via crypto wallets
- **Global access**: Available worldwide (subject to local laws)

#### Top Platforms

##### Sportbet.one
- First decentralized sportsbook
- BTC, ETH, USDT accepted
- Live betting available
- Smart contract automation
- URL: https://sportbet.one/

##### BetDex
- Peer-to-peer betting exchange
- Multiple crypto tokens
- Order book model
- Low fees (no house edge)

##### BC.Game / Thunderpick
- Wide sports coverage
- Instant settlements
- Provably fair
- Popular for eSports

#### API Integration
```javascript
// Web3.js example for Ethereum-based betting
const Web3 = require('web3');
const web3 = new Web3('https://mainnet.infura.io/v3/YOUR_KEY');

// Contract interaction
const contract = new web3.eth.Contract(ABI, CONTRACT_ADDRESS);

// Place bet via smart contract
await contract.methods.placeBet(
    gameId, 
    betAmount, 
    outcomeId
).send({ from: userAddress, value: betAmount });
```

#### Crypto Payment APIs
- **NOWPayments**: https://nowpayments.io/api/betting
- Supports Bitcoin, Ethereum, 100+ cryptocurrencies
- Automated deposits/withdrawals
- Mass payout functionality
- 99.99% uptime SLA

#### Advantages
✅ True automation via smart contracts  
✅ Anonymous (no KYC)  
✅ Instant payouts  
✅ Transparent (on-chain verification)  
✅ Global access  
✅ Lower fees (no intermediary)  
✅ Censorship-resistant  

#### Disadvantages
❌ Regulatory uncertainty in many jurisdictions  
❌ Requires crypto wallet knowledge  
❌ Smaller betting pools  
❌ Limited sports coverage vs traditional books  
❌ Smart contract risk  
❌ Cryptocurrency volatility  

---

### 3. Hong Kong Jockey Club (HKJC)

**Status**: ❌ NO public API available

#### Current Situation
- Only official HKJC apps/website for betting
- No developer API access
- All betting must be through approved channels
- Applies to: Horse racing, football, Mark Six lottery

#### Why No API?
- Heavy regulatory control
- Security and compliance requirements
- State-operated monopoly
- Fraud prevention

#### Alternative Approach
For those building Benter-style models:
1. Develop prediction models using scraped data
2. Use models to identify value bets
3. **Manually place bets** via HKJC app/website
4. Log results for model refinement

**Note**: Your data pipeline is perfect for model development, but bet placement remains manual.

---

## 📊 API Options for Data Only (No Bet Placement)

These services provide odds data but **do not** allow automated bet placement:

### SportsDataIO
- **URL**: https://sportsdata.io/live-odds-api
- Aggregates odds from all major US sportsbooks
- Real-time updates
- Historical data
- Pricing: $50-500/month

### The Odds API
- **URL**: https://the-odds-api.com/
- Live odds from 70+ sportsbooks
- Simple REST API
- Free tier available
- Pricing: $0-500/month

### Sportmonks
- Sports data and odds
- 50+ bookmakers
- No bet placement
- Good for analytics

### Use Cases for Data-Only APIs
- Odds comparison sites
- Value bet alerts
- Arbitrage detection
- Analytics dashboards
- Model training data
- Research and backtesting

---

## 🚫 What Does NOT Work

### US Sportsbooks (Illegal/Prohibited)
❌ DraftKings - No public API, TOS violations  
❌ FanDuel - No public API, TOS violations  
❌ BetMGM - No public API, TOS violations  
❌ Caesars - No public API, TOS violations  
❌ BetRivers - No public API, TOS violations  

### Attempts to Circumvent
❌ Reverse engineering mobile apps - TOS violation  
❌ Web scraping for automation - Detectable, bannable  
❌ Third-party "unofficial" APIs - Unreliable, illegal  
❌ VPN to access restricted markets - Fraud, illegal  

### Consequences
- Account closure
- Fund confiscation
- Blacklisting across networks
- Potential criminal charges (fraud)
- Civil lawsuits

---

## ✅ Recommended Approaches by Use Case

### 1. Sports Analytics / Research
**Solution**: Use data-only APIs
- SportsDataIO, Odds API, Sportmonks
- Build models and alerts
- Manual betting execution

### 2. European/UK Markets
**Solution**: Betfair Exchange API
- Full programmatic betting
- Official support
- Active community

### 3. Crypto-Friendly / Anonymous
**Solution**: Decentralized platforms
- Sportbet.one, BetDex
- Smart contract automation
- No geographic restrictions

### 4. Hong Kong Racing (Benter Model)
**Solution**: Hybrid approach
- Your data pipeline for predictions
- Manual bet placement via HKJC
- Kelly Criterion position sizing
- Log all bets for refinement

### 5. Fantasy Sports (US)
**Solution**: Third-party optimization
- pydfs-lineup-optimizer (GitHub)
- DraftKings/FanDuel analytics
- Lineup generation only

---

## 🔧 Implementation Examples

### Betfair API Example (Python)
```python
import betfairlightweight
from betfairlightweight import filters

# Initialize
trading = betfairlightweight.APIClient(
    username='your_username',
    password='your_password',
    app_key='your_app_key'
)

# Login
trading.login()

# Get markets
event_type_id = '1'  # Soccer
market_filter = filters.market_filter(
    event_type_ids=[event_type_id],
    market_countries=['GB']
)

markets = trading.betting.list_market_catalogue(
    filter=market_filter,
    max_results=10
)

# Place bet
instruction = filters.place_instruction(
    order_type='LIMIT',
    selection_id=12345,
    side='BACK',
    limit_order=filters.limit_order(size=10, price=2.5)
)

# Execute
trading.betting.place_orders(
    market_id='1.123456',
    instructions=[instruction]
)
```

### Decentralized Betting (Web3)
```python
from web3 import Web3
import json

# Connect to Ethereum
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR_KEY'))

# Load contract
with open('betting_contract_abi.json') as f:
    abi = json.load(f)

contract = w3.eth.contract(
    address='0xCONTRACT_ADDRESS',
    abi=abi
)

# Place bet
tx = contract.functions.placeBet(
    event_id=12345,
    outcome=1,  # Team A wins
    amount=w3.toWei(0.1, 'ether')
).buildTransaction({
    'from': account_address,
    'nonce': w3.eth.getTransactionCount(account_address),
    'gas': 200000,
    'gasPrice': w3.toWei('50', 'gwei')
})

# Sign and send
signed_tx = w3.eth.account.signTransaction(tx, private_key)
tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
```

---

## 📋 Decision Matrix

| Priority | US Legal | Europe | Asia | Anonymous | Cost | Recommendation |
|----------|----------|--------|------|-----------|------|----------------|
| US Sports | ✅ | ❌ | ❌ | ❌ | $ | Data APIs + Manual |
| UK/EU Sports | ❌ | ✅ | ❌ | ❌ | Free | **Betfair Exchange** |
| HK Racing | ❌ | ❌ | ⚠️ | ❌ | Free | Data + Manual HKJC |
| Crypto Friendly | ⚠️ | ⚠️ | ⚠️ | ✅ | $$ | **Decentralized** |
| Research Only | ✅ | ✅ | ✅ | ✅ | $-$$$ | Data APIs |

---

## 🎯 Recommendations for Your Project

Based on your multi-sport data pipeline and Benter model interest:

### Phase 1: Model Development (Now)
1. ✅ Continue building data collection (you're doing this)
2. ✅ Design and implement prediction models
3. ✅ Backtest on historical data
4. ✅ Calculate Kelly Criterion position sizes

### Phase 2: Paper Trading (Next)
1. Log predicted bets in database
2. Track theoretical performance
3. Refine models based on results
4. No real money at risk

### Phase 3: Live Betting (Future)
**For Hong Kong Racing:**
- Manually place bets via HKJC app
- Use your model for predictions
- Log all actual bets
- Verify edge exists before scaling

**For Other Sports (if desired):**
- **US/Canada**: Data APIs for models, manual betting
- **Europe/UK**: Consider Betfair Exchange API
- **Crypto**: Explore decentralized platforms

---

## ⚖️ Legal Disclaimer

This document is for informational purposes only. Before engaging in any sports betting activities:

1. **Verify local laws** - Gambling laws vary by jurisdiction
2. **Consult legal counsel** - Especially for automated systems
3. **Read Terms of Service** - Understand platform rules
4. **Ensure compliance** - KYC/AML requirements
5. **Bet responsibly** - Only risk what you can afford to lose

Programmatic betting may be:
- Illegal in your jurisdiction
- Against sportsbook terms of service
- Subject to taxation
- Regulated as professional gambling

**The authors accept no liability for legal issues arising from use of this information.**

---

## 📚 Additional Resources

### Betfair
- Developer Docs: https://developer.betfair.com/
- Exchange API: https://developer.betfair.com/exchange-api/
- Python Client: https://github.com/liampauling/betfair

### Decentralized
- Sportbet.one: https://sportbet.one/
- Web3.py: https://web3py.readthedocs.io/
- Ethereum Smart Contracts: https://ethereum.org/en/developers/

### Data APIs
- SportsDataIO: https://sportsdata.io/
- The Odds API: https://the-odds-api.com/
- Sportmonks: https://www.sportmonks.com/

### Books
- "Fortune's Formula" by William Poundstone
- "Trading on Sports Betting Markets" by Hyeongmin Kim
- "The Logic of Sports Betting" by Ed Miller & Matthew Davidow

---

**Last Updated**: 2026-01-16  
**Status**: Active research document  
**Next Review**: Quarterly (regulations change frequently)
