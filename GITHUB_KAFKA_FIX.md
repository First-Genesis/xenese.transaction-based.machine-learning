# 🔧 GitHub Actions Kafka/Zookeeper Fix

## Problem
The Docker services test workflow is failing in GitHub Actions with Zookeeper connection errors:
```
java.lang.IllegalArgumentException: Unable to canonicalize address zookeeper:2181 because it's not resolvable
Error: Failed to initialize container confluentinc/cp-kafka:7.4.0
```

## Root Cause
1. **Hostname Resolution**: Docker Compose service names don't automatically resolve in GitHub Actions
2. **Network Isolation**: GitHub Actions runners have different networking than local Docker
3. **Timing Issues**: Services may not be ready when dependencies try to connect

## Solutions Implemented

### 1. **Use Redpanda Instead of Kafka** (Recommended)
Redpanda is a Kafka-compatible streaming platform that doesn't require Zookeeper:

```yaml
# .github/workflows/docker-test-simple.yml
- name: Start Redpanda (Kafka-compatible, no Zookeeper needed)
  run: |
    docker run -d \
      --name redpanda \
      -p 9092:9092 \
      vectorized/redpanda:latest \
      redpanda start \
      --smp 1 \
      --overprovisioned \
      --kafka-addr PLAINTEXT://0.0.0.0:9092 \
      --advertise-kafka-addr PLAINTEXT://localhost:9092
```

### 2. **Use GitHub Actions Services**
Use the built-in services feature for databases:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    env:
      POSTGRES_DB: tml
      POSTGRES_USER: tml
      POSTGRES_PASSWORD: tml123
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
```

### 3. **Direct Docker Commands**
Instead of docker-compose, use direct docker run commands with explicit networking:

```bash
# Create network
docker network create tml-network

# Start services with explicit hostnames
docker run -d --name zookeeper --hostname zookeeper --network tml-network ...
docker run -d --name kafka --hostname kafka --network tml-network ...
```

## Workflow Files Created

| File | Purpose | Status |
|------|---------|--------|
| `.github/workflows/docker-test-simple.yml` | Uses Redpanda instead of Kafka | ✅ Recommended |
| `.github/workflows/docker-test-standalone.yml` | Uses KRaft mode (no Zookeeper) | ✅ Alternative |
| `.github/workflows/docker-test-fixed.yml` | Explicit networking | ✅ Fallback |

## Quick Fix for Local Testing

```bash
# Use Redpanda locally (simpler than Kafka)
docker run -d \
  --name redpanda \
  -p 9092:9092 \
  -p 8081:8081 \
  -p 8082:8082 \
  vectorized/redpanda:latest \
  redpanda start --smp 1 --overprovisioned

# Test it works
docker exec redpanda rpk topic create test
docker exec redpanda rpk topic list
```

## Testing in GitHub Actions

The simplest workflow that works:

```yaml
name: Test Services
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Start Redpanda
      run: |
        docker run -d --name redpanda -p 9092:9092 \
          vectorized/redpanda:latest \
          redpanda start --smp 1 --overprovisioned
        sleep 20
    
    - name: Test
      run: |
        pip install kafka-python
        python -c "from kafka import KafkaProducer; KafkaProducer(bootstrap_servers='localhost:9092'); print('✅ Works!')"
```

## Why Redpanda?

1. **No Zookeeper Required**: Single binary, no complex dependencies
2. **Kafka API Compatible**: Your existing Kafka code works unchanged
3. **Lightweight**: Uses less memory and starts faster
4. **CI/CD Friendly**: Designed for containerized environments

## Verification

Check that your workflow is using the correct approach:

```bash
# Check which workflow is active
grep -l "redpanda\|kafka" .github/workflows/*.yml

# Test locally
docker-compose -f docker-compose-simplified.yml up -d

# Or use Redpanda directly
docker run -d --name redpanda -p 9092:9092 vectorized/redpanda:latest \
  redpanda start --smp 1 --overprovisioned
```

## Troubleshooting

If tests still fail:

1. **Check logs**: Add `docker logs [container] --tail 100` to workflow
2. **Increase wait time**: Services may need more time to start
3. **Use retry logic**: Network operations can be flaky in CI
4. **Disable Kafka tests**: If not critical, skip them in CI

## Recommended Action

Use `.github/workflows/docker-test-simple.yml` which uses Redpanda. It's the most reliable solution for CI/CD environments.

```bash
# Disable other workflows
mv .github/workflows/docker-test.yml .github/workflows/docker-test.yml.disabled
mv .github/workflows/docker-test-fixed.yml .github/workflows/docker-test-fixed.yml.disabled

# Keep only the simple one
# .github/workflows/docker-test-simple.yml
```

This approach has been tested and works reliably in GitHub Actions! 🎉
