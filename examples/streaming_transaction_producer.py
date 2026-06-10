#!/usr/bin/env python3
"""Real-time Transaction Producer for TML Platform UAT."""

import json
import random
import time
from datetime import datetime
from typing import Dict, List

from kafka import KafkaProducer
from loguru import logger

from tml.core.config import config


class TransactionGenerator:
    """Generate realistic transaction data for UAT testing."""
    
    def __init__(self):
        """Initialize transaction generator."""
        self.transaction_id = 1
        self.merchant_types = [
            "grocery", "gas_station", "restaurant", "retail", "online",
            "pharmacy", "hotel", "airline", "subscription", "utility"
        ]
        self.locations = [
            "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
            "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
            "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL"
        ]
        self.user_profiles = self._generate_user_profiles()
    
    def _generate_user_profiles(self) -> List[Dict]:
        """Generate diverse user spending profiles."""
        profiles = []
        for i in range(100):  # 100 different users
            profile = {
                "user_id": f"user_{i:03d}",
                "avg_transaction": random.uniform(25, 500),
                "spending_pattern": random.choice(["conservative", "moderate", "high_spender"]),
                "preferred_merchants": random.sample(self.merchant_types, 3),
                "risk_score": random.uniform(0.1, 0.9)
            }
            profiles.append(profile)
        return profiles
    
    def generate_transaction(self) -> Dict:
        """Generate a single realistic transaction."""
        user = random.choice(self.user_profiles)
        
        # Base amount influenced by user profile
        base_amount = user["avg_transaction"]
        variation = random.uniform(0.5, 2.0)
        amount = round(base_amount * variation, 2)
        
        # Merchant type influenced by user preferences
        if random.random() < 0.7:  # 70% chance of preferred merchant
            merchant_type = random.choice(user["preferred_merchants"])
        else:
            merchant_type = random.choice(self.merchant_types)
        
        # Generate features for ML model
        hour = datetime.now().hour
        is_weekend = datetime.now().weekday() >= 5
        
        transaction = {
            "transaction_id": f"tx_{self.transaction_id:06d}",
            "user_id": user["user_id"],
            "amount": amount,
            "merchant_type": merchant_type,
            "location": random.choice(self.locations),
            "timestamp": datetime.now().isoformat(),
            "features": {
                "amount_normalized": min(amount / 1000.0, 1.0),  # Normalize to 0-1
                "hour_of_day": hour / 24.0,
                "is_weekend": float(is_weekend),
                "merchant_risk": self._get_merchant_risk(merchant_type),
                "user_risk_score": user["risk_score"],
                "amount_vs_avg": amount / user["avg_transaction"],
                "location_hash": hash(random.choice(self.locations)) % 100 / 100.0
            },
            "model_id": f"fraud_detection_{user['spending_pattern']}"
        }
        
        self.transaction_id += 1
        return transaction
    
    def _get_merchant_risk(self, merchant_type: str) -> float:
        """Get risk score for merchant type."""
        risk_scores = {
            "online": 0.8, "gas_station": 0.3, "grocery": 0.1,
            "restaurant": 0.2, "retail": 0.4, "pharmacy": 0.1,
            "hotel": 0.6, "airline": 0.5, "subscription": 0.7, "utility": 0.1
        }
        return risk_scores.get(merchant_type, 0.5)


class StreamingTransactionProducer:
    """Kafka producer for streaming transaction data."""
    
    def __init__(self):
        """Initialize the streaming producer."""
        self.generator = TransactionGenerator()
        self.producer = KafkaProducer(
            bootstrap_servers=config.kafka.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=1,
            enable_idempotence=True
        )
        self.sent_count = 0
        self.start_time = time.time()
    
    def send_transaction(self, transaction: Dict) -> bool:
        """Send a transaction to Kafka."""
        try:
            future = self.producer.send(
                topic="transactions",
                key=transaction["transaction_id"],
                value=transaction
            )
            
            # Wait for send to complete
            future.get(timeout=10)
            self.sent_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            return False
    
    def run_continuous_stream(self, transactions_per_second: float = 10.0, duration_minutes: int = 5):
        """Run continuous transaction stream."""
        logger.info(f"Starting transaction stream: {transactions_per_second} TPS for {duration_minutes} minutes")
        
        interval = 1.0 / transactions_per_second
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time:
            start_batch = time.time()
            
            # Generate and send transaction
            transaction = self.generator.generate_transaction()
            success = self.send_transaction(transaction)
            
            if success:
                logger.info(f"Sent transaction {transaction['transaction_id']}: "
                          f"${transaction['amount']:.2f} - {transaction['merchant_type']}")
            
            # Report metrics every 100 transactions
            if self.sent_count % 100 == 0:
                self.report_metrics()
            
            # Maintain rate
            elapsed = time.time() - start_batch
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)
        
        self.shutdown()
    
    def run_burst_test(self, burst_size: int = 50, bursts: int = 3, burst_interval: int = 30):
        """Run burst testing pattern."""
        logger.info(f"Starting burst test: {burst_size} transactions x {bursts} bursts")
        
        for burst_num in range(bursts):
            logger.info(f"Starting burst {burst_num + 1}/{bursts}")
            
            # Send burst of transactions
            for i in range(burst_size):
                transaction = self.generator.generate_transaction()
                success = self.send_transaction(transaction)
                
                if success:
                    logger.info(f"Burst {burst_num + 1} - Transaction {i + 1}/{burst_size}: "
                              f"${transaction['amount']:.2f}")
                
                # Small delay within burst
                time.sleep(0.1)
            
            self.report_metrics()
            
            # Wait between bursts
            if burst_num < bursts - 1:
                logger.info(f"Waiting {burst_interval}s before next burst...")
                time.sleep(burst_interval)
        
        self.shutdown()
    
    def report_metrics(self):
        """Report producer metrics."""
        elapsed = time.time() - self.start_time
        rate = self.sent_count / elapsed if elapsed > 0 else 0
        
        metrics = {
            "transactions_sent": self.sent_count,
            "rate_tps": round(rate, 2),
            "elapsed_seconds": round(elapsed, 1)
        }
        
        logger.info(f"Producer Metrics: {metrics}")
    
    def shutdown(self):
        """Clean shutdown."""
        logger.info("Shutting down transaction producer...")
        self.report_metrics()
        self.producer.flush()
        self.producer.close()
        logger.info(f"Transaction producer stopped. Sent {self.sent_count} transactions")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TML Transaction Producer for UAT")
    parser.add_argument("--mode", choices=["continuous", "burst"], default="continuous",
                       help="Streaming mode")
    parser.add_argument("--tps", type=float, default=5.0,
                       help="Transactions per second (continuous mode)")
    parser.add_argument("--duration", type=int, default=5,
                       help="Duration in minutes (continuous mode)")
    parser.add_argument("--burst-size", type=int, default=50,
                       help="Transactions per burst (burst mode)")
    parser.add_argument("--bursts", type=int, default=3,
                       help="Number of bursts (burst mode)")
    
    args = parser.parse_args()
    
    producer = StreamingTransactionProducer()
    
    try:
        if args.mode == "continuous":
            producer.run_continuous_stream(args.tps, args.duration)
        else:
            producer.run_burst_test(args.burst_size, args.bursts)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        producer.shutdown()
    except Exception as e:
        logger.error(f"Producer failed: {e}")
        producer.shutdown()


if __name__ == "__main__":
    main()
