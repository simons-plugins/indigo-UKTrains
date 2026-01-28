#!/bin/bash
#
# UK-Trains Plugin Test Runner
#
# Quick script to run the test suite with common options
#

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to tests directory
cd "$(dirname "$0")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}UK-Trains Plugin Test Suite${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}ERROR: pytest is not installed${NC}"
    echo -e "${YELLOW}Install with: pip3 install -r requirements-test.txt${NC}"
    exit 1
fi

# Parse command line arguments
MODE="${1:-all}"

case "$MODE" in
    all)
        echo -e "${YELLOW}Running all tests with coverage...${NC}"
        pytest --cov --cov-report=term-missing --cov-report=html -v
        ;;
    unit)
        echo -e "${YELLOW}Running unit tests only...${NC}"
        pytest -m unit -v
        ;;
    integration)
        echo -e "${YELLOW}Running integration tests only...${NC}"
        pytest -m integration -v
        ;;
    fast)
        echo -e "${YELLOW}Running fast tests (no slow tests)...${NC}"
        pytest -m "not slow" -v
        ;;
    coverage)
        echo -e "${YELLOW}Generating coverage report...${NC}"
        pytest --cov --cov-report=html
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;
    watch)
        echo -e "${YELLOW}Running tests in watch mode (install pytest-watch first)...${NC}"
        if command -v pytest-watch &> /dev/null; then
            pytest-watch -- --cov
        else
            echo -e "${RED}ERROR: pytest-watch not installed${NC}"
            echo -e "${YELLOW}Install with: pip3 install pytest-watch${NC}"
            exit 1
        fi
        ;;
    debug)
        echo -e "${YELLOW}Running tests in debug mode...${NC}"
        pytest --pdb -v
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo ""
        echo "Usage: $0 [mode]"
        echo ""
        echo "Modes:"
        echo "  all          - Run all tests with coverage (default)"
        echo "  unit         - Run only unit tests"
        echo "  integration  - Run only integration tests"
        echo "  fast         - Run only fast tests (skip slow ones)"
        echo "  coverage     - Generate HTML coverage report"
        echo "  watch        - Run tests in watch mode (auto-rerun on changes)"
        echo "  debug        - Run tests with Python debugger"
        echo ""
        exit 1
        ;;
esac

# Capture exit code
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

exit $EXIT_CODE
