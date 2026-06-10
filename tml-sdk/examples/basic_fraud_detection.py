#!/usr/bin/env python3
"""
Basic Fraud Detection Example
Demonstrates core TML SDK functionality with a fraud detection use case
"""

import sys
import os
import time
import random
from datetime import datetime, timedelta

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tml_sdk import TMLClient, Transaction, create_transaction


def generate_sample_transaction(is_fraud: bool = False) -> Transaction:
    """Generate a sample transaction for testing"""
    
    # Base transaction features
    base_amount = random.uniform(10, 1000)
    
    if is_fraud:
        # Fraudulent transactions tend to be higher amounts at odd hours
        amount = base_amount * random.uniform(2, 10)
        hour = random.choice([2, 3, 4, 23, 0, 1])  # Late night/early morning
        merchant_category_code = random.choice([0, 1, 2])  # 0=online, 1=gas_station, 2=atm
        location_risk = random.uniform(0.7, 1.0)  # High risk location
    else:
        # Normal transactions
        amount = base_amount
        hour = random.randint(8, 22)  # Normal business hours
        merchant_category_code = random.choice([3, 4, 5, 6])  # 3=grocery, 4=restaurant, 5=retail, 6=pharmacy
        location_risk = random.uniform(0.0, 0.3)  # Low risk location
    
    day_of_week = random.randint(0, 6)
    
    features = {
        "amount": round(amount, 2),
        "hour": hour,
        "merchant_category": merchant_category_code,  # Use numeric code instead of string
        "location_risk": location_risk,
        "day_of_week": day_of_week,
        "is_weekend": 1 if day_of_week in [5, 6] else 0,  # Convert to numeric
        "transaction_count_1h": random.randint(1, 10),
        "avg_amount_7d": random.uniform(50, 500)
    }
    
    return create_transaction(
        features=features,
        label=1 if is_fraud else 0,
        source="fraud_detection_demo",
        user_id=f"user_{random.randint(1000, 9999)}",
        region="US-CA"
    )


def main():
    """Main fraud detection demo"""
    print("🔍 TML SDK - Fraud Detection Demo")
    print("=" * 50)
    
    # Initialize TML Client
    print("\n1. Initializing TML Client...")
    client = TMLClient(
        api_url="http://localhost:8000",
        api_key="demo-key-12345"
    )
    
    try:
        # Test connection (will work in offline mode too)
        print(f"   Client initialized for: {client.config.api_url}")
        print(f"   Connection status: {'Connected' if client.is_connected() else 'Offline mode'}")
        
        # Create a fraud detection model
        print("\n2. Creating Fraud Detection Model...")
        model = client.models.create(
            name="fraud_detector_v1",
            model_type="river_classifier",
            algorithm="logistic_regression",
            features=[
                "amount", "hour", "merchant_category", "location_risk",
                "day_of_week", "is_weekend", "transaction_count_1h", "avg_amount_7d"
            ],
            target="is_fraud",
            preprocessing_steps=[],  # Remove standard_scaler for now due to categorical features
            hyperparameters={
                "l2": 0.01,
                "intercept_lr": 0.1
            },
            metadata={
                "description": "Real-time fraud detection model",
                "version": "1.0",
                "created_by": "fraud_team"
            }
        )
        
        print(f"   ✅ Model created: {model.name}")
        print(f"   Model ID: {model.model_id}")
        print(f"   Algorithm: {model.algorithm}")
        print(f"   Features: {len(model.features)}")
        
        # Generate training data
        print("\n3. Generating Training Data...")
        training_transactions = []
        
        # Generate 80% legitimate, 20% fraudulent transactions
        for i in range(800):
            transaction = generate_sample_transaction(is_fraud=False)
            training_transactions.append(transaction)
        
        for i in range(200):
            transaction = generate_sample_transaction(is_fraud=True)
            training_transactions.append(transaction)
        
        # Shuffle the data
        random.shuffle(training_transactions)
        print(f"   ✅ Generated {len(training_transactions)} training transactions")
        print(f"   Fraud rate: {sum(1 for t in training_transactions if t.label == 1) / len(training_transactions) * 100:.1f}%")
        
        # Train the model with online learning
        print("\n4. Training Model (Online Learning)...")
        correct_predictions = 0
        total_predictions = 0
        
        for i, transaction in enumerate(training_transactions):
            # Make prediction before learning (if not the first transaction)
            if i > 0:
                try:
                    prediction = model.predict_one(transaction.features)
                    predicted_class = 1 if prediction > 0.5 else 0
                    
                    if predicted_class == transaction.label:
                        correct_predictions += 1
                    total_predictions += 1
                    
                    # Add prediction to transaction
                    transaction.add_prediction(model.model_id, prediction, confidence=abs(prediction - 0.5) * 2)
                    
                except Exception:
                    pass  # Skip prediction for early samples
            
            # Learn from the transaction
            model.learn_one(transaction.features, transaction.label)
            
            # Progress update
            if (i + 1) % 200 == 0:
                accuracy = correct_predictions / max(total_predictions, 1) * 100
                print(f"   Progress: {i + 1}/{len(training_transactions)} - Accuracy: {accuracy:.1f}%")
        
        final_accuracy = correct_predictions / max(total_predictions, 1) * 100
        print(f"   ✅ Training completed - Final accuracy: {final_accuracy:.1f}%")
        
        # Update model status
        model.set_status("trained")
        model.update_metrics({
            "training_accuracy": final_accuracy,
            "training_samples": len(training_transactions),
            "fraud_rate": sum(1 for t in training_transactions if t.label == 1) / len(training_transactions)
        })
        
        # Test with new transactions
        print("\n5. Testing with New Transactions...")
        test_transactions = []
        
        # Generate test data
        for i in range(50):
            is_fraud = random.random() < 0.2  # 20% fraud rate
            transaction = generate_sample_transaction(is_fraud=is_fraud)
            test_transactions.append(transaction)
        
        # Make predictions
        test_correct = 0
        fraud_detected = 0
        high_confidence_predictions = 0
        
        # Category mapping for display
        category_names = {0: "online", 1: "gas_station", 2: "atm", 3: "grocery", 4: "restaurant", 5: "retail", 6: "pharmacy"}
        
        print("\n   Recent Predictions:")
        print("   " + "-" * 80)
        print("   Transaction ID       | Amount  | Hour | Category    | Pred | Conf | Actual")
        print("   " + "-" * 80)
        
        for transaction in test_transactions[-10:]:  # Show last 10
            prediction = model.predict_one(transaction.features)
            predicted_class = 1 if prediction > 0.5 else 0
            confidence = abs(prediction - 0.5) * 2
            
            # Add prediction to transaction
            transaction.add_prediction(model.model_id, prediction, confidence=confidence)
            
            # Statistics
            if predicted_class == transaction.label:
                test_correct += 1
            if predicted_class == 1:
                fraud_detected += 1
            if confidence > 0.8:
                high_confidence_predictions += 1
            
            # Display
            status = "✅" if predicted_class == transaction.label else "❌"
            fraud_label = "FRAUD" if transaction.label == 1 else "LEGIT"
            pred_label = "FRAUD" if predicted_class == 1 else "LEGIT"
            category_name = category_names.get(transaction.features['merchant_category'], 'unknown')
            
            print(f"   {transaction.transaction_id[:16]:<16} | "
                  f"${transaction.features['amount']:>6.2f} | "
                  f"{transaction.features['hour']:>4} | "
                  f"{category_name:<11} | "
                  f"{pred_label:<5} | "
                  f"{confidence:>4.2f} | "
                  f"{fraud_label} {status}")
        
        test_accuracy = test_correct / len(test_transactions) * 100
        print("   " + "-" * 80)
        print(f"   Test Accuracy: {test_accuracy:.1f}%")
        print(f"   Fraud Detected: {fraud_detected}")
        print(f"   High Confidence: {high_confidence_predictions}")
        
        # Model information
        print("\n6. Model Information...")
        model_info = model.get_info()
        print(f"   Model Status: {model_info['status']}")
        print(f"   Predictions Made: {model.prediction_count}")
        print(f"   Learning Updates: {model.learning_count}")
        print(f"   Current Metrics: {model_info.get('current_metrics', {})}")
        
        # Feature importance (if available)
        feature_importance = model.get_feature_importance()
        if feature_importance:
            print("\n   Feature Importance:")
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            for feature, importance in sorted_features[:5]:
                print(f"     {feature}: {importance:.4f}")
        
        # Save model
        print("\n7. Saving Model...")
        save_path = f"fraud_model_{model.model_id[:8]}.pkl"
        model.save(save_path)
        print(f"   ✅ Model saved to: {save_path}")
        
        # Simulate real-time processing
        print("\n8. Real-time Processing Simulation...")
        print("   Processing live transactions...")
        
        for i in range(5):
            # Generate a new transaction
            is_fraud = random.random() < 0.15  # 15% fraud rate
            transaction = generate_sample_transaction(is_fraud=is_fraud)
            
            # Process in real-time
            start_time = time.time()
            prediction = model.predict_one(transaction.features)
            processing_time = (time.time() - start_time) * 1000  # ms
            
            predicted_class = 1 if prediction > 0.5 else 0
            confidence = abs(prediction - 0.5) * 2
            
            # Learn from the transaction (in real deployment, this would happen after label confirmation)
            model.learn_one(transaction.features, transaction.label)
            
            # Display result
            result = "🚨 FRAUD ALERT" if predicted_class == 1 else "✅ Legitimate"
            actual = "FRAUD" if transaction.label == 1 else "LEGIT"
            
            print(f"   Transaction {i+1}: {result} (confidence: {confidence:.2f}) "
                  f"- Actual: {actual} - Processing: {processing_time:.1f}ms")
            
            time.sleep(0.5)  # Simulate real-time delay
        
        print("\n🎉 Fraud Detection Demo Completed Successfully!")
        print("\nKey Features Demonstrated:")
        print("  ✅ Model creation and configuration")
        print("  ✅ Online learning with streaming data")
        print("  ✅ Real-time predictions")
        print("  ✅ Model performance tracking")
        print("  ✅ Feature importance analysis")
        print("  ✅ Model persistence")
        print("  ✅ Real-time transaction processing")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        client.disconnect()


if __name__ == "__main__":
    main()
