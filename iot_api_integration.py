#!/usr/bin/env python3
"""
IoT API Integration for TML Platform

This integrates the IoT anomaly detection with the TML API server.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from iot_anomaly_detector import IoTSensorSimulator, IoTAnomalyDetector

API_BASE_URL = "http://localhost:8000"

async def send_to_api(session, endpoint, data):
    """Send data to TML API."""
    try:
        async with session.post(f"{API_BASE_URL}{endpoint}", json=data) as response:
            return await response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return None

async def run_iot_with_api(duration_seconds: int = 60, devices: int = 5):
    """Run IoT simulation with API integration."""
    
    print("=" * 80)
    print("🌡️  IoT Temperature Anomaly Detection with TML API Integration")
    print("=" * 80)
    print(f"Simulating {devices} IoT devices for {duration_seconds} seconds")
    print(f"API Server: {API_BASE_URL}")
    print("-" * 80)
    
    # Create simulators
    simulators = [
        IoTSensorSimulator(f"sensor_{i:03d}", f"Edge_{i:02d}")
        for i in range(1, devices + 1)
    ]
    
    async with aiohttp.ClientSession() as session:
        # Check API connection
        try:
            async with session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    health = await response.json()
                    print(f"✅ Connected to TML API - {health['models_active']} models active\n")
                else:
                    print("⚠️ API not responding properly")
                    return
        except:
            print("❌ Cannot connect to API. Start the API server first:")
            print("   python ui_api_server.py")
            return
        
        # Main simulation loop
        start_time = asyncio.get_event_loop().time()
        reading_count = 0
        
        try:
            while asyncio.get_event_loop().time() - start_time < duration_seconds:
                for simulator in simulators:
                    # Generate sensor reading
                    reading = simulator.generate_sensor_reading()
                    reading_count += 1
                    
                    # Create model via API if not exists
                    model_data = {
                        "transaction_id": f"iot_{reading['device_id']}_{reading_count}",
                        "user_id": reading["device_id"],
                        "model_type": "logistic_regression"
                    }
                    
                    # Try to get existing model or create new one
                    model_response = await send_to_api(session, "/api/models/create", model_data)
                    
                    if model_response:
                        model_id = model_response["id"]
                        
                        # Extract features for prediction
                        features = {
                            "humidity": reading["humidity"],
                            "pressure": reading["pressure"],
                            "vibration": reading["vibration"],
                            "power_draw": reading["power_draw"],
                            "cpu_load": reading["cpu_load"],
                            "fan_speed": reading["fan_speed"],
                            "ambient_temp": reading["ambient_temp"],
                            "hour_of_day": reading["hour_of_day"],
                        }
                        
                        # Make prediction via API
                        predict_data = {
                            "model_id": model_id,
                            "features": features
                        }
                        
                        predictions = await send_to_api(session, "/api/predict", predict_data)
                        
                        if predictions and len(predictions) > 0:
                            prediction = predictions[0]["prediction"]
                            
                            # Display results
                            temp = reading["temperature"]
                            actual = reading["is_anomaly"]
                            
                            temp_color = "\033[91m" if temp > 110 else "\033[92m"
                            pred_symbol = "⚠️ " if prediction else "✓"
                            
                            print(f"{reading_count:4d} | {reading['device_id']} | "
                                  f"Temp: {temp_color}{temp:6.1f}°F\033[0m | "
                                  f"API Predicted: {pred_symbol} | "
                                  f"Actual: {'🔥' if actual else '❄️'} | "
                                  f"Model: {model_id[-8:]}")
                            
                            # Train model with actual outcome
                            train_data = {
                                "model_id": model_id,
                                "features": features,
                                "target": actual
                            }
                            
                            await send_to_api(session, "/api/models/train", train_data)
                            
                            # Alert on anomaly
                            if prediction and temp > 100:
                                print(f"  🚨 ALERT: Model {model_id[-8:]} predicts anomaly!")
                                print(f"     Factors: CPU={reading['cpu_load']:.1f}%, "
                                      f"Fan={reading['fan_speed']:.0f}RPM, "
                                      f"Power={reading['power_draw']:.1f}W")
                    
                    await asyncio.sleep(0.5)  # Rate limiting
                
                # Get statistics from API
                if reading_count % 20 == 0:
                    async with session.get(f"{API_BASE_URL}/api/stats") as response:
                        if response.status == 200:
                            stats = await response.json()
                            print("\n📊 API Statistics:")
                            print(f"  Total Models: {stats['total_models']}")
                            print(f"  Total Updates: {stats['total_updates']}")
                            print(f"  Total Predictions: {stats['total_predictions']}")
                            print(f"  Average Accuracy: {stats['average_accuracy']:.2%}")
                            print("-" * 80)
                
        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user")
        
        # Final statistics
        print("\n" + "=" * 80)
        print("📈 Final API Statistics")
        print("=" * 80)
        
        async with session.get(f"{API_BASE_URL}/api/stats") as response:
            if response.status == 200:
                stats = await response.json()
                print(f"  Total Models Created: {stats['total_models']}")
                print(f"  Total Training Updates: {stats['total_updates']}")
                print(f"  Total Predictions Made: {stats['total_predictions']}")
                print(f"  Average Model Accuracy: {stats['average_accuracy']:.2%}")
                
                if stats['models']:
                    print("\n📊 Model Details:")
                    for model in stats['models'][:5]:  # Show first 5
                        print(f"    {model['id']}: {model['updates']} updates")
        
        print("\n✅ Successfully demonstrated IoT anomaly detection with TML API integration!")
        print("   Each sensor reading created a model that learned to predict temperature anomalies.")

if __name__ == "__main__":
    import sys
    
    # Make sure API server is running
    print("Make sure the TML API server is running:")
    print("  python ui_api_server.py")
    print()
    
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    devices = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    asyncio.run(run_iot_with_api(duration, devices))
