"""Kafka consumer for processing transaction events."""

import json
import time
import asyncio
from typing import Dict, Any, Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor

from kafka import KafkaConsumer
from kafka.errors import KafkaError
from loguru import logger

from tml.core.config import config
from tml.ingestion.kafka_producer import TransactionEvent


class TransactionConsumer:
    """Kafka consumer for processing transaction events."""

    def __init__(
        self,
        consumer_group: Optional[str] = None,
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "latest",
    ):
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.consumer_group = consumer_group or config.kafka.consumer_group
        self.transaction_topic = config.kafka.transaction_topic
        self.model_updates_topic = config.kafka.model_updates_topic

        # Consumer configuration
        consumer_config = {
            "bootstrap_servers": self.bootstrap_servers.split(","),
            "group_id": self.consumer_group,
            "auto_offset_reset": auto_offset_reset,
            "enable_auto_commit": False,  # Manual commit for better control
            "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
            "key_deserializer": lambda k: k.decode("utf-8") if k else None,
            "fetch_min_bytes": 1024,  # Minimum bytes to fetch
            "fetch_max_wait_ms": 500,  # Max wait time for fetch
            "max_poll_records": 100,  # Max records per poll
            "session_timeout_ms": 30000,
            "heartbeat_interval_ms": 10000,
        }

        try:
            self.consumer = KafkaConsumer(**consumer_config)
            logger.info(f"Kafka consumer initialized with group: {self.consumer_group}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise

        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.message_handlers: Dict[str, Callable] = {}

    def subscribe_to_transactions(self):
        """Subscribe to transaction events topic."""
        try:
            self.consumer.subscribe([self.transaction_topic])
            logger.info(f"Subscribed to topic: {self.transaction_topic}")
        except Exception as e:
            logger.error(f"Failed to subscribe to transactions topic: {e}")
            raise

    def subscribe_to_model_updates(self):
        """Subscribe to model updates topic."""
        try:
            self.consumer.subscribe([self.model_updates_topic])
            logger.info(f"Subscribed to topic: {self.model_updates_topic}")
        except Exception as e:
            logger.error(f"Failed to subscribe to model updates topic: {e}")
            raise

    def subscribe_to_all(self):
        """Subscribe to all topics."""
        try:
            topics = [self.transaction_topic, self.model_updates_topic]
            self.consumer.subscribe(topics)
            logger.info(f"Subscribed to topics: {topics}")
        except Exception as e:
            logger.error(f"Failed to subscribe to topics: {e}")
            raise

    def register_handler(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """Register a message handler for a specific topic."""
        self.message_handlers[topic] = handler
        logger.info(f"Registered handler for topic: {topic}")

    def start_consuming(self, timeout_ms: Optional[int] = None):
        """Start consuming messages synchronously."""
        self.running = True
        logger.info("Starting message consumption...")

        try:
            while self.running:
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=timeout_ms or 1000)

                if not message_batch:
                    continue

                # Process messages by topic
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic

                    for message in messages:
                        try:
                            self._process_message(topic, message)
                        except Exception as e:
                            logger.error(f"Error processing message from {topic}: {e}")

                # Commit offsets after processing batch
                try:
                    self.consumer.commit()
                except Exception as e:
                    logger.error(f"Failed to commit offsets: {e}")

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping consumer...")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            self.stop_consuming()

    async def start_consuming_async(self, timeout_ms: Optional[int] = None):
        """Start consuming messages asynchronously."""
        self.running = True
        logger.info("Starting async message consumption...")

        try:
            while self.running:
                # Run polling in executor to avoid blocking
                message_batch = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: self.consumer.poll(timeout_ms=timeout_ms or 1000),
                )

                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue

                # Process messages concurrently
                tasks = []
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic

                    for message in messages:
                        task = asyncio.create_task(
                            self._process_message_async(topic, message)
                        )
                        tasks.append(task)

                # Wait for all messages to be processed
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Commit offsets
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, self.consumer.commit
                    )
                except Exception as e:
                    logger.error(f"Failed to commit offsets: {e}")

        except asyncio.CancelledError:
            logger.info("Async consumer cancelled")
        except Exception as e:
            logger.error(f"Async consumer error: {e}")
        finally:
            self.stop_consuming()

    def _process_message(self, topic: str, message):
        """Process a single message synchronously."""
        try:
            # Extract message data
            data = {
                "topic": topic,
                "partition": message.partition,
                "offset": message.offset,
                "key": message.key,
                "value": message.value,
                "timestamp": message.timestamp,
            }

            # Call registered handler if available
            if topic in self.message_handlers:
                self.message_handlers[topic](data)
            else:
                # Default processing
                self._default_message_handler(data)

        except Exception as e:
            logger.error(f"Error in message processing: {e}")

    async def _process_message_async(self, topic: str, message):
        """Process a single message asynchronously."""
        try:
            # Extract message data
            data = {
                "topic": topic,
                "partition": message.partition,
                "offset": message.offset,
                "key": message.key,
                "value": message.value,
                "timestamp": message.timestamp,
            }

            # Call registered handler if available
            if topic in self.message_handlers:
                # Run handler in executor if it's not async
                handler = self.message_handlers[topic]
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, handler, data
                    )
            else:
                # Default processing
                await self._default_message_handler_async(data)

        except Exception as e:
            logger.error(f"Error in async message processing: {e}")

    def _default_message_handler(self, data: Dict[str, Any]):
        """Default message handler."""
        topic = data["topic"]
        value = data["value"]

        if topic == self.transaction_topic:
            # Process transaction event
            try:
                event = TransactionEvent.from_dict(value)
                logger.debug(f"Processed transaction: {event.transaction_id}")
                # Here you would typically send to the learning pipeline
            except Exception as e:
                logger.error(f"Failed to parse transaction event: {e}")

        elif topic == self.model_updates_topic:
            # Process model update
            try:
                model_id = value.get("model_id")
                update_type = value.get("update_type")
                logger.debug(f"Processed model update: {model_id} ({update_type})")
                # Here you would typically update the model registry
            except Exception as e:
                logger.error(f"Failed to parse model update: {e}")

    async def _default_message_handler_async(self, data: Dict[str, Any]):
        """Default async message handler."""
        # Run default handler in executor
        await asyncio.get_event_loop().run_in_executor(
            self.executor, self._default_message_handler, data
        )

    def stop_consuming(self):
        """Stop consuming messages."""
        self.running = False
        try:
            self.consumer.close()
            logger.info("Kafka consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping consumer: {e}")

    def get_consumer_metadata(self) -> Dict[str, Any]:
        """Get consumer metadata and statistics."""
        try:
            return {
                "group_id": self.consumer_group,
                "subscribed_topics": list(self.consumer.subscription()),
                "assignment": [
                    {"topic": tp.topic, "partition": tp.partition}
                    for tp in self.consumer.assignment()
                ],
                "position": {
                    f"{tp.topic}-{tp.partition}": self.consumer.position(tp)
                    for tp in self.consumer.assignment()
                },
            }
        except Exception as e:
            logger.error(f"Failed to get consumer metadata: {e}")
            return {}


class TransactionProcessor:
    """High-level processor for transaction events."""

    def __init__(self):
        self.consumer = TransactionConsumer()
        self.processed_count = 0
        self.error_count = 0
        self.start_time = time.time()

    def setup_handlers(self):
        """Setup message handlers."""
        self.consumer.register_handler(
            self.consumer.transaction_topic, self.handle_transaction
        )
        self.consumer.register_handler(
            self.consumer.model_updates_topic, self.handle_model_update
        )

    def handle_transaction(self, data: Dict[str, Any]):
        """Handle transaction event."""
        try:
            event_data = data["value"]
            event = TransactionEvent.from_dict(event_data)

            # Process the transaction
            self._process_transaction_event(event)

            self.processed_count += 1

            if self.processed_count % 100 == 0:
                self._log_processing_stats()

        except Exception as e:
            logger.error(f"Error handling transaction: {e}")
            self.error_count += 1

    def handle_model_update(self, data: Dict[str, Any]):
        """Handle model update event."""
        try:
            update_data = data["value"]
            model_id = update_data.get("model_id")

            # Process the model update
            self._process_model_update(model_id, update_data)

            logger.debug(f"Processed model update for {model_id}")

        except Exception as e:
            logger.error(f"Error handling model update: {e}")
            self.error_count += 1

    def _process_transaction_event(self, event: TransactionEvent):
        """Process a transaction event (placeholder for actual ML pipeline)."""
        # This is where you would:
        # 1. Extract features
        # 2. Get or create the appropriate model
        # 3. Make prediction
        # 4. Update model if target is available
        # 5. Store results

        logger.debug(
            f"Processing transaction {event.transaction_id} "
            f"for user {event.user_id}"
        )

    def _process_model_update(self, model_id: str, update_data: Dict[str, Any]):
        """Process a model update event."""
        # This is where you would:
        # 1. Load the model from registry
        # 2. Apply the update
        # 3. Store updated model
        # 4. Update metadata

        logger.debug(f"Processing update for model {model_id}")

    def _log_processing_stats(self):
        """Log processing statistics."""
        elapsed = time.time() - self.start_time
        rate = self.processed_count / elapsed if elapsed > 0 else 0

        logger.info(
            f"Processed {self.processed_count} events "
            f"({rate:.2f} events/sec), {self.error_count} errors"
        )

    def start(self):
        """Start the processor."""
        self.setup_handlers()
        self.consumer.subscribe_to_all()

        try:
            self.consumer.start_consuming()
        except KeyboardInterrupt:
            logger.info("Processor stopped by user")
        finally:
            self.consumer.stop_consuming()

    async def start_async(self):
        """Start the processor asynchronously."""
        self.setup_handlers()
        self.consumer.subscribe_to_all()

        try:
            await self.consumer.start_consuming_async()
        except asyncio.CancelledError:
            logger.info("Async processor cancelled")
        finally:
            self.consumer.stop_consuming()


# Example usage
def test_consumer():
    """Test the Kafka consumer."""
    processor = TransactionProcessor()
    processor.start()


if __name__ == "__main__":
    test_consumer()
