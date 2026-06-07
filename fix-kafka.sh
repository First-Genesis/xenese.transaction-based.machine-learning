#!/bin/bash

echo "🔧 Fixing Kafka Issues in Docker"
echo "================================="
echo ""

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker Desktop first."
        exit 1
    fi
    echo "✅ Docker is running"
}

# Function to clean up existing containers
cleanup() {
    echo ""
    echo "🧹 Cleaning up existing Kafka containers and volumes..."
    
    # Stop containers
    docker-compose down 2>/dev/null || true
    docker stop tml-kafka tml-zookeeper 2>/dev/null || true
    docker rm tml-kafka tml-zookeeper 2>/dev/null || true
    
    # Remove problematic volumes
    docker volume rm tml_kafka_data tml_zookeeper_data 2>/dev/null || true
    
    echo "✅ Cleanup complete"
}

# Function to check port availability
check_ports() {
    echo ""
    echo "🔍 Checking port availability..."
    
    ports=(2181 9092 29092)
    all_clear=true
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "❌ Port $port is already in use"
            all_clear=false
        else
            echo "✅ Port $port is available"
        fi
    done
    
    if [ "$all_clear" = false ]; then
        echo ""
        echo "⚠️  Some ports are in use. You can:"
        echo "1. Stop the services using these ports"
        echo "2. Or modify the port mappings in docker-compose.yml"
        exit 1
    fi
}

# Function to start services with proper order
start_services() {
    echo ""
    echo "🚀 Starting services in correct order..."
    
    # Use the fixed docker-compose file
    if [ -f "docker-compose-fixed.yml" ]; then
        echo "Using docker-compose-fixed.yml"
        
        # Start Zookeeper first
        echo "Starting Zookeeper..."
        docker-compose -f docker-compose-fixed.yml up -d zookeeper
        
        # Wait for Zookeeper to be healthy
        echo "Waiting for Zookeeper to be ready..."
        for i in {1..30}; do
            if docker exec tml-zookeeper bash -c "echo 'ruok' | nc localhost 2181 | grep imok" > /dev/null 2>&1; then
                echo "✅ Zookeeper is ready"
                break
            fi
            echo -n "."
            sleep 2
        done
        
        # Start Kafka
        echo "Starting Kafka..."
        docker-compose -f docker-compose-fixed.yml up -d kafka
        
        # Wait for Kafka to be ready
        echo "Waiting for Kafka to be ready..."
        for i in {1..30}; do
            if docker exec tml-kafka kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; then
                echo "✅ Kafka is ready"
                break
            fi
            echo -n "."
            sleep 2
        done
        
        # Start other services
        echo "Starting remaining services..."
        docker-compose -f docker-compose-fixed.yml up -d
        
    else
        echo "❌ docker-compose-fixed.yml not found"
        exit 1
    fi
}

# Function to verify Kafka is working
verify_kafka() {
    echo ""
    echo "🔍 Verifying Kafka functionality..."
    
    # Create a test topic
    docker exec tml-kafka kafka-topics \
        --bootstrap-server localhost:9092 \
        --create \
        --topic test-topic \
        --partitions 1 \
        --replication-factor 1 \
        2>/dev/null || true
    
    # List topics
    echo "Kafka topics:"
    docker exec tml-kafka kafka-topics \
        --bootstrap-server localhost:9092 \
        --list
    
    echo ""
    echo "✅ Kafka is working correctly!"
}

# Function to show logs
show_logs() {
    echo ""
    echo "📋 Recent logs from Kafka:"
    docker logs --tail 20 tml-kafka 2>&1 | grep -v "INFO"
    
    echo ""
    echo "📋 Recent logs from Zookeeper:"
    docker logs --tail 20 tml-zookeeper 2>&1 | grep -v "INFO"
}

# Main execution
main() {
    echo "This script will fix common Kafka issues in Docker"
    echo ""
    
    check_docker
    
    read -p "Do you want to clean up existing containers? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup
    fi
    
    check_ports
    start_services
    
    echo ""
    echo "⏳ Waiting for services to stabilize..."
    sleep 10
    
    verify_kafka
    
    echo ""
    echo "🎉 Success! Kafka is now running properly."
    echo ""
    echo "📊 Service URLs:"
    echo "  - Kafka: localhost:9092 (external), kafka:9092 (internal)"
    echo "  - Kafka UI: http://localhost:8082"
    echo "  - Zookeeper: localhost:2181"
    echo ""
    echo "💡 Tips:"
    echo "  - View all logs: docker-compose -f docker-compose-fixed.yml logs -f"
    echo "  - View Kafka logs: docker logs -f tml-kafka"
    echo "  - Access Kafka UI: http://localhost:8082"
    echo "  - Stop all services: docker-compose -f docker-compose-fixed.yml down"
    
    read -p "Do you want to see recent logs? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_logs
    fi
}

# Run main function
main
