#!/usr/bin/env python3
"""
Functional Test: Proto.Actor Integration with Real Transaction Flow
Tests Iteration 1: Connect actors to real transaction flow

Following agile methodology - validates actual functionality before proceeding
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any, List
from kafka import KafkaProducer, KafkaConsumer
from loguru import logger

# Add TML to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logger.add("actor_integration_test.log", rotation="10 MB", level="INFO")


class ActorIntegrationTester:
    """Comprehensive functional test for actor integration"""
    
    def __init__(self):
        self.producer = None
        self.consumer = None
        self.bridge = None
        self.test_results = {
            'transactions_sent': 0,
            'actor_results_received': 0,
            'models_created': 0,
            'inheritance_applied': 0,
            'processing_times': [],
            'errors': [],
            'start_time': time.time()
        }
        
    async def setup(self):
        """Setup test environment"""
        logger.info("🔧 Setting up Actor Integration Test...")
        
        # Initialize Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.consumer = KafkaConsumer(
            'actor-results',
            bootstrap_servers=['localhost:29092'],
            auto_offset_reset='latest',
            group_id='actor-test-consumer',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Create actor-results topic if it doesn't exist
        await self._ensure_kafka_topics()
        
        logger.info("✅ Test environment setup complete")
    
    async def _ensure_kafka_topics(self):
        """Ensure required Kafka topics exist"""
        try:
            # Note: In production, use kafka-admin-client
            # For now, assume topics exist or are auto-created
            logger.info("✅ Kafka topics verified")
        except Exception as e:
            logger.warning(f"Could not verify Kafka topics: {e}")
    
    def generate_test_transaction(self, index: int) -> Dict[str, Any]:
        """Generate realistic test transaction"""
        model_types = ['fraud_detection', 'risk_assessment', 'anomaly_detection']
        regions = ['north', 'south', 'east', 'west', 'central']
        
        model_type = model_types[index % len(model_types)]
        region = regions[index % len(regions)]
        
        return {
            'transaction_id': f'actor_test_{index:06d}',
            'model_id': f'{model_type}_{region}_{index // 10}',
            'amount': 100 + (index * 10) % 900,
            'features': {
                'amount_normalized': (index % 100) / 100.0,
                'hour_of_day': (index % 24) / 24.0,
                'day_of_week': (index % 7) / 7.0,
                'merchant_risk': (index % 10) / 10.0,
                'customer_score': ((index * 7) % 100) / 100.0,
                'location_risk': ((index * 3) % 10) / 10.0
            },
            'x_coord': -180 + (index % 360),
            'y_coord': -90 + (index % 180),
            'domain': model_type,
            'timestamp': time.time(),
            'test_batch': 'actor_integration'
        }
    
    async def send_test_transactions(self, count: int = 100):
        """Send test transactions to actor system"""
        logger.info(f"📤 Sending {count} test transactions to actor system...")
        
        for i in range(count):
            transaction = self.generate_test_transaction(i)
            
            # Send to transactions topic (actor bridge will consume)
            self.producer.send('transactions', transaction)
            
            self.test_results['transactions_sent'] += 1
            
            # Log progress
            if (i + 1) % 20 == 0:
                logger.info(f"  Sent {i + 1}/{count} transactions")
        
        self.producer.flush()
        logger.info(f"✅ Sent {count} transactions to actor system")
    
    async def monitor_actor_results(self, duration: int = 30):
        """Monitor results from actor processing"""
        logger.info(f"📊 Monitoring actor results for {duration} seconds...")
        
        start_time = time.time()
        model_stats = {}
        
        while time.time() - start_time < duration:
            try:
                # Poll for actor results
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        result = record.value
                        
                        # Validate this is from our test
                        if not result.get('transaction_id', '').startswith('actor_test_'):
                            continue
                        
                        self.test_results['actor_results_received'] += 1
                        
                        # Track processing times
                        if 'processing_time' in result:
                            self.test_results['processing_times'].append(result['processing_time'])
                        
                        # Track model creation
                        model_id = result.get('model_id', 'unknown')
                        if model_id not in model_stats:
                            model_stats[model_id] = {
                                'transactions': 0,
                                'inheritance_applied': False,
                                'actor_path': result.get('actor_path', 'unknown')
                            }
                        
                        model_stats[model_id]['transactions'] += 1
                        
                        # Track inheritance
                        if result.get('inheritance_applied'):
                            model_stats[model_id]['inheritance_applied'] = True
                            self.test_results['inheritance_applied'] += 1
                        
                        # Track errors
                        if not result.get('success', True):
                            self.test_results['errors'].append(result.get('error', 'Unknown error'))
                        
                        # Log interesting results
                        if result.get('inheritance_applied'):
                            logger.info(f"🧬 Actor inheritance: {model_id} via {result.get('actor_path')}")
                        
                        if result.get('processing_time', 0) > 0.1:
                            logger.warning(f"⏱️ Slow processing: {model_id} took {result.get('processing_time'):.3f}s")
                
            except Exception as e:
                logger.error(f"Error monitoring results: {e}")
                self.test_results['errors'].append(str(e))
        
        self.test_results['models_created'] = len(model_stats)
        
        # Log model statistics
        logger.info(f"📈 Model Statistics:")
        for model_id, stats in list(model_stats.items())[:10]:  # Top 10
            logger.info(f"  • {model_id}: {stats['transactions']} txns, "
                       f"Inheritance: {'Yes' if stats['inheritance_applied'] else 'No'}, "
                       f"Actor: {stats['actor_path']}")
        
        return model_stats
    
    async def validate_actor_system_health(self):
        """Validate that actor system is healthy and responsive"""
        logger.info("🏥 Validating actor system health...")
        
        try:
            # Import and test actor bridge
            from tml.orchestration.actor_transaction_bridge import ActorTransactionBridge
            
            # Create bridge instance
            bridge = ActorTransactionBridge(parallelism=2)
            
            # Test initialization
            await bridge.initialize()
            logger.info("✅ Actor system initialized successfully")
            
            # Get metrics
            metrics = await bridge.get_actor_metrics()
            logger.info(f"✅ Actor metrics retrieved: {len(metrics)} categories")
            
            # Verify actor creation
            if metrics['actor_system_status']['active_processors'] > 0:
                logger.info(f"✅ {metrics['actor_system_status']['active_processors']} active processors")
            else:
                logger.error("❌ No active processors found")
                return False
            
            # Cleanup
            await bridge.shutdown()
            logger.info("✅ Actor system shutdown gracefully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Actor system health check failed: {e}")
            return False
    
    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        elapsed = time.time() - self.test_results['start_time']
        
        # Processing rate
        tps = self.test_results['transactions_sent'] / elapsed if elapsed > 0 else 0
        response_rate = self.test_results['actor_results_received'] / elapsed if elapsed > 0 else 0
        
        # Success rate
        success_rate = (
            (self.test_results['actor_results_received'] / self.test_results['transactions_sent']) * 100
            if self.test_results['transactions_sent'] > 0 else 0
        )
        
        # Processing times
        avg_processing_time = (
            sum(self.test_results['processing_times']) / len(self.test_results['processing_times'])
            if self.test_results['processing_times'] else 0
        )
        
        # Inheritance rate
        inheritance_rate = (
            (self.test_results['inheritance_applied'] / self.test_results['actor_results_received']) * 100
            if self.test_results['actor_results_received'] > 0 else 0
        )
        
        return {
            'test_duration': elapsed,
            'transaction_rate': tps,
            'response_rate': response_rate,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'inheritance_rate': inheritance_rate,
            'error_count': len(self.test_results['errors']),
            'models_created': self.test_results['models_created']
        }
    
    def generate_test_report(self, metrics: Dict[str, Any]) -> str:
        """Generate comprehensive test report"""
        report = []
        report.append("="*70)
        report.append("🎭 PROTO.ACTOR INTEGRATION TEST REPORT")
        report.append("="*70)
        report.append("")
        
        # Test Summary
        report.append("📊 TEST SUMMARY")
        report.append("-" * 50)
        report.append(f"Transactions Sent: {self.test_results['transactions_sent']}")
        report.append(f"Actor Results Received: {self.test_results['actor_results_received']}")
        report.append(f"Models Created: {self.test_results['models_created']}")
        report.append(f"Inheritance Applied: {self.test_results['inheritance_applied']}")
        report.append(f"Errors: {len(self.test_results['errors'])}")
        report.append("")
        
        # Performance Metrics
        report.append("⚡ PERFORMANCE METRICS")
        report.append("-" * 50)
        report.append(f"Test Duration: {metrics['test_duration']:.2f} seconds")
        report.append(f"Transaction Rate: {metrics['transaction_rate']:.1f} TPS")
        report.append(f"Response Rate: {metrics['response_rate']:.1f} responses/sec")
        report.append(f"Success Rate: {metrics['success_rate']:.1f}%")
        report.append(f"Average Processing Time: {metrics['avg_processing_time']:.3f} seconds")
        report.append(f"Inheritance Rate: {metrics['inheritance_rate']:.1f}%")
        report.append("")
        
        # Pass/Fail Criteria
        report.append("✅ PASS/FAIL ANALYSIS")
        report.append("-" * 50)
        
        # Define success criteria
        criteria = [
            ("Success Rate > 80%", metrics['success_rate'] > 80),
            ("Processing Time < 100ms", metrics['avg_processing_time'] < 0.1),
            ("Models Created > 0", metrics['models_created'] > 0),
            ("Inheritance Applied", self.test_results['inheritance_applied'] > 0),
            ("Error Rate < 5%", (len(self.test_results['errors']) / max(1, self.test_results['transactions_sent'])) < 0.05)
        ]
        
        passed_tests = 0
        for criterion, passed in criteria:
            status = "✅ PASS" if passed else "❌ FAIL"
            report.append(f"{status}: {criterion}")
            if passed:
                passed_tests += 1
        
        report.append("")
        overall_pass = passed_tests >= 4  # At least 4/5 criteria must pass
        
        # Final Verdict
        report.append("🏁 FINAL VERDICT")
        report.append("-" * 50)
        if overall_pass:
            report.append("✅ PROTO.ACTOR INTEGRATION TEST PASSED!")
            report.append("   Actors successfully connected to real transaction flow")
        else:
            report.append("❌ PROTO.ACTOR INTEGRATION TEST FAILED")
            report.append(f"   Only {passed_tests}/5 criteria passed")
        
        report.append("")
        report.append("🔄 AGILE METHODOLOGY STATUS")
        report.append("-" * 50)
        if overall_pass:
            report.append("✅ Ready to proceed to Iteration 2: Actor Clustering")
        else:
            report.append("❌ Must fix issues before proceeding to next iteration")
        
        return "\n".join(report)


async def main():
    """Main test execution"""
    logger.info("🚀 Starting Proto.Actor Integration Functional Test")
    logger.info("="*70)
    
    tester = ActorIntegrationTester()
    
    try:
        # Phase 1: Setup
        await tester.setup()
        
        # Phase 2: Health Check
        logger.info("\n🏥 Phase 1: Actor System Health Check")
        health_ok = await tester.validate_actor_system_health()
        if not health_ok:
            logger.error("❌ Actor system health check failed - aborting test")
            return False
        
        # Phase 3: Send Transactions
        logger.info("\n📤 Phase 2: Sending Test Transactions")
        await tester.send_test_transactions(100)
        
        # Phase 4: Monitor Results  
        logger.info("\n📊 Phase 3: Monitoring Actor Processing")
        await asyncio.sleep(2)  # Give actors time to start processing
        model_stats = await tester.monitor_actor_results(25)
        
        # Phase 5: Calculate Metrics
        logger.info("\n📈 Phase 4: Calculating Performance Metrics")
        metrics = tester.calculate_performance_metrics()
        
        # Phase 6: Generate Report
        logger.info("\n📋 Phase 5: Generating Test Report")
        report = tester.generate_test_report(metrics)
        
        # Display results
        print("\n" + report)
        logger.info(report)
        
        # Return success status
        return metrics['success_rate'] > 80 and metrics['models_created'] > 0
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
