#!/bin/bash

# TML Platform Integration Tests
# Continue on error to run all tests
set +e

echo "🧪 TML Platform Integration Tests"
echo "=================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="http://localhost:5001"
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test function
test_endpoint() {
    local test_name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    local expected_status=$5
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo ""
    echo -e "${BLUE}Test:${NC} $test_name"
    echo "  Method: $method"
    echo "  Endpoint: $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
    elif [ "$method" = "POST" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                   -H "Content-Type: application/json" \
                   -d "$data" \
                   "$API_URL$endpoint")
    fi
    
    if [ "$response" = "$expected_status" ] || [ "$response" = "200" ] || [ "$response" = "201" ] || [ "$response" = "202" ]; then
        echo -e "  ${GREEN}✅ PASSED${NC} (Status: $response)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "  ${RED}❌ FAILED${NC} (Expected: $expected_status, Got: $response)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Test database function
test_database() {
    local test_name=$1
    local query=$2
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo ""
    echo -e "${BLUE}Test:${NC} $test_name"
    
    if docker exec tml-postgres-1 psql -U tml_user -d tml_production -c "$query" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "  ${RED}❌ FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Test Redis function
test_redis() {
    local test_name=$1
    local command=$2
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo ""
    echo -e "${BLUE}Test:${NC} $test_name"
    
    if docker exec tml-redis-1 redis-cli $command > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "  ${RED}❌ FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo ""
echo "📊 Testing Database Connectivity..."
echo "-----------------------------------"

test_database "Database Connection" "SELECT 1;"
test_database "Transactions Table" "SELECT COUNT(*) FROM Transactions;"
test_database "Models Table" "SELECT COUNT(*) FROM Models;"
test_database "Indexes Present" "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';"

echo ""
echo "💾 Testing Redis Connectivity..."
echo "--------------------------------"

test_redis "Redis Connection" "PING"
test_redis "Redis SET Operation" "SET test_key test_value"
test_redis "Redis GET Operation" "GET test_key"
test_redis "Redis DELETE Operation" "DEL test_key"

echo ""
echo "🌐 Testing API Endpoints..."
echo "---------------------------"

# Health endpoints
test_endpoint "Health Check" "GET" "/health" "" "200"
test_endpoint "Metrics Endpoint" "GET" "/metrics" "" "200"

# Transaction endpoints
test_endpoint "Get Transactions" "GET" "/api/transactions" "" "200"
test_endpoint "Get Transaction Statistics" "GET" "/api/transactions/statistics" "" "200"

# Test creating a transaction
transaction_data='{
  "data": {
    "xCoord": 100.5,
    "yCoord": 200.3,
    "thickness": 25.0,
    "minThickness": 15.0,
    "features": {
      "temperature": 22.5,
      "pressure": 101.3
    },
    "quality": 0.95
  },
  "source": "integration-test",
  "metadata": {
    "test_run": true,
    "test_id": "test-001"
  }
}'

test_endpoint "Create Transaction" "POST" "/api/transactions" "$transaction_data" "202"

# Model endpoints
test_endpoint "Get Models" "GET" "/api/models" "" "200"
test_endpoint "Get Model Statistics" "GET" "/api/models/statistics" "" "200"

# Batch processing test
batch_data='{
  "transactions": [
    {
      "data": {
        "xCoord": 150.0,
        "yCoord": 250.0,
        "thickness": 28.0,
        "minThickness": 18.0,
        "features": {},
        "quality": 0.92
      },
      "source": "batch-test",
      "metadata": {}
    },
    {
      "data": {
        "xCoord": 175.0,
        "yCoord": 275.0,
        "thickness": 30.0,
        "minThickness": 20.0,
        "features": {},
        "quality": 0.88
      },
      "source": "batch-test",
      "metadata": {}
    }
  ]
}'

test_endpoint "Batch Process Transactions" "POST" "/api/transactions/batch" "$batch_data" "202"

# Spatial query test
test_endpoint "Spatial Query" "GET" "/api/models/spatial/neighbors?x=100&y=200&radius=50&maxResults=5" "" "200"

echo ""
echo "🔍 Testing MinIO Storage..."
echo "---------------------------"

# Test MinIO connectivity
if curl -sf http://localhost:9000/minio/health/live > /dev/null; then
    echo -e "${GREEN}✅ MinIO Health Check${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
else
    echo -e "${RED}❌ MinIO Health Check${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
fi

echo ""
echo "🐳 Testing Docker Containers..."
echo "-------------------------------"

containers=("tml-postgres-1" "tml-redis-1" "tml-minio-1" "tml-api-test")
for container in "${containers[@]}"; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if docker ps | grep -q "$container"; then
        echo -e "${GREEN}✅ $container is running${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ $container is not running${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
done

# Final Summary
echo ""
echo "=================================="
echo "📊 Integration Test Results"
echo "=================================="
echo ""
echo -e "${BLUE}Total Tests:${NC} $TOTAL_TESTS"
echo -e "${GREEN}Passed:${NC} $PASSED_TESTS"
echo -e "${RED}Failed:${NC} $FAILED_TESTS"
echo ""

SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
echo "Success Rate: $SUCCESS_RATE%"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 All integration tests PASSED!${NC}"
    echo ""
    echo "✅ Database connectivity verified"
    echo "✅ Redis cache operational"
    echo "✅ MinIO storage accessible"
    echo "✅ API endpoints responding"
    echo "✅ All containers healthy"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed${NC}"
    echo ""
    echo "Please check the failed tests above for details."
    exit 1
fi
