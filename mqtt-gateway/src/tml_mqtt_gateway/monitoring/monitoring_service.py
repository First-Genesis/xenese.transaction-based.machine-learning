"""
Monitoring Service
Comprehensive monitoring, metrics collection, and observability
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

import structlog
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary

from ..config import TMLGatewayConfig
from ..metrics import TMLGatewayMetrics


logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """System health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """Types of metrics to collect"""

    SYSTEM = "system"
    MQTT = "mqtt"
    KAFKA = "kafka"
    DATABASE = "database"
    DEVICE = "device"
    PERFORMANCE = "performance"


class MonitoringService:
    """
    Advanced Monitoring Service for Production

    Features:
    - Real-time metrics collection
    - System health monitoring
    - Performance tracking
    - Resource utilization monitoring
    - Anomaly detection
    - Alert generation
    - Historical data retention
    - Predictive analytics
    """

    def __init__(self, config: TMLGatewayConfig, metrics: TMLGatewayMetrics):
        self.config = config
        self.metrics = metrics

        # Health tracking
        self.health_status = HealthStatus.UNKNOWN
        self.component_health = {}  # component -> status

        # Performance metrics
        self.performance_metrics = {
            "message_throughput": deque(maxlen=1000),
            "processing_latency": deque(maxlen=1000),
            "error_rate": deque(maxlen=1000),
            "resource_usage": deque(maxlen=1000),
        }

        # Time series data
        self.time_series_data = {}  # metric -> [(timestamp, value)]

        # Anomaly detection
        self.anomaly_thresholds = {
            "cpu_percent": 85.0,
            "memory_percent": 90.0,
            "disk_percent": 95.0,
            "message_latency_ms": 100.0,
            "error_rate_percent": 5.0,
        }

        # Monitoring intervals
        self.intervals = {
            "system": 10,  # seconds
            "performance": 5,
            "health": 30,
            "cleanup": 3600,  # 1 hour
        }

        # Alert conditions
        self.alert_conditions = {
            "high_cpu": False,
            "high_memory": False,
            "high_error_rate": False,
            "degraded_performance": False,
            "device_offline": False,
        }

        # Custom Prometheus metrics
        self._initialize_custom_metrics()

        self.logger = logger.bind(component="monitoring_service")

    def _initialize_custom_metrics(self):
        """Initialize custom Prometheus metrics"""
        # System metrics
        self.system_cpu_usage = Gauge(
            "gateway_system_cpu_percent", "CPU usage percentage"
        )
        self.system_memory_usage = Gauge(
            "gateway_system_memory_percent", "Memory usage percentage"
        )
        self.system_disk_usage = Gauge(
            "gateway_system_disk_percent", "Disk usage percentage"
        )
        self.system_network_bytes_sent = Counter(
            "gateway_network_bytes_sent_total", "Total network bytes sent"
        )
        self.system_network_bytes_recv = Counter(
            "gateway_network_bytes_received_total", "Total network bytes received"
        )

        # Performance metrics
        self.message_processing_time = Histogram(
            "gateway_message_processing_seconds",
            "Message processing time distribution",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
        )
        self.message_throughput_rate = Gauge(
            "gateway_message_throughput_per_second", "Current message throughput rate"
        )
        self.active_connections = Gauge(
            "gateway_active_connections", "Number of active connections"
        )

        # Health metrics
        self.health_score = Gauge(
            "gateway_health_score", "Overall system health score (0-100)"
        )
        self.component_health_status = Gauge(
            "gateway_component_health", "Component health status", ["component"]
        )

        # Error metrics
        self.error_rate = Gauge(
            "gateway_error_rate_percent", "Current error rate percentage"
        )
        self.alert_active = Gauge(
            "gateway_alert_active", "Active alert indicator", ["alert_type"]
        )

    async def initialize(self) -> None:
        """Initialize monitoring service"""
        try:
            self.logger.info("Initializing monitoring service")

            # Start monitoring tasks
            asyncio.create_task(self._monitor_system())
            asyncio.create_task(self._monitor_performance())
            asyncio.create_task(self._monitor_health())
            asyncio.create_task(self._cleanup_old_data())

            # Initial health check
            await self._perform_health_check()

            self.logger.info("Monitoring service initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize monitoring service", error=str(e))
            raise

    async def _monitor_system(self) -> None:
        """Monitor system resources"""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.system_cpu_usage.set(cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                self.system_memory_usage.set(memory_percent)

                # Disk usage
                disk = psutil.disk_usage("/")
                disk_percent = disk.percent
                self.system_disk_usage.set(disk_percent)

                # Network I/O
                net_io = psutil.net_io_counters()
                self.system_network_bytes_sent.inc(net_io.bytes_sent)
                self.system_network_bytes_recv.inc(net_io.bytes_recv)

                # Store in time series
                timestamp = datetime.utcnow()
                self._store_time_series("cpu_percent", timestamp, cpu_percent)
                self._store_time_series("memory_percent", timestamp, memory_percent)
                self._store_time_series("disk_percent", timestamp, disk_percent)

                # Check for anomalies
                await self._check_anomalies(
                    {
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "disk_percent": disk_percent,
                    }
                )

                # Store in performance metrics
                self.performance_metrics["resource_usage"].append(
                    {
                        "timestamp": timestamp,
                        "cpu": cpu_percent,
                        "memory": memory_percent,
                        "disk": disk_percent,
                    }
                )

                await asyncio.sleep(self.intervals["system"])

            except Exception as e:
                self.logger.error("Error in system monitoring", error=str(e))
                await asyncio.sleep(30)

    async def _monitor_performance(self) -> None:
        """Monitor application performance"""
        while True:
            try:
                # Calculate message throughput
                mqtt_messages = self.metrics.mqtt.messages_received._value.get()
                kafka_messages = self.metrics.kafka.messages_sent._value.get()

                # Calculate throughput rate (messages per second)
                throughput_rate = (
                    (mqtt_messages / self.intervals["performance"])
                    if mqtt_messages > 0
                    else 0
                )
                self.message_throughput_rate.set(throughput_rate)

                # Get active connections
                active_conn = self.metrics.mqtt.connected_clients._value.get()
                self.active_connections.set(active_conn)

                # Calculate error rate
                total_errors = (
                    self.metrics.mqtt.processing_errors._value.get()
                    + self.metrics.kafka.send_errors._value.get()
                )
                total_messages = mqtt_messages + kafka_messages
                error_rate = (
                    (total_errors / total_messages * 100) if total_messages > 0 else 0
                )
                self.error_rate.set(error_rate)

                # Store performance metrics
                timestamp = datetime.utcnow()
                self.performance_metrics["message_throughput"].append(
                    {"timestamp": timestamp, "throughput": throughput_rate}
                )
                self.performance_metrics["error_rate"].append(
                    {"timestamp": timestamp, "rate": error_rate}
                )

                # Check performance thresholds
                if error_rate > self.anomaly_thresholds["error_rate_percent"]:
                    self.alert_conditions["high_error_rate"] = True
                    self.alert_active.labels(alert_type="high_error_rate").set(1)
                else:
                    self.alert_conditions["high_error_rate"] = False
                    self.alert_active.labels(alert_type="high_error_rate").set(0)

                await asyncio.sleep(self.intervals["performance"])

            except Exception as e:
                self.logger.error("Error in performance monitoring", error=str(e))
                await asyncio.sleep(30)

    async def _monitor_health(self) -> None:
        """Monitor overall system health"""
        while True:
            try:
                await self._perform_health_check()

                await asyncio.sleep(self.intervals["health"])

            except Exception as e:
                self.logger.error("Error in health monitoring", error=str(e))
                await asyncio.sleep(60)

    async def _perform_health_check(self) -> None:
        """Perform comprehensive health check"""
        try:
            health_scores = {}

            # Check MQTT health
            mqtt_healthy = self.metrics.mqtt.connected_clients._value.get() > 0
            health_scores["mqtt"] = 100 if mqtt_healthy else 0
            self.component_health["mqtt"] = (
                HealthStatus.HEALTHY if mqtt_healthy else HealthStatus.CRITICAL
            )
            self.component_health_status.labels(component="mqtt").set(
                1 if mqtt_healthy else 0
            )

            # Check Kafka health
            kafka_errors = self.metrics.kafka.send_errors._value.get()
            kafka_healthy = kafka_errors < 10  # Less than 10 errors
            health_scores["kafka"] = 100 if kafka_healthy else 50
            self.component_health["kafka"] = (
                HealthStatus.HEALTHY if kafka_healthy else HealthStatus.DEGRADED
            )
            self.component_health_status.labels(component="kafka").set(
                1 if kafka_healthy else 0.5
            )

            # Check database health
            db_connections = self.metrics.database.db_connections_active._value.get()
            db_healthy = db_connections > 0
            health_scores["database"] = 100 if db_healthy else 0
            self.component_health["database"] = (
                HealthStatus.HEALTHY if db_healthy else HealthStatus.CRITICAL
            )
            self.component_health_status.labels(component="database").set(
                1 if db_healthy else 0
            )

            # Check system resources
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage("/").percent

            resource_healthy = (
                cpu_percent < self.anomaly_thresholds["cpu_percent"]
                and memory_percent < self.anomaly_thresholds["memory_percent"]
                and disk_percent < self.anomaly_thresholds["disk_percent"]
            )

            if resource_healthy:
                resource_score = 100
                resource_status = HealthStatus.HEALTHY
            elif cpu_percent < 95 and memory_percent < 95:
                resource_score = 75
                resource_status = HealthStatus.DEGRADED
            else:
                resource_score = 25
                resource_status = HealthStatus.CRITICAL

            health_scores["resources"] = resource_score
            self.component_health["resources"] = resource_status
            self.component_health_status.labels(component="resources").set(
                resource_score / 100
            )

            # Calculate overall health score
            overall_score = sum(health_scores.values()) / len(health_scores)
            self.health_score.set(overall_score)

            # Determine overall health status
            if overall_score >= 90:
                self.health_status = HealthStatus.HEALTHY
            elif overall_score >= 70:
                self.health_status = HealthStatus.DEGRADED
            else:
                self.health_status = HealthStatus.CRITICAL

            self.logger.info(
                "Health check completed",
                overall_score=overall_score,
                status=self.health_status.value,
                components=self.component_health,
            )

        except Exception as e:
            self.logger.error("Error performing health check", error=str(e))
            self.health_status = HealthStatus.UNKNOWN

    async def _check_anomalies(self, metrics: Dict[str, float]) -> None:
        """Check for anomalies in metrics"""
        try:
            # Check CPU
            if metrics.get("cpu_percent", 0) > self.anomaly_thresholds["cpu_percent"]:
                if not self.alert_conditions["high_cpu"]:
                    self.alert_conditions["high_cpu"] = True
                    self.alert_active.labels(alert_type="high_cpu").set(1)
                    self.logger.warning(
                        "High CPU usage detected", cpu_percent=metrics["cpu_percent"]
                    )
            else:
                self.alert_conditions["high_cpu"] = False
                self.alert_active.labels(alert_type="high_cpu").set(0)

            # Check memory
            if (
                metrics.get("memory_percent", 0)
                > self.anomaly_thresholds["memory_percent"]
            ):
                if not self.alert_conditions["high_memory"]:
                    self.alert_conditions["high_memory"] = True
                    self.alert_active.labels(alert_type="high_memory").set(1)
                    self.logger.warning(
                        "High memory usage detected",
                        memory_percent=metrics["memory_percent"],
                    )
            else:
                self.alert_conditions["high_memory"] = False
                self.alert_active.labels(alert_type="high_memory").set(0)

        except Exception as e:
            self.logger.error("Error checking anomalies", error=str(e))

    def _store_time_series(
        self, metric_name: str, timestamp: datetime, value: float
    ) -> None:
        """Store time series data"""
        try:
            if metric_name not in self.time_series_data:
                self.time_series_data[metric_name] = deque(maxlen=10000)

            self.time_series_data[metric_name].append((timestamp, value))

        except Exception as e:
            self.logger.error(
                "Error storing time series data", metric_name=metric_name, error=str(e)
            )

    async def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data"""
        while True:
            try:
                await asyncio.sleep(self.intervals["cleanup"])

                cutoff_time = datetime.utcnow() - timedelta(hours=24)

                # Clean up time series data
                for metric_name, data_points in self.time_series_data.items():
                    # Remove data older than 24 hours
                    while data_points and data_points[0][0] < cutoff_time:
                        data_points.popleft()

                # Clean up performance metrics
                for metric_type, data_points in self.performance_metrics.items():
                    # Keep only recent data
                    while data_points and len(data_points) > 1000:
                        data_points.popleft()

                self.logger.info("Cleaned up old monitoring data")

            except Exception as e:
                self.logger.error("Error cleaning up old data", error=str(e))

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "overall_status": self.health_status.value,
            "health_score": self.health_score._value.get()
            if hasattr(self, "health_score")
            else 0,
            "components": {
                component: status.value
                for component, status in self.component_health.items()
            },
            "active_alerts": [
                alert for alert, active in self.alert_conditions.items() if active
            ],
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return {
            "throughput_rate": self.message_throughput_rate._value.get()
            if hasattr(self, "message_throughput_rate")
            else 0,
            "active_connections": self.active_connections._value.get()
            if hasattr(self, "active_connections")
            else 0,
            "error_rate": self.error_rate._value.get()
            if hasattr(self, "error_rate")
            else 0,
            "cpu_usage": self.system_cpu_usage._value.get()
            if hasattr(self, "system_cpu_usage")
            else 0,
            "memory_usage": self.system_memory_usage._value.get()
            if hasattr(self, "system_memory_usage")
            else 0,
            "disk_usage": self.system_disk_usage._value.get()
            if hasattr(self, "system_disk_usage")
            else 0,
        }

    def get_time_series(
        self, metric_name: str, duration_hours: int = 1
    ) -> List[Tuple[datetime, float]]:
        """Get time series data for metric"""
        if metric_name not in self.time_series_data:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=duration_hours)

        return [
            (ts, value)
            for ts, value in self.time_series_data[metric_name]
            if ts >= cutoff_time
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get monitoring service status"""
        return {
            "health_status": self.health_status.value,
            "active_alerts": sum(
                1 for active in self.alert_conditions.values() if active
            ),
            "monitored_metrics": len(self.time_series_data),
            "anomaly_thresholds": self.anomaly_thresholds,
        }
