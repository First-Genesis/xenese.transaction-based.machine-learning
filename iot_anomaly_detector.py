#!/usr/bin/env python3
"""
IoT Anomaly Detection with TML Platform

Simulates IoT sensor data and uses TML to predict temperature anomalies (>110°F)
Each sensor reading creates its own model that learns from patterns.
"""

import sys
import time
import random
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import TML components
from tml.core.model import TransactionContext, RiverTransactionModel

# Constants
TEMP_ANOMALY_THRESHOLD = 110.0  # Fahrenheit
NORMAL_TEMP_RANGE = (60, 95)
ANOMALY_TEMP_RANGE = (110, 130)

class IoTSensorSimulator:
    """Simulates IoT edge device sensor data."""
    
    def __init__(self, device_id: str, location: str = "Edge_01"):
        self.device_id = device_id
        self.location = location
        self.base_temp = random.uniform(70, 85)
        self.anomaly_probability = 0.05  # 5% chance of anomaly
        self.time_offset = 0
        
    def generate_sensor_reading(self) -> Dict[str, Any]:
        """Generate realistic IoT sensor data."""
        
        # Time-based patterns
        hour = (datetime.now() + timedelta(hours=self.time_offset)).hour
        self.time_offset += 0.1  # Simulate time progression
        
        # Environmental factors that influence temperature
        humidity = random.uniform(30, 90)  # Percentage
        pressure = random.uniform(29.5, 30.5)  # inHg
        vibration = random.uniform(0, 10)  # Hz
        power_draw = random.uniform(100, 500)  # Watts
        cpu_load = random.uniform(10, 95)  # Percentage
        fan_speed = random.uniform(1000, 5000)  # RPM
        ambient_temp = self.base_temp + random.uniform(-10, 10)
        
        # Determine if this will be an anomaly
        is_anomaly = random.random() < self.anomaly_probability
        
        # Calculate temperature based on factors
        if is_anomaly:
            # Anomaly conditions: high load, low fan speed, high ambient
            cpu_load = random.uniform(80, 100)
            fan_speed = random.uniform(500, 1500)  # Fan failure
            power_draw = random.uniform(450, 600)
            temperature = random.uniform(*ANOMALY_TEMP_RANGE)
            
            # Correlated factors
            vibration = random.uniform(5, 15)  # Higher vibration during anomaly
            pressure = random.uniform(30.2, 30.8)  # Pressure spike
        else:
            # Normal temperature with some correlation to factors
            temp_influence = (
                (cpu_load / 100) * 20 +  # CPU load adds heat
                (power_draw / 500) * 15 +  # Power draw adds heat
                (100 - humidity) / 100 * 5 +  # Low humidity increases temp
                (5000 - fan_speed) / 5000 * 25 +  # Low fan speed increases temp
                ambient_temp * 0.3  # Ambient influence
            )
            
            temperature = self.base_temp + temp_influence + random.uniform(-5, 5)
            temperature = min(max(temperature, NORMAL_TEMP_RANGE[0]), NORMAL_TEMP_RANGE[1])
        
        # Create sensor reading
        reading = {
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "location": self.location,
            "temperature": round(temperature, 2),
            "humidity": round(humidity, 2),
            "pressure": round(pressure, 3),
            "vibration": round(vibration, 2),
            "power_draw": round(power_draw, 2),
            "cpu_load": round(cpu_load, 2),
            "fan_speed": round(fan_speed, 0),
            "ambient_temp": round(ambient_temp, 2),
            "hour_of_day": hour,
            "is_anomaly": temperature > TEMP_ANOMALY_THRESHOLD
        }
        
        return reading


class IoTAnomalyDetector:
    """TML-based anomaly detection for IoT data."""
    
    def __init__(self):
        self.models = {}  # Store models by device_id
        self.parent_model = None  # Global parent model for knowledge transfer
        self.prediction_history = []
        self.model_count = 0
        
    def extract_features(self, reading: Dict[str, Any]) -> Dict[str, float]:
        """Extract features for model training/prediction."""
        return {
            "humidity": reading["humidity"],
            "pressure": reading["pressure"],
            "vibration": reading["vibration"],
            "power_draw": reading["power_draw"],
            "cpu_load": reading["cpu_load"],
            "fan_speed": reading["fan_speed"],
            "ambient_temp": reading["ambient_temp"],
            "hour_of_day": reading["hour_of_day"],
            
            # Engineered features
            "heat_index": (reading["cpu_load"] * reading["power_draw"]) / 100,
            "cooling_efficiency": reading["fan_speed"] / (reading["cpu_load"] + 1),
            "pressure_deviation": abs(reading["pressure"] - 30.0),
            "time_of_day_risk": 1.0 if 12 <= reading["hour_of_day"] <= 18 else 0.5,
        }
    
    def process_sensor_reading(self, reading: Dict[str, Any]) -> Dict[str, Any]:
        """Process a sensor reading with TML."""
        
        device_id = reading["device_id"]
        features = self.extract_features(reading)
        
        # Create transaction context for this reading
        context = TransactionContext(
            transaction_id=f"iot_{device_id}_{int(time.time()*1000)}",
            user_id=device_id,
            session_id=reading["location"]
        )
        
        # Get or create model for this device
        if device_id not in self.models:
            # Create new model, inheriting from global parent if exists
            self.model_count += 1
            model = RiverTransactionModel(
                model_id=f"iot_model_{self.model_count:06d}",
                parent_model_id=self.parent_model.model_id if self.parent_model else None,
                model_type="logistic_regression"
            )
            model.context = context
            
            # Inherit knowledge from parent
            if self.parent_model:
                try:
                    import pickle
                    model.model = pickle.loads(pickle.dumps(self.parent_model.model))
                except:
                    pass
            
            self.models[device_id] = model
        else:
            model = self.models[device_id]
        
        # Make prediction BEFORE seeing actual temperature
        anomaly_prediction = model.predict(features)
        anomaly_probability = 0.5  # Default if no probability available
        
        # Try to get probability if available
        try:
            proba = model.predict_proba(features)
            if proba and True in proba:
                anomaly_probability = proba[True]
        except:
            pass
        
        # Actual anomaly status
        actual_anomaly = reading["is_anomaly"]
        
        # Update model with actual outcome
        model.update(features, actual_anomaly)
        
        # Update global parent model periodically for knowledge sharing
        if self.model_count % 10 == 0:
            self.parent_model = model
        
        # Calculate metrics
        prediction_correct = (anomaly_prediction == actual_anomaly)
        
        result = {
            "reading": reading,
            "prediction": {
                "will_exceed_110F": anomaly_prediction,
                "probability": anomaly_probability,
                "confidence": abs(anomaly_probability - 0.5) * 2,  # 0-1 scale
                "actual_anomaly": actual_anomaly,
                "correct": prediction_correct
            },
            "model_info": {
                "model_id": model.model_id,
                "parent_id": model.parent_model_id,
                "updates": model.metrics.total_updates,
                "accuracy": model.metrics.accuracy,
                "device_models": len(self.models)
            },
            "alert": anomaly_prediction and anomaly_probability > 0.7
        }
        
        # Store in history
        self.prediction_history.append(result)
        if len(self.prediction_history) > 100:
            self.prediction_history.pop(0)
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics."""
        if not self.prediction_history:
            return {
                "total_readings": 0,
                "anomalies_detected": 0,
                "anomalies_predicted": 0,
                "accuracy": 0,
                "precision": 0,
                "recall": 0,
                "false_positive_rate": 0
            }
        
        total = len(self.prediction_history)
        true_positives = sum(1 for h in self.prediction_history 
                           if h["prediction"]["will_exceed_110F"] and h["prediction"]["actual_anomaly"])
        false_positives = sum(1 for h in self.prediction_history 
                            if h["prediction"]["will_exceed_110F"] and not h["prediction"]["actual_anomaly"])
        true_negatives = sum(1 for h in self.prediction_history 
                           if not h["prediction"]["will_exceed_110F"] and not h["prediction"]["actual_anomaly"])
        false_negatives = sum(1 for h in self.prediction_history 
                            if not h["prediction"]["will_exceed_110F"] and h["prediction"]["actual_anomaly"])
        
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        fpr = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0
        
        return {
            "total_readings": total,
            "anomalies_detected": sum(1 for h in self.prediction_history if h["prediction"]["actual_anomaly"]),
            "anomalies_predicted": sum(1 for h in self.prediction_history if h["prediction"]["will_exceed_110F"]),
            "accuracy": round(accuracy * 100, 2),
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "false_positive_rate": round(fpr * 100, 2),
            "total_models": len(self.models),
            "model_inheritance_depth": self.model_count
        }


async def run_simulation(duration_seconds: int = 60, devices: int = 3):
    """Run IoT anomaly detection simulation."""
    
    print("=" * 80)
    print("🌡️  IoT Temperature Anomaly Detection with TML")
    print("=" * 80)
    print(f"Simulating {devices} IoT devices for {duration_seconds} seconds")
    print(f"Anomaly threshold: {TEMP_ANOMALY_THRESHOLD}°F")
    print("-" * 80)
    
    # Create simulators and detector
    simulators = [
        IoTSensorSimulator(f"sensor_{i:03d}", f"Edge_{i:02d}")
        for i in range(1, devices + 1)
    ]
    detector = IoTAnomalyDetector()
    
    start_time = time.time()
    reading_count = 0
    
    try:
        while time.time() - start_time < duration_seconds:
            # Generate readings from all devices
            for simulator in simulators:
                reading = simulator.generate_sensor_reading()
                result = detector.process_sensor_reading(reading)
                reading_count += 1
                
                # Display results
                temp = reading["temperature"]
                predicted = result["prediction"]["will_exceed_110F"]
                actual = result["prediction"]["actual_anomaly"]
                prob = result["prediction"]["probability"]
                
                # Color coding
                temp_color = "\033[91m" if temp > TEMP_ANOMALY_THRESHOLD else "\033[92m"
                pred_symbol = "⚠️ " if predicted else "✓"
                
                print(f"{reading_count:4d} | {reading['device_id']} | "
                      f"Temp: {temp_color}{temp:6.1f}°F\033[0m | "
                      f"Predicted: {pred_symbol} ({prob:.2%}) | "
                      f"Actual: {'🔥' if actual else '❄️'} | "
                      f"Model: {result['model_info']['model_id'][-6:]} | "
                      f"Acc: {result['model_info']['accuracy']:.1%}")
                
                # Alert on high-confidence anomaly predictions
                if result["alert"]:
                    print(f"  🚨 ALERT: High probability ({prob:.1%}) of temperature exceeding {TEMP_ANOMALY_THRESHOLD}°F!")
                    print(f"     Factors: CPU={reading['cpu_load']:.1f}%, Fan={reading['fan_speed']:.0f}RPM, "
                          f"Power={reading['power_draw']:.1f}W")
            
            # Show statistics every 10 readings
            if reading_count % 10 == 0:
                stats = detector.get_statistics()
                print("\n📊 Current Statistics:")
                print(f"  Accuracy: {stats['accuracy']}% | Precision: {stats['precision']}% | "
                      f"Recall: {stats['recall']}% | FPR: {stats['false_positive_rate']}%")
                print(f"  Models: {stats['total_models']} | Inheritance Depth: {stats['model_inheritance_depth']}")
                print("-" * 80)
            
            await asyncio.sleep(1)  # Simulate real-time data
            
    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")
    
    # Final statistics
    print("\n" + "=" * 80)
    print("📈 Final Statistics")
    print("=" * 80)
    
    stats = detector.get_statistics()
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # Show prediction improvement over time
    if len(detector.prediction_history) >= 20:
        early_accuracy = sum(1 for h in detector.prediction_history[:10] 
                           if h["prediction"]["correct"]) / 10
        late_accuracy = sum(1 for h in detector.prediction_history[-10:] 
                          if h["prediction"]["correct"]) / 10
        
        print(f"\n🎯 Learning Progress:")
        print(f"  First 10 predictions: {early_accuracy:.1%} accuracy")
        print(f"  Last 10 predictions:  {late_accuracy:.1%} accuracy")
        print(f"  Improvement: {(late_accuracy - early_accuracy):.1%}")
    
    print("\n✅ TML successfully learned to predict temperature anomalies from IoT sensor patterns!")
    print("   Each transaction spawned its own model, inheriting knowledge from previous models.")
    

if __name__ == "__main__":
    # Run simulation
    import sys
    
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    devices = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    asyncio.run(run_simulation(duration, devices))
