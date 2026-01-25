### /mnt/data2/nhlstats/FUNCTIONAL_TESTS.md
```markdown
1: # FUNCTIONAL_TESTS.md
2:
3: ## Comprehensive Functional Test Suite for Multi-Sport Betting System
4:
5: ### **Purpose**
6: Regular validation of DAGs, database, and dashboard integration to ensure system health and data consistency across all components.
7:
8: ### **Execution Frequency**
9: - **Critical Tests (1-30):** Hourly or before each DAG run
10: - **Core Tests (31-70):** Daily during system validation
11: - **Comprehensive Tests (71-100+):** Weekly or during deployment validation
12:
13: ---
14:
15: ## 🚨 **CRITICAL TESTS (1-30) - Hourly/Daily Execution**
16:
17: ### **1. DAG Infrastructure Tests**
18: 1. **DAG Import Validation**: All DAGs import without syntax errors
19: 2. **DAG Schedule Verification**: DAG schedules are valid cron expressions
20: 3. **Task Dependency Validation**: No circular dependencies in DAG task graphs
21: 4. **Airflow Connection Health**: All database and API connections are reachable
22: 5. **DAG File Permissions**: DAG files have correct permissions (644)
23: 6. **DAG Catchup Settings**: Catchup is disabled for production DAGs
24: 7. **Task Retry Configuration**: All tasks have appropriate retry settings
25: 8. **Email Alert Configuration**: Error notifications are properly configured
26: 9. **DAG Timezone Consistency**: All DAGs use UTC timezone
27: 10. **DAG Owner Assignment**: All DAGs have valid owners
28:
29: ### **2. Database Connectivity Tests**
30: 11. **PostgreSQL Connection**: Database connection established successfully
31: 12. **Database User Permissions**: Application user has required CRUD permissions
32: 13. **Connection Pool Health**: Connection pool not exhausted
33: 14. **Database Latency Check**: Query response time < 100ms
34: 15. **Transaction Isolation**: Read committed isolation level active
35: 16. **WAL Replication**: Write-ahead logging functioning (if configured)
36: 17. **Vacuum Status**: No tables requiring aggressive vacuum
37: 18. **Connection String Validation**: Environment variables correctly set
38: 19. **SSL/TLS Connection**: Secure database connection established
39: 20. **Connection Timeout**: Connections establish within 5 seconds
40:
41: ### **3. Core Table Existence Tests**
42: 21. **unified_games Table**: Primary games table exists with correct schema
43: 22. **game_odds Table**: Betting odds table exists with correct schema
44: 23. **placed_bets Table**: Historical bets tracking table exists
45: 24. **portfolio_value_snapshots Table**: Portfolio history table exists
46: 25. **cash_deposits Table**: Deposit tracking table exists
47: 26. **bet_recommendations Table**: Bet recommendations table exists
48: 27. **canonical_mappings Table**: Team name resolution table exists
49: 28. **kalshi_markets Table**: Kalshi market data table exists
50: 29. **kalshi_trades Table**: Kalshi trade history table exists
51: 30. **kalshi_candlesticks Table**: Market candlestick data table exists
52:
53: ---
54:
55: ## 🔧 **CORE FUNCTIONAL TESTS (31-70) - Daily Execution**
56:
57: ### **4. Data Pipeline Integrity Tests**
58: 31. **Multi-Sport DAG Task Count**: All 9 sports processed in main workflow
59: 32. **Sport-Specific Game Modules**: All sport game modules import successfully
60: 33. **Elo Class Instantiation**: All 9 Elo rating classes instantiate without errors
61: 34. **SPORTS_CONFIG Validation**: Configuration includes all 9 sports (NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1)
62: 35. **Game Data Download**: Each sport's game download function executes
63: 36. **Elo Rating Updates**: Elo ratings calculate for each sport
64: 37. **Market Data Fetch**: Kalshi market data retrieval for each sport
65: 38. **Bet Opportunity Identification**: Edge calculation works for all sports
66: 39. **Portfolio Optimization**: Kelly criterion calculations execute
67: 40. **Bet Placement Simulation**: Bet placement logic validates without actual placement
68:
69: ### **5. Database Schema & Data Quality Tests**
70: 41. **Primary Key Enforcement**: All tables have primary keys
71: 42. **Foreign Key Relationships**: Referential integrity maintained
72: 43. **Column Data Types**: All columns have appropriate data types
73: 44. **NULL Constraint Validation**: Required columns reject NULL values
74: 45. **Date Range Consistency**: All dates are within valid ranges
75: 46. **Probability Bounds**: All probabilities between 0 and 1
76: 47. **Currency Validation**: All monetary values positive and reasonable
77: 48. **Team Name Consistency**: Team names match canonical mappings
78: 49. **Sport Code Validation**: Sport codes match SPORTS_CONFIG
79: 50. **Timestamp Ordering**: Created_at <= updated_at for all records
80:
81: ### **6. Kalshi Integration Tests**
82: 51. **API Authentication**: Kalshi API key authentication succeeds
83: 52. **Market Data Retrieval**: Live market data fetch succeeds
84: 53. **Historical Data Access**: Historical market data available
85: 54. **Order Placement Simulation**: Order creation logic validates
86: 55. **Fill Status Checking**: Fill retrieval works
87: 56. **Portfolio Balance**: Current balance retrievable
88: 57. **Position Tracking**: Open positions list retrievable
89: 58. **Market Status Validation**: Market status codes are valid
90: 59. **Price Validation**: Market prices within 0-100 range
91: 60. **Contract Validation**: Contract counts are integers > 0
92:
93: ### **7. Dashboard Integration Tests**
94: 61. **Streamlit Server Startup**: Dashboard launches without errors
95: 62. **Database Connection from Dashboard**: Dashboard connects to PostgreSQL
96: 63. **Data Loading Performance**: Dashboard loads within 5 seconds
97: 64. **Chart Generation**: All Plotly charts render successfully
98: 65. **Filter Functionality**: Sport/date filters work correctly
99: 66. **Real-time Updates**: Dashboard shows current data
100: 67. **Portfolio Visualization**: Portfolio charts display correctly
101: 68. **Performance Metrics**: ROI, Sharpe ratio calculations work
102: 69. **Bet History Display**: Historical bets show correctly
103: 70. **Mobile Responsiveness**: Dashboard works on mobile devices
104:
105: ---
106:
107: ## 📊 **COMPREHENSIVE VALIDATION TESTS (71-100+) - Weekly Execution**
108:
109: ### **8. Cross-Component Integration Tests**
110: 71. **DAG-to-Database Flow**: DAG tasks write correctly to database
111: 72. **Database-to-Dashboard Flow**: Dashboard reads DAG-generated data
112: 73. **Real-time Sync**: Hourly sync DAG updates dashboard within 5 minutes
113: 74. **Data Freshness**: No data older than 24 hours in critical tables
114: 75. **Consistency Across Sports**: All 9 sports follow same data patterns
115: 76. **Error Propagation**: Component failures don't cascade
116: 77. **Recovery Procedures**: System recovers from individual component failures
117: 78. **Data Backup Integrity**: Backup files contain valid data
118: 79. **Logging Consistency**: All components log to same system
119: 80. **Monitoring Integration**: All components report to monitoring system
120:
121: ### **9. Business Logic Validation Tests**
122: 81. **Elo Rating Accuracy**: Elo predictions are probabilistically calibrated
123: 82. **Edge Calculation**: Positive edge opportunities identified correctly
124: 83. **Kelly Criterion**: Bet sizing follows Kelly formula
125: 84. **Portfolio Diversification**: Bets distributed across sports
126: 85. **Risk Management**: No single bet exceeds risk limits
127: 86. **Profit/Loss Calculation**: P&L calculations are accurate
128: 87. **ROI Tracking**: Return on investment calculated correctly
129: 88. **Win Rate Validation**: Actual win rate matches expected
130: 89. **Bankroll Management**: Total exposure within bankroll limits
131: 90. **Seasonal Adjustments**: Sport seasonality handled correctly
132:
133: ### **10. Performance & Scalability Tests**
134: 91. **Query Performance**: Critical queries execute under 1 second
135: 92. **Data Volume Handling**: System handles 10,000+ game records
136: 93. **Concurrent Access**: Multiple dashboard users supported
137: 94. **API Rate Limiting**: External API calls respect rate limits
138: 95. **Memory Usage**: System operates within memory limits
139: 96. **Disk Space**: Database growth within expected bounds
140: 97. **Network Latency**: External API calls complete within 10 seconds
141: 98. **Batch Processing**: Daily batch completes within 2 hours
142: 99. **Real-time Processing**: Hourly sync completes within 5 minutes
143: 100. **Error Recovery Time**: System recovers from errors within 15 minutes
144:
145: ### **11. Security & Compliance Tests**
146: 101. **API Key Rotation**: Kalshi API keys can be rotated
147: 102. **Database Encryption**: Sensitive data encrypted at rest
148: 103. **Access Control**: Unauthorized access prevented
149: 104. **Audit Trail**: All bet actions logged
150: 105. **Data Privacy**: PII not stored unnecessarily
151: 106. **Compliance Logging**: Regulatory requirements met
152: 107. **Backup Security**: Backups encrypted and secure
153: 108. **Network Security**: Firewall rules properly configured
154: 109. **Vulnerability Scanning**: Regular security scans clean
155: 110. **Incident Response**: Security incident procedures documented
156:
157: ### **12. Disaster Recovery Tests**
158: 111. **Database Backup Restoration**: Backups can be restored within 1 hour
159: 112. **DAG Replay Capability**: Historical DAG runs can be replayed
160: 113. **Data Migration**: Data can be migrated to new database
161: 114. **Component Isolation**: Individual components can be replaced
162: 115. **Rollback Procedures**: Failed deployments can be rolled back
163: 116. **High Availability**: System operates during single component failure
164: 117. **Data Consistency Post-Recovery**: Data remains consistent after recovery
165: 118. **Alerting System**: Alerts trigger for critical failures
166: 119. **Documentation Accuracy**: Recovery procedures documented and tested
167: 120. **Team Response**: Team can execute recovery within SLA
168:
169: ---
170:
171: ## 🛠️ **IMPLEMENTATION GUIDANCE**
172:
173: ### **Test Execution Framework**
174: ```python
175: # Example test structure for automated execution
176: class FunctionalTestSuite:
177:     def test_dag_import(self):
178:         """Test 1: DAG Import Validation"""
179:         from airflow.models import DagBag
180:         dag_bag = DagBag(dag_folder="dags", include_examples=False)
181:         assert len(dag_bag.import_errors) == 0
182:
183:     def test_database_connection(self):
184:         """Test 11: PostgreSQL Connection"""
185:         from plugins.db_manager import get_engine
186:         engine = get_engine()
187:         with engine.connect() as conn:
188:             result = conn.execute("SELECT 1")
189:             assert result.scalar() == 1
190:
191:     def test_core_tables_exist(self):
192:         """Test 21-30: Core Table Existence"""
193:         from plugins.db_manager import get_engine
194:         engine = get_engine()
195:         required_tables = [
196:             'unified_games', 'game_odds', 'placed_bets',
197:             'portfolio_value_snapshots', 'cash_deposits'
198:         ]
199:         existing_tables = engine.table_names()
200:         for table in required_tables:
201:             assert table in existing_tables
202: ```
203:
204: ### **Monitoring Integration**
205: - **Success Criteria**: 95%+ of tests pass
206: - **Alert Threshold**: < 90% pass rate triggers alert
207: - **Execution Schedule**:
208:   - Critical tests: Hourly via cron
209:   - Core tests: Daily at 2 AM UTC
210:   - Comprehensive tests: Weekly on Sunday at 3 AM UTC
211:
212: ### **Test Results Storage**
213: - Store results in `test_results_functional.csv`
214: - Maintain 30-day rolling history
215: - Integrate with existing CI/CD pipeline
216: - Include in deployment validation checklist
217:
218: ### **Failure Response Protocol**
219: 1. **Critical Failure** (< 80% pass rate): Immediate team notification
220: 2. **Moderate Failure** (80-90% pass rate): Daily review required
221: 3. **Minor Failure** (> 90% pass rate): Weekly review
222:
223: ---
224:
225: ## 📈 **CONTINUOUS IMPROVEMENT**
226:
227: ### **Metrics to Track**
228: - Test pass rate over time
229: - Time to detect failures
230: - Time to resolve failures
231: - Most frequent failure categories
232: - System uptime based on test results
233:
234: ### **Regular Review**
235: - Weekly review of test failures
236: - Monthly review of test coverage
237: - Quarterly review of test effectiveness
238: - Annual comprehensive test suite audit
239:
240: ### **Test Maintenance**
241: - Update tests when system components change
242: - Add tests for new features before deployment
243: - Remove obsolete tests
244: - Optimize test execution time
245:
246: ---
247:
248: **Last Updated**: 2026-01-25
249: **Test Count**: 120+ comprehensive functional checks
250: **Coverage**: DAGs, Database, Dashboard, Integration, Security, Recovery
251: **Status**: ✅ READY FOR IMPLEMENTATION
```


---

## 🕐 **HOURLY TEST SCRIPT IMPLEMENTATION**

### **Script Created: `scripts/hourly_functional_tests.sh`**

#### **Features:**
- **AI Agent Ready**: Structured output for AI diagnosis and repair
- **Comprehensive Logging**: Detailed logs with timestamps and colors
- **Test Categories**: 8 critical test categories covering core functionality
- **Diagnostic Reports**: Machine-readable output for failed tests
- **Exit Codes**: Clear success/failure indicators (0 = success, 1 = failure)

#### **Test Categories Implemented:**
1. **DAG Infrastructure Tests**: Import validation, schedule verification
2. **Database Connectivity Tests**: Connection, core table existence
3. **Elo System Tests**: All 9 Elo classes instantiation
4. **Sports Configuration Tests**: SPORTS_CONFIG validation
5. **Dashboard Integration Tests**: Streamlit app import
6. **Data Pipeline Tests**: Data validation module functionality
7. **Portfolio System Tests**: Portfolio snapshot system
8. **Kalshi Integration Tests**: Kalshi betting module structure

#### **Usage:**
```bash
# Run all tests
./scripts/hourly_functional_tests.sh

# Get help
./scripts/hourly_functional_tests.sh --help

# Expected output when tests pass:
# [SUCCESS] All X tests passed!
# ALL_TESTS_PASSED

# Expected output when tests fail:
# [ERROR] Tests failed: X
# DIAGNOSTIC_REPORT_START
# ... machine-readable diagnostic info ...
# DIAGNOSTIC_REPORT_END
```

#### **AI Agent Integration:**
The script produces structured output that AI agents can parse:
- `ALL_TESTS_PASSED`: System is healthy
- `DIAGNOSTIC_REPORT_START/END`: Contains failure details for AI diagnosis
- Log files in `logs/` directory with detailed execution traces

#### **Scheduling:**
Add to crontab for hourly execution:
```bash
# Run hourly at minute 0
0 * * * * /mnt/data2/nhlstats/scripts/hourly_functional_tests.sh
```

#### **Next Steps for Implementation:**
1. **Fix DAG Import Issue**: Current script shows DAG import errors (see logs)
2. **Add to CI/CD**: Integrate with existing `ci_cd_pipeline.sh`
3. **Monitoring Integration**: Connect test results to monitoring system
4. **Alert Configuration**: Set up alerts for test failures
5. **Expand Test Coverage**: Add more tests from the comprehensive list

#### **Status:**
✅ **Script Created**: `scripts/hourly_functional_tests.sh`
✅ **Executable**: Script is executable (chmod +x)
⚠️ **Initial Test**: Some tests failing (DAG import issues)
📋 **Ready for AI Agent**: Diagnostic output structured for AI repair

**Last Updated**: 2026-01-25
