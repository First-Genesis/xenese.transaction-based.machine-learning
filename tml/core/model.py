"""Core transaction model implementation with incremental learning."""

import uuid
import time
import pickle
import hashlib
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import numpy as np
from river import base, compose, preprocessing, linear_model, metrics
from loguru import logger


@dataclass
class TransactionContext:
    """Context information for a transaction."""
    transaction_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class ModelMetrics:
    """Metrics tracking for a transaction model."""
    total_predictions: int = 0
    total_updates: int = 0
    accuracy: float = 0.0
    loss: float = 0.0
    drift_score: float = 0.0
    last_updated: float = field(default_factory=time.time)
    creation_time: float = field(default_factory=time.time)
    
    def update_accuracy(self, y_true: Any, y_pred: Any):
        """Update accuracy metric."""
        self.total_predictions += 1
        # Simple accuracy calculation - can be enhanced based on problem type
        if y_true == y_pred:
            self.accuracy = (self.accuracy * (self.total_predictions - 1) + 1.0) / self.total_predictions
        else:
            self.accuracy = (self.accuracy * (self.total_predictions - 1)) / self.total_predictions


class BaseTransactionModel(ABC):
    """Abstract base class for transaction models."""
    
    def __init__(self, model_id: str, parent_model_id: Optional[str] = None):
        self.model_id = model_id
        self.parent_model_id = parent_model_id
        self.metrics = ModelMetrics()
        self.context: Optional[TransactionContext] = None
        
    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction."""
        pass
    
    @abstractmethod
    def update(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new data."""
        pass
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get model state for serialization."""
        pass
    
    @abstractmethod
    def set_state(self, state: Dict[str, Any]) -> None:
        """Set model state from serialized data."""
        pass
    
    def calculate_drift_score(self, recent_features: List[Dict[str, Any]]) -> float:
        """Calculate concept drift score."""
        # Simplified drift detection - can be enhanced with more sophisticated methods
        if len(recent_features) < 10:
            return 0.0
        
        # Calculate feature distribution changes
        # This is a placeholder - implement proper drift detection
        return np.random.random() * 0.1  # Placeholder


class RiverTransactionModel(BaseTransactionModel):
    """River-based incremental learning model."""
    
    def __init__(self, model_id: str, parent_model_id: Optional[str] = None, 
                 model_type: str = "logistic_regression"):
        super().__init__(model_id, parent_model_id)
        
        # Create River pipeline
        if model_type == "logistic_regression":
            self.model = compose.Pipeline(
                preprocessing.StandardScaler(),
                linear_model.LogisticRegression()
            )
        elif model_type == "regression":
            self.model = compose.Pipeline(
                preprocessing.StandardScaler(),
                linear_model.LinearRegression()
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
        
        self.model_type = model_type
        self._feature_names: Optional[List[str]] = None
        
    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction using the River model."""
        try:
            # Convert features to numeric format for River
            numeric_features = self._convert_features_to_numeric(features)
            prediction = self.model.predict_one(numeric_features)
            self.metrics.total_predictions += 1
            return prediction
        except Exception as e:
            logger.error(f"Prediction error for model {self.model_id}: {e}")
            return None
    
    def predict_proba(self, features: Dict[str, Any]) -> Dict[Any, float]:
        """Get prediction probabilities (for classification models)."""
        if hasattr(self.model, 'predict_proba_one'):
            return self.model.predict_proba_one(features)
        else:
            raise NotImplementedError("Model does not support probability predictions")
    
    def update(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new training data."""
        try:
            # Store feature names for consistency
            if self._feature_names is None:
                self._feature_names = sorted(features.keys())
            
            # Convert features to numeric format for River
            numeric_features = self._convert_features_to_numeric(features)
            
            # Make prediction before update for metrics
            prediction = self.model.predict_one(numeric_features)
            
            # Update the model
            self.model.learn_one(numeric_features, target)
            self.metrics.total_updates += 1
            self.metrics.last_updated = time.time()
            
            # Update accuracy metrics
            if prediction is not None:
                self.metrics.update_accuracy(target, prediction)
                
        except Exception as e:
            logger.error(f"Update error for model {self.model_id}: {e}")
    
    def _convert_features_to_numeric(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Convert features to numeric format for River compatibility."""
        numeric_features = {}
        
        for key, value in features.items():
            if isinstance(value, (int, float)):
                numeric_features[key] = float(value)
            elif isinstance(value, bool):
                numeric_features[key] = float(value)
            elif isinstance(value, str):
                # Hash string values to numeric (simple approach)
                numeric_features[key] = float(hash(value) % 1000) / 1000.0
            elif value is None:
                numeric_features[key] = 0.0
            else:
                # Convert other types to string then hash
                numeric_features[key] = float(hash(str(value)) % 1000) / 1000.0
        
        return numeric_features
    
    def get_state(self) -> Dict[str, Any]:
        """Serialize model state."""
        try:
            # River models can be pickled
            model_bytes = pickle.dumps(self.model)
            
            return {
                "model_id": self.model_id,
                "parent_model_id": self.parent_model_id,
                "model_type": self.model_type,
                "model_bytes": model_bytes,
                "feature_names": self._feature_names,
                "metrics": {
                    "total_predictions": self.metrics.total_predictions,
                    "total_updates": self.metrics.total_updates,
                    "accuracy": self.metrics.accuracy,
                    "loss": self.metrics.loss,
                    "drift_score": self.metrics.drift_score,
                    "last_updated": self.metrics.last_updated,
                    "creation_time": self.metrics.creation_time,
                },
                "context": self.context.to_dict() if self.context else None
            }
        except Exception as e:
            logger.error(f"State serialization error for model {self.model_id}: {e}")
            return {}
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """Deserialize model state."""
        try:
            self.model_id = state["model_id"]
            self.parent_model_id = state.get("parent_model_id")
            self.model_type = state["model_type"]
            self._feature_names = state.get("feature_names")
            
            # Restore model
            if "model_bytes" in state:
                self.model = pickle.loads(state["model_bytes"])
            
            # Restore metrics
            if "metrics" in state:
                metrics_data = state["metrics"]
                self.metrics.total_predictions = metrics_data.get("total_predictions", 0)
                self.metrics.total_updates = metrics_data.get("total_updates", 0)
                self.metrics.accuracy = metrics_data.get("accuracy", 0.0)
                self.metrics.loss = metrics_data.get("loss", 0.0)
                self.metrics.drift_score = metrics_data.get("drift_score", 0.0)
                self.metrics.last_updated = metrics_data.get("last_updated", time.time())
                self.metrics.creation_time = metrics_data.get("creation_time", time.time())
            
            # Restore context
            if state.get("context"):
                context_data = state["context"]
                self.context = TransactionContext(**context_data)
                
        except Exception as e:
            logger.error(f"State deserialization error for model {self.model_id}: {e}")


class TransactionModel:
    """Main transaction model class that handles model lifecycle."""
    
    def __init__(self, transaction_context: TransactionContext, 
                 parent_model: Optional['TransactionModel'] = None,
                 model_type: str = "logistic_regression"):
        
        self.context = transaction_context
        self.model_id = self._generate_model_id(transaction_context)
        self.parent_model_id = parent_model.model_id if parent_model else None
        
        # Create the underlying model
        self.model = RiverTransactionModel(
            model_id=self.model_id,
            parent_model_id=self.parent_model_id,
            model_type=model_type
        )
        self.model.context = transaction_context
        
        # Initialize from parent if available
        if parent_model:
            self._inherit_from_parent(parent_model)
    
    def _generate_model_id(self, context: TransactionContext) -> str:
        """Generate unique model ID based on transaction context."""
        # Create deterministic ID based on transaction context
        context_str = f"{context.transaction_id}_{context.timestamp}"
        hash_obj = hashlib.md5(context_str.encode())
        return f"model_{hash_obj.hexdigest()[:12]}"
    
    def _inherit_from_parent(self, parent_model: 'TransactionModel') -> None:
        """Inherit knowledge from parent model using transfer learning."""
        try:
            # Get parent model state
            parent_state = parent_model.model.get_state()
            
            # Initialize with parent's model parameters
            # For River models, we can copy the learned parameters
            if hasattr(parent_model.model.model, '_weights'):
                # Copy weights for linear models
                if hasattr(self.model.model, '_weights'):
                    self.model.model._weights = parent_model.model.model._weights.copy()
            
            logger.info(f"Model {self.model_id} inherited from parent {self.parent_model_id}")
            
        except Exception as e:
            logger.warning(f"Failed to inherit from parent model: {e}")
    
    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction."""
        return self.model.predict(features)
    
    def predict_proba(self, features: Dict[str, Any]) -> Dict[Any, float]:
        """Get prediction probabilities."""
        return self.model.predict_proba(features)
    
    def update(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new data."""
        self.model.update(features, target)
    
    def get_metrics(self) -> ModelMetrics:
        """Get model performance metrics."""
        return self.model.metrics
    
    def should_retrain(self, drift_threshold: float = 0.1) -> bool:
        """Check if model should be retrained due to concept drift."""
        return self.model.metrics.drift_score > drift_threshold
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete model state for persistence."""
        return self.model.get_state()
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore model from persisted state."""
        self.model.set_state(state)
        self.model_id = state["model_id"]
        self.parent_model_id = state.get("parent_model_id")
        
        if state.get("context"):
            self.context = TransactionContext(**state["context"])


class ModelFactory:
    """Factory for creating transaction models."""
    
    @staticmethod
    def create_model(transaction_context: TransactionContext,
                    parent_model: Optional[TransactionModel] = None,
                    model_type: str = "logistic_regression") -> TransactionModel:
        """Create a new transaction model."""
        return TransactionModel(
            transaction_context=transaction_context,
            parent_model=parent_model,
            model_type=model_type
        )
    
    @staticmethod
    def create_base_model(model_type: str = "logistic_regression") -> TransactionModel:
        """Create a base model for cold start scenarios."""
        base_context = TransactionContext(
            transaction_id="base_model",
            timestamp=time.time(),
            metadata={"type": "base_model"}
        )
        return TransactionModel(
            transaction_context=base_context,
            model_type=model_type
        )
