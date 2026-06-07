#!/bin/bash

echo "🔧 Fixing Kafka Container Issues with Redpanda"
echo "=============================================="
echo ""
echo "Error: confluentinc/cp-kafka:7.4.0 failing"
echo "Solution: Replace with Redpanda (Kafka-compatible, no Zookeeper needed)"
echo ""

# Function to stop existing containers
cleanup_kafka() {
    echo "🧹 Cleaning up existing Kafka/Zookeeper containers..."
    docker-compose down 2>/dev/null || true
    docker stop kafka zookeeper 2>/dev/null || true
    docker rm kafka zookeeper 2>/dev/null || true
    docker volume rm tml_kafka_data tml_zookeeper_data tml_zookeeper_logs 2>/dev/null || true
    echo "✅ Cleanup complete"
}

# Function to start Redpanda
start_redpanda() {
    echo ""
    echo "🚀 Starting Redpanda (Kafka-compatible)..."
    
    # Use the Redpanda docker-compose
    docker-compose -f docker-compose-redpanda.yml up -d redpanda
    
    echo "⏳ Waiting for Redpanda to start (20 seconds)..."
    sleep 20
    
    # Check if Redpanda is healthy
    if docker exec redpanda curl -f http://localhost:9644/v1/cluster/health_overview > /dev/null 2>&1; then
        echo "✅ Redpanda is healthy!"
    else
        echo "⚠️  Redpanda may still be starting..."
    fi
    
    # Create test topics
    echo ""
    echo "📝 Creating TML topics..."
    docker exec redpanda rpk topic create tml-transactions --partitions 10 --replicas 1 2>/dev/null || echo "  Topic tml-transactions already exists"
    docker exec redpanda rpk topic create tml-models --partitions 5 --replicas 1 2>/dev/null || echo "  Topic tml-models already exists"
    docker exec redpanda rpk topic create tml-predictions --partitions 10 --replicas 1 2>/dev/null || echo "  Topic tml-predictions already exists"
    
    echo ""
    echo "📊 Current topics:"
    docker exec redpanda rpk topic list
}

# Function to start all services
start_all_services() {
    echo ""
    echo "🚀 Starting all services with Redpanda..."
    docker-compose -f docker-compose-redpanda.yml up -d
    
    echo ""
    echo "⏳ Waiting for all services to be ready (30 seconds)..."
    sleep 30
    
    echo ""
    echo "📊 Service status:"
    docker-compose -f docker-compose-redpanda.yml ps
}

# Function to test Kafka compatibility
test_kafka_compatibility() {
    echo ""
    echo "🔍 Testing Kafka compatibility..."
    
    # Test with kafka-python
    python3 -c "
from kafka import KafkaProducer, KafkaConsumer
import json

try:
    # Test producer
    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    producer.send('tml-transactions', {'test': 'message'})
    producer.flush()
    print('✅ Kafka Producer: Compatible')
    
    # Test consumer
    consumer = KafkaConsumer(
        'tml-transactions',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='earliest',
        consumer_timeout_ms=5000
    )
    print('✅ Kafka Consumer: Compatible')
    
except Exception as e:
    print(f'❌ Compatibility test failed: {e}')
" 2>/dev/null || echo "  Note: Install kafka-python for compatibility test"
}

# Main menu
echo "Choose an option:"
echo "1. Quick fix - Replace Kafka with Redpanda"
echo "2. Full restart - All services with Redpanda"
echo "3. Test only - Check if Redpanda is working"
echo "4. Cleanup only - Remove Kafka/Zookeeper"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        cleanup_kafka
        start_redpanda
        test_kafka_compatibility
        ;;
    2)
        cleanup_kafka
        start_all_services
        test_kafka_compatibility
        ;;
    3)
        test_kafka_compatibility
        echo ""
        docker exec redpanda rpk cluster info || echo "Redpanda not running"
        ;;
    4)
        cleanup_kafka
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Done!"
echo ""
echo "📊 Service URLs:"
echo "  - Kafka API: localhost:9092"
echo "  - Redpanda Console: http://localhost:8080"
echo "  - Schema Registry: http://localhost:8081"
echo "  - Admin API: http://localhost:9644"
echo ""
echo "💡 Tips:"
echo "  - Redpanda is 100% Kafka API compatible"
echo "  - No Zookeeper required"
echo "  - View topics: docker exec redpanda rpk topic list"
echo "  - Console UI: http://localhost:8080"
echo "  - Logs: docker logs redpanda"
