"""
TML MQTT Gateway API Server
FastAPI-based REST API for gateway management and monitoring
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
import structlog

from .config import GatewayConfig
from .metrics import TMLGatewayMetrics


logger = structlog.get_logger(__name__)


# Pydantic models for API requests/responses
class DeviceRegistration(BaseModel):
    device_id: str
    device_type: str
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceStatus(BaseModel):
    device_id: str
    status: str
    last_seen: datetime
    metadata: Optional[Dict[str, Any]] = None


class GatewayStatus(BaseModel):
    gateway_id: str
    status: str
    uptime_seconds: float
    mqtt_connected: bool
    kafka_connected: bool
    database_connected: bool
    message_queue_size: int
    processing_workers: int


class MessagePublish(BaseModel):
    topic: str
    payload: Dict[str, Any]
    qos: Optional[int] = 1


security = HTTPBearer(auto_error=False)


class APIServer:
    """
    FastAPI-based API server for TML MQTT Gateway
    
    Provides REST endpoints for:
    - Gateway status and health monitoring
    - Device management and registration
    - Message publishing and monitoring
    - Metrics and diagnostics
    """
    
    def __init__(
        self,
        config: GatewayConfig,
        gateway,  # TMLMQTTGateway instance
        metrics: TMLGatewayMetrics
    ):
        self.config = config
        self.gateway = gateway
        self.metrics = metrics
        
        # Create FastAPI app
        self.app = FastAPI(
            title="TML MQTT Gateway API",
            description="REST API for TML MQTT Gateway management and monitoring",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Server instance
        self.server = None
        
        self.logger = logger.bind(component="api_server")
    
    def _setup_routes(self) -> None:
        """Setup API routes"""
        
        # Health and status endpoints
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @self.app.get("/status", response_model=GatewayStatus)
        async def get_gateway_status():
            """Get comprehensive gateway status"""
            status = self.gateway.get_status()
            
            return GatewayStatus(
                gateway_id=status['gateway']['id'],
                status="running" if status['gateway']['running'] else "stopped",
                uptime_seconds=status['gateway']['uptime_seconds'],
                mqtt_connected=status['mqtt'].get('connected', False),
                kafka_connected=bool(status['kafka']),
                database_connected=bool(status['device_manager']),
                message_queue_size=status['queue_size'],
                processing_workers=status['processing_workers']
            )
        
        @self.app.get("/metrics")
        async def get_metrics():
            """Get gateway metrics summary"""
            return self.metrics.get_metrics_summary()
        
        # Device management endpoints
        @self.app.post("/devices/register")
        async def register_device(
            device: DeviceRegistration,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Register a new device"""
            if not await self._authenticate(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            try:
                device_info = device.dict()
                success = await self.gateway.device_manager.register_device(device_info)
                
                if success:
                    return {"message": "Device registered successfully", "device_id": device.device_id}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to register device"
                    )
                    
            except Exception as e:
                self.logger.error("Error registering device", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        @self.app.get("/devices/{device_id}")
        async def get_device(device_id: str):
            """Get device information"""
            try:
                device = await self.gateway.device_manager.get_device(device_id)
                
                if device:
                    return device
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Device not found"
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error getting device", device_id=device_id, error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        @self.app.get("/devices")
        async def list_devices(
            device_type: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
        ):
            """List devices with optional filtering"""
            try:
                devices = await self.gateway.device_manager.list_devices(
                    device_type=device_type,
                    status=status,
                    limit=limit,
                    offset=offset
                )
                
                return {
                    "devices": devices,
                    "count": len(devices),
                    "limit": limit,
                    "offset": offset
                }
                
            except Exception as e:
                self.logger.error("Error listing devices", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        @self.app.post("/devices/{device_id}/status")
        async def update_device_status(
            device_id: str,
            status_update: DeviceStatus,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Update device status"""
            if not await self._authenticate(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            try:
                device_info = status_update.dict()
                await self.gateway.device_manager.update_device_status(device_info)
                
                return {"message": "Device status updated successfully"}
                
            except Exception as e:
                self.logger.error("Error updating device status", 
                                device_id=device_id, error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        # Message publishing endpoints
        @self.app.post("/messages/publish")
        async def publish_message(
            message: MessagePublish,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Publish message to MQTT topic"""
            if not await self._authenticate(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            try:
                if self.gateway.mqtt_client and self.gateway.mqtt_client.connected:
                    self.gateway.mqtt_client.publish(
                        topic=message.topic,
                        payload=message.payload,
                        qos=message.qos
                    )
                    
                    return {"message": "Message published successfully"}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="MQTT client not connected"
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error publishing message", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        # Gateway management endpoints
        @self.app.post("/gateway/shutdown")
        async def shutdown_gateway(
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Shutdown the gateway"""
            if not await self._authenticate(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            try:
                # Trigger shutdown
                self.gateway.shutdown_event.set()
                
                return {"message": "Gateway shutdown initiated"}
                
            except Exception as e:
                self.logger.error("Error shutting down gateway", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
        
        # Diagnostic endpoints
        @self.app.get("/diagnostics/mqtt")
        async def get_mqtt_diagnostics():
            """Get MQTT client diagnostics"""
            if self.gateway.mqtt_client:
                return self.gateway.mqtt_client.get_status()
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="MQTT client not initialized"
                )
        
        @self.app.get("/diagnostics/kafka")
        async def get_kafka_diagnostics():
            """Get Kafka producer diagnostics"""
            if self.gateway.kafka_producer:
                return self.gateway.kafka_producer.get_status()
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Kafka producer not initialized"
                )
        
        @self.app.get("/diagnostics/database")
        async def get_database_diagnostics():
            """Get database diagnostics"""
            if self.gateway.device_manager:
                return self.gateway.device_manager.get_status()
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Device manager not initialized"
                )
        
        # Configuration endpoints
        @self.app.get("/config")
        async def get_configuration(
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Get gateway configuration (sensitive data masked)"""
            if not await self._authenticate(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            # Return sanitized configuration
            config_dict = self.config.dict()
            
            # Mask sensitive information
            if 'password' in config_dict:
                config_dict['password'] = '***'
            if 'api_key' in config_dict:
                config_dict['api_key'] = '***'
            
            return config_dict
    
    async def _authenticate(self, credentials: HTTPAuthorizationCredentials) -> bool:
        """Authenticate API request"""
        if not self.config.enable_auth:
            return True
        
        if not credentials:
            return False
        
        if not self.config.api_key:
            return True  # No API key configured, allow access
        
        return credentials.credentials == self.config.api_key
    
    async def start(self) -> None:
        """Start the API server"""
        try:
            config = uvicorn.Config(
                app=self.app,
                host=self.config.api_host,
                port=self.config.api_port,
                log_level="info",
                access_log=True
            )
            
            self.server = uvicorn.Server(config)
            
            # Start server in background task
            asyncio.create_task(self.server.serve())
            
            self.logger.info("API server started",
                           host=self.config.api_host,
                           port=self.config.api_port)
            
        except Exception as e:
            self.logger.error("Failed to start API server", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the API server"""
        try:
            if self.server:
                self.server.should_exit = True
                
            self.logger.info("API server stopped")
            
        except Exception as e:
            self.logger.error("Error stopping API server", error=str(e))
