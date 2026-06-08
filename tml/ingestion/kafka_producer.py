"""Kafka producer for transaction events."""

import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

from kafka import KafkaProducer
from kafka.errors import KafkaError
from loguru import logger

from tml.core.config import config


@dataclass
class TransactionEvent:
    """Transaction event structure."""

    transaction_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    timestamp: float
    event_type: str  # purchase, click, view, etc.
    features: Dict[str, Any]
    target: Optional[Any] = None  # For supervised learning
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.transaction_id:
            self.transaction_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionEvent":
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "TransactionEvent":
        return cls.from_dict(json.loads(json_str))


class TransactionProducer:
    """Kafka producer for transaction events."""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.transaction_topic = config.kafka.transaction_topic
        self.model_updates_topic = config.kafka.model_updates_topic

        # Kafka producer configuration
        producer_config = {
            "bootstrap_servers": self.bootstrap_servers.split(","),
            "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
            "key_serializer": lambda k: k.encode("utf-8") if k else None,
            "acks": "all",  # Wait for all replicas
            "retries": 3,
            "batch_size": 16384,
            "linger_ms": 10,  # Small delay to batch messages
            "buffer_memory": 33554432,  # 32MB buffer
            "compression_type": "snappy",
            "max_in_flight_requests_per_connection": 5,
            "enable_idempotence": True,  # Exactly-once semantics
        }

        try:
            self.producer = KafkaProducer(**producer_config)
            logger.info(
                f"Kafka producer initialized with servers: {self.bootstrap_servers}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise

    def send_transaction(self, event: TransactionEvent) -> bool:
        """Send a transaction event to Kafka."""
        try:
            # Use transaction_id as partition key for consistent routing
            future = self.producer.send(
                topic=self.transaction_topic,
                key=event.transaction_id,
                value=event.to_dict(),
                partition=None,  # Let Kafka decide based on key
            )

            # Add callback for success/failure
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)

            logger.debug(
                f"Sent transaction {event.transaction_id} to topic {self.transaction_topic}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send transaction {event.transaction_id}: {e}")
            return False

    def send_model_update(self, model_id: str, update_data: Dict[str, Any]) -> bool:
        """Send a model update event to Kafka."""
        try:
            update_event = {
                "model_id": model_id,
                "timestamp": time.time(),
                "update_type": "incremental_learning",
                "data": update_data,
            }

            future = self.producer.send(
                topic=self.model_updates_topic, key=model_id, value=update_event
            )

            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)

            logger.debug(
                f"Sent model update for {model_id} to topic {self.model_updates_topic}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send model update for {model_id}: {e}")
            return False

    def send_batch_transactions(self, events: List[TransactionEvent]) -> int:
        """Send multiple transaction events in batch."""
        success_count = 0

        for event in events:
            if self.send_transaction(event):
                success_count += 1

        # Flush to ensure all messages are sent
        self.flush()

        logger.info(f"Sent {success_count}/{len(events)} transactions successfully")
        return success_count

    def flush(self, timeout: Optional[float] = None):
        """Flush pending messages."""
        try:
            self.producer.flush(timeout=timeout)
        except Exception as e:
            logger.error(f"Failed to flush producer: {e}")

    def close(self):
        """Close the producer."""
        try:
            self.producer.close()
            logger.info("Kafka producer closed")
        except Exception as e:
            logger.error(f"Error closing Kafka producer: {e}")

    def _on_send_success(self, record_metadata):
        """Callback for successful message send."""
        logger.debug(
            f"Message sent to topic {record_metadata.topic} "
            f"partition {record_metadata.partition} "
            f"offset {record_metadata.offset}"
        )

    def _on_send_error(self, exception):
        """Callback for failed message send."""
        logger.error(f"Failed to send message: {exception}")


class TransactionEventGenerator:
    """Generator for synthetic transaction events (for testing)."""

    def __init__(self):
        self.event_types = ["purchase", "click", "view", "add_to_cart", "search"]
        self.user_ids = [f"user_{i}" for i in range(1000)]

    def generate_event(
        self, event_type: Optional[str] = None, user_id: Optional[str] = None
    ) -> TransactionEvent:
        """Generate a synthetic transaction event."""
        import random

        if not event_type:
            event_type = random.choice(self.event_types)

        if not user_id:
            user_id = random.choice(self.user_ids)

        # Generate synthetic features based on event type
        features = self._generate_features(event_type)

        # Generate target (for supervised learning scenarios)
        target = self._generate_target(event_type, features)

        return TransactionEvent(
            transaction_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=f"session_{random.randint(1, 10000)}",
            timestamp=time.time(),
            event_type=event_type,
            features=features,
            target=target,
            metadata={"source": "synthetic_generator", "version": "1.0"},
        )

    def _generate_features(self, event_type: str) -> Dict[str, Any]:
        """Generate synthetic features based on event type."""
        import random

        base_features = {
            "hour_of_day": random.randint(0, 23),
            "day_of_week": random.randint(0, 6),
            "device_type": random.choice(["mobile", "desktop", "tablet"]),
            "browser": random.choice(["chrome", "firefox", "safari", "edge"]),
            "country": random.choice(["US", "UK", "CA", "DE", "FR"]),
        }

        if event_type == "purchase":
            base_features.update(
                {
                    "amount": round(random.uniform(10.0, 500.0), 2),
                    "category": random.choice(
                        ["electronics", "clothing", "books", "home"]
                    ),
                    "payment_method": random.choice(
                        ["credit_card", "paypal", "apple_pay"]
                    ),
                    "discount_applied": random.choice([True, False]),
                }
            )
        elif event_type == "click":
            base_features.update(
                {
                    "page_type": random.choice(
                        ["product", "category", "home", "search"]
                    ),
                    "position": random.randint(1, 20),
                    "element_type": random.choice(["button", "link", "image"]),
                }
            )
        elif event_type == "view":
            base_features.update(
                {
                    "page_type": random.choice(["product", "category", "home"]),
                    "time_on_page": random.randint(5, 300),
                    "scroll_depth": random.uniform(0.1, 1.0),
                }
            )
        elif event_type == "search":
            base_features.update(
                {
                    "query_length": random.randint(1, 50),
                    "results_count": random.randint(0, 1000),
                    "category_filter": random.choice([None, "electronics", "clothing"]),
                }
            )

        return base_features

    def _generate_target(self, event_type: str, features: Dict[str, Any]) -> Any:
        """Generate target variable based on event type and features."""
        import random

        if event_type == "purchase":
            # Binary classification: will user make another purchase in 30 days?
            # Higher probability for higher amounts and certain categories
            prob = 0.3
            if features.get("amount", 0) > 100:
                prob += 0.2
            if features.get("category") == "electronics":
                prob += 0.1
            return random.random() < prob

        elif event_type == "click":
            # Binary classification: will click lead to purchase?
            prob = 0.1
            if features.get("page_type") == "product":
                prob += 0.2
            if features.get("position", 0) <= 5:
                prob += 0.1
            return random.random() < prob

        elif event_type == "view":
            # Regression: predict time user will spend on site
            base_time = 60  # seconds
            if features.get("page_type") == "product":
                base_time += 30
            if features.get("device_type") == "mobile":
                base_time -= 20
            return max(10, base_time + random.randint(-30, 60))

        else:
            # Default binary classification
            return random.choice([True, False])

    def generate_batch(self, count: int) -> List[TransactionEvent]:
        """Generate a batch of synthetic events."""
        return [self.generate_event() for _ in range(count)]


# Example usage and testing functions
def test_producer():
    """Test the Kafka producer with synthetic data."""
    producer = TransactionProducer()
    generator = TransactionEventGenerator()

    try:
        # Generate and send test events
        events = generator.generate_batch(10)
        success_count = producer.send_batch_transactions(events)

        logger.info(f"Test completed: {success_count}/10 events sent successfully")

    finally:
        producer.close()


if __name__ == "__main__":
    test_producer()
