"""Metrics collection and monitoring for TML platform."""

import time
import threading
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
)
from loguru import logger

from tml.core.config import config


@dataclass
class ModelMetrics:
    """Metrics for a specific model."""

    model_id: str
    prediction_count: int = 0
    update_count: int = 0
    error_count: int = 0
    avg_prediction_time: float = 0.0
    avg_update_time: float = 0.0
    accuracy: float = 0.0
    drift_score: float = 0.0
    last_prediction_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)

    def update_prediction_metrics(self, processing_time: float):
        """Update prediction metrics."""
        self.prediction_count += 1
        self.avg_prediction_time = (
            self.avg_prediction_time * (self.prediction_count - 1) + processing_time
        ) / self.prediction_count
        self.last_prediction_time = time.time()

    def update_learning_metrics(self, processing_time: float, success: bool):
        """Update learning metrics."""
        if success:
            self.update_count += 1
            self.avg_update_time = (
                self.avg_update_time * (self.update_count - 1) + processing_time
            ) / self.update_count
            self.last_update_time = time.time()
        else:
            self.error_count += 1


class MetricsCollector:
    """Centralized metrics collector for TML platform."""

    def __init__(self):
        # Prometheus registry
        self.registry = CollectorRegistry()

        # Prometheus metrics
        self.prediction_counter = Counter(
            "tml_predictions_total",
            "Total number of predictions made",
            ["model_id", "status"],
            registry=self.registry,
        )

        self.prediction_duration = Histogram(
            "tml_prediction_duration_seconds",
            "Time spent on predictions",
            ["model_id"],
            registry=self.registry,
        )

        self.learning_counter = Counter(
            "tml_learning_updates_total",
            "Total number of learning updates",
            ["model_id", "status"],
            registry=self.registry,
        )

        self.learning_duration = Histogram(
            "tml_learning_duration_seconds",
            "Time spent on learning updates",
            ["model_id"],
            registry=self.registry,
        )

        self.model_accuracy = Gauge(
            "tml_model_accuracy",
            "Current model accuracy",
            ["model_id"],
            registry=self.registry,
        )

        self.drift_score = Gauge(
            "tml_drift_score",
            "Current drift score for model",
            ["model_id"],
            registry=self.registry,
        )

        self.active_models = Gauge(
            "tml_active_models", "Number of active models", registry=self.registry
        )

        self.request_duration = Histogram(
            "tml_request_duration_seconds",
            "HTTP request duration",
            ["endpoint", "method", "status"],
            registry=self.registry,
        )

        # Internal metrics storage
        self.model_metrics: Dict[str, ModelMetrics] = {}
        self.system_metrics: Dict[str, Any] = {
            "total_requests": 0,
            "total_errors": 0,
            "uptime_start": time.time(),
        }

        # Thread safety
        self.lock = threading.RLock()

        # Recent activity tracking
        self.recent_predictions = deque(maxlen=1000)
        self.recent_updates = deque(maxlen=1000)

    def record_prediction(
        self, model_id: str, processing_time_ms: float, success: bool = True
    ):
        """Record a prediction event."""
        with self.lock:
            # Update internal metrics
            if model_id not in self.model_metrics:
                self.model_metrics[model_id] = ModelMetrics(model_id=model_id)

            self.model_metrics[model_id].update_prediction_metrics(processing_time_ms)

            # Update Prometheus metrics
            status = "success" if success else "error"
            self.prediction_counter.labels(model_id=model_id, status=status).inc()
            self.prediction_duration.labels(model_id=model_id).observe(
                processing_time_ms / 1000.0
            )

            # Track recent activity
            self.recent_predictions.append(
                {
                    "model_id": model_id,
                    "timestamp": time.time(),
                    "processing_time_ms": processing_time_ms,
                    "success": success,
                }
            )

            # Update active models count
            self.active_models.set(len(self.model_metrics))

    def record_learning_update(
        self, model_id: str, processing_time_ms: float, success: bool = True
    ):
        """Record a learning update event."""
        with self.lock:
            # Update internal metrics
            if model_id not in self.model_metrics:
                self.model_metrics[model_id] = ModelMetrics(model_id=model_id)

            self.model_metrics[model_id].update_learning_metrics(
                processing_time_ms, success
            )

            # Update Prometheus metrics
            status = "success" if success else "error"
            self.learning_counter.labels(model_id=model_id, status=status).inc()

            if success:
                self.learning_duration.labels(model_id=model_id).observe(
                    processing_time_ms / 1000.0
                )

            # Track recent activity
            self.recent_updates.append(
                {
                    "model_id": model_id,
                    "timestamp": time.time(),
                    "processing_time_ms": processing_time_ms,
                    "success": success,
                }
            )

    def record_model_accuracy(self, model_id: str, accuracy: float):
        """Record model accuracy."""
        with self.lock:
            if model_id not in self.model_metrics:
                self.model_metrics[model_id] = ModelMetrics(model_id=model_id)

            self.model_metrics[model_id].accuracy = accuracy
            self.model_accuracy.labels(model_id=model_id).set(accuracy)

    def record_drift_score(self, model_id: str, drift_score: float):
        """Record drift score for a model."""
        with self.lock:
            if model_id not in self.model_metrics:
                self.model_metrics[model_id] = ModelMetrics(model_id=model_id)

            self.model_metrics[model_id].drift_score = drift_score
            self.drift_score.labels(model_id=model_id).set(drift_score)

    def record_request_duration(
        self,
        processing_time_ms: float,
        endpoint: str = "unknown",
        method: str = "GET",
        status: str = "success",
    ):
        """Record HTTP request duration."""
        self.request_duration.labels(
            endpoint=endpoint, method=method, status=status
        ).observe(processing_time_ms / 1000.0)

        with self.lock:
            self.system_metrics["total_requests"] += 1
            if status == "error":
                self.system_metrics["total_errors"] += 1

    def record_batch_prediction(self, batch_size: int, processing_time_ms: float):
        """Record batch prediction metrics."""
        with self.lock:
            # Record as multiple individual predictions for simplicity
            avg_time_per_prediction = (
                processing_time_ms / batch_size if batch_size > 0 else 0
            )

            for _ in range(batch_size):
                self.record_prediction("batch_model", avg_time_per_prediction)

    def get_model_metrics(self, model_id: str) -> Optional[ModelMetrics]:
        """Get metrics for a specific model."""
        with self.lock:
            return self.model_metrics.get(model_id)

    def get_all_model_metrics(self) -> Dict[str, ModelMetrics]:
        """Get metrics for all models."""
        with self.lock:
            return self.model_metrics.copy()

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        with self.lock:
            uptime = time.time() - self.system_metrics["uptime_start"]

            return {
                **self.system_metrics,
                "uptime_seconds": uptime,
                "active_models_count": len(self.model_metrics),
                "total_predictions": sum(
                    m.prediction_count for m in self.model_metrics.values()
                ),
                "total_updates": sum(
                    m.update_count for m in self.model_metrics.values()
                ),
                "total_errors": sum(m.error_count for m in self.model_metrics.values()),
                "avg_prediction_time_ms": self._calculate_avg_prediction_time(),
                "avg_update_time_ms": self._calculate_avg_update_time(),
            }

    def get_recent_activity(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """Get recent prediction and update activity."""
        with self.lock:
            return {
                "recent_predictions": list(self.recent_predictions)[-limit:],
                "recent_updates": list(self.recent_updates)[-limit:],
            }

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode("utf-8")

    def _calculate_avg_prediction_time(self) -> float:
        """Calculate average prediction time across all models."""
        if not self.model_metrics:
            return 0.0

        total_time = sum(
            m.avg_prediction_time * m.prediction_count
            for m in self.model_metrics.values()
        )
        total_count = sum(m.prediction_count for m in self.model_metrics.values())

        return total_time / total_count if total_count > 0 else 0.0

    def _calculate_avg_update_time(self) -> float:
        """Calculate average update time across all models."""
        if not self.model_metrics:
            return 0.0

        total_time = sum(
            m.avg_update_time * m.update_count for m in self.model_metrics.values()
        )
        total_count = sum(m.update_count for m in self.model_metrics.values())

        return total_time / total_count if total_count > 0 else 0.0

    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self.lock:
            self.model_metrics.clear()
            self.recent_predictions.clear()
            self.recent_updates.clear()
            self.system_metrics = {
                "total_requests": 0,
                "total_errors": 0,
                "uptime_start": time.time(),
            }

    def cleanup_old_models(self, max_age_hours: float = 24):
        """Remove metrics for models that haven't been active recently."""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        with self.lock:
            inactive_models = []
            for model_id, metrics in self.model_metrics.items():
                last_activity = max(
                    metrics.last_prediction_time, metrics.last_update_time
                )
                if last_activity < cutoff_time:
                    inactive_models.append(model_id)

            for model_id in inactive_models:
                del self.model_metrics[model_id]
                logger.info(f"Cleaned up metrics for inactive model: {model_id}")

            return len(inactive_models)


class AlertManager:
    """Manager for handling alerts based on metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_thresholds = {
            "high_error_rate": 0.05,  # 5% error rate
            "high_drift_score": 0.1,  # Drift score > 0.1
            "slow_predictions": 1000,  # > 1 second
            "low_accuracy": 0.7,  # < 70% accuracy
        }
        self.active_alerts: Dict[str, Dict[str, Any]] = {}

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alert conditions and return active alerts."""
        alerts = []

        # Check system-wide metrics
        system_metrics = self.metrics_collector.get_system_metrics()

        # High error rate alert
        total_requests = system_metrics.get("total_requests", 0)
        total_errors = system_metrics.get("total_errors", 0)

        if total_requests > 100:  # Only check if we have enough data
            error_rate = total_errors / total_requests
            if error_rate > self.alert_thresholds["high_error_rate"]:
                alert = {
                    "type": "high_error_rate",
                    "severity": "warning",
                    "message": f"High error rate: {error_rate:.2%}",
                    "value": error_rate,
                    "threshold": self.alert_thresholds["high_error_rate"],
                    "timestamp": time.time(),
                }
                alerts.append(alert)

        # Check per-model metrics
        for model_id, metrics in self.metrics_collector.get_all_model_metrics().items():
            # High drift score
            if metrics.drift_score > self.alert_thresholds["high_drift_score"]:
                alert = {
                    "type": "high_drift_score",
                    "model_id": model_id,
                    "severity": "warning",
                    "message": f"High drift score for model {model_id}: {metrics.drift_score:.3f}",
                    "value": metrics.drift_score,
                    "threshold": self.alert_thresholds["high_drift_score"],
                    "timestamp": time.time(),
                }
                alerts.append(alert)

            # Slow predictions
            if metrics.avg_prediction_time > self.alert_thresholds["slow_predictions"]:
                alert = {
                    "type": "slow_predictions",
                    "model_id": model_id,
                    "severity": "warning",
                    "message": f"Slow predictions for model {model_id}: {metrics.avg_prediction_time:.1f}ms",
                    "value": metrics.avg_prediction_time,
                    "threshold": self.alert_thresholds["slow_predictions"],
                    "timestamp": time.time(),
                }
                alerts.append(alert)

            # Low accuracy
            if (
                metrics.prediction_count > 100
                and metrics.accuracy < self.alert_thresholds["low_accuracy"]
            ):
                alert = {
                    "type": "low_accuracy",
                    "model_id": model_id,
                    "severity": "critical",
                    "message": f"Low accuracy for model {model_id}: {metrics.accuracy:.2%}",
                    "value": metrics.accuracy,
                    "threshold": self.alert_thresholds["low_accuracy"],
                    "timestamp": time.time(),
                }
                alerts.append(alert)

        # Update active alerts
        self._update_active_alerts(alerts)

        return alerts

    def _update_active_alerts(self, new_alerts: List[Dict[str, Any]]):
        """Update the active alerts dictionary."""
        # Clear old alerts
        self.active_alerts.clear()

        # Add new alerts
        for alert in new_alerts:
            alert_key = f"{alert['type']}_{alert.get('model_id', 'system')}"
            self.active_alerts[alert_key] = alert

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active alerts."""
        return list(self.active_alerts.values())

    def set_threshold(self, alert_type: str, threshold: float):
        """Set alert threshold."""
        if alert_type in self.alert_thresholds:
            self.alert_thresholds[alert_type] = threshold
            logger.info(f"Updated {alert_type} threshold to {threshold}")
        else:
            raise ValueError(f"Unknown alert type: {alert_type}")


# Global metrics collector instance
metrics_collector = MetricsCollector()
alert_manager = AlertManager(metrics_collector)
