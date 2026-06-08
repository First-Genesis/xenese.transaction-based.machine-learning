"""
Integration tests for TML API endpoints
"""

import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

# Import the API app
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ui_api_server import app


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def sample_model_data():
    """Sample model creation data"""
    return {
        "model_id": "test_model_001",
        "model_type": "logistic_regression",
        "parent_model_id": None,
    }


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health endpoint returns 200"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestModelEndpoints:
    """Test model CRUD endpoints"""

    def test_list_models_empty(self, client):
        """Test listing models when none exist"""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_create_model(self, client, sample_model_data):
        """Test creating a new model"""
        response = client.post("/api/models/create", json=sample_model_data)
        assert response.status_code == 200

        data = response.json()
        assert data["model_id"] == sample_model_data["model_id"]
        assert data["model_type"] == sample_model_data["model_type"]
        assert "created_at" in data
        assert "metrics" in data

    def test_create_model_with_parent(self, client):
        """Test creating a model with parent inheritance"""
        # First create parent model
        parent_data = {
            "model_id": "parent_model_001",
            "model_type": "logistic_regression",
            "parent_model_id": None,
        }
        parent_response = client.post("/api/models/create", json=parent_data)
        assert parent_response.status_code == 200

        # Then create child model
        child_data = {
            "model_id": "child_model_001",
            "model_type": "logistic_regression",
            "parent_model_id": "parent_model_001",
        }
        child_response = client.post("/api/models/create", json=child_data)
        assert child_response.status_code == 200

        child_data_response = child_response.json()
        assert child_data_response["parent_model_id"] == "parent_model_001"

    def test_get_model(self, client, sample_model_data):
        """Test retrieving a specific model"""
        # First create the model
        create_response = client.post("/api/models/create", json=sample_model_data)
        assert create_response.status_code == 200

        # Then retrieve it
        model_id = sample_model_data["model_id"]
        get_response = client.get(f"/api/models/{model_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["model_id"] == model_id
        assert data["model_type"] == sample_model_data["model_type"]

    def test_get_nonexistent_model(self, client):
        """Test retrieving a model that doesn't exist"""
        response = client.get("/api/models/nonexistent_model")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_models_after_creation(self, client, sample_model_data):
        """Test listing models after creating some"""
        # Create a model
        client.post("/api/models/create", json=sample_model_data)

        # List models
        response = client.get("/api/models")
        assert response.status_code == 200

        data = response.json()
        assert len(data["models"]) >= 1

        # Check if our model is in the list
        model_ids = [model["model_id"] for model in data["models"]]
        assert sample_model_data["model_id"] in model_ids


class TestPredictionEndpoints:
    """Test model prediction endpoints"""

    def test_predict_with_model(self, client, sample_model_data):
        """Test making predictions with a model"""
        # First create the model
        create_response = client.post("/api/models/create", json=sample_model_data)
        assert create_response.status_code == 200

        # Make a prediction
        model_id = sample_model_data["model_id"]
        prediction_data = {
            "features": {"feature_1": 1.0, "feature_2": 0.5, "feature_3": -0.2}
        }

        response = client.post(f"/api/models/{model_id}/predict", json=prediction_data)
        assert response.status_code == 200

        data = response.json()
        assert "prediction" in data
        assert "model_id" in data
        assert data["model_id"] == model_id

    def test_predict_nonexistent_model(self, client):
        """Test prediction with nonexistent model"""
        prediction_data = {"features": {"feature_1": 1.0, "feature_2": 0.5}}

        response = client.post("/api/models/nonexistent/predict", json=prediction_data)
        assert response.status_code == 404


class TestTrainingEndpoints:
    """Test model training endpoints"""

    def test_train_model(self, client, sample_model_data):
        """Test training a model"""
        # First create the model
        create_response = client.post("/api/models/create", json=sample_model_data)
        assert create_response.status_code == 200

        # Train the model
        model_id = sample_model_data["model_id"]
        training_data = {
            "features": {"feature_1": 1.0, "feature_2": 0.5, "feature_3": -0.2},
            "label": True,
        }

        response = client.post(f"/api/models/{model_id}/train", json=training_data)
        assert response.status_code == 200

        data = response.json()
        assert "model_id" in data
        assert "metrics" in data
        assert data["model_id"] == model_id

    def test_train_nonexistent_model(self, client):
        """Test training nonexistent model"""
        training_data = {
            "features": {"feature_1": 1.0, "feature_2": 0.5},
            "label": True,
        }

        response = client.post("/api/models/nonexistent/train", json=training_data)
        assert response.status_code == 404

    def test_multiple_training_updates_metrics(self, client, sample_model_data):
        """Test that multiple training calls update metrics correctly"""
        # Create model
        create_response = client.post("/api/models/create", json=sample_model_data)
        assert create_response.status_code == 200

        model_id = sample_model_data["model_id"]

        # Train multiple times
        for i in range(5):
            training_data = {
                "features": {"feature_1": float(i), "feature_2": float(i * 0.5)},
                "label": i % 2 == 0,
            }

            response = client.post(f"/api/models/{model_id}/train", json=training_data)
            assert response.status_code == 200

        # Check that metrics were updated
        get_response = client.get(f"/api/models/{model_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["metrics"]["updates"] >= 5


class TestDemoEndpoints:
    """Test demo-specific endpoints"""

    def test_create_demo_chain(self, client):
        """Test creating a demo model chain"""
        response = client.post("/api/demo/create-chain")
        assert response.status_code == 200

        data = response.json()
        assert "models" in data
        assert len(data["models"]) >= 2  # Should create multiple models

        # Check inheritance chain
        models = data["models"]
        parent_model = models[0]
        child_model = models[1]

        assert parent_model["parent_model_id"] is None
        assert child_model["parent_model_id"] == parent_model["model_id"]


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_json(self, client):
        """Test handling of invalid JSON"""
        response = client.post(
            "/api/models/create",
            data="invalid json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422  # Unprocessable Entity

    def test_missing_required_fields(self, client):
        """Test handling of missing required fields"""
        incomplete_data = {
            "model_id": "test_model"
            # Missing model_type
        }

        response = client.post("/api/models/create", json=incomplete_data)
        assert response.status_code == 422

    def test_invalid_model_type(self, client):
        """Test handling of invalid model type"""
        invalid_data = {"model_id": "test_model", "model_type": "invalid_type"}

        response = client.post("/api/models/create", json=invalid_data)
        assert response.status_code == 400  # Bad Request


class TestConcurrency:
    """Test concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_model_creation(self, client):
        """Test creating multiple models concurrently"""
        import asyncio
        import httpx

        async def create_model(model_id: str):
            async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/models/create",
                    json={"model_id": model_id, "model_type": "logistic_regression"},
                )
                return response.status_code

        # Create 5 models concurrently
        tasks = [create_model(f"concurrent_model_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 200 for status in results)

    @pytest.mark.asyncio
    async def test_concurrent_predictions(self, client):
        """Test making concurrent predictions"""
        # First create a model
        model_data = {
            "model_id": "concurrent_test_model",
            "model_type": "logistic_regression",
        }
        create_response = client.post("/api/models/create", json=model_data)
        assert create_response.status_code == 200

        async def make_prediction(features: dict):
            async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/models/concurrent_test_model/predict",
                    json={"features": features},
                )
                return response.status_code

        # Make 5 predictions concurrently
        tasks = [
            make_prediction({"feature_1": float(i), "feature_2": float(i * 0.5)})
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 200 for status in results)
