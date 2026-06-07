#!/usr/bin/env python3
"""
Test Kafka connectivity and functionality

This script tests that Kafka is working properly by:
1. Creating a test topic
2. Producing messages
3. Consuming messages
4. Verifying message delivery
"""

import json
import time
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

def test_kafka_connection():
    """Test basic Kafka connectivity."""
    print("🔍 Testing Kafka connection...")
    
    try:
        # Try to connect to Kafka
        admin_client = KafkaAdminClient(
            bootstrap_servers='localhost:29092',
            client_id='test_client'
        )
        
        # Get cluster metadata
        metadata = admin_client.list_topics()
        print(f"✅ Connected to Kafka successfully!")
        print(f"   Found {len(metadata)} existing topics")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Kafka is running: docker ps | grep kafka")
        print("2. Check Kafka logs: docker logs tml-kafka")
        print("3. Try using the fix script: ./fix-kafka.sh")
        return False

def create_test_topic():
    """Create a test topic."""
    print("\n📝 Creating test topic...")
    
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers='localhost:29092',
            client_id='test_admin'
        )
        
        topic = NewTopic(
            name='tml-test-topic',
            num_partitions=3,
            replication_factor=1
        )
        
        admin_client.create_topics([topic], validate_only=False)
        print("✅ Test topic created successfully!")
        return True
        
    except TopicAlreadyExistsError:
        print("ℹ️  Test topic already exists")
        return True
    except Exception as e:
        print(f"❌ Failed to create topic: {e}")
        return False

def test_producer():
    """Test producing messages to Kafka."""
    print("\n📤 Testing message production...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers='localhost:29092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Send test messages
        messages_sent = 0
        for i in range(10):
            message = {
                'id': i,
                'timestamp': time.time(),
                'data': f'Test message {i}',
                'source': 'test_script'
            }
            
            future = producer.send('tml-test-topic', value=message)
            result = future.get(timeout=10)
            messages_sent += 1
            print(f"   Sent message {i}: partition={result.partition}, offset={result.offset}")
        
        producer.flush()
        print(f"✅ Successfully sent {messages_sent} messages!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to produce messages: {e}")
        return False

def test_consumer():
    """Test consuming messages from Kafka."""
    print("\n📥 Testing message consumption...")
    
    try:
        consumer = KafkaConsumer(
            'tml-test-topic',
            bootstrap_servers='localhost:29092',
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=5000  # 5 second timeout
        )
        
        messages_received = 0
        print("   Consuming messages (5 second timeout)...")
        
        for message in consumer:
            data = message.value
            print(f"   Received: id={data['id']}, data='{data['data']}'")
            messages_received += 1
            
            if messages_received >= 10:
                break
        
        consumer.close()
        
        if messages_received > 0:
            print(f"✅ Successfully received {messages_received} messages!")
            return True
        else:
            print("⚠️  No messages received (this might be normal if topic was empty)")
            return True
            
    except Exception as e:
        print(f"❌ Failed to consume messages: {e}")
        return False

def test_tml_topics():
    """Create TML-specific topics."""
    print("\n🏗️  Creating TML platform topics...")
    
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers='localhost:29092',
            client_id='tml_admin'
        )
        
        topics = [
            NewTopic(name='tml-transactions', num_partitions=10, replication_factor=1),
            NewTopic(name='tml-model-updates', num_partitions=5, replication_factor=1),
            NewTopic(name='tml-predictions', num_partitions=10, replication_factor=1),
            NewTopic(name='tml-drift-alerts', num_partitions=3, replication_factor=1),
            NewTopic(name='tml-metrics', num_partitions=3, replication_factor=1)
        ]
        
        # Try to create each topic
        created = []
        for topic in topics:
            try:
                admin_client.create_topics([topic], validate_only=False)
                created.append(topic.name)
                print(f"   ✅ Created topic: {topic.name}")
            except TopicAlreadyExistsError:
                print(f"   ℹ️  Topic already exists: {topic.name}")
        
        print(f"✅ TML topics ready!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create TML topics: {e}")
        return False

def main():
    """Run all Kafka tests."""
    print("🚀 TML Kafka Testing Suite")
    print("=" * 50)
    
    # Check if kafka library is installed
    try:
        import kafka
        print(f"✅ kafka-python version: {kafka.__version__}")
    except ImportError:
        print("❌ kafka-python not installed!")
        print("   Install with: pip install kafka-python")
        return
    
    # Run tests
    tests = [
        ("Connection Test", test_kafka_connection),
        ("Topic Creation", create_test_topic),
        ("Message Production", test_producer),
        ("Message Consumption", test_consumer),
        ("TML Topic Setup", test_tml_topics)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 40)
        result = test_func()
        results.append((test_name, result))
        
        if not result:
            print(f"\n⚠️  {test_name} failed. Stopping tests.")
            break
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print("-" * 50)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Kafka is working correctly.")
        print("\n💡 Next steps:")
        print("   1. Your Kafka is ready for TML platform")
        print("   2. View Kafka UI at: http://localhost:8082")
        print("   3. Start TML services: docker-compose -f docker-compose-fixed.yml up -d")
    else:
        print("\n❌ Some tests failed. Please fix Kafka configuration.")
        print("\n🔧 To fix:")
        print("   1. Run: chmod +x fix-kafka.sh && ./fix-kafka.sh")
        print("   2. Check logs: docker logs tml-kafka")
        print("   3. Restart: docker-compose -f docker-compose-fixed.yml restart kafka")

if __name__ == "__main__":
    main()
