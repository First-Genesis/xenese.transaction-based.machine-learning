#!/usr/bin/env python3
"""
Test Apache Flink Integration for TML Platform
Verifies stateful stream processing with spatial inheritance
"""

import json
import time
import random
from typing import Dict, Any
from kafka import KafkaProducer, KafkaConsumer
from loguru import logger

# Configure logging
logger.add("flink_test.log", rotation="10 MB")


class FlinkTester:
    """Test harness for Flink integration"""
    
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.consumer = KafkaConsumer(
            'model-updates',
            bootstrap_servers=['localhost:29092'],
            auto_offset_reset='latest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info("Flink tester initialized")
    
    def generate_test_transaction(self, index: int) -> Dict[str, Any]:
        """Generate a test transaction with spatial context"""
        model_types = ['fraud_detection', 'risk_assessment', 'anomaly_detection']
        regions = ['north', 'south', 'east', 'west', 'central']
        
        model_type = model_types[index % len(model_types)]
        region = regions[index % len(regions)]
        
        return {
            'transaction_id': f'flink_test_{index:06d}',
            'model_id': f'{model_type}_{region}_{index // 100}',
            'amount': round(random.uniform(10, 1000), 2),
            'features': {
                'amount_normalized': random.random(),
                'hour_of_day': random.randint(0, 23) / 23.0,
                'day_of_week': random.randint(0, 6) / 6.0,
                'merchant_risk': random.random(),
                'customer_score': random.random(),
                'location_risk': random.random()
            },
            'x_coord': random.uniform(-180, 180),
            'y_coord': random.uniform(-90, 90),
            'domain': model_type,
            'timestamp': time.time()
        }
    
    def send_test_batch(self, batch_size: int = 100):
        """Send a batch of test transactions"""
        logger.info(f"Sending {batch_size} test transactions to Flink...")
        
        for i in range(batch_size):
            transaction = self.generate_test_transaction(i)
            self.producer.send('transactions', transaction)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Sent {i + 1}/{batch_size} transactions")
        
        self.producer.flush()
        logger.info(f"✅ Sent {batch_size} transactions to Flink")
    
    def monitor_results(self, duration: int = 30):
        """Monitor Flink processing results"""
        logger.info(f"Monitoring Flink results for {duration} seconds...")
        
        start_time = time.time()
        results = []
        model_stats = {}
        
        while time.time() - start_time < duration:
            try:
                # Poll for messages (100ms timeout)
                messages = self.consumer.poll(timeout_ms=100)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        result = record.value
                        results.append(result)
                        
                        # Track model statistics
                        model_id = result.get('model_id', 'unknown')
                        if model_id not in model_stats:
                            model_stats[model_id] = {
                                'count': 0,
                                'has_parent': False,
                                'drift_scores': []
                            }
                        
                        model_stats[model_id]['count'] += 1
                        model_stats[model_id]['has_parent'] = result.get('parent_model') is not None
                        model_stats[model_id]['drift_scores'].append(result.get('drift_score', 0))
                        
                        # Log interesting results
                        if result.get('spatial_inheritance'):
                            logger.info(f"🧬 Spatial inheritance detected: {model_id} <- {result.get('parent_model')}")
                        
                        if result.get('drift_score', 0) > 0.1:
                            logger.warning(f"⚠️ High drift detected: {model_id} (drift={result.get('drift_score'):.3f})")
                
            except Exception as e:
                logger.error(f"Error monitoring results: {e}")
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("📊 FLINK PROCESSING SUMMARY")
        logger.info("="*50)
        logger.info(f"Total results received: {len(results)}")
        logger.info(f"Unique models: {len(model_stats)}")
        
        inheritance_count = sum(1 for m in model_stats.values() if m['has_parent'])
        logger.info(f"Models with inheritance: {inheritance_count}/{len(model_stats)}")
        
        if model_stats:
            avg_drift = sum(
                sum(m['drift_scores'])/len(m['drift_scores']) 
                for m in model_stats.values() 
                if m['drift_scores']
            ) / len(model_stats)
            logger.info(f"Average drift score: {avg_drift:.4f}")
        
        logger.info("\nTop 5 Models by Transaction Count:")
        sorted_models = sorted(model_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        for model_id, stats in sorted_models:
            logger.info(f"  • {model_id}: {stats['count']} transactions, "
                       f"Parent: {'Yes' if stats['has_parent'] else 'No'}")
        
        return results, model_stats


def main():
    """Run Flink integration test"""
    logger.info("🚀 Starting Apache Flink Integration Test")
    
    tester = FlinkTester()
    
    # Phase 1: Send initial batch
    logger.info("\n📤 Phase 1: Sending initial batch...")
    tester.send_test_batch(100)
    
    # Phase 2: Monitor for 20 seconds
    logger.info("\n📊 Phase 2: Monitoring results...")
    time.sleep(2)  # Give Flink time to start processing
    results, stats = tester.monitor_results(20)
    
    # Phase 3: Send more data to test stateful processing
    logger.info("\n📤 Phase 3: Sending follow-up batch...")
    tester.send_test_batch(50)
    
    # Phase 4: Final monitoring
    logger.info("\n📊 Phase 4: Final monitoring...")
    time.sleep(2)
    final_results, final_stats = tester.monitor_results(15)
    
    # Final verdict
    logger.info("\n" + "="*50)
    logger.info("🏁 FLINK INTEGRATION TEST COMPLETE")
    logger.info("="*50)
    
    total_sent = 150
    total_received = len(results) + len(final_results)
    success_rate = (total_received / total_sent) * 100 if total_sent > 0 else 0
    
    logger.info(f"Transactions sent: {total_sent}")
    logger.info(f"Results received: {total_received}")
    logger.info(f"Success rate: {success_rate:.1f}%")
    
    if success_rate > 80:
        logger.success("✅ Flink integration test PASSED!")
    elif success_rate > 50:
        logger.warning("⚠️ Flink integration partially working")
    else:
        logger.error("❌ Flink integration test FAILED")
    
    return success_rate > 80


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
