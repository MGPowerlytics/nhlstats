# Building Ethereum Smart Contract Sports Betting Systems

## Overview

This guide covers building decentralized sports betting applications using Ethereum smart contracts, oracles for real-world data, and Layer 2 scaling solutions to minimize gas fees.

---

## 🏗️ Architecture Components

### 1. Smart Contract Layer (Solidity)
- **Betting logic**: Place bets, manage pools, calculate payouts
- **Escrow**: Hold funds in contract until settlement
- **Access control**: Owner/admin privileges
- **Event emission**: For frontend updates

### 2. Oracle Layer (Chainlink)
- **Real-world data**: Fetch NBA/NFL/NHL scores
- **Decentralized validation**: Multiple data sources
- **Automated settlement**: Trigger payouts based on results

### 3. Layer 2 Scaling (Polygon/Arbitrum)
- **Reduced gas fees**: $0.001-$3 vs $4-$10+ on mainnet
- **Faster transactions**: 2-10 seconds vs 30s-2min
- **Same security**: Backed by Ethereum

### 4. Frontend (Web3.js/Ethers.js)
- **Wallet connection**: MetaMask integration
- **Contract interaction**: Read/write blockchain data
- **User interface**: React/Next.js

---

## 📝 Smart Contract Code Examples

### Basic Sports Betting Contract

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SportsBetting
 * @dev Simple two-team betting contract with owner-controlled settlement
 */
contract SportsBetting {
    struct Bet {
        address bettor;
        uint256 amount;
        uint8 selectedTeam;
        bool claimed;
    }

    address public owner;
    bool public isBettingOpen = true;
    bool public isSettled = false;
    uint8 public winningTeam;
    
    mapping(uint8 => uint256) public totalBetsPerTeam;
    mapping(uint8 => Bet[]) public betsByTeam;
    mapping(address => uint256[]) public userBets; // Track user's bet indices
    
    uint256 public constant MIN_BET = 0.01 ether;
    uint256 public constant MAX_BET = 10 ether;
    uint256 public constant HOUSE_FEE_PERCENT = 2; // 2% house fee

    event BetPlaced(address indexed bettor, uint8 team, uint256 amount);
    event BettingClosed(uint256 timestamp);
    event WinnerDeclared(uint8 winningTeam, uint256 totalPool);
    event PayoutClaimed(address indexed winner, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not contract owner");
        _;
    }

    modifier bettingOpen() {
        require(isBettingOpen, "Betting closed");
        require(!isSettled, "Already settled");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Place a bet on team 1 or team 2
     * @param team Team number (1 or 2)
     */
    function placeBet(uint8 team) external payable bettingOpen {
        require(msg.value >= MIN_BET, "Bet too small");
        require(msg.value <= MAX_BET, "Bet too large");
        require(team == 1 || team == 2, "Invalid team");
        
        // Store bet
        betsByTeam[team].push(Bet({
            bettor: msg.sender,
            amount: msg.value,
            selectedTeam: team,
            claimed: false
        }));
        
        totalBetsPerTeam[team] += msg.value;
        userBets[msg.sender].push(betsByTeam[team].length - 1);
        
        emit BetPlaced(msg.sender, team, msg.value);
    }

    /**
     * @dev Close betting window (before game starts)
     */
    function closeBetting() external onlyOwner {
        require(isBettingOpen, "Already closed");
        isBettingOpen = false;
        emit BettingClosed(block.timestamp);
    }

    /**
     * @dev Declare winner and enable payouts
     * @param team Winning team (1 or 2)
     */
    function declareWinner(uint8 team) external onlyOwner {
        require(!isBettingOpen, "Betting still open");
        require(!isSettled, "Already settled");
        require(team == 1 || team == 2, "Invalid team");
        
        winningTeam = team;
        isSettled = true;
        
        uint256 totalPool = totalBetsPerTeam[1] + totalBetsPerTeam[2];
        emit WinnerDeclared(team, totalPool);
    }

    /**
     * @dev Claim payout if you bet on winning team
     */
    function claimPayout() external {
        require(isSettled, "Not settled yet");
        require(userBets[msg.sender].length > 0, "No bets found");
        
        uint256 totalPayout = 0;
        
        // Calculate payout for all winning bets by this user
        for (uint i = 0; i < userBets[msg.sender].length; i++) {
            uint256 betIndex = userBets[msg.sender][i];
            Bet storage bet = betsByTeam[winningTeam][betIndex];
            
            if (bet.bettor == msg.sender && bet.selectedTeam == winningTeam && !bet.claimed) {
                uint256 payout = calculatePayout(bet.amount);
                totalPayout += payout;
                bet.claimed = true;
            }
        }
        
        require(totalPayout > 0, "No winnings to claim");
        
        payable(msg.sender).transfer(totalPayout);
        emit PayoutClaimed(msg.sender, totalPayout);
    }

    /**
     * @dev Calculate payout for a winning bet
     * @param betAmount Amount bet
     */
    function calculatePayout(uint256 betAmount) public view returns (uint256) {
        uint256 totalPool = totalBetsPerTeam[1] + totalBetsPerTeam[2];
        uint256 winnersPool = totalBetsPerTeam[winningTeam];
        
        if (winnersPool == 0) return 0;
        
        // Calculate proportional share of total pool
        uint256 grossPayout = (betAmount * totalPool) / winnersPool;
        
        // Deduct house fee
        uint256 houseFee = (grossPayout * HOUSE_FEE_PERCENT) / 100;
        return grossPayout - houseFee;
    }

    /**
     * @dev Get user's total bet amount on a team
     */
    function getUserBetsOnTeam(address user, uint8 team) external view returns (uint256) {
        uint256 total = 0;
        for (uint i = 0; i < betsByTeam[team].length; i++) {
            if (betsByTeam[team][i].bettor == user) {
                total += betsByTeam[team][i].amount;
            }
        }
        return total;
    }

    /**
     * @dev Owner can withdraw house fees
     */
    function withdrawFees() external onlyOwner {
        require(isSettled, "Not settled yet");
        uint256 balance = address(this).balance;
        payable(owner).transfer(balance);
    }
}
```

### Advanced: Oracle-Integrated Contract

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@chainlink/contracts/src/v0.8/ChainlinkClient.sol";
import "@chainlink/contracts/src/v0.8/ConfirmedOwner.sol";

/**
 * @title OracleSportsBetting
 * @dev Automated sports betting using Chainlink oracles for score data
 */
contract OracleSportsBetting is ChainlinkClient, ConfirmedOwner {
    using Chainlink for Chainlink.Request;

    struct Game {
        string gameId;          // External game ID (e.g., "NBA_2026_01_15_LAL_BOS")
        uint8 homeTeam;         // Team 1
        uint8 awayTeam;         // Team 2
        uint256 homeScore;
        uint256 awayScore;
        bool isFinalized;
        uint256 bettingCloseTime;
    }

    struct Bet {
        address bettor;
        uint256 amount;
        uint8 selectedTeam;
        bool claimed;
    }

    // Oracle configuration
    address private oracle;
    bytes32 private jobId;
    uint256 private fee;

    // Game state
    Game public game;
    mapping(uint8 => Bet[]) public betsByTeam;
    mapping(uint8 => uint256) public totalBetsPerTeam;
    
    event BetPlaced(address indexed bettor, uint8 team, uint256 amount);
    event ScoreRequested(bytes32 indexed requestId);
    event ScoreFulfilled(uint256 homeScore, uint256 awayScore);
    event GameFinalized(uint8 winningTeam);

    constructor(
        address _oracle,
        bytes32 _jobId,
        uint256 _fee,
        string memory _gameId,
        uint256 _bettingCloseTime
    ) ConfirmedOwner(msg.sender) {
        setChainlinkToken(0x326C977E6efc84E512bB9C30f76E30c160eD06FB); // Polygon Mumbai LINK
        oracle = _oracle;
        jobId = _jobId;
        fee = _fee;
        
        game = Game({
            gameId: _gameId,
            homeTeam: 1,
            awayTeam: 2,
            homeScore: 0,
            awayScore: 0,
            isFinalized: false,
            bettingCloseTime: _bettingCloseTime
        });
    }

    /**
     * @dev Place bet on a team (must be before game start)
     */
    function placeBet(uint8 team) external payable {
        require(block.timestamp < game.bettingCloseTime, "Betting closed");
        require(!game.isFinalized, "Game already finished");
        require(msg.value > 0, "Bet must be > 0");
        require(team == 1 || team == 2, "Invalid team");
        
        betsByTeam[team].push(Bet({
            bettor: msg.sender,
            amount: msg.value,
            selectedTeam: team,
            claimed: false
        }));
        
        totalBetsPerTeam[team] += msg.value;
        emit BetPlaced(msg.sender, team, msg.value);
    }

    /**
     * @dev Request game score from Chainlink oracle
     */
    function requestGameScore() public returns (bytes32 requestId) {
        require(block.timestamp >= game.bettingCloseTime, "Game not started");
        require(!game.isFinalized, "Already finalized");
        
        Chainlink.Request memory req = buildChainlinkRequest(
            jobId,
            address(this),
            this.fulfillScore.selector
        );
        
        // Set parameters for the oracle request
        req.add("gameId", game.gameId);
        req.add("endpoint", "score");
        
        requestId = sendChainlinkRequest(req, fee);
        emit ScoreRequested(requestId);
        
        return requestId;
    }

    /**
     * @dev Callback function for Chainlink oracle
     * @param _requestId Request ID
     * @param _homeScore Home team score
     * @param _awayScore Away team score
     */
    function fulfillScore(
        bytes32 _requestId,
        uint256 _homeScore,
        uint256 _awayScore
    ) public recordChainlinkFulfillment(_requestId) {
        game.homeScore = _homeScore;
        game.awayScore = _awayScore;
        game.isFinalized = true;
        
        emit ScoreFulfilled(_homeScore, _awayScore);
        
        // Determine winner
        uint8 winner;
        if (_homeScore > _awayScore) {
            winner = game.homeTeam;
        } else if (_awayScore > _homeScore) {
            winner = game.awayTeam;
        } else {
            winner = 0; // Tie - refund all bets
        }
        
        emit GameFinalized(winner);
    }

    /**
     * @dev Claim payout after game is finalized
     */
    function claimPayout() external {
        require(game.isFinalized, "Game not finalized");
        
        uint8 winningTeam;
        if (game.homeScore > game.awayScore) {
            winningTeam = game.homeTeam;
        } else if (game.awayScore > game.homeScore) {
            winningTeam = game.awayTeam;
        } else {
            // Tie - refund logic
            refundBets(msg.sender);
            return;
        }
        
        // Calculate and send payout
        uint256 totalPayout = calculateUserPayout(msg.sender, winningTeam);
        require(totalPayout > 0, "No winnings");
        
        payable(msg.sender).transfer(totalPayout);
    }

    /**
     * @dev Calculate payout for user
     */
    function calculateUserPayout(address user, uint8 winningTeam) internal returns (uint256) {
        uint256 userBetAmount = 0;
        
        // Find and mark user's winning bets
        for (uint i = 0; i < betsByTeam[winningTeam].length; i++) {
            Bet storage bet = betsByTeam[winningTeam][i];
            if (bet.bettor == user && !bet.claimed) {
                userBetAmount += bet.amount;
                bet.claimed = true;
            }
        }
        
        if (userBetAmount == 0) return 0;
        
        // Calculate proportional payout
        uint256 totalPool = totalBetsPerTeam[1] + totalBetsPerTeam[2];
        uint256 winnersPool = totalBetsPerTeam[winningTeam];
        
        return (userBetAmount * totalPool) / winnersPool;
    }

    /**
     * @dev Refund bets in case of tie
     */
    function refundBets(address user) internal {
        uint256 refundAmount = 0;
        
        for (uint8 team = 1; team <= 2; team++) {
            for (uint i = 0; i < betsByTeam[team].length; i++) {
                Bet storage bet = betsByTeam[team][i];
                if (bet.bettor == user && !bet.claimed) {
                    refundAmount += bet.amount;
                    bet.claimed = true;
                }
            }
        }
        
        if (refundAmount > 0) {
            payable(user).transfer(refundAmount);
        }
    }

    /**
     * @dev Withdraw LINK tokens (for oracle fees)
     */
    function withdrawLink() public onlyOwner {
        LinkTokenInterface link = LinkTokenInterface(chainlinkTokenAddress());
        require(
            link.transfer(msg.sender, link.balanceOf(address(this))),
            "Unable to transfer"
        );
    }
}
```

---

## 🔗 Chainlink Oracle Integration

### Why Oracles?
Smart contracts can't access external data (NBA scores, NHL results, etc.). Oracles securely bridge blockchain and real world.

### Supported Data Providers
1. **SportsDataIO** - NBA, NFL, MLB, NHL scores + stats
2. **TheRundown** - Odds and live game data
3. **SportMonks** - Global sports coverage

### Setup Process

#### 1. Get Oracle Credentials
```javascript
// On Polygon Mumbai testnet
const ORACLE_ADDRESS = "0x40193c8518BB267228Fc409a613bDbD8eC5a97b3";
const JOB_ID = "7d80a6386ef543a3abb52817f6707e3b"; // SportsDataIO job
const LINK_FEE = ethers.utils.parseEther("0.1"); // 0.1 LINK per request
```

#### 2. Fund Contract with LINK
```javascript
// Contract needs LINK tokens to pay oracle
const LinkToken = await ethers.getContractAt("LinkToken", LINK_ADDRESS);
await LinkToken.transfer(contractAddress, ethers.utils.parseEther("10"));
```

#### 3. Request Score Data
```solidity
// In your contract
function requestNBAScore(string memory gameId) public {
    Chainlink.Request memory req = buildChainlinkRequest(jobId, address(this), this.fulfill.selector);
    req.add("gameId", gameId);
    req.add("sport", "nba");
    sendChainlinkRequestTo(oracle, req, fee);
}

// Callback
function fulfill(bytes32 requestId, uint256 homeScore, uint256 awayScore) public {
    // Oracle calls this with the score
}
```

### Example: NBA Game Score Request
```javascript
// Frontend code to trigger oracle
const gameId = "NBA_2026_01_15_401584875"; // Your data pipeline provides this
const tx = await bettingContract.requestGameScore();
await tx.wait();

// Oracle fetches score and calls fulfill() automatically
// Contract then processes payouts
```

---

## ⚡ Layer 2 Deployment Guide

### Why Layer 2?
| Network | Gas Fee | Speed | Use Case |
|---------|---------|-------|----------|
| Ethereum Mainnet | $4-10+ | 30s-2min | Not practical for betting |
| **Polygon** | **$0.001-0.003** | **<2s** | **Best for high-volume betting** |
| **Arbitrum** | **$1-3** | **3-10s** | **Best for high-value bets** |

### Deploy to Polygon

#### 1. Install Dependencies
```bash
npm install --save-dev hardhat @nomiclabs/hardhat-ethers ethers
```

#### 2. Configure Hardhat
```javascript
// hardhat.config.js
require("@nomiclabs/hardhat-ethers");

module.exports = {
  solidity: "0.8.20",
  networks: {
    polygonMumbai: {
      url: "https://rpc-mumbai.maticvigil.com",
      accounts: [process.env.PRIVATE_KEY],
      chainId: 80001
    },
    polygon: {
      url: "https://polygon-rpc.com",
      accounts: [process.env.PRIVATE_KEY],
      chainId: 137
    }
  }
};
```

#### 3. Deploy Script
```javascript
// scripts/deploy.js
async function main() {
  const SportsBetting = await ethers.getContractFactory("SportsBetting");
  const betting = await SportsBetting.deploy();
  await betting.deployed();
  
  console.log("SportsBetting deployed to:", betting.address);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
```

#### 4. Deploy
```bash
# Testnet
npx hardhat run scripts/deploy.js --network polygonMumbai

# Mainnet (after testing!)
npx hardhat run scripts/deploy.js --network polygon
```

### Deploy to Arbitrum

```javascript
// hardhat.config.js - add Arbitrum
arbitrumTestnet: {
  url: "https://goerli-rollup.arbitrum.io/rpc",
  accounts: [process.env.PRIVATE_KEY],
  chainId: 421613
},
arbitrumOne: {
  url: "https://arb1.arbitrum.io/rpc",
  accounts: [process.env.PRIVATE_KEY],
  chainId: 42161
}
```

---

## 💻 Frontend Integration

### Connect MetaMask and Contract

```javascript
// app.js
import { ethers } from 'ethers';
import SportsBettingABI from './abi/SportsBetting.json';

const CONTRACT_ADDRESS = "0x..."; // Your deployed contract

// Connect wallet
async function connectWallet() {
  if (typeof window.ethereum !== 'undefined') {
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    const signer = provider.getSigner();
    const address = await signer.getAddress();
    
    console.log("Connected:", address);
    return { provider, signer };
  } else {
    alert("Please install MetaMask!");
  }
}

// Get contract instance
async function getContract() {
  const { signer } = await connectWallet();
  return new ethers.Contract(CONTRACT_ADDRESS, SportsBettingABI, signer);
}

// Place a bet
async function placeBet(team, amount) {
  const contract = await getContract();
  const tx = await contract.placeBet(team, {
    value: ethers.utils.parseEther(amount)
  });
  
  await tx.wait();
  console.log("Bet placed!");
}

// Check if user won
async function checkWinnings() {
  const contract = await getContract();
  const { signer } = await connectWallet();
  const address = await signer.getAddress();
  
  const team1Bets = await contract.getUserBetsOnTeam(address, 1);
  const team2Bets = await contract.getUserBetsOnTeam(address, 2);
  
  console.log("Team 1 bets:", ethers.utils.formatEther(team1Bets));
  console.log("Team 2 bets:", ethers.utils.formatEther(team2Bets));
}

// Claim payout
async function claimWinnings() {
  const contract = await getContract();
  const tx = await contract.claimPayout();
  await tx.wait();
  console.log("Payout claimed!");
}

// Listen to events
async function listenToEvents() {
  const contract = await getContract();
  
  contract.on("BetPlaced", (bettor, team, amount) => {
    console.log(`Bet placed: ${bettor} bet ${ethers.utils.formatEther(amount)} on team ${team}`);
  });
  
  contract.on("WinnerDeclared", (team, totalPool) => {
    console.log(`Winner: Team ${team}, Pool: ${ethers.utils.formatEther(totalPool)}`);
  });
}
```

### React Component Example

```jsx
// BettingComponent.jsx
import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';

function BettingComponent({ contractAddress, abi }) {
  const [contract, setContract] = useState(null);
  const [account, setAccount] = useState(null);
  const [betAmount, setBetAmount] = useState("0.1");
  const [selectedTeam, setSelectedTeam] = useState(1);
  const [totalPot, setTotalPot] = useState({ team1: "0", team2: "0" });

  useEffect(() => {
    initContract();
  }, []);

  async function initContract() {
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    const signer = provider.getSigner();
    const addr = await signer.getAddress();
    setAccount(addr);

    const contractInstance = new ethers.Contract(contractAddress, abi, signer);
    setContract(contractInstance);

    // Load current pot sizes
    const team1Total = await contractInstance.totalBetsPerTeam(1);
    const team2Total = await contractInstance.totalBetsPerTeam(2);
    setTotalPot({
      team1: ethers.utils.formatEther(team1Total),
      team2: ethers.utils.formatEther(team2Total)
    });
  }

  async function handlePlaceBet() {
    if (!contract) return;
    
    try {
      const tx = await contract.placeBet(selectedTeam, {
        value: ethers.utils.parseEther(betAmount)
      });
      
      await tx.wait();
      alert("Bet placed successfully!");
      
      // Refresh pot sizes
      initContract();
    } catch (error) {
      console.error(error);
      alert("Error placing bet");
    }
  }

  async function handleClaimPayout() {
    if (!contract) return;
    
    try {
      const tx = await contract.claimPayout();
      await tx.wait();
      alert("Payout claimed!");
    } catch (error) {
      console.error(error);
      alert("Error claiming payout");
    }
  }

  return (
    <div className="betting-container">
      <h2>Sports Betting DApp</h2>
      <p>Connected: {account}</p>
      
      <div className="pot-info">
        <p>Team 1 Pot: {totalPot.team1} MATIC</p>
        <p>Team 2 Pot: {totalPot.team2} MATIC</p>
      </div>

      <div className="bet-form">
        <select value={selectedTeam} onChange={(e) => setSelectedTeam(Number(e.target.value))}>
          <option value={1}>Team 1</option>
          <option value={2}>Team 2</option>
        </select>
        
        <input 
          type="number" 
          value={betAmount} 
          onChange={(e) => setBetAmount(e.target.value)}
          step="0.01"
          min="0.01"
        />
        
        <button onClick={handlePlaceBet}>Place Bet</button>
      </div>

      <button onClick={handleClaimPayout}>Claim Winnings</button>
    </div>
  );
}

export default BettingComponent;
```

---

## 🔒 Security Considerations

### Critical Vulnerabilities to Avoid

#### 1. Reentrancy Attack
```solidity
// ❌ VULNERABLE
function claimPayout() external {
    uint256 payout = calculatePayout(msg.sender);
    payable(msg.sender).transfer(payout); // Transfer first
    claimed[msg.sender] = true; // State change after
}

// ✅ SAFE - Checks-Effects-Interactions pattern
function claimPayout() external {
    require(!claimed[msg.sender], "Already claimed");
    uint256 payout = calculatePayout(msg.sender);
    claimed[msg.sender] = true; // State change first
    payable(msg.sender).transfer(payout); // Transfer last
}
```

#### 2. Integer Overflow (Use Solidity 0.8+)
```solidity
// Solidity 0.8+ has built-in overflow checks
// No need for SafeMath library anymore
uint256 total = amount1 + amount2; // Reverts on overflow
```

#### 3. Oracle Manipulation
```solidity
// Use multiple oracles and median value
function requestScore() public {
    requestFromOracle1();
    requestFromOracle2();
    requestFromOracle3();
    // Take median of 3 responses
}
```

#### 4. Front-Running Prevention
```solidity
// Commit-reveal scheme
mapping(address => bytes32) public commitments;

function commitBet(bytes32 commitment) external {
    commitments[msg.sender] = commitment;
}

function revealBet(uint8 team, bytes32 secret) external payable {
    require(keccak256(abi.encodePacked(team, secret)) == commitments[msg.sender]);
    // Place bet
}
```

### Audit Checklist
- [ ] Use latest Solidity version (0.8.20+)
- [ ] Follow Checks-Effects-Interactions pattern
- [ ] Add reentrancy guards where needed
- [ ] Validate all inputs
- [ ] Use pull over push for payments
- [ ] Implement access controls
- [ ] Add emergency pause mechanism
- [ ] Test with Slither/Mythril security tools
- [ ] Get professional audit before mainnet

---

## 🧪 Testing

### Hardhat Test Example

```javascript
// test/SportsBetting.test.js
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SportsBetting", function () {
  let sportsBetting;
  let owner;
  let addr1;
  let addr2;

  beforeEach(async function () {
    [owner, addr1, addr2] = await ethers.getSigners();
    const SportsBetting = await ethers.getContractFactory("SportsBetting");
    sportsBetting = await SportsBetting.deploy();
    await sportsBetting.deployed();
  });

  it("Should allow users to place bets", async function () {
    await sportsBetting.connect(addr1).placeBet(1, { 
      value: ethers.utils.parseEther("1.0") 
    });
    
    const totalTeam1 = await sportsBetting.totalBetsPerTeam(1);
    expect(totalTeam1).to.equal(ethers.utils.parseEther("1.0"));
  });

  it("Should close betting", async function () {
    await sportsBetting.closeBetting();
    const isOpen = await sportsBetting.isBettingOpen();
    expect(isOpen).to.equal(false);
  });

  it("Should calculate correct payouts", async function () {
    // Team 1: 2 ETH total
    await sportsBetting.connect(addr1).placeBet(1, { value: ethers.utils.parseEther("2.0") });
    
    // Team 2: 1 ETH total
    await sportsBetting.connect(addr2).placeBet(2, { value: ethers.utils.parseEther("1.0") });
    
    await sportsBetting.closeBetting();
    await sportsBetting.declareWinner(1);
    
    // Team 1 should get: (2 / 2) * 3 = 3 ETH - 2% fee = 2.94 ETH
    const payout = await sportsBetting.calculatePayout(ethers.utils.parseEther("2.0"));
    expect(payout).to.be.closeTo(
      ethers.utils.parseEther("2.94"),
      ethers.utils.parseEther("0.01")
    );
  });

  it("Should prevent betting after close", async function () {
    await sportsBetting.closeBetting();
    
    await expect(
      sportsBetting.connect(addr1).placeBet(1, { value: ethers.utils.parseEther("1.0") })
    ).to.be.revertedWith("Betting closed");
  });
});
```

### Run Tests
```bash
npx hardhat test
npx hardhat coverage  # Check test coverage
```

---

## 📊 Integration with Your Data Pipeline

### How Your Project Fits In

Your existing infrastructure is **PERFECT** for this:

```
Your Data Pipeline → Smart Contract Betting
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Data Collection (You have this ✅)
   ├── plugins/nba_stats.py  → NBA games
   ├── plugins/nfl_stats.py  → NFL games
   ├── plugins/mlb_stats.py  → MLB games
   └── nhl_game_events.py    → NHL games

2. Prediction Models (Next step)
   ├── Load historical data
   ├── Train ML models
   ├── Generate predictions
   └── Calculate probabilities

3. Smart Contract Creation (New)
   ├── Deploy contract for each game
   ├── Set betting close time
   ├── Allow users to bet
   └── Oracle fetches result → auto-settle

4. Oracle Integration (New)
   ├── Your database → Oracle → Blockchain
   ├── Or use Chainlink → SportsDataIO
   └── Trigger payouts automatically
```

### Example: NBA Game Flow

```python
# 1. Your existing pipeline gets game schedule
from plugins.nba_stats import NBAStatsFetcher

fetcher = NBAStatsFetcher()
games_today = fetcher.get_todays_games("2026-01-16")

for game in games_today:
    game_id = game['gameId']
    home_team = game['homeTeam']
    away_team = game['awayTeam']
    start_time = game['startTime']
    
    # 2. Deploy smart contract for this game
    contract = deploy_betting_contract(
        game_id=game_id,
        home_team=home_team,
        away_team=away_team,
        betting_close_time=start_time
    )
    
    # 3. Users bet via frontend
    # (happens via Web3 interface)
    
    # 4. After game ends, your pipeline has score
    final_score = fetcher.get_game_final_score(game_id)
    
    # 5. Either:
    # a) Manual: Owner calls declareWinner()
    # b) Oracle: Chainlink auto-fetches and settles
    
    # 6. Winners claim payouts via smart contract
```

### Custom Oracle (Use Your Data)

Instead of Chainlink, you could build your own oracle:

```python
# oracle_server.py
from web3 import Web3
from plugins.nba_stats import NBAStatsFetcher

w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

def submit_game_result(game_id):
    # Get score from your pipeline
    fetcher = NBAStatsFetcher()
    score = fetcher.get_game_final_score(game_id)
    
    # Submit to smart contract
    tx = contract.functions.declareWinner(
        homeScore=score['home'],
        awayScore=score['away']
    ).buildTransaction({
        'from': ORACLE_ADDRESS,
        'nonce': w3.eth.getTransactionCount(ORACLE_ADDRESS),
    })
    
    signed = w3.eth.account.signTransaction(tx, private_key=ORACLE_PRIVATE_KEY)
    tx_hash = w3.eth.sendRawTransaction(signed.rawTransaction)
    
    print(f"Result submitted: {tx_hash.hex()}")

# Run after each game
for game in completed_games:
    submit_game_result(game['gameId'])
```

---

## 💡 Advanced Features

### 1. Multi-Outcome Betting
```solidity
// Support over/under, spreads, etc.
enum BetType { MoneyLine, Spread, OverUnder }

struct Bet {
    address bettor;
    uint256 amount;
    BetType betType;
    int8 line; // For spreads/totals
    uint8 selection;
}
```

### 2. Live Betting
```solidity
// Update odds in real-time
function updateOdds(uint256 newOddsTeam1, uint256 newOddsTeam2) external onlyOracle {
    oddsTeam1 = newOddsTeam1;
    oddsTeam2 = newOddsTeam2;
    emit OddsUpdated(newOddsTeam1, newOddsTeam2);
}
```

### 3. Parlay Bets
```solidity
struct Parlay {
    address bettor;
    uint256 amount;
    uint256[] gameIds;
    uint8[] selections;
    bool claimed;
}

// Must win all games to collect
```

### 4. Liquidity Pools
```solidity
// Users can be liquidity providers instead of peer-to-peer
mapping(address => uint256) public liquidityProviders;

function addLiquidity() external payable {
    liquidityProviders[msg.sender] += msg.value;
}
```

---

## 🚀 Deployment Checklist

### Pre-Launch
- [ ] Write comprehensive tests (>90% coverage)
- [ ] Run security analysis (Slither, Mythril)
- [ ] Test on testnet (Mumbai/Goerli) for 2+ weeks
- [ ] Get professional smart contract audit
- [ ] Set up monitoring and alerts
- [ ] Prepare emergency pause mechanism
- [ ] Document all contract functions
- [ ] Create user guides

### Launch
- [ ] Deploy to Layer 2 (Polygon/Arbitrum)
- [ ] Verify contract on block explorer
- [ ] Fund with LINK (if using Chainlink)
- [ ] Test with small real bets
- [ ] Monitor gas costs and optimize
- [ ] Launch frontend
- [ ] Set up customer support

### Post-Launch
- [ ] Monitor contract 24/7
- [ ] Track gas usage and optimize
- [ ] Gather user feedback
- [ ] Plan upgrades (use proxy pattern)
- [ ] Build community
- [ ] Add more sports/markets

---

## 📚 Resources

### Learning
- **Solidity Docs**: https://docs.soliditylang.org/
- **Hardhat**: https://hardhat.org/
- **Ethers.js**: https://docs.ethers.io/
- **Chainlink Docs**: https://docs.chain.link/

### Open Source Examples
- **Sport-Betting-Contract**: https://github.com/benjamin-m-hodgson/Sport-Betting-Contract
- **Betfair Clone**: Various on GitHub
- **Prediction Markets**: Augur, Polymarket contracts

### Tools
- **Remix IDE**: https://remix.ethereum.org/
- **MetaMask**: https://metamask.io/
- **Polygon Faucet**: https://faucet.polygon.technology/
- **Arbitrum Bridge**: https://bridge.arbitrum.io/

### Security
- **OpenZeppelin**: https://www.openzeppelin.com/contracts
- **Slither**: https://github.com/crytic/slither
- **MythX**: https://mythx.io/

---

## ⚠️ Legal Disclaimer

Building and operating betting platforms requires:
- Gambling licenses in target jurisdictions
- KYC/AML compliance
- Legal counsel
- Understanding of local laws

**This guide is for educational purposes only.**

---

**Ready to build?** Start with the basic contract, test thoroughly on testnet, then consider oracle integration and Layer 2 deployment!
