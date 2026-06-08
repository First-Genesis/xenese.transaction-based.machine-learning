"""Tests for core TML components."""

import pytest
import time
from unittest.mock import Mock, patch

from tml.core.model import TransactionContext, TransactionModel, ModelFactory
from tml.core.config import Config
from tml.learning.online_learner import RiverLearner, OnlineLearningEngine
from tml.ingestion.kafka_producer import TransactionEvent, TransactionEventGenerator


class TestTransactionContext:
    """Test TransactionContext class."""

    def test_create_context(self):
        """Test creating a transaction context."""
        context = TransactionContext(
            transaction_id="test_001", user_id="user_123", session_id="session_456"
        )

        assert context.transaction_id == "test_001"
        assert context.user_id == "user_123"
        assert context.session_id == "session_456"
        assert isinstance(context.timestamp, float)
        assert context.metadata == {}

    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        context = TransactionContext(transaction_id="test_001", user_id="user_123")

        context_dict = context.to_dict()

        assert context_dict["transaction_id"] == "test_001"
        assert context_dict["user_id"] == "user_123"
        assert "timestamp" in context_dict


class TestTransactionModel:
    """Test TransactionModel class."""

    def test_create_model(self):
        """Test creating a transaction model."""
        context = TransactionContext(transaction_id="test_001", user_id="user_123")

        model = TransactionModel(context)

        assert model.context == context
        assert model.model_id is not None
        assert model.parent_model_id is None

    def test_model_prediction(self):
        """Test model prediction."""
        context = TransactionContext(transaction_id="test_001", user_id="user_123")

        model = TransactionModel(context)

        features = {"amount": 100.0, "category": "electronics", "hour_of_day": 14}

        prediction = model.predict(features)
        assert prediction is not None

    def test_model_update(self):
        """Test model learning update."""
        context = TransactionContext(transaction_id="test_001", user_id="user_123")

        model = TransactionModel(context)

        features = {"amount": 100.0, "category": "electronics"}
        target = True

        # Should not raise an exception
        model.update(features, target)

        # Check that metrics were updated
        metrics = model.get_metrics()
        assert metrics.total_updates >= 1

    def test_model_inheritance(self):
        """Test model inheritance from parent."""
        parent_context = TransactionContext(
            transaction_id="parent_001", user_id="user_123"
        )
        parent_model = TransactionModel(parent_context)

        # Train parent model
        parent_model.update({"amount": 100}, True)

        child_context = TransactionContext(
            transaction_id="child_001", user_id="user_123"
        )
        child_model = TransactionModel(child_context, parent_model=parent_model)

        assert child_model.parent_model_id == parent_model.model_id


class TestModelFactory:
    """Test ModelFactory class."""

    def test_create_model(self):
        """Test factory model creation."""
        context = TransactionContext(transaction_id="factory_001", user_id="user_123")

        model = ModelFactory.create_model(context)

        assert isinstance(model, TransactionModel)
        assert model.context == context

    def test_create_base_model(self):
        """Test creating base model."""
        model = ModelFactory.create_base_model()

        assert isinstance(model, TransactionModel)
        assert model.context.transaction_id == "base_model"


class TestRiverLearner:
    """Test RiverLearner class."""

    def test_create_learner(self):
        """Test creating a River learner."""
        learner = RiverLearner(model_type="logistic_regression")

        assert learner.model_type == "logistic_regression"
        assert learner.model is not None

    def test_prediction(self):
        """Test making predictions."""
        learner = RiverLearner(model_type="logistic_regression")

        features = {"feature1": 1.0, "feature2": 2.0}
        prediction = learner.predict(features)

        # Should return some prediction (even if random initially)
        assert prediction is not None

    def test_learning(self):
        """Test learning from data."""
        learner = RiverLearner(model_type="logistic_regression")

        features = {"feature1": 1.0, "feature2": 2.0}
        target = True

        # Should not raise an exception
        learner.learn(features, target)

        metrics = learner.get_metrics()
        assert "accuracy" in metrics or "mae" in metrics

    def test_get_metrics(self):
        """Test getting learner metrics."""
        learner = RiverLearner(model_type="logistic_regression")

        metrics = learner.get_metrics()

        assert isinstance(metrics, dict)
        assert len(metrics) > 0


class TestOnlineLearningEngine:
    """Test OnlineLearningEngine class."""

    def test_create_engine(self):
        """Test creating learning engine."""
        engine = OnlineLearningEngine()

        assert engine.default_algorithm == "river"
        assert len(engine.learners) == 0

    def test_create_learner(self):
        """Test creating learner through engine."""
        engine = OnlineLearningEngine()

        learner = engine.create_learner("test_model", algorithm="river")

        assert "test_model" in engine.learners
        assert isinstance(learner, RiverLearner)

    def test_prediction_through_engine(self):
        """Test making predictions through engine."""
        engine = OnlineLearningEngine()

        # Create learner
        engine.create_learner("test_model")

        features = {"feature1": 1.0, "feature2": 2.0}
        prediction = engine.predict("test_model", features)

        assert prediction is not None

    def test_learning_through_engine(self):
        """Test learning through engine."""
        engine = OnlineLearningEngine()

        # Create learner
        engine.create_learner("test_model")

        features = {"feature1": 1.0, "feature2": 2.0}
        target = True

        success = engine.learn("test_model", features, target)

        assert success is True

    @pytest.mark.asyncio
    async def test_process_transaction(self):
        """Test processing transaction event."""
        engine = OnlineLearningEngine()

        event = TransactionEvent(
            transaction_id="test_001",
            user_id="user_123",
            timestamp=time.time(),
            event_type="purchase",
            features={"amount": 100.0, "category": "electronics"},
            target=True,
        )

        result = await engine.process_transaction(event)

        assert result.model_id is not None
        assert result.prediction is not None
        assert result.update_applied is True
        assert isinstance(result.processing_time_ms, float)


class TestTransactionEvent:
    """Test TransactionEvent class."""

    def test_create_event(self):
        """Test creating transaction event."""
        event = TransactionEvent(
            transaction_id="test_001",
            user_id="user_123",
            timestamp=time.time(),
            event_type="purchase",
            features={"amount": 100.0},
        )

        assert event.transaction_id == "test_001"
        assert event.user_id == "user_123"
        assert event.event_type == "purchase"
        assert event.features == {"amount": 100.0}

    def test_event_serialization(self):
        """Test event serialization."""
        event = TransactionEvent(
            transaction_id="test_001",
            user_id="user_123",
            timestamp=time.time(),
            event_type="purchase",
            features={"amount": 100.0},
        )

        # Test to_dict
        event_dict = event.to_dict()
        assert isinstance(event_dict, dict)
        assert event_dict["transaction_id"] == "test_001"

        # Test to_json
        event_json = event.to_json()
        assert isinstance(event_json, str)

        # Test from_json
        restored_event = TransactionEvent.from_json(event_json)
        assert restored_event.transaction_id == event.transaction_id


class TestTransactionEventGenerator:
    """Test TransactionEventGenerator class."""

    def test_generate_event(self):
        """Test generating single event."""
        generator = TransactionEventGenerator()

        event = generator.generate_event()

        assert isinstance(event, TransactionEvent)
        assert event.transaction_id is not None
        assert event.event_type in generator.event_types
        assert isinstance(event.features, dict)
        assert len(event.features) > 0

    def test_generate_batch(self):
        """Test generating batch of events."""
        generator = TransactionEventGenerator()

        events = generator.generate_batch(5)

        assert len(events) == 5
        assert all(isinstance(event, TransactionEvent) for event in events)

        # Check that events have different transaction IDs
        transaction_ids = [event.transaction_id for event in events]
        assert len(set(transaction_ids)) == 5  # All unique


class TestConfig:
    """Test configuration management."""

    def test_config_creation(self):
        """Test creating configuration."""
        config = Config()

        assert config.environment is not None
        assert config.redis is not None
        assert config.kafka is not None
        assert config.model is not None

    def test_config_values(self):
        """Test configuration values."""
        config = Config()

        # Test default values
        assert config.redis.host == "localhost"
        assert config.redis.port == 6379
        assert config.kafka.bootstrap_servers == "localhost:9092"
        assert config.model.base_model_type == "river"


if __name__ == "__main__":
    pytest.main([__file__])
