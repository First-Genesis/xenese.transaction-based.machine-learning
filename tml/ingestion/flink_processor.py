"""Apache Flink stream processor for stateful transaction processing."""

import json
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.datastream.formats.json import (
    JsonRowDeserializationSchema,
    JsonRowSerializationSchema,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream.functions import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ValueStateDescriptor, ListStateDescriptor
from pyflink.common.time import Time
from loguru import logger

from tml.core.config import config
from tml.ingestion.kafka_producer import TransactionEvent


@dataclass
class ModelState:
    """State information for a transaction model."""

    model_id: str
    last_updated: float
    prediction_count: int
    update_count: int
    accuracy: float
    drift_score: float
    features_seen: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "last_updated": self.last_updated,
            "prediction_count": self.prediction_count,
            "update_count": self.update_count,
            "accuracy": self.accuracy,
            "drift_score": self.drift_score,
            "features_seen": self.features_seen,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelState":
        return cls(**data)


class TransactionModelProcessor(KeyedProcessFunction):
    """Flink keyed process function for per-model state management."""

    def __init__(self):
        self.model_state_descriptor = None
        self.feature_history_descriptor = None
        self.model_state = None
        self.feature_history = None

    def open(self, runtime_context: RuntimeContext):
        """Initialize state descriptors."""
        # State for model metadata
        self.model_state_descriptor = ValueStateDescriptor(
            "model_state", Types.STRING()  # JSON serialized ModelState
        )
        self.model_state = runtime_context.get_state(self.model_state_descriptor)

        # State for feature history (for drift detection)
        self.feature_history_descriptor = ListStateDescriptor(
            "feature_history", Types.STRING()  # JSON serialized features
        )
        self.feature_history = runtime_context.get_list_state(
            self.feature_history_descriptor
        )

    def process_element(self, value, ctx, out):
        """Process a transaction event for a specific model."""
        try:
            # Parse transaction event
            event_data = json.loads(value)
            event = TransactionEvent.from_dict(event_data)

            # Get or create model state
            current_state = self._get_or_create_model_state(event)

            # Process the transaction
            result = self._process_transaction(event, current_state, ctx)

            # Update state
            self._update_model_state(current_state)

            # Output result
            out.collect(json.dumps(result))

        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
            # Output error event
            error_result = {"error": str(e), "timestamp": time.time(), "input": value}
            out.collect(json.dumps(error_result))

    def _get_or_create_model_state(self, event: TransactionEvent) -> ModelState:
        """Get existing model state or create new one."""
        try:
            state_json = self.model_state.value()
            if state_json:
                return ModelState.from_dict(json.loads(state_json))
            else:
                # Create new model state
                model_id = self._generate_model_id(event)
                return ModelState(
                    model_id=model_id,
                    last_updated=time.time(),
                    prediction_count=0,
                    update_count=0,
                    accuracy=0.0,
                    drift_score=0.0,
                    features_seen=0,
                )
        except Exception as e:
            logger.error(f"Error getting model state: {e}")
            # Return default state
            return ModelState(
                model_id=f"error_model_{int(time.time())}",
                last_updated=time.time(),
                prediction_count=0,
                update_count=0,
                accuracy=0.0,
                drift_score=0.0,
                features_seen=0,
            )

    def _generate_model_id(self, event: TransactionEvent) -> str:
        """Generate model ID based on transaction context."""
        # Use user_id as the key for model creation
        # In practice, you might use more sophisticated routing
        if event.user_id:
            return f"model_user_{event.user_id}"
        else:
            return f"model_session_{event.session_id or 'anonymous'}"

    def _process_transaction(
        self, event: TransactionEvent, state: ModelState, ctx
    ) -> Dict[str, Any]:
        """Process transaction and update model state."""

        # Update feature history for drift detection
        self._update_feature_history(event.features)

        # Calculate drift score
        drift_score = self._calculate_drift_score()
        state.drift_score = drift_score

        # Simulate model prediction and update
        prediction = self._make_prediction(event.features, state)
        state.prediction_count += 1

        # If we have a target, update the model
        if event.target is not None:
            accuracy = self._update_model(event.features, event.target, state)
            state.accuracy = accuracy
            state.update_count += 1

        state.features_seen += len(event.features)
        state.last_updated = time.time()

        # Prepare result
        result = {
            "transaction_id": event.transaction_id,
            "model_id": state.model_id,
            "prediction": prediction,
            "model_state": state.to_dict(),
            "drift_detected": drift_score > 0.1,  # Threshold
            "timestamp": time.time(),
            "processing_time_ms": ctx.timestamp(),
        }

        return result

    def _update_feature_history(self, features: Dict[str, Any]):
        """Update feature history for drift detection."""
        try:
            # Add current features to history
            feature_json = json.dumps(features)
            self.feature_history.add(feature_json)

            # Keep only recent history (last 100 transactions)
            history_list = list(self.feature_history.get())
            if len(history_list) > 100:
                # Clear and re-add recent items
                self.feature_history.clear()
                for item in history_list[-100:]:
                    self.feature_history.add(item)

        except Exception as e:
            logger.error(f"Error updating feature history: {e}")

    def _calculate_drift_score(self) -> float:
        """Calculate concept drift score based on feature history."""
        try:
            history_list = list(self.feature_history.get())
            if len(history_list) < 10:
                return 0.0

            # Simple drift detection: compare recent vs older features
            # In practice, you'd use more sophisticated methods
            recent_features = history_list[-10:]
            older_features = history_list[-20:-10] if len(history_list) >= 20 else []

            if not older_features:
                return 0.0

            # Calculate feature distribution differences (simplified)
            drift_score = 0.0
            for recent_json in recent_features:
                recent = json.loads(recent_json)
                for older_json in older_features:
                    older = json.loads(older_json)
                    # Simple difference calculation
                    for key in recent:
                        if key in older and isinstance(recent[key], (int, float)):
                            diff = abs(recent[key] - older[key])
                            drift_score += diff

            # Normalize by number of comparisons
            num_comparisons = len(recent_features) * len(older_features)
            return drift_score / num_comparisons if num_comparisons > 0 else 0.0

        except Exception as e:
            logger.error(f"Error calculating drift score: {e}")
            return 0.0

    def _make_prediction(self, features: Dict[str, Any], state: ModelState) -> Any:
        """Make a prediction using the model (simplified)."""
        # This is a placeholder - in practice, you'd load the actual model
        # and make a real prediction

        # Simple heuristic prediction based on features
        if "amount" in features:
            # For purchase prediction
            return features["amount"] > 100
        elif "time_on_page" in features:
            # For engagement prediction
            return features["time_on_page"] > 60
        else:
            # Default prediction
            return True

    def _update_model(
        self, features: Dict[str, Any], target: Any, state: ModelState
    ) -> float:
        """Update model with new data and return accuracy."""
        # This is a placeholder - in practice, you'd update the actual model

        # Simulate accuracy calculation
        prediction = self._make_prediction(features, state)
        correct = prediction == target

        # Update running accuracy
        total_updates = state.update_count + 1
        if state.update_count == 0:
            new_accuracy = 1.0 if correct else 0.0
        else:
            new_accuracy = (
                state.accuracy * state.update_count + (1.0 if correct else 0.0)
            ) / total_updates

        return new_accuracy

    def _update_model_state(self, state: ModelState):
        """Update the stored model state."""
        try:
            state_json = json.dumps(state.to_dict())
            self.model_state.update(state_json)
        except Exception as e:
            logger.error(f"Error updating model state: {e}")


class FlinkTransactionProcessor:
    """Main Flink processor for transaction streams."""

    def __init__(self):
        self.env = StreamExecutionEnvironment.get_execution_environment()
        self.env.set_parallelism(4)  # Adjust based on your cluster

        # Configure checkpointing for fault tolerance
        self.env.enable_checkpointing(60000)  # Checkpoint every minute

    def create_kafka_source(self) -> FlinkKafkaConsumer:
        """Create Kafka source for transaction events."""
        properties = {
            "bootstrap.servers": config.kafka.bootstrap_servers,
            "group.id": f"{config.kafka.consumer_group}_flink",
        }

        kafka_consumer = FlinkKafkaConsumer(
            topics=[config.kafka.transaction_topic],
            deserialization_schema=SimpleStringSchema(),
            properties=properties,
        )

        # Start from latest offset
        kafka_consumer.set_start_from_latest()

        return kafka_consumer

    def create_kafka_sink(self, topic: str) -> FlinkKafkaProducer:
        """Create Kafka sink for processed results."""
        properties = {"bootstrap.servers": config.kafka.bootstrap_servers}

        kafka_producer = FlinkKafkaProducer(
            topic=topic,
            serialization_schema=SimpleStringSchema(),
            producer_config=properties,
        )

        return kafka_producer

    def setup_processing_pipeline(self):
        """Setup the main processing pipeline."""

        # Create Kafka source
        kafka_source = self.create_kafka_source()

        # Create data stream
        transaction_stream = self.env.add_source(kafka_source)

        # Key by user_id for stateful processing
        keyed_stream = transaction_stream.key_by(
            lambda x: json.loads(x).get("user_id", "anonymous")
        )

        # Process transactions with stateful function
        processed_stream = keyed_stream.process(TransactionModelProcessor())

        # Create output sinks
        results_sink = self.create_kafka_sink("processed_transactions")
        processed_stream.add_sink(results_sink)

        # Optional: Create side outputs for monitoring
        # You could split the stream based on drift detection, errors, etc.

        return processed_stream

    def run(self, job_name: str = "TML Transaction Processor"):
        """Run the Flink job."""
        try:
            # Setup pipeline
            self.setup_processing_pipeline()

            # Execute the job
            logger.info(f"Starting Flink job: {job_name}")
            self.env.execute(job_name)

        except Exception as e:
            logger.error(f"Error running Flink job: {e}")
            raise


class FlinkJobManager:
    """Manager for Flink jobs and deployment."""

    def __init__(self):
        self.processors: Dict[str, FlinkTransactionProcessor] = {}

    def create_processor(self, name: str) -> FlinkTransactionProcessor:
        """Create a new Flink processor."""
        processor = FlinkTransactionProcessor()
        self.processors[name] = processor
        return processor

    def run_processor(self, name: str):
        """Run a specific processor."""
        if name in self.processors:
            self.processors[name].run(f"TML-{name}")
        else:
            raise ValueError(f"Processor {name} not found")

    def list_processors(self) -> List[str]:
        """List all available processors."""
        return list(self.processors.keys())


# Example usage and testing
def test_flink_processor():
    """Test the Flink processor locally."""
    processor = FlinkTransactionProcessor()

    try:
        processor.run("TML Test Job")
    except KeyboardInterrupt:
        logger.info("Flink job stopped by user")
    except Exception as e:
        logger.error(f"Flink job failed: {e}")


if __name__ == "__main__":
    test_flink_processor()
