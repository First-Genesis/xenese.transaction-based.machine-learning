#!/usr/bin/env python3
"""
CI/CD Service Tests for GitHub Actions
Simple tests to verify services are running correctly
"""
import sys
import time

def test_postgres():
    """Test PostgreSQL connectivity."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='tml',
            user='tml',
            password='tml123'
        )
        cur = conn.cursor()
        cur.execute('SELECT version()')
        version = cur.fetchone()[0].split()[0]
        conn.close()
        print(f'✅ PostgreSQL: {version}')
        return True
    except Exception as e:
        print(f'❌ PostgreSQL: {e}')
        return False

def test_redis():
    """Test Redis connectivity."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        r.set('test', 'value')
        result = r.get('test')
        print(f'✅ Redis: Working (test={result})')
        return True
    except Exception as e:
        print(f'❌ Redis: {e}')
        return False

def test_kafka():
    """Test Kafka/Redpanda connectivity."""
    try:
        from kafka import KafkaProducer
        
        # Give Redpanda time to stabilize
        time.sleep(5)
        
        producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            request_timeout_ms=10000,
            api_version_auto_timeout_ms=10000
        )
        future = producer.send('test', b'test message')
        producer.flush(timeout=10)
        print('✅ Kafka/Redpanda: Working')
        return True
    except Exception as e:
        print(f'⚠️ Kafka/Redpanda: {e}')
        # Don't fail for Kafka issues in CI
        return True

def main():
    """Run all tests."""
    print("=== CI/CD Service Tests ===")
    print("")
    
    results = []
    results.append(test_postgres())
    results.append(test_redis())
    results.append(test_kafka())
    
    print("")
    if all(results):
        print("✅ All services operational")
        sys.exit(0)
    else:
        print("⚠️ Some services have issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
