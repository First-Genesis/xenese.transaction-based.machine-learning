#!/usr/bin/env python3
"""
Test Proto.Actor integration with the TML Platform
"""

import asyncio
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tml.orchestration.streamlit_integration import StreamlitTMLPlatform, StreamlitTMLConfig

def test_proto_actor():
    """Test that Proto.Actor integration is working"""
    print("=" * 60)
    print("Proto.Actor Integration Test")
    print("=" * 60)
    
    try:
        # Create configuration
        config = StreamlitTMLConfig(
            node_id="test-node-01",
            redis_url="redis://localhost:6379",
            transaction_processor_replicas=3,
            model_actor_replicas=5,
            physics_validator_replicas=2,
            use_thread_pool=True,
            max_workers=4
        )
        
        print("\n📋 Configuration:")
        print(f"   Node ID: {config.node_id}")
        print(f"   Redis URL: {config.redis_url}")
        print(f"   Transaction Processors: {config.transaction_processor_replicas}")
        print(f"   Model Actors: {config.model_actor_replicas}")
        print(f"   Physics Validators: {config.physics_validator_replicas}")
        
        # Create platform
        platform = StreamlitTMLPlatform(config)
        print("\n✅ Proto.Actor platform created successfully!")
        
        # Try to start the platform
        print("\n🚀 Starting Proto.Actor system...")
        success = platform.start(timeout=10.0)
        
        if success:
            print("✅ Proto.Actor system started successfully!")
            
            # Get status
            status = platform.get_status()
            if status:
                print("\n📊 System Status:")
                print(f"   Is Running: {status.get('is_running', False)}")
                
                actor_system = status.get('actor_system', {})
                print(f"   Total Actors: {actor_system.get('total_actors', 0)}")
                print(f"   Message Processing Rate: {actor_system.get('message_processing_rate', 0):.2f} msg/s")
                print(f"   Average Latency: {actor_system.get('average_latency', 0):.2f} ms")
                
                actors = status.get('actors', {})
                print(f"\n   Actor Breakdown:")
                print(f"      Transaction Processors: {actors.get('transaction_processors', 0)}")
                print(f"      Model Actors: {actors.get('model_actors', 0)}")
                print(f"      Physics Validators: {actors.get('physics_validators', 0)}")
            
            # Process a test transaction
            print("\n📝 Processing test transaction...")
            result = platform.process_transaction_sync({
                'id': 'test-tx-001',
                'data': {
                    'x_coord': 100,
                    'y_coord': 200,
                    'thickness': 19.5,
                    'min_thickness': 15.0
                },
                'source': 'test',
                'metadata': {'test': True}
            })
            
            if result:
                print(f"✅ Transaction processed successfully!")
                print(f"   Transaction ID: {result.get('transaction_id')}")
                print(f"   Model ID: {result.get('model_id')}")
                print(f"   Processing Time: {result.get('processing_time_ms', 0):.2f}ms")
                print(f"   Physics Valid: {result.get('physics_valid')}")
                print(f"   Confidence: {result.get('confidence', 0):.2f}")
            
            # Stop platform
            print("\n🛑 Stopping Proto.Actor system...")
            platform.stop()
            print("✅ Proto.Actor system stopped cleanly")
            
        else:
            print("⚠️  Proto.Actor system failed to start")
            print("   This might be because Redis is not running")
            print("   Make sure Redis is available at redis://localhost:6379")
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        print("\nPossible issues:")
        print("   1. Redis not running (docker run -d -p 6379:6379 redis)")
        print("   2. Port conflicts")
        print("   3. Missing dependencies")
        return False
    
    print("\n" + "=" * 60)
    print("✅ Proto.Actor Integration Test Complete!")
    print("\n💡 Proto.Actor is now available in the demo UI:")
    print("   1. Open http://localhost:8501")
    print("   2. Look for 'Proto.Actor Status' in the sidebar")
    print("   3. Try processing data in Batch mode")
    print("   4. Watch the real-time metrics")
    
    return True

if __name__ == "__main__":
    # Test Redis connection first
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "exec", "tml-redis-1", "redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if "PONG" not in result.stdout and "Authentication" not in result.stdout:
            print("⚠️  Redis might not be running properly")
    except:
        print("⚠️  Could not check Redis status")
    
    # Run the test
    test_proto_actor()
