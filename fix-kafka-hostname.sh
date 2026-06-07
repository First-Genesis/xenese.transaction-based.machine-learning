#!/bin/bash

echo "🔧 Fixing Kafka Hostname Resolution Issue"
echo "========================================="
echo ""
echo "Error detected: 'Unable to canonicalize address zookeeper:2181'"
echo "This means Kafka cannot resolve the Zookeeper hostname."
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down
docker stop kafka zookeeper 2>/dev/null || true
docker rm kafka zookeeper 2>/dev/null || true

# Clear volumes to ensure clean start
echo "🧹 Clearing old data..."
docker volume rm tml_kafka_data tml_zookeeper_data tml_zookeeper_logs 2>/dev/null || true

echo ""
echo "🚀 Starting services with fixed configuration..."
echo "Using simplified docker-compose with proper hostnames..."
echo ""

# Use the simplified configuration
docker-compose -f docker-compose-simplified.yml up -d zookeeper

echo "⏳ Waiting for Zookeeper to start (20 seconds)..."
sleep 20

# Check if zookeeper is running
if docker exec zookeeper bash -c "echo ruok | nc localhost 2181" 2>/dev/null | grep -q imok; then
    echo "✅ Zookeeper is healthy!"
else
    echo "⚠️  Zookeeper may still be starting..."
fi

# Start Kafka
echo ""
echo "🚀 Starting Kafka..."
docker-compose -f docker-compose-simplified.yml up -d kafka

echo "⏳ Waiting for Kafka to start (30 seconds)..."
sleep 30

# Verify Kafka is working
echo ""
echo "🔍 Verifying Kafka connectivity..."
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1

# Create test topic
echo ""
echo "📝 Creating test topic..."
docker exec kafka kafka-topics \
    --bootstrap-server localhost:9092 \
    --create --topic test-topic \
    --partitions 3 --replication-factor 1 2>/dev/null || echo "Topic may already exist"

# Show running containers
echo ""
echo "📊 Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|kafka|zookeeper"

echo ""
echo "✅ Fix applied! Key changes:"
echo "   - Container names match service names (kafka, zookeeper)"
echo "   - Hostnames properly configured"
echo "   - Zookeeper exposed on port 2181"
echo "   - Network resolution should work correctly"
echo ""
echo "💡 Test commands:"
echo "   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list"
echo "   docker logs kafka --tail 50"
echo "   docker logs zookeeper --tail 50"
echo ""
echo "🌐 Access Kafka UI at: http://localhost:8082"
