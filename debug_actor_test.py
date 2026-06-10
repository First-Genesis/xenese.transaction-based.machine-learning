#!/usr/bin/env python3
"""
Debug Actor Integration Issues
Simple step-by-step diagnostic
"""

import sys
import os
import traceback

# Add TML to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_step(step_name, test_func):
    """Run a test step and report results"""
    print(f"\n🔍 {step_name}")
    print("-" * 50)
    try:
        result = test_func()
        print(f"✅ {step_name}: SUCCESS")
        return True, result
    except Exception as e:
        print(f"❌ {step_name}: FAILED")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False, None

def step1_basic_imports():
    """Test basic imports"""
    from tml.orchestration.actor_system import ActorSystem, Actor, ActorMessage
    from tml.orchestration.tml_actors import TransactionProcessorActor, ModelActor
    return "All imports successful"

def step2_actor_system_creation():
    """Test ActorSystem creation"""
    from tml.orchestration.actor_system import ActorSystem
    
    actor_system = ActorSystem(
        node_id="test-node",
        redis_url="redis://localhost:6379"
    )
    return f"ActorSystem created: {actor_system.node_id}"

def step3_bridge_import():
    """Test bridge import"""
    from tml.orchestration.actor_transaction_bridge import ActorTransactionBridge
    return "Bridge import successful"

def step4_bridge_creation():
    """Test bridge creation"""
    from tml.orchestration.actor_transaction_bridge import ActorTransactionBridge
    
    bridge = ActorTransactionBridge(parallelism=1)
    return f"Bridge created with node: {bridge.actor_system.node_id}"

def step5_kafka_test():
    """Test Kafka connectivity"""
    from kafka import KafkaProducer
    
    producer = KafkaProducer(
        bootstrap_servers=['localhost:29092'],
        request_timeout_ms=3000
    )
    producer.close()
    return "Kafka connection successful"

def step6_redis_test():
    """Test Redis connectivity"""
    import redis
    
    r = redis.from_url("redis://localhost:6379")
    r.ping()
    return "Redis connection successful"

def step7_async_test():
    """Test async functionality"""
    import asyncio
    from tml.orchestration.actor_transaction_bridge import ActorTransactionBridge
    
    async def async_test():
        bridge = ActorTransactionBridge(parallelism=1)
        # Just test creation, not full initialization
        return f"Async bridge creation: {bridge.actor_system.node_id}"
    
    result = asyncio.run(async_test())
    return result

def main():
    """Run all diagnostic steps"""
    print("🚀 Actor Integration Diagnostic Test")
    print("=" * 60)
    
    steps = [
        ("Basic Imports", step1_basic_imports),
        ("ActorSystem Creation", step2_actor_system_creation),
        ("Bridge Import", step3_bridge_import),
        ("Bridge Creation", step4_bridge_creation),
        ("Kafka Connectivity", step5_kafka_test),
        ("Redis Connectivity", step6_redis_test),
        ("Async Functionality", step7_async_test),
    ]
    
    results = []
    for step_name, test_func in steps:
        success, result = test_step(step_name, test_func)
        results.append((step_name, success, result))
        
        if not success:
            print(f"\n🛑 Stopping at failed step: {step_name}")
            break
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for step_name, success, result in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {step_name}")
        if success and result:
            print(f"      {result}")
    
    print(f"\nResult: {passed}/{total} steps passed")
    
    if passed == total:
        print("✅ All diagnostics passed - actor system should work")
        return True
    else:
        print("❌ Some diagnostics failed - need to fix issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
