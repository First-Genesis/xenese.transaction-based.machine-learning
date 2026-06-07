# 🚀 TML Platform Production Deployment Guide

This guide covers production deployment of the TML Platform with enterprise-grade configurations, monitoring, and scaling capabilities.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Database Configuration](#database-configuration)
4. [Container Deployment](#container-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Load Balancing](#load-balancing)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Monitoring Setup](#monitoring-setup)
9. [Backup and Recovery](#backup-and-recovery)
10. [Health Checks](#health-checks)

---

## Prerequisites

### System Requirements
- **CPU**: 16+ cores per node (recommended 32+ for high throughput)
- **Memory**: 64GB+ RAM per node (128GB+ recommended)
- **Storage**: NVMe SSD with 10,000+ IOPS
- **Network**: 10Gbps+ network connectivity
- **OS**: Ubuntu 20.04 LTS or RHEL 8+

### Software Dependencies
- **Docker**: 20.10+
- **Kubernetes**: 1.24+
- **PostgreSQL**: 14+
- **Redis**: 6.2+
- **.NET**: 8.0+
- **Python**: 3.9+

---

## Infrastructure Setup

### 1. Production Environment Variables

Create production environment configuration:

```bash
# /opt/tml/config/production.env

# Environment
TML_ENVIRONMENT=production
TML_DEBUG=false
TML_LOG_LEVEL=INFO

# Database Configuration
DATABASE_HOST=tml-postgres-primary.internal
DATABASE_PORT=5432
DATABASE_NAME=tml_production
DATABASE_USER=tml_app
DATABASE_PASSWORD=${DATABASE_PASSWORD}
DATABASE_SSL_MODE=require
DATABASE_MAX_CONNECTIONS=100

# Redis Configuration
REDIS_HOST=tml-redis-cluster.internal
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_SSL=true
REDIS_MAX_CONNECTIONS=1000

# API Configuration
API_HOST=0.0.0.0
API_PORT=5000
API_WORKERS=8
API_MAX_REQUESTS=10000
API_TIMEOUT=30

# Proto.Actor Configuration
ACTOR_SYSTEM_NAME=TMLProductionSystem
ACTOR_CLUSTER_ENABLED=true
ACTOR_CLUSTER_SEED_NODES=tml-actor-1:8080,tml-actor-2:8080,tml-actor-3:8080
TRANSACTION_PROCESSOR_COUNT=10
MODEL_ACTOR_COUNT=20
PHYSICS_VALIDATOR_COUNT=5

# Performance Tuning
MODEL_CACHE_SIZE=50000
DRIFT_DETECTION_BATCH_SIZE=1000
PROCESSING_TIMEOUT=5000
MAX_CONCURRENT_REQUESTS=5000

# Security
JWT_SECRET_KEY=${JWT_SECRET_KEY}
API_KEY_REQUIRED=true
CORS_ORIGINS=https://tml-dashboard.company.com
RATE_LIMIT_PER_MINUTE=1000

# Monitoring
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
GRAFANA_ENABLED=true
HEALTH_CHECK_INTERVAL=30
```

### 2. Directory Structure

```bash
/opt/tml/
├── config/
│   ├── production.env
│   ├── database.conf
│   ├── redis.conf
│   └── nginx.conf
├── data/
│   ├── postgres/
│   ├── redis/
│   └── logs/
├── ssl/
│   ├── tml.crt
│   ├── tml.key
│   └── ca.crt
├── scripts/
│   ├── deploy.sh
│   ├── backup.sh
│   └── health-check.sh
└── docker/
    ├── docker-compose.prod.yml
    └── Dockerfile.prod
```

---

## Database Configuration

### PostgreSQL Production Setup

```yaml
# docker-compose.prod.yml - PostgreSQL Configuration
version: '3.8'

services:
  postgres-primary:
    image: postgres:14
    container_name: tml-postgres-primary
    environment:
      POSTGRES_DB: tml_production
      POSTGRES_USER: tml_app
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_INITDB_ARGS: "--auth-host=md5"
    volumes:
      - /opt/tml/data/postgres:/var/lib/postgresql/data
      - ./config/postgresql.conf:/etc/postgresql/postgresql.conf
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    ports:
      - "5432:5432"
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 32G
          cpus: '8'
        reservations:
          memory: 16G
          cpus: '4'

  postgres-replica:
    image: postgres:14
    container_name: tml-postgres-replica
    environment:
      POSTGRES_DB: tml_production
      POSTGRES_USER: tml_app
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      PGUSER: postgres
    volumes:
      - /opt/tml/data/postgres-replica:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    depends_on:
      - postgres-primary
    restart: unless-stopped
```

### Database Initialization Script

```sql
-- scripts/init-db.sql
-- Create optimized indexes for production
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_models_status_created 
ON models (status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_models_parent_id 
ON models (parent_model_id) WHERE parent_model_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_drift_detection_model_time 
ON drift_detection (model_id, detected_at DESC);

-- Create partitioned tables for large datasets
CREATE TABLE model_performance_partitioned (
    LIKE model_performance INCLUDING ALL
) PARTITION BY RANGE (recorded_at);

-- Create monthly partitions
CREATE TABLE model_performance_2024_01 PARTITION OF model_performance_partitioned
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Enable connection pooling
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '8GB';
ALTER SYSTEM SET effective_cache_size = '24GB';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '2GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET default_statistics_target = 100;

SELECT pg_reload_conf();
```

---

## Container Deployment

### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # TML API Backend
  tml-api:
    build:
      context: .
      dockerfile: Dockerfile.api.prod
    container_name: tml-api
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
      - ASPNETCORE_URLS=http://+:5000
    env_file:
      - ./config/production.env
    ports:
      - "5000:5000"
    volumes:
      - /opt/tml/logs:/app/logs
    depends_on:
      - postgres-primary
      - redis-cluster
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G
          cpus: '1'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # TML Python Demo
  tml-demo:
    build:
      context: .
      dockerfile: Dockerfile.python.prod
    container_name: tml-demo
    environment:
      - STREAMLIT_SERVER_PORT=8081
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
    env_file:
      - ./config/production.env
    ports:
      - "8081:8081"
    volumes:
      - /opt/tml/logs:/app/logs
    depends_on:
      - tml-api
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1'
        reservations:
          memory: 1G
          cpus: '0.5'

  # Redis Cluster
  redis-cluster:
    image: redis:7-alpine
    container_name: tml-redis-cluster
    command: redis-server --appendonly yes --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000
    ports:
      - "6379:6379"
    volumes:
      - /opt/tml/data/redis:/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '2'
        reservations:
          memory: 4G
          cpus: '1'

  # Nginx Load Balancer
  nginx:
    image: nginx:alpine
    container_name: tml-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
      - /opt/tml/logs/nginx:/var/log/nginx
    depends_on:
      - tml-api
      - tml-demo
    restart: unless-stopped

  # Prometheus Monitoring
  prometheus:
    image: prom/prometheus:latest
    container_name: tml-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - /opt/tml/data/prometheus:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  # Grafana Dashboard
  grafana:
    image: grafana/grafana:latest
    container_name: tml-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - /opt/tml/data/grafana:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning
    restart: unless-stopped

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
```

### Production Dockerfiles

```dockerfile
# Dockerfile.api.prod
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app
EXPOSE 5000

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["src/TML.API/TML.API.csproj", "src/TML.API/"]
COPY ["src/TML.Actors/TML.Actors.csproj", "src/TML.Actors/"]
COPY ["src/TML.Storage/TML.Storage.csproj", "src/TML.Storage/"]
RUN dotnet restore "src/TML.API/TML.API.csproj"

COPY . .
WORKDIR "/src/src/TML.API"
RUN dotnet build "TML.API.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "TML.API.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .

# Create non-root user
RUN groupadd -r tml && useradd -r -g tml tml
RUN chown -R tml:tml /app
USER tml

ENTRYPOINT ["dotnet", "TML.API.dll"]
```

```dockerfile
# Dockerfile.python.prod
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r tml && useradd -r -g tml tml
RUN chown -R tml:tml /app
USER tml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8081/_stcore/health || exit 1

# Expose port
EXPOSE 8081

# Run Streamlit
CMD ["streamlit", "run", "demo/app.py", "--server.port=8081", "--server.address=0.0.0.0", "--server.headless=true"]
```

---

## Kubernetes Deployment

### Namespace and ConfigMap

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tml-production
  labels:
    name: tml-production
    environment: production

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tml-config
  namespace: tml-production
data:
  TML_ENVIRONMENT: "production"
  TML_LOG_LEVEL: "INFO"
  API_HOST: "0.0.0.0"
  API_PORT: "5000"
  ACTOR_SYSTEM_NAME: "TMLProductionSystem"
  TRANSACTION_PROCESSOR_COUNT: "10"
  MODEL_ACTOR_COUNT: "20"
  PHYSICS_VALIDATOR_COUNT: "5"
  PROMETHEUS_ENABLED: "true"
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: tml-secrets
  namespace: tml-production
type: Opaque
data:
  database-password: <base64-encoded-password>
  redis-password: <base64-encoded-password>
  jwt-secret: <base64-encoded-jwt-secret>
  grafana-password: <base64-encoded-grafana-password>
```

### API Deployment

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tml-api
  namespace: tml-production
  labels:
    app: tml-api
    version: v3.0
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 1
  selector:
    matchLabels:
      app: tml-api
  template:
    metadata:
      labels:
        app: tml-api
        version: v3.0
    spec:
      containers:
      - name: tml-api
        image: tml-platform/api:v3.0
        ports:
        - containerPort: 5000
          name: http
        env:
        - name: ASPNETCORE_ENVIRONMENT
          value: "Production"
        - name: ASPNETCORE_URLS
          value: "http://+:5000"
        envFrom:
        - configMapRef:
            name: tml-config
        - secretRef:
            name: tml-secrets
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: tml-logs-pvc
      nodeSelector:
        node-type: compute
      tolerations:
      - key: "compute-node"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"

---
apiVersion: v1
kind: Service
metadata:
  name: tml-api-service
  namespace: tml-production
  labels:
    app: tml-api
spec:
  type: ClusterIP
  ports:
  - port: 5000
    targetPort: 5000
    protocol: TCP
    name: http
  selector:
    app: tml-api
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tml-api-hpa
  namespace: tml-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tml-api
  minReplicas: 5
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 10
        periodSeconds: 15
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
      selectPolicy: Min
```

### Ingress Configuration

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tml-ingress
  namespace: tml-production
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "30"
spec:
  tls:
  - hosts:
    - api.tml-platform.com
    - demo.tml-platform.com
    secretName: tml-tls-secret
  rules:
  - host: api.tml-platform.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tml-api-service
            port:
              number: 5000
  - host: demo.tml-platform.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tml-demo-service
            port:
              number: 8081
```

---

## Load Balancing

### Nginx Configuration

```nginx
# config/nginx.conf
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss 
               application/atom+xml image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=demo:10m rate=10r/s;

    # Upstream servers
    upstream tml_api {
        least_conn;
        server tml-api-1:5000 max_fails=3 fail_timeout=30s;
        server tml-api-2:5000 max_fails=3 fail_timeout=30s;
        server tml-api-3:5000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    upstream tml_demo {
        server tml-demo:8081 max_fails=3 fail_timeout=30s;
        keepalive 16;
    }

    # API Server
    server {
        listen 443 ssl http2;
        server_name api.tml-platform.com;

        ssl_certificate /etc/nginx/ssl/tml.crt;
        ssl_certificate_key /etc/nginx/ssl/tml.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        location / {
            limit_req zone=api burst=200 nodelay;
            
            proxy_pass http://tml_api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        location /health {
            access_log off;
            proxy_pass http://tml_api/health;
        }
    }

    # Demo Application
    server {
        listen 443 ssl http2;
        server_name demo.tml-platform.com;

        ssl_certificate /etc/nginx/ssl/tml.crt;
        ssl_certificate_key /etc/nginx/ssl/tml.key;
        ssl_protocols TLSv1.2 TLSv1.3;

        location / {
            limit_req zone=demo burst=50 nodelay;
            
            proxy_pass http://tml_demo;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name api.tml-platform.com demo.tml-platform.com;
        return 301 https://$server_name$request_uri;
    }
}
```

---

## SSL/TLS Configuration

### Certificate Management

```bash
#!/bin/bash
# scripts/setup-ssl.sh

# Generate self-signed certificates for development
generate_self_signed() {
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /opt/tml/ssl/tml.key \
        -out /opt/tml/ssl/tml.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=tml-platform.com"
}

# Setup Let's Encrypt certificates for production
setup_letsencrypt() {
    certbot certonly --nginx \
        -d api.tml-platform.com \
        -d demo.tml-platform.com \
        --email admin@tml-platform.com \
        --agree-tos \
        --non-interactive

    # Copy certificates to TML directory
    cp /etc/letsencrypt/live/api.tml-platform.com/fullchain.pem /opt/tml/ssl/tml.crt
    cp /etc/letsencrypt/live/api.tml-platform.com/privkey.pem /opt/tml/ssl/tml.key
}

# Setup certificate renewal
setup_renewal() {
    echo "0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx" | crontab -
}

case "$1" in
    "dev")
        generate_self_signed
        ;;
    "prod")
        setup_letsencrypt
        setup_renewal
        ;;
    *)
        echo "Usage: $0 {dev|prod}"
        exit 1
        ;;
esac
```

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# config/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "tml_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'tml-api'
    static_configs:
      - targets: ['tml-api:5000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'tml-demo'
    static_configs:
      - targets: ['tml-demo:8081']
    metrics_path: '/_stcore/metrics'
    scrape_interval: 30s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Alert Rules

```yaml
# config/tml_rules.yml
groups:
- name: tml_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors per second"

  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency detected"
      description: "95th percentile latency is {{ $value }} seconds"

  - alert: DatabaseConnectionFailure
    expr: up{job="postgres"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection failure"
      description: "PostgreSQL database is not responding"

  - alert: HighDriftScore
    expr: tml_model_drift_score > 0.1
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High model drift detected"
      description: "Model drift score is {{ $value }}"

  - alert: LowModelAccuracy
    expr: tml_model_accuracy < 0.7
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "Low model accuracy"
      description: "Model accuracy is {{ $value }}"
```

---

## Backup and Recovery

### Database Backup Script

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/opt/tml/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="tml_production"
DB_USER="tml_app"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME \
    --verbose --clean --no-owner --no-privileges \
    --format=custom \
    --file=$BACKUP_DIR/tml_db_$DATE.backup

# Compress backup
gzip $BACKUP_DIR/tml_db_$DATE.backup

# Upload to S3 (optional)
if [ "$AWS_S3_BUCKET" ]; then
    aws s3 cp $BACKUP_DIR/tml_db_$DATE.backup.gz \
        s3://$AWS_S3_BUCKET/backups/database/
fi

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "tml_db_*.backup.gz" -mtime +30 -delete

echo "Backup completed: tml_db_$DATE.backup.gz"
```

### Recovery Script

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_FILE=$1
DB_NAME="tml_production"
DB_USER="tml_app"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Stop services
docker-compose -f docker-compose.prod.yml stop tml-api tml-demo

# Drop and recreate database
dropdb -h localhost -U $DB_USER $DB_NAME
createdb -h localhost -U $DB_USER $DB_NAME

# Restore from backup
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c $BACKUP_FILE | pg_restore -h localhost -U $DB_USER -d $DB_NAME --verbose
else
    pg_restore -h localhost -U $DB_USER -d $DB_NAME --verbose $BACKUP_FILE
fi

# Start services
docker-compose -f docker-compose.prod.yml start tml-api tml-demo

echo "Database restored from $BACKUP_FILE"
```

---

## Health Checks

### Comprehensive Health Check Script

```bash
#!/bin/bash
# scripts/health-check.sh

API_URL="https://api.tml-platform.com"
DEMO_URL="https://demo.tml-platform.com"
TIMEOUT=10

check_service() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "Checking $name... "
    
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url")
    
    if [ "$status" = "$expected_status" ]; then
        echo "✅ OK ($status)"
        return 0
    else
        echo "❌ FAILED ($status)"
        return 1
    fi
}

check_database() {
    echo -n "Checking PostgreSQL... "
    
    if pg_isready -h localhost -p 5432 -U tml_app > /dev/null 2>&1; then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

check_redis() {
    echo -n "Checking Redis... "
    
    if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

check_disk_space() {
    echo -n "Checking disk space... "
    
    usage=$(df /opt/tml | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -lt 80 ]; then
        echo "✅ OK (${usage}% used)"
        return 0
    else
        echo "⚠️  WARNING (${usage}% used)"
        return 1
    fi
}

check_memory() {
    echo -n "Checking memory usage... "
    
    usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$usage" -lt 90 ]; then
        echo "✅ OK (${usage}% used)"
        return 0
    else
        echo "⚠️  WARNING (${usage}% used)"
        return 1
    fi
}

# Run all checks
echo "🏥 TML Platform Health Check"
echo "=========================="

failed=0

check_service "API Health" "$API_URL/health" || ((failed++))
check_service "API Ready" "$API_URL/ready" || ((failed++))
check_service "Demo Application" "$DEMO_URL/_stcore/health" || ((failed++))
check_database || ((failed++))
check_redis || ((failed++))
check_disk_space || ((failed++))
check_memory || ((failed++))

echo "=========================="

if [ $failed -eq 0 ]; then
    echo "✅ All checks passed"
    exit 0
else
    echo "❌ $failed checks failed"
    exit 1
fi
```

### Kubernetes Health Check

```yaml
# k8s/health-check-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: tml-health-check
  namespace: tml-production
spec:
  schedule: "*/5 * * * *"  # Every 5 minutes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: health-check
            image: curlimages/curl:latest
            command:
            - /bin/sh
            - -c
            - |
              echo "Running TML health check..."
              
              # Check API health
              if ! curl -f -s http://tml-api-service:5000/health > /dev/null; then
                echo "API health check failed"
                exit 1
              fi
              
              # Check API readiness
              if ! curl -f -s http://tml-api-service:5000/ready > /dev/null; then
                echo "API readiness check failed"
                exit 1
              fi
              
              echo "All health checks passed"
          restartPolicy: OnFailure
```

---

## Deployment Scripts

### Main Deployment Script

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

ENVIRONMENT=${1:-production}
VERSION=${2:-latest}

echo "🚀 Deploying TML Platform v$VERSION to $ENVIRONMENT"

# Load environment variables
source /opt/tml/config/$ENVIRONMENT.env

# Pre-deployment checks
echo "📋 Running pre-deployment checks..."
./scripts/health-check.sh || {
    echo "❌ Pre-deployment health checks failed"
    exit 1
}

# Database migrations
echo "🗄️  Running database migrations..."
docker run --rm \
    --network tml_default \
    -e DATABASE_HOST=$DATABASE_HOST \
    -e DATABASE_PASSWORD=$DATABASE_PASSWORD \
    tml-platform/migrations:$VERSION

# Build and deploy containers
echo "🐳 Building and deploying containers..."
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --remove-orphans

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Post-deployment health checks
echo "🏥 Running post-deployment health checks..."
./scripts/health-check.sh || {
    echo "❌ Post-deployment health checks failed"
    echo "🔄 Rolling back..."
    docker-compose -f docker-compose.prod.yml down
    exit 1
}

# Cleanup old images
echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Deployment completed successfully!"
echo "🌐 API: https://api.tml-platform.com"
echo "🖥️  Demo: https://demo.tml-platform.com"
echo "📊 Monitoring: https://monitoring.tml-platform.com"
```

---

## Summary

This production deployment guide provides:

1. **Complete Infrastructure Setup** - Environment variables, directory structure, and configuration
2. **Database Configuration** - PostgreSQL with replication, optimization, and partitioning
3. **Container Deployment** - Production Docker Compose with resource limits and health checks
4. **Kubernetes Deployment** - Scalable K8s manifests with auto-scaling and ingress
5. **Load Balancing** - Nginx configuration with SSL/TLS and rate limiting
6. **Monitoring** - Prometheus and Grafana setup with custom alerts
7. **Backup & Recovery** - Automated backup scripts and recovery procedures
8. **Health Checks** - Comprehensive monitoring and alerting

The TML Platform is now ready for enterprise production deployment with high availability, scalability, and monitoring capabilities.
