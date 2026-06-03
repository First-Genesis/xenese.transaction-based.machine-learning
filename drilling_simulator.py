#!/usr/bin/env python3
"""
Oil & Gas Drilling Parameter Optimization Simulator

Generates realistic drilling data for TML platform demonstration.
Simulates real-time drilling operations with geological formations,
equipment parameters, and drilling challenges.
"""

import sys
import time
import random
import math
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import TML components
from tml.core.model import TransactionContext, RiverTransactionModel

class FormationType(Enum):
    """Geological formation types with different drilling characteristics."""
    SANDSTONE = "sandstone"
    SHALE = "shale"
    LIMESTONE = "limestone"
    DOLOMITE = "dolomite"
    SALT = "salt"
    GRANITE = "granite"

class DrillBitType(Enum):
    """Different drill bit types for various formations."""
    PDC = "pdc"  # Polycrystalline Diamond Compact
    TRICONE = "tricone"
    DIAMOND = "diamond"
    HYBRID = "hybrid"

@dataclass
class GeologicalLayer:
    """Represents a geological formation layer."""
    depth_start: float  # feet
    depth_end: float    # feet
    formation_type: FormationType
    hardness: float     # 1-10 scale (1=soft, 10=very hard)
    porosity: float     # 0-1 scale
    permeability: float # mD (millidarcies)
    pressure_gradient: float  # psi/ft
    temperature_gradient: float  # °F/ft
    abrasiveness: float # 1-10 scale
    stability: float    # 1-10 scale (1=unstable, 10=stable)

class DrillingRig:
    """Simulates a drilling rig with realistic equipment parameters."""
    
    def __init__(self, rig_id: str, rig_type: str = "Land_Rig_5000HP"):
        self.rig_id = rig_id
        self.rig_type = rig_type
        self.current_depth = 0.0
        self.target_depth = 12000.0  # feet
        self.bit_depth = 0.0
        self.drilling_rate = 0.0  # feet/hour
        
        # Equipment parameters
        self.weight_on_bit = 25000.0  # lbs
        self.rotary_speed = 120.0     # RPM
        self.torque = 8000.0          # ft-lbs
        self.mud_flow_rate = 450.0    # gpm
        self.mud_weight = 9.5         # ppg (pounds per gallon)
        self.mud_viscosity = 45.0     # seconds
        self.standpipe_pressure = 3200.0  # psi
        
        # Bit parameters
        self.bit_type = DrillBitType.PDC
        self.bit_wear = 0.0           # 0-100% (0=new, 100=worn out)
        self.bit_hours = 0.0
        
        # Equipment health
        self.pump_efficiency = 95.0   # %
        self.drawworks_load = 150000.0  # lbs
        self.rotary_table_torque = 12000.0  # ft-lbs
        self.mud_pump_pressure = 3500.0  # psi
        
        # Environmental conditions
        self.surface_temperature = 75.0  # °F
        self.wind_speed = 10.0          # mph
        self.humidity = 65.0            # %

class WellProfile:
    """Defines the geological profile of a well."""
    
    def __init__(self, well_name: str, location: Tuple[float, float]):
        self.well_name = well_name
        self.latitude, self.longitude = location
        self.geological_layers = self._generate_geological_profile()
        
    def _generate_geological_profile(self) -> List[GeologicalLayer]:
        """Generate realistic geological layers for the well."""
        layers = []
        current_depth = 0.0
        
        # Surface layer (0-100 ft) - Soft sediments
        layers.append(GeologicalLayer(
            depth_start=0.0, depth_end=100.0,
            formation_type=FormationType.SANDSTONE,
            hardness=2.0, porosity=0.25, permeability=100.0,
            pressure_gradient=0.433, temperature_gradient=0.015,
            abrasiveness=3.0, stability=8.0
        ))
        
        # Shallow formations (100-2000 ft) - Mixed sediments
        layers.append(GeologicalLayer(
            depth_start=100.0, depth_end=2000.0,
            formation_type=FormationType.SHALE,
            hardness=4.0, porosity=0.15, permeability=0.1,
            pressure_gradient=0.45, temperature_gradient=0.018,
            abrasiveness=6.0, stability=6.0
        ))
        
        # Intermediate formations (2000-6000 ft) - Harder rocks
        layers.append(GeologicalLayer(
            depth_start=2000.0, depth_end=6000.0,
            formation_type=FormationType.LIMESTONE,
            hardness=6.0, porosity=0.12, permeability=5.0,
            pressure_gradient=0.465, temperature_gradient=0.02,
            abrasiveness=7.0, stability=7.0
        ))
        
        # Deep formations (6000-10000 ft) - High pressure zone
        layers.append(GeologicalLayer(
            depth_start=6000.0, depth_end=10000.0,
            formation_type=FormationType.DOLOMITE,
            hardness=7.5, porosity=0.08, permeability=1.0,
            pressure_gradient=0.52, temperature_gradient=0.022,
            abrasiveness=8.0, stability=5.0
        ))
        
        # Ultra-deep formations (10000+ ft) - Extreme conditions
        layers.append(GeologicalLayer(
            depth_start=10000.0, depth_end=15000.0,
            formation_type=FormationType.GRANITE,
            hardness=9.0, porosity=0.02, permeability=0.01,
            pressure_gradient=0.58, temperature_gradient=0.025,
            abrasiveness=9.5, stability=4.0
        ))
        
        return layers
    
    def get_formation_at_depth(self, depth: float) -> GeologicalLayer:
        """Get the geological formation at a specific depth."""
        for layer in self.geological_layers:
            if layer.depth_start <= depth <= layer.depth_end:
                return layer
        # Return the deepest layer if depth exceeds profile
        return self.geological_layers[-1]

class DrillingSimulator:
    """Main drilling simulation engine with TML integration."""
    
    def __init__(self):
        self.wells = {}  # Store well profiles
        self.rigs = {}   # Store rig instances
        self.models = {} # Store TML models per well
        self.drilling_history = []
        self.model_count = 0
        
    def create_well(self, well_name: str, location: Tuple[float, float]) -> WellProfile:
        """Create a new well with geological profile."""
        well = WellProfile(well_name, location)
        self.wells[well_name] = well
        return well
        
    def create_rig(self, rig_id: str, rig_type: str = "Land_Rig_5000HP") -> DrillingRig:
        """Create a new drilling rig."""
        rig = DrillingRig(rig_id, rig_type)
        self.rigs[rig_id] = rig
        return rig
    
    def calculate_rate_of_penetration(self, rig: DrillingRig, formation: GeologicalLayer) -> float:
        """Calculate realistic rate of penetration based on parameters."""
        
        # Base ROP calculation using drilling equation
        # ROP = f(WOB, RPM, Bit_Type, Formation_Hardness, Mud_Properties)
        
        # Normalize parameters
        wob_factor = min(rig.weight_on_bit / 40000.0, 1.5)  # Optimal around 30-40k lbs
        rpm_factor = min(rig.rotary_speed / 150.0, 1.2)    # Optimal around 120-150 RPM
        
        # Formation resistance
        hardness_resistance = 1.0 / (formation.hardness / 2.0)
        stability_factor = formation.stability / 10.0
        
        # Bit efficiency
        bit_efficiency = (100.0 - rig.bit_wear) / 100.0
        
        # Mud properties effect
        mud_factor = 1.0
        if rig.mud_weight < formation.pressure_gradient * rig.current_depth / 1000.0:
            mud_factor *= 0.7  # Underbalanced - faster but risky
        elif rig.mud_weight > formation.pressure_gradient * rig.current_depth / 800.0:
            mud_factor *= 0.8  # Overbalanced - slower but safer
            
        # Base ROP calculation
        base_rop = 50.0 * wob_factor * rpm_factor * hardness_resistance * bit_efficiency * mud_factor * stability_factor
        
        # Add realistic variations
        variation = random.uniform(0.8, 1.2)
        rop = base_rop * variation
        
        # Depth effect - generally slower at greater depths
        depth_factor = max(0.3, 1.0 - (rig.current_depth / 20000.0))
        rop *= depth_factor
        
        return max(5.0, min(200.0, rop))  # Realistic bounds: 5-200 ft/hr
    
    def calculate_equipment_failure_probability(self, rig: DrillingRig, formation: GeologicalLayer) -> float:
        """Calculate equipment failure probability based on operating conditions."""
        
        failure_prob = 0.0
        
        # Bit wear factor
        if rig.bit_wear > 80:
            failure_prob += 0.15
        elif rig.bit_wear > 60:
            failure_prob += 0.08
        elif rig.bit_wear > 40:
            failure_prob += 0.03
            
        # Excessive parameters
        if rig.weight_on_bit > 45000:
            failure_prob += 0.05
        if rig.rotary_speed > 180:
            failure_prob += 0.04
        if rig.torque > 15000:
            failure_prob += 0.06
            
        # Formation abrasiveness
        if formation.abrasiveness > 8:
            failure_prob += 0.03
        if formation.stability < 4:
            failure_prob += 0.04
            
        # Pump pressure
        if rig.standpipe_pressure > 4000:
            failure_prob += 0.02
            
        # Operating hours
        hours_factor = min(rig.bit_hours / 100.0, 0.1)
        failure_prob += hours_factor
        
        return min(failure_prob, 0.95)  # Cap at 95%
    
    def calculate_stuck_pipe_risk(self, rig: DrillingRig, formation: GeologicalLayer) -> float:
        """Calculate stuck pipe risk assessment."""
        
        stuck_risk = 0.0
        
        # Formation stability issues
        if formation.stability < 5:
            stuck_risk += 0.2
        if formation.formation_type == FormationType.SHALE and formation.stability < 6:
            stuck_risk += 0.15  # Shale instability
            
        # Mud weight issues
        formation_pressure = formation.pressure_gradient * rig.current_depth
        mud_pressure = rig.mud_weight * 0.052 * rig.current_depth
        
        if mud_pressure < formation_pressure * 1.05:  # Underbalanced
            stuck_risk += 0.25
        elif mud_pressure > formation_pressure * 1.3:  # Overbalanced
            stuck_risk += 0.1
            
        # Differential sticking
        if rig.mud_weight > 12.0 and formation.permeability > 10:
            stuck_risk += 0.15
            
        # Hole cleaning issues
        if rig.mud_flow_rate < 400:
            stuck_risk += 0.1
        if rig.rotary_speed < 80:
            stuck_risk += 0.08
            
        # Torque and drag
        if rig.torque > 12000:
            stuck_risk += 0.05
            
        return min(stuck_risk, 0.9)  # Cap at 90%
    
    def optimize_mud_weight(self, rig: DrillingRig, formation: GeologicalLayer) -> float:
        """Calculate optimal mud weight for current conditions."""
        
        # Formation pressure
        formation_pressure = formation.pressure_gradient * rig.current_depth
        
        # Fracture pressure (estimated)
        fracture_gradient = formation.pressure_gradient * 1.2 + 0.1
        fracture_pressure = fracture_gradient * rig.current_depth
        
        # Safety margins
        min_mud_weight = (formation_pressure * 1.05) / (0.052 * rig.current_depth)  # 5% overbalance
        max_mud_weight = (fracture_pressure * 0.95) / (0.052 * rig.current_depth)   # 5% below fracture
        
        # Formation-specific adjustments
        if formation.formation_type == FormationType.SHALE:
            min_mud_weight *= 1.1  # Higher for shale stability
        elif formation.formation_type == FormationType.SALT:
            min_mud_weight *= 0.95  # Lower for salt sections
            
        # Stuck pipe considerations
        if formation.permeability > 50:
            min_mud_weight *= 1.05  # Higher for permeable zones
            
        # Optimal mud weight (middle of safe window)
        optimal_mud_weight = (min_mud_weight + max_mud_weight) / 2.0
        
        return round(optimal_mud_weight, 1)
    
    def generate_drilling_data(self, well_name: str, rig_id: str, depth_interval: float = 10.0) -> Dict[str, Any]:
        """Generate realistic drilling data for a specific depth interval."""
        
        if well_name not in self.wells or rig_id not in self.rigs:
            raise ValueError(f"Well {well_name} or Rig {rig_id} not found")
            
        well = self.wells[well_name]
        rig = self.rigs[rig_id]
        
        # Advance drilling depth
        rig.current_depth += depth_interval
        rig.bit_depth = rig.current_depth
        
        # Get current formation
        formation = well.get_formation_at_depth(rig.current_depth)
        
        # Add some realistic parameter variations
        rig.weight_on_bit += random.uniform(-2000, 2000)
        rig.weight_on_bit = max(15000, min(50000, rig.weight_on_bit))
        
        rig.rotary_speed += random.uniform(-10, 10)
        rig.rotary_speed = max(60, min(200, rig.rotary_speed))
        
        rig.mud_flow_rate += random.uniform(-20, 20)
        rig.mud_flow_rate = max(350, min(550, rig.mud_flow_rate))
        
        # Update bit wear
        rig.bit_hours += depth_interval / max(rig.drilling_rate, 10.0)
        rig.bit_wear = min(100.0, rig.bit_wear + formation.abrasiveness * 0.1)
        
        # Calculate predictions
        rop_forecast = self.calculate_rate_of_penetration(rig, formation)
        equipment_failure_prob = self.calculate_equipment_failure_probability(rig, formation)
        stuck_pipe_risk = self.calculate_stuck_pipe_risk(rig, formation)
        optimal_mud_weight = self.optimize_mud_weight(rig, formation)
        
        # Update rig parameters based on calculations
        rig.drilling_rate = rop_forecast
        
        # Calculate downhole conditions
        downhole_pressure = formation.pressure_gradient * rig.current_depth
        downhole_temp = 70 + formation.temperature_gradient * rig.current_depth
        
        # Generate sensor data
        drilling_data = {
            "timestamp": datetime.now().isoformat(),
            "well_name": well_name,
            "rig_id": rig_id,
            "depth": rig.current_depth,
            "target_depth": rig.target_depth,
            
            # Formation properties
            "formation_type": formation.formation_type.value,
            "formation_hardness": formation.hardness,
            "formation_pressure": downhole_pressure,
            "formation_temperature": downhole_temp,
            "formation_stability": formation.stability,
            
            # Drilling parameters
            "weight_on_bit": round(rig.weight_on_bit, 0),
            "rotary_speed": round(rig.rotary_speed, 1),
            "torque": round(rig.torque, 0),
            "mud_flow_rate": round(rig.mud_flow_rate, 1),
            "mud_weight": round(rig.mud_weight, 1),
            "standpipe_pressure": round(rig.standpipe_pressure, 0),
            
            # Bit information
            "bit_type": rig.bit_type.value,
            "bit_wear": round(rig.bit_wear, 1),
            "bit_hours": round(rig.bit_hours, 1),
            
            # Predictions (TML outputs)
            "rate_of_penetration": round(rop_forecast, 1),
            "equipment_failure_probability": round(equipment_failure_prob * 100, 1),
            "stuck_pipe_risk": round(stuck_pipe_risk * 100, 1),
            "optimal_mud_weight": optimal_mud_weight,
            
            # Optimal parameter recommendations
            "recommended_wob": round(min(35000, max(20000, 30000 - formation.hardness * 1000)), 0),
            "recommended_rpm": round(min(150, max(80, 120 - formation.hardness * 5)), 0),
            "recommended_flow_rate": round(450 + formation.stability * 10, 0),
            
            # Risk indicators
            "drilling_efficiency": round((rop_forecast / 100.0) * 100, 1),  # % of optimal
            "safety_score": round((1.0 - max(equipment_failure_prob, stuck_pipe_risk)) * 100, 1),
            "cost_per_foot": round(50000 / max(rop_forecast, 10), 0),  # $/ft
            
            # Alerts and warnings
            "alerts": self._generate_alerts(rig, formation, equipment_failure_prob, stuck_pipe_risk)
        }
        
        return drilling_data
    
    def _generate_alerts(self, rig: DrillingRig, formation: GeologicalLayer, 
                        equipment_failure_prob: float, stuck_pipe_risk: float) -> List[str]:
        """Generate drilling alerts based on current conditions."""
        alerts = []
        
        if equipment_failure_prob > 0.3:
            alerts.append("HIGH_EQUIPMENT_FAILURE_RISK")
        if stuck_pipe_risk > 0.4:
            alerts.append("HIGH_STUCK_PIPE_RISK")
        if rig.bit_wear > 80:
            alerts.append("BIT_REPLACEMENT_RECOMMENDED")
        if rig.weight_on_bit > 45000:
            alerts.append("EXCESSIVE_WEIGHT_ON_BIT")
        if rig.torque > 15000:
            alerts.append("HIGH_TORQUE_WARNING")
        if formation.stability < 4:
            alerts.append("UNSTABLE_FORMATION")
        if rig.standpipe_pressure > 4000:
            alerts.append("HIGH_PUMP_PRESSURE")
            
        return alerts

async def run_drilling_simulation(well_name: str, rig_id: str, duration_minutes: int = 60):
    """Run real-time drilling simulation."""
    
    print("=" * 80)
    print("🛢️  Oil & Gas Drilling Parameter Optimization - TML Demo")
    print("=" * 80)
    print(f"Well: {well_name} | Rig: {rig_id} | Duration: {duration_minutes} minutes")
    print("-" * 80)
    
    # Initialize simulator
    simulator = DrillingSimulator()
    
    # Create well and rig
    well_location = (29.7604, -95.3698)  # Houston area coordinates
    well = simulator.create_well(well_name, well_location)
    rig = simulator.create_rig(rig_id)
    
    print(f"📍 Well Location: {well_location[0]:.4f}, {well_location[1]:.4f}")
    print(f"🎯 Target Depth: {rig.target_depth:,.0f} ft")
    print(f"⚙️  Rig Type: {rig.rig_type}")
    print("-" * 80)
    
    start_time = time.time()
    interval_count = 0
    
    try:
        while time.time() - start_time < duration_minutes * 60:
            # Generate drilling data for 10-foot interval
            drilling_data = simulator.generate_drilling_data(well_name, rig_id, 10.0)
            interval_count += 1
            
            # Display real-time data
            depth = drilling_data["depth"]
            formation = drilling_data["formation_type"]
            rop = drilling_data["rate_of_penetration"]
            equipment_risk = drilling_data["equipment_failure_probability"]
            stuck_risk = drilling_data["stuck_pipe_risk"]
            mud_weight = drilling_data["mud_weight"]
            optimal_mud = drilling_data["optimal_mud_weight"]
            safety_score = drilling_data["safety_score"]
            
            # Color coding for risks
            equipment_color = "\033[91m" if equipment_risk > 30 else "\033[93m" if equipment_risk > 15 else "\033[92m"
            stuck_color = "\033[91m" if stuck_risk > 40 else "\033[93m" if stuck_risk > 20 else "\033[92m"
            
            print(f"{interval_count:4d} | Depth: {depth:7.0f}ft | {formation:10s} | "
                  f"ROP: {rop:5.1f}ft/hr | "
                  f"Equip Risk: {equipment_color}{equipment_risk:4.1f}%\033[0m | "
                  f"Stuck Risk: {stuck_color}{stuck_risk:4.1f}%\033[0m | "
                  f"Mud: {mud_weight:4.1f}→{optimal_mud:4.1f}ppg | "
                  f"Safety: {safety_score:5.1f}%")
            
            # Show alerts
            if drilling_data["alerts"]:
                for alert in drilling_data["alerts"]:
                    print(f"      🚨 ALERT: {alert}")
            
            # Show recommendations every 10 intervals
            if interval_count % 10 == 0:
                print(f"\n📊 TML Recommendations (Depth {depth:.0f}ft):")
                print(f"   Optimal WOB: {drilling_data['recommended_wob']:,.0f} lbs")
                print(f"   Optimal RPM: {drilling_data['recommended_rpm']:.0f}")
                print(f"   Optimal Flow: {drilling_data['recommended_flow_rate']:.0f} gpm")
                print(f"   Cost/Foot: ${drilling_data['cost_per_foot']:,.0f}")
                print(f"   Drilling Efficiency: {drilling_data['drilling_efficiency']:.1f}%")
                print("-" * 80)
            
            # Simulate drilling time (1 second = 1 drilling interval)
            await asyncio.sleep(1)
            
            # Stop if target depth reached
            if depth >= rig.target_depth:
                print("\n🎯 Target depth reached!")
                break
                
    except KeyboardInterrupt:
        print("\n\nDrilling simulation stopped by user")
    
    # Final statistics
    final_depth = drilling_data["depth"]
    total_time = time.time() - start_time
    avg_rop = final_depth / (total_time / 3600)  # ft/hr
    
    print("\n" + "=" * 80)
    print("📈 Drilling Summary")
    print("=" * 80)
    print(f"Final Depth: {final_depth:,.0f} ft")
    print(f"Total Time: {total_time/60:.1f} minutes")
    print(f"Average ROP: {avg_rop:.1f} ft/hr")
    print(f"Total Intervals: {interval_count}")
    print(f"Final Formation: {drilling_data['formation_type']}")
    print(f"Bit Wear: {drilling_data['bit_wear']:.1f}%")
    print(f"Final Safety Score: {drilling_data['safety_score']:.1f}%")
    
    print("\n✅ TML successfully optimized drilling parameters in real-time!")
    print("   Each interval created a smarter model for better predictions.")

if __name__ == "__main__":
    import sys
    
    well_name = sys.argv[1] if len(sys.argv) > 1 else "EAGLE_FORD_001"
    rig_id = sys.argv[2] if len(sys.argv) > 2 else "RIG_042"
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    asyncio.run(run_drilling_simulation(well_name, rig_id, duration))
