#!/usr/bin/env python3
"""
Test script to verify TML API integration with the demo
"""

import requests
import json
import time
import numpy as np

API_BASE_URL = "http://localhost:5001"

def test_api_connection():
    """Test if the API is reachable"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API Health Check: OK")
            return True
        else:
            print(f"❌ API Health Check Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

def create_test_transaction(x_coord=100, y_coord=200, thickness=19.5):
    """Create a test transaction via API"""
    transaction_data = {
        "data": {
            "xCoord": x_coord,
            "yCoord": y_coord,
            "thickness": thickness,
            "minThickness": 15.0,
            "quality": 0.95,
            "features": {"feature1": 1.0, "feature2": 2.0}
        },
        "source": "demo-ui",
        "metadata": {"demo": True, "timestamp": time.time()}
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/transactions",
            json=transaction_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Transaction created: {result['transactionId']}")
            print(f"   Model ID: {result['modelId']}")
            print(f"   Status: {result['status']}")
            print(f"   Processing Time: {result['processingTimeMs']:.2f}ms")
            print(f"   Physics Valid: {result['physicsValid']}")
            print(f"   Confidence: {result['confidence']}")
            return result
        else:
            print(f"❌ Failed to create transaction: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating transaction: {e}")
        return None

def get_statistics():
    """Get current statistics from API"""
    try:
        # Get transaction statistics
        response = requests.get(f"{API_BASE_URL}/api/transactions/statistics")
        if response.status_code == 200:
            stats = response.json()
            print("\n📊 Transaction Statistics:")
            print(f"   Total Count: {stats['totalCount']}")
            print(f"   Average Processing Time: {stats['averageProcessingTimeMs']:.2f}ms")
        
        # Get model statistics
        response = requests.get(f"{API_BASE_URL}/api/models/statistics")
        if response.status_code == 200:
            stats = response.json()
            print("\n📊 Model Statistics:")
            print(f"   Total Count: {stats['totalCount']}")
            print(f"   Average Confidence: {stats['averageConfidence']:.3f}")
            print(f"   Average R²: {stats['averageRSquared']:.3f}")
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")

def simulate_cscan_batch(num_points=10):
    """Simulate processing a batch of C-scan data points"""
    print(f"\n🔄 Processing {num_points} C-scan data points...")
    
    results = []
    for i in range(num_points):
        x = np.random.randint(0, 50) * 2
        y = np.random.randint(850, 880)
        thickness = 19.8 + np.random.normal(0, 0.5)
        
        print(f"\nPoint {i+1}/{num_points}: X={x}, Y={y}, Thickness={thickness:.2f}mm")
        result = create_test_transaction(x, y, thickness)
        if result:
            results.append(result)
        
        time.sleep(0.1)  # Small delay between requests
    
    print(f"\n✅ Batch processing complete: {len(results)}/{num_points} successful")
    return results

def main():
    print("=" * 60)
    print("TML Platform API Integration Test")
    print("=" * 60)
    
    # Test API connection
    if not test_api_connection():
        print("\n⚠️  Make sure the API is running at http://localhost:5001")
        print("   Run: docker run -d --name tml-api-test ...")
        return
    
    # Create a few test transactions
    print("\n📝 Creating test transactions...")
    create_test_transaction(100, 200, 19.5)
    create_test_transaction(102, 200, 19.3)
    create_test_transaction(104, 200, 19.8)
    
    # Simulate a batch of C-scan data
    simulate_cscan_batch(5)
    
    # Get statistics
    get_statistics()
    
    print("\n" + "=" * 60)
    print("✅ API Integration Test Complete!")
    print("\n💡 You can now:")
    print("   1. View the demo UI at http://localhost:8501")
    print("   2. The demo processes data internally")
    print("   3. Use this script to send data to the API")
    print("   4. Combine both for full platform testing")

if __name__ == "__main__":
    main()
