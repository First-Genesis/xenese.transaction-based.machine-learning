#!/bin/bash

# TML Platform Quick Start Script
# Starts all services in the correct order with proper port configuration

echo "🚀 Starting TML Platform for UAT"
echo "================================"

# Set environment variables
export KAFKA_BOOTSTRAP_SERVERS=localhost:29092
export MLFLOW_TRACKING_URI=http://localhost:5003
export PYTHONPATH=/Users/rwattyfirstgenesis.com/TML
export TML_ACTOR_METRICS_PORT=8001

echo "✅ Environment variables set"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please create it first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate
echo "✅ Python environment activated"

# Step 1: Start Infrastructure
echo ""
echo "📦 Step 1: Starting Infrastructure Services..."
docker-compose up -d postgres redis kafka zookeeper
sleep 10
echo "✅ Infrastructure started"

# Step 2: Check Kafka is ready
echo ""
echo "🔌 Step 2: Verifying Kafka..."
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
echo "✅ Kafka verified"

# Step 3: Start MLflow
echo ""
echo "🧪 Step 3: Starting MLflow on port 5003..."
mlflow server \
    --backend-store-uri postgresql://tml:tml123@localhost:5432/mlflow \
    --default-artifact-root ./mlruns \
    --host 0.0.0.0 \
    --port 5003 &
MLFLOW_PID=$!
echo "✅ MLflow started (PID: $MLFLOW_PID)"
sleep 5

# Step 4: Start TML API Server
echo ""
echo "🌐 Step 4: Starting TML API Server..."
python -m uvicorn tml.serving.api_server:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "✅ API Server started (PID: $API_PID)"
sleep 3

# Step 5: Start Kafka Consumer
echo ""
echo "📡 Step 5: Starting Stream Processor..."
python -m tml.ingestion.kafka_consumer &
CONSUMER_PID=$!
echo "✅ Stream Processor started (PID: $CONSUMER_PID)"
sleep 2

# Step 6: Start Model Trainer
echo ""
echo "🤖 Step 6: Starting Model Trainer Service..."
python -m tml.core.model_trainer_service &
TRAINER_PID=$!
echo "✅ Model Trainer started (PID: $TRAINER_PID)"
sleep 2

# Step 7: Optional - Start Actor System
echo ""
echo "🎭 Step 7: Proto.Actor System (Optional)"
echo "To start Actor-based processing, run:"
echo "  python tml_actor_trainer_service.py"
echo ""

# Step 8: Verify all services
echo "================================"
echo "🔍 Verifying All Services..."
sleep 3

# Check ports
python check_ports.py

echo ""
echo "================================"
echo "✅ TML Platform Started Successfully!"
echo ""
echo "📊 Access Points:"
echo "  • API Server: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • MLflow UI: http://localhost:5003"
echo "  • Dashboard: http://localhost:8081"
echo "  • Prometheus: http://localhost:9090"
echo ""
echo "🛑 To stop all services:"
echo "  • Press Ctrl+C to stop Python services"
echo "  • Run: docker-compose down"
echo ""
echo "📝 Process IDs:"
echo "  • MLflow: $MLFLOW_PID"
echo "  • API Server: $API_PID"
echo "  • Stream Processor: $CONSUMER_PID"
echo "  • Model Trainer: $TRAINER_PID"
echo ""
echo "💡 Tip: Run 'python check_ports.py' to verify configuration"

# Wait for interrupt
wait
