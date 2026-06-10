"""
Flink-Style Stream Processor for TML Platform
Implements stateful stream processing without PyFlink dependencies
Mimics Apache Flink's keyed state and windowing capabilities
"""

import asyncio
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

import redis
from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from tml.core.inheritance import SpatialContext, SpatialInheritanceCoordinator
from tml.learning.online_learner import OnlineLearningEngine


@dataclass
class StreamState:
    """State for a keyed stream (similar to Flink's ValueState)"""

    model_id: str
    transaction_count: int = 0
    last_update: float = 0.0
    drift_score: float = 0.0
    parent_model_id: Optional[str] = None
    feature_history: List[Dict] = None
    checkpointed: bool = False

    def __post_init__(self):
        if self.feature_history is None:
            self.feature_history = []
        if self.last_update == 0:
            self.last_update = time.time()


class KeyedStateBackend:
    """
    State backend for keyed stream processing (mimics Flink's state backend)
    Uses Redis for persistence and fault tolerance
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.local_cache = {}
        self.checkpoint_interval = 30  # seconds
        self.last_checkpoint = time.time()

    def get_state(self, key: str) -> Optional[StreamState]:
        """Get state for a key"""
        # Check local cache first
        if key in self.local_cache:
            return self.local_cache[key]

        # Check Redis
        state_data = self.redis_client.get(f"state:{key}")
        if state_data:
            state_dict = json.loads(state_data)
            state = StreamState(**state_dict)
            self.local_cache[key] = state
            return state

        return None

    def update_state(self, key: str, state: StreamState):
        """Update state for a key"""
        self.local_cache[key] = state

        # Checkpoint to Redis periodically
        if time.time() - self.last_checkpoint > self.checkpoint_interval:
            self.checkpoint()

    def checkpoint(self):
        """Checkpoint all states to Redis"""
        for key, state in self.local_cache.items():
            state_json = json.dumps(asdict(state))
            self.redis_client.set(f"state:{key}", state_json, ex=3600)  # 1 hour TTL
            state.checkpointed = True

        self.last_checkpoint = time.time()
        logger.info(f"Checkpointed {len(self.local_cache)} states to Redis")


class StreamProcessor:
    """
    Flink-style stream processor with stateful processing
    """

    def __init__(self, parallelism: int = 4):
        self.parallelism = parallelism
        self.state_backend = KeyedStateBackend()
        self.learning_engine = OnlineLearningEngine()
        self.inheritance_coordinator = SpatialInheritanceCoordinator()
        self.executor = ThreadPoolExecutor(max_workers=parallelism)
        self.processing_stats = defaultdict(int)

        # Kafka setup
        self.consumer = None
        self.producer = None
        self.running = False

    def initialize_kafka(self, bootstrap_servers: str = "localhost:29092"):
        """Initialize Kafka consumer and producer"""
        self.consumer = KafkaConsumer(
            "transactions",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="flink-style-processor",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        logger.info(f"Initialized Kafka with {bootstrap_servers}")

    def key_by(self, transaction: Dict) -> str:
        """Extract key from transaction (similar to Flink's keyBy)"""
        return transaction.get(
            "model_id", f"model_{transaction.get('transaction_id', 'unknown')}"
        )

    def process_keyed_transaction(self, key: str, transaction: Dict) -> Dict:
        """
        Process a transaction for a specific key with state management
        Similar to Flink's KeyedProcessFunction
        """
        # Get or create state
        state = self.state_backend.get_state(key)
        if not state:
            state = self._create_state_with_inheritance(key, transaction)

        # Process with learning engine
        features = transaction.get("features", {})
        target = transaction.get("amount", 0) / 1000.0

        # Learn with spatial inheritance
        learned = self.learning_engine.learn(key, features, target)

        # Update state
        state.transaction_count += 1
        state.last_update = time.time()
        state.feature_history.append(features)

        # Keep only last 100 features for drift detection
        if len(state.feature_history) > 100:
            state.feature_history = state.feature_history[-100:]

        # Calculate drift
        if state.parent_model_id and len(state.feature_history) > 10:
            state.drift_score = self._calculate_drift(state.feature_history)

        # Update state backend
        self.state_backend.update_state(key, state)

        # Create output event
        result = {
            "model_id": key,
            "transaction_id": transaction.get("transaction_id"),
            "processed_at": time.time(),
            "transaction_count": state.transaction_count,
            "drift_score": state.drift_score,
            "parent_model": state.parent_model_id,
            "learned": learned,
            "spatial_inheritance": state.parent_model_id is not None,
            "state_checkpointed": state.checkpointed,
        }

        # Update stats
        self.processing_stats["transactions_processed"] += 1
        if state.parent_model_id:
            self.processing_stats["inheritance_applied"] += 1
        if state.drift_score > 0.1:
            self.processing_stats["drift_detected"] += 1

        return result

    def _create_state_with_inheritance(
        self, key: str, transaction: Dict
    ) -> StreamState:
        """Create state with spatial inheritance"""
        try:
            # Create spatial context
            context = SpatialContext(
                x_coord=transaction.get("x_coord", hash(key) % 100),
                y_coord=transaction.get("y_coord", hash(str(transaction)) % 100),
                timestamp=time.time(),
                domain=transaction.get("domain", "default"),
                features=transaction.get("features", {}),
                metadata=transaction,
            )

            # Find parent through inheritance
            inheritance_info = self.inheritance_coordinator.process_inheritance(
                key, context
            )

            parent_model_id = None
            if inheritance_info.get("parent_models"):
                parent_model_id = inheritance_info["parent_models"][0]
                logger.info(f"🧬 Model {key} inheriting from {parent_model_id}")
                self.processing_stats["models_with_inheritance"] += 1

            self.processing_stats["models_created"] += 1

            return StreamState(model_id=key, parent_model_id=parent_model_id)

        except Exception as e:
            logger.error(f"Error creating state with inheritance: {e}")
            return StreamState(model_id=key)

    def _calculate_drift(self, feature_history: List[Dict]) -> float:
        """Calculate drift score from feature history"""
        if len(feature_history) < 2:
            return 0.0

        # Compare recent features with older ones
        recent = feature_history[-10:]
        older = feature_history[:-10]

        drift_scores = []
        for feature_key in recent[0].keys():
            if isinstance(recent[0][feature_key], (int, float)):
                recent_values = [f.get(feature_key, 0) for f in recent]
                older_values = [f.get(feature_key, 0) for f in older]

                recent_mean = sum(recent_values) / len(recent_values)
                older_mean = (
                    sum(older_values) / len(older_values)
                    if older_values
                    else recent_mean
                )

                drift = abs(recent_mean - older_mean) / (abs(older_mean) + 1e-7)
                drift_scores.append(min(drift, 1.0))

        return sum(drift_scores) / len(drift_scores) if drift_scores else 0.0

    async def process_stream(self):
        """Main stream processing loop"""
        logger.info("Starting stream processing...")

        while self.running:
            try:
                # Poll for messages
                messages = self.consumer.poll(timeout_ms=1000)

                # Process messages in parallel
                futures = []
                for topic_partition, records in messages.items():
                    for record in records:
                        transaction = record.value
                        key = self.key_by(transaction)

                        # Submit to executor for parallel processing
                        future = self.executor.submit(
                            self.process_keyed_transaction, key, transaction
                        )
                        futures.append(future)

                # Collect results
                for future in futures:
                    try:
                        result = future.result(timeout=5)
                        # Send to output topic
                        self.producer.send("model-updates", result)

                        # Log progress
                        if self.processing_stats["transactions_processed"] % 10 == 0:
                            logger.info(
                                f"Processed {self.processing_stats['transactions_processed']} transactions | "
                                f"Models: {self.processing_stats['models_created']} | "
                                f"Inheritance: {self.processing_stats['models_with_inheritance']} | "
                                f"Drift: {self.processing_stats['drift_detected']}"
                            )
                    except Exception as e:
                        logger.error(f"Error processing result: {e}")

                # Periodic checkpoint
                if self.processing_stats["transactions_processed"] % 100 == 0:
                    self.state_backend.checkpoint()

            except Exception as e:
                logger.error(f"Error in stream processing: {e}")
                await asyncio.sleep(1)

    def start(self):
        """Start the stream processor"""
        logger.info("🚀 Starting Flink-style Stream Processor")
        self.initialize_kafka()
        self.running = True

        # Run async event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.process_stream())
        except KeyboardInterrupt:
            logger.info("Stream processor stopped by user")
        finally:
            self.stop()

    def stop(self):
        """Stop the stream processor"""
        logger.info("Stopping stream processor...")
        self.running = False

        # Final checkpoint
        self.state_backend.checkpoint()

        # Cleanup
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        self.executor.shutdown(wait=True)

        # Print final stats
        logger.info("=" * 60)
        logger.info("📊 Stream Processing Statistics")
        logger.info("=" * 60)
        for key, value in self.processing_stats.items():
            logger.info(f"  • {key}: {value}")


def main():
    """Main entry point"""
    processor = StreamProcessor(parallelism=4)
    processor.start()


if __name__ == "__main__":
    main()
