#!/usr/bin/env python3
"""
TML MQTT Gateway Functional Tests
Comprehensive end-to-end testing following agile development principles
"""

import asyncio
import json
import time
import pytest
from datetime import datetime
from typing import Dict, Any

import paho.mqtt.client as mqtt
from kafka import KafkaConsumer
import psycopg2
import redis

from tml_mqtt_gateway.config import TMLGatewayConfig
from tml_mqtt_gateway.gateway import TMLMQTTGateway


class IoTDeviceSimulator:
    """Simulates IoT devices for testing"""
    
    def __init__(self, device_id: str, device_type: str, mqtt_config: Dict[str, Any]):
        self.device_id = device_id
        self.device_type = device_type
        self.mqtt_config = mqtt_config
        self.client = None
        self.connected = False
        
    def connect(self):
        """Connect to MQTT broker"""
        self.client = mqtt.Client(client_id=f"test_{self.device_id}")
        
        if self.mqtt_config.get('username') and self.mqtt_config.get('password'):
            self.client.username_pw_set(
                self.mqtt_config['username'],
                self.mqtt_config['password']
            )
        
        def on_connect(client, userdata, flags, rc):
            self.connected = (rc == 0)
        
        self.client.on_connect = on_connect
        
        self.client.connect(
            self.mqtt_config['host'],
            self.mqtt_config['port'],
            60
        )
        
        self.client.loop_start()
        
        # Wait for connection
        timeout = time.time() + 10
        while not self.connected and time.time() < timeout:
            time.sleep(0.1)
        
        return self.connected
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def send_telemetry(self, data: Dict[str, Any]):
        """Send telemetry data"""
        if not self.connected:
            return False
        
        topic = f"tml/devices/{self.device_type}/{self.device_id}/telemetry"
        
        message = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        result = self.client.publish(topic, json.dumps(message), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def send_status(self, status: str, health_data: Dict[str, Any] = None):
        """Send device status"""
        if not self.connected:
            return False
        
        topic = f"tml/devices/{self.device_type}/{self.device_id}/status"
        
        message = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "health": health_data or {}
        }
        
        result = self.client.publish(topic, json.dumps(message), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS


class FunctionalTestSuite:
    """Comprehensive functional test suite for TML MQTT Gateway"""
    
    def __init__(self):
        self.config = None
        self.gateway = None
        self.test_devices = []
        self.kafka_consumer = None
        self.db_connection = None
        self.redis_client = None
        
        # Test metrics
        self.test_results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'performance_metrics': {},
            'errors': []
        }
    
    async def setup(self):
        """Setup test environment"""
        print("🔧 Setting up functional test environment...")
        
        # Load test configuration
        self.config = TMLGatewayConfig()
        
        # Override with test settings
        self.config.mqtt.host = "localhost"
        self.config.kafka.bootstrap_servers = "localhost:29092"
        self.config.database.host = "localhost"
        self.config.redis.host = "localhost"
        
        # Initialize gateway
        self.gateway = TMLMQTTGateway(self.config)
        
        # Setup external connections for verification
        await self._setup_verification_connections()
        
        print("✅ Test environment setup complete")
    
    async def _setup_verification_connections(self):
        """Setup connections for test verification"""
        try:
            # Kafka consumer for message verification
            self.kafka_consumer = KafkaConsumer(
                'tml.iot.telemetry',
                'tml.iot.device_status',
                bootstrap_servers=self.config.kafka.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=5000,
                auto_offset_reset='latest'
            )
            
            # Database connection for device verification
            self.db_connection = psycopg2.connect(
                host=self.config.database.host,
                port=self.config.database.port,
                database=self.config.database.database,
                user=self.config.database.username,
                password=self.config.database.password
            )
            
            # Redis client for cache verification
            self.redis_client = redis.Redis(
                host=self.config.redis.host,
                port=self.config.redis.port,
                db=self.config.redis.db,
                decode_responses=True
            )
            
            print("✅ Verification connections established")
            
        except Exception as e:
            print(f"❌ Failed to setup verification connections: {e}")
            raise
    
    async def test_01_gateway_initialization(self):
        """Test 1: Gateway Initialization and Component Setup"""
        print("\n📋 Test 1: Gateway Initialization")
        
        try:
            start_time = time.time()
            
            # Initialize gateway
            await self.gateway.initialize()
            
            initialization_time = time.time() - start_time
            
            # Verify components are initialized
            assert self.gateway.mqtt_client is not None, "MQTT client not initialized"
            assert self.gateway.kafka_producer is not None, "Kafka producer not initialized"
            assert self.gateway.device_manager is not None, "Device manager not initialized"
            assert self.gateway.api_server is not None, "API server not initialized"
            
            self.test_results['performance_metrics']['initialization_time'] = initialization_time
            
            print(f"   ✅ Gateway initialized successfully in {initialization_time:.2f}s")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ Gateway initialization failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_02_mqtt_connection(self):
        """Test 2: MQTT Broker Connection and Subscription"""
        print("\n📋 Test 2: MQTT Connection")
        
        try:
            start_time = time.time()
            
            # Connect to MQTT broker
            await self.gateway.mqtt_client.connect()
            
            connection_time = time.time() - start_time
            
            # Verify connection
            assert self.gateway.mqtt_client.connected, "MQTT client not connected"
            
            # Verify subscriptions
            await asyncio.sleep(2)  # Allow time for subscriptions
            
            mqtt_status = self.gateway.mqtt_client.get_status()
            assert mqtt_status['connected'], "MQTT status shows disconnected"
            assert len(mqtt_status['subscribed_topics']) > 0, "No topics subscribed"
            
            self.test_results['performance_metrics']['mqtt_connection_time'] = connection_time
            
            print(f"   ✅ MQTT connected successfully in {connection_time:.2f}s")
            print(f"   📊 Subscribed to {len(mqtt_status['subscribed_topics'])} topics")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ MQTT connection failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_03_device_simulation(self):
        """Test 3: IoT Device Simulation and Registration"""
        print("\n📋 Test 3: Device Simulation")
        
        try:
            # Create test devices
            device_configs = [
                {"id": "temp_sensor_001", "type": "sensor"},
                {"id": "camera_001", "type": "camera"},
                {"id": "valve_001", "type": "actuator"}
            ]
            
            mqtt_config = {
                'host': self.config.mqtt.host,
                'port': self.config.mqtt.port,
                'username': self.config.mqtt.username,
                'password': self.config.mqtt.password
            }
            
            connected_devices = 0
            
            for device_config in device_configs:
                device = IoTDeviceSimulator(
                    device_config['id'],
                    device_config['type'],
                    mqtt_config
                )
                
                if device.connect():
                    self.test_devices.append(device)
                    connected_devices += 1
                    print(f"   ✅ Device {device_config['id']} connected")
                else:
                    print(f"   ❌ Device {device_config['id']} failed to connect")
            
            assert connected_devices == len(device_configs), f"Only {connected_devices}/{len(device_configs)} devices connected"
            
            self.test_results['performance_metrics']['devices_connected'] = connected_devices
            
            print(f"   ✅ All {connected_devices} test devices connected successfully")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ Device simulation failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_04_message_processing(self):
        """Test 4: End-to-End Message Processing"""
        print("\n📋 Test 4: Message Processing Pipeline")
        
        try:
            # Start gateway processing
            gateway_task = asyncio.create_task(self.gateway.start())
            await asyncio.sleep(3)  # Allow gateway to fully start
            
            # Send test messages
            messages_sent = 0
            start_time = time.time()
            
            for device in self.test_devices:
                # Send telemetry
                telemetry_data = {
                    "temperature": 23.5,
                    "humidity": 45.2,
                    "battery_level": 87
                }
                
                if device.send_telemetry(telemetry_data):
                    messages_sent += 1
                
                # Send status
                health_data = {
                    "signal_strength": -65,
                    "memory_usage": 45,
                    "uptime": 3600
                }
                
                if device.send_status("online", health_data):
                    messages_sent += 1
            
            # Allow time for processing
            await asyncio.sleep(5)
            
            processing_time = time.time() - start_time
            
            # Verify messages were processed
            gateway_status = self.gateway.get_status()
            processed_count = gateway_status['metrics']['gateway']['total_messages_processed']
            
            assert processed_count > 0, "No messages were processed"
            assert messages_sent > 0, "No messages were sent"
            
            # Calculate throughput
            throughput = processed_count / processing_time if processing_time > 0 else 0
            
            self.test_results['performance_metrics'].update({
                'messages_sent': messages_sent,
                'messages_processed': processed_count,
                'processing_time': processing_time,
                'throughput_msg_per_sec': throughput
            })
            
            print(f"   ✅ Processed {processed_count} messages in {processing_time:.2f}s")
            print(f"   📊 Throughput: {throughput:.1f} messages/second")
            self._record_test_pass()
            
            # Stop gateway
            self.gateway.shutdown_event.set()
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Message processing failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_05_kafka_integration(self):
        """Test 5: Kafka Message Delivery Verification"""
        print("\n📋 Test 5: Kafka Integration")
        
        try:
            # Check for messages in Kafka topics
            kafka_messages = []
            
            # Consume messages with timeout
            for message in self.kafka_consumer:
                kafka_messages.append(message.value)
                if len(kafka_messages) >= 3:  # Expect at least 3 messages
                    break
            
            assert len(kafka_messages) > 0, "No messages found in Kafka topics"
            
            # Verify message structure
            for msg in kafka_messages:
                assert 'device_id' in msg, "Message missing device_id"
                assert 'timestamp' in msg, "Message missing timestamp"
                assert '_kafka_metadata' in msg, "Message missing Kafka metadata"
            
            self.test_results['performance_metrics']['kafka_messages_received'] = len(kafka_messages)
            
            print(f"   ✅ Received {len(kafka_messages)} messages from Kafka")
            print(f"   📊 Message structure validation passed")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ Kafka integration failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_06_database_integration(self):
        """Test 6: Database Device Registration Verification"""
        print("\n📋 Test 6: Database Integration")
        
        try:
            cursor = self.db_connection.cursor()
            
            # Check if devices were registered
            cursor.execute("SELECT COUNT(*) FROM devices")
            device_count = cursor.fetchone()[0]
            
            assert device_count > 0, "No devices found in database"
            
            # Verify device data
            cursor.execute("""
                SELECT device_id, device_type, status, last_seen 
                FROM devices 
                ORDER BY created_at DESC
            """)
            
            devices = cursor.fetchall()
            
            # Verify at least one device has recent activity
            recent_devices = [d for d in devices if d[2] == 'online']  # status = 'online'
            assert len(recent_devices) > 0, "No devices marked as online"
            
            self.test_results['performance_metrics']['database_devices'] = device_count
            
            print(f"   ✅ Found {device_count} devices in database")
            print(f"   📊 {len(recent_devices)} devices currently online")
            self._record_test_pass()
            
            cursor.close()
            
        except Exception as e:
            print(f"   ❌ Database integration failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_07_api_endpoints(self):
        """Test 7: REST API Functionality"""
        print("\n📋 Test 7: API Endpoints")
        
        try:
            import httpx
            
            base_url = f"http://{self.config.gateway.api_host}:{self.config.gateway.api_port}"
            
            async with httpx.AsyncClient() as client:
                # Test health endpoint
                response = await client.get(f"{base_url}/health")
                assert response.status_code == 200, f"Health check failed: {response.status_code}"
                
                health_data = response.json()
                assert health_data['status'] == 'healthy', "Health status not healthy"
                
                # Test status endpoint
                response = await client.get(f"{base_url}/status")
                assert response.status_code == 200, f"Status check failed: {response.status_code}"
                
                status_data = response.json()
                assert 'gateway_id' in status_data, "Status missing gateway_id"
                
                # Test metrics endpoint
                response = await client.get(f"{base_url}/metrics")
                assert response.status_code == 200, f"Metrics check failed: {response.status_code}"
                
                metrics_data = response.json()
                assert 'mqtt' in metrics_data, "Metrics missing MQTT data"
                assert 'kafka' in metrics_data, "Metrics missing Kafka data"
            
            print(f"   ✅ All API endpoints responding correctly")
            print(f"   📊 Health, status, and metrics endpoints validated")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ API endpoints test failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    async def test_08_performance_benchmarks(self):
        """Test 8: Performance Benchmarks and Metrics"""
        print("\n📋 Test 8: Performance Benchmarks")
        
        try:
            metrics = self.test_results['performance_metrics']
            
            # Performance assertions
            assert metrics.get('initialization_time', 999) < 30, "Initialization too slow"
            assert metrics.get('mqtt_connection_time', 999) < 10, "MQTT connection too slow"
            assert metrics.get('throughput_msg_per_sec', 0) > 1, "Throughput too low"
            
            # Calculate overall performance score
            performance_score = 100
            
            if metrics.get('initialization_time', 0) > 10:
                performance_score -= 10
            if metrics.get('mqtt_connection_time', 0) > 5:
                performance_score -= 10
            if metrics.get('throughput_msg_per_sec', 0) < 10:
                performance_score -= 20
            
            self.test_results['performance_metrics']['performance_score'] = performance_score
            
            print(f"   ✅ Performance benchmarks passed")
            print(f"   📊 Overall performance score: {performance_score}/100")
            self._record_test_pass()
            
        except Exception as e:
            print(f"   ❌ Performance benchmarks failed: {e}")
            self._record_test_fail(str(e))
            raise
    
    def _record_test_pass(self):
        """Record a test pass"""
        self.test_results['tests_run'] += 1
        self.test_results['tests_passed'] += 1
    
    def _record_test_fail(self, error: str):
        """Record a test failure"""
        self.test_results['tests_run'] += 1
        self.test_results['tests_failed'] += 1
        self.test_results['errors'].append(error)
    
    async def cleanup(self):
        """Cleanup test environment"""
        print("\n🧹 Cleaning up test environment...")
        
        # Disconnect test devices
        for device in self.test_devices:
            device.disconnect()
        
        # Close verification connections
        if self.kafka_consumer:
            self.kafka_consumer.close()
        
        if self.db_connection:
            self.db_connection.close()
        
        if self.redis_client:
            self.redis_client.close()
        
        # Stop gateway
        if self.gateway:
            await self.gateway.stop()
        
        print("✅ Cleanup complete")
    
    def print_final_report(self):
        """Print comprehensive test report"""
        print("\n" + "="*80)
        print("🎯 TML MQTT GATEWAY - FUNCTIONAL TEST REPORT")
        print("="*80)
        
        results = self.test_results
        
        print(f"\n📊 TEST SUMMARY:")
        print(f"   Tests Run: {results['tests_run']}")
        print(f"   Tests Passed: {results['tests_passed']}")
        print(f"   Tests Failed: {results['tests_failed']}")
        print(f"   Success Rate: {(results['tests_passed']/results['tests_run']*100):.1f}%")
        
        print(f"\n⚡ PERFORMANCE METRICS:")
        metrics = results['performance_metrics']
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"   {key.replace('_', ' ').title()}: {value:.2f}")
            else:
                print(f"   {key.replace('_', ' ').title()}: {value}")
        
        if results['errors']:
            print(f"\n❌ ERRORS:")
            for i, error in enumerate(results['errors'], 1):
                print(f"   {i}. {error}")
        
        # Overall assessment
        success_rate = results['tests_passed'] / results['tests_run'] * 100
        performance_score = metrics.get('performance_score', 0)
        
        print(f"\n🎯 OVERALL ASSESSMENT:")
        if success_rate == 100 and performance_score >= 80:
            print("   ✅ EXCELLENT - Production ready!")
        elif success_rate >= 90 and performance_score >= 70:
            print("   ✅ GOOD - Ready with minor optimizations")
        elif success_rate >= 80:
            print("   ⚠️  ACCEPTABLE - Needs improvements")
        else:
            print("   ❌ NEEDS WORK - Major issues found")
        
        print("="*80)


async def run_functional_tests():
    """Run complete functional test suite"""
    print("🚀 TML MQTT Gateway - Phase 1 Functional Testing")
    print("Following agile development principles with comprehensive validation")
    print("="*80)
    
    test_suite = FunctionalTestSuite()
    
    try:
        # Setup
        await test_suite.setup()
        
        # Run all tests
        await test_suite.test_01_gateway_initialization()
        await test_suite.test_02_mqtt_connection()
        await test_suite.test_03_device_simulation()
        await test_suite.test_04_message_processing()
        await test_suite.test_05_kafka_integration()
        await test_suite.test_06_database_integration()
        await test_suite.test_07_api_endpoints()
        await test_suite.test_08_performance_benchmarks()
        
    except Exception as e:
        print(f"\n💥 Critical test failure: {e}")
    
    finally:
        # Cleanup and report
        await test_suite.cleanup()
        test_suite.print_final_report()


if __name__ == "__main__":
    asyncio.run(run_functional_tests())
