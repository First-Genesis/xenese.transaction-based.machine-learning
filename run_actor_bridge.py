#!/usr/bin/env python3
"""
Run Proto.Actor Transaction Bridge
Connects actors to real transaction flow for production processing
"""

import asyncio
import sys
import os
import signal
from loguru import logger

# Add TML to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logger.add("actor_bridge.log", rotation="10 MB", level="INFO")

# Global bridge instance for signal handling
bridge = None


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    if bridge:
        asyncio.create_task(bridge.shutdown())
    sys.exit(0)


async def main():
    """Main entry point"""
    global bridge
    
    logger.info("="*60)
    logger.info("🎭 TML Platform - Proto.Actor Transaction Bridge")
    logger.info("="*60)
    
    # Set environment variables
    os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:29092'
    os.environ['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check prerequisites
    logger.info("🔌 Checking prerequisites...")
    
    # Check Kafka
    try:
        from kafka import KafkaProducer
        test_producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            request_timeout_ms=5000
        )
        test_producer.close()
        logger.info("✅ Kafka connection successful")
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        logger.error("Please ensure Kafka is running on localhost:29092")
        return 1
    
    # Check Redis (for actor state)
    try:
        import redis
        r = redis.from_url("redis://localhost:6379")
        r.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error("Please ensure Redis is running on localhost:6379")
        return 1
    
    # Import and start bridge
    try:
        from tml.orchestration.actor_transaction_bridge import ActorTransactionBridge
        
        logger.info("")
        logger.info("🎯 Configuration:")
        logger.info("  • Actor System: TMLActorSystem")
        logger.info("  • Parallelism: 4 transaction processors")
        logger.info("  • Input Topic: transactions")
        logger.info("  • Output Topic: actor-results")
        logger.info("  • Integration: TML Learning Engine + Spatial Inheritance")
        logger.info("")
        
        # Create and initialize bridge
        bridge = ActorTransactionBridge(parallelism=4)
        await bridge.initialize()
        
        logger.info("🚀 Starting actor-based transaction processing...")
        logger.info("="*60)
        
        # Start processing (this blocks)
        await bridge.process_transaction_stream()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Actor bridge stopped by user")
    except Exception as e:
        logger.error(f"❌ Actor bridge failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if bridge:
            await bridge.shutdown()
    
    logger.info("")
    logger.info("✅ Actor bridge shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
