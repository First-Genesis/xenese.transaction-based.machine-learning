# 📈 TML Platform Scaling Guide

This guide covers horizontal and vertical scaling strategies for the TML Platform to handle enterprise-scale workloads with millions of models and high-throughput transaction processing.

## Table of Contents
1. [Scaling Overview](#scaling-overview)
2. [Performance Baselines](#performance-baselines)
3. [Horizontal Scaling](#horizontal-scaling)
4. [Vertical Scaling](#vertical-scaling)
5. [Database Scaling](#database-scaling)
6. [Caching Strategy](#caching-strategy)
7. [Load Testing](#load-testing)
8. [Auto-Scaling Configuration](#auto-scaling-configuration)
9. [Monitoring and Metrics](#monitoring-and-metrics)
10. [Cost Optimization](#cost-optimization)

---

## Scaling Overview

### Current Production Metrics
- **Models Stored**: 1,274+ in PostgreSQL
- **Models Monitored**: 546+ for drift detection
- **Drift Score**: 0.000 (healthy baseline)
- **Processing Modes**: Sequential, Proto.Actor, Docker integration
- **Target Performance**: <100ms latency, >10K TPS, 99.99% uptime

### Scaling Dimensions

| Component | Horizontal Scaling | Vertical Scaling | Auto-Scaling |
|-----------|-------------------|------------------|--------------|
| **API Servers** | ✅ Load balancer + replicas | ✅ CPU/Memory increase | ✅ HPA based on CPU/Memory |
| **Proto.Actor System** | ✅ Actor clustering | ✅ More actors per node | ✅ Custom metrics scaling |
| **Database** | ✅ Read replicas + sharding | ✅ Larger instances | ❌ Manual scaling |
| **Redis Cache** | ✅ Redis Cluster | ✅ More memory | ✅ Memory-based scaling |
| **Streamlit Demo** | ✅ Multiple instances | ✅ Resource increase | ✅ Traffic-based scaling |

---

## Performance Baselines

### Single Node Performance

```yaml
# Baseline Configuration (Single Node)
Resources:
  CPU: 8 cores
  Memory: 32GB RAM
  Storage: 1TB NVMe SSD
  Network: 1Gbps

Performance Metrics:
  - API Requests: 1,000 RPS
  - Model Processing: 500 models/second
  - Database Queries: 5,000 QPS
  - Memory Usage: 16GB (50%)
  - CPU Usage: 60%
  - Storage I/O: 2,000 IOPS
```

### Target Scale Performance

```yaml
# Target Scale Configuration (Multi-Node Cluster)
Resources:
  Nodes: 20 compute nodes
  Total CPU: 640 cores
  Total Memory: 2.5TB RAM
  Storage: 100TB distributed
  Network: 100Gbps backbone

Performance Targets:
  - API Requests: 100,000 RPS
  - Model Processing: 50,000 models/second
  - Concurrent Models: 1,000,000+
  - Database Queries: 500,000 QPS
  - Latency P95: <100ms
  - Availability: 99.99%
```

---

## Horizontal Scaling

### API Server Scaling

#### Load Balancer Configuration

```yaml
# k8s/api-scaling.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tml-api
  namespace: tml-production
spec:
  replicas: 20  # Scale from 5 to 20 replicas
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 5
      maxUnavailable: 2
  template:
    spec:
      containers:
      - name: tml-api
        image: tml-platform/api:v3.0
        resources:
          requests:
            memory: "4Gi"
            cpu: "2000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
        env:
        - name: ACTOR_SYSTEM_NAME
          value: "TMLScaledSystem"
        - name: TRANSACTION_PROCESSOR_COUNT
          value: "20"  # Increased from 10
        - name: MODEL_ACTOR_COUNT
          value: "50"  # Increased from 20
        - name: PHYSICS_VALIDATOR_COUNT
          value: "10"  # Increased from 5

---
# Advanced HPA with custom metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tml-api-advanced-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tml-api
  minReplicas: 10
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: tml_models_processed_per_second
      target:
        type: AverageValue
        averageValue: "100"
  - type: Pods
    pods:
      metric:
        name: tml_drift_detection_queue_length
      target:
        type: AverageValue
        averageValue: "50"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 30
      - type: Pods
        value: 5
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 120
```

#### Multi-Region Deployment

```yaml
# k8s/multi-region-deployment.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tml-us-east-1
  namespace: argocd
spec:
  project: tml-production
  source:
    repoURL: https://github.com/company/tml-platform
    targetRevision: main
    path: k8s/overlays/us-east-1
  destination:
    server: https://us-east-1.k8s.company.com
    namespace: tml-production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true

---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tml-us-west-2
  namespace: argocd
spec:
  project: tml-production
  source:
    repoURL: https://github.com/company/tml-platform
    targetRevision: main
    path: k8s/overlays/us-west-2
  destination:
    server: https://us-west-2.k8s.company.com
    namespace: tml-production
```

### Proto.Actor Clustering

```csharp
// src/TML.Actors/Configuration/ClusterConfiguration.cs
public class ClusterConfiguration
{
    public static ActorSystemConfig CreateClusterConfig()
    {
        return ActorSystemConfig
            .Setup()
            .WithClusterKind("transaction-processor", Props.FromProducer<TransactionProcessorActor>)
            .WithClusterKind("model-actor", Props.FromProducer<ModelActor>)
            .WithClusterKind("physics-validator", Props.FromProducer<PhysicsValidatorActor>)
            .WithClusterProvider(new ConsulProvider(new ConsulProviderConfig
            {
                Address = Environment.GetEnvironmentVariable("CONSUL_ADDRESS") ?? "localhost:8500",
                ServiceName = "tml-actors",
                Id = Environment.MachineName + "-" + Guid.NewGuid().ToString("N")[..8],
                DeregisterCritical = TimeSpan.FromSeconds(30),
                RefreshTtl = TimeSpan.FromSeconds(10),
                BlockingWaitTime = TimeSpan.FromSeconds(20)
            }))
            .WithRemote(GrpcNetRemoteConfig
                .BindToLocalhost()
                .WithPort(8080)
                .WithEndpointWriterMaxRetries(3))
            .WithDeadLetterThrottleCount(10)
            .WithDeadLetterThrottleInterval(TimeSpan.FromSeconds(1))
            .WithDeveloperSupervisionLogging(false);
    }
}
```

```csharp
// Enhanced Actor Pool Management
public class ScalableActorPool
{
    private readonly ActorSystem _system;
    private readonly List<PID> _transactionProcessors = new();
    private readonly List<PID> _modelActors = new();
    private readonly SemaphoreSlim _scalingSemaphore = new(1, 1);
    
    public async Task ScaleTransactionProcessors(int targetCount)
    {
        await _scalingSemaphore.WaitAsync();
        try
        {
            var currentCount = _transactionProcessors.Count;
            
            if (targetCount > currentCount)
            {
                // Scale up
                for (int i = currentCount; i < targetCount; i++)
                {
                    var props = Props.FromProducer(() => new TransactionProcessorActor());
                    var pid = _system.Root.SpawnNamed(props, $"transaction-processor-{i}");
                    _transactionProcessors.Add(pid);
                }
            }
            else if (targetCount < currentCount)
            {
                // Scale down gracefully
                for (int i = currentCount - 1; i >= targetCount; i--)
                {
                    await _system.Root.StopAsync(_transactionProcessors[i]);
                    _transactionProcessors.RemoveAt(i);
                }
            }
        }
        finally
        {
            _scalingSemaphore.Release();
        }
    }
    
    public PID GetLeastLoadedProcessor()
    {
        // Implement load balancing logic
        return _transactionProcessors[Random.Shared.Next(_transactionProcessors.Count)];
    }
}
```

---

## Vertical Scaling

### Resource Optimization

```yaml
# k8s/vertical-scaling.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tml-production-quota
  namespace: tml-production
spec:
  hard:
    requests.cpu: "500"
    requests.memory: "1000Gi"
    limits.cpu: "1000"
    limits.memory: "2000Gi"
    persistentvolumeclaims: "50"
    services.loadbalancers: "5"

---
# Vertical Pod Autoscaler
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: tml-api-vpa
  namespace: tml-production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tml-api
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: tml-api
      minAllowed:
        cpu: "1000m"
        memory: "2Gi"
      maxAllowed:
        cpu: "8000m"
        memory: "16Gi"
      controlledResources: ["cpu", "memory"]
```

### Node Configuration

```yaml
# k8s/node-pools.yaml
apiVersion: v1
kind: Node
metadata:
  name: tml-compute-node
  labels:
    node-type: compute
    instance-type: c5.24xlarge
    zone: us-east-1a
spec:
  capacity:
    cpu: "96"
    memory: "192Gi"
    ephemeral-storage: "1800Gi"
  allocatable:
    cpu: "94"
    memory: "180Gi"
    ephemeral-storage: "1700Gi"
  taints:
  - key: "compute-node"
    value: "true"
    effect: "NoSchedule"

---
# Node affinity for TML workloads
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tml-api-compute
spec:
  template:
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: node-type
                operator: In
                values: ["compute"]
              - key: instance-type
                operator: In
                values: ["c5.24xlarge", "c5.18xlarge", "c5.12xlarge"]
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values: ["tml-api"]
              topologyKey: kubernetes.io/hostname
```

---

## Database Scaling

### PostgreSQL Read Replicas

```yaml
# k8s/postgres-scaling.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: tml-postgres-cluster
  namespace: tml-production
spec:
  instances: 5  # 1 primary + 4 read replicas
  
  postgresql:
    parameters:
      max_connections: "500"
      shared_buffers: "16GB"
      effective_cache_size: "48GB"
      work_mem: "512MB"
      maintenance_work_mem: "4GB"
      checkpoint_completion_target: "0.9"
      wal_buffers: "128MB"
      default_statistics_target: "100"
      random_page_cost: "1.1"
      effective_io_concurrency: "200"
      
  resources:
    requests:
      memory: "64Gi"
      cpu: "16"
    limits:
      memory: "64Gi"
      cpu: "16"
      
  storage:
    size: "2Ti"
    storageClass: "fast-ssd"
    
  monitoring:
    enabled: true
    
  backup:
    retentionPolicy: "30d"
    barmanObjectStore:
      destinationPath: "s3://tml-backups/postgres"
      s3Credentials:
        accessKeyId:
          name: backup-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: backup-credentials
          key: SECRET_ACCESS_KEY
      wal:
        retention: "7d"
      data:
        retention: "30d"
```

### Database Connection Pooling

```yaml
# k8s/pgbouncer.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
  namespace: tml-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      containers:
      - name: pgbouncer
        image: pgbouncer/pgbouncer:latest
        ports:
        - containerPort: 5432
        env:
        - name: DATABASES_HOST
          value: "tml-postgres-cluster-rw"
        - name: DATABASES_PORT
          value: "5432"
        - name: DATABASES_USER
          value: "tml_app"
        - name: DATABASES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: tml-secrets
              key: database-password
        - name: DATABASES_DBNAME
          value: "tml_production"
        - name: POOL_MODE
          value: "transaction"
        - name: MAX_CLIENT_CONN
          value: "1000"
        - name: DEFAULT_POOL_SIZE
          value: "100"
        - name: MIN_POOL_SIZE
          value: "10"
        - name: RESERVE_POOL_SIZE
          value: "20"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

---
apiVersion: v1
kind: Service
metadata:
  name: pgbouncer-service
  namespace: tml-production
spec:
  selector:
    app: pgbouncer
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
```

### Database Sharding Strategy

```sql
-- Database sharding for model storage
-- Shard by model_id hash for even distribution

-- Shard 1: models_shard_1 (model_id hash % 4 = 0)
CREATE TABLE models_shard_1 (
    LIKE models INCLUDING ALL
) INHERITS (models);

-- Shard 2: models_shard_2 (model_id hash % 4 = 1)
CREATE TABLE models_shard_2 (
    LIKE models INCLUDING ALL
) INHERITS (models);

-- Shard 3: models_shard_3 (model_id hash % 4 = 2)
CREATE TABLE models_shard_3 (
    LIKE models INCLUDING ALL
) INHERITS (models);

-- Shard 4: models_shard_4 (model_id hash % 4 = 3)
CREATE TABLE models_shard_4 (
    LIKE models INCLUDING ALL
) INHERITS (models);

-- Trigger function for automatic sharding
CREATE OR REPLACE FUNCTION models_insert_trigger()
RETURNS TRIGGER AS $$
DECLARE
    shard_id INTEGER;
BEGIN
    shard_id := hashtext(NEW.id::text) % 4;
    
    CASE shard_id
        WHEN 0 THEN INSERT INTO models_shard_1 VALUES (NEW.*);
        WHEN 1 THEN INSERT INTO models_shard_2 VALUES (NEW.*);
        WHEN 2 THEN INSERT INTO models_shard_3 VALUES (NEW.*);
        WHEN 3 THEN INSERT INTO models_shard_4 VALUES (NEW.*);
    END CASE;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
CREATE TRIGGER models_insert_trigger
    BEFORE INSERT ON models
    FOR EACH ROW EXECUTE FUNCTION models_insert_trigger();
```

---

## Caching Strategy

### Redis Cluster Configuration

```yaml
# k8s/redis-cluster.yaml
apiVersion: redis.redis.opstreelabs.in/v1beta1
kind: RedisCluster
metadata:
  name: tml-redis-cluster
  namespace: tml-production
spec:
  clusterSize: 6
  clusterVersion: v7
  persistenceEnabled: true
  
  redisExporter:
    enabled: true
    image: oliver006/redis_exporter:latest
    
  redisConfig:
    maxmemory: "8gb"
    maxmemory-policy: "allkeys-lru"
    save: "900 1 300 10 60 10000"
    appendonly: "yes"
    appendfsync: "everysec"
    tcp-keepalive: "60"
    timeout: "300"
    
  storage:
    volumeClaimTemplate:
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: "fast-ssd"
        resources:
          requests:
            storage: "100Gi"
            
  resources:
    requests:
      cpu: "2000m"
      memory: "10Gi"
    limits:
      cpu: "4000m"
      memory: "10Gi"
      
  nodeSelector:
    node-type: "memory-optimized"
    
  tolerations:
  - key: "memory-node"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

### Multi-Level Caching

```python
# tml/caching/multi_level_cache.py
import asyncio
import redis.asyncio as redis
from typing import Any, Optional, Dict, List
import json
import pickle
import hashlib

class MultiLevelCache:
    def __init__(self, redis_cluster_nodes: List[str]):
        # L1 Cache: In-memory (fastest)
        self.l1_cache: Dict[str, Any] = {}
        self.l1_max_size = 10000
        
        # L2 Cache: Redis Cluster (fast, distributed)
        self.redis_cluster = redis.RedisCluster(
            startup_nodes=[{"host": node.split(':')[0], "port": int(node.split(':')[1])} 
                          for node in redis_cluster_nodes],
            decode_responses=False,
            skip_full_coverage_check=True,
            max_connections_per_node=100
        )
        
        # L3 Cache: Database query cache (slower, persistent)
        self.db_cache_ttl = 3600  # 1 hour
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-level cache"""
        
        # Try L1 cache first
        if key in self.l1_cache:
            return self.l1_cache[key]
        
        # Try L2 cache (Redis)
        try:
            value = await self.redis_cluster.get(key)
            if value:
                deserialized = pickle.loads(value)
                # Promote to L1 cache
                self._set_l1(key, deserialized)
                return deserialized
        except Exception as e:
            print(f"Redis cache error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in multi-level cache"""
        
        # Set in L1 cache
        self._set_l1(key, value)
        
        # Set in L2 cache (Redis)
        try:
            serialized = pickle.dumps(value)
            await self.redis_cluster.setex(key, ttl, serialized)
        except Exception as e:
            print(f"Redis cache set error: {e}")
    
    def _set_l1(self, key: str, value: Any) -> None:
        """Set value in L1 cache with LRU eviction"""
        if len(self.l1_cache) >= self.l1_max_size:
            # Remove oldest item (simple LRU)
            oldest_key = next(iter(self.l1_cache))
            del self.l1_cache[oldest_key]
        
        self.l1_cache[key] = value
    
    async def get_model_prediction(self, model_id: str, input_hash: str) -> Optional[Any]:
        """Specialized method for model prediction caching"""
        cache_key = f"prediction:{model_id}:{input_hash}"
        return await self.get(cache_key)
    
    async def set_model_prediction(self, model_id: str, input_hash: str, 
                                 prediction: Any, confidence: float) -> None:
        """Cache model prediction with confidence-based TTL"""
        cache_key = f"prediction:{model_id}:{input_hash}"
        
        # Higher confidence = longer TTL
        ttl = int(3600 * confidence)  # 1 hour * confidence
        ttl = max(300, min(ttl, 7200))  # Between 5 minutes and 2 hours
        
        await self.set(cache_key, {
            'prediction': prediction,
            'confidence': confidence,
            'model_id': model_id
        }, ttl)
    
    async def invalidate_model_cache(self, model_id: str) -> None:
        """Invalidate all cache entries for a specific model"""
        pattern = f"prediction:{model_id}:*"
        
        # Remove from L1 cache
        keys_to_remove = [k for k in self.l1_cache.keys() if k.startswith(f"prediction:{model_id}:")]
        for key in keys_to_remove:
            del self.l1_cache[key]
        
        # Remove from Redis
        try:
            async for key in self.redis_cluster.scan_iter(match=pattern):
                await self.redis_cluster.delete(key)
        except Exception as e:
            print(f"Cache invalidation error: {e}")
```

---

## Load Testing

### Load Testing Configuration

```python
# tests/load_testing/locust_load_test.py
from locust import HttpUser, task, between
import json
import random
import uuid

class TMLLoadTest(HttpUser):
    wait_time = between(0.1, 0.5)  # 100-500ms between requests
    
    def on_start(self):
        """Setup test data"""
        self.test_models = []
        self.test_transactions = []
        
        # Generate test data
        for i in range(1000):
            self.test_transactions.append({
                'id': str(uuid.uuid4()),
                'data': {
                    'feature_1': random.uniform(0, 100),
                    'feature_2': random.uniform(0, 1),
                    'feature_3': random.choice(['A', 'B', 'C']),
                    'timestamp': '2024-01-01T12:00:00Z'
                }
            })
    
    @task(10)
    def process_transaction(self):
        """Test transaction processing endpoint"""
        transaction = random.choice(self.test_transactions)
        
        response = self.client.post("/api/transactions/process", 
                                  json=transaction,
                                  headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            result = response.json()
            if 'model_id' in result:
                self.test_models.append(result['model_id'])
    
    @task(5)
    def get_model_health(self):
        """Test model health endpoint"""
        self.client.get("/api/models/health")
    
    @task(3)
    def get_drift_monitoring(self):
        """Test drift monitoring endpoint"""
        self.client.get("/api/drift/monitor")
    
    @task(2)
    def get_actor_health(self):
        """Test actor system health"""
        self.client.get("/api/actors/health")
    
    @task(1)
    def get_specific_model(self):
        """Test specific model retrieval"""
        if self.test_models:
            model_id = random.choice(self.test_models)
            self.client.get(f"/api/models/{model_id}")

class TMLStressTest(HttpUser):
    """High-intensity stress test"""
    wait_time = between(0.01, 0.05)  # 10-50ms between requests
    
    @task
    def rapid_fire_processing(self):
        """Rapid transaction processing"""
        transaction = {
            'id': str(uuid.uuid4()),
            'data': {
                'value': random.uniform(0, 1000),
                'category': random.choice(['high', 'medium', 'low']),
                'urgent': random.choice([True, False])
            }
        }
        
        self.client.post("/api/transactions/process", json=transaction)
```

### Load Testing Scripts

```bash
#!/bin/bash
# scripts/load-test.sh

ENVIRONMENT=${1:-staging}
USERS=${2:-100}
SPAWN_RATE=${3:-10}
DURATION=${4:-300}

echo "🔥 Starting load test against $ENVIRONMENT"
echo "Users: $USERS, Spawn Rate: $SPAWN_RATE, Duration: ${DURATION}s"

# Set target URL based on environment
case $ENVIRONMENT in
    "staging")
        TARGET_URL="https://staging-api.tml-platform.com"
        ;;
    "production")
        TARGET_URL="https://api.tml-platform.com"
        ;;
    "local")
        TARGET_URL="http://localhost:5000"
        ;;
    *)
        echo "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

# Run load test
locust -f tests/load_testing/locust_load_test.py \
       --host=$TARGET_URL \
       --users=$USERS \
       --spawn-rate=$SPAWN_RATE \
       --run-time=${DURATION}s \
       --html=load-test-results/report-$(date +%Y%m%d_%H%M%S).html \
       --csv=load-test-results/results-$(date +%Y%m%d_%H%M%S) \
       --headless

# Analyze results
python scripts/analyze-load-test.py load-test-results/

echo "✅ Load test completed"
```

### Performance Benchmarking

```python
# scripts/benchmark.py
import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any

class TMLBenchmark:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results: Dict[str, List[float]] = {}
    
    async def benchmark_endpoint(self, endpoint: str, payload: Dict[str, Any], 
                                concurrent_requests: int = 100, 
                                total_requests: int = 1000) -> Dict[str, Any]:
        """Benchmark a specific endpoint"""
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        response_times = []
        errors = 0
        
        async def make_request(session: aiohttp.ClientSession) -> float:
            async with semaphore:
                start_time = time.time()
                try:
                    async with session.post(f"{self.base_url}{endpoint}", 
                                          json=payload) as response:
                        await response.read()
                        if response.status != 200:
                            nonlocal errors
                            errors += 1
                        return time.time() - start_time
                except Exception:
                    errors += 1
                    return time.time() - start_time
        
        # Run benchmark
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(total_requests)]
            response_times = await asyncio.gather(*tasks)
        
        # Calculate statistics
        response_times = [rt for rt in response_times if rt > 0]
        
        return {
            'endpoint': endpoint,
            'total_requests': total_requests,
            'successful_requests': len(response_times),
            'failed_requests': errors,
            'success_rate': len(response_times) / total_requests,
            'avg_response_time': statistics.mean(response_times),
            'median_response_time': statistics.median(response_times),
            'p95_response_time': statistics.quantiles(response_times, n=20)[18],
            'p99_response_time': statistics.quantiles(response_times, n=100)[98],
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'requests_per_second': len(response_times) / sum(response_times)
        }
    
    async def run_full_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive benchmark suite"""
        
        benchmarks = [
            {
                'endpoint': '/api/transactions/process',
                'payload': {
                    'id': 'benchmark_001',
                    'data': {'value': 100, 'category': 'test'}
                }
            },
            {
                'endpoint': '/api/models/health',
                'payload': {}
            },
            {
                'endpoint': '/api/drift/monitor',
                'payload': {}
            },
            {
                'endpoint': '/api/actors/health',
                'payload': {}
            }
        ]
        
        results = {}
        
        for benchmark in benchmarks:
            print(f"Benchmarking {benchmark['endpoint']}...")
            result = await self.benchmark_endpoint(
                benchmark['endpoint'], 
                benchmark['payload']
            )
            results[benchmark['endpoint']] = result
            
            print(f"  Avg Response Time: {result['avg_response_time']:.3f}s")
            print(f"  P95 Response Time: {result['p95_response_time']:.3f}s")
            print(f"  Success Rate: {result['success_rate']:.2%}")
            print(f"  RPS: {result['requests_per_second']:.1f}")
            print()
        
        return results

async def main():
    benchmark = TMLBenchmark("http://localhost:5000")
    results = await benchmark.run_full_benchmark()
    
    # Save results
    import json
    with open(f"benchmark-results-{int(time.time())}.json", 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Auto-Scaling Configuration

### Custom Metrics Auto-Scaling

```yaml
# k8s/custom-metrics-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tml-custom-metrics-hpa
  namespace: tml-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tml-api
  minReplicas: 5
  maxReplicas: 200
  metrics:
  # CPU and Memory
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
  
  # Custom TML Metrics
  - type: Pods
    pods:
      metric:
        name: tml_models_processed_per_second
      target:
        type: AverageValue
        averageValue: "50"
  
  - type: Pods
    pods:
      metric:
        name: tml_drift_detection_queue_length
      target:
        type: AverageValue
        averageValue: "100"
  
  - type: Pods
    pods:
      metric:
        name: tml_actor_mailbox_size
      target:
        type: AverageValue
        averageValue: "500"
  
  - type: Object
    object:
      metric:
        name: tml_database_connection_pool_usage
      target:
        type: Value
        value: "80"
      describedObject:
        apiVersion: v1
        kind: Service
        name: pgbouncer-service
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 10
        periodSeconds: 30
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 120
      - type: Pods
        value: 2
        periodSeconds: 120
      selectPolicy: Min
```

### Vertical Pod Autoscaler

```yaml
# k8s/vpa-config.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: tml-api-vpa
  namespace: tml-production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tml-api
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: tml-api
      minAllowed:
        cpu: "2000m"
        memory: "4Gi"
      maxAllowed:
        cpu: "16000m"
        memory: "32Gi"
      controlledResources: ["cpu", "memory"]
      controlledValues: RequestsAndLimits
```

### Cluster Autoscaler

```yaml
# k8s/cluster-autoscaler.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    metadata:
      labels:
        app: cluster-autoscaler
    spec:
      containers:
      - image: k8s.gcr.io/autoscaling/cluster-autoscaler:v1.21.0
        name: cluster-autoscaler
        resources:
          limits:
            cpu: 100m
            memory: 300Mi
          requests:
            cpu: 100m
            memory: 300Mi
        command:
        - ./cluster-autoscaler
        - --v=4
        - --stderrthreshold=info
        - --cloud-provider=aws
        - --skip-nodes-with-local-storage=false
        - --expander=least-waste
        - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/tml-production
        - --balance-similar-node-groups
        - --scale-down-enabled=true
        - --scale-down-delay-after-add=10m
        - --scale-down-unneeded-time=10m
        - --scale-down-utilization-threshold=0.5
        - --max-nodes-total=1000
        - --cores-total=0:32000
        - --memory-total=0:128000
```

---

## Monitoring and Metrics

### Custom Metrics Collection

```csharp
// src/TML.API/Metrics/TMLMetrics.cs
using Prometheus;

public static class TMLMetrics
{
    // Transaction Processing Metrics
    public static readonly Counter TransactionsProcessed = Metrics
        .CreateCounter("tml_transactions_processed_total", 
                      "Total number of transactions processed",
                      new[] { "status", "processing_mode" });
    
    public static readonly Histogram TransactionProcessingDuration = Metrics
        .CreateHistogram("tml_transaction_processing_duration_seconds",
                        "Time spent processing transactions",
                        new[] { "processing_mode" });
    
    // Model Metrics
    public static readonly Gauge ModelsInMemory = Metrics
        .CreateGauge("tml_models_in_memory", 
                    "Number of models currently in memory");
    
    public static readonly Counter ModelsCreated = Metrics
        .CreateCounter("tml_models_created_total",
                      "Total number of models created");
    
    public static readonly Gauge ModelDriftScore = Metrics
        .CreateGauge("tml_model_drift_score",
                    "Current drift score for models",
                    new[] { "model_id" });
    
    // Actor System Metrics
    public static readonly Gauge ActorMailboxSize = Metrics
        .CreateGauge("tml_actor_mailbox_size",
                    "Size of actor mailboxes",
                    new[] { "actor_type", "actor_id" });
    
    public static readonly Counter ActorMessages = Metrics
        .CreateCounter("tml_actor_messages_total",
                      "Total messages processed by actors",
                      new[] { "actor_type", "message_type" });
    
    // Database Metrics
    public static readonly Gauge DatabaseConnections = Metrics
        .CreateGauge("tml_database_connections",
                    "Number of active database connections");
    
    public static readonly Histogram DatabaseQueryDuration = Metrics
        .CreateHistogram("tml_database_query_duration_seconds",
                        "Time spent on database queries",
                        new[] { "query_type" });
    
    // Cache Metrics
    public static readonly Counter CacheHits = Metrics
        .CreateCounter("tml_cache_hits_total",
                      "Total cache hits",
                      new[] { "cache_level" });
    
    public static readonly Counter CacheMisses = Metrics
        .CreateCounter("tml_cache_misses_total",
                      "Total cache misses",
                      new[] { "cache_level" });
}
```

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "TML Platform Scaling Dashboard",
    "panels": [
      {
        "title": "Transaction Processing Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(tml_transactions_processed_total[5m])",
            "legendFormat": "{{status}} - {{processing_mode}}"
          }
        ]
      },
      {
        "title": "Response Time Percentiles",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(tml_transaction_processing_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          },
          {
            "expr": "histogram_quantile(0.95, rate(tml_transaction_processing_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.99, rate(tml_transaction_processing_duration_seconds_bucket[5m]))",
            "legendFormat": "99th percentile"
          }
        ]
      },
      {
        "title": "Auto-Scaling Status",
        "type": "graph",
        "targets": [
          {
            "expr": "kube_deployment_status_replicas{deployment=\"tml-api\"}",
            "legendFormat": "Current Replicas"
          },
          {
            "expr": "kube_deployment_spec_replicas{deployment=\"tml-api\"}",
            "legendFormat": "Desired Replicas"
          }
        ]
      },
      {
        "title": "Resource Utilization",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(container_cpu_usage_seconds_total{pod=~\"tml-api-.*\"}[5m]) * 100",
            "legendFormat": "CPU Usage %"
          },
          {
            "expr": "container_memory_usage_bytes{pod=~\"tml-api-.*\"} / container_spec_memory_limit_bytes * 100",
            "legendFormat": "Memory Usage %"
          }
        ]
      }
    ]
  }
}
```

---

## Cost Optimization

### Resource Right-Sizing

```python
# scripts/cost-optimization.py
import json
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ResourceRecommendation:
    component: str
    current_cost: float
    recommended_cost: float
    savings: float
    confidence: float
    reasoning: str

class CostOptimizer:
    def __init__(self, metrics_data: Dict[str, Any]):
        self.metrics = metrics_data
        self.recommendations: List[ResourceRecommendation] = []
    
    def analyze_api_servers(self) -> ResourceRecommendation:
        """Analyze API server resource usage and costs"""
        
        current_replicas = self.metrics.get('api_replicas', 20)
        avg_cpu_usage = self.metrics.get('avg_cpu_usage', 0.45)  # 45%
        avg_memory_usage = self.metrics.get('avg_memory_usage', 0.60)  # 60%
        
        # Cost per replica per month (c5.2xlarge = $0.34/hour)
        cost_per_replica = 0.34 * 24 * 30  # $244.8/month
        current_cost = current_replicas * cost_per_replica
        
        # Recommendation based on usage
        if avg_cpu_usage < 0.5 and avg_memory_usage < 0.7:
            # Can reduce instance size or replica count
            recommended_replicas = max(10, int(current_replicas * 0.8))
            recommended_cost = recommended_replicas * cost_per_replica
            
            return ResourceRecommendation(
                component="API Servers",
                current_cost=current_cost,
                recommended_cost=recommended_cost,
                savings=current_cost - recommended_cost,
                confidence=0.85,
                reasoning=f"Low resource utilization (CPU: {avg_cpu_usage:.1%}, Memory: {avg_memory_usage:.1%}). Reduce replicas from {current_replicas} to {recommended_replicas}."
            )
        
        return ResourceRecommendation(
            component="API Servers",
            current_cost=current_cost,
            recommended_cost=current_cost,
            savings=0,
            confidence=0.95,
            reasoning="Resource utilization is optimal."
        )
    
    def analyze_database(self) -> ResourceRecommendation:
        """Analyze database resource usage and costs"""
        
        current_instance = "db.r5.4xlarge"  # $1.152/hour
        current_cost = 1.152 * 24 * 30  # $829.44/month
        
        db_cpu_usage = self.metrics.get('db_cpu_usage', 0.35)
        db_memory_usage = self.metrics.get('db_memory_usage', 0.55)
        
        if db_cpu_usage < 0.4 and db_memory_usage < 0.6:
            # Can downgrade to smaller instance
            recommended_instance = "db.r5.2xlarge"  # $0.576/hour
            recommended_cost = 0.576 * 24 * 30  # $414.72/month
            
            return ResourceRecommendation(
                component="Database",
                current_cost=current_cost,
                recommended_cost=recommended_cost,
                savings=current_cost - recommended_cost,
                confidence=0.80,
                reasoning=f"Low resource utilization. Downgrade from {current_instance} to {recommended_instance}."
            )
        
        return ResourceRecommendation(
            component="Database",
            current_cost=current_cost,
            recommended_cost=current_cost,
            savings=0,
            confidence=0.90,
            reasoning="Database sizing is appropriate for current load."
        )
    
    def analyze_redis(self) -> ResourceRecommendation:
        """Analyze Redis cluster costs"""
        
        current_nodes = 6
        node_cost = 0.188 * 24 * 30  # cache.r5.xlarge = $135.36/month
        current_cost = current_nodes * node_cost
        
        redis_memory_usage = self.metrics.get('redis_memory_usage', 0.40)
        
        if redis_memory_usage < 0.5:
            # Can reduce cluster size
            recommended_nodes = 4
            recommended_cost = recommended_nodes * node_cost
            
            return ResourceRecommendation(
                component="Redis Cluster",
                current_cost=current_cost,
                recommended_cost=recommended_cost,
                savings=current_cost - recommended_cost,
                confidence=0.75,
                reasoning=f"Low memory utilization ({redis_memory_usage:.1%}). Reduce cluster from {current_nodes} to {recommended_nodes} nodes."
            )
        
        return ResourceRecommendation(
            component="Redis Cluster",
            current_cost=current_cost,
            recommended_cost=current_cost,
            savings=0,
            confidence=0.85,
            reasoning="Redis cluster sizing is optimal."
        )
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive cost optimization report"""
        
        self.recommendations = [
            self.analyze_api_servers(),
            self.analyze_database(),
            self.analyze_redis()
        ]
        
        total_current_cost = sum(r.current_cost for r in self.recommendations)
        total_recommended_cost = sum(r.recommended_cost for r in self.recommendations)
        total_savings = total_current_cost - total_recommended_cost
        
        return {
            'summary': {
                'total_current_cost': total_current_cost,
                'total_recommended_cost': total_recommended_cost,
                'total_monthly_savings': total_savings,
                'savings_percentage': (total_savings / total_current_cost) * 100
            },
            'recommendations': [
                {
                    'component': r.component,
                    'current_cost': r.current_cost,
                    'recommended_cost': r.recommended_cost,
                    'monthly_savings': r.savings,
                    'confidence': r.confidence,
                    'reasoning': r.reasoning
                }
                for r in self.recommendations
            ]
        }

# Example usage
if __name__ == "__main__":
    # Mock metrics data
    metrics = {
        'api_replicas': 20,
        'avg_cpu_usage': 0.45,
        'avg_memory_usage': 0.60,
        'db_cpu_usage': 0.35,
        'db_memory_usage': 0.55,
        'redis_memory_usage': 0.40
    }
    
    optimizer = CostOptimizer(metrics)
    report = optimizer.generate_report()
    
    print(json.dumps(report, indent=2))
```

### Spot Instance Integration

```yaml
# k8s/spot-instances.yaml
apiVersion: v1
kind: NodePool
metadata:
  name: tml-spot-pool
spec:
  clusterName: tml-production
  nodeClassRef:
    name: tml-spot-nodeclass
  requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot"]
  - key: node.kubernetes.io/instance-type
    operator: In
    values: ["c5.2xlarge", "c5.4xlarge", "c5.9xlarge", "c5.12xlarge"]
  - key: kubernetes.io/arch
    operator: In
    values: ["amd64"]
  limits:
    cpu: 10000
    memory: 10000Gi
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 30s
    expireAfter: 2160h # 90 days

---
# Deployment with spot instance tolerance
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tml-api-spot
  namespace: tml-production
spec:
  replicas: 10
  template:
    spec:
      tolerations:
      - key: "karpenter.sh/capacity-type"
        operator: "Equal"
        value: "spot"
        effect: "NoSchedule"
      nodeSelector:
        karpenter.sh/capacity-type: "spot"
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: tml-api-spot
```

---

## Summary

This scaling guide provides comprehensive strategies for:

1. **Horizontal Scaling** - Multi-replica deployments with load balancing and clustering
2. **Vertical Scaling** - Resource optimization and VPA configuration
3. **Database Scaling** - Read replicas, connection pooling, and sharding
4. **Caching Strategy** - Multi-level caching with Redis clustering
5. **Load Testing** - Comprehensive testing frameworks and benchmarking
6. **Auto-Scaling** - HPA, VPA, and cluster autoscaler configuration
7. **Monitoring** - Custom metrics and Grafana dashboards
8. **Cost Optimization** - Resource right-sizing and spot instance usage

The TML Platform can now scale from single-node development to enterprise-scale production with millions of models and high-throughput processing capabilities.
