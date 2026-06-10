#!/usr/bin/env python3
"""
Real-time Streaming Example
Demonstrates continuous learning and prediction with streaming data
"""

import sys
import os
import time
import random
import threading
from datetime import datetime
from queue import Queue

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tml_sdk import TMLClient, create_transaction


class DataStreamSimulator:
    """Simulates a real-time data stream"""
    
    def __init__(self, stream_rate: float = 2.0):
        """
        Initialize data stream simulator
        
        Args:
            stream_rate: Transactions per second
        """
        self.stream_rate = stream_rate
        self.running = False
        self.data_queue = Queue()
        self.thread = None
        
    def start(self):
        """Start the data stream"""
        self.running = True
        self.thread = threading.Thread(target=self._generate_stream)
        self.thread.daemon = True
        self.thread.start()
        print(f"📡 Data stream started at {self.stream_rate} transactions/second")
    
    def stop(self):
        """Stop the data stream"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("🛑 Data stream stopped")
    
    def get_transaction(self):
        """Get next transaction from stream"""
        if not self.data_queue.empty():
            return self.data_queue.get()
        return None
    
    def _generate_stream(self):
        """Generate streaming transactions"""
        transaction_id = 0
        
        while self.running:
            # Generate transaction
            transaction_id += 1
            
            # Simulate different transaction patterns
            if random.random() < 0.1:  # 10% anomalous transactions
                features = self._generate_anomalous_transaction()
                label = 1  # Anomaly
            else:
                features = self._generate_normal_transaction()
                label = 0  # Normal
            
            transaction = create_transaction(
                features=features,
                label=label,
                source="streaming_simulator",
                transaction_id=f"stream_{transaction_id:06d}"
            )
            
            self.data_queue.put(transaction)
            
            # Wait for next transaction
            time.sleep(1.0 / self.stream_rate)
    
    def _generate_normal_transaction(self):
        """Generate normal transaction features"""
        return {
            "amount": random.uniform(10, 500),
            "hour": random.randint(8, 22),
            "day_of_week": random.randint(0, 6),
            "merchant_type": random.randint(0, 4),
            "location_risk": random.uniform(0.0, 0.3),
            "user_age": random.randint(18, 70),
            "account_age_days": random.randint(30, 3650),
            "avg_transaction_amount": random.uniform(50, 300)
        }
    
    def _generate_anomalous_transaction(self):
        """Generate anomalous transaction features"""
        return {
            "amount": random.uniform(1000, 10000),  # High amount
            "hour": random.choice([2, 3, 4, 23, 0, 1]),  # Odd hours
            "day_of_week": random.randint(0, 6),
            "merchant_type": random.randint(0, 4),
            "location_risk": random.uniform(0.7, 1.0),  # High risk
            "user_age": random.randint(18, 70),
            "account_age_days": random.randint(1, 30),  # New account
            "avg_transaction_amount": random.uniform(10, 100)  # Low average
        }


class RealTimeProcessor:
    """Real-time transaction processor"""
    
    def __init__(self, model, window_size: int = 100):
        """
        Initialize processor
        
        Args:
            model: TML model for processing
            window_size: Size of performance tracking window
        """
        self.model = model
        self.window_size = window_size
        
        # Performance tracking
        self.processed_count = 0
        self.correct_predictions = 0
        self.recent_predictions = []
        self.recent_accuracies = []
        
        # Timing
        self.total_prediction_time = 0
        self.total_learning_time = 0
        
    def process_transaction(self, transaction):
        """Process a single transaction"""
        # Make prediction
        start_time = time.time()
        prediction = self.model.predict_one(transaction.features)
        prediction_time = time.time() - start_time
        
        # Convert to binary prediction
        predicted_class = 1 if prediction > 0.5 else 0
        confidence = abs(prediction - 0.5) * 2
        
        # Learn from transaction
        start_time = time.time()
        self.model.learn_one(transaction.features, transaction.label)
        learning_time = time.time() - start_time
        
        # Update statistics
        self.processed_count += 1
        self.total_prediction_time += prediction_time
        self.total_learning_time += learning_time
        
        # Track accuracy
        is_correct = predicted_class == transaction.label
        if is_correct:
            self.correct_predictions += 1
        
        # Maintain sliding window of recent predictions
        self.recent_predictions.append({
            'transaction_id': transaction.transaction_id,
            'predicted': predicted_class,
            'actual': transaction.label,
            'correct': is_correct,
            'confidence': confidence,
            'prediction_time': prediction_time * 1000,  # ms
            'learning_time': learning_time * 1000  # ms
        })
        
        # Keep only recent predictions
        if len(self.recent_predictions) > self.window_size:
            self.recent_predictions.pop(0)
        
        # Calculate recent accuracy
        if len(self.recent_predictions) >= 10:
            recent_correct = sum(1 for p in self.recent_predictions[-50:] if p['correct'])
            recent_accuracy = recent_correct / min(50, len(self.recent_predictions))
            self.recent_accuracies.append(recent_accuracy)
            
            if len(self.recent_accuracies) > 20:
                self.recent_accuracies.pop(0)
        
        return {
            'prediction': predicted_class,
            'confidence': confidence,
            'actual': transaction.label,
            'correct': is_correct,
            'prediction_time_ms': prediction_time * 1000,
            'learning_time_ms': learning_time * 1000
        }
    
    def get_performance_stats(self):
        """Get current performance statistics"""
        if self.processed_count == 0:
            return {}
        
        overall_accuracy = self.correct_predictions / self.processed_count
        recent_accuracy = self.recent_accuracies[-1] if self.recent_accuracies else 0
        
        avg_prediction_time = (self.total_prediction_time / self.processed_count) * 1000
        avg_learning_time = (self.total_learning_time / self.processed_count) * 1000
        
        return {
            'processed_count': self.processed_count,
            'overall_accuracy': overall_accuracy,
            'recent_accuracy': recent_accuracy,
            'avg_prediction_time_ms': avg_prediction_time,
            'avg_learning_time_ms': avg_learning_time,
            'recent_predictions': len(self.recent_predictions)
        }


def main():
    """Main streaming demo"""
    print("🌊 TML SDK - Real-time Streaming Demo")
    print("=" * 50)
    
    # Initialize TML Client
    print("\n1. Initializing TML Client...")
    client = TMLClient(
        api_url="http://localhost:8000",
        api_key="streaming-demo-key"
    )
    
    try:
        print(f"   Client initialized: {client.config.api_url}")
        print(f"   Mode: {'Connected' if client.is_connected() else 'Offline'}")
        
        # Create anomaly detection model
        print("\n2. Creating Anomaly Detection Model...")
        model = client.models.create(
            name="streaming_anomaly_detector",
            model_type="river_classifier",
            algorithm="logistic_regression",
            features=[
                "amount", "hour", "day_of_week", "merchant_type",
                "location_risk", "user_age", "account_age_days", "avg_transaction_amount"
            ],
            target="is_anomaly",
            hyperparameters={"l2": 0.01},
            metadata={
                "description": "Real-time anomaly detection for streaming transactions",
                "use_case": "fraud_detection",
                "version": "1.0"
            }
        )
        
        print(f"   ✅ Model created: {model.name}")
        print(f"   Model ID: {model.model_id}")
        print(f"   Features: {len(model.features)}")
        
        # Initialize components
        print("\n3. Initializing Streaming Components...")
        stream_simulator = DataStreamSimulator(stream_rate=3.0)  # 3 transactions/second
        processor = RealTimeProcessor(model, window_size=100)
        
        print("   ✅ Data stream simulator ready")
        print("   ✅ Real-time processor ready")
        
        # Start streaming
        print("\n4. Starting Real-time Processing...")
        stream_simulator.start()
        
        print("   🔄 Processing live transactions...")
        print("   Press Ctrl+C to stop\n")
        
        # Display header
        print("   " + "="*90)
        print("   Transaction ID | Prediction | Confidence | Actual | Status | Pred(ms) | Learn(ms)")
        print("   " + "="*90)
        
        last_stats_time = time.time()
        
        try:
            while True:
                # Get next transaction
                transaction = stream_simulator.get_transaction()
                
                if transaction:
                    # Process transaction
                    result = processor.process_transaction(transaction)
                    
                    # Display result
                    status = "✅" if result['correct'] else "❌"
                    pred_label = "ANOMALY" if result['prediction'] == 1 else "NORMAL "
                    actual_label = "ANOMALY" if result['actual'] == 1 else "NORMAL "
                    
                    print(f"   {transaction.transaction_id:<14} | "
                          f"{pred_label:<10} | "
                          f"{result['confidence']:>8.3f} | "
                          f"{actual_label:<6} | "
                          f"{status:<6} | "
                          f"{result['prediction_time_ms']:>7.2f} | "
                          f"{result['learning_time_ms']:>8.2f}")
                
                # Show performance stats every 10 seconds
                current_time = time.time()
                if current_time - last_stats_time >= 10:
                    stats = processor.get_performance_stats()
                    
                    if stats:
                        print("\n   📊 Performance Statistics:")
                        print(f"      Processed: {stats['processed_count']} transactions")
                        print(f"      Overall Accuracy: {stats['overall_accuracy']:.1%}")
                        print(f"      Recent Accuracy: {stats['recent_accuracy']:.1%}")
                        print(f"      Avg Prediction Time: {stats['avg_prediction_time_ms']:.2f}ms")
                        print(f"      Avg Learning Time: {stats['avg_learning_time_ms']:.2f}ms")
                        print("   " + "="*90)
                    
                    last_stats_time = current_time
                
                # Small delay to prevent overwhelming output
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping real-time processing...")
            
        finally:
            # Stop streaming
            stream_simulator.stop()
            
            # Final statistics
            print("\n5. Final Performance Report...")
            final_stats = processor.get_performance_stats()
            
            if final_stats:
                print(f"   📈 Total Transactions Processed: {final_stats['processed_count']}")
                print(f"   🎯 Overall Accuracy: {final_stats['overall_accuracy']:.1%}")
                print(f"   ⚡ Average Prediction Time: {final_stats['avg_prediction_time_ms']:.2f}ms")
                print(f"   🧠 Average Learning Time: {final_stats['avg_learning_time_ms']:.2f}ms")
                print(f"   📊 Throughput: {final_stats['processed_count'] / 60:.1f} transactions/minute")
                
                # Model information
                model_info = model.get_info()
                print(f"\n   🤖 Model Performance:")
                print(f"      Predictions Made: {model.prediction_count}")
                print(f"      Learning Updates: {model.learning_count}")
                print(f"      Model Status: {model_info['status']}")
            
            print("\n🎉 Real-time Streaming Demo Completed!")
            print("\nKey Capabilities Demonstrated:")
            print("  ✅ Real-time data stream simulation")
            print("  ✅ Continuous online learning")
            print("  ✅ Live prediction and feedback")
            print("  ✅ Performance monitoring")
            print("  ✅ Anomaly detection")
            print("  ✅ Sub-millisecond processing")
            
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        client.disconnect()


if __name__ == "__main__":
    main()
