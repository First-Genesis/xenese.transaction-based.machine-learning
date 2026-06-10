# 🏗️ TML Full-Stack Integrated Dashboard

## Overview

Complete enterprise dashboard integrating with the full TML platform infrastructure, providing real-time monitoring and control of all advanced AI/ML capabilities with live data streams.

## Architecture

### 🏗️ Infrastructure Integration

The full-stack dashboard connects to the complete TML ecosystem:

```
┌─────────────────────────────────────────────────────────────┐
│                    TML Full-Stack Dashboard                 │
├─────────────────────────────────────────────────────────────┤
│  🖥️  Streamlit Frontend with Real-Time Updates             │
├─────────────────────────────────────────────────────────────┤
│  🔌 Infrastructure Connectors                              │
│  ├── PostgreSQL (Models & Transactions)                    │
│  ├── Redis (Cache & Sessions)                              │
│  ├── Kafka (Real-Time Streams)                             │
│  ├── Proto.Actor (Distributed Processing)                  │
│  ├── MLflow (Model Registry)                               │
│  └── Prometheus (Metrics & Monitoring)                     │
├─────────────────────────────────────────────────────────────┤
│  🧠 Advanced AI/ML Features                                │
│  ├── Enhanced Spatial Inheritance                          │
│  ├── Hyperparameter Optimization                           │
│  ├── Real-Time Model Explainability                        │
│  ├── Advanced Drift Detection                              │
│  └── Federated Learning                                    │
└─────────────────────────────────────────────────────────────┘
```

## Features

### 🏠 System Overview
- **Real-Time Infrastructure Status**: Live monitoring of all services
- **Transaction Stream**: Live Kafka transaction data display
- **Performance Metrics**: Real-time system performance indicators
- **Health Dashboard**: Comprehensive system health monitoring

### 🏗️ Infrastructure Monitoring
- **Service Health Matrix**: Status of all infrastructure components
- **Database Statistics**: Live PostgreSQL performance metrics
- **Cache Performance**: Redis hit rates and memory usage
- **Message Queue Status**: Kafka topic and partition monitoring
- **Actor System Health**: Proto.Actor cluster status and metrics

### 🧠 Integrated AI Features
- **Live Data Integration**: AI features connected to real infrastructure
- **Database-Backed Models**: Spatial inheritance using real model data
- **MLflow Integration**: Hyperparameter optimization with experiment tracking
- **Real-Time Explanations**: Model explainability with live model data
- **Stream-Based Drift Detection**: Drift detection using live Kafka streams
- **Distributed Federation**: Federated learning across real infrastructure

### 📊 Real-Time Analytics
- **Live Data Streams**: Real-time visualization of Kafka data
- **Performance Dashboards**: System-wide performance monitoring
- **Alert Management**: Real-time alerts and notifications
- **Trend Analysis**: Historical data analysis and forecasting

### 🔧 System Administration
- **Service Control**: Start/stop infrastructure services
- **Configuration Management**: Runtime configuration updates
- **User Management**: Access control and permissions
- **Maintenance Tools**: System maintenance and diagnostics

## Quick Start

### 1. Infrastructure Setup

#### Option A: Full Infrastructure Startup
```bash
# Start all TML infrastructure services
python start_tml_infrastructure.py

# This will start:
# - Docker services (PostgreSQL, Redis, Kafka)
# - MLflow server
# - Proto.Actor system
```

#### Option B: Manual Service Startup
```bash
# Start Docker services
docker-compose up -d postgres redis kafka zookeeper

# Start MLflow server
mlflow server --host 0.0.0.0 --port 5003

# Start Proto.Actor system
python run_actor_bridge.py
```

### 2. Launch Full-Stack Dashboard
```bash
# Launch with infrastructure checking
python launch_full_stack_dashboard.py

# Dashboard will be available at:
# http://localhost:8505
```

### 3. Access Dashboard
- **URL**: http://localhost:8505
- **Auto-Infrastructure Check**: Validates all services on startup
- **Graceful Degradation**: Works with partial infrastructure
- **Real-Time Updates**: Configurable refresh rates

## Infrastructure Requirements

### Required Services
| Service | Port | Purpose | Status Check |
|---------|------|---------|--------------|
| **PostgreSQL** | 5432 | Models & transaction storage | Connection test |
| **Redis** | 6379 | Caching & session management | Ping command |
| **Kafka** | 29092 | Real-time data streams | Producer connection |

### Optional Services
| Service | Port | Purpose | Fallback |
|---------|------|---------|----------|
| **Proto.Actor** | 8001 | Distributed processing | Simulated metrics |
| **MLflow** | 5003 | Model registry & tracking | Local experiments |
| **Prometheus** | 9090 | System monitoring | Basic health checks |

## Dashboard Views

### 🏠 System Overview
```
┌─────────────────────────────────────────────────────────┐
│  Infrastructure Status    │  Real-Time Metrics          │
│  ┌─────────────────────┐  │  ┌─────────────────────────┐ │
│  │ 🟢 PostgreSQL       │  │  │ Transactions: 1,247     │ │
│  │ 🟢 Redis            │  │  │ Active Models: 15       │ │
│  │ 🟢 Kafka            │  │  │ Cache Hit Rate: 94.2%   │ │
│  │ 🔴 Proto.Actor      │  │  └─────────────────────────┘ │
│  │ 🟢 MLflow           │  │                              │
│  │ 🟢 Prometheus       │  │  Live Transaction Stream     │
│  └─────────────────────┘  │  ┌─────────────────────────┐ │
│                            │  │ 15:42:33 | TX_001 | $50 │ │
│                            │  │ 15:42:34 | TX_002 | $25 │ │
│                            │  │ 15:42:35 | TX_003 | $75 │ │
│                            │  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 🧠 Integrated AI Features
```
┌─────────────────────────────────────────────────────────┐
│  🧠 Spatial Inheritance  │  ⚙️ Hyperparameter Opt      │
│  ┌─────────────────────┐  │  ┌─────────────────────────┐ │
│  │ Real Models from DB │  │  │ MLflow Integration      │ │
│  │ Live Inheritance    │  │  │ Live Optimization       │ │
│  └─────────────────────┘  │  └─────────────────────────┘ │
│                            │                              │
│  🔍 Model Explainability  │  📊 Drift Detection         │
│  ┌─────────────────────┐  │  ┌─────────────────────────┐ │
│  │ Real Model Data     │  │  │ Live Stream Analysis    │ │
│  │ Live Explanations   │  │  │ Statistical Testing     │ │
│  └─────────────────────┘  │  └─────────────────────────┘ │
│                            │                              │
│  🌐 Federated Learning                                   │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Distributed Infrastructure Integration              │ │
│  │ Real Node Coordination                              │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Real-Time Features

### 🔄 Live Data Integration
- **PostgreSQL Queries**: Real-time model and transaction data
- **Redis Monitoring**: Cache performance and session data
- **Kafka Streams**: Live transaction and event processing
- **Actor Metrics**: Distributed processing performance
- **MLflow Tracking**: Live experiment and model tracking

### 📊 Dynamic Visualizations
- **Interactive Charts**: Plotly-based real-time visualizations
- **Live Updates**: Configurable refresh rates (1-30 seconds)
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Professional Styling**: Enterprise-grade UI with custom CSS

### 🚨 Alert System
- **Infrastructure Alerts**: Service availability notifications
- **Performance Alerts**: Threshold-based performance warnings
- **AI Feature Alerts**: Model drift and performance degradation
- **Real-Time Notifications**: Instant alert display and management

## Configuration

### Environment Variables
```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=tml_platform
POSTGRES_USER=tml_user
POSTGRES_PASSWORD=tml_password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:29092

# MLflow Configuration
MLFLOW_TRACKING_URI=http://localhost:5003

# Actor System Configuration
ACTOR_METRICS_PORT=8001

# Prometheus Configuration
PROMETHEUS_URL=http://localhost:9090
```

### Dashboard Settings
```python
# Real-time update configuration
REFRESH_RATE_SECONDS = 5
MAX_TRANSACTION_DISPLAY = 10
CACHE_TTL_SECONDS = 30

# Infrastructure timeouts
CONNECTION_TIMEOUT = 3
HEALTH_CHECK_TIMEOUT = 5
QUERY_TIMEOUT = 10
```

## Performance Characteristics

### Resource Usage
- **Memory**: 300-800 MB (depending on data volume)
- **CPU**: Low impact with efficient caching
- **Network**: Minimal bandwidth for real-time updates
- **Storage**: Temporary caching only

### Scalability
- **Concurrent Users**: Supports multiple simultaneous users
- **Data Volume**: Handles high-volume transaction streams
- **Service Load**: Minimal impact on infrastructure services
- **Response Time**: <2 seconds for most operations

## Troubleshooting

### Common Issues

#### Infrastructure Connection Failures
```bash
# Check service status
docker-compose ps

# Restart specific service
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

#### Dashboard Performance Issues
```bash
# Check Python process
ps aux | grep streamlit

# Monitor resource usage
top -p $(pgrep -f streamlit)

# Clear cache
rm -rf ~/.streamlit/cache/
```

#### Real-Time Data Issues
```bash
# Test Kafka connection
kafka-console-consumer --bootstrap-server localhost:29092 --topic tml-transactions

# Test Redis connection
redis-cli ping

# Test PostgreSQL connection
psql -h localhost -U tml_user -d tml_platform -c "SELECT 1;"
```

## Development

### Adding New Features
1. **Infrastructure Integration**: Add new service connectors
2. **AI Feature Integration**: Connect new AI capabilities
3. **Visualization**: Create new dashboard components
4. **Real-Time Updates**: Implement live data streams

### Testing
```bash
# Test infrastructure connections
python -c "from tml.ui.full_stack_dashboard import TMLInfrastructureConnector; TMLInfrastructureConnector()"

# Test dashboard components
streamlit run tml/ui/full_stack_dashboard.py --server.port=8506

# Load testing
# Use tools like Apache Bench or Locust for load testing
```

## Security Considerations

### Access Control
- **Network Security**: Restrict access to infrastructure ports
- **Authentication**: Implement user authentication for production
- **Authorization**: Role-based access control for different features
- **Data Privacy**: Ensure sensitive data is properly protected

### Infrastructure Security
- **Database Security**: Use strong passwords and encrypted connections
- **Message Queue Security**: Implement Kafka security features
- **Cache Security**: Secure Redis with authentication
- **Monitoring Security**: Protect metrics and monitoring endpoints

## Production Deployment

### Recommended Setup
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  tml-dashboard:
    build: .
    ports:
      - "8505:8505"
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - postgres
      - redis
      - kafka
    restart: unless-stopped
```

### Monitoring
- **Health Checks**: Implement comprehensive health checking
- **Logging**: Structured logging for troubleshooting
- **Metrics**: Export dashboard metrics to monitoring systems
- **Alerting**: Set up alerts for dashboard availability

## Future Enhancements

### Planned Features
- **Multi-Tenant Support**: Support for multiple organizations
- **Advanced Analytics**: Machine learning on dashboard usage
- **Mobile App**: Native mobile application
- **API Gateway**: REST API for programmatic access
- **Custom Widgets**: User-configurable dashboard components

### Integration Roadmap
- **Kubernetes**: Native Kubernetes deployment
- **Cloud Services**: AWS/Azure/GCP integration
- **Advanced Security**: OAuth2/SAML integration
- **Data Lakes**: Integration with data lake platforms
- **Edge Computing**: Edge device monitoring and control

## Support

For issues with the full-stack dashboard:

1. **Check Infrastructure**: Verify all required services are running
2. **Review Logs**: Check dashboard and service logs for errors
3. **Test Connections**: Validate infrastructure connectivity
4. **Resource Monitoring**: Ensure adequate system resources
5. **Configuration**: Verify all configuration parameters

The full-stack dashboard represents the complete integration of TML's advanced AI/ML capabilities with enterprise-grade infrastructure, providing a comprehensive platform for real-time AI operations and monitoring.
