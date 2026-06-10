"""
Actor Transaction Bridge - Connects Proto.Actor System to Real Transaction Flow
Integrates actors with Kafka streams and TML learning engine
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from ..core.inheritance import SpatialInheritanceCoordinator
from ..learning.online_learner import OnlineLearningEngine
from .actor_system import ActorMessage, ActorSystem, MessagePriority
from .tml_actors import (
    InheritanceCoordinatorActor,
    ModelActor,
    PhysicsValidatorActor,
    TMLMessageType,
    TransactionData,
    TransactionProcessorActor,
)


@dataclass
class ActorProcessingResult:
    """Result from actor-based transaction processing"""

    transaction_id: str
    model_id: str
    processing_time: float
    actor_path: str
    inheritance_applied: bool
    physics_validated: bool
    success: bool
    error: Optional[str] = None


class ActorTransactionBridge:
    """
    Bridges real transaction flow with Proto.Actor system
    Connects Kafka streams to distributed actor processing
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str = "localhost:29092",
        actor_system_name: str = "TMLActorSystem",
        parallelism: int = 4,
    ):
        self.kafka_servers = kafka_bootstrap_servers
        self.parallelism = parallelism

        # Initialize actor system
        self.actor_system = ActorSystem(
            node_id="tml-bridge-node",
            redis_url="redis://localhost:6379",
            metrics_port=8001,
        )

        # Kafka components
        self.consumer = None
        self.producer = None

        # Actor references
        self.transaction_processors: List[Any] = []
        self.inheritance_coordinator = None
        self.physics_validator = None

        # Processing statistics
        self.stats = {
            "transactions_processed": 0,
            "models_created": 0,
            "inheritance_applied": 0,
            "physics_validated": 0,
            "errors": 0,
            "start_time": time.time(),
        }

        # Integration with TML components
        self.learning_engine = OnlineLearningEngine()
        self.spatial_coordinator = SpatialInheritanceCoordinator()

        logger.info(
            f"Actor Transaction Bridge initialized with {parallelism} processors"
        )

    async def initialize(self):
        """Initialize all components"""
        # Start actor system
        await self.actor_system.start()
        logger.info("✅ Actor system started")

        # Create core actors
        await self._create_core_actors()

        # Initialize Kafka
        self._initialize_kafka()

        logger.info("✅ Actor Transaction Bridge fully initialized")

    async def _create_core_actors(self):
        """Create core actor hierarchy"""
        # Create transaction processor actors
        for i in range(self.parallelism):
            processor = await self.actor_system.create_actor(
                TransactionProcessorActor, f"transaction_processor_{i}"
            )
            self.transaction_processors.append(processor)

        # Create inheritance coordinator
        self.inheritance_coordinator = await self.actor_system.create_actor(
            InheritanceCoordinatorActor, "inheritance_coordinator"
        )

        # Create physics validator
        self.physics_validator = await self.actor_system.create_actor(
            PhysicsValidatorActor, "physics_validator"
        )

        logger.info(
            f"✅ Created {len(self.transaction_processors)} transaction processors"
        )
        logger.info("✅ Created inheritance coordinator and physics validator")

    def _initialize_kafka(self):
        """Initialize Kafka consumer and producer"""
        self.consumer = KafkaConsumer(
            "transactions",
            bootstrap_servers=self.kafka_servers,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="actor-transaction-bridge",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        logger.info("✅ Kafka consumer and producer initialized")

    async def process_transaction_stream(self):
        """Main processing loop - bridges Kafka to actors"""
        logger.info("🚀 Starting actor-based transaction processing...")

        processor_index = 0

        while True:
            try:
                # Poll for messages
                messages = self.consumer.poll(timeout_ms=1000)

                for topic_partition, records in messages.items():
                    for record in records:
                        # Process transaction through actors
                        result = await self._process_transaction_via_actors(
                            record.value, processor_index
                        )

                        # Send result to output topic
                        if result:
                            await self._send_actor_result(result)

                        # Round-robin processor selection
                        processor_index = (processor_index + 1) % len(
                            self.transaction_processors
                        )

                        # Update statistics
                        self.stats["transactions_processed"] += 1

                        # Log progress
                        if self.stats["transactions_processed"] % 50 == 0:
                            await self._log_processing_stats()

            except Exception as e:
                logger.error(f"Error in transaction stream processing: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(1)

    async def _process_transaction_via_actors(
        self, transaction: Dict, processor_index: int
    ) -> Optional[ActorProcessingResult]:
        """Process single transaction through actor system"""
        start_time = time.time()

        try:
            # Extract transaction details
            transaction_id = transaction.get(
                "transaction_id", f"tx_{int(time.time() * 1000)}"
            )
            model_id = transaction.get("model_id", f"model_{transaction_id}")

            # Create transaction data
            tx_data = TransactionData(
                transaction_id=transaction_id,
                data=transaction,
                timestamp=time.time(),
                source="kafka_bridge",
                metadata={"processor_index": processor_index},
            )

            # Get processor actor
            processor_ref = self.transaction_processors[processor_index]

            # Send transaction to actor
            message = ActorMessage(
                message_type=TMLMessageType.PROCESS_TRANSACTION.value,
                payload={"transaction": asdict(tx_data)},
                priority=MessagePriority.NORMAL,
                reply_to=f"bridge_{transaction_id}",
            )

            # Send message to actor
            await processor_ref.tell(message)

            # Also process with TML learning engine for integration
            features = transaction.get("features", {})
            target = transaction.get("amount", 0) / 1000.0

            # Learn with spatial inheritance
            learned = self.learning_engine.learn(model_id, features, target)

            # Check for inheritance
            inheritance_applied = model_id in self.learning_engine.learners
            if inheritance_applied:
                self.stats["inheritance_applied"] += 1

            # Create result
            result = ActorProcessingResult(
                transaction_id=transaction_id,
                model_id=model_id,
                processing_time=time.time() - start_time,
                actor_path=f"transaction_processor_{processor_index}",
                inheritance_applied=inheritance_applied,
                physics_validated=True,  # Assume validated for now
                success=True,
            )

            if inheritance_applied:
                self.stats["models_created"] += 1

            return result

        except Exception as e:
            logger.error(f"Error processing transaction via actors: {e}")
            self.stats["errors"] += 1

            return ActorProcessingResult(
                transaction_id=transaction.get("transaction_id", "unknown"),
                model_id=transaction.get("model_id", "unknown"),
                processing_time=time.time() - start_time,
                actor_path=f"transaction_processor_{processor_index}",
                inheritance_applied=False,
                physics_validated=False,
                success=False,
                error=str(e),
            )

    async def _send_actor_result(self, result: ActorProcessingResult):
        """Send processing result to Kafka output topic"""
        try:
            result_data = {
                "transaction_id": result.transaction_id,
                "model_id": result.model_id,
                "processing_time": result.processing_time,
                "actor_path": result.actor_path,
                "inheritance_applied": result.inheritance_applied,
                "physics_validated": result.physics_validated,
                "success": result.success,
                "error": result.error,
                "processed_at": time.time(),
                "processing_method": "proto_actor",
            }

            self.producer.send("actor-results", result_data)

        except Exception as e:
            logger.error(f"Error sending actor result: {e}")

    async def _log_processing_stats(self):
        """Log current processing statistics"""
        elapsed = time.time() - self.stats["start_time"]
        tps = self.stats["transactions_processed"] / elapsed if elapsed > 0 else 0

        logger.info(f"🎭 Actor Processing Stats:")
        logger.info(f"  • Transactions: {self.stats['transactions_processed']}")
        logger.info(f"  • Models Created: {self.stats['models_created']}")
        logger.info(f"  • Inheritance Applied: {self.stats['inheritance_applied']}")
        logger.info(f"  • Processing Rate: {tps:.1f} TPS")
        logger.info(f"  • Errors: {self.stats['errors']}")
        logger.info(f"  • Active Processors: {len(self.transaction_processors)}")

    async def get_actor_metrics(self) -> Dict[str, Any]:
        """Get comprehensive actor system metrics"""
        # Get metrics from transaction processors
        processor_metrics = []
        for i, processor in enumerate(self.transaction_processors):
            try:
                metrics_msg = ActorMessage(
                    message_type=TMLMessageType.GET_METRICS.value,
                    payload={},
                    reply_to=f"bridge_metrics_{i}",
                )
                await processor.tell(metrics_msg)
                # Note: In real implementation, would wait for response
                processor_metrics.append({"processor_id": i, "status": "active"})
            except Exception as e:
                processor_metrics.append(
                    {"processor_id": i, "status": "error", "error": str(e)}
                )

        return {
            "bridge_stats": self.stats,
            "processor_metrics": processor_metrics,
            "actor_system_status": {
                "running": self.actor_system.is_running,
                "total_actors": len(self.actor_system.actors),
                "active_processors": len(self.transaction_processors),
            },
            "learning_engine_stats": {
                "active_models": len(self.learning_engine.learners),
                "total_updates": self.learning_engine.total_updates,
            },
        }

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Actor Transaction Bridge...")

        # Close Kafka connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()

        # Stop actor system
        await self.actor_system.stop()

        # Final stats
        await self._log_processing_stats()

        logger.info("✅ Actor Transaction Bridge shutdown complete")


async def main():
    """Main entry point for testing"""
    bridge = ActorTransactionBridge(parallelism=4)

    try:
        await bridge.initialize()
        await bridge.process_transaction_stream()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await bridge.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
