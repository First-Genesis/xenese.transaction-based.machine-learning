"""Online learning engine with multiple algorithm support."""

import asyncio
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
from loguru import logger

# River imports
from river import base, compose, ensemble, linear_model, metrics, preprocessing, tree
from river.drift import ADWIN, PageHinkley

# Vowpal Wabbit import (optional)
try:
    import vowpalwabbit as vw

    VW_AVAILABLE = True
except ImportError:
    VW_AVAILABLE = False
    logger.warning(
        "Vowpal Wabbit not available. Install with: pip install vowpalwabbit"
    )

from tml.core.config import config
from tml.core.inheritance import SpatialInheritanceCoordinator, SpatialContext
from tml.core.model import TransactionContext, TransactionModel
from tml.ingestion.kafka_producer import TransactionEvent


@dataclass
class LearningResult:
    """Result of a learning operation."""

    model_id: str
    prediction: Any
    confidence: Optional[float]
    update_applied: bool
    drift_detected: bool
    processing_time_ms: float
    metadata: Dict[str, Any]


class OnlineLearner(ABC):
    """Abstract base class for online learning algorithms."""

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction."""
        pass

    @abstractmethod
    def predict_proba(self, features: Dict[str, Any]) -> Dict[Any, float]:
        """Get prediction probabilities (if supported)."""
        pass

    @abstractmethod
    def learn(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new data."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, float]:
        """Get current model metrics."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the model to initial state."""
        pass


class RiverLearner(OnlineLearner):
    """River-based online learner."""

    def __init__(self, model_type: str = "logistic_regression", **kwargs):
        self.model_type = model_type
        self.model = self._create_model(model_type, **kwargs)
        self.metrics_tracker = self._create_metrics_tracker(model_type)
        self.drift_detector = ADWIN(delta=0.002)
        self.feature_names: Optional[List[str]] = None

    def _create_model(self, model_type: str, **kwargs):
        """Create River model based on type."""
        if model_type == "logistic_regression":
            return compose.Pipeline(
                preprocessing.StandardScaler(),
                linear_model.LogisticRegression(**kwargs),
            )
        elif model_type == "linear_regression":
            return compose.Pipeline(
                preprocessing.StandardScaler(), linear_model.LinearRegression(**kwargs)
            )
        elif model_type == "hoeffding_tree":
            return tree.HoeffdingTreeClassifier(**kwargs)
        elif model_type == "adaptive_random_forest":
            # AdaptiveRandomForestClassifier may not be available in all river versions
            if hasattr(ensemble, "AdaptiveRandomForestClassifier"):
                return ensemble.AdaptiveRandomForestClassifier(**kwargs)
            else:
                # Fallback to another ensemble method
                return tree.HoeffdingTreeClassifier(**kwargs)
        elif model_type == "sgd_regressor":
            # SGDRegressor may not be available, use PARegressor as fallback
            if hasattr(linear_model, "SGDRegressor"):
                return compose.Pipeline(
                    preprocessing.StandardScaler(), linear_model.SGDRegressor(**kwargs)
                )
            else:
                return compose.Pipeline(
                    preprocessing.StandardScaler(), linear_model.PARegressor(**kwargs)
                )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _create_metrics_tracker(self, model_type: str):
        """Create appropriate metrics tracker."""
        if "classifier" in model_type.lower() or "logistic" in model_type.lower():
            return metrics.Accuracy()
        else:
            return metrics.MAE()  # Mean Absolute Error for regression

    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction."""
        try:
            return self.model.predict_one(features)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None

    def predict_proba(self, features: Dict[str, Any]) -> Dict[Any, float]:
        """Get prediction probabilities."""
        try:
            if hasattr(self.model, "predict_proba_one"):
                return self.model.predict_proba_one(features)
            else:
                # For regression models, return confidence interval
                pred = self.predict(features)
                return {pred: 1.0} if pred is not None else {}
        except Exception as e:
            logger.error(f"Probability prediction error: {e}")
            return {}

    def learn(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new data."""
        try:
            # Store feature names for consistency
            if self.feature_names is None:
                self.feature_names = sorted(features.keys())

            # Make prediction before learning for metrics
            prediction = self.predict(features)

            # Update model
            self.model.learn_one(features, target)

            # Update metrics
            if prediction is not None:
                self.metrics_tracker.update(target, prediction)

            # Check for drift
            if prediction is not None:
                error = (
                    abs(target - prediction)
                    if isinstance(target, (int, float))
                    else (target != prediction)
                )
                self.drift_detector.update(error)

        except Exception as e:
            logger.error(f"Learning error: {e}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current model metrics."""
        return {
            (
                "accuracy" if hasattr(self.metrics_tracker, "get") else "mae"
            ): self.metrics_tracker.get(),
            "drift_detected": float(self.drift_detector.drift_detected),
            "n_detections": float(getattr(self.drift_detector, "n_detections", 0)),
        }

    def reset(self) -> None:
        """Reset the model to initial state."""
        self.model = self._create_model(self.model_type)
        self.metrics_tracker = self._create_metrics_tracker(self.model_type)
        self.drift_detector = ADWIN(delta=0.002)


class VowpalWabbitLearner(OnlineLearner):
    """Vowpal Wabbit-based online learner."""

    def __init__(self, **kwargs):
        if not VW_AVAILABLE:
            raise ImportError("Vowpal Wabbit not available")

        # Default VW arguments
        vw_args = {
            "learning_rate": 0.1,
            "loss_function": "logistic",
            "l2": 0.001,
        }
        vw_args.update(kwargs)

        # Create VW model
        args_str = " ".join([f"--{k} {v}" for k, v in vw_args.items()])
        self.model = vw.Workspace(args_str)

        self.prediction_count = 0
        self.update_count = 0
        self.total_loss = 0.0

    def _format_features(self, features: Dict[str, Any]) -> str:
        """Format features for VW."""
        # Convert features to VW format: |namespace feature:value
        feature_str = "|features "
        for key, value in features.items():
            if isinstance(value, (int, float)):
                feature_str += f"{key}:{value} "
            else:
                # For categorical features, use feature name as indicator
                feature_str += f"{key}_{value}:1 "
        return feature_str.strip()

    def predict(self, features: Dict[str, Any]) -> Any:
        """Make a prediction."""
        try:
            feature_str = self._format_features(features)
            prediction = self.model.predict(feature_str)
            self.prediction_count += 1
            return prediction
        except Exception as e:
            logger.error(f"VW prediction error: {e}")
            return None

    def predict_proba(self, features: Dict[str, Any]) -> Dict[Any, float]:
        """Get prediction probabilities."""
        # VW doesn't directly provide probabilities, use sigmoid transformation
        try:
            raw_pred = self.predict(features)
            if raw_pred is not None:
                prob = 1 / (1 + np.exp(-raw_pred))  # Sigmoid
                return {1: prob, 0: 1 - prob}
            return {}
        except Exception as e:
            logger.error(f"VW probability error: {e}")
            return {}

    def learn(self, features: Dict[str, Any], target: Any) -> None:
        """Update the model with new data."""
        try:
            # Format for VW: label |features feature:value
            feature_str = self._format_features(features)
            vw_example = f"{target} {feature_str}"

            # Learn from example
            loss = self.model.learn(vw_example)
            self.update_count += 1
            self.total_loss += loss

        except Exception as e:
            logger.error(f"VW learning error: {e}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current model metrics."""
        avg_loss = self.total_loss / max(1, self.update_count)
        return {
            "average_loss": avg_loss,
            "prediction_count": float(self.prediction_count),
            "update_count": float(self.update_count),
        }

    def reset(self) -> None:
        """Reset the model to initial state."""
        # VW doesn't have a direct reset, need to recreate
        self.model.finish()
        self.__init__()


class OnlineLearningEngine:
    """Main engine for managing online learning across multiple models."""

    def __init__(self, default_algorithm: str = "river"):
        self.default_algorithm = default_algorithm
        self.learners: Dict[str, OnlineLearner] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)

        # Performance tracking
        self.total_predictions = 0
        self.total_updates = 0
        self.start_time = time.time()

        # Initialize spatial inheritance coordinator for River ML
        self.inheritance_coordinator = SpatialInheritanceCoordinator(
            {"max_parents": 3, "similarity_threshold": 0.4, "inheritance_decay": 0.85}
        )

        logger.info("✅ Spatial Inheritance Coordinator initialized for River ML models")

    def create_learner(
        self,
        model_id: str,
        algorithm: Optional[str] = None,
        model_type: str = "logistic_regression",
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> OnlineLearner:
        """Create a new online learner with spatial inheritance."""
        algorithm = algorithm or self.default_algorithm

        try:
            # Create spatial context for inheritance
            spatial_context = None
            if context:
                spatial_context = SpatialContext(
                    x_coord=context.get("x_coord", 0.0),
                    y_coord=context.get("y_coord", 0.0),
                    timestamp=context.get("timestamp", time.time()),
                    domain=context.get("domain", "default"),
                    features=context.get("features", {}),
                    metadata=context.get("metadata", {}),
                )

            # Check for spatial inheritance opportunities
            parent_models = []
            if spatial_context and len(self.learners) > 0:
                inheritance_info = self.inheritance_coordinator.process_inheritance(
                    model_id, spatial_context
                )
                parent_models = inheritance_info.get("parent_models", [])

                if parent_models:
                    logger.info(
                        f"🧬 Spatial inheritance: Model {model_id} will inherit from {len(parent_models)} parent models"
                    )

            # Create the base learner
            learner: OnlineLearner
            if algorithm == "river":
                learner = RiverLearner(model_type=model_type, **kwargs)

                # Apply spatial inheritance for River models
                if parent_models and hasattr(learner, "model"):
                    self._apply_river_inheritance(learner, parent_models, model_id)

            elif algorithm == "vowpal_wabbit":
                learner = VowpalWabbitLearner(**kwargs)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            self.learners[model_id] = learner

            if parent_models:
                logger.info(
                    f"✅ Created {algorithm} learner for {model_id} with spatial inheritance from {parent_models}"
                )
            else:
                logger.info(
                    f"✅ Created {algorithm} learner for {model_id} (no inheritance - first model)"
                )

            return learner

        except Exception as e:
            logger.error(f"Failed to create learner for {model_id}: {e}")
            raise

    def _apply_river_inheritance(
        self, learner: OnlineLearner, parent_models: List[str], model_id: str
    ):
        """Apply spatial inheritance to River ML models."""
        try:
            # Get the River model from the learner
            river_model = learner.model

            # For River models, we can inherit by pre-training on parent model data
            # or by initializing with weighted parameters from parent models

            inheritance_samples = 0
            for parent_id in parent_models:
                parent_learner = self.learners.get(parent_id)
                if parent_learner and hasattr(parent_learner, "model"):
                    # For linear models, we can inherit coefficients
                    if hasattr(river_model, "_pipeline") and hasattr(
                        parent_learner.model, "_pipeline"
                    ):
                        try:
                            # Get the linear model from the pipeline
                            if len(river_model._pipeline) > 1:
                                child_linear = river_model._pipeline[
                                    -1
                                ]  # Last step is usually the model
                                parent_linear = parent_learner.model._pipeline[-1]

                                # Inherit weights if both are linear models
                                if hasattr(child_linear, "_weights") and hasattr(
                                    parent_linear, "_weights"
                                ):
                                    # Initialize with parent weights (scaled down for inheritance)
                                    inheritance_factor = 0.3  # 30% inheritance strength
                                    for (
                                        feature,
                                        weight,
                                    ) in parent_linear._weights.items():
                                        child_linear._weights[feature] = (
                                            weight * inheritance_factor
                                        )

                                    inheritance_samples += len(parent_linear._weights)
                                    logger.info(
                                        f"🧬 Inherited {len(parent_linear._weights)} features from {parent_id}"
                                    )
                        except Exception as e:
                            logger.debug(
                                f"Could not inherit linear weights from {parent_id}: {e}"
                            )

                    # Alternative: Inherit through synthetic training data
                    # This works for any River model type
                    if (
                        hasattr(parent_learner, "feature_names")
                        and parent_learner.feature_names
                    ):
                        try:
                            # Generate synthetic samples based on parent model's learned patterns
                            synthetic_features = self._generate_synthetic_features(
                                parent_learner
                            )
                            for features in synthetic_features[
                                :5
                            ]:  # Limit to 5 synthetic samples
                                # Make a prediction with parent model to get target
                                target = parent_learner.predict(features)
                                if target is not None:
                                    # Train child model on parent's knowledge
                                    river_model.learn_one(features, target)
                                    inheritance_samples += 1
                        except Exception as e:
                            logger.debug(
                                f"Could not generate synthetic inheritance data from {parent_id}: {e}"
                            )

            if inheritance_samples > 0:
                logger.info(
                    f"✅ Applied spatial inheritance to {model_id}: {inheritance_samples} inherited patterns from {len(parent_models)} parents"
                )
            else:
                logger.info(
                    f"⚠️ No inheritance patterns applied to {model_id} (incompatible parent models)"
                )

        except Exception as e:
            logger.error(f"Error applying River inheritance to {model_id}: {e}")

    def _generate_synthetic_features(
        self, parent_learner: OnlineLearner
    ) -> List[Dict[str, Any]]:
        """Generate synthetic feature sets based on parent model's learned patterns."""
        synthetic_samples = []

        if hasattr(parent_learner, "feature_names") and parent_learner.feature_names:
            # Create variations of known feature patterns
            base_features = {
                name: 0.5 for name in parent_learner.feature_names[:10]
            }  # Limit features

            # Generate 5 synthetic samples with variations
            for i in range(5):
                features = base_features.copy()
                # Add some variation
                for key in features:
                    features[key] += (i - 2) * 0.1  # Vary by ±0.2
                synthetic_samples.append(features)

        return synthetic_samples

    def get_learner(self, model_id: str) -> Optional[OnlineLearner]:
        """Get an existing learner."""
        return self.learners.get(model_id)

    def predict(self, model_id: str, features: Dict[str, Any]) -> Optional[Any]:
        """Make a prediction using a specific model."""
        learner = self.get_learner(model_id)
        if learner:
            self.total_predictions += 1
            return learner.predict(features)
        return None

    def predict_proba(
        self, model_id: str, features: Dict[str, Any]
    ) -> Dict[Any, float]:
        """Get prediction probabilities."""
        learner = self.get_learner(model_id)
        if learner:
            return learner.predict_proba(features)
        return {}

    def learn(self, model_id: str, features: Dict[str, Any], target: Any) -> bool:
        """Update a model with new data, creating learner if needed."""
        learner = self.get_learner(model_id)

        # Create learner if it doesn't exist (enables spatial inheritance)
        if not learner:
            try:
                logger.info(f"Creating new learner for model {model_id}")

                # Create context for spatial inheritance
                context = {
                    "features": features,
                    "domain": model_id.split("_")[0] if "_" in model_id else "default",
                    "timestamp": time.time(),
                    "x_coord": hash(model_id) % 100,  # Synthetic spatial coordinates
                    "y_coord": hash(str(features)) % 100,
                    "metadata": {"target": target},
                }

                learner = self.create_learner(model_id, context=context)
                logger.info(
                    f"✅ Created learner for {model_id} - spatial inheritance enabled"
                )
            except Exception as e:
                logger.error(f"Failed to create learner for {model_id}: {e}")
                return False

        if learner:
            try:
                learner.learn(features, target)
                self.total_updates += 1
                logger.debug(
                    f"Model {model_id} learned from transaction (total updates: {self.total_updates})"
                )
                return True
            except Exception as e:
                logger.error(f"Learning failed for model {model_id}: {e}")
        return False

    async def process_transaction(
        self, event: TransactionEvent, model_id: Optional[str] = None
    ) -> LearningResult:
        """Process a transaction event with online learning."""
        start_time = time.time()

        # Generate model ID if not provided
        if not model_id:
            model_id = self._generate_model_id(event)

        # Get or create learner
        learner = self.get_learner(model_id)
        if not learner:
            learner = self.create_learner(model_id)

        # Make prediction
        prediction = learner.predict(event.features)
        probabilities = learner.predict_proba(event.features)

        # Calculate confidence
        confidence = None
        if probabilities:
            confidence = max(probabilities.values())

        # Update model if target is available
        update_applied = False
        if event.target is not None:
            learner.learn(event.features, event.target)
            update_applied = True

        # Check for drift
        metrics = learner.get_metrics()
        drift_detected = metrics.get("drift_detected", 0.0) > 0

        processing_time = (time.time() - start_time) * 1000  # ms

        return LearningResult(
            model_id=model_id,
            prediction=prediction,
            confidence=confidence,
            update_applied=update_applied,
            drift_detected=drift_detected,
            processing_time_ms=processing_time,
            metadata={
                "algorithm": type(learner).__name__,
                "metrics": metrics,
                "probabilities": probabilities,
            },
        )

    async def batch_process_transactions(
        self, events: List[TransactionEvent]
    ) -> List[LearningResult]:
        """Process multiple transactions in parallel."""
        tasks = [self.process_transaction(event) for event in events]
        return await asyncio.gather(*tasks)

    def _generate_model_id(self, event: TransactionEvent) -> str:
        """Generate model ID based on transaction context."""
        # Use user_id as primary key, fall back to session_id
        if event.user_id:
            return f"user_{event.user_id}"
        elif event.session_id:
            return f"session_{event.session_id}"
        else:
            return f"anonymous_{hash(event.transaction_id) % 10000}"

    def get_model_metrics(self, model_id: str) -> Dict[str, Any]:
        """Get metrics for a specific model."""
        learner = self.get_learner(model_id)
        if learner:
            return learner.get_metrics()
        return {}

    def get_engine_stats(self) -> Dict[str, Any]:
        """Get overall engine statistics."""
        uptime = time.time() - self.start_time
        return {
            "total_models": len(self.learners),
            "total_predictions": self.total_predictions,
            "total_updates": self.total_updates,
            "predictions_per_second": (
                self.total_predictions / uptime if uptime > 0 else 0
            ),
            "updates_per_second": self.total_updates / uptime if uptime > 0 else 0,
            "uptime_seconds": uptime,
        }

    def cleanup_inactive_models(self, max_age_hours: float = 24):
        """Remove models that haven't been used recently."""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        inactive_models = []
        for model_id, learner in self.learners.items():
            # This is a simplified check - in practice, you'd track last access time
            if hasattr(learner, "last_access_time"):
                if learner.last_access_time < cutoff_time:
                    inactive_models.append(model_id)

        for model_id in inactive_models:
            del self.learners[model_id]
            logger.info(f"Cleaned up inactive model: {model_id}")

        return len(inactive_models)


# Global learning engine instance
learning_engine = OnlineLearningEngine(default_algorithm=config.model.base_model_type)
