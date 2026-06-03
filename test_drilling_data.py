#!/usr/bin/env python3
"""
Quick test of drilling data generation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from drilling_simulator import DrillingSimulator

def test_drilling_data():
    print("🛢️ Testing Drilling Parameter Optimization Data Generation")
    print("=" * 60)
    
    # Create simulator
    simulator = DrillingSimulator()
    
    # Create well and rig
    well = simulator.create_well("EAGLE_FORD_TEST", (29.7604, -95.3698))
    rig = simulator.create_rig("RIG_TEST")
    
    print(f"✅ Created well: {well.well_name}")
    print(f"✅ Created rig: {rig.rig_id}")
    print(f"📍 Location: {well.latitude:.4f}, {well.longitude:.4f}")
    print(f"🎯 Target depth: {rig.target_depth:,.0f} ft")
    print()
    
    # Generate 10 drilling intervals
    print("📊 Generating drilling data intervals:")
    print("-" * 60)
    
    for i in range(10):
        data = simulator.generate_drilling_data("EAGLE_FORD_TEST", "RIG_TEST", 50.0)
        
        depth = data["depth"]
        formation = data["formation_type"]
        rop = data["rate_of_penetration"]
        equipment_risk = data["equipment_failure_probability"]
        stuck_risk = data["stuck_pipe_risk"]
        mud_weight = data["mud_weight"]
        optimal_mud = data["optimal_mud_weight"]
        
        print(f"{i+1:2d} | Depth: {depth:7.0f}ft | {formation:10s} | "
              f"ROP: {rop:5.1f}ft/hr | "
              f"Equip Risk: {equipment_risk:4.1f}% | "
              f"Stuck Risk: {stuck_risk:4.1f}% | "
              f"Mud: {mud_weight:4.1f}→{optimal_mud:4.1f}ppg")
        
        # Show alerts if any
        if data["alerts"]:
            for alert in data["alerts"]:
                print(f"     🚨 {alert}")
    
    print()
    print("✅ Drilling data generation test completed successfully!")
    print()
    
    # Show sample detailed data
    print("📋 Sample Detailed Data Record:")
    print("-" * 60)
    sample_data = simulator.generate_drilling_data("EAGLE_FORD_TEST", "RIG_TEST", 25.0)
    
    for key, value in sample_data.items():
        if isinstance(value, (int, float)):
            if 'probability' in key or 'risk' in key:
                print(f"  {key:25s}: {value:6.1f}%")
            elif 'weight' in key or 'pressure' in key:
                print(f"  {key:25s}: {value:8.0f}")
            else:
                print(f"  {key:25s}: {value:8.1f}")
        elif isinstance(value, list):
            print(f"  {key:25s}: {', '.join(value) if value else 'None'}")
        else:
            print(f"  {key:25s}: {value}")
    
    print()
    print("🎯 Key TML Predictions Demonstrated:")
    print("  ✓ Rate of Penetration Forecast")
    print("  ✓ Equipment Failure Probability")
    print("  ✓ Stuck Pipe Risk Assessment")
    print("  ✓ Optimal Mud Weight Adjustments")
    print("  ✓ Real-time Parameter Optimization")

if __name__ == "__main__":
    test_drilling_data()
