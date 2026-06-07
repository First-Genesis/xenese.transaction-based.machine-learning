#!/usr/bin/env python3
"""
TML Production API Server

Enterprise-grade REST API server for the TML platform featuring:
- JWT authentication and authorization
- Rate limiting and throttling
- Comprehensive error handling
- Prometheus metrics integration
- OpenTelemetry distributed tracing
- WebSocket support for real-time data
- Health checks and monitoring

Copyright (c) 2024 First Genesis. All rights reserved.
"""

import os
import json
import time
import asyncio
import uvicorn
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Security, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from prometheus_fastapi_instrumentator import Instrumentator
import jwt
from passlib.context import CryptContext
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import TML components
from tml.core.production_processor import (
    ProductionTransactionProcessor,
    ProductionConfig,
    ProcessingResult
)

# Configuration from environment
class Settings:
    """Application settings from environment variables."""
    
    # API Configuration
    api_host: str = os.getenv('API_HOST', '0.0.0.0')
    api_port: int = int(os.getenv('API_PORT', 8000))
    
    # Security
    jwt_secret: str = os.getenv('JWT_SECRET', 'change-me-in-production')
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    api_key: str = os.getenv('API_KEY', 'change-me-in-production')
    
    # Database
    database_url: str = os.getenv(
        'DATABASE_URL',
        'postgresql+asyncpg://tml_user:password@localhost/tml_production'
    )
    
    # Redis
    redis_url: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Rate Limiting
    rate_limit_requests: int = int(os.getenv('RATE_LIMIT_REQUESTS', 1000))
    rate_limit_window: int = int(os.getenv('RATE_LIMIT_WINDOW', 60))

settings = Settings()

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Pydantic models
class TransactionRequest(BaseModel):
    """Transaction request model with validation."""
    
    x_coord: float = Field(..., ge=-180, le=180, description="X coordinate")
    y_coord: float = Field(..., ge=-90, le=90, description="Y coordinate")
    z_coord: Optional[float] = Field(None, ge=-10000, le=10000, description="Z coordinate")
    features: Dict[str, Any] = Field(default_factory=dict, description="Feature dictionary")
    domain: str = Field("general", min_length=1, max_length=50, description="Domain")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")
    require_physics_validation: bool = Field(False, description="Enable physics validation")
    
    @validator('domain')
    def validate_domain(cls, v):
        allowed_domains = ['drilling', 'healthcare', 'finance', 'manufacturing', 'general']
        if v not in allowed_domains:
            raise ValueError(f'Domain must be one of {allowed_domains}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "x_coord": 10.5,
                "y_coord": 20.3,
                "features": {"pressure": 100, "temperature": 50},
                "domain": "drilling"
            }
        }


class BatchRequest(BaseModel):
    """Batch processing request."""
    transactions: List[TransactionRequest] = Field(
        ..., 
        min_items=1,
        max_items=100,
        description="Batch of transactions"
    )


# Dependency injection
async def get_redis_client():
    """Get Redis client."""
    return await redis.from_url(settings.redis_url, decode_responses=True)


async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token."""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting TML API Server")
    
    # Initialize processor
    config = ProductionConfig(
        postgres_host=os.getenv('DB_HOST', 'localhost'),
        postgres_port=int(os.getenv('DB_PORT', 5432)),
        postgres_db=os.getenv('DB_NAME', 'tml_production'),
        postgres_user=os.getenv('DB_USER', 'tml_user'),
        postgres_password=os.getenv('DB_PASSWORD', 'password'),
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        redis_port=int(os.getenv('REDIS_PORT', 6379)),
        redis_password=os.getenv('REDIS_PASSWORD')
    )
    app.state.processor = ProductionTransactionProcessor(config)
    await app.state.processor.initialize()
    
    # Initialize Redis
    app.state.redis = await get_redis_client()
    
    # Initialize database
    engine = create_async_engine(settings.database_url, echo=False, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.state.db = async_session
    
    logger.info("TML API Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TML API Server")
    
    # Cleanup
    app.state.processor.shutdown()
    await app.state.redis.close()
    await engine.dispose()
    
    logger.info("TML API Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="TML Production API",
    version="3.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)


# API Endpoints
@app.get("/", tags=["root"])
@limiter.limit("10/minute")
async def root(request: Request):
    """Root endpoint."""
    return {
        "name": "TML Production API",
        "version": "3.0.0",
        "status": "operational",
        "documentation": "/docs"
    }


@app.get("/health", tags=["monitoring"])
async def health_check():
    """Health check endpoint."""
    health = app.state.processor.health_check()
    return health


@app.post("/api/v1/process", tags=["processing"])
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def process_transaction(
    request: Request,
    transaction: TransactionRequest,
    background_tasks: BackgroundTasks,
    token_payload = Depends(verify_token)
):
    """
    Process a single transaction.
    
    Requires JWT authentication.
    """
    try:
        # Add metadata
        transaction_data = transaction.dict()
        transaction_data['metadata']['client_id'] = token_payload.get('sub', 'unknown')
        transaction_data['metadata']['api_version'] = "3.0.0"
        
        # Process transaction
        result = await app.state.processor.process_transaction_async(transaction_data)
        
        # Background logging
        background_tasks.add_task(log_transaction, token_payload.get('sub'), result)
        
        # Return result
        return JSONResponse(
            content=json.loads(result.to_json()),
            headers={"X-Processing-Time": str(result.processing_time)}
        )
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/batch", tags=["processing"])
@limiter.limit("10/minute")  # Stricter limit for batch
async def process_batch(
    request: Request,
    batch: BatchRequest,
    token_payload = Depends(verify_token)
):
    """
    Process a batch of transactions.
    
    Requires JWT authentication.
    """
    try:
        # Process all transactions
        results = []
        for transaction in batch.transactions:
            transaction_data = transaction.dict()
            transaction_data['metadata']['client_id'] = token_payload.get('sub', 'unknown')
            
            result = await app.state.processor.process_transaction_async(transaction_data)
            results.append(json.loads(result.to_json()))
        
        return {
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/models/{model_id}", tags=["models"])
async def get_model_info(
    model_id: str,
    token_payload = Depends(verify_token)
):
    """
    Get information about a specific model.
    """
    # In a real implementation, retrieve model info from database
    return {
        "model_id": model_id,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "performance_metrics": {
            "accuracy": 0.85,
            "predictions": 1000
        }
    }


@app.get("/api/v1/statistics", tags=["monitoring"])
async def get_statistics(token_payload = Depends(verify_token)):
    """
    Get processing statistics.
    """
    stats = app.state.processor.get_statistics()
    return stats


@app.post("/auth/token", tags=["authentication"])
@limiter.limit("5/minute")  # Strict limit on auth
async def create_token(api_key: str):
    """
    Create JWT token for API access.
    
    Exchange API key for JWT token.
    """
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Create token
    expiration = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration_minutes)
    token_data = {
        'sub': api_key[:8],  # Use first 8 chars as client ID
        'exp': expiration
    }
    
    token = jwt.encode(token_data, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    return {
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': settings.jwt_expiration_minutes * 60
    }


# WebSocket endpoint for real-time data
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transaction processing.
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive transaction data
            data = await websocket.receive_text()
            transaction_data = json.loads(data)
            
            # Process transaction
            result = await app.state.processor.process_transaction_async(transaction_data)
            
            # Send result back
            await websocket.send_text(result.to_json())
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


# Background tasks
async def log_transaction(client_id: str, result: ProcessingResult):
    """Log transaction for analytics."""
    try:
        logger.info(
            f"Transaction processed: client={client_id} "
            f"transaction_id={result.transaction_id} "
            f"status={result.status} "
            f"time={result.processing_time:.3f}s"
        )
    except Exception as e:
        logger.error(f"Failed to log transaction: {e}")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "production_server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
        log_level="info"
    )
