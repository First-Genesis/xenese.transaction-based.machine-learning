"""Basic usage example for TML platform."""

import asyncio
import time
from typing import List

from tml.core.model import TransactionContext, ModelFactory
from tml.learning.online_learner import learning_engine
from tml.ingestion.kafka_producer import TransactionEvent, TransactionEventGenerator
from tml.features.feature_store import feature_store
from tml.monitoring.metrics import metrics_collector
from loguru import logger


async def basic_prediction_example():
    """Demonstrate basic prediction functionality."""
    logger.info("=== Basic Prediction Example ===")
    
    # Create a transaction context
    context = TransactionContext(
        transaction_id="demo_001",
        user_id="user_123",
        session_id="session_456"
    )
    
    # Create a model
    model = ModelFactory.create_model(context)
    
    # Sample features
    features = {
        "amount": 150.0,
        "category": "electronics",
        "hour_of_day": 14,
        "device_type": "mobile",
        "user_age": 28
    }
    
    # Make a prediction
    prediction = model.predict(features)
    logger.info(f"Prediction: {prediction}")
    
    # Get prediction probabilities
    try:
        probabilities = model.predict_proba(features)
        logger.info(f"Probabilities: {probabilities}")
    except NotImplementedError:
        logger.info("Probabilities not available for this model type")
    
    return model, features, prediction


async def online_learning_example():
    """Demonstrate online learning functionality."""
    logger.info("=== Online Learning Example ===")
    
    # Generate some synthetic transaction events
    generator = TransactionEventGenerator()
    events = generator.generate_batch(10)
    
    results = []
    
    for event in events:
        # Process each transaction with online learning
        result = await learning_engine.process_transaction(event)
        results.append(result)
        
        logger.info(f"Transaction {event.transaction_id}: "
                   f"Prediction={result.prediction}, "
                   f"Updated={result.update_applied}, "
                   f"Drift={result.drift_detected}")
    
    return results


async def feature_store_example():
    """Demonstrate feature store functionality."""
    logger.info("=== Feature Store Example ===")
    
    # Get user features
    user_features = feature_store.get_user_features("user_123")
    logger.info(f"User features: {user_features}")
    
    # Get session features
    session_features = feature_store.get_session_features("session_456")
    logger.info(f"Session features: {session_features}")
    
    # Get contextual features
    contextual_features = feature_store.get_contextual_features()
    logger.info(f"Contextual features: {contextual_features}")
    
    # Get enriched features (combining all sources)
    enriched_features = feature_store.get_enriched_features(
        user_id="user_123",
        session_id="session_456",
        transaction_data={"amount": 100.0, "category": "books"}
    )
    logger.info(f"Enriched features count: {len(enriched_features)}")
    
    return enriched_features


async def model_lifecycle_example():
    """Demonstrate complete model lifecycle."""
    logger.info("=== Model Lifecycle Example ===")
    
    # Create multiple models for different users
    users = ["user_001", "user_002", "user_003"]
    models = {}
    
    for user_id in users:
        context = TransactionContext(
            transaction_id=f"init_{user_id}",
            user_id=user_id
        )
        model = ModelFactory.create_model(context)
        models[user_id] = model
        logger.info(f"Created model for {user_id}: {model.model_id}")
    
    # Simulate transactions and learning
    generator = TransactionEventGenerator()
    
    for i in range(20):  # 20 transactions
        # Generate event for random user
        user_id = users[i % len(users)]
        event = generator.generate_event(user_id=user_id)
        
        # Process with online learning
        result = await learning_engine.process_transaction(event)
        
        # Get model metrics
        metrics = learning_engine.get_model_metrics(result.model_id)
        
        if i % 5 == 0:  # Log every 5th transaction
            logger.info(f"Transaction {i+1}: Model {result.model_id}, "
                       f"Metrics: {metrics}")
    
    # Get final engine statistics
    engine_stats = learning_engine.get_engine_stats()
    logger.info(f"Final engine stats: {engine_stats}")
    
    return models, engine_stats


async def monitoring_example():
    """Demonstrate monitoring and metrics collection."""
    logger.info("=== Monitoring Example ===")
    
    # Simulate some predictions and updates
    for i in range(50):
        model_id = f"model_{i % 5}"  # 5 different models
        
        # Record prediction
        processing_time = 10 + (i % 20)  # Varying processing times
        success = (i % 10) != 0  # 90% success rate
        
        metrics_collector.record_prediction(
            model_id=model_id,
            processing_time_ms=processing_time,
            success=success
        )
        
        # Record learning update (less frequent)
        if i % 3 == 0:
            metrics_collector.record_learning_update(
                model_id=model_id,
                processing_time_ms=processing_time * 1.5,
                success=success
            )
        
        # Record accuracy (occasionally)
        if i % 10 == 0:
            accuracy = 0.7 + (i % 30) / 100  # Varying accuracy
            metrics_collector.record_model_accuracy(model_id, accuracy)
    
    # Get system metrics
    system_metrics = metrics_collector.get_system_metrics()
    logger.info(f"System metrics: {system_metrics}")
    
    # Get model-specific metrics
    for model_id in [f"model_{i}" for i in range(5)]:
        model_metrics = metrics_collector.get_model_metrics(model_id)
        if model_metrics:
            logger.info(f"Model {model_id} metrics: "
                       f"Predictions={model_metrics.prediction_count}, "
                       f"Updates={model_metrics.update_count}, "
                       f"Avg time={model_metrics.avg_prediction_time:.1f}ms")
    
    return system_metrics


async def drift_detection_example():
    """Demonstrate concept drift detection."""
    logger.info("=== Drift Detection Example ===")
    
    # Create a model
    context = TransactionContext(
        transaction_id="drift_demo",
        user_id="drift_user"
    )
    model = ModelFactory.create_model(context)
    
    # Simulate normal behavior
    logger.info("Phase 1: Normal behavior")
    for i in range(50):
        features = {
            "amount": 50 + (i % 20),  # Stable pattern
            "hour_of_day": 10 + (i % 8),
            "category": "electronics"
        }
        target = features["amount"] > 60  # Simple rule
        
        model.update(features, target)
        
        if i % 10 == 0:
            metrics = model.get_metrics()
            logger.info(f"Step {i}: Accuracy={metrics.accuracy:.3f}")
    
    # Simulate concept drift
    logger.info("Phase 2: Concept drift (pattern changes)")
    for i in range(50, 100):
        features = {
            "amount": 200 + (i % 50),  # Different pattern
            "hour_of_day": 20 + (i % 4),
            "category": "luxury"
        }
        target = features["amount"] < 220  # Inverted rule
        
        model.update(features, target)
        
        if i % 10 == 0:
            metrics = model.get_metrics()
            drift_detected = model.should_retrain()
            logger.info(f"Step {i}: Accuracy={metrics.accuracy:.3f}, "
                       f"Drift detected={drift_detected}")
    
    final_metrics = model.get_metrics()
    return final_metrics


async def run_all_examples():
    """Run all examples in sequence."""
    logger.info("Starting TML Platform Examples")
    logger.info("=" * 50)
    
    try:
        # Basic prediction
        await basic_prediction_example()
        await asyncio.sleep(1)
        
        # Online learning
        await online_learning_example()
        await asyncio.sleep(1)
        
        # Feature store
        await feature_store_example()
        await asyncio.sleep(1)
        
        # Model lifecycle
        await model_lifecycle_example()
        await asyncio.sleep(1)
        
        # Monitoring
        await monitoring_example()
        await asyncio.sleep(1)
        
        # Drift detection
        await drift_detection_example()
        
        logger.info("=" * 50)
        logger.info("All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_all_examples())
