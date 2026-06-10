"""
TML MQTT Gateway Metrics
Prometheus metrics collection for monitoring and observability
"""

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server
import structlog

logger = structlog.get_logger(__name__)


class MQTTMetrics:
    """MQTT-related metrics"""

    def __init__(self):
        # Connection metrics
        self.connections_total = Counter(
            "mqtt_connections_total", "Total number of MQTT connections"
        )

        self.connection_failures = Counter(
            "mqtt_connection_failures_total", "Total number of MQTT connection failures"
        )

        self.disconnections_total = Counter(
            "mqtt_disconnections_total", "Total number of MQTT disconnections"
        )

        self.connected_clients = Gauge(
            "mqtt_connected_clients", "Number of currently connected MQTT clients"
        )

        # Message metrics
        self.messages_received = Counter(
            "mqtt_messages_received_total", "Total number of MQTT messages received"
        )

        self.messages_processed = Counter(
            "mqtt_messages_processed_total",
            "Total number of MQTT messages processed successfully",
        )

        self.messages_published = Counter(
            "mqtt_messages_published_total", "Total number of MQTT messages published"
        )

        self.parse_errors = Counter(
            "mqtt_parse_errors_total", "Total number of message parsing errors"
        )

        self.processing_errors = Counter(
            "mqtt_processing_errors_total", "Total number of message processing errors"
        )

        # Performance metrics
        self.message_processing_time = Histogram(
            "mqtt_message_processing_seconds", "Time spent processing MQTT messages"
        )

        self.queue_size = Gauge(
            "mqtt_message_queue_size", "Number of messages in the processing queue"
        )


class KafkaMetrics:
    """Kafka-related metrics"""

    def __init__(self):
        # Producer metrics
        self.messages_sent = Counter(
            "kafka_messages_sent_total", "Total number of messages sent to Kafka"
        )

        self.bytes_sent = Counter(
            "kafka_bytes_sent_total", "Total number of bytes sent to Kafka"
        )

        self.send_errors = Counter(
            "kafka_send_errors_total", "Total number of Kafka send errors"
        )

        self.dead_letter_messages = Counter(
            "kafka_dead_letter_messages_total",
            "Total number of messages sent to dead letter queue",
        )

        self.flush_timeouts = Counter(
            "kafka_flush_timeouts_total", "Total number of Kafka flush timeouts"
        )

        # Performance metrics
        self.send_duration = Histogram(
            "kafka_send_duration_seconds", "Time spent sending messages to Kafka"
        )

        self.batch_size = Histogram(
            "kafka_batch_size", "Size of message batches sent to Kafka"
        )


class GatewayMetrics:
    """Gateway-specific metrics"""

    def __init__(self):
        # Gateway status
        self.gateway_info = Info("gateway_info", "Gateway information")

        self.uptime_seconds = Gauge(
            "gateway_uptime_seconds", "Gateway uptime in seconds"
        )

        self.health_status = Gauge(
            "gateway_health_status", "Gateway health status (1=healthy, 0=unhealthy)"
        )

        # Processing metrics
        self.total_messages_processed = Counter(
            "gateway_messages_processed_total",
            "Total number of messages processed by the gateway",
        )

        self.processing_rate = Gauge(
            "gateway_processing_rate_per_second",
            "Current message processing rate per second",
        )

        # Resource metrics
        self.memory_usage_bytes = Gauge(
            "gateway_memory_usage_bytes", "Gateway memory usage in bytes"
        )

        self.cpu_usage_percent = Gauge(
            "gateway_cpu_usage_percent", "Gateway CPU usage percentage"
        )

        # Error metrics
        self.total_errors = Counter(
            "gateway_errors_total", "Total number of gateway errors", ["error_type"]
        )


class DatabaseMetrics:
    """Database-related metrics"""

    def __init__(self):
        # Connection metrics
        self.db_connections_active = Gauge(
            "db_connections_active", "Number of active database connections"
        )

        self.db_connections_total = Counter(
            "db_connections_total", "Total number of database connections created"
        )

        self.db_connection_errors = Counter(
            "db_connection_errors_total", "Total number of database connection errors"
        )

        # Query metrics
        self.db_queries_total = Counter(
            "db_queries_total", "Total number of database queries", ["operation"]
        )

        self.db_query_duration = Histogram(
            "db_query_duration_seconds", "Database query duration", ["operation"]
        )

        self.db_query_errors = Counter(
            "db_query_errors_total",
            "Total number of database query errors",
            ["operation"],
        )


class TMLGatewayMetrics:
    """Combined metrics for TML Gateway"""

    def __init__(self, gateway_id: str):
        self.gateway_id = gateway_id

        # Initialize metric groups
        self.mqtt = MQTTMetrics()
        self.kafka = KafkaMetrics()
        self.gateway = GatewayMetrics()
        self.database = DatabaseMetrics()

        # Set gateway info
        self.gateway.gateway_info.info(
            {
                "gateway_id": gateway_id,
                "version": "1.0.0",
                "component": "tml-mqtt-gateway",
            }
        )

        logger.info("Metrics initialized", gateway_id=gateway_id)

    def start_metrics_server(self, port: int = 9090) -> None:
        """Start Prometheus metrics HTTP server"""
        try:
            start_http_server(port)
            logger.info("Metrics server started", port=port)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e))
            raise

    def update_health_status(self, healthy: bool) -> None:
        """Update gateway health status"""
        self.gateway.health_status.set(1 if healthy else 0)

    def record_message_processed(self) -> None:
        """Record a processed message"""
        self.gateway.total_messages_processed.inc()

    def record_error(self, error_type: str) -> None:
        """Record an error"""
        self.gateway.total_errors.labels(error_type=error_type).inc()

    def get_metrics_summary(self) -> dict:
        """Get summary of key metrics"""
        return {
            "mqtt": {
                "connections_total": self.mqtt.connections_total._value.get(),
                "messages_received": self.mqtt.messages_received._value.get(),
                "messages_processed": self.mqtt.messages_processed._value.get(),
                "connected_clients": self.mqtt.connected_clients._value.get(),
            },
            "kafka": {
                "messages_sent": self.kafka.messages_sent._value.get(),
                "bytes_sent": self.kafka.bytes_sent._value.get(),
                "send_errors": self.kafka.send_errors._value.get(),
                "dead_letter_messages": self.kafka.dead_letter_messages._value.get(),
            },
            "gateway": {
                "total_messages_processed": self.gateway.total_messages_processed._value.get(),
                "health_status": self.gateway.health_status._value.get(),
                "uptime_seconds": self.gateway.uptime_seconds._value.get(),
            },
        }
