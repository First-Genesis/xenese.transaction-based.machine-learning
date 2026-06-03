# Getting Started with TML Platform

This guide will help you get the Transaction-based Machine Learning (TML) Platform up and running.

## Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Git

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd TML
```

### 2. Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration as needed
nano .env
```

### 4. Start Infrastructure

```bash
# Start all infrastructure services
make start-infra

# Or manually with Docker Compose
docker-compose -f docker/docker-compose.yml up -d
```

### 5. Start TML Platform

```bash
# Start the platform with all components
python scripts/start_platform.py start --with-infra --with-kafka

# Or start individual components
python scripts/start_platform.py start  # API server only
```

### 6. Verify Installation

```bash
# Check platform status
python scripts/start_platform.py status

# Run basic examples
python examples/basic_usage.py
```

## Architecture Overview

The TML platform consists of several key components:

### Core Components

1. **Transaction Models** (`tml.core.model`)
   - Individual models that learn incrementally
   - Each transaction spawns its own specialized model
   - Models inherit knowledge from parent models

2. **Online Learning Engine** (`tml.learning`)
   - Supports River and Vowpal Wabbit algorithms
   - Handles millions of concurrent models
   - Implements continual learning techniques

3. **Model Registry** (`tml.core.registry`)
   - Hot storage in Redis for active models
   - Cold storage in Cassandra for archived models
   - MLflow integration for experiment tracking

### Data Pipeline

4. **Kafka Ingestion** (`tml.ingestion`)
   - High-throughput transaction streaming
   - Schema registry for data contracts
   - Stateful stream processing with Flink

5. **Feature Store** (`tml.features`)
   - Feast-based feature management
   - Real-time and batch feature serving
   - Feature lineage and versioning

### Serving & Monitoring

6. **API Server** (`tml.serving`)
   - FastAPI-based REST API
   - Real-time predictions and learning
   - Batch processing capabilities

7. **Monitoring** (`tml.monitoring`)
   - Prometheus metrics collection
   - Grafana dashboards
   - Drift detection and alerting

## Basic Usage Examples

### Making Predictions

```python
from tml.core.model import TransactionContext, ModelFactory

# Create a transaction context
context = TransactionContext(
    transaction_id="demo_001",
    user_id="user_123"
)

# Create a model
model = ModelFactory.create_model(context)

# Make a prediction
features = {
    "amount": 150.0,
    "category": "electronics",
    "hour_of_day": 14
}

prediction = model.predict(features)
print(f"Prediction: {prediction}")
```

### Online Learning

```python
from tml.learning.online_learner import learning_engine
from tml.ingestion.kafka_producer import TransactionEvent

# Create a transaction event
event = TransactionEvent(
    transaction_id="learn_001",
    user_id="user_123",
    event_type="purchase",
    features={"amount": 100.0, "category": "books"},
    target=True  # Positive outcome
)

# Process with online learning
result = await learning_engine.process_transaction(event)
print(f"Model updated: {result.update_applied}")
```

### Using the API

```python
import aiohttp
import asyncio

async def api_example():
    async with aiohttp.ClientSession() as session:
        # Make a prediction
        async with session.post('http://localhost:8000/predict', json={
            "features": {"amount": 150.0, "category": "electronics"},
            "user_id": "user_123",
            "return_probabilities": True
        }) as response:
            result = await response.json()
            print(f"Prediction: {result['prediction']}")

asyncio.run(api_example())
```

## Key Features

### 1. Incremental Learning
- Each model learns continuously from new data
- No need for batch retraining
- Supports concept drift detection

### 2. Model Inheritance
- New models inherit knowledge from parent models
- Prevents cold start problems
- Maintains model lineage

### 3. Scalability
- Handles millions of concurrent models
- Efficient model storage and retrieval
- Horizontal scaling with Kubernetes

### 4. Fault Tolerance
- Checkpointing and recovery
- Graceful degradation
- Circuit breaker patterns

## Configuration

### Environment Variables

Key configuration options:

```bash
# Environment
TML_ENVIRONMENT=development
TML_DEBUG=true
TML_LOG_LEVEL=INFO

# Redis (Hot Storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis123

# Kafka (Streaming)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TRANSACTION_TOPIC=transactions

# Model Configuration
MODEL_BASE_TYPE=river
MODEL_MAX_IN_MEMORY=10000
MODEL_DRIFT_THRESHOLD=0.1
```

### Advanced Configuration

For production deployments, see:
- [Production Deployment Guide](deployment.md)
- [Scaling Guide](scaling.md)
- [Security Configuration](security.md)

## Monitoring and Observability

### Dashboards

Access monitoring dashboards:

- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Kafka UI**: http://localhost:8080
- **MLflow**: http://localhost:5000

### Metrics

Key metrics to monitor:

- **Prediction Latency**: Time to make predictions
- **Learning Rate**: Model update frequency
- **Drift Score**: Concept drift detection
- **Accuracy**: Model performance over time
- **Throughput**: Transactions processed per second

### Alerts

Configure alerts for:

- High error rates (>5%)
- Slow predictions (>1 second)
- Concept drift detection
- Low model accuracy (<70%)

## Development

### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
pytest tests/test_core.py -v
pytest tests/integration/ -v
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Type checking
mypy tml/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks
5. Submit a pull request

## Troubleshooting

### Common Issues

**1. Infrastructure not starting**
```bash
# Check Docker status
docker ps

# View logs
docker-compose -f docker/docker-compose.yml logs
```

**2. API server connection errors**
```bash
# Check if services are running
python scripts/start_platform.py status

# Check API health
curl http://localhost:8000/health
```

**3. Memory issues with many models**
```bash
# Adjust model cache size
export MODEL_MAX_IN_MEMORY=5000

# Enable model compression
export MODEL_COMPRESSION_ENABLED=true
```

### Getting Help

- Check the [FAQ](faq.md)
- Review [API Documentation](api.md)
- Open an issue on GitHub
- Join our community Slack

## Next Steps

- Explore [Advanced Features](advanced_features.md)
- Learn about [Model Optimization](optimization.md)
- Set up [Production Deployment](deployment.md)
- Integrate with your [Data Pipeline](integration.md)
