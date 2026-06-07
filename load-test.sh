#!/bin/bash

# TML Platform Load Testing Script
echo "⚡ TML Platform Load Testing"
echo "============================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="http://localhost:5001"
TRANSACTIONS_PER_BATCH=50
BATCHES=20
TOTAL_TRANSACTIONS=$((TRANSACTIONS_PER_BATCH * BATCHES))
CONCURRENT_REQUESTS=5

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  API URL: $API_URL"
echo "  Transactions per batch: $TRANSACTIONS_PER_BATCH"
echo "  Number of batches: $BATCHES"  
echo "  Total transactions: $TOTAL_TRANSACTIONS"
echo "  Concurrent requests: $CONCURRENT_REQUESTS"
echo ""

# Function to generate random transaction data
generate_transaction() {
    local x=$((RANDOM % 1000 + 100))
    local y=$((RANDOM % 1000 + 100))
    local thickness=$((RANDOM % 20 + 15))
    local quality=$(echo "scale=2; 0.7 + $(($RANDOM % 30)) / 100" | bc)
    
    echo "{
        \"data\": {
            \"xCoord\": $x.$(($RANDOM % 99)),
            \"yCoord\": $y.$(($RANDOM % 99)),
            \"thickness\": $thickness.$(($RANDOM % 99)),
            \"minThickness\": 15.0,
            \"features\": {
                \"temperature\": $(($RANDOM % 10 + 20)).$(($RANDOM % 99)),
                \"pressure\": $(($RANDOM % 20 + 95)).$(($RANDOM % 99))
            },
            \"quality\": $quality
        },
        \"source\": \"load-test-$(date +%s)\",
        \"metadata\": {
            \"batch_id\": \"batch-$1\",
            \"test_type\": \"load\"
        }
    }"
}

# Function to generate batch
generate_batch() {
    local batch_id=$1
    local size=$2
    
    echo "{"
    echo "  \"transactions\": ["
    for ((i=1; i<=size; i++)); do
        generate_transaction "$batch_id"
        if [ $i -lt $size ]; then
            echo ","
        fi
    done
    echo "  ]"
    echo "}"
}

# Create results directory
mkdir -p load-test-results
RESULTS_FILE="load-test-results/test-$(date +%Y%m%d-%H%M%S).txt"

echo -e "${BLUE}Starting Load Test...${NC}"
echo ""

# Track timing
START_TIME=$(date +%s)

# Function to send batch
send_batch() {
    local batch_num=$1
    local batch_data=$(generate_batch "$batch_num" "$TRANSACTIONS_PER_BATCH")
    
    echo -n "Batch $batch_num: "
    
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" \
                          -X POST \
                          -H "Content-Type: application/json" \
                          -d "$batch_data" \
                          "$API_URL/api/transactions/batch")
    
    echo "Response time: ${response_time}s" | tee -a "$RESULTS_FILE"
}

# Send batches with concurrency control
echo "Sending $BATCHES batches..." | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

for ((batch=1; batch<=BATCHES; batch++)); do
    # Run in background for concurrency
    send_batch $batch &
    
    # Control concurrency
    if [ $((batch % CONCURRENT_REQUESTS)) -eq 0 ]; then
        wait
    fi
done

# Wait for all remaining jobs
wait

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "" | tee -a "$RESULTS_FILE"
echo "===========================" | tee -a "$RESULTS_FILE"
echo "Load Test Results" | tee -a "$RESULTS_FILE"
echo "===========================" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

echo -e "${BLUE}Summary:${NC}" | tee -a "$RESULTS_FILE"
echo "  Total transactions: $TOTAL_TRANSACTIONS" | tee -a "$RESULTS_FILE"
echo "  Total duration: ${DURATION}s" | tee -a "$RESULTS_FILE"
echo "  Transactions per second: $((TOTAL_TRANSACTIONS / DURATION))" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

# Check database for results
echo -e "${BLUE}Database Statistics:${NC}" | tee -a "$RESULTS_FILE"
if docker exec tml-postgres-1 psql -U tml_user -d tml_production -t -c "SELECT COUNT(*) FROM Transactions;" 2>/dev/null; then
    TRANSACTION_COUNT=$(docker exec tml-postgres-1 psql -U tml_user -d tml_production -t -c "SELECT COUNT(*) FROM Transactions;" 2>/dev/null | tr -d ' ')
    echo "  Transactions in database: $TRANSACTION_COUNT" | tee -a "$RESULTS_FILE"
fi

if docker exec tml-postgres-1 psql -U tml_user -d tml_production -t -c "SELECT COUNT(*) FROM Models;" 2>/dev/null; then
    MODEL_COUNT=$(docker exec tml-postgres-1 psql -U tml_user -d tml_production -t -c "SELECT COUNT(*) FROM Models;" 2>/dev/null | tr -d ' ')
    echo "  Models in database: $MODEL_COUNT" | tee -a "$RESULTS_FILE"
fi

echo "" | tee -a "$RESULTS_FILE"

# Check Redis cache
echo -e "${BLUE}Cache Statistics:${NC}" | tee -a "$RESULTS_FILE"
CACHE_KEYS=$(docker exec tml-redis-1 redis-cli DBSIZE | cut -d' ' -f2)
echo "  Keys in cache: $CACHE_KEYS" | tee -a "$RESULTS_FILE"

MEMORY_USAGE=$(docker exec tml-redis-1 redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
echo "  Memory usage: $MEMORY_USAGE" | tee -a "$RESULTS_FILE"

echo "" | tee -a "$RESULTS_FILE"
echo -e "${GREEN}✅ Load test completed!${NC}" | tee -a "$RESULTS_FILE"
echo "Results saved to: $RESULTS_FILE"
