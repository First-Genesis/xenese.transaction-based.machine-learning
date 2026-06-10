"""
Fault-Tolerant Actor Bridge for TML Platform
Integrates supervision and fault tolerance with transaction processing
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from .actor_system import ActorSystem, ActorMessage, MessagePriority, ActorState
from .supervision_manager import (
    SupervisionManager, SupervisionPolicy, FaultType, 
    RecoveryAction, SupervisionStrategy
)
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
class FaultTolerantProcessingResult:
    """Result from fault-tolerant processing"""
    transaction_id: str
    model_id: str
    processing_time: float
    processing_node: str
    actor_path: str
    supervision_events: List[str]
    recovery_attempts: int
    circuit_breaker_state: str
    success: bool
    error: Optional[str] = None


class FaultTolerantActorBridge:
    """
    Fault-tolerant actor bridge with enterprise-grade supervision
    Combines clustering, supervision, and fault tolerance
    """
    
    def __init__(self, 
                 kafka_bootstrap_servers: str = "localhost:29092",
                 cluster_config: ClusterConfig = None,
                 parallelism: int = 4):
        
        self.kafka_servers = kafka_bootstrap_servers
        self.parallelism = parallelism
        
        # Initialize actor system
        node_suffix = int(time.time() * 1000) % 10000
        self.actor_system = ActorSystem(
            node_id=f"tml-ft-node-{node_suffix}",
            redis_url="redis://localhost:6379",
            cluster_port=8200 + (node_suffix % 100),
            metrics_port=9200 + (node_suffix % 100)
        )
        
        # Initialize cluster manager
        self.cluster_config = cluster_config or ClusterConfig(
            strategy=ClusterStrategy.LOAD_BALANCED,
            max_nodes=5,
            shard_count=50,
            auto_scaling=True
        )
        self.cluster_manager = EnhancedClusterManager(self.actor_system, self.cluster_config)
        
        # Initialize supervision manager
        self.supervision_manager = SupervisionManager(self.actor_system)
        
        # Kafka components
        self.consumer = None
        self.producer = None
        
        # Actor references with fault tolerance
        self.transaction_processors: List[str] = []
        self.critical_actors: Dict[str, str] = {}  # role -> actor_id
        
        # Fault tolerance statistics
        self.ft_stats = {
            'transactions_processed': 0,
            'faults_detected': 0,
            'recoveries_successful': 0,
            'recoveries_failed': 0,
            'circuit_breaker_trips': 0,
            'supervision_escalations': 0,
            'start_time': time.time()
        }
        
        # Integration with TML components
        self.learning_engine = OnlineLearningEngine()
        self.spatial_coordinator = SpatialInheritanceCoordinator()
        
        logger.info(f"Fault-Tolerant Actor Bridge initialized: {self.actor_system.node_id}")
    
    async def initialize(self):
        """Initialize fault-tolerant bridge with supervision"""
        # Start actor system
        await self.actor_system.start()
        logger.info("✅ Actor system started")
        
        # Initialize cluster
        await self.cluster_manager.initialize_cluster()
        logger.info("✅ Cluster manager initialized")
        
        # Create fault-tolerant actors with supervision
        await self._create_supervised_actors()
        
        # Initialize Kafka
        self._initialize_kafka()
        
        # Start supervision services
        asyncio.create_task(self.supervision_manager.health_check_loop())
        asyncio.create_task(self._fault_tolerance_monitor())
        
        logger.info("✅ Fault-Tolerant Actor Bridge fully initialized")
    
    async def _create_supervised_actors(self):
        """Create actors with comprehensive supervision policies"""
        
        # Create transaction processors with restart supervision
        for i in range(self.parallelism):
            actor_id = f"ft_transaction_processor_{i}"
            
            # Create actor with clustering
            node_id = await self.cluster_manager.create_distributed_actor(
                TransactionProcessorActor,
                actor_id
            )
            
            # Register for supervision with aggressive restart policy
            supervision_policy = SupervisionPolicy(
                strategy=SupervisionStrategy.RESTART,
                max_retries=5,
                retry_window=120.0,
                backoff_multiplier=1.2,
                max_backoff=10.0,
                escalation_threshold=3,
                circuit_breaker_enabled=True,
                health_check_interval=15.0,
                recovery_timeout=60.0
            )
            
            self.supervision_manager.register_actor_supervision(
                actor_id, 
                parent_id=None,  # Root level
                policy=supervision_policy
            )
            
            self.transaction_processors.append(actor_id)
            logger.info(f"✅ Created supervised transaction processor {actor_id} on node {node_id}")
        
        # Create critical shared services with escalation supervision
        critical_services = [
            ("ft_inheritance_coordinator", InheritanceCoordinatorActor),
            ("ft_physics_validator", PhysicsValidatorActor)
        ]
        
        for service_id, service_class in critical_services:
            node_id = await self.cluster_manager.create_distributed_actor(
                service_class,
                service_id
            )
            
            # Critical services get escalation supervision
            critical_policy = SupervisionPolicy(
                strategy=SupervisionStrategy.ESCALATE,
                max_retries=2,
                retry_window=60.0,
                escalation_threshold=2,
                circuit_breaker_enabled=True,
                recovery_timeout=30.0
            )
            
            self.supervision_manager.register_actor_supervision(
                service_id,
                parent_id=None,
                policy=critical_policy
            )
            
            self.critical_actors[service_id] = service_id
        
        logger.info("✅ Created supervised actor hierarchy with fault tolerance")
    
    def _initialize_kafka(self):
        """Initialize Kafka with fault-tolerant consumer group"""
        consumer_group = f"ft-actor-bridge-{self.actor_system.node_id}"
        
        self.consumer = KafkaConsumer(
            'transactions',
            bootstrap_servers=self.kafka_servers,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id=consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            # Fault tolerance settings
            request_timeout_ms=30000,
            retry_backoff_ms=1000,
            reconnect_backoff_ms=1000
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            # Fault tolerance settings
            retries=3,
            retry_backoff_ms=1000,
            request_timeout_ms=30000
        )
        
        logger.info(f"✅ Fault-tolerant Kafka initialized: {consumer_group}")
    
    async def process_fault_tolerant_stream(self):
        """Main processing loop with comprehensive fault tolerance"""
        logger.info("🚀 Starting fault-tolerant transaction processing...")
        
        processor_index = 0
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:
            try:
                # Poll for messages with timeout
                messages = self.consumer.poll(timeout_ms=1000)
                
                if not messages:
                    # Reset error count on successful poll
                    consecutive_errors = 0
                    continue
                
                for topic_partition, records in messages.items():
                    for record in records:
                        try:
                            # Process transaction with fault tolerance
                            result = await self._process_transaction_with_ft(
                                record.value, processor_index
                            )
                            
                            # Send result
                            if result:
                                await self._send_ft_result(result)
                            
                            # Update processor selection
                            processor_index = (processor_index + 1) % len(self.transaction_processors)
                            
                            # Update statistics
                            self.ft_stats['transactions_processed'] += 1
                            
                            # Log progress
                            if self.ft_stats['transactions_processed'] % 20 == 0:
                                await self._log_ft_stats()
                        
                        except Exception as e:
                            logger.error(f"Error processing individual transaction: {e}")
                            consecutive_errors += 1
                            
                            # Handle individual transaction failure
                            await self._handle_transaction_failure(record.value, e)
                
                # Reset consecutive errors on successful batch
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in fault-tolerant processing loop: {e}")
                
                # Circuit breaker logic for the entire processing loop
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), backing off...")
                    await asyncio.sleep(min(consecutive_errors * 2, 60))  # Exponential backoff
                    consecutive_errors = 0  # Reset after backoff
                else:
                    await asyncio.sleep(1)
    
    async def _process_transaction_with_ft(self, transaction: Dict, processor_index: int) -> Optional[FaultTolerantProcessingResult]:
        """Process transaction with comprehensive fault tolerance"""
        start_time = time.time()
        supervision_events = []
        recovery_attempts = 0
        
        try:
            # Extract transaction details
            transaction_id = transaction.get('transaction_id', f'ft_tx_{int(time.time() * 1000)}')
            model_id = transaction.get('model_id', f'model_{transaction_id}')
            
            # Get processor actor
            processor_actor_id = self.transaction_processors[processor_index]
            
            # Check circuit breaker
            if processor_actor_id in self.supervision_manager.circuit_breakers:
                cb = self.supervision_manager.circuit_breakers[processor_actor_id]
                if cb.is_open():
                    supervision_events.append("circuit_breaker_open")
                    self.ft_stats['circuit_breaker_trips'] += 1
                    
                    # Try next processor
                    processor_index = (processor_index + 1) % len(self.transaction_processors)
                    processor_actor_id = self.transaction_processors[processor_index]
            
            # Create transaction data
            tx_data = TransactionData(
                transaction_id=transaction_id,
                data=transaction,
                timestamp=time.time(),
                source='fault_tolerant_bridge',
                metadata={
                    'processor_index': processor_index, 
                    'node': self.actor_system.node_id,
                    'fault_tolerance': True
                }
            )
            
            # Create message with fault tolerance
            message = ActorMessage(
                message_type=TMLMessageType.PROCESS_TRANSACTION.value,
                recipient=processor_actor_id,
                payload={'transaction': asdict(tx_data)},
                priority=MessagePriority.NORMAL,
                reply_to=f"ft_bridge_{transaction_id}",
                timeout=30.0  # 30 second timeout
            )
            
            # Attempt processing with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Route through cluster manager
                    routed = await asyncio.wait_for(
                        self.cluster_manager.route_message_to_actor(message),
                        timeout=35.0
                    )
                    
                    if routed:
                        supervision_events.append(f"routed_attempt_{attempt + 1}")
                        
                        # Record success in circuit breaker
                        if processor_actor_id in self.supervision_manager.circuit_breakers:
                            self.supervision_manager.circuit_breakers[processor_actor_id].record_success()
                        
                        break
                    else:
                        raise Exception("Message routing failed")
                
                except asyncio.TimeoutError:
                    recovery_attempts += 1
                    supervision_events.append(f"timeout_attempt_{attempt + 1}")
                    
                    # Handle timeout as fault
                    await self.supervision_manager.handle_actor_failure(
                        processor_actor_id,
                        Exception("Message timeout"),
                        FaultType.MESSAGE_TIMEOUT
                    )
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                except Exception as e:
                    recovery_attempts += 1
                    supervision_events.append(f"error_attempt_{attempt + 1}")
                    
                    # Handle processing failure
                    await self.supervision_manager.handle_actor_failure(
                        processor_actor_id,
                        e,
                        FaultType.ACTOR_CRASH
                    )
                    
                    # Record failure in circuit breaker
                    if processor_actor_id in self.supervision_manager.circuit_breakers:
                        self.supervision_manager.circuit_breakers[processor_actor_id].record_failure()
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            
            # Process with TML learning engine (fault-tolerant)
            try:
                features = transaction.get('features', {})
                target = transaction.get('amount', 0) / 1000.0
                learned = self.learning_engine.learn(model_id, features, target)
            except Exception as e:
                logger.warning(f"TML learning failed for {model_id}: {e}")
                learned = False
            
            # Get circuit breaker state
            cb_state = "closed"
            if processor_actor_id in self.supervision_manager.circuit_breakers:
                cb_state = self.supervision_manager.circuit_breakers[processor_actor_id].state.value
            
            # Get processing node
            processing_node = self.cluster_manager.actor_distribution.get(
                processor_actor_id, 
                self.actor_system.node_id
            )
            
            # Create result
            result = FaultTolerantProcessingResult(
                transaction_id=transaction_id,
                model_id=model_id,
                processing_time=time.time() - start_time,
                processing_node=processing_node,
                actor_path=processor_actor_id,
                supervision_events=supervision_events,
                recovery_attempts=recovery_attempts,
                circuit_breaker_state=cb_state,
                success=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Fault-tolerant processing failed: {e}")
            self.ft_stats['faults_detected'] += 1
            
            return FaultTolerantProcessingResult(
                transaction_id=transaction.get('transaction_id', 'unknown'),
                model_id=transaction.get('model_id', 'unknown'),
                processing_time=time.time() - start_time,
                processing_node=self.actor_system.node_id,
                actor_path=f"processor_{processor_index}",
                supervision_events=supervision_events,
                recovery_attempts=recovery_attempts,
                circuit_breaker_state="unknown",
                success=False,
                error=str(e)
            )
    
    async def _handle_transaction_failure(self, transaction: Dict, error: Exception):
        """Handle individual transaction failure"""
        self.ft_stats['faults_detected'] += 1
        
        # Log the failure
        logger.error(f"Transaction failure: {transaction.get('transaction_id', 'unknown')} - {error}")
        
        # Could implement dead letter queue here
        # For now, just count the failure
    
    async def _send_ft_result(self, result: FaultTolerantProcessingResult):
        """Send fault-tolerant processing result"""
        try:
            result_data = {
                'transaction_id': result.transaction_id,
                'model_id': result.model_id,
                'processing_time': result.processing_time,
                'processing_node': result.processing_node,
                'actor_path': result.actor_path,
                'supervision_events': result.supervision_events,
                'recovery_attempts': result.recovery_attempts,
                'circuit_breaker_state': result.circuit_breaker_state,
                'success': result.success,
                'error': result.error,
                'processed_at': time.time(),
                'processing_method': 'fault_tolerant_actor',
                'fault_tolerance_enabled': True
            }
            
            self.producer.send('fault-tolerant-results', result_data)
            
        except Exception as e:
            logger.error(f"Error sending fault-tolerant result: {e}")
    
    async def _fault_tolerance_monitor(self):
        """Background fault tolerance monitoring"""
        while True:
            try:
                # Update fault tolerance statistics
                supervision_status = self.supervision_manager.get_supervision_status()
                
                self.ft_stats.update({
                    'supervised_actors': supervision_status['supervised_actors'],
                    'healthy_actors': supervision_status['healthy_actors'],
                    'unhealthy_actors': supervision_status['unhealthy_actors'],
                    'total_faults_last_hour': supervision_status['total_faults_last_hour']
                })
                
                await asyncio.sleep(60)  # Monitor every minute
                
            except Exception as e:
                logger.error(f"Fault tolerance monitor error: {e}")
                await asyncio.sleep(30)
    
    async def _log_ft_stats(self):
        """Log fault tolerance statistics"""
        elapsed = time.time() - self.ft_stats['start_time']
        tps = self.ft_stats['transactions_processed'] / elapsed if elapsed > 0 else 0
        
        supervision_status = self.supervision_manager.get_supervision_status()
        
        logger.info(f"🛡️ Fault-Tolerant Processing Stats:")
        logger.info(f"  • Transactions: {self.ft_stats['transactions_processed']}")
        logger.info(f"  • Processing Rate: {tps:.1f} TPS")
        logger.info(f"  • Faults Detected: {self.ft_stats['faults_detected']}")
        logger.info(f"  • Successful Recoveries: {supervision_status['recovery_stats']['successful_recoveries']}")
        logger.info(f"  • Failed Recoveries: {supervision_status['recovery_stats']['failed_recoveries']}")
        logger.info(f"  • Circuit Breaker Trips: {self.ft_stats['circuit_breaker_trips']}")
        logger.info(f"  • Healthy Actors: {supervision_status['healthy_actors']}/{supervision_status['supervised_actors']}")
    
    async def get_fault_tolerance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive fault tolerance metrics"""
        supervision_status = self.supervision_manager.get_supervision_status()
        cluster_status = self.cluster_manager.get_cluster_status()
        
        return {
            'ft_stats': self.ft_stats,
            'supervision_status': supervision_status,
            'cluster_status': cluster_status,
            'actor_system_status': {
                'node_id': self.actor_system.node_id,
                'running': self.actor_system.is_running,
                'total_actors': len(self.actor_system.actors)
            },
            'learning_engine_stats': {
                'active_models': len(self.learning_engine.learners),
                'total_updates': self.learning_engine.total_updates
            }
        }
    
    async def simulate_fault(self, actor_id: str, fault_type: FaultType = FaultType.ACTOR_CRASH):
        """Simulate a fault for testing purposes"""
        logger.info(f"🧪 Simulating {fault_type.value} fault for {actor_id}")
        
        await self.supervision_manager.handle_actor_failure(
            actor_id,
            Exception(f"Simulated {fault_type.value} fault"),
            fault_type
        )
    
    async def shutdown(self):
        """Graceful shutdown with fault tolerance"""
        logger.info("🛑 Shutting down Fault-Tolerant Actor Bridge...")
        
        # Close Kafka connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        
        # Stop actor system (supervision will handle cleanup)
        await self.actor_system.stop()
        
        # Final stats
        await self._log_ft_stats()
        
        logger.info("✅ Fault-Tolerant Actor Bridge shutdown complete")


async def main():
    """Main entry point for testing"""
    cluster_config = ClusterConfig(
        strategy=ClusterStrategy.LOAD_BALANCED,
        max_nodes=3,
        auto_scaling=True
    )
    
    bridge = FaultTolerantActorBridge(
        cluster_config=cluster_config,
        parallelism=3
    )
    
    try:
        await bridge.initialize()
        await bridge.process_fault_tolerant_stream()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await bridge.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
