"""
Apache Flink Integration for TML Platform - Production Ready
Stateful stream processing with spatial model inheritance
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from loguru import logger
from pyflink.common import Configuration, WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import KeyedProcessFunction, ProcessFunction
from pyflink.datastream.state import ListStateDescriptor, ValueStateDescriptor

from tml.core.config import config
from tml.core.inheritance import SpatialContext, SpatialInheritanceCoordinator
from tml.learning.online_learner import OnlineLearningEngine


@dataclass
class ModelStateData:
    """Enhanced model state for Flink processing"""

    model_id: str
    transaction_count: int = 0
    last_update: float = 0.0
    drift_score: float = 0.0
    accuracy: float = 0.0
    parent_model_id: Optional[str] = None
    spatial_context: Optional[Dict] = None
    feature_stats: Dict = None

    def __post_init__(self):
        if self.feature_stats is None:
            self.feature_stats = {}
        if self.last_update == 0:
            self.last_update = time.time()


class SpatialModelProcessor(KeyedProcessFunction):
    """
    Flink processor with spatial model inheritance for TML Platform.
    Maintains stateful per-model processing with inheritance.
    """

    def __init__(self):
        self.model_state = None
        self.feature_history = None
        self.learning_engine = None
        self.inheritance_coordinator = None

    def open(self, runtime_context):
        """Initialize state and TML components"""
        # Initialize state descriptors
        self.model_state = runtime_context.get_state(
            ValueStateDescriptor("model_state", Types.STRING())
        )

        self.feature_history = runtime_context.get_list_state(
            ListStateDescriptor("feature_history", Types.STRING())
        )

        # Initialize TML components
        self.learning_engine = OnlineLearningEngine()
        self.inheritance_coordinator = SpatialInheritanceCoordinator()

        logger.info("SpatialModelProcessor initialized with TML components")

    def process_element(self, transaction: str, ctx, out):
        """Process transaction with spatial inheritance"""
        try:
            # Parse transaction
            tx_data = json.loads(transaction)
            model_id = tx_data.get(
                "model_id", f"model_{tx_data.get('transaction_id', 'unknown')}"
            )

            # Get or create model state
            state_json = self.model_state.value()
            if state_json:
                state = ModelStateData(**json.loads(state_json))
            else:
                # Create new model with spatial inheritance
                state = self._create_model_with_inheritance(model_id, tx_data)

            # Process transaction through learning engine
            features = tx_data.get("features", {})
            target = tx_data.get("amount", 0) / 1000.0  # Normalize

            # Learn with spatial context
            learned = self.learning_engine.learn(model_id, features, target)

            # Update state
            state.transaction_count += 1
            state.last_update = time.time()

            # Calculate drift if parent exists
            if state.parent_model_id:
                state.drift_score = self._calculate_drift(state, features)

            # Save state
            self.model_state.update(json.dumps(asdict(state)))

            # Add to feature history for drift detection
            self.feature_history.add(json.dumps(features))

            # Output enriched result
            result = {
                "model_id": model_id,
                "transaction_id": tx_data.get("transaction_id"),
                "processed_at": time.time(),
                "transaction_count": state.transaction_count,
                "drift_score": state.drift_score,
                "parent_model": state.parent_model_id,
                "learned": learned,
                "spatial_inheritance": state.parent_model_id is not None,
            }

            out.collect(json.dumps(result))

            # Log progress
            if state.transaction_count % 100 == 0:
                logger.info(
                    f"Model {model_id}: Processed {state.transaction_count} transactions, "
                    f"Drift: {state.drift_score:.4f}"
                )

        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
            error_event = {
                "error": str(e),
                "transaction": transaction,
                "timestamp": time.time(),
            }
            out.collect(json.dumps(error_event))

    def _create_model_with_inheritance(
        self, model_id: str, tx_data: Dict
    ) -> ModelStateData:
        """Create model with spatial inheritance from similar models"""
        try:
            # Create spatial context
            context = SpatialContext(
                x_coord=tx_data.get("x_coord", hash(model_id) % 100),
                y_coord=tx_data.get("y_coord", hash(str(tx_data)) % 100),
                timestamp=time.time(),
                domain=tx_data.get("domain", "default"),
                features=tx_data.get("features", {}),
                metadata=tx_data,
            )

            # Find parent through inheritance coordinator
            inheritance_info = self.inheritance_coordinator.process_inheritance(
                model_id, context
            )

            parent_model_id = None
            if inheritance_info.get("parent_models"):
                parent_model_id = inheritance_info["parent_models"][0]
                logger.info(f"Model {model_id} inheriting from {parent_model_id}")

            return ModelStateData(
                model_id=model_id,
                parent_model_id=parent_model_id,
                spatial_context=asdict(context),
            )

        except Exception as e:
            logger.error(f"Error in spatial inheritance: {e}")
            return ModelStateData(model_id=model_id)

    def _calculate_drift(self, state: ModelStateData, features: Dict) -> float:
        """Calculate drift score from parent model"""
        try:
            # Simple drift calculation based on feature difference
            if not state.feature_stats:
                return 0.0

            drift_scores = []
            for key, value in features.items():
                if key in state.feature_stats:
                    expected = state.feature_stats[key]
                    if isinstance(value, (int, float)) and isinstance(
                        expected, (int, float)
                    ):
                        drift = abs(value - expected) / (abs(expected) + 1e-7)
                        drift_scores.append(min(drift, 1.0))

            return sum(drift_scores) / len(drift_scores) if drift_scores else 0.0

        except Exception as e:
            logger.error(f"Error calculating drift: {e}")
            return 0.0


class FlinkTMLPipeline:
    """
    Production-ready Flink pipeline for TML Platform
    """

    def __init__(self):
        # Configure Flink environment
        config = Configuration()
        config.set_string("state.backend", "rocksdb")
        config.set_string("state.checkpoints.dir", "file:///tmp/flink-checkpoints")
        config.set_integer("parallelism.default", 4)

        self.env = StreamExecutionEnvironment.get_execution_environment(config)
        self.env.set_parallelism(4)

        # Enable checkpointing for fault tolerance
        self.env.enable_checkpointing(30000)  # 30 seconds

        logger.info("Flink TML Pipeline initialized")

    def build_pipeline(self):
        """Build the complete Flink processing pipeline"""

        # Kafka source configuration
        kafka_source = (
            KafkaSource.builder()
            .set_bootstrap_servers("localhost:29092")
            .set_topics("transactions")
            .set_group_id("flink-tml-processor")
            .set_starting_offsets(KafkaOffsetsInitializer.latest())
            .set_value_only_deserializer(SimpleStringSchema())
            .build()
        )

        # Create source stream
        transaction_stream = self.env.from_source(
            kafka_source,
            WatermarkStrategy.for_monotonous_timestamps(),
            "Kafka Transaction Source",
        )

        # Key by model_id for stateful processing
        keyed_stream = transaction_stream.key_by(lambda tx: self._extract_model_id(tx))

        # Process with spatial model inheritance
        processed_stream = keyed_stream.process(SpatialModelProcessor()).name(
            "Spatial Model Processing"
        )

        # Kafka sink for processed results
        kafka_sink = (
            KafkaSink.builder()
            .set_bootstrap_servers("localhost:29092")
            .set_record_serializer(
                KafkaRecordSerializationSchema.builder()
                .set_topic("model-updates")
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
            )
            .build()
        )

        # Write results to Kafka
        processed_stream.sink_to(kafka_sink).name("Model Updates Sink")

        # Also print to console for monitoring
        processed_stream.print().set_parallelism(1)

        logger.info("Flink pipeline built successfully")

        return self.env

    def _extract_model_id(self, transaction: str) -> str:
        """Extract model_id from transaction for keying"""
        try:
            tx_data = json.loads(transaction)
            return tx_data.get(
                "model_id", f"model_{tx_data.get('transaction_id', 'unknown')}"
            )
        except:
            return "model_unknown"

    def start(self):
        """Start the Flink pipeline"""
        try:
            logger.info("Starting Flink TML Pipeline...")
            env = self.build_pipeline()

            # Execute the pipeline
            env.execute("TML Flink Spatial Processing Pipeline")

        except Exception as e:
            logger.error(f"Failed to start Flink pipeline: {e}")
            raise


def main():
    """Main entry point for Flink integration"""
    pipeline = FlinkTMLPipeline()
    pipeline.start()


if __name__ == "__main__":
    main()
