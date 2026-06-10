# TML Platform Port Configuration

## 🚀 Infrastructure Services

| Service | Port | Container | Usage | Notes |
|---------|------|-----------|-------|-------|
| **PostgreSQL** | 5432 | tml-postgres-1 | Database | Primary data store |
| **Redis** | 6379 | tml-redis-1 | Cache/State | Model state & caching |
| **Kafka (External)** | **29092** | kafka | **Python Clients** | **USE THIS PORT** |
| **Kafka (Internal)** | 9092 | kafka | Docker network | Internal only |
| **Zookeeper** | 2181 | zookeeper | Kafka coordination | Required for Kafka |

## 🎯 TML Services

| Service | Port | Type | Usage | Notes |
|---------|------|------|-------|-------|
| **TML API Server** | 8000 | Python FastAPI | Main API | Model serving & transactions |
| **TML Actor System** | 8001 | Proto.Actor | Actor metrics | Distributed processing |
| **TML Dashboard** | 8081 | Docker | Web UI | Monitoring dashboard |
| **MLflow Server** | **5003** | Python | Model registry | **NOT 5000** (ControlCenter) |
| **C# TML API** | 5001 | Docker | Legacy API | C# implementation |

## 📊 Monitoring & Metrics

| Service | Port | Container | Usage | Notes |
|---------|------|-----------|-------|-------|
| **Prometheus** | 9090 | tml-prometheus-1 | Metrics collection | Time series DB |
| **Grafana** | 3000 | tml-grafana-1 | Dashboards | Visualization |
| **MLflow (Docker)** | 5002 | tml-mlflow-1 | Model registry | **BROKEN - Use 5003** |

## ⚠️ Port Conflicts to AVOID

| Port | Service | Reason | Solution |
|------|---------|--------|----------|
| **5000** | macOS ControlCenter | AirPlay Receiver | Use 5003 for MLflow |
| **8000** | Various dev servers | Common conflict | Check before starting |
| **6379** | Other Redis instances | Default Redis port | Ensure single instance |
| **9092** | External Kafka access | Docker network only | Use 29092 instead |

## 🔧 Environment Variables

```bash
# Kafka Configuration (CRITICAL)
export KAFKA_BOOTSTRAP_SERVERS=localhost:29092

# MLflow Configuration  
export MLFLOW_TRACKING_URI=http://localhost:5003

# Actor System Configuration
export TML_ACTOR_METRICS_PORT=8001

# Database Configuration
export DATABASE_URL=postgresql://tml:tml123@localhost:5432/tml
export REDIS_URL=redis://localhost:6379
```

## 🐳 Docker Compose Port Mappings

```yaml
services:
  kafka:
    ports:
      - "9092:9092"      # Internal
      - "29092:29092"    # External (USE THIS)
  
  postgres:
    ports:
      - "5432:5432"
  
  redis:
    ports:
      - "6379:6379"
  
  tml-api:
    ports:
      - "5001:8080"      # C# API
  
  tml-dashboard:
    ports:
      - "8081:8081"      # Dashboard
```

## 🎭 Proto.Actor System Ports

| Actor Type | Port Range | Usage |
|------------|------------|-------|
| **Metrics Server** | 8001 | Prometheus metrics |
| **Cluster Communication** | 8002-8010 | Inter-node communication |
| **Health Checks** | 8001/health | Actor system health |

## 🔍 Port Verification Commands

```bash
# Check what's using ports
lsof -i :5000  # Should show ControlCenter
lsof -i :8000  # Check for conflicts
lsof -i :29092 # Should show Kafka

# Test Kafka connectivity
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092  # Internal
python -c "from kafka import KafkaProducer; KafkaProducer(bootstrap_servers=['localhost:29092'])"  # External

# Test MLflow
curl http://localhost:5003/health

# Test TML API
curl http://localhost:8000/health
```

## 🚨 UAT Port Checklist

Before starting UAT, verify:

- [ ] Port 5000 is NOT used (ControlCenter conflict)
- [ ] Kafka external port 29092 is accessible
- [ ] MLflow is on port 5003 (not 5000 or 5002)
- [ ] Actor system uses port 8001 for metrics
- [ ] No Redis conflicts on 6379
- [ ] TML API is on 8000 (check for conflicts)

## 🔄 Port Allocation Strategy

1. **Infrastructure**: 5000-6999
2. **TML Services**: 8000-8999  
3. **Monitoring**: 9000-9999
4. **Avoid**: 5000 (ControlCenter), 3000 (common dev)

This ensures clean separation and avoids common conflicts in development environments.
