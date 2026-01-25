# Deployment Protocol & Validation Checklist

## Overview
Standardized deployment protocol for the Multi-Sport Betting System to ensure reliable, repeatable deployments with zero manual interventions.

## Pre-Deployment Validation

### 1. Code Quality Checks
- [ ] **Static Analysis**: Run ruff check and fix
- [ ] **Dead Code Detection**: Run vulture with min-confidence 80
- [ ] **Type Checking**: Run mypy on critical modules (optional)
- [ ] **Security Scanning**: Check for known vulnerabilities

### 2. Test Validation
- [ ] **Unit Tests**: All unit tests pass (pytest tests/ -x)
- [ ] **Smoke Tests**: Comprehensive smoke tests pass (pytest tests/smoke/)
- [ ] **Integration Tests**: Integration tests pass (pytest tests/integration/)
- [ ] **Coverage**: Maintain >85% test coverage

### 3. Database Validation
- [ ] **Schema Consistency**: All tables have primary keys
- [ ] **Foreign Key Integrity**: No orphaned records
- [ ] **Data Quality**: Critical tables have minimum row counts
- [ ] **Migration Scripts**: Any schema changes have migration scripts

### 4. Configuration Validation
- [ ] **Environment Variables**: All required env vars are set
- [ ] **API Credentials**: Kalshi API credentials valid
- [ ] **Database Connections**: PostgreSQL connection successful
- [ ] **File Permissions**: Key files have correct permissions

## Deployment Process

### Blue-Green Deployment Pattern
1. **Prepare New Environment**
   - Build new Docker images
   - Run migrations on new database (if needed)
   - Validate new environment with smoke tests

2. **Traffic Switch**
   - Update load balancer to point to new environment
   - Monitor for errors
   - Have rollback plan ready

3. **Post-Deployment Validation**
   - Run comprehensive smoke tests
   - Verify all services are healthy
   - Monitor error rates for 15 minutes

### Docker Compose Deployment
```bash
# 1. Pull latest changes
git pull origin main

# 2. Run pre-deployment validation
./ci_cd_pipeline.sh --validate-only

# 3. Build new images
docker compose build

# 4. Deploy with zero downtime
docker compose up -d --scale airflow-worker=2

# 5. Wait for services to be healthy
sleep 30

# 6. Run post-deployment validation
python scripts/validate_deployment.py

# 7. Remove old containers
docker system prune -f
```

## Post-Deployment Verification

### Service Health Checks
- [ ] **Airflow Scheduler**: Responds to health check
- [ ] **Airflow Webserver**: API endpoints accessible
- [ ] **PostgreSQL**: Database queries successful
- [ ] **Redis**: Cache operations working
- [ ] **Dashboard**: Streamlit app accessible

### Functional Verification
- [ ] **DAG Parsing**: All DAGs parse successfully
- [ ] **Elo Engine**: All sport Elo classes initialize
- [ ] **Kalshi API**: Can connect to Kalshi (sandbox)
- [ ] **Data Pipeline**: Can download and process game data

### Performance Verification
- [ ] **Response Times**: API responses < 2 seconds
- [ ] **Database Queries**: Critical queries < 1 second
- [ ] **Memory Usage**: Services within limits
- [ ] **Disk Space**: Adequate free space

## Rollback Procedure

### Automatic Rollback Triggers
- Any service fails health check for 3 consecutive minutes
- Error rate exceeds 5% for 5 minutes
- Smoke tests fail on new deployment
- Database migration fails

### Manual Rollback Steps
```bash
# 1. Switch back to previous version
git checkout HEAD~1

# 2. Restart with previous version
docker compose down
docker compose up -d

# 3. Verify rollback successful
python scripts/validate_deployment.py
```

## Monitoring & Alerting

### Critical Metrics to Monitor
1. **Error Rates**: API error percentage
2. **Latency**: 95th percentile response times
3. **Throughput**: Requests per minute
4. **Resource Usage**: CPU, memory, disk
5. **Queue Lengths**: Airflow task queue sizes

### Alert Thresholds
- **P1 Critical**: Service down > 5 minutes
- **P2 High**: Error rate > 10% for 10 minutes
- **P3 Medium**: Latency > 5 seconds for 15 minutes
- **P4 Low**: Resource usage > 80% for 30 minutes

## Success Criteria

### Deployment Success Definition
- Zero manual interventions during deployment
- All smoke tests pass post-deployment
- Error rate remains below 1% for first hour
- No user-reported issues for 24 hours

### Continuous Improvement
- Track deployment success rate (target: 99%)
- Measure mean time to recovery (MTTR)
- Document all deployment failures and root causes
- Update this protocol based on lessons learned

## Emergency Procedures

### Database Recovery
1. **Point-in-Time Recovery**: Use PostgreSQL WAL archiving
2. **Backup Restoration**: Daily backups stored in S3/equivalent
3. **Data Validation**: Verify data integrity after recovery

### Service Recovery
1. **Container Restart**: `docker compose restart [service]`
2. **Full Restart**: `docker compose down && docker compose up -d`
3. **Resource Scaling**: Increase CPU/memory allocation if needed

## Appendix

### Required Tools
- Docker & Docker Compose
- Git
- Python 3.10+
- PostgreSQL client tools
- Monitoring dashboard (Grafana/Prometheus)

### Contact Information
- **Primary On-Call**: [Team Lead]
- **Secondary On-Call**: [Backup Engineer]
- **Escalation Path**: [Engineering Manager]

### Change Log
- **2026-01-24**: Initial deployment protocol created
- **2026-01-24**: Added blue-green deployment pattern
- **2026-01-24**: Enhanced validation checklist
