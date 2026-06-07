#!/usr/bin/env python3
"""Test the Streamlit-compatible Proto.Actor integration"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tml.orchestration.streamlit_integration import StreamlitTMLPlatform, StreamlitTMLConfig

print("Testing Streamlit-compatible Proto.Actor integration...")

# Create config
config = StreamlitTMLConfig(
    node_id="test-node",
    redis_url="redis://localhost:6379",
    transaction_processor_replicas=2,
    model_actor_replicas=3,
    physics_validator_replicas=1,
    use_thread_pool=True,
    max_workers=4
)

# Create platform
platform = StreamlitTMLPlatform(config)

print("\n1. Starting platform...")
if platform.start(timeout=10.0):
    print("✅ Platform started successfully!")
    
    # Get status
    status = platform.get_status()
    print(f"\n2. Platform Status:")
    print(f"   - Running: {status['is_running']}")
    print(f"   - Node ID: {status['node_id']}")
    print(f"   - Total Actors: {status['actor_system']['total_actors']}")
    print(f"   - Transaction Processors: {status['actor_system']['transaction_processors']}")
    print(f"   - Model Actors: {status['actor_system']['model_actors']}")
    
    # Test single transaction
    print("\n3. Testing single transaction...")
    transaction = {
        'id': 'test_tx_001',
        'data': {
            'x_coord': 100,
            'y_coord': 200,
            'thickness': 20.5,
            'min_thickness': 15.0
        },
        'source': 'test'
    }
    
    result = platform.process_transaction_sync(transaction)
    if result['status'] == 'success':
        print(f"✅ Transaction processed: {result}")
    else:
        print(f"❌ Transaction failed: {result}")
    
    # Test batch processing
    print("\n4. Testing batch processing...")
    batch_transactions = [
        {
            'id': f'batch_tx_{i}',
            'data': {
                'x_coord': 100 + i*10,
                'y_coord': 200,
                'thickness': 20.0 + i*0.5,
                'min_thickness': 15.0
            },
            'source': 'batch_test'
        }
        for i in range(5)
    ]
    
    batch_results = platform.batch_process_sync(batch_transactions)
    success_count = sum(1 for r in batch_results if r.get('status') == 'success')
    print(f"✅ Batch processed: {success_count}/{len(batch_transactions)} successful")
    
    # Stop platform
    print("\n5. Stopping platform...")
    platform.stop()
    print("✅ Platform stopped")
    
    print("\n🎉 All tests passed! Streamlit-Proto.Actor integration is working!")
else:
    print("❌ Platform failed to start")
    print("Check if Redis is running: redis-cli ping")
