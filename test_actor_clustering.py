#!/usr/bin/env python3
"""
Functional Test: Proto.Actor Clustering Implementation
Tests Iteration 2: Actor clustering with load balancing and distribution

Following agile methodology - validates clustering functionality
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
logger.add("actor_clustering_test.log", rotation="10 MB", level="INFO")


class ActorClusteringTester:
    """Comprehensive functional test for actor clustering"""
    
    def __init__(self):
        self.producer = None
        self.consumer = None
        self.bridges = []  # Multiple bridges to simulate cluster
        self.test_results = {
            'transactions_sent': 0,
            'clustered_results_received': 0,
            'nodes_created': 0,
            'cluster_operations': 0,
            'load_balance_events': 0,
            'remote_messages': 0,
            'local_messages': 0,
            'processing_times': [],
            'errors': [],
            'start_time': time.time()
        }
        
    async def setup(self):
        """Setup clustering test environment"""
        logger.info("🔧 Setting up Actor Clustering Test...")
        
        # Initialize Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.consumer = KafkaConsumer(
            'clustered-actor-results',
            bootstrap_servers=['localhost:29092'],
            auto_offset_reset='latest',
            group_id='clustering-test-consumer',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info("✅ Kafka setup complete")
    
    async def create_cluster_nodes(self, node_count: int = 3):
        """Create multiple actor bridge nodes to simulate clustering"""
        logger.info(f"🏗️ Creating {node_count} cluster nodes...")
        
        from tml.orchestration.clustered_actor_bridge import ClusteredActorBridge
        from tml.orchestration.enhanced_cluster_manager import ClusterConfig, ClusterStrategy
        
        for i in range(node_count):
            # Create cluster config with different strategies
            strategies = [ClusterStrategy.LOAD_BALANCED, ClusterStrategy.ROUND_ROBIN, ClusterStrategy.SHARDED]
            strategy = strategies[i % len(strategies)]
            
            cluster_config = ClusterConfig(
                strategy=strategy,
                max_nodes=node_count,
                shard_count=20,
                auto_scaling=True
            )
            
            bridge = ClusteredActorBridge(
                cluster_config=cluster_config,
                parallelism=2  # Smaller parallelism per node
            )
            
            # Initialize bridge
            await bridge.initialize()
            self.bridges.append(bridge)
            
            logger.info(f"✅ Created cluster node {i+1}: {bridge.actor_system.node_id} ({strategy.value})")
        
        self.test_results['nodes_created'] = len(self.bridges)
        logger.info(f"✅ Cluster with {len(self.bridges)} nodes created")
    
    def generate_cluster_test_transaction(self, index: int) -> Dict[str, Any]:
        """Generate test transaction for clustering"""
        model_types = ['fraud_detection', 'risk_assessment', 'anomaly_detection', 'pattern_recognition']
        regions = ['north', 'south', 'east', 'west', 'central', 'northeast', 'southwest']
        
        model_type = model_types[index % len(model_types)]
        region = regions[index % len(regions)]
        
        return {
            'transaction_id': f'cluster_test_{index:06d}',
            'model_id': f'{model_type}_{region}_{index // 20}',
            'amount': 50 + (index * 15) % 950,
            'features': {
                'amount_normalized': (index % 100) / 100.0,
                'hour_of_day': (index % 24) / 24.0,
                'day_of_week': (index % 7) / 7.0,
                'merchant_risk': (index % 10) / 10.0,
                'customer_score': ((index * 11) % 100) / 100.0,
                'location_risk': ((index * 5) % 10) / 10.0,
                'cluster_test': True
            },
            'x_coord': -180 + (index % 360),
            'y_coord': -90 + (index % 180),
            'domain': model_type,
            'timestamp': time.time(),
            'test_batch': 'clustering_validation'
        }
    
    async def send_clustered_transactions(self, count: int = 150):
        """Send transactions to test clustering"""
        logger.info(f"📤 Sending {count} transactions to test clustering...")
        
        for i in range(count):
            transaction = self.generate_cluster_test_transaction(i)
            
            # Send to transactions topic (all cluster nodes will compete for messages)
            self.producer.send('transactions', transaction)
            
            self.test_results['transactions_sent'] += 1
            
            # Add small delay to see load balancing in action
            if i % 10 == 0:
                await asyncio.sleep(0.1)
            
            # Log progress
            if (i + 1) % 30 == 0:
                logger.info(f"  Sent {i + 1}/{count} transactions")
        
        self.producer.flush()
        logger.info(f"✅ Sent {count} transactions to cluster")
    
    async def monitor_cluster_results(self, duration: int = 40):
        """Monitor results from clustered processing"""
        logger.info(f"📊 Monitoring cluster results for {duration} seconds...")
        
        start_time = time.time()
        node_stats = {}
        cluster_stats = {
            'strategies_used': set(),
            'nodes_processing': set(),
            'total_hops': 0,
            'remote_vs_local': {'remote': 0, 'local': 0}
        }
        
        while time.time() - start_time < duration:
            try:
                # Poll for clustered results
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        result = record.value
                        
                        # Validate this is from our clustering test
                        if not result.get('transaction_id', '').startswith('cluster_test_'):
                            continue
                        
                        self.test_results['clustered_results_received'] += 1
                        
                        # Track processing times
                        if 'processing_time' in result:
                            self.test_results['processing_times'].append(result['processing_time'])
                        
                        # Track node statistics
                        processing_node = result.get('processing_node', 'unknown')
                        if processing_node not in node_stats:
                            node_stats[processing_node] = {
                                'transactions': 0,
                                'strategy': result.get('cluster_strategy', 'unknown'),
                                'avg_hops': 0,
                                'total_hops': 0
                            }
                        
                        node_stats[processing_node]['transactions'] += 1
                        
                        # Track cluster operations
                        cluster_hops = result.get('cluster_hops', 0)
                        node_stats[processing_node]['total_hops'] += cluster_hops
                        cluster_stats['total_hops'] += cluster_hops
                        
                        # Track strategies and nodes
                        cluster_stats['strategies_used'].add(result.get('cluster_strategy', 'unknown'))
                        cluster_stats['nodes_processing'].add(processing_node)
                        
                        # Track remote vs local processing
                        if cluster_hops > 0:
                            cluster_stats['remote_vs_local']['remote'] += 1
                        else:
                            cluster_stats['remote_vs_local']['local'] += 1
                        
                        # Track errors
                        if not result.get('success', True):
                            self.test_results['errors'].append(result.get('error', 'Unknown error'))
                        
                        # Log interesting clustering events
                        if cluster_hops > 0:
                            logger.info(f"🔄 Cluster routing: {result.get('transaction_id')} "
                                      f"via {processing_node} ({cluster_hops} hops)")
                
            except Exception as e:
                logger.error(f"Error monitoring cluster results: {e}")
                self.test_results['errors'].append(str(e))
        
        # Calculate node averages
        for node_id, stats in node_stats.items():
            if stats['transactions'] > 0:
                stats['avg_hops'] = stats['total_hops'] / stats['transactions']
        
        # Log cluster statistics
        logger.info(f"📈 Cluster Statistics:")
        logger.info(f"  • Active Nodes: {len(cluster_stats['nodes_processing'])}")
        logger.info(f"  • Strategies Used: {list(cluster_stats['strategies_used'])}")
        logger.info(f"  • Total Cluster Hops: {cluster_stats['total_hops']}")
        logger.info(f"  • Remote vs Local: {cluster_stats['remote_vs_local']}")
        
        logger.info(f"📊 Node Distribution:")
        for node_id, stats in list(node_stats.items())[:5]:  # Top 5 nodes
            logger.info(f"  • {node_id}: {stats['transactions']} txns, "
                       f"Strategy: {stats['strategy']}, "
                       f"Avg Hops: {stats['avg_hops']:.2f}")
        
        return node_stats, cluster_stats
    
    async def test_cluster_scaling(self):
        """Test cluster scaling capabilities"""
        logger.info("📈 Testing cluster scaling...")
        
        if not self.bridges:
            logger.warning("No bridges available for scaling test")
            return False
        
        # Test scaling up
        bridge = self.bridges[0]
        await bridge.scale_cluster(5)
        
        # Test scaling down
        await bridge.scale_cluster(2)
        
        logger.info("✅ Cluster scaling test completed")
        return True
    
    async def get_cluster_health(self) -> Dict[str, Any]:
        """Get health status of all cluster nodes"""
        health_data = {}
        
        for i, bridge in enumerate(self.bridges):
            try:
                metrics = await bridge.get_cluster_metrics()
                health_data[f'node_{i}'] = {
                    'node_id': metrics['actor_system_status']['node_id'],
                    'running': metrics['actor_system_status']['running'],
                    'transactions_processed': metrics['bridge_stats']['transactions_processed'],
                    'cluster_operations': metrics['bridge_stats']['cluster_operations'],
                    'strategy': metrics['cluster_config']['strategy']
                }
            except Exception as e:
                health_data[f'node_{i}'] = {'error': str(e)}
        
        return health_data
    
    def calculate_clustering_metrics(self, node_stats: Dict, cluster_stats: Dict) -> Dict[str, Any]:
        """Calculate clustering performance metrics"""
        elapsed = time.time() - self.test_results['start_time']
        
        # Processing rate
        tps = self.test_results['transactions_sent'] / elapsed if elapsed > 0 else 0
        response_rate = self.test_results['clustered_results_received'] / elapsed if elapsed > 0 else 0
        
        # Success rate
        success_rate = (
            (self.test_results['clustered_results_received'] / self.test_results['transactions_sent']) * 100
            if self.test_results['transactions_sent'] > 0 else 0
        )
        
        # Processing times
        avg_processing_time = (
            sum(self.test_results['processing_times']) / len(self.test_results['processing_times'])
            if self.test_results['processing_times'] else 0
        )
        
        # Clustering efficiency
        total_remote = cluster_stats['remote_vs_local']['remote']
        total_local = cluster_stats['remote_vs_local']['local']
        total_messages = total_remote + total_local
        
        cluster_efficiency = (
            (total_remote / total_messages) * 100 if total_messages > 0 else 0
        )
        
        # Load distribution
        node_loads = [stats['transactions'] for stats in node_stats.values()]
        load_variance = (
            (max(node_loads) - min(node_loads)) / max(node_loads) * 100
            if node_loads and max(node_loads) > 0 else 0
        )
        
        return {
            'test_duration': elapsed,
            'transaction_rate': tps,
            'response_rate': response_rate,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'cluster_efficiency': cluster_efficiency,
            'load_variance': load_variance,
            'nodes_active': len(cluster_stats['nodes_processing']),
            'strategies_used': len(cluster_stats['strategies_used']),
            'total_cluster_hops': cluster_stats['total_hops'],
            'error_count': len(self.test_results['errors'])
        }
    
    def generate_clustering_report(self, metrics: Dict[str, Any], node_stats: Dict) -> str:
        """Generate comprehensive clustering test report"""
        report = []
        report.append("="*70)
        report.append("🎭 PROTO.ACTOR CLUSTERING TEST REPORT")
        report.append("="*70)
        report.append("")
        
        # Test Summary
        report.append("📊 CLUSTERING TEST SUMMARY")
        report.append("-" * 50)
        report.append(f"Transactions Sent: {self.test_results['transactions_sent']}")
        report.append(f"Clustered Results Received: {self.test_results['clustered_results_received']}")
        report.append(f"Cluster Nodes Created: {self.test_results['nodes_created']}")
        report.append(f"Active Processing Nodes: {metrics['nodes_active']}")
        report.append(f"Clustering Strategies Used: {metrics['strategies_used']}")
        report.append(f"Total Cluster Hops: {metrics['total_cluster_hops']}")
        report.append(f"Errors: {len(self.test_results['errors'])}")
        report.append("")
        
        # Performance Metrics
        report.append("⚡ CLUSTERING PERFORMANCE")
        report.append("-" * 50)
        report.append(f"Test Duration: {metrics['test_duration']:.2f} seconds")
        report.append(f"Transaction Rate: {metrics['transaction_rate']:.1f} TPS")
        report.append(f"Response Rate: {metrics['response_rate']:.1f} responses/sec")
        report.append(f"Success Rate: {metrics['success_rate']:.1f}%")
        report.append(f"Average Processing Time: {metrics['avg_processing_time']:.3f} seconds")
        report.append(f"Cluster Efficiency: {metrics['cluster_efficiency']:.1f}% (remote routing)")
        report.append(f"Load Distribution Variance: {metrics['load_variance']:.1f}%")
        report.append("")
        
        # Node Distribution
        report.append("🏗️ NODE LOAD DISTRIBUTION")
        report.append("-" * 50)
        for node_id, stats in list(node_stats.items())[:5]:
            report.append(f"• {node_id}: {stats['transactions']} transactions")
            report.append(f"  Strategy: {stats['strategy']}, Avg Hops: {stats['avg_hops']:.2f}")
        report.append("")
        
        # Pass/Fail Criteria
        report.append("✅ CLUSTERING CRITERIA ANALYSIS")
        report.append("-" * 50)
        
        criteria = [
            ("Success Rate > 75%", metrics['success_rate'] > 75),
            ("Multiple Nodes Active", metrics['nodes_active'] > 1),
            ("Cluster Routing Working", metrics['total_cluster_hops'] > 0),
            ("Load Distribution < 50% variance", metrics['load_variance'] < 50),
            ("Processing Time < 200ms", metrics['avg_processing_time'] < 0.2),
            ("Error Rate < 10%", metrics['error_count'] / max(1, self.test_results['transactions_sent']) < 0.1)
        ]
        
        passed_tests = 0
        for criterion, passed in criteria:
            status = "✅ PASS" if passed else "❌ FAIL"
            report.append(f"{status}: {criterion}")
            if passed:
                passed_tests += 1
        
        report.append("")
        overall_pass = passed_tests >= 4  # At least 4/6 criteria must pass
        
        # Final Verdict
        report.append("🏁 FINAL VERDICT")
        report.append("-" * 50)
        if overall_pass:
            report.append("✅ ACTOR CLUSTERING TEST PASSED!")
            report.append("   Distributed actor processing is functional")
        else:
            report.append("❌ ACTOR CLUSTERING TEST FAILED")
            report.append(f"   Only {passed_tests}/6 criteria passed")
        
        report.append("")
        report.append("🔄 AGILE METHODOLOGY STATUS")
        report.append("-" * 50)
        if overall_pass:
            report.append("✅ Ready to proceed to Iteration 3: Supervision and Fault Tolerance")
        else:
            report.append("❌ Must fix clustering issues before proceeding")
        
        return "\n".join(report)
    
    async def cleanup(self):
        """Cleanup test resources"""
        logger.info("🧹 Cleaning up cluster test resources...")
        
        # Shutdown all bridges
        for bridge in self.bridges:
            try:
                await bridge.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down bridge: {e}")
        
        # Close Kafka connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        
        logger.info("✅ Cleanup complete")


async def main():
    """Main clustering test execution"""
    logger.info("🚀 Starting Proto.Actor Clustering Functional Test")
    logger.info("="*70)
    
    tester = ActorClusteringTester()
    
    try:
        # Phase 1: Setup
        await tester.setup()
        
        # Phase 2: Create Cluster
        logger.info("\n🏗️ Phase 1: Creating Cluster Nodes")
        await tester.create_cluster_nodes(3)
        
        # Phase 3: Send Transactions
        logger.info("\n📤 Phase 2: Sending Clustered Transactions")
        await tester.send_clustered_transactions(150)
        
        # Phase 4: Monitor Results
        logger.info("\n📊 Phase 3: Monitoring Cluster Processing")
        await asyncio.sleep(3)  # Give cluster time to process
        node_stats, cluster_stats = await tester.monitor_cluster_results(35)
        
        # Phase 5: Test Scaling
        logger.info("\n📈 Phase 4: Testing Cluster Scaling")
        await tester.test_cluster_scaling()
        
        # Phase 6: Health Check
        logger.info("\n🏥 Phase 5: Cluster Health Check")
        health = await tester.get_cluster_health()
        logger.info(f"Cluster health: {len([h for h in health.values() if 'error' not in h])}/{len(health)} nodes healthy")
        
        # Phase 7: Calculate Metrics
        logger.info("\n📈 Phase 6: Calculating Clustering Metrics")
        metrics = tester.calculate_clustering_metrics(node_stats, cluster_stats)
        
        # Phase 8: Generate Report
        logger.info("\n📋 Phase 7: Generating Clustering Report")
        report = tester.generate_clustering_report(metrics, node_stats)
        
        # Display results
        print("\n" + report)
        logger.info(report)
        
        # Return success status
        return (metrics['success_rate'] > 75 and 
                metrics['nodes_active'] > 1 and 
                metrics['total_cluster_hops'] > 0)
        
    except Exception as e:
        logger.error(f"❌ Clustering test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
