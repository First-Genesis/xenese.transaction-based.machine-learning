"""
Clustered Actor Transaction Bridge
Integrates enhanced clustering with transaction processing
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from .actor_system import ActorSystem, ActorMessage, MessagePriority
from .enhanced_cluster_manager import EnhancedClusterManager, ClusterConfig, ClusterStrategy
from .tml_actors import (
    TransactionProcessorActor, 
    ModelActor, 
    InheritanceCoordinatorActor,
    PhysicsValidatorActor,
    TMLMessageType,
    TransactionData
)
from ..learning.online_learner import OnlineLearningEngine
from ..core.inheritance import SpatialInheritanceCoordinator


@dataclass
class ClusteredProcessingResult:
    """Result from clustered actor processing"""
    transaction_id: str
    model_id: str
    processing_time: float
    processing_node: str
    actor_path: str
    cluster_hops: int
    inheritance_applied: bool
    success: bool
    error: Optional[str] = None


class ClusteredActorBridge:
    """
    Clustered actor bridge with distributed processing capabilities
    Extends the basic bridge with clustering and load balancing
    """
    
    def __init__(self, 
                 kafka_bootstrap_servers: str = "localhost:29092",
                 cluster_config: ClusterConfig = None,
                 parallelism: int = 4):
        
        self.kafka_servers = kafka_bootstrap_servers
        self.parallelism = parallelism
        
        # Initialize actor system with clustering
        node_suffix = int(time.time() * 1000) % 10000
        self.actor_system = ActorSystem(
            node_id=f"tml-cluster-node-{node_suffix}",
            redis_url="redis://localhost:6379",
            cluster_port=8080 + (node_suffix % 100),  # Dynamic port
            metrics_port=9000 + (node_suffix % 100)   # Dynamic metrics port
        )
        
        # Initialize cluster manager
        self.cluster_config = cluster_config or ClusterConfig(
            strategy=ClusterStrategy.LOAD_BALANCED,
            max_nodes=5,
            shard_count=50,
            auto_scaling=True
        )
        self.cluster_manager = EnhancedClusterManager(self.actor_system, self.cluster_config)
        
        # Kafka components
        self.consumer = None
        self.producer = None
        
        # Actor references (distributed)
        self.transaction_processors: List[str] = []  # Store actor IDs, not refs
        self.model_actors: Dict[str, str] = {}  # model_id -> actor_id
        
        # Processing statistics
        self.stats = {
            'transactions_processed': 0,
            'cluster_operations': 0,
            'load_balance_events': 0,
            'remote_messages': 0,
            'local_messages': 0,
            'start_time': time.time()
        }
        
        # Integration with TML components
        self.learning_engine = OnlineLearningEngine()
        self.spatial_coordinator = SpatialInheritanceCoordinator()
        
        logger.info(f"Clustered Actor Bridge initialized: {self.actor_system.node_id}")
    
    async def initialize(self):
        """Initialize clustered bridge"""
        # Start actor system
        await self.actor_system.start()
        logger.info("✅ Actor system started")
        
        # Initialize cluster
        await self.cluster_manager.initialize_cluster()
        logger.info("✅ Cluster manager initialized")
        
        # Create distributed actors
        await self._create_distributed_actors()
        
        # Initialize Kafka
        self._initialize_kafka()
        
        logger.info("✅ Clustered Actor Bridge fully initialized")
    
    async def _create_distributed_actors(self):
        """Create actors distributed across cluster"""
        # Create transaction processors with clustering
        for i in range(self.parallelism):
            actor_id = f"clustered_transaction_processor_{i}"
            
            # Use cluster manager to place actor
            node_id = await self.cluster_manager.create_distributed_actor(
                TransactionProcessorActor,
                actor_id
            )
            
            self.transaction_processors.append(actor_id)
            logger.info(f"✅ Created transaction processor {actor_id} on node {node_id}")
        
        # Create shared services (one per cluster)
        inheritance_actor_id = "clustered_inheritance_coordinator"
        await self.cluster_manager.create_distributed_actor(
            InheritanceCoordinatorActor,
            inheritance_actor_id
        )
        
        physics_actor_id = "clustered_physics_validator"
        await self.cluster_manager.create_distributed_actor(
            PhysicsValidatorActor,
            physics_actor_id
        )
        
        logger.info("✅ Created distributed actor hierarchy")
    
    def _initialize_kafka(self):
        """Initialize Kafka with cluster-aware consumer group"""
        # Use node-specific consumer group for clustering
        consumer_group = f"clustered-actor-bridge-{self.actor_system.node_id}"
        
        self.consumer = KafkaConsumer(
            'transactions',
            bootstrap_servers=self.kafka_servers,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id=consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        logger.info(f"✅ Kafka initialized with consumer group: {consumer_group}")
    
    async def process_clustered_transaction_stream(self):
        """Main processing loop with clustering"""
        logger.info("🚀 Starting clustered transaction processing...")
        
        processor_index = 0
        
        while True:
            try:
                # Poll for messages
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        # Process transaction through clustered actors
                        result = await self._process_transaction_clustered(
                            record.value, processor_index
                        )
                        
                        # Send result to output topic
                        if result:
                            await self._send_clustered_result(result)
                        
                        # Round-robin processor selection
                        processor_index = (processor_index + 1) % len(self.transaction_processors)
                        
                        # Update statistics
                        self.stats['transactions_processed'] += 1
                        
                        # Log progress
                        if self.stats['transactions_processed'] % 25 == 0:
                            await self._log_cluster_stats()
                
            except Exception as e:
                logger.error(f"Error in clustered transaction processing: {e}")
                await asyncio.sleep(1)
    
    async def _process_transaction_clustered(self, transaction: Dict, processor_index: int) -> Optional[ClusteredProcessingResult]:
        """Process transaction through clustered actors"""
        start_time = time.time()
        cluster_hops = 0
        
        try:
            # Extract transaction details
            transaction_id = transaction.get('transaction_id', f'clustered_tx_{int(time.time() * 1000)}')
            model_id = transaction.get('model_id', f'model_{transaction_id}')
            
            # Create transaction data
            tx_data = TransactionData(
                transaction_id=transaction_id,
                data=transaction,
                timestamp=time.time(),
                source='clustered_kafka_bridge',
                metadata={'processor_index': processor_index, 'cluster_node': self.actor_system.node_id}
            )
            
            # Get processor actor ID
            processor_actor_id = self.transaction_processors[processor_index]
            
            # Create message for clustered delivery
            message = ActorMessage(
                message_type=TMLMessageType.PROCESS_TRANSACTION.value,
                recipient=processor_actor_id,
                payload={'transaction': asdict(tx_data)},
                priority=MessagePriority.NORMAL,
                reply_to=f"clustered_bridge_{transaction_id}"
            )
            
            # Route through cluster manager
            routed = await self.cluster_manager.route_message_to_actor(message)
            
            if routed:
                self.stats['cluster_operations'] += 1
                
                # Check if message was routed remotely
                if processor_actor_id in self.cluster_manager.actor_distribution:
                    target_node = self.cluster_manager.actor_distribution[processor_actor_id]
                    if target_node != self.actor_system.node_id:
                        cluster_hops += 1
                        self.stats['remote_messages'] += 1
                    else:
                        self.stats['local_messages'] += 1
            
            # Also process with TML learning engine for integration
            features = transaction.get('features', {})
            target = transaction.get('amount', 0) / 1000.0
            
            # Learn with spatial inheritance
            learned = self.learning_engine.learn(model_id, features, target)
            
            # Get processing node
            processing_node = self.cluster_manager.actor_distribution.get(
                processor_actor_id, 
                self.actor_system.node_id
            )
            
            # Create result
            result = ClusteredProcessingResult(
                transaction_id=transaction_id,
                model_id=model_id,
                processing_time=time.time() - start_time,
                processing_node=processing_node,
                actor_path=processor_actor_id,
                cluster_hops=cluster_hops,
                inheritance_applied=learned,
                success=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing clustered transaction: {e}")
            
            return ClusteredProcessingResult(
                transaction_id=transaction.get('transaction_id', 'unknown'),
                model_id=transaction.get('model_id', 'unknown'),
                processing_time=time.time() - start_time,
                processing_node=self.actor_system.node_id,
                actor_path=f"processor_{processor_index}",
                cluster_hops=cluster_hops,
                inheritance_applied=False,
                success=False,
                error=str(e)
            )
    
    async def _send_clustered_result(self, result: ClusteredProcessingResult):
        """Send clustered processing result to Kafka"""
        try:
            result_data = {
                'transaction_id': result.transaction_id,
                'model_id': result.model_id,
                'processing_time': result.processing_time,
                'processing_node': result.processing_node,
                'actor_path': result.actor_path,
                'cluster_hops': result.cluster_hops,
                'inheritance_applied': result.inheritance_applied,
                'success': result.success,
                'error': result.error,
                'processed_at': time.time(),
                'processing_method': 'clustered_proto_actor',
                'cluster_strategy': self.cluster_config.strategy.value
            }
            
            self.producer.send('clustered-actor-results', result_data)
            
        except Exception as e:
            logger.error(f"Error sending clustered result: {e}")
    
    async def _log_cluster_stats(self):
        """Log cluster processing statistics"""
        elapsed = time.time() - self.stats['start_time']
        tps = self.stats['transactions_processed'] / elapsed if elapsed > 0 else 0
        
        cluster_status = self.cluster_manager.get_cluster_status()
        
        logger.info(f"🎭 Clustered Processing Stats:")
        logger.info(f"  • Transactions: {self.stats['transactions_processed']}")
        logger.info(f"  • Processing Rate: {tps:.1f} TPS")
        logger.info(f"  • Cluster Nodes: {cluster_status['metrics']['healthy_nodes']}/{cluster_status['metrics']['total_nodes']}")
        logger.info(f"  • Local Messages: {self.stats['local_messages']}")
        logger.info(f"  • Remote Messages: {self.stats['remote_messages']}")
        logger.info(f"  • Load Balance Events: {self.cluster_manager.cluster_metrics['load_balance_operations']}")
    
    async def get_cluster_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cluster metrics"""
        cluster_status = self.cluster_manager.get_cluster_status()
        
        return {
            'bridge_stats': self.stats,
            'cluster_status': cluster_status,
            'actor_system_status': {
                'node_id': self.actor_system.node_id,
                'running': self.actor_system.is_running,
                'total_actors': len(self.actor_system.actors),
                'cluster_port': self.actor_system.cluster_port
            },
            'learning_engine_stats': {
                'active_models': len(self.learning_engine.learners),
                'total_updates': self.learning_engine.total_updates
            },
            'cluster_config': asdict(self.cluster_config)
        }
    
    async def scale_cluster(self, target_nodes: int):
        """Scale cluster to target number of nodes"""
        current_nodes = self.cluster_manager.cluster_metrics['healthy_nodes']
        
        if target_nodes > current_nodes:
            logger.info(f"Scaling up cluster from {current_nodes} to {target_nodes} nodes")
            # In a real implementation, this would spawn new nodes
            for i in range(target_nodes - current_nodes):
                logger.info(f"Would spawn new node {i+1}")
        
        elif target_nodes < current_nodes:
            logger.info(f"Scaling down cluster from {current_nodes} to {target_nodes} nodes")
            # In a real implementation, this would gracefully shutdown nodes
            for i in range(current_nodes - target_nodes):
                logger.info(f"Would shutdown node {i+1}")
    
    async def shutdown(self):
        """Graceful shutdown of clustered bridge"""
        logger.info("🛑 Shutting down Clustered Actor Bridge...")
        
        # Close Kafka connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        
        # Stop actor system (will handle cluster cleanup)
        await self.actor_system.stop()
        
        # Final stats
        await self._log_cluster_stats()
        
        logger.info("✅ Clustered Actor Bridge shutdown complete")


async def main():
    """Main entry point for testing"""
    cluster_config = ClusterConfig(
        strategy=ClusterStrategy.LOAD_BALANCED,
        max_nodes=3,
        shard_count=20,
        auto_scaling=True
    )
    
    bridge = ClusteredActorBridge(
        cluster_config=cluster_config,
        parallelism=4
    )
    
    try:
        await bridge.initialize()
        await bridge.process_clustered_transaction_stream()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await bridge.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
