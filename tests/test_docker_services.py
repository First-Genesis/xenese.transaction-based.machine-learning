#!/usr/bin/env python3
"""
Test script for Docker services in CI/CD environment.
This is used by GitHub Actions to verify all services are running correctly.
"""

import sys
import time
import os


def test_kafka():
    """Test Kafka connectivity."""
    try:
        from kafka import KafkaProducer, KafkaConsumer

        # Try to connect and send a message
        producer = KafkaProducer(bootstrap_servers="localhost:9092")
        producer.send("test-topic", b"test message")
        producer.flush()
        print("✅ Kafka test passed")
        return True
    except Exception as e:
        print(f"❌ Kafka test failed: {e}")
        return False


def test_redis():
    """Test Redis connectivity."""
    try:
        import redis

        # Connect to Redis
        r = redis.Redis(
            host="localhost", port=6379, password="redis123", decode_responses=True
        )
        r.ping()
        print("✅ Redis test passed")
        return True
    except Exception as e:
        print(f"❌ Redis test failed: {e}")
        return False


def test_postgres():
    """Test PostgreSQL connectivity."""
    try:
        import psycopg2

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost", port=5432, database="tml", user="tml", password="tml123"
        )
        conn.close()
        print("✅ PostgreSQL test passed")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🔍 Testing Docker services...")
    print("-" * 40)

    # Install dependencies if needed
    try:
        import kafka
    except ImportError:
        print("Installing kafka-python...")
        os.system("pip install kafka-python")

    try:
        import redis
    except ImportError:
        print("Installing redis...")
        os.system("pip install redis")

    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...")
        os.system("pip install psycopg2-binary")

    # Run tests
    results = []

    print("\n📊 Running service tests:")
    print("-" * 40)

    results.append(("Kafka", test_kafka()))
    time.sleep(1)

    results.append(("Redis", test_redis()))
    time.sleep(1)

    results.append(("PostgreSQL", test_postgres()))

    # Print summary
    print("\n" + "=" * 40)
    print("📊 Test Summary:")
    print("-" * 40)

    all_passed = True
    for service, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{service}: {status}")
        if not passed:
            all_passed = False

    print("=" * 40)

    if all_passed:
        print("\n🎉 All service tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        print("Check the service logs for more details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
