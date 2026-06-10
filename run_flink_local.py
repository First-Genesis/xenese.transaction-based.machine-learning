#!/usr/bin/env python3
"""
Run Apache Flink locally for TML Platform
No Docker required - uses local Python environment
"""

import os
import sys
import time
import asyncio
from loguru import logger

# Add TML to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logger.add("flink_local.log", rotation="10 MB", level="INFO")


def check_dependencies():
    """Check if all required dependencies are installed"""
    missing = []
    
    try:
        import pyflink
        logger.info(f"✅ PyFlink version: {pyflink.__version__}")
    except ImportError:
        missing.append("pyflink")
    
    try:
        from kafka import KafkaProducer
        logger.info("✅ Kafka-python installed")
    except ImportError:
        missing.append("kafka-python")
    
    try:
        import river
        logger.info(f"✅ River ML version: {river.__version__}")
    except ImportError:
        missing.append("river")
    
    if missing:
        logger.error(f"❌ Missing dependencies: {', '.join(missing)}")
        logger.error("Install with: pip install " + " ".join(missing))
        return False
    
    return True


def setup_environment():
    """Setup environment for Flink execution"""
    # Set Java home if not set
    if not os.environ.get('JAVA_HOME'):
        # Try common Java locations
        java_paths = [
            '/usr/lib/jvm/java-11-openjdk-amd64',
            '/usr/lib/jvm/java-11-openjdk',
            '/Library/Java/JavaVirtualMachines/openjdk-11.jdk/Contents/Home',
            '/System/Library/Frameworks/JavaVM.framework/Home',
        ]
        
        for path in java_paths:
            if os.path.exists(path):
                os.environ['JAVA_HOME'] = path
                logger.info(f"Set JAVA_HOME to: {path}")
                break
    
    # Set Python path
    if not os.environ.get('PYTHONPATH'):
        os.environ['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    # Set Kafka bootstrap servers
    os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:29092'
    
    logger.info("Environment configured")


def run_flink_mini_cluster():
    """Run Flink with local mini cluster"""
    try:
        from pyflink.datastream import StreamExecutionEnvironment
        from pyflink.common import Configuration
        
        # Configure local execution
        config = Configuration()
        config.set_string("python.fn-execution.memory.managed", "true")
        config.set_string("python.fn-execution.buffer.memory.size", "1024mb")
        config.set_string("taskmanager.memory.process.size", "2048mb")
        config.set_string("state.backend", "filesystem")
        config.set_string("state.checkpoints.dir", "file:///tmp/flink-checkpoints")
        config.set_integer("parallelism.default", 2)
        
        # Create environment with configuration
        env = StreamExecutionEnvironment.get_execution_environment(config)
        env.set_parallelism(2)
        
        logger.info("✅ Flink mini cluster configured")
        
        # Import and run our Flink pipeline
        from tml.ingestion.flink_integration import FlinkTMLPipeline
        
        logger.info("Starting TML Flink Pipeline...")
        pipeline = FlinkTMLPipeline()
        
        # Override the environment configuration for local execution
        pipeline.env = env
        
        # Build and execute pipeline
        pipeline.build_pipeline()
        
        logger.info("🚀 Executing Flink job locally...")
        env.execute("TML Flink Local Processing")
        
    except Exception as e:
        logger.error(f"Failed to run Flink: {e}")
        raise


async def monitor_execution():
    """Monitor Flink execution and show statistics"""
    logger.info("📊 Monitoring Flink execution...")
    
    stats = {
        'start_time': time.time(),
        'transactions_processed': 0,
        'models_created': 0,
        'inheritance_applied': 0,
        'drift_detected': 0
    }
    
    while True:
        elapsed = time.time() - stats['start_time']
        logger.info(f"⏱️ Running for {elapsed:.0f}s - "
                   f"Transactions: {stats['transactions_processed']} | "
                   f"Models: {stats['models_created']} | "
                   f"Inheritance: {stats['inheritance_applied']}")
        await asyncio.sleep(10)


async def main_async():
    """Main async execution"""
    # Start monitoring in background
    monitor_task = asyncio.create_task(monitor_execution())
    
    # Run Flink in separate thread
    import threading
    flink_thread = threading.Thread(target=run_flink_mini_cluster)
    flink_thread.start()
    
    # Wait for execution
    try:
        await monitor_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")


def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("🚀 TML Platform - Apache Flink Local Runner")
    logger.info("="*60)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Setup environment
    setup_environment()
    
    # Check Kafka connectivity
    logger.info("🔌 Checking Kafka connectivity...")
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            request_timeout_ms=5000
        )
        producer.close()
        logger.info("✅ Kafka connection successful")
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        logger.error("Please ensure Kafka is running on localhost:29092")
        return 1
    
    # Run Flink
    try:
        logger.info("")
        logger.info("🎯 Starting Apache Flink Mini Cluster...")
        logger.info("="*60)
        
        # Run async main
        asyncio.run(main_async())
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Flink execution stopped by user")
    except Exception as e:
        logger.error(f"❌ Flink execution failed: {e}")
        return 1
    
    logger.info("")
    logger.info("✅ Flink local execution complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
