"""
TML MQTT Gateway
Main gateway service that coordinates MQTT and Kafka components
"""

import asyncio
import signal
import time
from typing import Dict, Any
from datetime import datetime

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import TMLGatewayConfig, get_config
from .mqtt_client import TMLMQTTClient
from .kafka_producer import TMLKafkaProducer
from .metrics import TMLGatewayMetrics
from .device_manager import DeviceManager
from .api_server import APIServer


logger = structlog.get_logger(__name__)


class TMLMQTTGateway:
    """
    Production-ready MQTT Gateway for TML Platform
    
    Coordinates MQTT message reception, processing, and Kafka publishing
    with comprehensive error handling, monitoring, and device management.
    """
    
    def __init__(self, config: TMLGatewayConfig = None):
        self.config = config or get_config()
        
        # Core components
        self.mqtt_client: TMLMQTTClient = None
        self.kafka_producer: TMLKafkaProducer = None
        self.device_manager: DeviceManager = None
        self.api_server: APIServer = None
        
        # Metrics and monitoring
        self.metrics = TMLGatewayMetrics(self.config.gateway.gateway_id)
        
        # Runtime state
        self.running = False
        self.start_time = None
        self.shutdown_event = asyncio.Event()
        
        # Message processing
        self.message_queue = asyncio.Queue(maxsize=10000)
        self.processing_tasks = []
        
        self.logger = logger.bind(
            gateway_id=self.config.gateway.gateway_id,
            component="gateway"
        )
    
    async def initialize(self) -> None:
        """Initialize all gateway components"""
        try:
            self.logger.info("Initializing TML MQTT Gateway")
            
            # Initialize metrics server
            self.metrics.start_metrics_server(self.config.gateway.metrics_port)
            
            # Initialize device manager
            self.device_manager = DeviceManager(
                self.config.database,
                self.config.redis,
                self.metrics.database
            )
            await self.device_manager.initialize()
            
            # Initialize Kafka producer
            self.kafka_producer = TMLKafkaProducer(
                self.config.kafka,
                self.metrics.kafka
            )
            self.kafka_producer.initialize()
            
            # Initialize MQTT client
            self.mqtt_client = TMLMQTTClient(
                self.config.mqtt,
                self._handle_mqtt_message,
                self.metrics.mqtt
            )
            self.mqtt_client.initialize()
            
            # Initialize API server
            self.api_server = APIServer(
                self.config.gateway,
                self,
                self.metrics
            )
            
            # Set up signal handlers
            self._setup_signal_handlers()
            
            self.logger.info("Gateway initialization completed successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize gateway", error=str(e))
            raise
    
    async def start(self) -> None:
        """Start the gateway service"""
        try:
            self.logger.info("Starting TML MQTT Gateway")
            self.start_time = datetime.now()
            self.running = True
            
            # Update health status
            self.metrics.update_health_status(True)
            
            # Connect to MQTT broker
            await self.mqtt_client.connect()
            
            # Start message processing workers
            await self._start_processing_workers()
            
            # Start API server
            await self.api_server.start()
            
            # Start monitoring tasks
            await self._start_monitoring_tasks()
            
            self.logger.info("Gateway started successfully")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error("Error starting gateway", error=str(e))
            self.metrics.record_error("startup_error")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the gateway service"""
        try:
            self.logger.info("Stopping TML MQTT Gateway")
            self.running = False
            
            # Update health status
            self.metrics.update_health_status(False)
            
            # Stop API server
            if self.api_server:
                await self.api_server.stop()
            
            # Stop processing workers
            await self._stop_processing_workers()
            
            # Disconnect MQTT client
            if self.mqtt_client:
                self.mqtt_client.disconnect()
            
            # Close Kafka producer
            if self.kafka_producer:
                self.kafka_producer.close()
            
            # Close device manager
            if self.device_manager:
                await self.device_manager.close()
            
            self.logger.info("Gateway stopped successfully")
            
        except Exception as e:
            self.logger.error("Error stopping gateway", error=str(e))
    
    def _handle_mqtt_message(self, topic: str, message: Dict[str, Any]) -> None:
        """Handle incoming MQTT message"""
        try:
            # Add to processing queue
            if not self.message_queue.full():
                self.message_queue.put_nowait((topic, message))
            else:
                self.logger.warning("Message queue full, dropping message", topic=topic)
                self.metrics.record_error("queue_full")
                
        except Exception as e:
            self.logger.error("Error handling MQTT message", 
                            topic=topic, error=str(e))
            self.metrics.record_error("message_handling_error")
    
    async def _start_processing_workers(self) -> None:
        """Start message processing worker tasks"""
        num_workers = self.config.gateway.max_workers
        
        for i in range(num_workers):
            task = asyncio.create_task(
                self._message_processing_worker(f"worker-{i}")
            )
            self.processing_tasks.append(task)
        
        self.logger.info("Started message processing workers", count=num_workers)
    
    async def _stop_processing_workers(self) -> None:
        """Stop message processing worker tasks"""
        # Cancel all worker tasks
        for task in self.processing_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.processing_tasks:
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        
        self.processing_tasks.clear()
        self.logger.info("Stopped message processing workers")
    
    async def _message_processing_worker(self, worker_id: str) -> None:
        """Message processing worker coroutine"""
        worker_logger = self.logger.bind(worker_id=worker_id)
        worker_logger.info("Message processing worker started")
        
        try:
            while self.running:
                try:
                    # Get message from queue with timeout
                    topic, message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                    
                    # Process message
                    await self._process_message(topic, message)
                    
                    # Mark task as done
                    self.message_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # Timeout is normal, continue loop
                    continue
                except Exception as e:
                    worker_logger.error("Error in message processing worker", 
                                      error=str(e))
                    self.metrics.record_error("worker_error")
                    
        except asyncio.CancelledError:
            worker_logger.info("Message processing worker cancelled")
        except Exception as e:
            worker_logger.error("Message processing worker failed", error=str(e))
        finally:
            worker_logger.info("Message processing worker stopped")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _process_message(self, topic: str, message: Dict[str, Any]) -> None:
        """Process individual message"""
        start_time = time.time()
        
        try:
            # Validate message
            if not self._validate_message(message):
                self.logger.warning("Invalid message format", topic=topic)
                self.metrics.record_error("invalid_message")
                return
            
            # Extract device information
            device_info = self._extract_device_info(topic, message)
            
            # Update device registry
            if device_info:
                await self.device_manager.update_device_status(device_info)
            
            # Send to Kafka
            self.kafka_producer.process_mqtt_message(topic, message)
            
            # Update metrics
            self.metrics.record_message_processed()
            
            # Record processing time
            processing_time = time.time() - start_time
            self.metrics.mqtt.message_processing_time.observe(processing_time)
            
            self.logger.debug("Message processed successfully",
                            topic=topic,
                            processing_time=processing_time)
            
        except Exception as e:
            self.logger.error("Failed to process message",
                            topic=topic,
                            error=str(e))
            self.metrics.record_error("processing_error")
            raise
    
    def _validate_message(self, message: Dict[str, Any]) -> bool:
        """Validate message format and required fields"""
        try:
            # Check if message is a dictionary
            if not isinstance(message, dict):
                return False
            
            # Check for required fields based on message type
            mqtt_metadata = message.get('_mqtt_metadata', {})
            topic = mqtt_metadata.get('topic', '')
            
            if 'telemetry' in topic:
                # Telemetry messages should have data field
                return 'data' in message or any(
                    key for key in message.keys() 
                    if not key.startswith('_')
                )
            elif 'status' in topic:
                # Status messages should have status field
                return 'status' in message or 'health' in message
            
            # Default validation - message should have some content
            return len(message) > 1  # More than just metadata
            
        except Exception as e:
            self.logger.error("Error validating message", error=str(e))
            return False
    
    def _extract_device_info(self, topic: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract device information from topic and message"""
        try:
            # Parse topic: tml/devices/{type}/{id}/{data_type}
            parts = topic.split('/')
            
            if len(parts) >= 4 and parts[1] == 'devices':
                device_type = parts[2]
                device_id = parts[3]
                
                return {
                    'device_id': device_id,
                    'device_type': device_type,
                    'last_seen': datetime.now(),
                    'topic': topic,
                    'message_data': message
                }
            
            return None
            
        except Exception as e:
            self.logger.error("Error extracting device info", 
                            topic=topic, error=str(e))
            return None
    
    async def _start_monitoring_tasks(self) -> None:
        """Start monitoring and health check tasks"""
        # Start uptime monitoring
        asyncio.create_task(self._update_uptime())
        
        # Start health monitoring
        asyncio.create_task(self._health_monitor())
        
        self.logger.info("Monitoring tasks started")
    
    async def _update_uptime(self) -> None:
        """Update uptime metrics"""
        while self.running:
            try:
                if self.start_time:
                    uptime = (datetime.now() - self.start_time).total_seconds()
                    self.metrics.gateway.uptime_seconds.set(uptime)
                
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error updating uptime", error=str(e))
                await asyncio.sleep(10)
    
    async def _health_monitor(self) -> None:
        """Monitor gateway health"""
        while self.running:
            try:
                # Check component health
                mqtt_healthy = self.mqtt_client and self.mqtt_client.connected
                kafka_healthy = self.kafka_producer is not None
                db_healthy = await self.device_manager.health_check() if self.device_manager else False
                
                # Overall health
                overall_healthy = mqtt_healthy and kafka_healthy and db_healthy
                self.metrics.update_health_status(overall_healthy)
                
                if not overall_healthy:
                    self.logger.warning("Health check failed",
                                      mqtt=mqtt_healthy,
                                      kafka=kafka_healthy,
                                      database=db_healthy)
                
                await asyncio.sleep(self.config.gateway.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in health monitor", error=str(e))
                await asyncio.sleep(30)
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info("Received shutdown signal", signal=signum)
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive gateway status"""
        return {
            'gateway': {
                'id': self.config.gateway.gateway_id,
                'running': self.running,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            },
            'mqtt': self.mqtt_client.get_status() if self.mqtt_client else {},
            'kafka': self.kafka_producer.get_status() if self.kafka_producer else {},
            'device_manager': self.device_manager.get_status() if self.device_manager else {},
            'metrics': self.metrics.get_metrics_summary(),
            'queue_size': self.message_queue.qsize(),
            'processing_workers': len(self.processing_tasks)
        }
