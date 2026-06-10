#!/bin/bash

# TML Platform - Apache Flink Startup Script

echo "🚀 Starting Apache Flink for TML Platform"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check service status
check_service() {
    if docker ps | grep -q $1; then
        echo -e "${GREEN}✓${NC} $2 is running"
        return 0
    else
        echo -e "${RED}✗${NC} $2 is not running"
        return 1
    fi
}

# Step 1: Check prerequisites
echo ""
echo "📋 Checking prerequisites..."
check_service "kafka" "Kafka" || { echo -e "${RED}Error: Kafka must be running first${NC}"; exit 1; }
check_service "postgres" "PostgreSQL" || { echo -e "${RED}Error: PostgreSQL must be running first${NC}"; exit 1; }
check_service "redis" "Redis" || { echo -e "${RED}Error: Redis must be running first${NC}"; exit 1; }

# Step 2: Start Flink cluster
echo ""
echo "🎯 Starting Flink cluster..."
docker-compose -f docker-compose-flink.yml up -d flink-jobmanager flink-taskmanager-1 flink-taskmanager-2

# Wait for Flink to be ready
echo "⏳ Waiting for Flink to initialize..."
sleep 10

# Check Flink status
if docker ps | grep -q flink-jobmanager; then
    echo -e "${GREEN}✓${NC} Flink JobManager started"
    echo -e "${GREEN}✓${NC} Flink UI available at: http://localhost:8081"
else
    echo -e "${RED}✗${NC} Failed to start Flink JobManager"
    exit 1
fi

# Step 3: Build Python Flink job container
echo ""
echo "🔨 Building Python Flink job container..."
docker build -f Dockerfile.flink -t tml-flink-job:latest .

# Step 4: Submit Flink job
echo ""
echo "📤 Submitting TML Flink job..."
docker-compose -f docker-compose-flink.yml up -d flink-python-job

# Wait for job to start
sleep 5

# Step 5: Verify job is running
echo ""
echo "🔍 Verifying Flink job status..."

# Check if Python job container is running
if docker ps | grep -q flink-python-job; then
    echo -e "${GREEN}✓${NC} TML Flink job submitted successfully"
    
    # Show recent logs
    echo ""
    echo "📜 Recent job logs:"
    docker logs --tail 10 flink-python-job
else
    echo -e "${RED}✗${NC} Failed to submit Flink job"
    echo "Check logs with: docker logs flink-python-job"
fi

# Step 6: Create test topic if not exists
echo ""
echo "📦 Ensuring Kafka topics exist..."
docker exec kafka kafka-topics.sh --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --topic transactions \
    --partitions 3 \
    --replication-factor 1

docker exec kafka kafka-topics.sh --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --topic model-updates \
    --partitions 3 \
    --replication-factor 1

echo -e "${GREEN}✓${NC} Kafka topics ready"

# Step 7: Display status summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Apache Flink Status Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Web UI: http://localhost:8081"
echo "📡 JobManager RPC: localhost:6123"
echo "💾 State Backend: RocksDB"
echo "🔄 Checkpointing: Enabled (30s interval)"
echo "⚡ Parallelism: 8 slots (2 TaskManagers × 4 slots)"
echo ""
echo "📥 Input Topic: transactions"
echo "📤 Output Topic: model-updates"
echo ""
echo -e "${GREEN}✅ Apache Flink is ready for TML processing!${NC}"
echo ""
echo "🛠️ Useful commands:"
echo "  • View logs: docker logs -f flink-python-job"
echo "  • Monitor UI: open http://localhost:8081"
echo "  • Stop Flink: docker-compose -f docker-compose-flink.yml down"
echo ""
