"""
Edge ML Manager
Manages machine learning models deployed at the edge for real-time inference
"""

import asyncio
import json
import pickle
import os
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

import numpy as np
import structlog
from sklearn.base import BaseEstimator
import joblib

from ..config import TMLGatewayConfig
from ..metrics import TMLGatewayMetrics


logger = structlog.get_logger(__name__)


class ModelType(Enum):
    """Supported edge ML model types"""

    ANOMALY_DETECTION = "anomaly_detection"
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    TIME_SERIES = "time_series"


class ModelStatus(Enum):
    """Edge model deployment status"""

    DOWNLOADING = "downloading"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    UPDATING = "updating"


class EdgeMLManager:
    """
    Edge Machine Learning Manager

    Features:
    - Model deployment to edge devices
    - Real-time inference at the edge
    - Model versioning and updates
    - Performance monitoring
    - Automatic model optimization
    - Offline inference capability
    - Model drift detection
    - Resource-aware deployment
    """

    def __init__(self, config: TMLGatewayConfig, metrics: TMLGatewayMetrics):
        self.config = config
        self.metrics = metrics

        # Edge model storage
        self.models_dir = Path("/app/edge_models")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Deployed models registry
        self.deployed_models = {}  # model_id -> model_info
        self.model_instances = {}  # model_id -> loaded_model

        # Inference statistics
        self.inference_stats = {}  # model_id -> stats

        # Model update queue
        self.update_queue = asyncio.Queue()

        # Resource monitoring
        self.resource_limits = {
            "max_models": 10,
            "max_memory_mb": 1024,
            "max_cpu_percent": 80,
        }

        # Performance thresholds
        self.performance_thresholds = {
            "max_inference_time_ms": 100,
            "min_accuracy": 0.8,
            "max_error_rate": 0.05,
        }

        self.logger = logger.bind(component="edge_ml_manager")

    async def initialize(self) -> None:
        """Initialize edge ML manager"""
        try:
            self.logger.info("Initializing Edge ML Manager")

            # Load existing models
            await self._load_existing_models()

            # Start model monitor
            asyncio.create_task(self._model_monitor())

            # Start update processor
            asyncio.create_task(self._update_processor())

            self.logger.info("Edge ML Manager initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize Edge ML Manager", error=str(e))
            raise

    async def deploy_model(
        self,
        model_id: str,
        model_data: bytes,
        model_type: ModelType,
        version: str,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Deploy ML model to edge

        Args:
            model_id: Unique model identifier
            model_data: Serialized model data
            model_type: Type of ML model
            version: Model version
            metadata: Additional model metadata

        Returns:
            True if deployment successful
        """
        try:
            self.logger.info(
                "Deploying model to edge",
                model_id=model_id,
                model_type=model_type.value,
                version=version,
            )

            # Check resource limits
            if not await self._check_resource_availability():
                raise RuntimeError("Insufficient resources for model deployment")

            # Create model directory
            model_path = self.models_dir / model_id
            model_path.mkdir(exist_ok=True)

            # Save model data
            model_file = model_path / f"{model_id}_v{version}.pkl"
            with open(model_file, "wb") as f:
                f.write(model_data)

            # Create model info
            model_info = {
                "model_id": model_id,
                "model_type": model_type.value,
                "version": version,
                "deployed_at": datetime.utcnow(),
                "status": ModelStatus.LOADING.value,
                "file_path": str(model_file),
                "metadata": metadata or {},
                "inference_count": 0,
                "last_inference": None,
                "performance_metrics": {
                    "avg_inference_time_ms": 0.0,
                    "accuracy": 0.0,
                    "error_rate": 0.0,
                },
            }

            # Load model
            model_instance = await self._load_model(model_file, model_type)

            # Store model
            self.deployed_models[model_id] = model_info
            self.model_instances[model_id] = model_instance
            self.inference_stats[model_id] = []

            # Update status
            model_info["status"] = ModelStatus.READY.value

            self.logger.info(
                "Model deployed successfully",
                model_id=model_id,
                file_size=len(model_data),
            )

            return True

        except Exception as e:
            self.logger.error("Failed to deploy model", model_id=model_id, error=str(e))

            # Update status to error
            if model_id in self.deployed_models:
                self.deployed_models[model_id]["status"] = ModelStatus.ERROR.value

            return False

    async def predict(
        self, model_id: str, features: Dict[str, Any], return_confidence: bool = False
    ) -> Dict[str, Any]:
        """
        Perform inference using deployed model

        Args:
            model_id: Model identifier
            features: Input features for prediction
            return_confidence: Whether to return confidence scores

        Returns:
            Prediction results
        """
        try:
            # Check if model is deployed and ready
            if model_id not in self.deployed_models:
                raise ValueError(f"Model {model_id} not deployed")

            model_info = self.deployed_models[model_id]
            if model_info["status"] != ModelStatus.READY.value:
                raise ValueError(
                    f"Model {model_id} not ready (status: {model_info['status']})"
                )

            model = self.model_instances[model_id]

            # Prepare features
            feature_array = self._prepare_features(features, model_info)

            # Perform inference
            start_time = time.time()

            if model_info["model_type"] == ModelType.ANOMALY_DETECTION.value:
                prediction = model.predict(feature_array)
                anomaly_score = (
                    model.decision_function(feature_array)
                    if hasattr(model, "decision_function")
                    else None
                )
                result = {
                    "prediction": int(prediction[0]),
                    "is_anomaly": bool(prediction[0] == -1),
                    "anomaly_score": float(anomaly_score[0])
                    if anomaly_score is not None
                    else None,
                }

            elif model_info["model_type"] == ModelType.CLASSIFICATION.value:
                prediction = model.predict(feature_array)
                if return_confidence and hasattr(model, "predict_proba"):
                    probabilities = model.predict_proba(feature_array)
                    confidence = float(np.max(probabilities))
                    class_probabilities = dict(zip(model.classes_, probabilities[0]))
                else:
                    confidence = None
                    class_probabilities = None

                result = {
                    "prediction": int(prediction[0])
                    if isinstance(prediction[0], (np.integer, int))
                    else str(prediction[0]),
                    "confidence": confidence,
                    "class_probabilities": class_probabilities,
                }

            elif model_info["model_type"] == ModelType.REGRESSION.value:
                prediction = model.predict(feature_array)
                result = {"prediction": float(prediction[0])}

            else:
                # Generic prediction
                prediction = model.predict(feature_array)
                result = {
                    "prediction": prediction[0].tolist()
                    if isinstance(prediction[0], np.ndarray)
                    else prediction[0]
                }

            inference_time = (time.time() - start_time) * 1000  # milliseconds

            # Update statistics
            await self._update_inference_stats(model_id, inference_time, result)

            # Add metadata to result
            result.update(
                {
                    "model_id": model_id,
                    "model_version": model_info["version"],
                    "inference_time_ms": inference_time,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            return result

        except Exception as e:
            self.logger.error("Inference failed", model_id=model_id, error=str(e))
            raise

    async def update_model(
        self, model_id: str, new_model_data: bytes, new_version: str
    ) -> bool:
        """
        Update deployed model with new version

        Args:
            model_id: Model identifier
            new_model_data: New model data
            new_version: New version string

        Returns:
            True if update successful
        """
        try:
            if model_id not in self.deployed_models:
                raise ValueError(f"Model {model_id} not deployed")

            # Add to update queue
            await self.update_queue.put(
                {
                    "model_id": model_id,
                    "model_data": new_model_data,
                    "version": new_version,
                    "timestamp": datetime.utcnow(),
                }
            )

            self.logger.info(
                "Model update queued", model_id=model_id, new_version=new_version
            )

            return True

        except Exception as e:
            self.logger.error(
                "Failed to queue model update", model_id=model_id, error=str(e)
            )
            return False

    async def remove_model(self, model_id: str) -> bool:
        """
        Remove deployed model from edge

        Args:
            model_id: Model identifier

        Returns:
            True if removal successful
        """
        try:
            if model_id not in self.deployed_models:
                return True  # Already removed

            # Remove from memory
            if model_id in self.model_instances:
                del self.model_instances[model_id]

            if model_id in self.inference_stats:
                del self.inference_stats[model_id]

            # Remove files
            model_path = self.models_dir / model_id
            if model_path.exists():
                import shutil

                shutil.rmtree(model_path)

            # Remove from registry
            del self.deployed_models[model_id]

            self.logger.info("Model removed from edge", model_id=model_id)
            return True

        except Exception as e:
            self.logger.error("Failed to remove model", model_id=model_id, error=str(e))
            return False

    async def _load_model(self, model_file: Path, model_type: ModelType) -> Any:
        """Load model from file"""
        try:
            # Load using joblib (supports scikit-learn models)
            model = joblib.load(model_file)

            # Validate model has required methods
            if model_type in [
                ModelType.ANOMALY_DETECTION,
                ModelType.CLASSIFICATION,
                ModelType.REGRESSION,
            ]:
                if not hasattr(model, "predict"):
                    raise ValueError("Model missing predict method")

            return model

        except Exception as e:
            self.logger.error(
                "Failed to load model", model_file=str(model_file), error=str(e)
            )
            raise

    def _prepare_features(
        self, features: Dict[str, Any], model_info: Dict[str, Any]
    ) -> np.ndarray:
        """Prepare features for model input"""
        try:
            # Extract feature values in consistent order
            feature_names = model_info.get("metadata", {}).get(
                "feature_names", list(features.keys())
            )
            feature_values = [features.get(name, 0.0) for name in feature_names]

            # Convert to numpy array
            return np.array([feature_values])

        except Exception as e:
            self.logger.error("Failed to prepare features", error=str(e))
            raise

    async def _update_inference_stats(
        self, model_id: str, inference_time: float, result: Dict[str, Any]
    ) -> None:
        """Update inference statistics"""
        try:
            model_info = self.deployed_models[model_id]

            # Update counters
            model_info["inference_count"] += 1
            model_info["last_inference"] = datetime.utcnow()

            # Update performance metrics
            perf = model_info["performance_metrics"]

            # Update average inference time
            if perf["avg_inference_time_ms"] == 0:
                perf["avg_inference_time_ms"] = inference_time
            else:
                # Exponential moving average
                alpha = 0.1
                perf["avg_inference_time_ms"] = (
                    alpha * inference_time + (1 - alpha) * perf["avg_inference_time_ms"]
                )

            # Store recent inference stats
            stats = self.inference_stats[model_id]
            stats.append(
                {
                    "timestamp": datetime.utcnow(),
                    "inference_time": inference_time,
                    "result": result,
                }
            )

            # Keep only recent stats (last 1000)
            if len(stats) > 1000:
                stats.pop(0)

        except Exception as e:
            self.logger.error(
                "Failed to update inference stats", model_id=model_id, error=str(e)
            )

    async def _check_resource_availability(self) -> bool:
        """Check if resources are available for model deployment"""
        try:
            # Check number of models
            if len(self.deployed_models) >= self.resource_limits["max_models"]:
                return False

            # Check memory usage (simplified)
            import psutil

            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 90:  # 90% memory usage
                return False

            return True

        except Exception as e:
            self.logger.error("Failed to check resource availability", error=str(e))
            return False

    async def _load_existing_models(self) -> None:
        """Load existing models from disk"""
        try:
            model_count = 0

            for model_dir in self.models_dir.iterdir():
                if model_dir.is_dir():
                    model_id = model_dir.name

                    # Find latest model file
                    model_files = list(model_dir.glob(f"{model_id}_v*.pkl"))
                    if model_files:
                        latest_file = max(model_files, key=lambda f: f.stat().st_mtime)

                        try:
                            # Extract version from filename
                            version = latest_file.stem.split("_v")[-1]

                            # Create model info
                            model_info = {
                                "model_id": model_id,
                                "version": version,
                                "status": ModelStatus.LOADING.value,
                                "file_path": str(latest_file),
                                "deployed_at": datetime.fromtimestamp(
                                    latest_file.stat().st_mtime
                                ),
                                "inference_count": 0,
                                "performance_metrics": {
                                    "avg_inference_time_ms": 0.0,
                                    "accuracy": 0.0,
                                    "error_rate": 0.0,
                                },
                            }

                            # Try to load model
                            model_instance = joblib.load(latest_file)

                            # Store model
                            self.deployed_models[model_id] = model_info
                            self.model_instances[model_id] = model_instance
                            self.inference_stats[model_id] = []

                            model_info["status"] = ModelStatus.READY.value
                            model_count += 1

                        except Exception as e:
                            self.logger.error(
                                "Failed to load existing model",
                                model_id=model_id,
                                error=str(e),
                            )

            self.logger.info("Loaded existing models", count=model_count)

        except Exception as e:
            self.logger.error("Failed to load existing models", error=str(e))

    async def _model_monitor(self) -> None:
        """Monitor model performance and health"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                for model_id, model_info in self.deployed_models.items():
                    if model_info["status"] != ModelStatus.READY.value:
                        continue

                    # Check performance thresholds
                    perf = model_info["performance_metrics"]

                    if (
                        perf["avg_inference_time_ms"]
                        > self.performance_thresholds["max_inference_time_ms"]
                    ):
                        self.logger.warning(
                            "Model inference time exceeded threshold",
                            model_id=model_id,
                            inference_time=perf["avg_inference_time_ms"],
                        )

                    # Check if model has been used recently
                    if model_info["last_inference"]:
                        time_since_last = (
                            datetime.utcnow() - model_info["last_inference"]
                        )
                        if time_since_last > timedelta(hours=24):
                            self.logger.info(
                                "Model inactive for 24 hours", model_id=model_id
                            )

            except Exception as e:
                self.logger.error("Error in model monitor", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _update_processor(self) -> None:
        """Process model updates from queue"""
        while True:
            try:
                # Get update from queue
                update = await self.update_queue.get()

                model_id = update["model_id"]
                model_data = update["model_data"]
                new_version = update["version"]

                self.logger.info(
                    "Processing model update",
                    model_id=model_id,
                    new_version=new_version,
                )

                # Update model status
                if model_id in self.deployed_models:
                    self.deployed_models[model_id][
                        "status"
                    ] = ModelStatus.UPDATING.value

                # Save new model file
                model_path = self.models_dir / model_id
                new_model_file = model_path / f"{model_id}_v{new_version}.pkl"

                with open(new_model_file, "wb") as f:
                    f.write(model_data)

                # Load new model
                new_model_instance = await self._load_model(
                    new_model_file, ModelType.CLASSIFICATION
                )

                # Replace old model
                old_model_file = self.deployed_models[model_id]["file_path"]
                self.model_instances[model_id] = new_model_instance
                self.deployed_models[model_id]["version"] = new_version
                self.deployed_models[model_id]["file_path"] = str(new_model_file)
                self.deployed_models[model_id]["status"] = ModelStatus.READY.value

                # Remove old model file
                if os.path.exists(old_model_file):
                    os.remove(old_model_file)

                self.logger.info(
                    "Model updated successfully",
                    model_id=model_id,
                    new_version=new_version,
                )

            except Exception as e:
                self.logger.error("Failed to process model update", error=str(e))

                # Reset status on error
                if model_id in self.deployed_models:
                    self.deployed_models[model_id]["status"] = ModelStatus.ERROR.value

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get information about deployed model"""
        return self.deployed_models.get(model_id)

    def list_deployed_models(self) -> List[Dict[str, Any]]:
        """List all deployed models"""
        return list(self.deployed_models.values())

    def get_inference_statistics(self, model_id: str) -> Dict[str, Any]:
        """Get inference statistics for model"""
        if model_id not in self.deployed_models:
            return {}

        model_info = self.deployed_models[model_id]
        stats = self.inference_stats.get(model_id, [])

        # Calculate statistics from recent inferences
        recent_stats = stats[-100:] if len(stats) > 100 else stats

        if recent_stats:
            inference_times = [s["inference_time"] for s in recent_stats]
            avg_time = sum(inference_times) / len(inference_times)
            min_time = min(inference_times)
            max_time = max(inference_times)
        else:
            avg_time = min_time = max_time = 0

        return {
            "model_id": model_id,
            "total_inferences": model_info["inference_count"],
            "recent_inferences": len(recent_stats),
            "avg_inference_time_ms": avg_time,
            "min_inference_time_ms": min_time,
            "max_inference_time_ms": max_time,
            "last_inference": model_info["last_inference"].isoformat()
            if model_info["last_inference"]
            else None,
            "status": model_info["status"],
        }

    def get_status(self) -> Dict[str, Any]:
        """Get edge ML manager status"""
        total_inferences = sum(
            info["inference_count"] for info in self.deployed_models.values()
        )

        return {
            "deployed_models": len(self.deployed_models),
            "ready_models": sum(
                1
                for info in self.deployed_models.values()
                if info["status"] == ModelStatus.READY.value
            ),
            "total_inferences": total_inferences,
            "resource_limits": self.resource_limits,
            "performance_thresholds": self.performance_thresholds,
        }
