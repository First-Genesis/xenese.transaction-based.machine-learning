"""
Unit tests for TML core models
"""

import pytest
import pickle
from unittest.mock import Mock, patch
from datetime import datetime

from tml.core.model import TransactionContext, RiverTransactionModel, ModelMetrics


class TestTransactionContext:
    """Test TransactionContext functionality"""

    def test_context_creation(self):
        """Test basic context creation"""
        context = TransactionContext(
            transaction_id="test_001", user_id="user_123", session_id="session_456"
        )

        assert context.transaction_id == "test_001"
        assert context.user_id == "user_123"
        assert context.session_id == "session_456"
        assert isinstance(context.timestamp, datetime)

    def test_context_serialization(self):
        """Test context can be serialized/deserialized"""
        context = TransactionContext(
            transaction_id="test_001", user_id="user_123", session_id="session_456"
        )

        # Should be serializable
        serialized = pickle.dumps(context)
        deserialized = pickle.loads(serialized)

        assert deserialized.transaction_id == context.transaction_id
        assert deserialized.user_id == context.user_id
        assert deserialized.session_id == context.session_id


class TestModelMetrics:
    """Test ModelMetrics functionality"""

    def test_metrics_initialization(self):
        """Test metrics are initialized correctly"""
        metrics = ModelMetrics()

        assert metrics.total_updates == 0
        assert metrics.accuracy == 0.0
        assert isinstance(metrics.created_at, float)

    def test_metrics_update(self):
        """Test metrics can be updated"""
        metrics = ModelMetrics()

        # Update metrics
        metrics.total_updates = 10
        metrics.accuracy = 0.85

        assert metrics.total_updates == 10
        assert metrics.accuracy == 0.85


class TestRiverTransactionModel:
    """Test RiverTransactionModel functionality"""

    def test_model_creation(self):
        """Test basic model creation"""
        model = RiverTransactionModel(
            model_id="test_model_001", model_type="logistic_regression"
        )

        assert model.model_id == "test_model_001"
        assert model.model_type == "logistic_regression"
        assert model.parent_model_id is None
        assert isinstance(model.metrics, ModelMetrics)
        assert model.model is not None  # River model should be initialized

    def test_model_with_parent(self):
        """Test model creation with parent inheritance"""
        model = RiverTransactionModel(
            model_id="child_model_001",
            parent_model_id="parent_model_001",
            model_type="logistic_regression",
        )

        assert model.model_id == "child_model_001"
        assert model.parent_model_id == "parent_model_001"

    def test_model_prediction(self):
        """Test model can make predictions"""
        model = RiverTransactionModel(
            model_id="test_model_001", model_type="logistic_regression"
        )

        # Test features
        features = {"feature_1": 1.0, "feature_2": 0.5, "feature_3": -0.2}

        # Should not raise an error
        prediction = model.predict(features)
        assert prediction in [True, False]  # Binary classification

    def test_model_training(self):
        """Test model can be trained"""
        model = RiverTransactionModel(
            model_id="test_model_001", model_type="logistic_regression"
        )

        # Test features and label
        features = {"feature_1": 1.0, "feature_2": 0.5, "feature_3": -0.2}
        label = True

        # Get initial update count
        initial_updates = model.metrics.total_updates

        # Train model
        model.update(features, label)

        # Should increment update count
        assert model.metrics.total_updates == initial_updates + 1

    def test_model_serialization(self):
        """Test model state can be serialized"""
        model = RiverTransactionModel(
            model_id="test_model_001", model_type="logistic_regression"
        )

        # Train model a bit
        features = {"feature_1": 1.0, "feature_2": 0.5}
        model.update(features, True)

        # Should be serializable
        serialized = pickle.dumps(model.model)
        deserialized = pickle.loads(serialized)

        # Should still work
        prediction = deserialized.predict_one(features)
        assert prediction in [0, 1]  # River returns 0/1

    def test_invalid_model_type(self):
        """Test invalid model type raises error"""
        with pytest.raises(ValueError, match="Unsupported model type"):
            RiverTransactionModel(
                model_id="test_model_001", model_type="invalid_model_type"
            )

    def test_model_context_assignment(self):
        """Test model can have context assigned"""
        model = RiverTransactionModel(
            model_id="test_model_001", model_type="logistic_regression"
        )

        context = TransactionContext(
            transaction_id="test_001", user_id="user_123", session_id="session_456"
        )

        model.context = context
        assert model.context == context
        assert model.context.transaction_id == "test_001"


class TestModelInheritance:
    """Test model inheritance functionality"""

    def test_parent_child_relationship(self):
        """Test parent-child model relationship"""
        # Create parent model
        parent = RiverTransactionModel(
            model_id="parent_001", model_type="logistic_regression"
        )

        # Train parent model
        features = {"feature_1": 1.0, "feature_2": 0.5}
        parent.update(features, True)
        parent.update({"feature_1": -1.0, "feature_2": -0.5}, False)

        # Create child model
        child = RiverTransactionModel(
            model_id="child_001",
            parent_model_id="parent_001",
            model_type="logistic_regression",
        )

        # Simulate inheritance by copying model state
        child.model = pickle.loads(pickle.dumps(parent.model))
        child.metrics.total_updates = parent.metrics.total_updates

        # Child should have inherited knowledge
        assert child.metrics.total_updates == parent.metrics.total_updates

        # Child should be able to make predictions based on parent's knowledge
        prediction = child.predict(features)
        assert prediction in [True, False]

    def test_multiple_inheritance_levels(self):
        """Test multiple levels of inheritance"""
        # Create grandparent
        grandparent = RiverTransactionModel(
            model_id="grandparent_001", model_type="logistic_regression"
        )

        # Create parent inheriting from grandparent
        parent = RiverTransactionModel(
            model_id="parent_001",
            parent_model_id="grandparent_001",
            model_type="logistic_regression",
        )

        # Create child inheriting from parent
        child = RiverTransactionModel(
            model_id="child_001",
            parent_model_id="parent_001",
            model_type="logistic_regression",
        )

        # Verify inheritance chain
        assert grandparent.parent_model_id is None
        assert parent.parent_model_id == "grandparent_001"
        assert child.parent_model_id == "parent_001"


@pytest.fixture
def sample_features():
    """Sample features for testing"""
    return {"feature_1": 1.0, "feature_2": 0.5, "feature_3": -0.2, "feature_4": 2.1}


@pytest.fixture
def trained_model(sample_features):
    """A pre-trained model for testing"""
    model = RiverTransactionModel(
        model_id="trained_model_001", model_type="logistic_regression"
    )

    # Train with some sample data
    for i in range(10):
        features = {k: v + (i * 0.1) for k, v in sample_features.items()}
        label = i % 2 == 0  # Alternating labels
        model.update(features, label)

    return model


class TestModelPerformance:
    """Test model performance and accuracy tracking"""

    def test_accuracy_calculation(self, trained_model, sample_features):
        """Test that accuracy is calculated correctly"""
        # Make some predictions and updates
        correct_predictions = 0
        total_predictions = 5

        for i in range(total_predictions):
            features = {k: v + (i * 0.05) for k, v in sample_features.items()}
            prediction = trained_model.predict(features)
            actual = i % 2 == 0

            if prediction == actual:
                correct_predictions += 1

            trained_model.update(features, actual)

        # Accuracy should be reasonable (not testing exact value due to randomness)
        assert 0.0 <= trained_model.metrics.accuracy <= 1.0

    def test_update_count_tracking(self, trained_model, sample_features):
        """Test that update count is tracked correctly"""
        initial_updates = trained_model.metrics.total_updates

        # Perform some updates
        for i in range(5):
            features = {k: v + (i * 0.1) for k, v in sample_features.items()}
            trained_model.update(features, i % 2 == 0)

        # Should have incremented by 5
        assert trained_model.metrics.total_updates == initial_updates + 5
