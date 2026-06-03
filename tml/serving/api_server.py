"""FastAPI server for TML model serving."""

import time
import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from loguru import logger

from tml.core.config import config
from tml.core.registry import ModelRegistry
from tml.learning.online_learner import learning_engine, LearningResult
from tml.ingestion.kafka_producer import TransactionEvent, TransactionProducer
from tml.monitoring.metrics import MetricsCollector


# Pydantic models for API
class PredictionRequest(BaseModel):
    """Request model for predictions."""
    features: Dict[str, Any] = Field(..., description="Feature dictionary")
    model_id: Optional[str] = Field(None, description="Specific model ID to use")
    user_id: Optional[str] = Field(None, description="User ID for model selection")
    session_id: Optional[str] = Field(None, description="Session ID for model selection")
    return_probabilities: bool = Field(False, description="Return prediction probabilities")
    
    class Config:
        schema_extra = {
            "example": {
                "features": {
                    "amount": 150.0,
                    "category": "electronics",
                    "hour_of_day": 14,
                    "device_type": "mobile"
                },
                "user_id": "user_12345",
                "return_probabilities": True
            }
        }


class PredictionResponse(BaseModel):
    """Response model for predictions."""
    prediction: Any = Field(..., description="Model prediction")
    model_id: str = Field(..., description="ID of model used")
    confidence: Optional[float] = Field(None, description="Prediction confidence")
    probabilities: Optional[Dict[str, float]] = Field(None, description="Class probabilities")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class LearningRequest(BaseModel):
    """Request model for online learning."""
    features: Dict[str, Any] = Field(..., description="Feature dictionary")
    target: Any = Field(..., description="Target value for learning")
    model_id: Optional[str] = Field(None, description="Specific model ID to update")
    user_id: Optional[str] = Field(None, description="User ID for model selection")
    session_id: Optional[str] = Field(None, description="Session ID for model selection")
    
    class Config:
        schema_extra = {
            "example": {
                "features": {
                    "amount": 150.0,
                    "category": "electronics",
                    "hour_of_day": 14,
                    "device_type": "mobile"
                },
                "target": True,
                "user_id": "user_12345"
            }
        }


class LearningResponse(BaseModel):
    """Response model for learning operations."""
    success: bool = Field(..., description="Whether learning was successful")
    model_id: str = Field(..., description="ID of model updated")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BatchPredictionRequest(BaseModel):
    """Request model for batch predictions."""
    requests: List[PredictionRequest] = Field(..., description="List of prediction requests")
    
    class Config:
        schema_extra = {
            "example": {
                "requests": [
                    {
                        "features": {"amount": 100.0, "category": "books"},
                        "user_id": "user_1"
                    },
                    {
                        "features": {"amount": 200.0, "category": "electronics"},
                        "user_id": "user_2"
                    }
                ]
            }
        }


class BatchPredictionResponse(BaseModel):
    """Response model for batch predictions."""
    predictions: List[PredictionResponse] = Field(..., description="List of predictions")
    total_processing_time_ms: float = Field(..., description="Total processing time")


class ModelStatsResponse(BaseModel):
    """Response model for model statistics."""
    model_id: str
    total_predictions: int
    total_updates: int
    accuracy: float
    drift_score: float
    last_updated: float
    creation_time: float


# Global instances
model_registry = ModelRegistry()
metrics_collector = MetricsCollector()
kafka_producer = TransactionProducer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting TML API Server...")
    yield
    # Shutdown
    logger.info("Shutting down TML API Server...")
    kafka_producer.close()


# Create FastAPI app
app = FastAPI(
    title="TML Platform API",
    description="Transaction-based Machine Learning Platform API",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for metrics collection
async def collect_metrics():
    """Dependency to collect request metrics."""
    start_time = time.time()
    yield
    processing_time = (time.time() - start_time) * 1000
    metrics_collector.record_request_duration(processing_time)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TML Platform API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "learning_engine": "running",
            "model_registry": "running",
            "kafka_producer": "running"
        }
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(collect_metrics)
):
    """Make a prediction using the appropriate model."""
    start_time = time.time()
    
    try:
        # Determine model ID
        model_id = request.model_id
        if not model_id:
            if request.user_id:
                model_id = f"user_{request.user_id}"
            elif request.session_id:
                model_id = f"session_{request.session_id}"
            else:
                model_id = "default_model"
        
        # Get or create learner
        learner = learning_engine.get_learner(model_id)
        if not learner:
            learner = learning_engine.create_learner(model_id)
        
        # Make prediction
        prediction = learner.predict(request.features)
        
        # Get probabilities if requested
        probabilities = None
        confidence = None
        if request.return_probabilities:
            probabilities = learner.predict_proba(request.features)
            if probabilities:
                confidence = max(probabilities.values())
        
        processing_time = (time.time() - start_time) * 1000
        
        # Record metrics in background
        background_tasks.add_task(
            metrics_collector.record_prediction,
            model_id=model_id,
            processing_time_ms=processing_time
        )
        
        return PredictionResponse(
            prediction=prediction,
            model_id=model_id,
            confidence=confidence,
            probabilities=probabilities,
            processing_time_ms=processing_time,
            metadata={
                "algorithm": type(learner).__name__,
                "features_count": len(request.features)
            }
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/learn", response_model=LearningResponse)
async def learn(
    request: LearningRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(collect_metrics)
):
    """Update a model with new training data."""
    start_time = time.time()
    
    try:
        # Determine model ID
        model_id = request.model_id
        if not model_id:
            if request.user_id:
                model_id = f"user_{request.user_id}"
            elif request.session_id:
                model_id = f"session_{request.session_id}"
            else:
                model_id = "default_model"
        
        # Update model
        success = learning_engine.learn(model_id, request.features, request.target)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Send to Kafka for further processing
        if success:
            transaction_event = TransactionEvent(
                transaction_id=f"learn_{int(time.time() * 1000)}",
                user_id=request.user_id,
                session_id=request.session_id,
                timestamp=time.time(),
                event_type="learning_update",
                features=request.features,
                target=request.target
            )
            background_tasks.add_task(kafka_producer.send_transaction, transaction_event)
        
        # Record metrics in background
        background_tasks.add_task(
            metrics_collector.record_learning_update,
            model_id=model_id,
            success=success,
            processing_time_ms=processing_time
        )
        
        return LearningResponse(
            success=success,
            model_id=model_id,
            processing_time_ms=processing_time,
            metadata={
                "features_count": len(request.features),
                "target_type": type(request.target).__name__
            }
        )
        
    except Exception as e:
        logger.error(f"Learning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def batch_predict(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(collect_metrics)
):
    """Make batch predictions."""
    start_time = time.time()
    
    try:
        predictions = []
        
        # Process requests concurrently
        tasks = []
        for pred_request in request.requests:
            task = asyncio.create_task(_process_single_prediction(pred_request))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch prediction error for request {i}: {result}")
                # Add error response
                predictions.append(PredictionResponse(
                    prediction=None,
                    model_id="error",
                    processing_time_ms=0,
                    metadata={"error": str(result)}
                ))
            else:
                predictions.append(result)
        
        total_processing_time = (time.time() - start_time) * 1000
        
        # Record batch metrics
        background_tasks.add_task(
            metrics_collector.record_batch_prediction,
            batch_size=len(request.requests),
            processing_time_ms=total_processing_time
        )
        
        return BatchPredictionResponse(
            predictions=predictions,
            total_processing_time_ms=total_processing_time
        )
        
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _process_single_prediction(request: PredictionRequest) -> PredictionResponse:
    """Process a single prediction request."""
    start_time = time.time()
    
    # Determine model ID
    model_id = request.model_id
    if not model_id:
        if request.user_id:
            model_id = f"user_{request.user_id}"
        elif request.session_id:
            model_id = f"session_{request.session_id}"
        else:
            model_id = "default_model"
    
    # Get or create learner
    learner = learning_engine.get_learner(model_id)
    if not learner:
        learner = learning_engine.create_learner(model_id)
    
    # Make prediction
    prediction = learner.predict(request.features)
    
    # Get probabilities if requested
    probabilities = None
    confidence = None
    if request.return_probabilities:
        probabilities = learner.predict_proba(request.features)
        if probabilities:
            confidence = max(probabilities.values())
    
    processing_time = (time.time() - start_time) * 1000
    
    return PredictionResponse(
        prediction=prediction,
        model_id=model_id,
        confidence=confidence,
        probabilities=probabilities,
        processing_time_ms=processing_time,
        metadata={
            "algorithm": type(learner).__name__,
            "features_count": len(request.features)
        }
    )


@app.get("/models", response_model=List[str])
async def list_models():
    """List all available models."""
    try:
        model_ids = await model_registry.list_models()
        return model_ids
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models/{model_id}/stats", response_model=ModelStatsResponse)
async def get_model_stats(model_id: str):
    """Get statistics for a specific model."""
    try:
        metadata = await model_registry.get_model_metadata(model_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return ModelStatsResponse(
            model_id=metadata.model_id,
            total_predictions=metadata.total_predictions,
            total_updates=metadata.total_updates,
            accuracy=metadata.accuracy,
            drift_score=metadata.drift_score,
            last_updated=metadata.last_updated,
            creation_time=metadata.creation_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/models/{model_id}")
async def delete_model(model_id: str):
    """Delete a specific model."""
    try:
        success = await model_registry.delete_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return {"message": f"Model {model_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_system_stats():
    """Get overall system statistics."""
    try:
        engine_stats = learning_engine.get_engine_stats()
        cache_stats = model_registry.get_cache_stats()
        
        return {
            "learning_engine": engine_stats,
            "model_registry": cache_stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Get Prometheus-style metrics."""
    try:
        return metrics_collector.get_prometheus_metrics()
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, **kwargs):
    """Run the API server."""
    uvicorn.run(
        "tml.serving.api_server:app",
        host=host,
        port=port,
        reload=config.debug,
        log_level=config.log_level.lower(),
        **kwargs
    )


if __name__ == "__main__":
    run_server()
