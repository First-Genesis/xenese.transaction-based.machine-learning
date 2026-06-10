#!/usr/bin/env python3
"""Production Model Trainer Service for TML Platform UAT."""

import asyncio
import json
import signal
import sys
import time
from typing import Any, Dict, Optional

from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from tml.core.config import config
from tml.core.registry import ModelRegistry
from tml.learning.online_learner import OnlineLearningEngine


class ModelTrainerService:
    """Production model training service that consumes from Kafka and trains models."""

    def __init__(self):
        """Initialize the model trainer service."""
        self.running = False
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
        self.learning_engine = OnlineLearningEngine(
            default_algorithm=config.model.base_model_type
        )
        self.registry = ModelRegistry()
        self.processed_count = 0
        self.model_updates = 0
        self.start_time = time.time()

    def initialize(self):
        """Initialize Kafka connections and setup signal handlers."""
        logger.info("Initializing Model Trainer Service...")
        
        # Setup Kafka consumer
        self.consumer = KafkaConsumer(
            "transactions",
            "training-requests",
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            group_id="tml_model_trainers",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        
        # Setup Kafka producer for model updates
        self.producer = KafkaProducer(
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
        )
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Model Trainer Service initialized successfully")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def train_model_async(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Train model with transaction data asynchronously."""
        try:
            # Extract model ID and features
            model_id = transaction_data.get("model_id", "default")
            features = transaction_data.get("features", {})
            target = transaction_data.get("amount", 0.0)
            
            # Perform online learning
            success = self.learning_engine.learn(
                model_id=model_id,
                features=features,
                target=target
            )
            
            if success:
                self.model_updates += 1
                
                # Publish model update event
                update_event = {
                    "model_id": model_id,
                    "timestamp": time.time(),
                    "update_type": "incremental",
                    "features_processed": len(features),
                    "target_value": target
                }
                
                self.producer.send("model-updates", value=update_event)
                logger.info(f"Model {model_id} updated successfully")
            
            return {
                "success": True,
                "model_id": model_id,
                "updated": success
            }
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return {"success": False, "error": str(e)}

    def process_message(self, message):
        """Process a single Kafka message."""
        try:
            transaction_data = message.value
            
            # Run async training in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.train_model_async(transaction_data))
            loop.close()
            
            self.processed_count += 1
            
            if self.processed_count % 100 == 0:
                self.report_metrics()
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def report_metrics(self):
        """Report service metrics."""
        uptime = time.time() - self.start_time
        rate = self.processed_count / uptime if uptime > 0 else 0
        
        metrics = {
            "processed_transactions": self.processed_count,
            "model_updates": self.model_updates,
            "processing_rate": f"{rate:.2f} tx/sec",
            "uptime_seconds": uptime,
            "active_models": len(self.learning_engine.learners)
        }
        
        logger.info(f"Model Trainer Metrics: {metrics}")
        
        # Publish metrics
        self.producer.send("service-metrics", value={
            "service": "model-trainer",
            "metrics": metrics,
            "timestamp": time.time()
        })

    def run(self):
        """Main service loop."""
        self.running = True
        logger.info("Model Trainer Service started, waiting for messages...")
        
        while self.running:
            try:
                # Poll for messages with timeout
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for message in records:
                        self.process_message(message)
                        
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)  # Brief pause before retrying
        
        self.shutdown()

    def shutdown(self):
        """Clean shutdown of the service."""
        logger.info("Shutting down Model Trainer Service...")
        
        # Report final metrics
        self.report_metrics()
        
        # Clean up connections
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        
        logger.info(f"Model Trainer Service stopped. Processed {self.processed_count} transactions")


def main():
    """Main entry point for the service."""
    logger.info("Starting TML Model Trainer Service for Production UAT")
    
    service = ModelTrainerService()
    service.initialize()
    
    try:
        service.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
