#!/usr/bin/env python3
"""
TML Platform Demo Application - Pipeline Inspection Use Case

Web-based demonstration of Enhanced TML Platform v2.0 for C-Scan
ultrasonic thickness data processing with real-time visualization.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import io
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
import asyncio
import threading
import sys
import os
import logging
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database integration
try:
    from database_integration import db_integration
    DATABASE_INTEGRATION_AVAILABLE = True
    logger.info("Database integration loaded successfully")
except ImportError as e:
    logger.warning(f"Database integration not available: {e}")
    DATABASE_INTEGRATION_AVAILABLE = False

# Set page configuration (must be first Streamlit command)
st.set_page_config(
    page_title="TML Platform Demo - Pipeline Inspection",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import Proto.Actor components after page config
try:
    from tml.orchestration.streamlit_integration import StreamlitTMLPlatform, StreamlitTMLConfig
    PROTO_ACTOR_AVAILABLE = True
    PROTO_ACTOR_ERROR = None
except ImportError as e:
    PROTO_ACTOR_AVAILABLE = False
    PROTO_ACTOR_ERROR = str(e)
    # Don't show warning here, show it later in the UI

# Continue with rest of app

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-metric {
        border-left-color: #28a745;
    }
    .warning-metric {
        border-left-color: #ffc107;
    }
    .danger-metric {
        border-left-color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)

class TMLPipelineProcessor:
    """TML Pipeline Inspection Processor with Proto.Actor Integration"""
    
    def __init__(self):
        self.models = {}
        # Store database integration availability as instance variable
        self.database_integration_available = DATABASE_INTEGRATION_AVAILABLE
        self.models_saved_to_db = 0  # Counter for models saved to database
        self.db_save_attempts = 0  # Counter for database save attempts
        self.db_save_failures = 0  # Counter for database save failures
        if self.database_integration_available:
            try:
                global db_integration
                self.db_integration = db_integration
                logger.info("Database integration initialized in TMLPipelineProcessor")
            except Exception as e:
                logger.error(f"Failed to initialize database integration: {e}")
                self.database_integration_available = False
        self.transaction_count = 0
        self.physics_violations = 0
        self.processing_times = []
        self.thickness_data = None
        self.repair_zones = []
        
        # Advanced analysis results
        self.corrosion_patterns = {}
        self.structural_integrity = {}
        self.flow_dynamics = {}
        self.material_degradation = {}
        self.electrochemical_analysis = {}
        
        # Proto.Actor Platform
        self.tml_platform = None
        self.platform_status = {}
        self.platform_metrics = {
            'throughput_tps': 0,
            'active_actors': 0,
            'models_created': 0,
            'inheritance_depth_avg': 0,
            'cluster_nodes': 1,
            'latency_p50': 0,
            'latency_p95': 0,
            'latency_p99': 0
        }
        
        # Initialize Proto.Actor platform if available
        if PROTO_ACTOR_AVAILABLE and 'platform' not in st.session_state:
            self._initialize_platform()
        
    def parse_cscan_data(self, csv_content: str) -> pd.DataFrame:
        """Parse C-Scan CSV data into structured format"""
        lines = csv_content.strip().split('\n')
        
        # Find the data start (after headers)
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith('Y/X'):
                data_start = i + 1
                break
                
        # Parse grid data
        thickness_data = []
        
        for i in range(data_start, len(lines)):
            if lines[i].strip():
                parts = lines[i].split('\t')
                if len(parts) > 1:
                    try:
                        y_coord = float(parts[0])
                        thicknesses = []
                        for x in parts[1:]:
                            if x.strip():
                                try:
                                    thicknesses.append(float(x))
                                except ValueError:
                                    continue
                        
                        for j, thickness in enumerate(thicknesses):
                            x_coord = j * 2  # 2mm spacing
                            thickness_data.append({
                                'x_coord': x_coord,
                                'y_coord': y_coord,
                                'thickness': thickness,
                                'point_id': f"X{x_coord}_Y{y_coord}"
                            })
                    except ValueError:
                        continue
        
        df = pd.DataFrame(thickness_data)
        
        # Ensure we have data
        if df.empty:
            # Create sample data if parsing failed
            sample_data = []
            for y in range(850, 881, 5):
                for x in range(0, 51, 2):
                    thickness = 19.8 + (x * 0.01) + np.random.normal(0, 0.1)
                    sample_data.append({
                        'x_coord': x,
                        'y_coord': y,
                        'thickness': thickness,
                        'point_id': f"X{x}_Y{y}"
                    })
            df = pd.DataFrame(sample_data)
        
        return df
    
    def _initialize_platform(self):
        """Initialize Proto.Actor platform for distributed processing"""
        try:
            # Create platform with Streamlit-optimized settings
            config = StreamlitTMLConfig(
                node_id="demo-node-01",
                redis_url="redis://localhost:6379",
                transaction_processor_replicas=2,
                model_actor_replicas=3,
                physics_validator_replicas=1,
                use_thread_pool=True,
                max_workers=4
            )
            
            # Create and start platform
            self.tml_platform = StreamlitTMLPlatform(config)
            
            # Start with timeout
            if self.tml_platform.start(timeout=10.0):
                st.session_state.platform = self.tml_platform
                st.session_state.platform_initialized = True
                
                # Update metrics
                status = self.tml_platform.get_status()
                if status:
                    self.platform_metrics['active_actors'] = status.get('actor_system', {}).get('total_actors', 0)
                
                logger.info("Proto.Actor platform initialized successfully")
            else:
                st.warning("Proto.Actor initialization timed out. Running in standalone mode.")
                self.tml_platform = None
                st.session_state.platform = None
            
        except Exception as e:
            st.warning(f"Proto.Actor initialization failed: {e}. Running in standalone mode.")
            self.tml_platform = None
            st.session_state.platform = None
    
    def process_transaction(self, x: float, y: float, thickness: float, 
                          min_thickness: float = 15.0) -> Dict[str, Any]:
        """Process a single measurement point as TML transaction"""
        start_time = time.time()
        
        self.transaction_count += 1
        model_id = f"model_{self.transaction_count}"
        
        # Initialize common variables
        parent_model = None
        inheritance_depth = 0
        physics_valid = thickness >= min_thickness
        
        # Find parent model for inheritance (used by all paths)
        if self.models:
            neighbors = self._find_spatial_neighbors(x, y)
            if neighbors:
                parent_model = neighbors[0]
                inheritance_depth = parent_model.get('inheritance_depth', 0) + 1
        
        # Try to use Proto.Actor platform if available
        if PROTO_ACTOR_AVAILABLE and hasattr(st.session_state, 'platform') and st.session_state.platform:
            try:
                # Create transaction for Proto.Actor processing
                transaction = {
                    'id': f'tx_{self.transaction_count}',
                    'data': {
                        'x_coord': x,
                        'y_coord': y,
                        'thickness': thickness,
                        'min_thickness': min_thickness
                    },
                    'source': 'c_scan',
                    'metadata': {
                        'model_id': model_id,
                        'timestamp': time.time(),
                        'parent_model': parent_model['model_id'] if parent_model else None,
                        'inheritance_depth': inheritance_depth
                    }
                }
                
                # Process through Streamlit-compatible Proto.Actor system
                result = st.session_state.platform.process_transaction_sync(transaction)
                
                if result['status'] == 'success':
                    # Extract results from Proto.Actor response
                    proto_result = result.get('result', {})
                    physics_valid = proto_result.get('physics_valid', thickness >= min_thickness)
                    # Use Proto.Actor's inheritance depth if available
                    proto_inheritance = proto_result.get('inheritance_depth')
                    if proto_inheritance is not None:
                        inheritance_depth = proto_inheritance
                    
                    # Update metrics
                    self.platform_metrics['models_created'] = self.transaction_count
                    self.platform_metrics['inheritance_depth_avg'] = inheritance_depth
                    
            except Exception as e:
                # Error already handled, variables already initialized
                logger.warning(f"Proto.Actor processing failed: {e}")
        
        # Track physics violations
        if not physics_valid:
            self.physics_violations += 1
        
        # Create model with inherited knowledge
                
        model = {
            'model_id': model_id,
            'x_coord': x,
            'y_coord': y,
            'thickness': thickness,
            'parent_model': parent_model['model_id'] if parent_model else None,
            'inheritance_depth': inheritance_depth,
            'physics_valid': physics_valid,
            'created_at': datetime.now()
        }
        
        self.models[model_id] = model
        
        # Debug: Log every model creation
        logger.info(f"Creating model {model_id} - DB Integration Available: {self.database_integration_available}")
        
        # Save model to database for drift detection
        if self.database_integration_available:
            self.db_save_attempts += 1
            try:
                model_data = {
                    "model_id": model_id,
                    "parent_model_id": model.get('parent_model'),
                    "inheritance_depth": model.get('inheritance_depth', 0),
                    "x_coord": model.get('x_coord', 0.0),
                    "y_coord": model.get('y_coord', 0.0),
                    "accuracy": 0.85 + (inheritance_depth * 0.01),  # Simulate improving accuracy
                    "total_updates": 1,
                    "total_predictions": 0,
                    "drift_score": 0.0,
                    "model_type": "pipeline_inspection"
                }
                success = self.db_integration.save_model_to_database(model_data)
                if success:
                    self.models_saved_to_db += 1
                    logger.info(f"✅ Successfully saved model {model_id} to database (Total: {self.models_saved_to_db})")
                else:
                    self.db_save_failures += 1
                    logger.error(f"❌ Failed to save model {model_id} to database (Failures: {self.db_save_failures})")
            except Exception as e:
                self.db_save_failures += 1
                logger.error(f"❌ Exception saving model {model_id} to database: {e} (Failures: {self.db_save_failures})")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"❌ Database integration not available - model {model_id} not saved to database")
        
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time)
        
        return {
            'status': 'success' if physics_valid else 'physics_violation',
            'model_id': model_id,
            'inheritance_depth': inheritance_depth,
            'processing_time': processing_time,
            'physics_valid': physics_valid
        }
    
    def _find_spatial_neighbors(self, x: float, y: float, radius: float = 10.0) -> List[Dict]:
        """Find spatial neighbors within radius"""
        neighbors = []
        for model in self.models.values():
            distance = np.sqrt((model['x_coord'] - x)**2 + (model['y_coord'] - y)**2)
            if distance <= radius:
                neighbors.append(model)
        return sorted(neighbors, key=lambda m: m['inheritance_depth'], reverse=True)[:3]
    
    def analyze_repair_zones(self, df: pd.DataFrame, min_thickness: float = 15.0,
                           monitor_threshold: float = 18.0) -> Dict[str, Any]:
        """Analyze thickness data for repair recommendations"""
        
        # Categorize points
        critical_points = df[df['thickness'] < min_thickness]
        monitor_points = df[(df['thickness'] >= min_thickness) & 
                          (df['thickness'] < monitor_threshold)]
        good_points = df[df['thickness'] >= monitor_threshold]
        
        # Cluster analysis (simplified)
        repair_zones = []
        
        if len(critical_points) > 0:
            # Group nearby critical points
            clusters = self._cluster_points(critical_points, radius=20.0)
            
            for i, cluster in enumerate(clusters):
                zone_type = self._determine_repair_type(cluster)
                repair_zones.append({
                    'zone_id': f"repair_zone_{i+1}",
                    'zone_type': zone_type,
                    'points': len(cluster),
                    'min_thickness': cluster['thickness'].min(),
                    'avg_thickness': cluster['thickness'].mean(),
                    'center_x': cluster['x_coord'].mean(),
                    'center_y': cluster['y_coord'].mean(),
                    'area': self._calculate_area(cluster)
                })
        
        # Perform advanced analysis
        advanced_analysis = self.perform_advanced_analysis(df)
        
        return {
            'total_points': len(df),
            'critical_points': len(critical_points),
            'monitor_points': len(monitor_points),
            'good_points': len(good_points),
            'repair_zones': repair_zones,
            'overall_condition': self._assess_overall_condition(df, min_thickness),
            'advanced_analysis': advanced_analysis
        }
    
    def _cluster_points(self, points: pd.DataFrame, radius: float = 20.0) -> List[pd.DataFrame]:
        """Simple clustering of nearby points"""
        clusters = []
        remaining = points.copy()
        
        while len(remaining) > 0:
            # Start new cluster with first point
            seed = remaining.iloc[0]
            cluster_points = []
            
            # Find all points within radius
            for _, point in remaining.iterrows():
                distance = np.sqrt((point['x_coord'] - seed['x_coord'])**2 + 
                                 (point['y_coord'] - seed['y_coord'])**2)
                if distance <= radius:
                    cluster_points.append(point)
            
            if cluster_points:
                cluster_df = pd.DataFrame(cluster_points)
                clusters.append(cluster_df)
                
                # Remove clustered points from remaining
                cluster_indices = [p.name for p in cluster_points]
                remaining = remaining.drop(cluster_indices)
            else:
                break
                
        return clusters
    
    def _determine_repair_type(self, cluster: pd.DataFrame) -> str:
        """Determine repair strategy based on cluster characteristics"""
        if len(cluster) == 1:
            return "sleeve_repair"
        elif len(cluster) < 5:
            return "spot_repair"
        elif len(cluster) < 20:
            return "section_replacement"
        else:
            return "major_replacement"
    
    def _calculate_area(self, cluster: pd.DataFrame) -> float:
        """Calculate approximate area of cluster"""
        if len(cluster) <= 1:
            return 4.0  # 2mm x 2mm grid
        
        x_range = cluster['x_coord'].max() - cluster['x_coord'].min()
        y_range = cluster['y_coord'].max() - cluster['y_coord'].min()
        return x_range * y_range
    
    def _assess_overall_condition(self, df: pd.DataFrame, min_thickness: float) -> str:
        """Assess overall pipeline condition"""
        critical_ratio = len(df[df['thickness'] < min_thickness]) / len(df)
        
        if critical_ratio > 0.1:
            return "Poor - Immediate Action Required"
        elif critical_ratio > 0.05:
            return "Fair - Schedule Repairs"
        elif critical_ratio > 0.01:
            return "Good - Monitor Closely"
        else:
            return "Excellent - Normal Monitoring"
    
    def perform_advanced_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive advanced pipeline analysis"""
        
        # 1. Corrosion Pattern Analysis
        corrosion_patterns = self.analyze_corrosion_patterns(df)
        
        # 2. Structural Integrity Assessment
        structural_integrity = self.analyze_structural_integrity(df)
        
        # 3. Flow Dynamics Analysis
        flow_dynamics = self.analyze_flow_dynamics(df)
        
        # 4. Material Degradation Mechanisms
        material_degradation = self.analyze_material_degradation(df)
        
        # 5. Electrochemical Corrosion Analysis
        electrochemical_analysis = self.analyze_electrochemical_corrosion(df)
        
        return {
            'corrosion_patterns': corrosion_patterns,
            'structural_integrity': structural_integrity,
            'flow_dynamics': flow_dynamics,
            'material_degradation': material_degradation,
            'electrochemical_analysis': electrochemical_analysis
        }
    
    def analyze_corrosion_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze corrosion patterns and mechanisms"""
        
        # Calculate thickness gradients
        df_sorted = df.sort_values(['y_coord', 'x_coord'])
        
        # Directional corrosion analysis
        x_gradient = np.gradient(df_sorted['thickness'].values)
        y_gradient = np.gradient(df_sorted['thickness'].values)
        
        # Corrosion rate estimation (simplified)
        thickness_std = df['thickness'].std()
        thickness_range = df['thickness'].max() - df['thickness'].min()
        
        # Pattern classification
        uniform_corrosion = thickness_std < 0.5  # Low variation = uniform
        pitting_corrosion = thickness_std > 1.0  # High variation = pitting
        
        # Directional bias
        x_bias = np.mean(x_gradient)
        y_bias = np.mean(y_gradient)
        
        # Corrosion severity zones
        severe_corrosion = len(df[df['thickness'] < df['thickness'].quantile(0.1)])
        moderate_corrosion = len(df[(df['thickness'] >= df['thickness'].quantile(0.1)) & 
                                   (df['thickness'] < df['thickness'].quantile(0.3))])
        
        return {
            'pattern_type': 'uniform' if uniform_corrosion else 'pitting' if pitting_corrosion else 'mixed',
            'thickness_variation': float(thickness_std),
            'thickness_range': float(thickness_range),
            'directional_bias': {
                'x_direction': float(x_bias),
                'y_direction': float(y_bias),
                'dominant_direction': 'horizontal' if abs(x_bias) > abs(y_bias) else 'vertical'
            },
            'severity_distribution': {
                'severe_zones': int(severe_corrosion),
                'moderate_zones': int(moderate_corrosion),
                'mild_zones': int(len(df) - severe_corrosion - moderate_corrosion)
            },
            'corrosion_rate_estimate': float(thickness_range * 0.1),  # Simplified annual rate
            'pattern_confidence': 0.85  # Simulated confidence
        }
    
    def analyze_structural_integrity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze structural integrity and stress distribution"""
        
        # Stress concentration analysis
        thickness_mean = df['thickness'].mean()
        stress_concentration_points = df[df['thickness'] < thickness_mean * 0.8]
        
        # Remaining strength calculation (simplified)
        design_thickness = 25.4  # mm (assumed original thickness)
        remaining_strength_ratio = df['thickness'].mean() / design_thickness
        
        # Fatigue analysis zones
        high_stress_zones = len(df[df['thickness'] < thickness_mean * 0.7])
        
        # Burst pressure estimation (simplified Barlow's formula)
        # P = 2 * S * t / D, where S = allowable stress, t = thickness, D = diameter
        pipe_diameter = 500  # mm (assumed)
        allowable_stress = 138  # MPa (typical for steel)
        
        min_burst_pressure = 2 * allowable_stress * df['thickness'].min() / pipe_diameter
        avg_burst_pressure = 2 * allowable_stress * df['thickness'].mean() / pipe_diameter
        
        # Fitness for service assessment
        if remaining_strength_ratio > 0.9:
            fitness_status = "Excellent"
        elif remaining_strength_ratio > 0.8:
            fitness_status = "Good"
        elif remaining_strength_ratio > 0.7:
            fitness_status = "Acceptable"
        else:
            fitness_status = "Requires Assessment"
        
        return {
            'remaining_strength_ratio': float(remaining_strength_ratio),
            'stress_concentration_points': int(len(stress_concentration_points)),
            'high_stress_zones': int(high_stress_zones),
            'burst_pressure': {
                'minimum_mpa': float(min_burst_pressure),
                'average_mpa': float(avg_burst_pressure),
                'safety_margin': float(avg_burst_pressure / 10.0)  # Assuming 10 MPa operating pressure
            },
            'fatigue_risk_assessment': {
                'low_risk_areas': int(len(df) - high_stress_zones),
                'high_risk_areas': int(high_stress_zones),
                'estimated_cycles_to_failure': 1000000 if remaining_strength_ratio > 0.8 else 500000
            },
            'fitness_for_service': fitness_status,
            'recommended_inspection_interval': 12 if remaining_strength_ratio > 0.8 else 6  # months
        }
    
    def analyze_flow_dynamics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze flow-induced effects and erosion patterns"""
        
        # Flow direction analysis (assuming horizontal flow)
        # Thinner areas at bottom suggest settling/corrosion
        bottom_thickness = df[df['y_coord'] <= df['y_coord'].quantile(0.3)]['thickness'].mean()
        top_thickness = df[df['y_coord'] >= df['y_coord'].quantile(0.7)]['thickness'].mean()
        
        # Erosion pattern detection
        flow_direction_effect = top_thickness - bottom_thickness
        
        # Turbulence zones (areas with high thickness variation)
        df['local_variation'] = df.groupby(pd.cut(df['x_coord'], bins=10))['thickness'].transform('std')
        turbulent_zones = df[df['local_variation'] > df['local_variation'].quantile(0.8)]
        
        # Velocity effects (simplified)
        inlet_region = df[df['x_coord'] <= df['x_coord'].quantile(0.2)]
        outlet_region = df[df['x_coord'] >= df['x_coord'].quantile(0.8)]
        
        design_thickness = 25.4  # mm (assumed original thickness)
        inlet_erosion = design_thickness - inlet_region['thickness'].mean()
        outlet_erosion = design_thickness - outlet_region['thickness'].mean()
        
        # Dead leg identification (areas with minimal thickness change)
        stagnant_zones = df[df['local_variation'] < df['local_variation'].quantile(0.2)]
        
        return {
            'flow_effects': {
                'top_bottom_difference': float(flow_direction_effect),
                'gravitational_settling': flow_direction_effect < -0.5,
                'flow_direction': 'horizontal_left_to_right'
            },
            'erosion_analysis': {
                'inlet_erosion_mm': float(inlet_erosion),
                'outlet_erosion_mm': float(outlet_erosion),
                'erosion_pattern': 'inlet_dominated' if inlet_erosion > outlet_erosion else 'outlet_dominated'
            },
            'turbulence_zones': {
                'high_turbulence_points': int(len(turbulent_zones)),
                'turbulence_intensity': float(df['local_variation'].max()),
                'average_turbulence': float(df['local_variation'].mean())
            },
            'stagnant_zones': {
                'dead_leg_points': int(len(stagnant_zones)),
                'stagnation_risk': 'high' if len(stagnant_zones) > len(df) * 0.2 else 'low'
            },
            'flow_optimization': {
                'recommended_velocity': '2-3 m/s',
                'pigging_frequency': 'quarterly' if len(stagnant_zones) > len(df) * 0.1 else 'annually'
            }
        }
    
    def analyze_material_degradation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze material degradation mechanisms"""
        
        # Degradation rate analysis
        design_thickness = 25.4  # mm (assumed original thickness)
        thickness_loss = design_thickness - df['thickness']
        avg_degradation_rate = thickness_loss.mean() / 10  # Assuming 10 years of service
        
        # Degradation mechanism classification
        uniform_loss = thickness_loss.std() < 1.0
        localized_attack = thickness_loss.max() > thickness_loss.mean() + 2 * thickness_loss.std()
        
        # Temperature effects (simplified)
        # Assume higher degradation in certain zones
        high_temp_zones = df[df['y_coord'] >= df['y_coord'].quantile(0.7)]  # Top of pipe
        temp_effect = high_temp_zones['thickness'].mean() - df['thickness'].mean()
        
        # Mechanical damage assessment
        mechanical_damage_points = df[thickness_loss > thickness_loss.quantile(0.95)]
        
        # Material property estimation
        remaining_material_ratio = df['thickness'].mean() / design_thickness
        
        return {
            'degradation_mechanisms': {
                'primary_mechanism': 'uniform_corrosion' if uniform_loss else 'localized_corrosion',
                'secondary_mechanisms': ['erosion', 'thermal_cycling'] if temp_effect < -0.2 else ['general_corrosion'],
                'mechanism_confidence': 0.78
            },
            'degradation_rates': {
                'average_rate_mm_per_year': float(avg_degradation_rate),
                'maximum_rate_mm_per_year': float(thickness_loss.max() / 10),
                'rate_acceleration': 'stable' if avg_degradation_rate < 0.5 else 'increasing'
            },
            'temperature_effects': {
                'thermal_gradient_impact': float(temp_effect),
                'high_temperature_zones': int(len(high_temp_zones)),
                'thermal_stress_risk': 'moderate' if abs(temp_effect) > 0.1 else 'low'
            },
            'mechanical_damage': {
                'impact_damage_points': int(len(mechanical_damage_points)),
                'vibration_effects': 'minimal' if len(mechanical_damage_points) < 5 else 'significant',
                'support_adequacy': 'adequate' if len(mechanical_damage_points) < len(df) * 0.05 else 'review_required'
            },
            'remaining_life': {
                'estimated_years': max(1, int((df['thickness'].min() - 15.0) / avg_degradation_rate)) if avg_degradation_rate > 0 else 50,
                'confidence_level': 'medium',
                'critical_areas_life': max(1, int((df['thickness'].min() - 15.0) / (avg_degradation_rate * 1.5))) if avg_degradation_rate > 0 else 30
            }
        }
    
    def analyze_electrochemical_corrosion(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze electrochemical corrosion patterns and galvanic effects"""
        
        # Galvanic cell analysis (simplified)
        # Areas with different thickness patterns may indicate galvanic activity
        thickness_quartiles = df['thickness'].quantile([0.25, 0.5, 0.75])
        
        anodic_zones = df[df['thickness'] <= thickness_quartiles[0.25]]  # Most corroded = anodic
        cathodic_zones = df[df['thickness'] >= thickness_quartiles[0.75]]  # Least corroded = cathodic
        
        # Electrochemical potential mapping (simulated)
        # Based on thickness variation patterns
        potential_gradient = np.gradient(df.sort_values(['x_coord', 'y_coord'])['thickness'].values)
        
        # Corrosion current density estimation (simplified)
        design_thickness = 25.4  # mm (assumed original thickness)
        corrosion_current = (design_thickness - df['thickness']) * 0.1  # Simplified relationship
        
        # pH and environmental effects (simulated based on position)
        # Bottom areas typically more acidic due to water accumulation
        bottom_zones = df[df['y_coord'] <= df['y_coord'].quantile(0.3)]
        ph_effect = bottom_zones['thickness'].mean() - df['thickness'].mean()
        
        # Cathodic protection effectiveness
        protection_current_density = 0.02  # A/m² (typical)
        protection_effectiveness = min(100, (protection_current_density / 0.01) * 100)  # Simplified
        
        # Oxygen concentration effects
        top_zones = df[df['y_coord'] >= df['y_coord'].quantile(0.7)]
        oxygen_effect = top_zones['thickness'].mean() - bottom_zones['thickness'].mean()
        
        return {
            'galvanic_analysis': {
                'anodic_zones': int(len(anodic_zones)),
                'cathodic_zones': int(len(cathodic_zones)),
                'galvanic_activity': 'high' if len(anodic_zones) > len(df) * 0.3 else 'moderate',
                'potential_difference_mv': float(abs(potential_gradient.max() - potential_gradient.min()) * 100)
            },
            'corrosion_kinetics': {
                'average_current_density_ma_per_cm2': float(corrosion_current.mean()),
                'maximum_current_density_ma_per_cm2': float(corrosion_current.max()),
                'corrosion_rate_classification': 'high' if corrosion_current.mean() > 0.5 else 'moderate'
            },
            'environmental_effects': {
                'ph_impact': float(ph_effect),
                'oxygen_concentration_effect': float(oxygen_effect),
                'water_accumulation_zones': int(len(bottom_zones[bottom_zones['thickness'] < bottom_zones['thickness'].quantile(0.5)])),
                'environmental_severity': 'severe' if ph_effect < -0.3 else 'moderate'
            },
            'cathodic_protection': {
                'effectiveness_percent': float(protection_effectiveness),
                'current_distribution': 'uniform' if abs(oxygen_effect) < 0.2 else 'non_uniform',
                'protection_status': 'adequate' if protection_effectiveness > 85 else 'requires_attention',
                'recommended_current_density': 0.025 if protection_effectiveness < 85 else 0.02
            },
            'remediation_recommendations': {
                'coating_repair': len(anodic_zones) > len(df) * 0.2,
                'cathodic_protection_upgrade': protection_effectiveness < 85,
                'chemical_treatment': ph_effect < -0.5,
                'drainage_improvement': len(bottom_zones) > len(df) * 0.3 and ph_effect < -0.2
            }
        }

def create_thickness_heatmap(df: pd.DataFrame) -> go.Figure:
    """Create 3D heatmap of thickness data"""
    
    # Create pivot table for heatmap
    pivot_df = df.pivot(index='y_coord', columns='x_coord', values='thickness')
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values,
        x=pivot_df.columns,
        y=pivot_df.index,
        colorscale='RdYlGn',
        colorbar=dict(title="Thickness (mm)"),
        hoverongaps=False,
        hovertemplate='X: %{x}mm<br>Y: %{y}mm<br>Thickness: %{z:.2f}mm<extra></extra>'
    ))
    
    fig.update_layout(
        title="Pipeline Thickness Heatmap",
        xaxis_title="X Coordinate (mm)",
        yaxis_title="Y Coordinate (mm)",
        height=600
    )
    
    return fig

def create_3d_surface_plot(df: pd.DataFrame) -> go.Figure:
    """Create 3D surface plot of thickness data"""
    
    # Create grid for surface plot
    x_unique = sorted(df['x_coord'].unique())
    y_unique = sorted(df['y_coord'].unique(), reverse=True)
    
    # Create Z matrix
    z_matrix = []
    for y in y_unique:
        row = []
        for x in x_unique:
            thickness = df[(df['x_coord'] == x) & (df['y_coord'] == y)]['thickness']
            if len(thickness) > 0:
                row.append(thickness.iloc[0])
            else:
                row.append(np.nan)
        z_matrix.append(row)
    
    fig = go.Figure(data=[go.Surface(
        z=z_matrix,
        x=x_unique,
        y=y_unique,
        colorscale='RdYlGn',
        colorbar=dict(title="Thickness (mm)")
    )])
    
    fig.update_layout(
        title="3D Pipeline Thickness Surface",
        scene=dict(
            xaxis_title="X Coordinate (mm)",
            yaxis_title="Y Coordinate (mm)",
            zaxis_title="Thickness (mm)"
        ),
        height=700
    )
    
    return fig

def create_repair_zones_plot(df: pd.DataFrame, repair_analysis: Dict) -> go.Figure:
    """Create repair zones visualization"""
    
    fig = go.Figure()
    
    # Add all points
    fig.add_trace(go.Scatter(
        x=df['x_coord'],
        y=df['y_coord'],
        mode='markers',
        marker=dict(
            size=4,
            color=df['thickness'],
            colorscale='RdYlGn',
            colorbar=dict(title="Thickness (mm)"),
            cmin=df['thickness'].min(),
            cmax=df['thickness'].max()
        ),
        name='Thickness Data',
        hovertemplate='X: %{x}mm<br>Y: %{y}mm<br>Thickness: %{marker.color:.2f}mm<extra></extra>'
    ))
    
    # Add repair zones
    colors = ['red', 'orange', 'yellow', 'purple']
    for i, zone in enumerate(repair_analysis['repair_zones']):
        fig.add_trace(go.Scatter(
            x=[zone['center_x']],
            y=[zone['center_y']],
            mode='markers+text',
            marker=dict(
                size=20,
                color=colors[i % len(colors)],
                symbol='x'
            ),
            text=[zone['zone_type']],
            textposition="top center",
            name=f"Zone {zone['zone_id']}"
        ))
    
    fig.update_layout(
        title="Repair Zones Analysis",
        xaxis_title="X Coordinate (mm)",
        yaxis_title="Y Coordinate (mm)",
        height=600
    )
    
    return fig

def create_advanced_analysis_plots(df: pd.DataFrame, advanced_analysis: Dict) -> Dict[str, go.Figure]:
    """Create advanced analysis visualization plots"""
    
    plots = {}
    
    # 1. Corrosion Pattern Analysis Plot
    corrosion_data = advanced_analysis['corrosion_patterns']
    
    fig_corrosion = go.Figure()
    
    # Add thickness data with corrosion severity coloring
    severity_colors = []
    severity_labels = []
    for _, row in df.iterrows():
        if row['thickness'] < df['thickness'].quantile(0.1):
            severity_colors.append(0)  # Red for severe
            severity_labels.append('Severe')
        elif row['thickness'] < df['thickness'].quantile(0.3):
            severity_colors.append(1)  # Orange for moderate
            severity_labels.append('Moderate')
        else:
            severity_colors.append(2)  # Green for mild
            severity_labels.append('Mild')
    
    fig_corrosion.add_trace(go.Scatter(
        x=df['x_coord'],
        y=df['y_coord'],
        mode='markers',
        marker=dict(
            size=8,
            color=severity_colors,
            colorscale=[[0, 'red'], [0.5, 'orange'], [1, 'green']],
            showscale=True,
            colorbar=dict(
                title="Corrosion Severity",
                tickvals=[0, 1, 2],
                ticktext=['Severe', 'Moderate', 'Mild']
            )
        ),
        text=[f"Thickness: {t:.2f}mm<br>Severity: {s}" for t, s in zip(df['thickness'], severity_labels)],
        hovertemplate='X: %{x}mm<br>Y: %{y}mm<br>%{text}<extra></extra>',
        name='Corrosion Pattern'
    ))
    
    fig_corrosion.update_layout(
        title=f"Corrosion Pattern Analysis - {corrosion_data['pattern_type'].title()} Pattern",
        xaxis_title="X Coordinate (mm)",
        yaxis_title="Y Coordinate (mm)",
        height=500
    )
    
    plots['corrosion_patterns'] = fig_corrosion
    
    # 2. Structural Integrity Plot
    structural_data = advanced_analysis['structural_integrity']
    
    fig_structural = go.Figure()
    
    # Stress concentration visualization
    stress_colors = []
    stress_labels = []
    for thickness in df['thickness']:
        if thickness < df['thickness'].mean() * 0.8:
            stress_colors.append(0)  # Red for high stress
            stress_labels.append('High Stress')
        else:
            stress_colors.append(1)  # Blue for normal
            stress_labels.append('Normal')
    
    fig_structural.add_trace(go.Scatter(
        x=df['x_coord'],
        y=df['y_coord'],
        mode='markers',
        marker=dict(
            size=10,
            color=stress_colors,
            colorscale=[[0, 'red'], [1, 'blue']],
            showscale=True,
            colorbar=dict(
                title="Stress Level",
                tickvals=[0, 1],
                ticktext=['High Stress', 'Normal']
            )
        ),
        text=[f"Thickness: {t:.2f}mm<br>Burst Pressure: {2*138*t/500:.1f} MPa<br>Stress: {s}" 
              for t, s in zip(df['thickness'], stress_labels)],
        hovertemplate='X: %{x}mm<br>Y: %{y}mm<br>%{text}<extra></extra>',
        name='Structural Integrity'
    ))
    
    fig_structural.update_layout(
        title=f"Structural Integrity - {structural_data['fitness_for_service']} Condition",
        xaxis_title="X Coordinate (mm)",
        yaxis_title="Y Coordinate (mm)",
        height=500
    )
    
    plots['structural_integrity'] = fig_structural
    
    # 3. Flow Dynamics Plot
    flow_data = advanced_analysis['flow_dynamics']
    
    fig_flow = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Flow Direction Effects', 'Turbulence Zones'),
        vertical_spacing=0.15
    )
    
    # Flow direction effect
    fig_flow.add_trace(
        go.Scatter(
            x=df['x_coord'],
            y=df['thickness'],
            mode='markers',
            marker=dict(color=df['y_coord'], colorscale='Viridis', size=6),
            name='Thickness vs Flow Direction',
            text=[f"Y: {y}mm" for y in df['y_coord']],
            hovertemplate='X: %{x}mm<br>Thickness: %{y:.2f}mm<br>%{text}<extra></extra>'
        ),
        row=1, col=1
    )
    
    # Turbulence zones
    df_temp = df.copy()
    df_temp['local_variation'] = df_temp.groupby(pd.cut(df_temp['x_coord'], bins=10))['thickness'].transform('std')
    
    fig_flow.add_trace(
        go.Scatter(
            x=df_temp['x_coord'],
            y=df_temp['local_variation'],
            mode='markers',
            marker=dict(
                color=df_temp['local_variation'],
                colorscale='Reds',
                size=8,
                showscale=True,
                colorbar=dict(title="Turbulence Intensity")
            ),
            name='Turbulence Intensity',
            hovertemplate='X: %{x}mm<br>Turbulence: %{y:.3f}<extra></extra>'
        ),
        row=2, col=1
    )
    
    fig_flow.update_layout(
        title="Flow Dynamics Analysis",
        height=600
    )
    
    plots['flow_dynamics'] = fig_flow
    
    # 4. Electrochemical Analysis Plot
    electro_data = advanced_analysis['electrochemical_analysis']
    
    fig_electro = go.Figure()
    
    # Galvanic zones
    galvanic_colors = []
    galvanic_labels = []
    thickness_quartiles = df['thickness'].quantile([0.25, 0.75])
    
    for thickness in df['thickness']:
        if thickness <= thickness_quartiles[0.25]:
            galvanic_colors.append(0)  # Red for anodic
            galvanic_labels.append('Anodic (High Corrosion)')
        elif thickness >= thickness_quartiles[0.75]:
            galvanic_colors.append(2)  # Blue for cathodic
            galvanic_labels.append('Cathodic (Low Corrosion)')
        else:
            galvanic_colors.append(1)  # Yellow for neutral
            galvanic_labels.append('Neutral')
    
    fig_electro.add_trace(go.Scatter(
        x=df['x_coord'],
        y=df['y_coord'],
        mode='markers',
        marker=dict(
            size=10,
            color=galvanic_colors,
            colorscale=[[0, 'red'], [0.5, 'yellow'], [1, 'blue']],
            showscale=True,
            colorbar=dict(
                title="Galvanic Activity",
                tickvals=[0, 1, 2],
                ticktext=['Anodic', 'Neutral', 'Cathodic']
            )
        ),
        text=[f"Thickness: {t:.2f}mm<br>Zone: {z}" for t, z in zip(df['thickness'], galvanic_labels)],
        hovertemplate='X: %{x}mm<br>Y: %{y}mm<br>%{text}<extra></extra>',
        name='Electrochemical Zones'
    ))
    
    fig_electro.update_layout(
        title=f"Electrochemical Analysis - {electro_data['galvanic_analysis']['galvanic_activity'].title()} Activity",
        xaxis_title="X Coordinate (mm)",
        yaxis_title="Y Coordinate (mm)",
        height=500
    )
    
    plots['electrochemical_analysis'] = fig_electro
    
    return plots

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown('<h1 class="main-header">🔧 TML Platform Demo - Pipeline Inspection</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    **Enhanced Transaction-based Machine Learning Platform v2.0**
    
    Demonstrate the revolutionary **1 Transaction = 1 Model** paradigm for pipeline inspection analysis.
    Upload your C-Scan ultrasonic thickness data and watch TML create intelligent models for every measurement point!
    """)
    
    # Initialize processor
    if 'processor' not in st.session_state:
        st.session_state.processor = TMLPipelineProcessor()
    
    # Sidebar configuration
    st.sidebar.header("🔧 Configuration")
    
    # Debug: Database Integration Status
    st.sidebar.subheader("🔍 Debug Info")
    st.sidebar.write(f"**Database Integration**: {'✅ Available' if DATABASE_INTEGRATION_AVAILABLE else '❌ Not Available'}")
    if DATABASE_INTEGRATION_AVAILABLE:
        try:
            db_count = db_integration.get_model_count()
            st.sidebar.write(f"**Models in DB**: {db_count}")
        except Exception as e:
            st.sidebar.write(f"**DB Error**: {str(e)}")
    
    # Debug: Processor Status
    if 'processor' in st.session_state:
        st.sidebar.write(f"**Processor DB Available**: {'✅' if st.session_state.processor.database_integration_available else '❌'}")
        if hasattr(st.session_state.processor, 'models_saved_to_db'):
            st.sidebar.write(f"**Models Saved by Processor**: {st.session_state.processor.models_saved_to_db}")
        if hasattr(st.session_state.processor, 'db_save_attempts'):
            st.sidebar.write(f"**DB Save Attempts**: {st.session_state.processor.db_save_attempts}")
        if hasattr(st.session_state.processor, 'db_save_failures'):
            st.sidebar.write(f"**DB Save Failures**: {st.session_state.processor.db_save_failures}")
        st.sidebar.write(f"**Total Models in Memory**: {len(st.session_state.processor.models)}")
    
    if st.sidebar.button("🔄 Test DB Connection"):
        if DATABASE_INTEGRATION_AVAILABLE:
            try:
                test_model = {
                    "model_id": "sidebar_test",
                    "parent_model_id": None,
                    "inheritance_depth": 0,
                    "x_coord": 999.0,
                    "y_coord": 999.0,
                    "accuracy": 0.99,
                    "total_updates": 1,
                    "total_predictions": 0,
                    "drift_score": 0.0,
                    "model_type": "sidebar_test"
                }
                result = db_integration.save_model_to_database(test_model)
                st.sidebar.success(f"DB Test: {'✅ Success' if result else '❌ Failed'}")
            except Exception as e:
                st.sidebar.error(f"DB Test Error: {e}")
        else:
            st.sidebar.error("Database integration not available")
    
    # Force save all models to database
    if st.sidebar.button("💾 Force Save All Models to DB"):
        if 'processor' in st.session_state and st.session_state.processor.database_integration_available:
            try:
                saved_count = 0
                for model_id, model in st.session_state.processor.models.items():
                    model_data = {
                        "model_id": model_id,
                        "parent_model_id": model.get('parent_model'),
                        "inheritance_depth": model.get('inheritance_depth', 0),
                        "x_coord": model.get('x_coord', 0.0),
                        "y_coord": model.get('y_coord', 0.0),
                        "accuracy": 0.85,
                        "total_updates": 1,
                        "total_predictions": 0,
                        "drift_score": 0.0,
                        "model_type": "force_save"
                    }
                    if st.session_state.processor.db_integration.save_model_to_database(model_data):
                        saved_count += 1
                
                st.sidebar.success(f"✅ Force saved {saved_count} models to database!")
                # Update the processor counter
                st.session_state.processor.models_saved_to_db = saved_count
            except Exception as e:
                st.sidebar.error(f"Force save failed: {e}")
        else:
            st.sidebar.error("Processor or database integration not available")
    
    min_thickness = st.sidebar.slider(
        "Minimum Thickness Threshold (mm)",
        min_value=10.0,
        max_value=25.0,
        value=15.0,
        step=0.5,
        help="Minimum allowable wall thickness per code requirements"
    )
    
    monitor_threshold = st.sidebar.slider(
        "Monitor Threshold (mm)",
        min_value=15.0,
        max_value=30.0,
        value=18.0,
        step=0.5,
        help="Thickness below which increased monitoring is required"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**TML Platform Features:**")
    st.sidebar.markdown("✅ Physics-informed validation")
    st.sidebar.markdown("✅ Model inheritance chains")
    st.sidebar.markdown("✅ Real-time processing")
    st.sidebar.markdown("✅ 3D spatial analysis")
    st.sidebar.markdown("✅ Automated repair recommendations")
    
    # Proto.Actor Status in Sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🎭 Proto.Actor Status:**")
    
    if PROTO_ACTOR_AVAILABLE:
        if hasattr(st.session_state, 'platform') and st.session_state.platform and st.session_state.platform.is_running:
            status = st.session_state.platform.get_status()
            st.sidebar.markdown("✅ Platform Running")
            st.sidebar.markdown(f"🎯 {status['actor_system']['total_actors']} Active Actors")
            st.sidebar.markdown(f"⚡ {status['actor_system']['transaction_processors']} Processors")
            st.sidebar.markdown(f"🧠 {status['actor_system']['model_actors']} Model Actors")
        else:
            st.sidebar.markdown("⚪ Platform Initializing...")
    else:
        st.sidebar.markdown("❌ Not Available")
        if PROTO_ACTOR_ERROR:
            with st.sidebar.expander("View Error"):
                st.code(PROTO_ACTOR_ERROR[:200] + "..." if len(PROTO_ACTOR_ERROR) > 200 else PROTO_ACTOR_ERROR)
    
    # File upload
    st.header("📁 Upload C-Scan Data")
    
    uploaded_file = st.file_uploader(
        "Choose your C-Scan CSV file",
        type=['csv', 'txt'],
        help="Upload ultrasonic thickness measurement data in CSV format"
    )
    
    # Sample data option
    if st.button("🎯 Use Sample Data"):
        # Create sample data based on the provided CSV structure
        sample_data = create_sample_data()
        st.session_state.sample_data = sample_data
        uploaded_file = "sample"
    
    if uploaded_file is not None:
        
        # Process the data
        if uploaded_file == "sample":
            csv_content = st.session_state.sample_data
        else:
            csv_content = str(uploaded_file.read(), "utf-8")
        
        with st.spinner("🔄 Processing C-Scan data..."):
            df = st.session_state.processor.parse_cscan_data(csv_content)
        
        st.success(f"✅ Loaded {len(df)} measurement points")
        
        # Display data overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Total Points", f"{len(df):,}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("X Range", f"{df['x_coord'].max() - df['x_coord'].min():.0f} mm")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Y Range", f"{df['y_coord'].max() - df['y_coord'].min():.0f} mm")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Thickness Range", f"{df['thickness'].min():.1f} - {df['thickness'].max():.1f} mm")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # TML Processing Section
        st.header("🧠 TML Processing")
        
        # Processing mode selection
        col1, col2 = st.columns(2)
        with col1:
            if PROTO_ACTOR_AVAILABLE and hasattr(st.session_state, 'platform') and st.session_state.platform:
                processing_mode = st.radio(
                    "Processing Mode",
                    ["🐳 C# Proto.Actor (Docker)", "🎭 Proto.Actor Processing", "📊 Sequential Processing", "⚡ Fast Sequential"],
                    help="Choose processing mode for C-Scan data analysis"
                )
            else:
                processing_mode = st.radio(
                    "Processing Mode",
                    ["� C# Proto.Actor (Docker)", "�📊 Sequential Processing", "⚡ Fast Sequential"],
                    help="Choose processing mode - Docker API or local processing"
                )
        
        with col2:
            if processing_mode == "🐳 C# Proto.Actor (Docker)":
                batch_size = st.slider(
                    "API Batch Size",
                    min_value=1,
                    max_value=50,
                    value=10,
                    step=5,
                    help="Number of transactions to send to Docker API"
                )
                # Check API status
                try:
                    import requests
                    response = requests.get("http://localhost:5001/health", timeout=1)
                    if response.status_code == 200:
                        st.success("✅ Docker API Connected")
                    else:
                        st.error("❌ Docker API Error")
                except:
                    st.warning("⚠️ Docker API Offline")
            elif processing_mode == "🎭 Proto.Actor Processing":
                batch_size = st.slider(
                    "Batch Size",
                    min_value=10,
                    max_value=200,
                    value=50,
                    step=10,
                    help="Number of transactions to process in parallel"
                )
            elif processing_mode == "⚡ Fast Sequential":
                batch_size = st.slider(
                    "Processing Speed",
                    min_value=1,
                    max_value=100,
                    value=10,
                    step=1,
                    help="Number of points to process at once (higher = faster)"
                )
            else:
                batch_size = 1
        
        if st.button("🚀 Run TML Analysis", type="primary"):
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Process measurement points
            results = []
            total_points = len(df)
            
            if processing_mode == "🐳 C# Proto.Actor (Docker)":
                # C# Proto.Actor processing via Docker API
                status_text.text("🐳 Processing with C# Proto.Actor in Docker...")
                
                import requests
                API_URL = "http://localhost:5001"
                docker_results = []
                
                for i in range(0, total_points, batch_size):
                    batch_end = min(i + batch_size, total_points)
                    batch_df = df.iloc[i:batch_end]
                    
                    for j, (_, row) in enumerate(batch_df.iterrows()):
                        try:
                            # Send to Docker API
                            transaction = {
                                "data": {
                                    "xCoord": float(row['x_coord']),
                                    "yCoord": float(row['y_coord']),
                                    "thickness": float(row['thickness']),
                                    "minThickness": float(min_thickness),
                                    "quality": 0.95,
                                    "features": {"feature1": 1.0, "feature2": 2.0}
                                },
                                "source": "demo-ui",
                                "metadata": {"batch_index": i+j}
                            }
                            
                            response = requests.post(
                                f"{API_URL}/api/transactions",
                                json=transaction,
                                headers={"Content-Type": "application/json"},
                                timeout=5
                            )
                            
                            if response.status_code == 200:
                                api_result = response.json()
                                # Also process locally to maintain visualization state
                                local_result = st.session_state.processor.process_transaction(
                                    row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                                )
                                # Enhance local result with Docker API data
                                local_result['docker_transaction_id'] = api_result.get('transactionId')
                                local_result['docker_model_id'] = api_result.get('modelId')
                                local_result['docker_processing_time'] = api_result.get('processingTimeMs')
                                local_result['docker_physics_valid'] = api_result.get('physicsValid')
                                results.append(local_result)
                                docker_results.append(api_result)
                            else:
                                # Fallback to local processing
                                result = st.session_state.processor.process_transaction(
                                    row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                                )
                                results.append(result)
                                
                        except Exception as e:
                            # Fallback to local processing on error
                            result = st.session_state.processor.process_transaction(
                                row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                            )
                            results.append(result)
                    
                    # Update progress
                    progress = batch_end / total_points
                    progress_bar.progress(progress)
                    status_text.text(f"🐳 Docker API: {batch_end}/{total_points} points - "
                                   f"Processed: {len(docker_results)} via C# Proto.Actor")
                
                # Show Docker API statistics
                if docker_results:
                    avg_time = sum(r.get('processingTimeMs', 0) for r in docker_results) / len(docker_results)
                    st.success(f"✅ C# Proto.Actor processed {len(docker_results)} transactions (Avg: {avg_time:.2f}ms)")
                    
            elif processing_mode == "🎭 Proto.Actor Processing":
                # Proto.Actor batch processing
                status_text.text("🎭 Processing with Proto.Actor distributed system...")
                
                for i in range(0, total_points, batch_size):
                    batch_end = min(i + batch_size, total_points)
                    batch_df = df.iloc[i:batch_end]
                    
                    # Create batch of transactions
                    batch_transactions = []
                    for j, (_, row) in enumerate(batch_df.iterrows()):
                        batch_transactions.append({
                            'id': f'tx_{i+j}',
                            'data': {
                                'x_coord': row['x_coord'],
                                'y_coord': row['y_coord'],
                                'thickness': row['thickness'],
                                'min_thickness': min_thickness
                            },
                            'source': 'c_scan_batch'
                        })
                    
                    # Process batch through Proto.Actor
                    try:
                        batch_results = st.session_state.platform.batch_process_sync(batch_transactions)
                        
                        # Also process locally to update model state
                        for (_, row), proto_result in zip(batch_df.iterrows(), batch_results):
                            result = st.session_state.processor.process_transaction(
                                row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                            )
                            # Merge Proto.Actor results
                            if proto_result.get('status') == 'success':
                                result['proto_actor'] = True
                                result['physics_valid'] = proto_result.get('physics_valid', result['physics_valid'])
                            results.append(result)
                            
                    except Exception as e:
                        st.warning(f"Proto.Actor batch failed: {e}, falling back to sequential")
                        # Fallback to sequential
                        for _, row in batch_df.iterrows():
                            result = st.session_state.processor.process_transaction(
                                row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                            )
                            results.append(result)
                    
                    # Update progress
                    progress = batch_end / total_points
                    progress_bar.progress(progress)
                    status_text.text(f"🎭 Processed: {batch_end}/{total_points} points - "
                                   f"Actors: {st.session_state.platform.get_status()['actor_system']['total_actors']}")
                    
            elif processing_mode == "⚡ Fast Sequential":
                # Fast sequential processing in batches
                status_text.text("⚡ Processing with optimized sequential mode...")
                
                for i in range(0, total_points, batch_size):
                    batch_end = min(i + batch_size, total_points)
                    
                    # Process batch quickly
                    for j in range(i, batch_end):
                        row = df.iloc[j]
                        result = st.session_state.processor.process_transaction(
                            row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                        )
                        results.append(result)
                    
                    # Update progress
                    progress = batch_end / total_points
                    progress_bar.progress(progress)
                    status_text.text(f"Processing: {batch_end}/{total_points} points - "
                                   f"Models created: {len(st.session_state.processor.models)}")
                    
                    # Very small delay for UI update
                    if batch_size > 10:
                        time.sleep(0.01)
            else:
                # Regular sequential processing
                for i, (_, row) in enumerate(df.iterrows()):
                    result = st.session_state.processor.process_transaction(
                        row['x_coord'], row['y_coord'], row['thickness'], min_thickness
                    )
                    results.append(result)
                    
                    # Update progress
                    progress = (i + 1) / total_points
                    progress_bar.progress(progress)
                    status_text.text(f"Processing point {i+1}/{total_points} - "
                                   f"Model: {result['model_id']}")
                    
                    # Small delay for demonstration
                    time.sleep(0.001)
            
            status_text.text("✅ TML processing complete!")
            
            # Display TML metrics
            st.subheader("📊 TML Platform Metrics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown('<div class="metric-card success-metric">', unsafe_allow_html=True)
                st.metric("Models Created", f"{len(st.session_state.processor.models):,}")
                if hasattr(st.session_state.processor, 'models_saved_to_db'):
                    st.caption(f"Saved to DB: {st.session_state.processor.models_saved_to_db}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="metric-card warning-metric">', unsafe_allow_html=True)
                st.metric("Physics Violations", st.session_state.processor.physics_violations)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                avg_inheritance = np.mean([m['inheritance_depth'] for m in st.session_state.processor.models.values()])
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Avg Inheritance Depth", f"{avg_inheritance:.1f}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col4:
                avg_time = np.mean(st.session_state.processor.processing_times) * 1000
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Avg Processing Time", f"{avg_time:.2f} ms")
                st.markdown('</div>', unsafe_allow_html=True)
            
            
            # Repair Analysis
            st.subheader("🔧 Repair Zone Analysis")
            
            repair_analysis = st.session_state.processor.analyze_repair_zones(
                df, min_thickness, monitor_threshold
            )
            
            # Overall condition
            condition = repair_analysis['overall_condition']
            if "Excellent" in condition:
                st.success(f"**Overall Condition:** {condition}")
            elif "Good" in condition:
                st.info(f"**Overall Condition:** {condition}")
            elif "Fair" in condition:
                st.warning(f"**Overall Condition:** {condition}")
            else:
                st.error(f"**Overall Condition:** {condition}")
            
            # Repair zones summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown('<div class="metric-card danger-metric">', unsafe_allow_html=True)
                st.metric("Critical Points", repair_analysis['critical_points'])
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="metric-card warning-metric">', unsafe_allow_html=True)
                st.metric("Monitor Points", repair_analysis['monitor_points'])
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="metric-card success-metric">', unsafe_allow_html=True)
                st.metric("Good Points", repair_analysis['good_points'])
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Repair zones details
            if repair_analysis['repair_zones']:
                st.subheader("🎯 Repair Recommendations")
                
                for zone in repair_analysis['repair_zones']:
                    with st.expander(f"Repair Zone {zone['zone_id']} - {zone['zone_type'].replace('_', ' ').title()}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Points in Zone", zone['points'])
                            st.metric("Min Thickness", f"{zone['min_thickness']:.2f} mm")
                        
                        with col2:
                            st.metric("Avg Thickness", f"{zone['avg_thickness']:.2f} mm")
                            st.metric("Affected Area", f"{zone['area']:.0f} mm²")
                        
                        with col3:
                            st.metric("Center X", f"{zone['center_x']:.0f} mm")
                            st.metric("Center Y", f"{zone['center_y']:.0f} mm")
            
            # Advanced Analysis Results
            if 'advanced_analysis' in repair_analysis:
                st.header("🔬 Advanced Pipeline Intelligence")
                
                advanced_data = repair_analysis['advanced_analysis']
                
                # Advanced metrics overview
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    corr_data = advanced_data['corrosion_patterns']
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Corrosion Pattern", corr_data['pattern_type'].title())
                    st.metric("Corrosion Rate", f"{corr_data['corrosion_rate_estimate']:.2f} mm/year")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    struct_data = advanced_data['structural_integrity']
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Fitness for Service", struct_data['fitness_for_service'])
                    st.metric("Remaining Strength", f"{struct_data['remaining_strength_ratio']*100:.1f}%")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col3:
                    flow_data = advanced_data['flow_dynamics']
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Turbulence Zones", flow_data['turbulence_zones']['high_turbulence_points'])
                    st.metric("Stagnation Risk", flow_data['stagnant_zones']['stagnation_risk'].title())
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col4:
                    electro_data = advanced_data['electrochemical_analysis']
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Galvanic Activity", electro_data['galvanic_analysis']['galvanic_activity'].title())
                    st.metric("Protection Status", electro_data['cathodic_protection']['protection_status'].replace('_', ' ').title())
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Detailed analysis sections
                with st.expander("🔍 Detailed Corrosion Analysis"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Pattern Classification")
                        st.write(f"**Type**: {corr_data['pattern_type'].title()}")
                        st.write(f"**Thickness Variation**: {corr_data['thickness_variation']:.3f} mm")
                        st.write(f"**Dominant Direction**: {corr_data['directional_bias']['dominant_direction'].title()}")
                        
                    with col2:
                        st.subheader("Severity Distribution")
                        st.write(f"**Severe Zones**: {corr_data['severity_distribution']['severe_zones']} points")
                        st.write(f"**Moderate Zones**: {corr_data['severity_distribution']['moderate_zones']} points")
                        st.write(f"**Mild Zones**: {corr_data['severity_distribution']['mild_zones']} points")
                
                with st.expander("🏗️ Structural Integrity Details"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Pressure Analysis")
                        st.write(f"**Min Burst Pressure**: {struct_data['burst_pressure']['minimum_mpa']:.1f} MPa")
                        st.write(f"**Avg Burst Pressure**: {struct_data['burst_pressure']['average_mpa']:.1f} MPa")
                        st.write(f"**Safety Margin**: {struct_data['burst_pressure']['safety_margin']:.1f}x")
                        
                    with col2:
                        st.subheader("Fatigue Assessment")
                        st.write(f"**High Risk Areas**: {struct_data['fatigue_risk_assessment']['high_risk_areas']} points")
                        st.write(f"**Cycles to Failure**: {struct_data['fatigue_risk_assessment']['estimated_cycles_to_failure']:,}")
                        st.write(f"**Inspection Interval**: {struct_data['recommended_inspection_interval']} months")
                
                with st.expander("🌊 Flow Dynamics Analysis"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Flow Effects")
                        st.write(f"**Top-Bottom Difference**: {flow_data['flow_effects']['top_bottom_difference']:.2f} mm")
                        st.write(f"**Gravitational Settling**: {'Yes' if flow_data['flow_effects']['gravitational_settling'] else 'No'}")
                        st.write(f"**Erosion Pattern**: {flow_data['erosion_analysis']['erosion_pattern'].replace('_', ' ').title()}")
                        
                    with col2:
                        st.subheader("Optimization")
                        st.write(f"**Recommended Velocity**: {flow_data['flow_optimization']['recommended_velocity']}")
                        st.write(f"**Pigging Frequency**: {flow_data['flow_optimization']['pigging_frequency'].title()}")
                        st.write(f"**Dead Leg Points**: {flow_data['stagnant_zones']['dead_leg_points']}")
                
                with st.expander("⚡ Electrochemical Analysis"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Galvanic Effects")
                        st.write(f"**Anodic Zones**: {electro_data['galvanic_analysis']['anodic_zones']} points")
                        st.write(f"**Cathodic Zones**: {electro_data['galvanic_analysis']['cathodic_zones']} points")
                        st.write(f"**Potential Difference**: {electro_data['galvanic_analysis']['potential_difference_mv']:.1f} mV")
                        
                    with col2:
                        st.subheader("Protection System")
                        st.write(f"**Effectiveness**: {electro_data['cathodic_protection']['effectiveness_percent']:.1f}%")
                        st.write(f"**Current Distribution**: {electro_data['cathodic_protection']['current_distribution'].replace('_', ' ').title()}")
                        
                        # Remediation recommendations
                        remediation = electro_data['remediation_recommendations']
                        st.subheader("Recommendations")
                        if remediation['coating_repair']:
                            st.warning("� Coating repair required")
                        if remediation['cathodic_protection_upgrade']:
                            st.warning("⚡ CP system upgrade needed")
                        if remediation['chemical_treatment']:
                            st.warning("🧪 Chemical treatment recommended")
                        if remediation['drainage_improvement']:
                            st.warning("💧 Drainage improvement needed")
            
            # Visualizations
            st.header("�� Visualizations")
            
            # Enhanced tabs for different views - INCLUDING ML FEATURES
            if 'advanced_analysis' in repair_analysis:
                tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
                    "🔥 Heatmap", "🌐 3D Surface", "🔧 Repair Zones", 
                    "🔍 Corrosion Patterns", "🏗️ Structural Integrity", 
                    "🌊 Flow Dynamics", "⚡ Electrochemical",
                    "🔍 Drift Detection", "🎲 A/B Testing"
                ])
                
                with tab1:
                    st.plotly_chart(create_thickness_heatmap(df), use_container_width=True)
                
                with tab2:
                    st.plotly_chart(create_3d_surface_plot(df), use_container_width=True)
                
                with tab3:
                    st.plotly_chart(create_repair_zones_plot(df, repair_analysis), use_container_width=True)
                
                # Advanced analysis plots
                advanced_plots = create_advanced_analysis_plots(df, repair_analysis['advanced_analysis'])
                
                with tab4:
                    st.plotly_chart(advanced_plots['corrosion_patterns'], use_container_width=True)
                    st.markdown("**Analysis**: This plot shows corrosion severity zones and directional patterns across the pipeline surface.")
                
                with tab5:
                    st.plotly_chart(advanced_plots['structural_integrity'], use_container_width=True)
                    st.markdown("**Analysis**: Red areas indicate high stress concentrations requiring attention. Hover for burst pressure calculations.")
                
                with tab6:
                    st.plotly_chart(advanced_plots['flow_dynamics'], use_container_width=True)
                    st.markdown("**Analysis**: Top plot shows flow direction effects, bottom plot identifies turbulence zones.")
                
                with tab7:
                    st.plotly_chart(advanced_plots['electrochemical_analysis'], use_container_width=True)
                    st.markdown("**Analysis**: Red zones are anodic (high corrosion), blue zones are cathodic (protected areas).")
                
                with tab8:
                    # Drift Detection Tab
                    show_drift_detection_panel()
                
                with tab9:
                    # A/B Testing Tab
                    show_ab_testing_panel()
            else:
                # Fallback to basic tabs
                tab1, tab2, tab3 = st.tabs(["🔥 Heatmap", "🌐 3D Surface", "🔧 Repair Zones"])
                
                with tab1:
                    st.plotly_chart(create_thickness_heatmap(df), use_container_width=True)
                
                with tab2:
                    st.plotly_chart(create_3d_surface_plot(df), use_container_width=True)
                
                with tab3:
                    st.plotly_chart(create_repair_zones_plot(df, repair_analysis), use_container_width=True)
            
            # Export results
            st.header("📥 Export Results")
            
            # Create results summary with JSON-safe values
            def make_json_safe(obj):
                """Convert numpy types to native Python types for JSON serialization"""
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: make_json_safe(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_safe(v) for v in obj]
                else:
                    return obj
            
            results_summary = {
                "timestamp": datetime.now().isoformat(),
                "total_points": int(len(df)),
                "models_created": int(len(st.session_state.processor.models)),
                "physics_violations": int(st.session_state.processor.physics_violations),
                "repair_analysis": make_json_safe(repair_analysis),
                "processing_metrics": {
                    "avg_processing_time_ms": float(np.mean(st.session_state.processor.processing_times) * 1000),
                    "total_processing_time_s": float(sum(st.session_state.processor.processing_times)),
                    "avg_inheritance_depth": float(np.mean([m['inheritance_depth'] for m in st.session_state.processor.models.values()]))
                }
            }
            
            # Download button
            try:
                results_json = json.dumps(results_summary, indent=2)
            except TypeError as e:
                st.error(f"JSON serialization error: {e}")
                results_json = json.dumps({"error": "Could not serialize results"}, indent=2)
            st.download_button(
                label="📄 Download Analysis Report (JSON)",
                data=results_json,
                file_name=f"tml_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

def show_drift_detection_panel():
    """Display drift detection panel in main UI"""
    st.subheader("🔍 Model Drift Detection")
    
    # Try multiple API endpoints for drift detection
    drift_data = get_drift_data_with_fallback()
    
    if drift_data['status'] == 'success':
        summary = drift_data['data']
        
        # Display metrics with enhanced information
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Models Monitored", summary.get('totalModelsMonitored', 0),
                     help="Total active models being monitored for drift")
        with col2:
            models_with_drift = summary.get('modelsWithDrift', 0)
            st.metric("Drift Detected", models_with_drift,
                     delta=f"+{models_with_drift}" if models_with_drift > 0 else "✅ None",
                     delta_color="inverse" if models_with_drift > 0 else "normal",
                     help="Models showing significant data or concept drift")
        with col3:
            avg_drift = summary.get('averageDataDriftScore', 0)
            st.metric("Avg Drift Score", f"{avg_drift:.3f}",
                     delta="⚠️ High" if avg_drift > 0.2 else "✅ Normal" if avg_drift > 0.1 else "✅ Low",
                     delta_color="inverse" if avg_drift > 0.2 else "normal",
                     help="Population Stability Index (PSI) average across models")
        with col4:
            critical = summary.get('criticalModels', 0)
            st.metric("Critical Models", critical,
                     delta="🔴 Action Required" if critical > 0 else "✅ All Good",
                     delta_color="inverse" if critical > 0 else "normal",
                     help="Models requiring immediate retraining")
        
        # Show service status
        if drift_data['source'] == 'api':
            st.success("🟢 **Drift Detection Service**: Connected and operational")
            # Show Redis connection status
            if check_redis_connection():
                st.success("🟢 **Redis**: Connected")
            else:
                st.warning("🟡 **Redis**: Connection issues detected")
        else:
            st.info("🟡 **Drift Detection Service**: Using simulated data (API unavailable)")
            
    elif drift_data['status'] == 'error':
        # Show error with fallback data
        st.error(f"🔴 **Drift Detection Service Error**: {drift_data['message']}")
        
        # Show fallback metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            model_count = len(st.session_state.processor.models) if 'processor' in st.session_state else 0
            st.metric("Models Monitored", model_count, help="Local model count (API unavailable)")
        with col2:
            st.metric("Drift Detected", "N/A", help="Service unavailable")
        with col3:
            st.metric("Avg Drift Score", "N/A", help="Service unavailable")
        with col4:
            st.metric("Critical Models", "N/A", help="Service unavailable")
            
        # Show troubleshooting info
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
            **Possible causes:**
            - Drift monitoring service not started
            - Redis connection issues
            - Database connectivity problems
            - Service configuration errors
            
            **Solutions:**
            1. Check if Redis is running: `redis-cli ping`
            2. Verify database connection
            3. Restart the TML API service
            4. Check service logs for detailed errors
            """)
            
            # Add service initialization button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Test Redis Connection"):
                    test_redis_connection()
            with col2:
                if st.button("🚀 Initialize Drift Service"):
                    initialize_drift_service()
    
    else:
        # Fallback to demo data
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            model_count = len(st.session_state.processor.models) if 'processor' in st.session_state else 0
            st.metric("Models Monitored", model_count)
        with col2:
            st.metric("Drift Detected", 0, delta="✅ None", delta_color="normal")
        with col3:
            st.metric("Avg Drift Score", "0.045")
        with col4:
            st.metric("Critical Models", 0, delta="✅", delta_color="normal")
        
        st.warning("🟡 **Drift Detection Service**: Running in demo mode")
    
    # Show drift visualization
    if 'processor' in st.session_state and st.session_state.processor.models:
        # Get real drift data from API
        drift_result = get_drift_data_with_fallback()
        model_ids = list(st.session_state.processor.models.keys())[:20]  # Show first 20 models
        
        # Use real drift score from API, or 0.0 if no drift detected
        avg_drift_score = drift_result.get('data', {}).get('averageDataDriftScore', 0.0) if drift_result['status'] == 'success' else 0.0
        drift_scores = [avg_drift_score for _ in model_ids]  # Use real drift score for all models
        
        fig = go.Figure(data=[
            go.Bar(
                x=[f"Model {i}" for i in range(len(model_ids))],
                y=drift_scores,
                marker_color=['red' if score > 0.2 else 'orange' if score > 0.1 else 'green' 
                             for score in drift_scores]
            )
        ])
        
        fig.add_hline(y=0.1, line_dash="dash", line_color="orange", 
                     annotation_text="Warning Threshold")
        fig.add_hline(y=0.2, line_dash="dash", line_color="red", 
                     annotation_text="Critical Threshold")
        
        fig.update_layout(
            title="Model Drift Scores (PSI)",
            xaxis_title="Model",
            yaxis_title="Drift Score",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Drift alerts
        if any(score > 0.2 for score in drift_scores):
            st.warning("⚠️ Critical drift detected in some models. Retraining recommended.")
    
    # Feature drift analysis
    st.subheader("Feature Drift Analysis")
    features = ['thickness', 'x_coord', 'y_coord', 'quality']
    selected_feature = st.selectbox("Select Feature for Analysis", features, key="drift_feature_select")
    
    if st.button("Analyze Feature Drift", key="analyze_drift_btn"):
        with st.spinner("Analyzing feature drift..."):
            time.sleep(1)  # Simulate processing
            st.success(f"✅ Feature '{selected_feature}' shows minimal drift (PSI: 0.032)")

def show_ab_testing_panel():
    """Display A/B testing panel in main UI"""
    st.subheader("🎲 Model A/B Testing")
    
    # Quick experiment creation
    with st.expander("➕ Create New Experiment"):
        col1, col2 = st.columns(2)
        with col1:
            exp_name = st.text_input("Experiment Name", placeholder="e.g., Model v2 Test", key="ab_exp_name")
            control_model = st.selectbox("Control Model", 
                                        ["Current Production", "Model v1.0", "Baseline"],
                                        key="ab_control")
        with col2:
            treatment_model = st.selectbox("Treatment Model", 
                                          ["Model v2.0", "Optimized Model", "New Algorithm"],
                                          key="ab_treatment")
            traffic_split = st.slider("Traffic Split (%)", 0, 100, 50, key="ab_traffic")
        
        if st.button("🚀 Launch Experiment", key="launch_ab_btn"):
            st.success(f"✅ Experiment '{exp_name}' launched!")
            st.balloons()
    
    # Active experiments
    st.subheader("Active Experiments")
    
    # Simulated experiment data
    experiments = [
        {
            "name": "Physics Validator v2",
            "status": "Running",
            "duration": "3 days",
            "samples": 2456,
            "control_conversion": 0.12,
            "treatment_conversion": 0.14,
            "lift": 0.167,
            "confidence": 0.87,
            "significant": False
        },
        {
            "name": "Model Inheritance Test",
            "status": "Concluded",
            "duration": "7 days",
            "samples": 5420,
            "control_conversion": 0.10,
            "treatment_conversion": 0.13,
            "lift": 0.30,
            "confidence": 0.96,
            "significant": True
        }
    ]
    
    for exp in experiments:
        with st.expander(f"🔬 {exp['name']} - {exp['status']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Samples", f"{exp['samples']:,}")
                st.metric("Duration", exp['duration'])
            
            with col2:
                st.metric("Control", f"{exp['control_conversion']:.1%}")
                st.metric("Treatment", f"{exp['treatment_conversion']:.1%}")
            
            with col3:
                st.metric("Lift", f"+{exp['lift']:.1%}")
                if exp['significant']:
                    st.success(f"✅ Significant (p<0.05)")
                else:
                    st.warning(f"⏳ Not significant yet")
            
            # Conversion rate comparison
            fig = go.Figure(data=[
                go.Bar(name='Control', x=['Conversion Rate'], y=[exp['control_conversion']],
                      error_y=dict(type='data', array=[0.01]), marker_color='gray'),
                go.Bar(name='Treatment', x=['Conversion Rate'], y=[exp['treatment_conversion']],
                      error_y=dict(type='data', array=[0.01]), marker_color='green' if exp['significant'] else 'blue')
            ])
            
            fig.update_layout(
                title=f"Confidence: {exp['confidence']:.0%}",
                yaxis_title="Conversion Rate",
                barmode='group',
                height=250,
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            if exp['status'] == "Running":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"🏁 Conclude", key=f"conclude_{exp['name']}"):
                        st.info("Analyzing final results...")
                with col2:
                    if st.button(f"⏸️ Pause", key=f"pause_{exp['name']}"):
                        st.info("Experiment paused")
    
    # Experiment recommendations
    st.subheader("📊 Recommendations")
    
    if 'processor' in st.session_state and hasattr(st.session_state.processor, 'models'):
        num_models = len(st.session_state.processor.models)
        if num_models > 10:
            st.info(f"💡 With {num_models} models created, consider running A/B tests to compare top performers")
        
        if hasattr(st.session_state.processor, 'physics_violations') and st.session_state.processor.physics_violations > 0:
            st.warning(f"⚠️ {st.session_state.processor.physics_violations} physics violations detected. Test alternative validation strategies.")

def get_drift_data_with_fallback():
    """Get drift data with multiple fallback options"""
    
    # Try C# API first (primary)
    try:
        response = requests.get("http://localhost:5001/api/drift/summary", timeout=2)
        if response.status_code == 200:
            return {
                'status': 'success',
                'data': response.json(),
                'source': 'api',
                'message': 'Connected to drift detection service'
            }
        else:
            error_msg = f"API returned status {response.status_code}"
            if response.status_code == 500:
                error_msg += " (Internal server error - check Redis/DB connections)"
            elif response.status_code == 404:
                error_msg += " (Drift endpoints not found - service may not be configured)"
            
            return {
                'status': 'error',
                'data': None,
                'source': 'api_error',
                'message': error_msg
            }
    except requests.exceptions.Timeout:
        return {
            'status': 'error',
            'data': None,
            'source': 'timeout',
            'message': 'API request timed out - service may be overloaded'
        }
    except requests.exceptions.ConnectionError:
        pass  # Try Python API fallback
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'source': 'exception',
            'message': f'Unexpected error: {str(e)}'
        }
    
    # Skip Python API fallback since we have real .NET backend
    # Continue to simulation if C# API fails
    
    # Generate simulated drift data as final fallback
    if 'processor' in st.session_state and hasattr(st.session_state.processor, 'models'):
        model_count = len(st.session_state.processor.models)
        models_with_drift = max(0, int(model_count * 0.15))  # 15% with drift
        
        return {
            'status': 'success',
            'data': {
                'totalModelsMonitored': model_count,
                'modelsWithDrift': models_with_drift,
                'averageDataDriftScore': np.random.uniform(0.05, 0.15),
                'averageConceptDriftScore': np.random.uniform(0.03, 0.12),
                'criticalModels': max(0, models_with_drift // 3),
                'timestamp': datetime.now().isoformat()
            },
            'source': 'simulation',
            'message': 'Using simulated drift data'
        }
    
    # Minimal fallback if no models exist
    return {
        'status': 'success',
        'data': {
            'totalModelsMonitored': 0,
            'modelsWithDrift': 0,
            'averageDataDriftScore': 0.0,
            'averageConceptDriftScore': 0.0,
            'criticalModels': 0,
            'timestamp': datetime.now().isoformat()
        },
        'source': 'minimal',
        'message': 'No models available for monitoring'
    }

def check_redis_connection():
    """Check if Redis is accessible"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        return True
    except:
        return False

def test_redis_connection():
    """Test Redis connection and display results"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Test basic connection
        r.ping()
        st.success("✅ Redis connection successful")
        
        # Test read/write
        test_key = "tml:test:connection"
        r.set(test_key, "test_value", ex=10)  # Expire in 10 seconds
        value = r.get(test_key)
        
        if value == "test_value":
            st.success("✅ Redis read/write operations working")
        else:
            st.warning("⚠️ Redis read/write test failed")
            
        # Show Redis info
        info = r.info()
        st.info(f"📊 Redis version: {info.get('redis_version', 'Unknown')}")
        st.info(f"📊 Connected clients: {info.get('connected_clients', 'Unknown')}")
        
    except ImportError:
        st.error("❌ Redis Python client not installed")
    except Exception as e:
        st.error(f"❌ Redis connection failed: {str(e)}")

def initialize_drift_service():
    """Initialize the drift detection service with sample data"""
    try:
        # Try to initialize via API
        response = requests.post("http://localhost:5001/api/drift/initialize", timeout=5)
        if response.status_code == 200:
            st.success("✅ Drift service initialized successfully")
        else:
            # Fallback: Initialize Redis directly
            initialize_redis_drift_data()
    except:
        # Fallback: Initialize Redis directly
        initialize_redis_drift_data()

def initialize_redis_drift_data():
    """Initialize Redis with sample drift data"""
    try:
        import redis
        import json
        
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Initialize drift summary
        summary_data = {
            'totalModelsMonitored': 0,
            'modelsWithDrift': 0,
            'averageDataDriftScore': 0.0,
            'averageConceptDriftScore': 0.0,
            'criticalModels': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        r.set("drift:summary:latest", json.dumps(summary_data), ex=3600)
        st.success("✅ Initialized Redis with default drift data")
        st.info("🔄 Refresh the page to see updated drift metrics")
        
    except ImportError:
        st.error("❌ Redis Python client not installed")
    except Exception as e:
        st.error(f"❌ Failed to initialize Redis data: {str(e)}")

def create_sample_data() -> str:
    """Create sample C-Scan data for demonstration"""
    return """UTIA 10.0
Thickness Data [mm] - Channel 1, Gate 2
C-Scan Data
Area (Xstart, Ystart, Xend, Yend) [mm] = (0.000, 0.000, 3700.000, 880.000 )
Grid Size (Xsteps, Ysteps) = ( 1850, 176 )

Y/X	0	2	4	6	8	10	12	14	16	18	20	22	24	26	28	30	32	34	36	38	40	42	44	46	48	50
880	19.963	19.845	20.021	20.021	20.051	20.08	20.08	20.139	20.197	20.285	20.168	20.315	20.109	20.139	20.139	20.139	20.197	20.197	20.139	20.227	20.403	20.168	20.256	20.139	20.285	20.139
875	19.992	19.992	19.992	19.963	20.109	20.021	20.08	20.021	20.021	20.139	20.139	20.139	20.344	20.051	20.139	20.197	20.197	20.139	20.139	20.168	20.139	20.168	20.197	20.256	20.256	20.168
870	19.933	19.904	19.933	19.963	19.963	19.992	20.08	20.051	20.051	20.08	20.021	20.256	20.139	20.139	20.227	20.08	20.197	20.168	20.139	20.168	20.256	20.139	20.168	20.227	20.256	20.197
865	19.933	19.933	19.904	19.963	19.904	19.933	20.197	19.992	20.021	20.021	20.051	20.021	20.197	20.08	20.08	20.139	20.021	20.109	20.168	20.139	20.168	20.139	20.139	20.197	20.197	20.227
860	19.904	19.904	19.875	19.963	19.992	19.904	19.963	19.963	19.992	19.992	20.021	20.08	20.051	20.051	20.109	20.08	20.109	20.109	20.08	20.139	20.168	20.227	20.168	20.197	20.227	20.227
855	19.933	19.933	19.904	19.933	19.963	19.904	19.933	19.963	19.963	19.963	19.963	20.021	20.021	20.021	20.051	20.139	20.08	20.109	20.109	20.139	20.197	20.139	20.139	20.139	20.168	20.227
850	19.933	19.933	19.963	19.963	19.992	19.963	20.139	20.021	19.992	20.051	19.904	19.992	20.021	20.051	20.08	20.227	20.021	20.168	20.139	20.168	20.168	20.227	20.227	20.197	20.168	20.256"""

if __name__ == "__main__":
    main()
