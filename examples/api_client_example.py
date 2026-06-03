"""Example API client for TML platform."""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List

from loguru import logger


class TMLAPIClient:
    """Client for interacting with TML API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session: aiohttp.ClientSession = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()
    
    async def predict(self, features: Dict[str, Any], 
                     user_id: str = None, 
                     return_probabilities: bool = False) -> Dict[str, Any]:
        """Make a prediction."""
        payload = {
            "features": features,
            "return_probabilities": return_probabilities
        }
        
        if user_id:
            payload["user_id"] = user_id
        
        async with self.session.post(
            f"{self.base_url}/predict",
            json=payload
        ) as response:
            return await response.json()
    
    async def learn(self, features: Dict[str, Any], target: Any,
                   user_id: str = None) -> Dict[str, Any]:
        """Update model with new data."""
        payload = {
            "features": features,
            "target": target
        }
        
        if user_id:
            payload["user_id"] = user_id
        
        async with self.session.post(
            f"{self.base_url}/learn",
            json=payload
        ) as response:
            return await response.json()
    
    async def batch_predict(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Make batch predictions."""
        payload = {"requests": requests}
        
        async with self.session.post(
            f"{self.base_url}/predict/batch",
            json=payload
        ) as response:
            return await response.json()
    
    async def list_models(self) -> List[str]:
        """List all models."""
        async with self.session.get(f"{self.base_url}/models") as response:
            return await response.json()
    
    async def get_model_stats(self, model_id: str) -> Dict[str, Any]:
        """Get model statistics."""
        async with self.session.get(
            f"{self.base_url}/models/{model_id}/stats"
        ) as response:
            return await response.json()
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        async with self.session.get(f"{self.base_url}/stats") as response:
            return await response.json()


async def basic_api_example():
    """Basic API usage example."""
    logger.info("=== Basic API Example ===")
    
    async with TMLAPIClient() as client:
        # Health check
        health = await client.health_check()
        logger.info(f"API Health: {health['status']}")
        
        # Make a prediction
        features = {
            "amount": 150.0,
            "category": "electronics",
            "hour_of_day": 14,
            "device_type": "mobile"
        }
        
        prediction_result = await client.predict(
            features=features,
            user_id="api_user_123",
            return_probabilities=True
        )
        
        logger.info(f"Prediction: {prediction_result['prediction']}")
        logger.info(f"Model ID: {prediction_result['model_id']}")
        logger.info(f"Processing time: {prediction_result['processing_time_ms']:.1f}ms")
        
        if prediction_result.get('probabilities'):
            logger.info(f"Probabilities: {prediction_result['probabilities']}")
        
        # Update the model
        learn_result = await client.learn(
            features=features,
            target=True,  # Assume positive outcome
            user_id="api_user_123"
        )
        
        logger.info(f"Learning success: {learn_result['success']}")
        logger.info(f"Learning time: {learn_result['processing_time_ms']:.1f}ms")


async def batch_prediction_example():
    """Batch prediction example."""
    logger.info("=== Batch Prediction Example ===")
    
    async with TMLAPIClient() as client:
        # Prepare batch requests
        requests = []
        for i in range(5):
            requests.append({
                "features": {
                    "amount": 100 + i * 50,
                    "category": ["electronics", "clothing", "books"][i % 3],
                    "hour_of_day": 10 + i,
                    "device_type": "mobile" if i % 2 == 0 else "desktop"
                },
                "user_id": f"batch_user_{i}",
                "return_probabilities": True
            })
        
        # Make batch prediction
        batch_result = await client.batch_predict(requests)
        
        logger.info(f"Batch processing time: {batch_result['total_processing_time_ms']:.1f}ms")
        
        for i, prediction in enumerate(batch_result['predictions']):
            logger.info(f"Request {i}: Prediction={prediction['prediction']}, "
                       f"Model={prediction['model_id']}")


async def model_management_example():
    """Model management example."""
    logger.info("=== Model Management Example ===")
    
    async with TMLAPIClient() as client:
        # Create some models by making predictions
        users = ["mgmt_user_1", "mgmt_user_2", "mgmt_user_3"]
        
        for user_id in users:
            await client.predict(
                features={"amount": 100, "category": "test"},
                user_id=user_id
            )
        
        # List all models
        models = await client.list_models()
        logger.info(f"Total models: {len(models)}")
        
        # Get stats for each model
        for model_id in models[:3]:  # Limit to first 3
            try:
                stats = await client.get_model_stats(model_id)
                logger.info(f"Model {model_id}: "
                           f"Predictions={stats['total_predictions']}, "
                           f"Updates={stats['total_updates']}")
            except Exception as e:
                logger.warning(f"Could not get stats for {model_id}: {e}")
        
        # Get system stats
        system_stats = await client.get_system_stats()
        logger.info(f"System stats: {system_stats}")


async def performance_test():
    """Simple performance test."""
    logger.info("=== Performance Test ===")
    
    async with TMLAPIClient() as client:
        # Test prediction latency
        features = {
            "amount": 150.0,
            "category": "electronics",
            "hour_of_day": 14
        }
        
        num_requests = 50
        start_time = time.time()
        
        tasks = []
        for i in range(num_requests):
            task = client.predict(
                features=features,
                user_id=f"perf_user_{i % 10}"  # 10 different users
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate statistics
        processing_times = [r['processing_time_ms'] for r in results]
        avg_processing_time = sum(processing_times) / len(processing_times)
        max_processing_time = max(processing_times)
        min_processing_time = min(processing_times)
        
        logger.info(f"Performance Test Results:")
        logger.info(f"  Total requests: {num_requests}")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(f"  Requests/second: {num_requests / total_time:.1f}")
        logger.info(f"  Avg processing time: {avg_processing_time:.1f}ms")
        logger.info(f"  Min processing time: {min_processing_time:.1f}ms")
        logger.info(f"  Max processing time: {max_processing_time:.1f}ms")


async def learning_workflow_example():
    """Complete learning workflow example."""
    logger.info("=== Learning Workflow Example ===")
    
    async with TMLAPIClient() as client:
        user_id = "workflow_user"
        
        # Phase 1: Initial predictions (cold start)
        logger.info("Phase 1: Cold start predictions")
        for i in range(5):
            features = {
                "amount": 100 + i * 20,
                "category": "electronics",
                "hour_of_day": 10 + i
            }
            
            result = await client.predict(features=features, user_id=user_id)
            logger.info(f"Cold start prediction {i+1}: {result['prediction']}")
        
        # Phase 2: Learning from feedback
        logger.info("Phase 2: Learning from feedback")
        training_data = [
            ({"amount": 50, "category": "books"}, False),
            ({"amount": 200, "category": "electronics"}, True),
            ({"amount": 30, "category": "clothing"}, False),
            ({"amount": 300, "category": "luxury"}, True),
            ({"amount": 80, "category": "home"}, False),
        ]
        
        for features, target in training_data:
            learn_result = await client.learn(
                features=features,
                target=target,
                user_id=user_id
            )
            logger.info(f"Learning update: {learn_result['success']}")
        
        # Phase 3: Improved predictions
        logger.info("Phase 3: Improved predictions")
        test_cases = [
            {"amount": 45, "category": "books"},      # Should predict False
            {"amount": 250, "category": "electronics"}, # Should predict True
            {"amount": 25, "category": "clothing"},    # Should predict False
        ]
        
        for features in test_cases:
            result = await client.predict(
                features=features, 
                user_id=user_id,
                return_probabilities=True
            )
            logger.info(f"Improved prediction for {features}: "
                       f"{result['prediction']} "
                       f"(confidence: {result.get('confidence', 'N/A')})")


async def run_all_api_examples():
    """Run all API examples."""
    logger.info("Starting TML API Client Examples")
    logger.info("=" * 50)
    
    try:
        await basic_api_example()
        await asyncio.sleep(1)
        
        await batch_prediction_example()
        await asyncio.sleep(1)
        
        await model_management_example()
        await asyncio.sleep(1)
        
        await performance_test()
        await asyncio.sleep(1)
        
        await learning_workflow_example()
        
        logger.info("=" * 50)
        logger.info("All API examples completed successfully!")
        
    except Exception as e:
        logger.error(f"API example failed: {e}")
        raise


if __name__ == "__main__":
    # Run API examples
    asyncio.run(run_all_api_examples())
