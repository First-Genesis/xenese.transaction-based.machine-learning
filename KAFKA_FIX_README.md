# 🔧 Fixing Kafka Issues in Docker

## Common Kafka Problems & Solutions

### ❌ Problem: Kafka container fails to start

**Symptoms:**
- Container exits immediately after starting
- Error: "Cannot assign requested address"
- Connection refused errors

**Solution:**
```bash
# 1. Use the fixed docker-compose file
chmod +x fix-kafka.sh
./fix-kafka.sh

# 2. Or manually fix:
docker-compose -f docker-compose-fixed.yml down
docker volume rm tml_kafka_data tml_zookeeper_data
docker-compose -f docker-compose-fixed.yml up -d
```

### ❌ Problem: Kafka cannot connect to Zookeeper

**Symptoms:**
- Error: "Connection to node -1 could not be established"
- Kafka keeps restarting

**Solution:**
```bash
# Ensure Zookeeper starts first and is healthy
docker-compose -f docker-compose-fixed.yml up -d zookeeper
# Wait 30 seconds
sleep 30
docker-compose -f docker-compose-fixed.yml up -d kafka
```

### ❌ Problem: Port conflicts

**Symptoms:**
- Error: "bind: address already in use"
- Cannot start containers

**Solution:**
```bash
# Check what's using the ports
lsof -i :9092
lsof -i :2181

# Kill conflicting processes or change ports in docker-compose
```

## 📋 Quick Fix Steps

### 1. Stop and Clean Everything
```bash
# Stop all containers
docker-compose down

# Remove problematic containers
docker rm -f tml-kafka tml-zookeeper

# Clean volumes
docker volume rm tml_kafka_data tml_zookeeper_data
```

### 2. Use the Fixed Configuration
```bash
# The fixed configuration includes:
# - Proper health checks
# - Correct listener configuration
# - Memory limits
# - Better error handling

docker-compose -f docker-compose-fixed.yml up -d
```

### 3. Verify Kafka is Working
```bash
# Install Python dependencies
pip install kafka-python

# Run the test script
python test-kafka.py
```

### 4. Monitor Logs
```bash
# Watch Kafka logs
docker logs -f tml-kafka

# Watch all services
docker-compose -f docker-compose-fixed.yml logs -f
```

## 🎯 Key Fixes in docker-compose-fixed.yml

### 1. **Proper Listener Configuration**
```yaml
KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,PLAINTEXT_HOST://0.0.0.0:29092
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
```

### 2. **Health Checks**
```yaml
healthcheck:
  test: ["CMD", "kafka-topics", "--bootstrap-server", "kafka:9092", "--list"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

### 3. **Dependency Management**
```yaml
depends_on:
  zookeeper:
    condition: service_healthy
```

### 4. **Memory Configuration**
```yaml
KAFKA_HEAP_OPTS: "-Xmx512M -Xms512M"
```

## 🚀 Complete Setup from Scratch

```bash
# 1. Clone or navigate to TML directory
cd /Users/rwattyfirstgenesis.com/TML

# 2. Run the fix script
chmod +x fix-kafka.sh
./fix-kafka.sh

# 3. Test Kafka
pip install kafka-python
python test-kafka.py

# 4. Access Kafka UI
open http://localhost:8082
```

## 📊 Service URLs After Fix

| Service | Internal URL | External URL |
|---------|-------------|--------------|
| Kafka | kafka:9092 | localhost:29092 |
| Zookeeper | zookeeper:2181 | localhost:2181 |
| Kafka UI | - | http://localhost:8082 |
| Redis | redis:6379 | localhost:6379 |
| PostgreSQL | postgres:5432 | localhost:5432 |

## 🔍 Debugging Commands

```bash
# Check if containers are running
docker ps | grep tml

# View Kafka topics
docker exec tml-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Create a test topic
docker exec tml-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create --topic test \
  --partitions 3 --replication-factor 1

# Produce a test message
docker exec -it tml-kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic test

# Consume test messages
docker exec -it tml-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic test --from-beginning
```

## ⚠️ Important Notes

1. **Always start Zookeeper before Kafka**
2. **Wait for health checks to pass before starting dependent services**
3. **Use the Kafka UI at http://localhost:8082 for visual debugging**
4. **Check logs if services fail to start**

## 🆘 Still Having Issues?

If Kafka still won't start:

1. **Check Docker resources**:
   - Ensure Docker has at least 4GB RAM allocated
   - Check disk space: `docker system df`

2. **Clean Docker completely**:
   ```bash
   docker system prune -a --volumes
   ```

3. **Try the minimal setup**:
   ```bash
   # Start only Zookeeper and Kafka
   docker-compose -f docker-compose-fixed.yml up -d zookeeper kafka
   ```

4. **Check firewall/antivirus**:
   - Some security software blocks Docker networking
   - Try temporarily disabling to test

## ✅ Success Indicators

You know Kafka is working when:
- ✅ All containers show "healthy" status
- ✅ No restart loops in `docker ps`
- ✅ Can list topics without errors
- ✅ Kafka UI shows cluster information
- ✅ test-kafka.py passes all tests

---

**Need help?** Check logs with `docker logs tml-kafka` and look for ERROR messages!
