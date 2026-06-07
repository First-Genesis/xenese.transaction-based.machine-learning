#!/usr/bin/env python3
"""
Demonstration: Local Demo → Docker API (C# Proto.Actor)
Shows the C# Proto.Actor system in Docker processing requests
"""

import requests
import json
import time
import numpy as np
from datetime import datetime

# Docker API endpoint
API_URL = "http://localhost:5001"

def demo_header():
    print("=" * 70)
    print("🐳 DOCKER C# PROTO.ACTOR DEMONSTRATION")
    print("=" * 70)
    print("\nThis shows the C# Proto.Actor system (in Docker) processing requests")
    print("from our local demo environment.\n")
    print("Architecture:")
    print("  [Local Demo] → HTTP → [Docker API:5001] → [C# Proto.Actor System]")
    print("=" * 70)

def create_transaction_via_docker_api(x, y, thickness):
    """Send transaction to Docker API which uses C# Proto.Actor"""
    
    transaction = {
        "data": {
            "xCoord": x,
            "yCoord": y,
            "thickness": thickness,
            "minThickness": 15.0,
            "quality": 0.95,
            "features": {
                "feature1": np.random.random(),
                "feature2": np.random.random()
            }
        },
        "source": "demo-to-docker",
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "demo_test": True,
            "processing_system": "C# Proto.Actor in Docker"
        }
    }
    
    print(f"\n📤 Sending to Docker API (C# Proto.Actor):")
    print(f"   Location: X={x}, Y={y}")
    print(f"   Thickness: {thickness:.2f}mm")
    
    try:
        response = requests.post(
            f"{API_URL}/api/transactions",
            json=transaction,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ C# Proto.Actor Processed Successfully!")
            print(f"   🔹 Transaction ID: {result['transactionId']}")
            print(f"   🔹 Model ID: {result['modelId']}")
            print(f"   🔹 Status: {result['status']}")
            print(f"   🔹 Processing Time: {result['processingTimeMs']:.2f}ms")
            print(f"   🔹 Physics Valid: {result['physicsValid']}")
            print(f"   🔹 Inheritance Depth: {result.get('inheritanceDepth', 0)}")
            print(f"   🔹 Confidence: {result.get('confidence', 0)}")
            return result
        else:
            print(f"❌ Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def simulate_cscan_pipeline_inspection():
    """Simulate C-Scan pipeline inspection using Docker API"""
    
    print("\n" + "="*70)
    print("🔬 SIMULATING C-SCAN PIPELINE INSPECTION")
    print("="*70)
    print("\nProcessing pipeline thickness measurements through Docker C# Proto.Actor...")
    
    # Simulate scanning a pipeline section
    scan_points = [
        (100, 850, 19.5),  # Normal thickness
        (102, 850, 19.3),  # Slight reduction
        (104, 850, 18.8),  # More reduction
        (106, 850, 18.2),  # Approaching critical
        (108, 850, 17.5),  # Below normal
        (110, 850, 14.8),  # Critical - below minimum
        (112, 850, 16.2),  # Recovery
        (114, 850, 18.9),  # Normal again
    ]
    
    results = []
    for i, (x, y, thickness) in enumerate(scan_points, 1):
        print(f"\n{'='*50}")
        print(f"📍 Scan Point {i}/{len(scan_points)}")
        
        result = create_transaction_via_docker_api(x, y, thickness)
        if result:
            results.append(result)
            
            # Check for critical conditions
            if thickness < 15.0:
                print(f"\n⚠️  ALERT: Critical thickness detected!")
                print(f"   Thickness {thickness:.2f}mm is below minimum 15.0mm")
                print(f"   C# Proto.Actor marked physics_valid = {result.get('physicsValid', False)}")
        
        time.sleep(0.5)  # Small delay between measurements
    
    return results

def show_statistics():
    """Get statistics from Docker API"""
    
    print("\n" + "="*70)
    print("📊 STATISTICS FROM DOCKER C# PROTO.ACTOR SYSTEM")
    print("="*70)
    
    try:
        # Transaction statistics
        response = requests.get(f"{API_URL}/api/transactions/statistics")
        if response.status_code == 200:
            stats = response.json()
            print("\n📈 Transaction Statistics:")
            print(f"   Total Processed: {stats.get('totalCount', 0)}")
            print(f"   Average Processing Time: {stats.get('averageProcessingTimeMs', 0):.2f}ms")
            
            # Show recent transactions
            recent = stats.get('recentTransactions', [])
            if recent:
                print(f"\n   Recent Transactions (last {len(recent)}):")
                for tx in recent[:3]:
                    print(f"      • {tx.get('id', 'N/A')}: {tx.get('status', 'N/A')}")
        
        # Model statistics
        response = requests.get(f"{API_URL}/api/models/statistics")
        if response.status_code == 200:
            stats = response.json()
            print("\n🤖 Model Statistics:")
            print(f"   Total Models Created: {stats.get('totalCount', 0)}")
            print(f"   Average Confidence: {stats.get('averageConfidence', 0):.3f}")
            print(f"   Average R²: {stats.get('averageRSquared', 0):.3f}")
            
    except Exception as e:
        print(f"❌ Could not retrieve statistics: {e}")

def main():
    """Run the demonstration"""
    
    demo_header()
    
    # Check API health
    print("\n🔍 Checking Docker API Status...")
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            print("✅ Docker API (C# Proto.Actor) is running!")
        else:
            print("❌ Docker API not responding correctly")
            return
    except:
        print("❌ Cannot connect to Docker API at http://localhost:5001")
        print("   Make sure the Docker container is running:")
        print("   docker ps | grep tml-api-test")
        return
    
    # Run the simulation
    results = simulate_cscan_pipeline_inspection()
    
    # Show statistics
    show_statistics()
    
    # Summary
    print("\n" + "="*70)
    print("🎯 DEMONSTRATION COMPLETE")
    print("="*70)
    print(f"\n✅ Successfully processed {len(results)} transactions")
    print("   All processing done by C# Proto.Actor in Docker container")
    print("\n💡 What happened:")
    print("   1. Demo sent HTTP requests to localhost:5001")
    print("   2. Docker container received the requests")
    print("   3. C# Proto.Actor system processed each transaction")
    print("   4. Models were created with inheritance")
    print("   5. Physics validation was performed")
    print("   6. Results returned to demo")
    
    print("\n🔗 This proves the Docker C# Proto.Actor is working with the demo!")

if __name__ == "__main__":
    main()
