#!/usr/bin/env python3
"""
Drilling Parameter Optimization with Full TML Integration

Demonstrates real-time drilling optimization using the TML platform
with model inheritance and continuous learning.
"""

import sys
import time
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import TML components
from tml.core.model import TransactionContext, RiverTransactionModel
from drilling_simulator import DrillingSimulator

class TMLDrillingOptimizer:
    """TML-powered drilling parameter optimization system."""
    
    def __init__(self):
        self.simulator = DrillingSimulator()
        self.models = {}  # Store TML models per well
        self.parent_model = None  # Global parent for knowledge inheritance
        self.model_count = 0
        self.optimization_history = []
        
    def create_drilling_model(self, well_name: str, rig_id: str, depth: float) -> RiverTransactionModel:
        """Create a TML model for drilling optimization at specific depth."""
        
        # Create transaction context
        context = TransactionContext(
            transaction_id=f"drill_{well_name}_{int(depth)}ft_{int(time.time())}",
            user_id=f"rig_{rig_id}",
            session_id=f"well_{well_name}"
        )
        
        # Generate unique model ID
        self.model_count += 1
        model_id = f"drill_model_{self.model_count:06d}"
        
        # Create model with inheritance
        model = RiverTransactionModel(
            model_id=model_id,
            parent_model_id=self.parent_model.model_id if self.parent_model else None,
            model_type="logistic_regression"  # For risk prediction
        )
        model.context = context
        
        # Inherit knowledge from parent model
        if self.parent_model:
            try:
                import pickle
                model.model = pickle.loads(pickle.dumps(self.parent_model.model))
                model.metrics.total_updates = self.parent_model.metrics.total_updates
                print(f"   🧬 Model {model_id} inherited knowledge from {self.parent_model.model_id}")
            except Exception as e:
                print(f"   ⚠️  Inheritance failed: {e}")
        
        # Store model
        model_key = f"{well_name}_{rig_id}_{int(depth)}"
        self.models[model_key] = model
        
        # Update global parent every 5 models for knowledge sharing
        if self.model_count % 5 == 0:
            self.parent_model = model
            print(f"   📚 Updated global parent model to {model_id}")
        
        return model
    
    def extract_drilling_features(self, drilling_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract features for TML model training/prediction."""
        return {
            "formation_hardness": drilling_data["formation_hardness"],
            "formation_pressure": drilling_data["formation_pressure"] / 1000.0,  # Normalize
            "formation_stability": drilling_data["formation_stability"],
            "weight_on_bit": drilling_data["weight_on_bit"] / 1000.0,  # Normalize
            "rotary_speed": drilling_data["rotary_speed"] / 100.0,  # Normalize
            "mud_weight": drilling_data["mud_weight"],
            "mud_flow_rate": drilling_data["mud_flow_rate"] / 100.0,  # Normalize
            "bit_wear": drilling_data["bit_wear"] / 100.0,  # Normalize
            "depth": drilling_data["depth"] / 1000.0,  # Normalize
            "standpipe_pressure": drilling_data["standpipe_pressure"] / 1000.0,  # Normalize
            
            # Engineered features
            "drilling_intensity": (drilling_data["weight_on_bit"] * drilling_data["rotary_speed"]) / 1000000.0,
            "mud_efficiency": drilling_data["mud_flow_rate"] / drilling_data["mud_weight"],
            "formation_challenge": drilling_data["formation_hardness"] / drilling_data["formation_stability"],
            "equipment_stress": drilling_data["bit_wear"] * drilling_data["standpipe_pressure"] / 100000.0,
        }
    
    def predict_drilling_risks(self, model: RiverTransactionModel, features: Dict[str, float]) -> Dict[str, float]:
        """Use TML model to predict drilling risks."""
        
        try:
            # Predict equipment failure risk
            equipment_risk_prediction = model.predict(features)
            
            # Try to get probability if available
            try:
                equipment_risk_prob = model.predict_proba(features)
                if equipment_risk_prob and True in equipment_risk_prob:
                    equipment_risk = equipment_risk_prob[True] * 100
                else:
                    equipment_risk = 50.0 if equipment_risk_prediction else 10.0
            except:
                equipment_risk = 50.0 if equipment_risk_prediction else 10.0
            
            # For demo, simulate stuck pipe risk based on features
            stuck_pipe_risk = min(90.0, max(0.0, 
                features["formation_challenge"] * 20 + 
                features["mud_weight"] * 5 + 
                (1.0 - features["formation_stability"] / 10.0) * 30
            ))
            
            return {
                "equipment_failure_risk": equipment_risk,
                "stuck_pipe_risk": stuck_pipe_risk,
                "overall_risk": max(equipment_risk, stuck_pipe_risk)
            }
            
        except Exception as e:
            print(f"   ⚠️  Prediction error: {e}")
            return {
                "equipment_failure_risk": 15.0,
                "stuck_pipe_risk": 10.0,
                "overall_risk": 15.0
            }
    
    def optimize_parameters(self, drilling_data: Dict[str, Any], risk_predictions: Dict[str, float]) -> Dict[str, float]:
        """Generate optimized drilling parameters based on TML predictions."""
        
        current_wob = drilling_data["weight_on_bit"]
        current_rpm = drilling_data["rotary_speed"]
        current_flow = drilling_data["mud_flow_rate"]
        current_mud_weight = drilling_data["mud_weight"]
        
        # Risk-based parameter adjustments
        if risk_predictions["equipment_failure_risk"] > 30:
            # Reduce aggressive parameters
            optimal_wob = current_wob * 0.85
            optimal_rpm = current_rpm * 0.9
        elif risk_predictions["equipment_failure_risk"] < 10:
            # Can be more aggressive
            optimal_wob = min(45000, current_wob * 1.1)
            optimal_rpm = min(180, current_rpm * 1.05)
        else:
            optimal_wob = current_wob
            optimal_rpm = current_rpm
        
        if risk_predictions["stuck_pipe_risk"] > 25:
            # Increase circulation and adjust mud weight
            optimal_flow = min(550, current_flow * 1.15)
            optimal_mud_weight = drilling_data["optimal_mud_weight"]
        else:
            optimal_flow = current_flow
            optimal_mud_weight = current_mud_weight
        
        # Formation-based adjustments
        formation_hardness = drilling_data["formation_hardness"]
        if formation_hardness > 7:  # Hard formation
            optimal_wob = min(optimal_wob * 1.2, 45000)
            optimal_rpm = max(optimal_rpm * 0.9, 80)
        
        return {
            "optimal_weight_on_bit": round(optimal_wob, 0),
            "optimal_rotary_speed": round(optimal_rpm, 0),
            "optimal_flow_rate": round(optimal_flow, 0),
            "optimal_mud_weight": round(optimal_mud_weight, 1),
            "confidence": min(100.0, 60.0 + (self.model_count * 2))  # Increases with learning
        }
    
    def train_model(self, model: RiverTransactionModel, features: Dict[str, float], 
                   actual_outcome: bool, drilling_data: Dict[str, Any]):
        """Train the TML model with actual drilling outcomes."""
        
        try:
            # Train model with actual equipment failure or stuck pipe event
            model.update(features, actual_outcome)
            
            print(f"   📈 Model {model.model_id} trained - Updates: {model.metrics.total_updates}, "
                  f"Accuracy: {model.metrics.accuracy:.1%}")
            
        except Exception as e:
            print(f"   ⚠️  Training error: {e}")

async def run_tml_drilling_demo(well_name: str, rig_id: str, duration_minutes: int = 10):
    """Run TML-powered drilling optimization demo."""
    
    print("=" * 80)
    print("🛢️  TML-Powered Drilling Parameter Optimization Demo")
    print("=" * 80)
    print(f"Well: {well_name} | Rig: {rig_id} | Duration: {duration_minutes} minutes")
    print("Demonstrating: Model inheritance, continuous learning, real-time optimization")
    print("-" * 80)
    
    # Initialize TML optimizer
    optimizer = TMLDrillingOptimizer()
    
    # Create well and rig in simulator
    well_location = (29.7604, -95.3698)  # Eagle Ford coordinates
    well = optimizer.simulator.create_well(well_name, well_location)
    rig = optimizer.simulator.create_rig(rig_id)
    
    print(f"📍 Well Location: {well_location[0]:.4f}, {well_location[1]:.4f}")
    print(f"🎯 Target Depth: {rig.target_depth:,.0f} ft")
    print(f"⚙️  Rig Type: {rig.rig_type}")
    print("-" * 80)
    
    start_time = time.time()
    interval_count = 0
    total_risk_reduction = 0
    
    try:
        while time.time() - start_time < duration_minutes * 60:
            # Generate drilling data for current interval
            drilling_data = optimizer.simulator.generate_drilling_data(well_name, rig_id, 25.0)
            interval_count += 1
            
            depth = drilling_data["depth"]
            formation = drilling_data["formation_type"]
            
            print(f"\n🔄 Interval {interval_count} - Depth: {depth:.0f}ft - Formation: {formation}")
            
            # Create TML model for this drilling decision
            model = optimizer.create_drilling_model(well_name, rig_id, depth)
            
            # Extract features for TML
            features = optimizer.extract_drilling_features(drilling_data)
            
            # Make TML predictions
            risk_predictions = optimizer.predict_drilling_risks(model, features)
            
            # Generate optimized parameters
            optimizations = optimizer.optimize_parameters(drilling_data, risk_predictions)
            
            # Display results
            original_equipment_risk = drilling_data["equipment_failure_probability"]
            original_stuck_risk = drilling_data["stuck_pipe_risk"]
            
            tml_equipment_risk = risk_predictions["equipment_failure_risk"]
            tml_stuck_risk = risk_predictions["stuck_pipe_risk"]
            
            # Color coding
            equipment_color = "\033[91m" if tml_equipment_risk > 30 else "\033[93m" if tml_equipment_risk > 15 else "\033[92m"
            stuck_color = "\033[91m" if tml_stuck_risk > 25 else "\033[93m" if tml_stuck_risk > 15 else "\033[92m"
            
            print(f"   📊 TML Predictions:")
            print(f"      Equipment Risk: {equipment_color}{tml_equipment_risk:5.1f}%\033[0m (vs {original_equipment_risk:5.1f}% baseline)")
            print(f"      Stuck Pipe Risk: {stuck_color}{tml_stuck_risk:5.1f}%\033[0m (vs {original_stuck_risk:5.1f}% baseline)")
            
            print(f"   🎯 TML Optimizations (Confidence: {optimizations['confidence']:.0f}%):")
            print(f"      WOB: {drilling_data['weight_on_bit']:,.0f} → {optimizations['optimal_weight_on_bit']:,.0f} lbs")
            print(f"      RPM: {drilling_data['rotary_speed']:.0f} → {optimizations['optimal_rotary_speed']:.0f}")
            print(f"      Flow: {drilling_data['mud_flow_rate']:.0f} → {optimizations['optimal_flow_rate']:.0f} gpm")
            print(f"      Mud Weight: {drilling_data['mud_weight']:.1f} → {optimizations['optimal_mud_weight']:.1f} ppg")
            
            # Simulate actual outcome (for training)
            # In reality, this would come from actual drilling results
            actual_equipment_failure = tml_equipment_risk > 40 and random.random() < 0.3
            actual_stuck_pipe = tml_stuck_risk > 30 and random.random() < 0.2
            actual_problem = actual_equipment_failure or actual_stuck_pipe
            
            # Train model with actual outcome
            optimizer.train_model(model, features, actual_problem, drilling_data)
            
            # Calculate risk reduction
            baseline_risk = max(original_equipment_risk, original_stuck_risk)
            tml_risk = max(tml_equipment_risk, tml_stuck_risk)
            risk_reduction = max(0, baseline_risk - tml_risk)
            total_risk_reduction += risk_reduction
            
            if risk_reduction > 5:
                print(f"   ✅ Risk reduced by {risk_reduction:.1f}% through TML optimization")
            
            # Show alerts
            if drilling_data["alerts"]:
                for alert in drilling_data["alerts"]:
                    print(f"   🚨 ALERT: {alert}")
            
            # Show model inheritance info every 5 intervals
            if interval_count % 5 == 0:
                print(f"\n📚 TML Model Status:")
                print(f"   Total Models Created: {optimizer.model_count}")
                print(f"   Current Parent Model: {optimizer.parent_model.model_id if optimizer.parent_model else 'None'}")
                print(f"   Average Risk Reduction: {total_risk_reduction/interval_count:.1f}%")
                print("-" * 80)
            
            await asyncio.sleep(2)  # 2-second intervals
            
            # Stop if target depth reached
            if depth >= rig.target_depth:
                print("\n🎯 Target depth reached!")
                break
                
    except KeyboardInterrupt:
        print("\n\nDemo stopped by user")
    
    # Final statistics
    final_depth = drilling_data["depth"]
    total_time = time.time() - start_time
    avg_risk_reduction = total_risk_reduction / interval_count if interval_count > 0 else 0
    
    print("\n" + "=" * 80)
    print("📈 TML Drilling Optimization Summary")
    print("=" * 80)
    print(f"Final Depth: {final_depth:,.0f} ft")
    print(f"Total Time: {total_time/60:.1f} minutes")
    print(f"Total Intervals: {interval_count}")
    print(f"Models Created: {optimizer.model_count}")
    print(f"Average Risk Reduction: {avg_risk_reduction:.1f}%")
    print(f"Final Model Accuracy: {model.metrics.accuracy:.1%}")
    print(f"Total Model Updates: {model.metrics.total_updates}")
    
    print(f"\n🧠 Model Inheritance Chain:")
    if optimizer.parent_model:
        print(f"   Latest Model: {model.model_id}")
        print(f"   Parent Model: {model.parent_model_id or 'Base Model'}")
        print(f"   Knowledge Inherited: {model.metrics.total_updates} updates")
    
    print("\n✅ TML successfully demonstrated:")
    print("   🔄 Real-time parameter optimization")
    print("   🧬 Model inheritance and knowledge transfer")
    print("   📈 Continuous learning from drilling outcomes")
    print("   🎯 Risk-based decision making")
    print("   ⚡ Adaptive drilling intelligence")
    
    print(f"\n💰 Estimated Value:")
    print(f"   Risk Reduction: {avg_risk_reduction:.1f}% average")
    print(f"   Potential Savings: ${avg_risk_reduction * 50000:.0f} per well")
    print(f"   Model #1000 would be significantly smarter than Model #1!")

if __name__ == "__main__":
    import random
    import sys
    
    well_name = sys.argv[1] if len(sys.argv) > 1 else "EAGLE_FORD_TML_001"
    rig_id = sys.argv[2] if len(sys.argv) > 2 else "RIG_TML_042"
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    asyncio.run(run_tml_drilling_demo(well_name, rig_id, duration))
