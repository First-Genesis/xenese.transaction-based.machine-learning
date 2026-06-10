"""
TML Kafka Producer
Production-ready Kafka producer for MQTT to Kafka message bridge
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import KafkaConfig
from .metrics import KafkaMetrics


logger = structlog.get_logger(__name__)


class TMLKafkaProducer:
    """
    Production-ready Kafka producer for TML Gateway
    
    Features:
    - Automatic retry with exponential backoff
    - Dead letter queue for failed messages
    - Batch processing for high throughput
    - Comprehensive error handling and logging
    - Metrics collection
    """
    
    def __init__(self, config: KafkaConfig, metrics: KafkaMetrics):
        self.config = config
        self.metrics = metrics
        
        # Producer instance
        self.producer: Optional[KafkaProducer] = None
        
        # Message batching
        self.message_batch = []
        self.batch_size = 100
        self.last_flush_time = time.time()
        self.flush_interval = 1.0  # seconds
        
        # Statistics
        self.messages_sent = 0
        self.messages_failed = 0
        self.bytes_sent = 0
        
        # Topic mapping
        self.topic_mapping = {
            'telemetry': config.telemetry_topic,
            'status': config.status_topic,
            'alerts': config.alerts_topic,
            'dead_letter': config.dead_letter_topic
        }
        
        self.logger = logger.bind(component="kafka_producer")
    
    def initialize(self) -> None:
        """Initialize Kafka producer"""
        try:
            producer_config = {
                'bootstrap_servers': self.config.bootstrap_servers.split(','),
                'acks': self.config.acks,
                'retries': self.config.retries,
                'batch_size': self.config.batch_size,
                'linger_ms': self.config.linger_ms,
                'compression_type': self.config.compression_type,
                'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
                'key_serializer': lambda k: k.encode('utf-8') if k else None,
                'max_in_flight_requests_per_connection': 5,
                'enable_idempotence': True,
                'request_timeout_ms': 30000,
                'delivery_timeout_ms': 120000
            }
            
            self.producer = KafkaProducer(**producer_config)
            
            self.logger.info("Kafka producer initialized",
                           bootstrap_servers=self.config.bootstrap_servers,
                           acks=self.config.acks,
                           compression=self.config.compression_type)
            
        except Exception as e:
            self.logger.error("Failed to initialize Kafka producer", error=str(e))
            raise
    
    def close(self) -> None:
        """Close Kafka producer"""
        try:
            if self.producer:
                # Flush any remaining messages
                self.flush()
                
                # Close producer
                self.producer.close(timeout=30)
                
            self.logger.info("Kafka producer closed")
            
        except Exception as e:
            self.logger.error("Error closing Kafka producer", error=str(e))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def send_message(
        self,
        topic_type: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Send message to Kafka topic
        
        Args:
            topic_type: Type of topic (telemetry, status, alerts)
            message: Message payload
            key: Optional message key for partitioning
            headers: Optional message headers
        """
        try:
            # Get topic name
            topic = self.topic_mapping.get(topic_type)
            if not topic:
                raise ValueError(f"Unknown topic type: {topic_type}")
            
            # Add metadata
            enriched_message = self._enrich_message(message)
            
            # Prepare headers
            kafka_headers = []
            if headers:
                kafka_headers = [(k, v.encode('utf-8')) for k, v in headers.items()]
            
            # Add standard headers
            kafka_headers.extend([
                ('gateway_id', self.config.topic_prefix.encode('utf-8')),
                ('message_type', topic_type.encode('utf-8')),
                ('timestamp', str(int(time.time())).encode('utf-8'))
            ])
            
            # Send message
            future = self.producer.send(
                topic=topic,
                value=enriched_message,
                key=key,
                headers=kafka_headers
            )
            
            # Add callback for success/failure handling
            future.add_callback(self._on_send_success, topic, enriched_message)
            future.add_errback(self._on_send_error, topic, enriched_message)
            
            self.logger.debug("Message sent to Kafka",
                            topic=topic,
                            key=key,
                            message_size=len(json.dumps(enriched_message)))
            
        except Exception as e:
            self.logger.error("Failed to send message to Kafka",
                            topic_type=topic_type,
                            error=str(e))
            
            # Send to dead letter queue
            self._send_to_dead_letter_queue(message, str(e))
            raise
    
    def send_batch(self, messages: list) -> None:
        """Send batch of messages"""
        try:
            for msg_data in messages:
                self.send_message(**msg_data)
            
            # Flush to ensure delivery
            self.flush()
            
            self.logger.info("Sent message batch", count=len(messages))
            
        except Exception as e:
            self.logger.error("Failed to send message batch", error=str(e))
            raise
    
    def flush(self) -> None:
        """Flush producer to ensure all messages are sent"""
        try:
            if self.producer:
                self.producer.flush(timeout=30)
                self.last_flush_time = time.time()
                
                self.logger.debug("Kafka producer flushed")
                
        except KafkaTimeoutError:
            self.logger.error("Kafka flush timeout")
            self.metrics.flush_timeouts.inc()
        except Exception as e:
            self.logger.error("Error flushing Kafka producer", error=str(e))
    
    def _enrich_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich message with additional metadata"""
        enriched = message.copy()
        
        # Add gateway metadata
        enriched['_kafka_metadata'] = {
            'producer_timestamp': datetime.now().isoformat(),
            'gateway_id': self.config.topic_prefix,
            'producer_version': '1.0.0'
        }
        
        return enriched
    
    def _on_send_success(self, topic: str, message: Dict[str, Any], record_metadata) -> None:
        """Handle successful message send"""
        self.messages_sent += 1
        self.bytes_sent += len(json.dumps(message))
        
        # Update metrics
        self.metrics.messages_sent.inc()
        self.metrics.bytes_sent.inc(len(json.dumps(message)))
        
        self.logger.debug("Message sent successfully",
                        topic=topic,
                        partition=record_metadata.partition,
                        offset=record_metadata.offset)
    
    def _on_send_error(self, topic: str, message: Dict[str, Any], exception) -> None:
        """Handle failed message send"""
        self.messages_failed += 1
        
        # Update metrics
        self.metrics.send_errors.inc()
        
        self.logger.error("Failed to send message",
                        topic=topic,
                        error=str(exception))
        
        # Send to dead letter queue
        self._send_to_dead_letter_queue(message, str(exception))
    
    def _send_to_dead_letter_queue(self, message: Dict[str, Any], error: str) -> None:
        """Send failed message to dead letter queue"""
        try:
            dead_letter_message = {
                'original_message': message,
                'error': error,
                'timestamp': datetime.now().isoformat(),
                'gateway_id': self.config.topic_prefix
            }
            
            # Send to dead letter topic (without retry to avoid infinite loop)
            future = self.producer.send(
                topic=self.config.dead_letter_topic,
                value=dead_letter_message
            )
            
            future.add_callback(lambda metadata: self.logger.info(
                "Message sent to dead letter queue",
                partition=metadata.partition,
                offset=metadata.offset
            ))
            
            # Update metrics
            self.metrics.dead_letter_messages.inc()
            
        except Exception as e:
            self.logger.error("Failed to send message to dead letter queue", error=str(e))
    
    def get_topic_for_mqtt_topic(self, mqtt_topic: str) -> str:
        """Map MQTT topic to Kafka topic"""
        # Parse MQTT topic structure: tml/devices/{type}/{id}/{data_type}
        parts = mqtt_topic.split('/')
        
        if len(parts) >= 5:
            data_type = parts[-1]  # telemetry, status, etc.
            
            if data_type == 'telemetry':
                return 'telemetry'
            elif data_type == 'status':
                return 'status'
            elif 'alert' in data_type.lower():
                return 'alerts'
        
        # Default to telemetry
        return 'telemetry'
    
    def process_mqtt_message(self, mqtt_topic: str, message: Dict[str, Any]) -> None:
        """Process MQTT message and send to appropriate Kafka topic"""
        try:
            # Determine Kafka topic
            topic_type = self.get_topic_for_mqtt_topic(mqtt_topic)
            
            # Extract device information from MQTT topic
            parts = mqtt_topic.split('/')
            if len(parts) >= 4:
                device_type = parts[2] if len(parts) > 2 else 'unknown'
                device_id = parts[3] if len(parts) > 3 else 'unknown'
                
                # Use device_id as message key for partitioning
                key = f"{device_type}:{device_id}"
            else:
                key = None
            
            # Add MQTT topic information
            message['_source_topic'] = mqtt_topic
            
            # Send to Kafka
            self.send_message(
                topic_type=topic_type,
                message=message,
                key=key,
                headers={
                    'source_protocol': 'mqtt',
                    'mqtt_topic': mqtt_topic
                }
            )
            
        except Exception as e:
            self.logger.error("Error processing MQTT message",
                            mqtt_topic=mqtt_topic,
                            error=str(e))
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get producer status information"""
        return {
            'messages_sent': self.messages_sent,
            'messages_failed': self.messages_failed,
            'bytes_sent': self.bytes_sent,
            'batch_size': self.batch_size,
            'last_flush_time': self.last_flush_time,
            'topic_mapping': self.topic_mapping,
            'bootstrap_servers': self.config.bootstrap_servers
        }
