# 🧠 Transaction-based Machine Learning (TML) Platform v2.0

[![CI/CD](https://github.com/First-Genesis/xenese.transaction-based.machine-learning/workflows/CI/badge.svg)](https://github.com/First-Genesis/xenese.transaction-based.machine-learning/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Physics-Informed](https://img.shields.io/badge/physics--informed-ML-green.svg)](https://en.wikipedia.org/wiki/Physics-informed_neural_networks)

A revolutionary machine learning platform where **every transaction spawns its own model** that inherits knowledge from predecessors while remaining independently tunable. Model #1,000,000 is exponentially smarter than Model #1 through continuous knowledge inheritance.

## 🚀 Enhanced Architecture v2.0

**Multi-Layer Intelligence Stack:**
- **Kafka**: High-throughput telemetry transport
- **Flink**: Real-time distributed compute engine  
- **Proto.Actor**: Stateful orchestration system
- **Physics Models**: Engineering equation validation
- **Enhanced AI/ML**: Multi-algorithm predictive inference

## 🎯 Core Innovation

**Traditional ML**: One model serves all users → Poor personalization, catastrophic forgetting
**TML Platform**: One model per transaction → Infinite personalization, knowledge accumulation

```
Transaction 1 → Model_1 (Base knowledge)
Transaction 2 → Model_2 (Inherits Model_1 + learns new patterns)
Transaction 3 → Model_3 (Inherits Model_2 + specializes further)
...
Transaction 1M → Model_1M (Inherits 999,999 models of wisdom)
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)
```bash
git clone https://github.com/First-Genesis/xenese.transaction-based.machine-learning.git && cd transaction-based.machine-learning
docker-compose up -d
open http://localhost:8081  # Access demo hub
```

### Option 2: Local Development
```bash
git clone https://github.com/First-Genesis/xenese.transaction-based.machine-learning.git && cd transaction-based.machine-learning
make setup
make start
open http://localhost:8081  # Access demo hub
```

### Option 3: Production Deployment
```bash
git clone https://github.com/First-Genesis/xenese.transaction-based.machine-learning.git && cd transaction-based.machine-learning
make deploy-k8s  # Kubernetes deployment
```

## Core Concept

- **Model #1,000,000 > Model #1**: Each model inherits accumulated knowledge
- **Independent Tuning**: Per-transaction context specialization  
- **Incremental Learning**: No retraining from scratch
- **Scalable Architecture**: Handles millions of concurrent models

## Architecture Overview

```
Transactions → Kafka → Flink (stateful processing)
                           ↓
                    Feature Store (Feast)
                           ↓
              Online Learning Engine (River / VW)
                    ↙              ↘
        Model State (Redis)    Model Archive (Cassandra)
                           ↓
              Model Registry (MLflow)
                           ↓
         Serving Layer (Ray Serve / KServing)
                           ↓
              Monitoring (Evidently + Arize)
```

## Technology Stack

### Data Ingestion & Streaming
- **Apache Kafka**: High-throughput transaction event streaming
- **Apache Flink**: Stateful stream processing for per-model state
- **Confluent Schema Registry**: Data contract enforcement

### Online Learning Framework
- **River**: Purpose-built Python online ML framework
- **Vowpal Wabbit**: Battle-tested online learning at scale
- **scikit-multiflow**: Concept drift detection

### Model Storage & Registry
- **MLflow**: Model lineage and metadata tracking
- **Redis + RedisAI**: Ultra-low latency model state storage
- **Apache Cassandra**: Distributed model parameter storage
- **Delta Lake**: Versioned model snapshots

### Feature Store
- **Feast**: Open-source feature store for shared intelligence

### Compute & Orchestration
- **Kubernetes + KServing**: Container orchestration
- **Ray**: Distributed Python framework with Ray Serve
- **Apache Spark**: Bulk feature computation

### Model Serving & Inference
- **Triton Inference Server**: High-performance serving
- **BentoML**: Lightweight per-entity model packaging
- **gRPC + Protocol Buffers**: Low-latency communication

### Monitoring & Drift Detection
- **Evidently AI**: Data and model drift monitoring
- **Prometheus + Grafana**: Infrastructure metrics

## Project Structure

```
tml/
├── ingestion/          # Kafka + Flink data pipeline
├── learning/           # Online learning engines
├── storage/            # Model storage and registry
├── features/           # Feature store implementation
├── serving/            # Model serving infrastructure
├── monitoring/         # Drift detection and observability
├── orchestration/      # Kubernetes manifests and deployment
├── config/             # Configuration management
├── tests/              # Test suites
└── docs/               # Documentation
```

## Quick Start

1. **Environment Setup**:
   ```bash
   make setup-env
   ```

2. **Start Infrastructure**:
   ```bash
   make start-infra
   ```

3. **Deploy Platform**:
   ```bash
   make deploy
   ```

4. **Run Tests**:
   ```bash
   make test
   ```

## Key Design Solutions

| Challenge | Solution |
|-----------|----------|
| 1M models in memory | Model compression + lazy loading from Redis |
| Catastrophic forgetting | Elastic Weight Consolidation (EWC) |
| Concept drift | Per-model drift scores + auto re-initialization |
| Cold start | Transfer learning from global base model |
| Auditability | Immutable model snapshots in Delta Lake |

## Development

See [Development Guide](docs/development.md) for detailed setup and contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
