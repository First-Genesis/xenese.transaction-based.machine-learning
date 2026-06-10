"""
TML MQTT Client
Production-ready MQTT client with connection management and error handling
"""

import asyncio
import json
import ssl
import time
from typing import Dict, Any, Callable, Optional
from datetime import datetime

import paho.mqtt.client as mqtt
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import MQTTConfig
from .metrics import MQTTMetrics


logger = structlog.get_logger(__name__)


class TMLMQTTClient:
    """
    Production-ready MQTT client for TML Gateway
    
    Features:
    - Automatic reconnection with exponential backoff
    - Message queuing during disconnection
    - Comprehensive error handling and logging
    - Metrics collection
    - TLS support
    """
    
    def __init__(
        self,
        config: MQTTConfig,
        message_handler: Callable[[str, Dict[str, Any]], None],
        metrics: MQTTMetrics
    ):
        self.config = config
        self.message_handler = message_handler
        self.metrics = metrics
        
        # Connection state
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.connection_attempts = 0
        self.last_connection_time = None
        
        # Message queue for offline messages
        self.message_queue = []
        self.max_queue_size = 10000
        
        # Statistics
        self.messages_received = 0
        self.messages_processed = 0
        self.connection_count = 0
        
        self.logger = logger.bind(client_id=config.client_id)
    
    def initialize(self) -> None:
        """Initialize MQTT client"""
        try:
            # Create MQTT client
            self.client = mqtt.Client(
                client_id=self.config.client_id,
                clean_session=True,
                protocol=mqtt.MQTTv311
            )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_subscribe = self._on_subscribe
            self.client.on_log = self._on_log
            
            # Configure authentication
            if self.config.username and self.config.password:
                self.client.username_pw_set(
                    self.config.username,
                    self.config.password
                )
            
            # Configure TLS
            if self.config.use_tls:
                self._configure_tls()
            
            # Set keep alive
            self.client.keepalive = self.config.keepalive
            
            self.logger.info("MQTT client initialized", 
                           host=self.config.host,
                           port=self.config.port,
                           tls=self.config.use_tls)
            
        except Exception as e:
            self.logger.error("Failed to initialize MQTT client", error=str(e))
            raise
    
    def _configure_tls(self) -> None:
        """Configure TLS/SSL settings"""
        try:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            
            # Load CA certificate
            if self.config.ca_cert_path:
                context.load_verify_locations(self.config.ca_cert_path)
            
            # Load client certificate and key
            if self.config.cert_path and self.config.key_path:
                context.load_cert_chain(self.config.cert_path, self.config.key_path)
            
            # Set TLS version
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            self.client.tls_set_context(context)
            
            self.logger.info("TLS configured successfully")
            
        except Exception as e:
            self.logger.error("Failed to configure TLS", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def connect(self) -> None:
        """Connect to MQTT broker with retry logic"""
        try:
            self.connection_attempts += 1
            
            self.logger.info("Attempting to connect to MQTT broker",
                           attempt=self.connection_attempts,
                           host=self.config.host,
                           port=self.config.port)
            
            # Connect to broker
            result = self.client.connect(
                self.config.host,
                self.config.port,
                self.config.keepalive
            )
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"MQTT connection failed with code: {result}")
            
            # Start network loop
            self.client.loop_start()
            
            # Wait for connection confirmation
            await self._wait_for_connection()
            
            self.logger.info("Successfully connected to MQTT broker")
            
        except Exception as e:
            self.logger.error("Failed to connect to MQTT broker", error=str(e))
            self.metrics.connection_failures.inc()
            raise
    
    async def _wait_for_connection(self, timeout: int = 30) -> None:
        """Wait for connection to be established"""
        start_time = time.time()
        
        while not self.connected and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
        
        if not self.connected:
            raise TimeoutError("Connection timeout")
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker"""
        try:
            if self.client and self.connected:
                self.client.loop_stop()
                self.client.disconnect()
                
            self.logger.info("Disconnected from MQTT broker")
            
        except Exception as e:
            self.logger.error("Error during disconnect", error=str(e))
    
    def subscribe_to_topics(self) -> None:
        """Subscribe to configured topics"""
        try:
            for topic in self.config.subscribe_topics:
                result, mid = self.client.subscribe(topic, self.config.qos)
                
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.info("Subscribed to topic", topic=topic, qos=self.config.qos)
                else:
                    self.logger.error("Failed to subscribe to topic", 
                                    topic=topic, result=result)
                    
        except Exception as e:
            self.logger.error("Error subscribing to topics", error=str(e))
    
    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle connection event"""
        if rc == 0:
            self.connected = True
            self.connection_count += 1
            self.last_connection_time = datetime.now()
            
            self.logger.info("Connected to MQTT broker", 
                           result_code=rc,
                           connection_count=self.connection_count)
            
            # Subscribe to topics
            self.subscribe_to_topics()
            
            # Process queued messages
            self._process_message_queue()
            
            # Update metrics
            self.metrics.connections_total.inc()
            self.metrics.connected_clients.set(1)
            
        else:
            self.connected = False
            self.logger.error("Failed to connect to MQTT broker", result_code=rc)
            self.metrics.connection_failures.inc()
    
    def _on_disconnect(self, client, userdata, rc) -> None:
        """Handle disconnection event"""
        self.connected = False
        
        if rc != 0:
            self.logger.warning("Unexpected disconnection from MQTT broker", 
                              result_code=rc)
        else:
            self.logger.info("Disconnected from MQTT broker")
        
        # Update metrics
        self.metrics.connected_clients.set(0)
        self.metrics.disconnections_total.inc()
    
    def _on_message(self, client, userdata, msg) -> None:
        """Handle incoming message"""
        try:
            self.messages_received += 1
            
            # Decode message
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            self.logger.debug("Received MQTT message",
                            topic=topic,
                            payload_size=len(payload),
                            qos=msg.qos)
            
            # Parse JSON payload
            try:
                message_data = json.loads(payload)
            except json.JSONDecodeError as e:
                self.logger.error("Failed to parse JSON message",
                                topic=topic,
                                payload=payload[:100],
                                error=str(e))
                self.metrics.parse_errors.inc()
                return
            
            # Add metadata
            message_data['_mqtt_metadata'] = {
                'topic': topic,
                'qos': msg.qos,
                'retain': msg.retain,
                'timestamp': datetime.now().isoformat(),
                'gateway_id': self.config.client_id
            }
            
            # Process message
            self.message_handler(topic, message_data)
            self.messages_processed += 1
            
            # Update metrics
            self.metrics.messages_received.inc()
            self.metrics.messages_processed.inc()
            
        except Exception as e:
            self.logger.error("Error processing MQTT message",
                            topic=msg.topic,
                            error=str(e))
            self.metrics.processing_errors.inc()
    
    def _on_subscribe(self, client, userdata, mid, granted_qos) -> None:
        """Handle subscription confirmation"""
        self.logger.info("Subscription confirmed", 
                        message_id=mid,
                        granted_qos=granted_qos)
    
    def _on_log(self, client, userdata, level, buf) -> None:
        """Handle MQTT client logs"""
        if level == mqtt.MQTT_LOG_ERR:
            self.logger.error("MQTT client error", message=buf)
        elif level == mqtt.MQTT_LOG_WARNING:
            self.logger.warning("MQTT client warning", message=buf)
        elif level == mqtt.MQTT_LOG_DEBUG:
            self.logger.debug("MQTT client debug", message=buf)
    
    def _process_message_queue(self) -> None:
        """Process queued messages after reconnection"""
        if not self.message_queue:
            return
        
        self.logger.info("Processing queued messages", count=len(self.message_queue))
        
        for topic, message_data in self.message_queue:
            try:
                self.message_handler(topic, message_data)
                self.messages_processed += 1
            except Exception as e:
                self.logger.error("Error processing queued message",
                                topic=topic,
                                error=str(e))
        
        # Clear queue
        self.message_queue.clear()
    
    def publish(self, topic: str, payload: Dict[str, Any], qos: int = None) -> None:
        """Publish message to MQTT topic"""
        try:
            qos = qos or self.config.qos
            payload_json = json.dumps(payload)
            
            if self.connected:
                result = self.client.publish(topic, payload_json, qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.debug("Published message", topic=topic, qos=qos)
                    self.metrics.messages_published.inc()
                else:
                    self.logger.error("Failed to publish message", 
                                    topic=topic, result=result.rc)
            else:
                # Queue message for later delivery
                if len(self.message_queue) < self.max_queue_size:
                    self.message_queue.append((topic, payload))
                    self.logger.debug("Queued message for later delivery", topic=topic)
                else:
                    self.logger.warning("Message queue full, dropping message", topic=topic)
                    
        except Exception as e:
            self.logger.error("Error publishing message", topic=topic, error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status information"""
        return {
            'connected': self.connected,
            'connection_count': self.connection_count,
            'last_connection_time': self.last_connection_time.isoformat() if self.last_connection_time else None,
            'messages_received': self.messages_received,
            'messages_processed': self.messages_processed,
            'queued_messages': len(self.message_queue),
            'subscribed_topics': self.config.subscribe_topics,
            'client_id': self.config.client_id,
            'broker_host': self.config.host,
            'broker_port': self.config.port
        }
