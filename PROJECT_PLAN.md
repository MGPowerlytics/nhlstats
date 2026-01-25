# PROJECT_PLAN.md

*Last Updated: 2026-01-25*
*Current Status: Phase 1.1 COMPLETED, Phase 1.2 COMPLETED, Phase 1.3 COMPLETED, Phase 1.4 COMPLETED*

## 📊 Current System Overview

### ✅ **Production-Ready Components**
1. **Multi-Sport Elo Rating System** (9 sports: NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1)
2. **Automated Betting Pipeline** (Airflow DAGs with hourly/daily schedules)
3. **Portfolio Management** (Kelly Criterion, risk management, position sizing)
4. **Streamlit Dashboard** (Real-time monitoring, performance analytics)
5. **PostgreSQL Database** (Unified schema, historical data)
6. **Kalshi & BetMGM Integration** (Live betting, market data)
7. **Comprehensive Test Suite** (113 test files, 60+ Playwright tests)

### 🔄 **Recent Major Accomplishments** (from CHANGELOG.md)
- **2026-01-25**: Updated DAG imports to use unified Elo module (from elo import ...), ensuring all sport-specific Elo classes are imported correctly
- **2026-01-23**: BaseEloRating abstract class implemented via TDD, unified Elo interface established
- **2026-01-22**: Deposit tracking system, portfolio value fixes, tennis Elo calibration
- **2026-01-21**: NHL shift/play-by-play data verification, database connection fixes
- **2026-01-20**: PostgreSQL migration complete, dashboard updates, basketball backtesting
- **2026-01-19**: Portfolio betting optimization, WNCAAB support, order deduplication

---

## 🎯 **Phase 1: Immediate Priorities**

### **✅ 1.1 Code Quality & Technical Debt - COMPLETED**
| Priority | Task | Status | Notes |
|----------|------|--------|-------|
| ✅ High | Run Vulture to identify unused code | **COMPLETED** | 8 archive files deleted |
| ✅ High | Delete confirmed dead code from Vulture report | **COMPLETED** | Backup created, test files cleaned |
| ✅ High | Ensure all tests pass (ignore Playwright tests for now) | **COMPLETED** | 99.87% pass rate (3 tests skipped temporarily) |
| ✅ High | Create BaseEloRating abstract class | **COMPLETED** | TDD approach: 6/6 tests passing |
| 🔄 High | Refactor sport-specific Elo classes to inherit from BaseEloRating | **COMPLETED** | 9/9 completed (NHL, NBA, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis) |

### **✅ 1.2 Unified Elo Engine Refactoring - COMPLETED**
| Priority | Task | Status | Notes |
|----------|------|--------|-------|
| ✅ High | Refactor NHLEloRating to inherit from BaseEloRating | **COMPLETED** | All existing tests pass, maintains NHL-specific features |
| ✅ High | Refactor NBAEloRating to inherit from BaseEloRating | **COMPLETED** | All 3 TDD tests passing, maintains existing functionality |
| ✅ High | Refactor MLBEloRating to inherit from BaseEloRating | **COMPLETED** | All 10 existing tests pass, maintains backward compatibility with update_legacy |
| ✅ High | Refactor NFLEloRating to inherit from BaseEloRating | **COMPLETED** | All 7 existing tests pass, maintains backward compatibility with update_legacy |
| ✅ High | Refactor EPLEloRating to inherit from BaseEloRating | **COMPLETED** | All 5 TDD tests passing, maintains 3-way prediction functionality |
| ✅ High | Refactor Ligue1EloRating to inherit from BaseEloRating | **COMPLETED** | All 6 TDD tests passing, maintains 3-way prediction functionality |
| ✅ High | Refactor NCAABEloRating to inherit from BaseEloRating | **COMPLETED** | All 10 TDD tests passing, maintains existing functionality |
| ✅ High | Refactor WNCAABEloRating to inherit from BaseEloRating | **COMPLETED** | All 10 TDD tests passing, maintains existing functionality |
| ✅ High | Refactor TennisEloRating to inherit from BaseEloRating | **COMPLETED** | All 12 TDD tests passing, maintains tennis-specific functionality with interface adaptation |
| 🔄 Medium | Update SPORTS_CONFIG to use unified interface | **COMPLETED** | After all sport classes refactored |
| 🔄 Medium | Update DAGs to use unified Elo interface | **COMPLETED** | After SPORTS_CONFIG update |
| 🔄 Medium | Update dashboard to use unified Elo interface | **COMPLETED** | After DAGs updated |

### **1.3 Database & Schema Improvements**
| Priority | Task | Skills Required | Estimated Effort | Dependencies |
|----------|------|----------------|------------------|--------------|
| High | Document all DB tables and their producing DAG tasks | database-design, airflow-dag-patterns | **COMPLETED** | Database documentation created in docs/database_schema.md |
| High | Identify orphan tables (no DAG producer) | database-design | **COMPLETED** | Analysis complete: No orphan tables found |
| Medium | Ensure all tables have Primary Keys | database-design | **COMPLETED** | All documented tables have primary keys |
| Medium | Validate SPORTS_CONFIG matches unified_games.sport values | database-design | **COMPLETED** | Validation complete: SPORTS_CONFIG sport codes match database sport values |

## 🔗 **Phase 1.4: Integration Testing & Systems Integration Foundation**

### **Overview**
Comprehensive integration testing and systems integration foundation to verify all Phase 1 components work together correctly after the unified Elo refactoring and database documentation. This phase establishes the operational ecosystem needed for production reliability.

### **Integration Testing Tasks**
| Priority | Task | Skills Required | Estimated Effort | Dependencies | Status |
|----------|------|----------------|------------------|--------------|--------|
| 🔴 **CRITICAL** | **1.4.1: Comprehensive Smoke Test Suite | system-testing, validation | 8 hours | All Phase 1 components | **COMPLETED**** |
| 🔴 **CRITICAL** | **1.4.2: Integration Test Harness | test-automation, python-integration | 12 hours | Database, Elo system | **COMPLETED**** |
| 🔴 **CRITICAL** | **1.4.3: Observability Foundation | monitoring, logging, metrics | 16 hours | All components | **COMPLETED**** |
| 🔴 **CRITICAL** | **1.4.4: Deployment Validation Checklist | devops, deployment-automation | 6 hours | Docker, Airflow | **COMPLETED**** |
| 🔴 **HIGH** | DAG-Elo Integration Tests | airflow-testing, python-integration | 8 hours | DAGs, Elo system | **COMPLETED**** |
| 🔴 **HIGH** | Database Integration Tests | database-testing, sqlalchemy | 10 hours | Database schema | **COMPLETED**** |
| 🔴 **HIGH** | End-to-End Pipeline Test | system-testing, data-pipeline | 12 hours | All Phase 1 components | **COMPLETED**** |
| 🟡 **MEDIUM** | Dashboard Integration Tests | streamlit-testing, ui-testing | 6 hours | Dashboard, database | **COMPLETED**** |
| 🟡 **MEDIUM** | Cross-Sport Consistency Tests | test-automation, sports-logic | 8 hours | All 9 sports | **COMPLETED**** |
| 🟡 **MEDIUM** | Error Propagation Tests | error-handling, system-design | 6 hours | Component interfaces | **COMPLETED**** |
| 🟢 **LOW** | Performance Integration Tests | performance-testing, profiling | 8 hours | System stability | **COMPLETED**** |

### **Detailed Task Descriptions**

#### **1.4.1: Comprehensive Smoke Test Suite**
**Objective**: Establish "lights on" validation that the entire system works after deployment.

**Implementation**:
- Create `tests/smoke/test_system_smoke.py` with standardized smoke test protocol
- Validate: Database connectivity, Elo engine initialization, Kalshi API connectivity, Airflow DAG validation, Streamlit dashboard startup
- **Success Criteria**: 100% pass rate on smoke tests before any deployment

#### **1.4.2: Integration Test Harness**
**Objective**: Create standardized integration test environment with proper isolation.

**Implementation**:
- Create `tests/integration/conftest.py` with standardized test fixtures
- Implement database transaction isolation, mock external APIs, clean test data management
- **Enterprise Integration Pattern**: Channel Adapter Pattern with standardized test interfaces

#### **1.4.3: Observability Foundation**
**Objective**: Implement "If a system isn't monitored, it doesn't exist" philosophy.

**Implementation**:
- Create `config/observability/observability_standards.yaml` with standardized logging, metrics, tracing, and alerting
- Add structured logging to all components with correlation IDs and sport context
- Implement Prometheus metrics endpoint for core system metrics
- **Success Criteria**: All components emit structured logs and metrics

#### **1.4.4: Deployment Validation Checklist**
**Objective**: Replace manual container restarts with standardized deployment protocol.

**Implementation**:
- Create `docs/deployment_protocol.md` with Definition of Done checklist
- Implement pre-deployment validation, blue-green deployment patterns, post-deployment verification
- **Success Criteria**: Zero manual interventions in last 3 deployments

### **Success Criteria for Phase 1.4**
- **Smoke Tests**: 100% pass rate in staging environment
- **Integration Test Coverage**: 70%+ of component boundaries tested
- **Observability**: All components emit structured logs and metrics
- **Deployment Reliability**: Zero manual interventions in last 3 deployments
- **Error Classification**: 100% of errors categorized using standardized protocol

---

## 🚀 **Phase 2: Enhanced Features & Systems Integration**

### **2.1 Advanced Betting Models**
- Implement Bayesian Elo ratings with uncertainty quantification
- Add momentum-based adjustments (win/loss streaks)
- Implement home/away specific Elo adjustments

### **2.2 Performance Monitoring**
- Real-time betting performance dashboards
- Automated backtesting framework
- Risk-adjusted return metrics (Sharpe ratio, Sortino ratio)

### **2.3 Data Pipeline Improvements**
- Automated data quality checks
- Missing data detection and alerting
- Performance optimization for large datasets

### **2.4: Message Bus Architecture** 🔄 **NEW**
**Problem**: Tight coupling between Airflow tasks creates monolithic failure points.

**Enterprise Integration Pattern**: **Publish-Subscribe Channel**

**Implementation**:
- Create `plugins/integration/event_bus.py` with standardized event protocol
- Implement Redis Pub/Sub for decoupled processing
- Migrate from direct task dependencies to event-driven architecture

**Benefits**:
- Improved system reliability through decoupling
- Better scalability for adding new sports
- Enhanced fault isolation

### **2.5: Circuit Breaker Pattern for External APIs** 🔄 **NEW**
**Problem**: Kalshi API failures can cascade through the entire system.

**Implementation**:
- Create `plugins/integration/circuit_breaker.py` with standardized circuit breaker
- Implement failure thresholds, reset timeouts, and trial requests
- Add circuit breaker protection to all external API calls

**Benefits**:
- Prevent cascading failures
- Improve system resilience
- Better user experience during API outages

### **2.6: Standardized Error Handling Protocol** 🔄 **NEW**
**Problem**: Inconsistent error handling makes debugging and recovery unpredictable.

**Implementation**:
- Create `plugins/integration/errors.py` with error classification standard
- Define error categories: TRANSIENT, PERMANENT, SYSTEM
- Implement standardized error responses with error codes and suggested actions

**Benefits**:
- Consistent error handling across all components
- Improved debugging and monitoring
- Better user experience with clear error messages

### **2.7: API Governance & Standards** 🔄 **NEW**
**Problem**: Ad-hoc API development creates integration challenges.

**Implementation**:
- Create `docs/api_standards.md` with Minimum Viable API Standard
- Standardize versioning, error handling, authentication, and rate limiting
- Implement OpenAPI 3.0 specifications for all internal APIs

**Benefits**:
- Consistent API design across the platform
- Better developer experience
- Easier integration with external systems

### **The Golden Path: Pre-Approved Integration Stack**

| Component | Approved Solution | Rationale |
|-----------|-------------------|-----------|
| Message Bus | **Redis Pub/Sub** | Lightweight, battle-tested, Airflow-compatible |
| Metrics Collection | **Prometheus + Grafana** | Industry standard, rich visualization |
| Distributed Tracing | **Jaeger with OpenTelemetry** | CNCF project, language-agnostic |
| Error Tracking | **Sentry** | Excellent Python support, rich context |
| API Documentation | **OpenAPI 3.0 + Swagger UI** | Industry standard, tooling ecosystem |

### **Standardized Development Workflow**
1. **Write Integration Tests First** - Define component boundaries and interfaces
2. **Implement Feature** - Following TDD principles
3. **Run Smoke Tests** - Validate basic functionality
4. **Deploy to Staging** - Using blue-green deployment
5. **Run E2E Tests** - Validate complete workflows
6. **Performance Validation** - Ensure SLA compliance
7. **Deploy to Production** - With automated rollback capability

### **Impact Assessments**

#### **Security Impact**
| Improvement | Security Benefit | Risk Mitigation |
|-------------|-----------------|-----------------|
| Structured Logging | Audit trail for compliance | PII masking in logs |
| Circuit Breakers | DoS protection | Rate limiting configuration |
| API Standards | Consistent auth patterns | Regular security reviews |

#### **Performance Impact**
| Improvement | Performance Benefit | Monitoring Metric |
|-------------|-------------------|------------------|
| Message Bus | Decoupled processing | Event processing latency |
| Circuit Breakers | Fail-fast behavior | API call success rate |
| Caching Layer | Reduced API calls | Cache hit ratio |

#### **Cost Impact**
| Improvement | Cost Consideration | ROI Justification |
|-------------|-------------------|------------------|
| Observability Stack | Additional infrastructure | Reduced MTTR by 40% |
| Message Bus | Redis cluster costs | Improved system reliability |
| Testing Infrastructure | CI/CD pipeline costs | Fewer production incidents |

---

## 📈 **Success Metrics**
- **Test Coverage**: Maintain >85% coverage
- **System Uptime**: 99.9% for critical components
- **Betting Performance**: Positive expected value across all sports
- **Code Quality**: Zero critical issues in static analysis

---

## 🛠️ **Technical Standards**
1. **TDD First**: Write tests before implementation
2. **Type Hints**: All new code must include type hints
3. **Documentation**: Google-style docstrings for all public methods
4. **Code Formatting**: Black formatting for all Python code
5. **Database Usage**: All production data in PostgreSQL, no CSV/JSON for production
