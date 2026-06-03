#!/usr/bin/env python3
"""
Basic TML Platform Test

This script tests the core functionality without requiring external dependencies.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that core modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        # Test core imports
        from tml.core.model import TransactionContext, TransactionModel, ModelFactory
        print("  ✅ Core model imports successful")
        
        from tml.learning.online_learner import RiverLearner, OnlineLearningEngine
        print("  ✅ Learning engine imports successful")
        
        from tml.ingestion.kafka_producer import TransactionEvent, TransactionEventGenerator
        print("  ✅ Kafka producer imports successful")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def test_basic_model_creation():
    """Test basic model creation and prediction."""
    print("\n🧠 Testing basic model creation...")
    
    try:
        from tml.core.model import TransactionContext, ModelFactory
        
        # Create transaction context
        context = TransactionContext(
            transaction_id="test_001",
            user_id="test_user",
            session_id="test_session"
        )
        print(f"  ✅ Created context: {context.transaction_id}")
        
        # Create model
        model = ModelFactory.create_model(context)
        print(f"  ✅ Created model: {model.model_id}")
        
        # Test prediction
        features = {
            "amount": 100.0,
            "category": "electronics",
            "hour_of_day": 14
        }
        
        prediction = model.predict(features)
        print(f"  ✅ Made prediction: {prediction}")
        
        # Test learning
        model.update(features, True)
        metrics = model.get_metrics()
        print(f"  ✅ Updated model, total updates: {metrics.total_updates}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Model test failed: {e}")
        return False

def test_online_learning():
    """Test online learning engine."""
    print("\n📚 Testing online learning engine...")
    
    try:
        from tml.learning.online_learner import OnlineLearningEngine
        
        # Create learning engine
        engine = OnlineLearningEngine()
        print("  ✅ Created learning engine")
        
        # Create a learner
        learner = engine.create_learner("test_model", algorithm="river")
        print("  ✅ Created River learner")
        
        # Test prediction and learning
        features = {"feature1": 1.0, "feature2": 2.0}
        
        prediction = engine.predict("test_model", features)
        print(f"  ✅ Made prediction: {prediction}")
        
        success = engine.learn("test_model", features, True)
        print(f"  ✅ Learning update successful: {success}")
        
        # Get engine stats
        stats = engine.get_engine_stats()
        print(f"  ✅ Engine stats - Models: {stats['total_models']}, Predictions: {stats['total_predictions']}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Online learning test failed: {e}")
        return False

def test_transaction_events():
    """Test transaction event generation."""
    print("\n📝 Testing transaction events...")
    
    try:
        from tml.ingestion.kafka_producer import TransactionEvent, TransactionEventGenerator
        
        # Create event manually
        event = TransactionEvent(
            transaction_id="test_event_001",
            user_id="test_user",
            event_type="purchase",
            features={"amount": 150.0, "category": "books"},
            target=True
        )
        print(f"  ✅ Created event: {event.transaction_id}")
        
        # Test serialization
        event_dict = event.to_dict()
        event_json = event.to_json()
        restored_event = TransactionEvent.from_json(event_json)
        print(f"  ✅ Serialization works: {restored_event.transaction_id}")
        
        # Test event generator
        generator = TransactionEventGenerator()
        generated_event = generator.generate_event()
        print(f"  ✅ Generated event: {generated_event.event_type}")
        
        # Generate batch
        batch = generator.generate_batch(5)
        print(f"  ✅ Generated batch of {len(batch)} events")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Transaction event test failed: {e}")
        return False

def test_model_inheritance():
    """Test model inheritance functionality."""
    print("\n🧬 Testing model inheritance...")
    
    try:
        from tml.core.model import TransactionContext, ModelFactory
        
        # Create parent model
        parent_context = TransactionContext(
            transaction_id="parent_001",
            user_id="parent_user"
        )
        parent_model = ModelFactory.create_model(parent_context)
        
        # Train parent model
        for i in range(5):
            features = {"amount": 100 + i * 20, "category": "electronics"}
            target = features["amount"] > 120
            parent_model.update(features, target)
        
        parent_metrics = parent_model.get_metrics()
        print(f"  ✅ Trained parent model - Updates: {parent_metrics.total_updates}")
        
        # Create child model with inheritance
        child_context = TransactionContext(
            transaction_id="child_001",
            user_id="child_user"
        )
        child_model = ModelFactory.create_model(child_context, parent_model=parent_model)
        
        print(f"  ✅ Created child model with parent: {child_model.parent_model_id}")
        
        # Test both models
        test_features = {"amount": 140, "category": "electronics"}
        parent_pred = parent_model.predict(test_features)
        child_pred = child_model.predict(test_features)
        
        print(f"  ✅ Parent prediction: {parent_pred}, Child prediction: {child_pred}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Model inheritance test failed: {e}")
        return False

async def test_async_processing():
    """Test async processing capabilities."""
    print("\n⚡ Testing async processing...")
    
    try:
        from tml.learning.online_learner import learning_engine
        from tml.ingestion.kafka_producer import TransactionEvent
        
        # Create test event
        event = TransactionEvent(
            transaction_id="async_test_001",
            user_id="async_user",
            event_type="purchase",
            features={"amount": 200.0, "category": "electronics"},
            target=True
        )
        
        # Process transaction
        result = await learning_engine.process_transaction(event)
        
        print(f"  ✅ Async processing successful")
        print(f"      Model ID: {result.model_id}")
        print(f"      Prediction: {result.prediction}")
        print(f"      Updated: {result.update_applied}")
        print(f"      Processing time: {result.processing_time_ms:.2f}ms")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Async processing test failed: {e}")
        return False

def run_all_tests():
    """Run all basic tests."""
    print("🚀 Starting TML Platform Basic Tests")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Model Creation", test_basic_model_creation),
        ("Online Learning", test_online_learning),
        ("Transaction Events", test_transaction_events),
        ("Model Inheritance", test_model_inheritance),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Test async functionality
    print("\n⚡ Testing async processing...")
    try:
        import asyncio
        success = asyncio.run(test_async_processing())
        results.append(("Async Processing", success))
    except Exception as e:
        print(f"  ❌ Async processing crashed: {e}")
        results.append(("Async Processing", False))
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! TML Platform core functionality is working!")
        print("\n🚀 Ready for:")
        print("  • Full demo: python3 run_demo.py")
        print("  • API server: python3 scripts/start_platform.py start")
        print("  • Infrastructure: make start-infra")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite crashed: {e}")
        sys.exit(1)
