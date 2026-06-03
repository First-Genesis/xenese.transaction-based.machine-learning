"""
Physics Models Integration for TML Platform

This module provides physics-informed machine learning capabilities
for engineering applications with transaction-based model inheritance.
"""

from .physics_engine import PhysicsEngine, PhysicsConstraint
from .engineering_equations import EngineeringEquations
from .physics_informed_ml import PhysicsInformedModel
from .constraint_validator import ConstraintValidator

__all__ = [
    'PhysicsEngine',
    'PhysicsConstraint', 
    'EngineeringEquations',
    'PhysicsInformedModel',
    'ConstraintValidator'
]
