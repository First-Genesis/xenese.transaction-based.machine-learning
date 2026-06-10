#!/usr/bin/env python3
"""Real-time Model Updater for TML Platform UAT."""

import json
import time
from collections import defaultdict
from typing import Dict, List

import requests
from kafka import KafkaConsumer, KafkaProducer
from loguru import logger

from tml.core.config import config


class ModelPerformanceMonitor:
    """Monitor model performance and trigger updates."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.model_stats = defaultdict(lambda: {
            "predictions": 0,
            "accuracy_sum": 0.0,
            "last_update": time.time(),
            "drift_score": 0.0,
            "performance_trend": []
        })
        self.api_base_url = f"http://localhost:8000"
    
    def update_model_stats(self, model_id: str, accuracy: float, drift_score: float):
        """Update statistics for a model."""
        stats = self.model_stats[model_id]
        stats["predictions"] += 1
        stats["accuracy_sum"] += accuracy
        stats["drift_score"] = drift_score
        
        # Track performance trend (last 10 measurements)
        avg_accuracy = stats["accuracy_sum"] / stats["predictions"]
        stats["performance_trend"].append(avg_accuracy)
        if len(stats["performance_trend"]) > 10:
            stats["performance_trend"].pop(0)
    
    def should_trigger_update(self, model_id: str) -> bool:
        """Determine if model needs updating."""
        stats = self.model_stats[model_id]
        
        # Trigger conditions
        conditions = [
            # High drift score
            stats["drift_score"] > 0.7,
            
            # Performance degradation
            len(stats["performance_trend"]) >= 5 and 
            stats["performance_trend"][-1] < stats["performance_trend"][0] - 0.1,
            
            # Time-based update (every 2 minutes)
            time.time() - stats["last_update"] > 120,
            
            # Sufficient data points
            stats["predictions"] >= 50
        ]
        
        return any(conditions)
    
    def get_model_health(self, model_id: str) -> Dict:
        """Get comprehensive model health metrics."""
        stats = self.model_stats[model_id]
        
        if stats["predictions"] == 0:
            return {"status": "no_data", "health_score": 0.0}
        
        avg_accuracy = stats["accuracy_sum"] / stats["predictions"]
        
        # Calculate health score (0-1)
        health_factors = [
            min(avg_accuracy * 2, 1.0),  # Accuracy factor
            max(0, 1.0 - stats["drift_score"]),  # Drift factor
            min(stats["predictions"] / 100.0, 1.0)  # Data sufficiency factor
        ]
        
        health_score = sum(health_factors) / len(health_factors)
        
        return {
            "status": "healthy" if health_score > 0.7 else "degraded" if health_score > 0.4 else "critical",
            "health_score": health_score,
            "avg_accuracy": avg_accuracy,
            "drift_score": stats["drift_score"],
            "predictions_count": stats["predictions"],
            "last_update": stats["last_update"]
        }


class StreamingModelUpdater:
    """Monitor model performance and trigger updates via streaming."""
    
    def __init__(self):
        """Initialize the model updater."""
        self.monitor = ModelPerformanceMonitor()
        
        # Kafka consumer for model updates and metrics
        self.consumer = KafkaConsumer(
            "model-updates",
            "service-metrics",
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            group_id="tml_model_monitors",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest"
        )
        
        # Kafka producer for training requests
        self.producer = KafkaProducer(
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all"
        )
        
        self.running = False
        self.processed_updates = 0
        self.triggered_retrains = 0
        self.start_time = time.time()
    
    def trigger_model_retrain(self, model_id: str, reason: str) -> bool:
        """Trigger model retraining via API and Kafka."""
        try:
            # Send retrain request via API
            api_response = requests.post(
                f"{self.monitor.api_base_url}/api/v1/models/{model_id}/retrain",
                json={"reason": reason, "priority": "high"},
                timeout=10
            )
            
            # Send training request via Kafka
            training_request = {
                "model_id": model_id,
                "action": "retrain",
                "reason": reason,
                "timestamp": time.time(),
                "priority": "high",
                "config": {
                    "learning_rate": 0.01,
                    "batch_size": 32,
                    "max_iterations": 1000
                }
            }
            
            self.producer.send("training-requests", value=training_request)
            self.triggered_retrains += 1
            
            logger.info(f"Triggered retrain for model {model_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger retrain for {model_id}: {e}")
            return False
    
    def process_model_update(self, update_data: Dict):
        """Process model update event."""
        model_id = update_data.get("model_id")
        performance = update_data.get("performance", {})
        
        # Extract metrics
        accuracy = performance.get("accuracy", 0.8)  # Default reasonable accuracy
        drift_score = performance.get("drift_score", 0.0)
        
        # Update monitoring stats
        self.monitor.update_model_stats(model_id, accuracy, drift_score)
        
        # Check if retrain needed
        if self.monitor.should_trigger_update(model_id):
            health = self.monitor.get_model_health(model_id)
            reason = f"Health score: {health['health_score']:.2f}, Drift: {drift_score:.2f}"
            self.trigger_model_retrain(model_id, reason)
            
            # Reset last update time
            self.monitor.model_stats[model_id]["last_update"] = time.time()
    
    def process_service_metrics(self, metrics_data: Dict):
        """Process service metrics for monitoring."""
        service = metrics_data.get("service")
        metrics = metrics_data.get("metrics", {})
        
        if service == "model-trainer":
            logger.info(f"Model Trainer Status: {metrics}")
        elif service == "stream-processor":
            logger.info(f"Stream Processor Status: {metrics}")
    
    def generate_health_report(self) -> Dict:
        """Generate comprehensive health report."""
        report = {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.start_time,
            "processed_updates": self.processed_updates,
            "triggered_retrains": self.triggered_retrains,
            "monitored_models": len(self.monitor.model_stats),
            "model_health": {}
        }
        
        # Add health for each model
        for model_id in self.monitor.model_stats:
            report["model_health"][model_id] = self.monitor.get_model_health(model_id)
        
        return report
    
    def run_monitoring(self, duration_minutes: int = 10):
        """Run model monitoring for specified duration."""
        logger.info(f"Starting model monitoring for {duration_minutes} minutes...")
        self.running = True
        
        end_time = time.time() + (duration_minutes * 60)
        last_report = time.time()
        
        while self.running and time.time() < end_time:
            try:
                # Poll for messages
                messages = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    topic = topic_partition.topic
                    
                    for message in records:
                        if topic == "model-updates":
                            self.process_model_update(message.value)
                            self.processed_updates += 1
                        elif topic == "service-metrics":
                            self.process_service_metrics(message.value)
                
                # Generate periodic health reports
                if time.time() - last_report > 60:  # Every minute
                    report = self.generate_health_report()
                    logger.info(f"Health Report: {json.dumps(report, indent=2)}")
                    
                    # Publish health report
                    self.producer.send("health-reports", value=report)
                    last_report = time.time()
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)
        
        self.shutdown()
    
    def shutdown(self):
        """Clean shutdown."""
        logger.info("Shutting down model updater...")
        
        # Final report
        final_report = self.generate_health_report()
        logger.info(f"Final Health Report: {json.dumps(final_report, indent=2)}")
        
        # Cleanup
        self.consumer.close()
        self.producer.flush()
        self.producer.close()
        
        logger.info(f"Model updater stopped. Processed {self.processed_updates} updates, "
                   f"triggered {self.triggered_retrains} retrains")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TML Model Updater for UAT")
    parser.add_argument("--duration", type=int, default=10,
                       help="Monitoring duration in minutes")
    
    args = parser.parse_args()
    
    updater = StreamingModelUpdater()
    
    try:
        updater.run_monitoring(args.duration)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        updater.shutdown()
    except Exception as e:
        logger.error(f"Model updater failed: {e}")
        updater.shutdown()


if __name__ == "__main__":
    main()
