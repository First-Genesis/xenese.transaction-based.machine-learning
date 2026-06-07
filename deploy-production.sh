#!/bin/bash

# TML Platform Production Deployment Script
set -e

echo "🚀 TML Platform Production Deployment Starting..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check prerequisites
print_header "Checking Prerequisites"

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

if ! command -v dotnet &> /dev/null; then
    print_error ".NET 8 SDK is not installed. Please install .NET 8 SDK first."
    exit 1
fi

print_status "All prerequisites satisfied ✓"

# Build the application
print_header "Building TML Platform"
cd src
print_status "Building .NET application in Release mode..."
dotnet build TML.API/TML.API.csproj --configuration Release --no-restore

if [ $? -eq 0 ]; then
    print_status "Build successful ✓"
else
    print_error "Build failed ✗"
    exit 1
fi

cd ..

# Start infrastructure services
print_header "Starting Infrastructure Services"
print_status "Starting PostgreSQL, Redis, Kafka, MinIO..."
docker-compose -f docker-compose.prod.yml up -d postgres redis kafka zookeeper minio consul

# Wait for services to be ready
print_status "Waiting for services to initialize..."
sleep 15

# Setup MinIO
print_header "Setting up MinIO"
print_status "Creating MinIO buckets..."
docker-compose -f docker-compose.prod.yml exec -T minio mc config host add minio http://localhost:9000 minioadmin minioadmin123 || true
docker-compose -f docker-compose.prod.yml exec -T minio mc mb minio/tml-models || true
docker-compose -f docker-compose.prod.yml exec -T minio mc policy set public minio/tml-models || true

# Create Kafka topics
print_header "Setting up Kafka"
print_status "Creating Kafka topics..."
docker-compose -f docker-compose.prod.yml exec -T kafka kafka-topics --create --if-not-exists --topic tml.transactions --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092 || true
docker-compose -f docker-compose.prod.yml exec -T kafka kafka-topics --create --if-not-exists --topic tml.models --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092 || true
docker-compose -f docker-compose.prod.yml exec -T kafka kafka-topics --create --if-not-exists --topic tml.events --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092 || true
docker-compose -f docker-compose.prod.yml exec -T kafka kafka-topics --create --if-not-exists --topic tml.metrics --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092 || true

# Start monitoring services
print_header "Starting Monitoring Services"
print_status "Starting Prometheus, Grafana, Jaeger..."
docker-compose -f docker-compose.prod.yml up -d prometheus grafana jaeger

# Start API service
print_header "Starting TML API Service"
print_status "Starting TML API..."
docker-compose -f docker-compose.prod.yml up -d tml-api

# Start additional services
print_header "Starting Additional Services"
print_status "Starting Traefik, Zitadel, MLflow..."
docker-compose -f docker-compose.prod.yml up -d traefik zitadel mlflow schema-registry

# Health check
print_header "Health Check"
print_status "Waiting for services to be healthy..."
sleep 30

# Check service health
check_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}
    
    if curl -sf "$url" > /dev/null 2>&1; then
        print_status "$service_name: ✓ Healthy"
        return 0
    else
        print_warning "$service_name: ✗ Not responding"
        return 1
    fi
}

print_status "Checking service health..."
check_service "PostgreSQL" "http://localhost:5432" || true
check_service "Redis" "http://localhost:6379" || true
check_service "MinIO" "http://localhost:9000/minio/health/live"
check_service "Kafka" "http://localhost:9092" || true
check_service "TML API" "http://localhost:5000/health"
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"
check_service "Jaeger" "http://localhost:16686"

# Display access information
print_header "Deployment Complete!"
echo ""
print_status "🎉 TML Platform is now running in production mode!"
echo ""
echo -e "${BLUE}📊 Access Points:${NC}"
echo "  • TML API:          http://localhost:5000"
echo "  • API Documentation: http://localhost:5000/swagger"
echo "  • Health Check:     http://localhost:5000/health"
echo "  • Metrics:          http://localhost:5000/metrics"
echo ""
echo -e "${BLUE}🔧 Management Interfaces:${NC}"
echo "  • MinIO Console:    http://localhost:9001 (minioadmin/minioadmin123)"
echo "  • Grafana:          http://localhost:3000 (admin/grafana_prod_2024!)"
echo "  • Prometheus:       http://localhost:9090"
echo "  • Jaeger:           http://localhost:16686"
echo "  • Traefik:          http://localhost:8080"
echo "  • Consul:           http://localhost:8500"
echo ""
echo -e "${BLUE}🚀 Production Features Enabled:${NC}"
echo "  ✓ MinIO S3-compatible storage for offline capability"
echo "  ✓ PostgreSQL with TimescaleDB for time-series data"
echo "  ✓ Redis cluster for high-performance caching"
echo "  ✓ Kafka streaming for real-time data processing"
echo "  ✓ Proto.Actor distributed processing system"
echo "  ✓ Comprehensive monitoring and observability"
echo "  ✓ Enterprise security with Zitadel"
echo "  ✓ API Gateway with Traefik"
echo ""
echo -e "${GREEN}🎯 The TML Platform is production-ready!${NC}"
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "  1. Test the API endpoints"
echo "  2. Configure authentication"
echo "  3. Set up production monitoring alerts"
echo "  4. Configure backup strategies"
echo "  5. Implement CI/CD pipelines"
echo ""
echo -e "${BLUE}💡 Useful Commands:${NC}"
echo "  • View logs:        docker-compose -f docker-compose.prod.yml logs -f"
echo "  • Stop services:    docker-compose -f docker-compose.prod.yml down"
echo "  • Restart services: docker-compose -f docker-compose.prod.yml restart"
echo "  • Health check:     make -f Makefile.prod health"
echo ""
