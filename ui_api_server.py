#!/usr/bin/env python3
"""
TML Platform API Server for UI Integration

This server provides REST endpoints for the UI to interact with the real TML platform.
"""

import sys
import json
import uuid
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# FastAPI and dependencies
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Installing required dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "python-multipart"])
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn

# Import TML components
from tml.core.model import TransactionContext, RiverTransactionModel, ModelFactory

# Initialize FastAPI app
app = FastAPI(title="TML Platform API", version="1.0.0")

# Enable CORS for UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for models (in production, use Redis)
models_store: Dict[str, RiverTransactionModel] = {}
model_counter = 0

# Pydantic models for API requests/responses
class CreateModelRequest(BaseModel):
    transaction_id: str
    user_id: str
    parent_model_id: Optional[str] = None
    model_type: str = "logistic_regression"
    session_id: Optional[str] = None

class TrainModelRequest(BaseModel):
    model_id: str
    features: Dict[str, Any]
    target: bool

class PredictRequest(BaseModel):
    model_id: Optional[str] = None  # If None, predict with all models
    features: Dict[str, Any]

class ModelInfo(BaseModel):
    id: str
    parent_id: Optional[str]
    type: str
    updates: int
    accuracy: float
    created_at: str
    predictions: int

class PredictionResult(BaseModel):
    model_id: str
    prediction: bool
    confidence: Optional[float] = None

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TML Platform API",
        "status": "online",
        "models_count": len(models_store),
        "endpoints": {
            "health": "/health",
            "models": "/api/models",
            "create_model": "/api/models/create",
            "train": "/api/models/train",
            "predict": "/api/predict",
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "models_active": len(models_store),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/models", response_model=List[ModelInfo])
async def list_models():
    """List all models."""
    models_list = []
    for model_id, model in models_store.items():
        models_list.append(ModelInfo(
            id=model_id,
            parent_id=model.parent_model_id,
            type=model.model_type if hasattr(model, 'model_type') else "logistic_regression",
            updates=model.metrics.total_updates,
            accuracy=model.metrics.accuracy,
            created_at=datetime.now().isoformat(),
            predictions=model.metrics.total_predictions
        ))
    return models_list

@app.post("/api/models/create", response_model=ModelInfo)
async def create_model(request: CreateModelRequest):
    """Create a new model."""
    global model_counter
    
    try:
        # Create transaction context
        context = TransactionContext(
            transaction_id=request.transaction_id,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        # Get parent model if specified
        parent_model = None
        if request.parent_model_id and request.parent_model_id in models_store:
            parent_model = models_store[request.parent_model_id]
        
        # Create model directly (ModelFactory may have issues)
        model_counter += 1
        model_id = f"model_{uuid.uuid4().hex[:12]}"
        
        model = RiverTransactionModel(
            model_id=model_id,
            parent_model_id=parent_model.model_id if parent_model else None,
            model_type=request.model_type
        )
        model.context = context
        
        # Inherit from parent if exists
        if parent_model:
            # Copy model state for inheritance
            try:
                import pickle
                model.model = pickle.loads(pickle.dumps(parent_model.model))
                model.metrics.total_updates = parent_model.metrics.total_updates
            except:
                pass  # Inheritance failed, use fresh model
        
        # Store model
        models_store[model.model_id] = model
        
        # Return model info
        return ModelInfo(
            id=model.model_id,
            parent_id=model.parent_model_id,
            type=request.model_type,
            updates=model.metrics.total_updates,
            accuracy=model.metrics.accuracy,
            created_at=datetime.now().isoformat(),
            predictions=model.metrics.total_predictions
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/models/train")
async def train_model(request: TrainModelRequest):
    """Train a model with new data."""
    if request.model_id not in models_store:
        raise HTTPException(status_code=404, detail=f"Model {request.model_id} not found")
    
    try:
        model = models_store[request.model_id]
        model.update(request.features, request.target)
        
        return {
            "status": "success",
            "model_id": request.model_id,
            "updates": model.metrics.total_updates,
            "accuracy": model.metrics.accuracy
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/predict", response_model=List[PredictionResult])
async def predict(request: PredictRequest):
    """Make predictions with one or all models."""
    results = []
    
    if request.model_id:
        # Predict with specific model
        if request.model_id not in models_store:
            raise HTTPException(status_code=404, detail=f"Model {request.model_id} not found")
        
        model = models_store[request.model_id]
        prediction = model.predict(request.features)
        
        results.append(PredictionResult(
            model_id=request.model_id,
            prediction=bool(prediction) if prediction is not None else False,
            confidence=None  # Could calculate confidence if needed
        ))
    else:
        # Predict with all models
        for model_id, model in models_store.items():
            prediction = model.predict(request.features)
            results.append(PredictionResult(
                model_id=model_id,
                prediction=bool(prediction) if prediction is not None else False,
                confidence=None
            ))
    
    return results

@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    """Delete a specific model."""
    if model_id not in models_store:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    del models_store[model_id]
    return {"status": "success", "message": f"Model {model_id} deleted"}

@app.delete("/api/models")
async def clear_all_models():
    """Clear all models."""
    global model_counter
    count = len(models_store)
    models_store.clear()
    model_counter = 0
    return {"status": "success", "message": f"Cleared {count} models"}

@app.get("/api/models/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str):
    """Get details of a specific model."""
    if model_id not in models_store:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    model = models_store[model_id]
    return ModelInfo(
        id=model_id,
        parent_id=model.parent_model_id,
        type=model.model_type if hasattr(model, 'model_type') else "logistic_regression",
        updates=model.metrics.total_updates,
        accuracy=model.metrics.accuracy,
        created_at=datetime.now().isoformat(),
        predictions=model.metrics.total_predictions
    )

@app.get("/api/stats")
async def get_stats():
    """Get platform statistics."""
    total_updates = sum(m.metrics.total_updates for m in models_store.values())
    total_predictions = sum(m.metrics.total_predictions for m in models_store.values())
    avg_accuracy = sum(m.metrics.accuracy for m in models_store.values()) / len(models_store) if models_store else 0
    
    return {
        "total_models": len(models_store),
        "total_updates": total_updates,
        "total_predictions": total_predictions,
        "average_accuracy": avg_accuracy,
        "models": [
            {
                "id": model_id,
                "parent": model.parent_model_id,
                "updates": model.metrics.total_updates
            }
            for model_id, model in models_store.items()
        ]
    }

# Demo endpoint for testing
@app.post("/api/demo/create_chain")
async def create_demo_chain():
    """Create a chain of demo models for testing."""
    global model_counter
    demo_models = []
    parent_id = None
    
    for i in range(1, 4):
        context = TransactionContext(
            transaction_id=f"demo_txn_{i:03d}",
            user_id=f"demo_user_{i}"
        )
        
        parent_model = models_store.get(parent_id) if parent_id else None
        
        # Create model directly
        model_counter += 1
        model_id = f"model_demo_{i:03d}"
        
        model = RiverTransactionModel(
            model_id=model_id,
            parent_model_id=parent_model.model_id if parent_model else None,
            model_type="logistic_regression"
        )
        model.context = context
        
        # Inherit from parent if exists
        if parent_model:
            try:
                model.model = pickle.loads(pickle.dumps(parent_model.model))
                model.metrics.total_updates = parent_model.metrics.total_updates
            except:
                pass
        
        # Add some training data
        for j in range(3):
            features = {
                "amount": 50 + (i * 50) + (j * 20),
                "category": ["electronics", "books", "clothing"][j % 3],
                "hour": 10 + j
            }
            target = features["amount"] > 100
            model.update(features, target)
        
        models_store[model.model_id] = model
        demo_models.append(model.model_id)
        parent_id = model.model_id
    
    return {
        "status": "success",
        "message": f"Created chain of {len(demo_models)} demo models",
        "models": demo_models
    }

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TML Platform API Server")
    print("=" * 60)
    print("\n📍 Starting API server on http://localhost:8000")
    print("📊 API documentation: http://localhost:8000/docs")
    print("🌐 UI should connect automatically to this API")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
