#!/bin/bash

# Multi-Platform Arbitrage System Setup
echo "========================================================================"
echo "MULTI-PLATFORM ARBITRAGE SYSTEM SETUP"
echo "========================================================================"
echo ""

# Check for The Odds API key
if [ -z "$ODDS_API_KEY" ]; then
    echo "❌ ODDS_API_KEY not set"
    echo ""
    echo "To get started:"
    echo "1. Sign up for free API key at: https://the-odds-api.com/"
    echo "   (Free tier: 500 requests/month)"
    echo ""
    echo "2. Set environment variable:"
    echo "   export ODDS_API_KEY='your-api-key-here'"
    echo ""
    echo "3. Add to shell profile for persistence:"
    echo "   echo 'export ODDS_API_KEY=\"your-key\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
    echo ""
    exit 1
else
    echo "✅ ODDS_API_KEY found"
fi

echo ""
echo "Testing The Odds API connection..."
python3 plugins/the_odds_api.py

echo ""
echo "========================================================================"
echo "SETUP COMPLETE!"
echo "========================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Find arbitrage opportunities:"
echo "   python3 find_arbitrage.py"
echo ""
echo "2. View documentation:"
echo "   cat docs/ARBITRAGE_GUIDE.md"
echo ""
echo "3. Integration options:"
echo "   - The Odds API: 40+ sportsbooks (ACTIVE)"
echo "   - Kalshi: Prediction markets (ACTIVE)"
echo "   - Cloudbet: Crypto sportsbook (needs API key)"
echo "   - Polymarket: DeFi markets (read-only)"
echo ""
echo "========================================================================"
