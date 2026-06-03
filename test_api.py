#!/usr/bin/env python3
"""Quick test of the API server"""

import requests
import json

# Test creating a model
url = "http://localhost:8000/api/models/create"
data = {
    "transaction_id": "test_txn_001",
    "user_id": "test_user",
    "model_type": "logistic_regression"
}

print("Testing model creation...")
response = requests.post(url, json=data)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print(f"Success! Created model: {result['id']}")
    print(json.dumps(result, indent=2))
else:
    print(f"Error: {response.text}")
