# 🔧 GitHub Actions Kafka/Zookeeper DNS Resolution Fix

## ❌ The Error
```
java.net.UnknownHostException: zookeeper: Name or service not known
java.lang.IllegalArgumentException: Unable to canonicalize address zookeeper:2181 because it's not resolvable
Service container kafka failed.
Error: One or more containers failed to start.
```

## 🔍 Root Cause

The `confluentinc/cp-kafka:7.4.0` image requires Zookeeper, but in GitHub Actions:
1. Service containers don't automatically resolve each other's hostnames
2. Kafka expects `zookeeper:2181` but can't resolve the hostname
3. There's no Zookeeper service defined (or it can't communicate)

## ✅ The Solution: Use Redpanda Instead

**Redpanda** is a Kafka API-compatible streaming platform that:
- ✅ Doesn't require Zookeeper
- ✅ Works perfectly in GitHub Actions
- ✅ 100% compatible with Kafka clients
- ✅ Lighter and faster than Kafka

## 📝 How to Fix Your Workflows

### Step 1: Remove Kafka Service Container

**BEFORE (Broken):**
```yaml
services:
  kafka:
    image: confluentinc/cp-kafka:7.4.0
    env:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181  # ❌ Can't resolve
```

**AFTER (Fixed):**
```yaml
services:
  # DO NOT ADD KAFKA SERVICE HERE!
  # Use Redpanda in steps instead
```

### Step 2: Add Redpanda in Steps

Add this step before running tests:

```yaml
- name: Start Redpanda (Kafka replacement)
  run: |
    docker run -d \
      --name redpanda \
      -p 9092:9092 \
      vectorized/redpanda:latest \
      redpanda start \
      --smp 1 \
      --reserve-memory 0M \
      --overprovisioned \
      --kafka-addr PLAINTEXT://0.0.0.0:9092 \
      --advertise-kafka-addr PLAINTEXT://localhost:9092
    
    # Wait for Redpanda to be ready
    for i in {1..30}; do
      if docker exec redpanda rpk cluster info &>/dev/null; then
        echo "Redpanda is ready!"
        break
      fi
      sleep 2
    done
```

## 🔄 Complete Working Example

```yaml
name: CI Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
      
      # NO KAFKA SERVICE HERE!
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Start Redpanda
      run: |
        docker run -d --name redpanda -p 9092:9092 \
          vectorized/redpanda:latest \
          redpanda start --smp 1 --overprovisioned
        sleep 20  # Wait for startup
    
    - name: Run tests
      run: |
        # Your tests here
        # Kafka clients connect to localhost:9092 as usual
      env:
        KAFKA_BOOTSTRAP_SERVERS: localhost:9092
```

## ⚡ Quick Commands

### Test if Redpanda is working:
```bash
docker exec redpanda rpk cluster info
docker exec redpanda rpk topic list
```

### Create a topic:
```bash
docker exec redpanda rpk topic create test-topic
```

### Python test:
```python
from kafka import KafkaProducer
producer = KafkaProducer(bootstrap_servers='localhost:9092')
producer.send('test', b'message')
print("✅ Redpanda works with Kafka clients!")
```

## 📊 Comparison

| Feature | Kafka + Zookeeper | Redpanda |
|---------|------------------|----------|
| GitHub Actions Compatible | ❌ DNS issues | ✅ Works perfectly |
| Setup Complexity | Complex | Simple |
| Memory Usage | 1GB+ | 256MB |
| Startup Time | 30-60s | 5-10s |
| Kafka API Compatible | Yes | Yes |
| Dependencies | Requires Zookeeper | None |

## 🚨 Important Notes

1. **Never use Kafka service containers in GitHub Actions** - They will fail with Zookeeper DNS issues
2. **Always use Redpanda as a regular container** - Start it in a step, not as a service
3. **Your Kafka code doesn't change** - Redpanda is 100% Kafka API compatible

## 🎯 Summary

The fix is simple:
1. **Remove** any Kafka/Zookeeper service containers
2. **Add** Redpanda as a step before tests
3. **Use** `localhost:9092` as before

Your tests will now pass without any Zookeeper connection errors! 🎉
