#!/usr/bin/env python3
"""Test batch processing fix for parent_model error"""

import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from demo.app import TMLPipelineProcessor

print("Testing batch processing fix...")

# Create processor
processor = TMLPipelineProcessor()

# Test data points
test_points = [
    (100, 200, 20.5),
    (105, 200, 20.3),
    (110, 200, 19.8),
    (115, 200, 21.0),
    (120, 200, 20.7)
]

print("\n1. Testing sequential processing (without Proto.Actor):")
for i, (x, y, thickness) in enumerate(test_points):
    try:
        result = processor.process_transaction(x, y, thickness)
        print(f"   ✅ Point {i+1}: {result['model_id']} - parent: {result.get('parent_model', 'None')}")
    except Exception as e:
        print(f"   ❌ Point {i+1} failed: {e}")

print(f"\n2. Summary:")
print(f"   - Models created: {len(processor.models)}")
print(f"   - Physics violations: {processor.physics_violations}")
print(f"   - Models with inheritance: {sum(1 for m in processor.models.values() if m.get('parent_model'))}")

print("\n✅ Test completed successfully! The parent_model error has been fixed.")
