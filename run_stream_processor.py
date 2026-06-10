#!/usr/bin/env python3
"""
Run Flink-Style Stream Processor for TML Platform
Production-ready stateful stream processing with spatial inheritance
"""

import os
import sys
import time
import signal
import threading
from loguru import logger

# Add TML to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logger.add("stream_processor.log", rotation="10 MB", level="INFO")

# Global processor instance for signal handling
processor = None


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    if processor:
        processor.stop()
    sys.exit(0)


def main():
    """Main entry point"""
    global processor
    
    logger.info("="*60)
    logger.info("🚀 TML Platform - Flink-Style Stream Processor")
    logger.info("="*60)
    
    # Set environment variables
    os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:29092'
    os.environ['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check Kafka connectivity
    logger.info("🔌 Checking Kafka connectivity...")
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
    
    # Check Redis connectivity
    logger.info("🔌 Checking Redis connectivity...")
    try:
        import redis
        r = redis.from_url("redis://localhost:6379")
        r.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error("Please ensure Redis is running on localhost:6379")
        return 1
    
    # Import and start processor
    try:
        from tml.ingestion.stream_processor import StreamProcessor
        
        logger.info("")
        logger.info("🎯 Configuration:")
        logger.info("  • Parallelism: 4")
        logger.info("  • Input Topic: transactions")
        logger.info("  • Output Topic: model-updates")
        logger.info("  • State Backend: Redis")
        logger.info("  • Checkpoint Interval: 30s")
        logger.info("")
        
        # Create processor
        processor = StreamProcessor(parallelism=4)
        
        logger.info("🚀 Starting stream processing...")
        logger.info("="*60)
        
        # Start processor (this blocks)
        processor.start()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Stream processing stopped by user")
    except Exception as e:
        logger.error(f"❌ Stream processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    logger.info("")
    logger.info("✅ Stream processing complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
