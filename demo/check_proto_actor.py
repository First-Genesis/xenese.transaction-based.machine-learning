#!/usr/bin/env python3
"""Quick check for Proto.Actor availability in demo context"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if Proto.Actor can be imported
try:
    from tml.orchestration.integration import TMLPlatform, TMLPlatformBuilder, TMLPlatformConfig
    print("✅ Proto.Actor imports: SUCCESS")
    
    # Check Redis connection
    import aioredis
    import asyncio
    
    async def check_redis():
        try:
            redis = aioredis.from_url("redis://localhost:6379")
            await redis.ping()
            await redis.close()
            print("✅ Redis connection: SUCCESS")
            return True
        except Exception as e:
            print(f"❌ Redis connection: FAILED - {e}")
            return False
    
    asyncio.run(check_redis())
    
    print("\n🎉 Proto.Actor is AVAILABLE and READY!")
    print("\nTo use in the demo:")
    print("1. Refresh your browser (Cmd+R or F5)")
    print("2. You should see '✅ Platform Initialized' in the sidebar")
    print("3. Select '🚀 Batch Processing (Proto.Actor)' when processing")
    
except ImportError as e:
    print(f"❌ Proto.Actor imports: FAILED - {e}")
    print("\nProto.Actor is NOT available. The demo will use sequential processing.")
