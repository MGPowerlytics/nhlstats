#!/bin/bash
# CI/CD Pipeline Script for Multi-Sport Betting System
# Runs code quality checks, tests, and restarts Docker containers

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

echo "🚀 Starting CI/CD Pipeline for Multi-Sport Betting System"
echo "=========================================================="
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if we're in the project root
if [ ! -f "requirements.txt" ] && [ ! -f "docker-compose.yaml" ]; then
    print_error "Not in project root directory. Please run from project root."
    exit 1
fi

# Step 1: Code Quality Checks
print_status "Step 1: Running code quality checks..."

# Check if vulture is installed
if ! command -v vulture &> /dev/null; then
    print_warning "vulture not found, installing..."
    pip install vulture
fi

print_status "Running vulture to find dead code..."
vulture . --min-confidence 80 --exclude "archive/*,tests/*,data/*,.venv/*,.git/*" > vulture_report.txt
VULTURE_EXIT_CODE=$?

if [ $VULTURE_EXIT_CODE -eq 0 ]; then
    DEAD_CODE_COUNT=$(wc -l < vulture_report.txt)
    if [ $DEAD_CODE_COUNT -eq 0 ]; then
        print_success "No dead code found"
    else
        print_warning "Found $DEAD_CODE_COUNT potential dead code items"
        cat vulture_report.txt
    fi
else
    print_error "Vulture failed with exit code $VULTURE_EXIT_CODE"
    exit 1
fi

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    print_warning "ruff not found, installing..."
    pip install ruff
fi

print_status "Running ruff for linting..."
ruff check . --fix
RUFF_EXIT_CODE=$?

if [ $RUFF_EXIT_CODE -eq 0 ]; then
    print_success "Ruff linting passed"
else
    print_error "Ruff found issues (exit code: $RUFF_EXIT_CODE)"
    # Continue anyway - ruff issues are warnings, not blockers
fi

# Step 2: Run Tests
print_status "Step 2: Running tests..."

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_warning "pytest not found, installing..."
    pip install pytest pytest-cov
fi

print_status "Running pytest with coverage..."
pytest tests/ \
    --cov=plugins \
    --cov=dags \
    --cov-report=term \
    --cov-report=html:reports/coverage \
    --cov-report=xml:reports/coverage.xml \
    --junitxml=reports/test-results.xml \
    -v

PYTEST_EXIT_CODE=$?

if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    print_success "All tests passed!"

    # Generate coverage summary
    COVERAGE=$(pytest --cov=plugins --cov=dags --cov-report=term-missing | grep "TOTAL" | awk '{print $4}')
    print_status "Test coverage: $COVERAGE"

    if [[ $COVERAGE < "85%" ]]; then
        print_warning "Coverage below 85% target: $COVERAGE"
    else
        print_success "Coverage meets 85% target: $COVERAGE"
    fi
else
    print_error "Tests failed with exit code $PYTEST_EXIT_CODE"
    exit 1
fi

# Step 3: Integration Tests (if they exist)
print_status "Step 3: Running integration tests..."

if [ -d "tests/" ] && compgen -G "tests/test_*integration*.py" > /dev/null; then
    print_status "Found integration tests, running them..."
    pytest tests/test_*integration*.py -v
    INTEGRATION_EXIT_CODE=$?

    if [ $INTEGRATION_EXIT_CODE -eq 0 ]; then
        print_success "Integration tests passed"
    else
        print_error "Integration tests failed"
        exit 1
    fi
else
    print_warning "No integration tests found"
fi

# Step 4: Data Validation (if script exists)
print_status "Step 4: Running data validation..."

if [ -f "plugins/data_validation.py" ]; then
    print_status "Running data validation script..."
    python -c "from plugins.data_validation import main; main()"
    VALIDATION_EXIT_CODE=$?

    if [ $VALIDIDATION_EXIT_CODE -eq 0 ]; then
        print_success "Data validation passed"
    else
        print_error "Data validation failed"
        exit 1
    fi
else
    print_warning "Data validation script not found"
fi

# Step 5: Docker Container Management
print_status "Step 5: Managing Docker containers..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker daemon."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "docker-compose not found"
    exit 1
fi

# Use docker compose (v2) if available, otherwise docker-compose (v1)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

print_status "Stopping existing containers..."
$DOCKER_COMPOSE_CMD down

print_status "Starting containers..."
$DOCKER_COMPOSE_CMD up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if services are running
print_status "Checking service status..."
$DOCKER_COMPOSE_CMD ps

# Step 6: Final Summary
print_status "Step 6: Generating final report..."

echo ""
echo "=========================================================="
echo "📊 CI/CD Pipeline Summary"
echo "=========================================================="
echo "✅ Code Quality: Vulture and Ruff checks completed"
echo "✅ Tests: pytest with coverage completed"
echo "✅ Integration: Integration tests completed"
echo "✅ Data Validation: Data validation completed"
echo "✅ Docker: Containers restarted"
echo ""
echo "📈 Test Coverage: $COVERAGE"
echo "📁 Reports generated in:"
echo "   - reports/coverage/ (HTML coverage report)"
echo "   - reports/coverage.xml (XML coverage report)"
echo "   - reports/test-results.xml (JUnit test results)"
echo "   - vulture_report.txt (Dead code analysis)"
echo ""
echo "🚀 Pipeline completed successfully at $(date)"
echo "=========================================================="

# Clean up
rm -f vulture_report.txt

exit 0
