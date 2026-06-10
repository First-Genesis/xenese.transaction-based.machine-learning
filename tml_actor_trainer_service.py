#!/usr/bin/env python3
"""TML Actor-Based Model Trainer Service for Production UAT."""

import asyncio
import json
import signal
import sys
import time
from typing import Any, Dict, Optional

from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from tml.core.config import config
from tml.orchestration.actor_system import ActorSystem, ActorMessage
from tml.orchestration.tml_actors import (
    TransactionProcessorActor,
    ModelActor,
    InheritanceCoordinatorActor,
    PhysicsValidatorActor,
    TMLMessageType,
    TransactionData
)


class ActorBasedModelTrainerService:
    """Production model training service using Proto.Actor pattern."""

    def __init__(self):
        """Initialize the actor-based model trainer service."""
        self.running = False
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
        self.actor_system: Optional[ActorSystem] = None
        
        # Actor references
        self.transaction_processor = None
        self.inheritance_coordinator = None
        self.physics_validator = None
        self.model_actors = {}  # model_id -> actor_ref
        
        # Metrics
        self.processed_count = 0
        self.model_updates = 0
        self.start_time = time.time()

    async def initialize(self):
        """Initialize Kafka connections and Actor system."""
        logger.info("Initializing Actor-Based Model Trainer Service...")
        
        # Setup Kafka consumer
        self.consumer = KafkaConsumer(
            "transactions",
            "training-requests",
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            group_id="tml_actor_trainers",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        
        # Setup Kafka producer for model updates
        self.producer = KafkaProducer(
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
        )
        
        # Initialize Actor System with custom port
        self.actor_system = ActorSystem(
            node_id="tml-trainer-node",
            redis_url="redis://localhost:6379",
            metrics_port=8001  # Use different port to avoid conflicts
        )
        await self.actor_system.start()
        
        # Deploy core actors
        await self.deploy_core_actors()
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("✅ Actor-Based Model Trainer Service initialized with Proto.Actor system")

    async def deploy_core_actors(self):
        """Deploy the core TML actors."""
        logger.info("🎭 Deploying TML Actor System...")
        
        # Deploy Inheritance Coordinator
        self.inheritance_coordinator = await self.actor_system.create_actor(
            InheritanceCoordinatorActor, "inheritance_coordinator"
        )
        logger.info("✅ Deployed InheritanceCoordinatorActor")
        
        # Deploy Physics Validator
        self.physics_validator = await self.actor_system.create_actor(
            PhysicsValidatorActor, "physics_validator"
        )
        logger.info("✅ Deployed PhysicsValidatorActor")
        
        # Deploy Transaction Processor
        self.transaction_processor = await self.actor_system.create_actor(
            TransactionProcessorActor, "transaction_processor"
        )
        logger.info("✅ Deployed TransactionProcessorActor")
        
        logger.info("🎭 TML Actor System deployment complete!")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down actor system...")
        self.running = False

    async def get_or_create_model_actor(self, model_id: str) -> Any:
        """Get existing model actor or create new one with spatial inheritance."""
        if model_id not in self.model_actors:
            # Create new model actor
            model_actor = await self.actor_system.create_actor(
                ModelActor, f"model_{model_id}"
            )
            self.model_actors[model_id] = model_actor
            
            logger.info(f"🎭 Created new ModelActor for {model_id} with spatial inheritance")
            
        return self.model_actors[model_id]

    async def process_transaction_with_actors(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process transaction using the actor system."""
        try:
            # Convert to TransactionData
            transaction = TransactionData(
                transaction_id=transaction_data.get("transaction_id", "unknown"),
                user_id=transaction_data.get("user_id", "unknown"),
                amount=transaction_data.get("amount", 0.0),
                features=transaction_data.get("features", {}),
                timestamp=transaction_data.get("timestamp", time.time()),
                metadata=transaction_data.get("metadata", {})
            )
            
            # Step 1: Process transaction through TransactionProcessorActor
            process_message = ActorMessage(
                message_type=TMLMessageType.PROCESS_TRANSACTION.value,
                payload={"transaction": transaction.__dict__}
            )
            
            process_result = await self.transaction_processor.ask(process_message, timeout=10.0)
            
            if not process_result.get("success", False):
                return {"success": False, "error": "Transaction processing failed"}
            
            # Step 2: Get or create model actor for this model
            model_id = transaction_data.get("model_id", "default")
            model_actor = await self.get_or_create_model_actor(model_id)
            
            # Step 3: Train model through ModelActor (with spatial inheritance)
            train_message = ActorMessage(
                message_type=TMLMessageType.TRAIN_MODEL.value,
                payload={
                    "transaction": transaction.__dict__,
                    "model_id": model_id
                }
            )
            
            train_result = await model_actor.ask(train_message, timeout=15.0)
            
            if train_result.get("model_updated", False):
                self.model_updates += 1
                
                # Publish model update event
                update_event = {
                    "model_id": model_id,
                    "timestamp": time.time(),
                    "update_type": "actor_based_incremental",
                    "actor_id": f"model_{model_id}",
                    "inheritance_applied": train_result.get("inheritance_applied", False),
                    "physics_validated": train_result.get("physics_valid", False)
                }
                
                self.producer.send("model-updates", value=update_event)
                logger.info(f"🎭 Actor-based model {model_id} updated successfully")
            
            return {
                "success": True,
                "model_id": model_id,
                "updated": train_result.get("model_updated", False),
                "inheritance_applied": train_result.get("inheritance_applied", False),
                "physics_validated": train_result.get("physics_valid", False),
                "actor_system": "proto_actor"
            }
            
        except Exception as e:
            logger.error(f"Error processing transaction with actors: {e}")
            return {"success": False, "error": str(e)}

    def process_message(self, message):
        """Process a single Kafka message using actors."""
        try:
            transaction_data = message.value
            
            # Run async actor processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.process_transaction_with_actors(transaction_data)
            )
            loop.close()
            
            self.processed_count += 1
            
            if self.processed_count % 50 == 0:
                asyncio.run(self.report_actor_metrics())
                
        except Exception as e:
            logger.error(f"Error processing message with actors: {e}")

    async def report_actor_metrics(self):
        """Report actor system metrics."""
        uptime = time.time() - self.start_time
        rate = self.processed_count / uptime if uptime > 0 else 0
        
        # Get actor system health
        actor_health = await self.actor_system.get_health_status()
        
        metrics = {
            "processed_transactions": self.processed_count,
            "model_updates": self.model_updates,
            "processing_rate": f"{rate:.2f} tx/sec",
            "uptime_seconds": uptime,
            "actor_system": {
                "total_actors": len(self.actor_system.actors),
                "model_actors": len(self.model_actors),
                "system_health": actor_health,
                "inheritance_coordinator": "active",
                "physics_validator": "active"
            }
        }
        
        logger.info(f"🎭 Actor System Metrics: {metrics}")
        
        # Publish metrics
        self.producer.send("service-metrics", value={
            "service": "actor-model-trainer",
            "metrics": metrics,
            "timestamp": time.time()
        })

    async def run_async(self):
        """Main async service loop."""
        self.running = True
        logger.info("🎭 Actor-Based Model Trainer Service started, waiting for messages...")
        
        while self.running:
            try:
                # Poll for messages with timeout
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for message in records:
                        self.process_message(message)
                        
            except Exception as e:
                logger.error(f"Error in actor main loop: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
        
        await self.shutdown()

    def run(self):
        """Main service loop (sync wrapper)."""
        asyncio.run(self.run_async())

    async def shutdown(self):
        """Clean shutdown of the actor system."""
        logger.info("🎭 Shutting down Actor-Based Model Trainer Service...")
        
        # Report final metrics
        await self.report_actor_metrics()
        
        # Shutdown actor system
        if self.actor_system:
            await self.actor_system.stop()
        
        # Clean up connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        
        logger.info(f"🎭 Actor-Based Service stopped. Processed {self.processed_count} transactions with {len(self.model_actors)} model actors")


async def main():
    """Main entry point for the actor-based service."""
    logger.info("🎭 Starting TML Actor-Based Model Trainer Service for Production UAT")
    
    service = ActorBasedModelTrainerService()
    await service.initialize()
    
    try:
        await service.run_async()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Actor service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
