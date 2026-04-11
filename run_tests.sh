#!/bin/bash
# EventOps Test Runner
#
# Usage: ./run_tests.sh [group] [pytest-args...]
#
# Groups (pick one):
#   all             Run entire suite (85 tests, ~30 min)
#   basic           Basic chatbot tests (test_chatbot_scenarios.py)
#   comprehensive   Comprehensive tests (test_comprehensive.py)
#   gaps            Critical gap tests (test_critical_gaps.py)
#   deep            Deep prompting tests (test_deep_prompting.py)
#
# Category shortcuts (faster, targeted runs):
#   categories      Vendor categorization only
#   payments        All payment-related tests across all files
#   tasks           All task-related tests across all files
#   queries         All query tests (budget, complex, empty data)
#   context         Conversation context tests
#   deletes         Delete operation tests
#   subevents       Sub-event CRUD tests
#   feedback        Feedback system tests
#   errors          API error handling & edge cases
#   dashboard       Dashboard stats tests
#
# Examples:
#   ./run_tests.sh payments          # ~5 min, just payment tests
#   ./run_tests.sh tasks             # ~3 min, just task tests
#   ./run_tests.sh feedback          # ~1 min, no LLM calls
#   ./run_tests.sh errors            # ~1 min, API validation
#   ./run_tests.sh basic -x          # stop on first failure
#   ./run_tests.sh all --tb=long     # full suite, long tracebacks
#   ./run_tests.sh -k "test_pandit"  # run a single test by name

set -e
cd "$(dirname "$0")"

if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "eventops_venv" ]; then
    source eventops_venv/bin/activate
fi

GROUP="${1:-}"
shift 2>/dev/null || true
EXTRA_ARGS="$@"

case "$GROUP" in
    all|"")
        TARGET="tests/"
        DESC="All tests"
        ;;
    basic)
        TARGET="tests/test_chatbot_scenarios.py"
        DESC="Basic chatbot scenarios"
        ;;
    comprehensive)
        TARGET="tests/test_comprehensive.py"
        DESC="Comprehensive tests"
        ;;
    gaps)
        TARGET="tests/test_critical_gaps.py"
        DESC="Critical gap tests"
        ;;
    deep)
        TARGET="tests/test_deep_prompting.py"
        DESC="Deep prompting tests"
        ;;
    categories)
        TARGET="-k TestVendorCategorization or TestCategoryInference"
        DESC="Vendor categorization"
        ;;
    payments)
        TARGET="-k TestPaymentFlows or TestPaymentOperations or TestPaymentUpdateE2E or TestPendingPaymentLogic or TestDataAccuracy"
        DESC="Payment tests"
        ;;
    tasks)
        TARGET="-k TestTaskOperations or TestTaskAutoCreation"
        DESC="Task tests"
        ;;
    queries)
        TARGET="-k TestBudgetQueries or TestQueryHandling or TestComplexQueries or TestEmptyDataHandling"
        DESC="Query tests"
        ;;
    context)
        TARGET="-k TestConversationContext"
        DESC="Conversation context"
        ;;
    deletes)
        TARGET="-k TestDeleteE2E or TestDeleteOperations or TestDeleteConfirmation"
        DESC="Delete operation tests"
        ;;
    subevents)
        TARGET="-k TestSubEventCRUD or TestSubEventOperations or TestUpdateOperations"
        DESC="Sub-event tests"
        ;;
    feedback)
        TARGET="-k TestFeedbackSystem"
        DESC="Feedback system tests"
        ;;
    errors)
        TARGET="-k TestEdgeCases or TestAPIErrors"
        DESC="Error handling & edge cases"
        ;;
    dashboard)
        TARGET="-k TestDashboardStats or TestRelationshipIntegrity"
        DESC="Dashboard & relationship tests"
        ;;
    -k*)
        TARGET="$GROUP"
        DESC="Custom filter"
        ;;
    *)
        TARGET="-k $GROUP"
        DESC="Custom: $GROUP"
        ;;
esac

echo "========================================"
echo "  EventOps Test Runner"
echo "  Group: $DESC"
echo "========================================"
echo ""

python3 -m pytest tests/ $TARGET $EXTRA_ARGS

echo ""
echo "========================================"
echo "  Done: $DESC"
echo "========================================"
