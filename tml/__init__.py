"""
Transaction-based Machine Learning (TML) Platform

A sophisticated platform where each transaction spawns its own incrementally 
learning model, creating millions of specialized models that inherit knowledge 
while remaining independently tunable.
"""

__version__ = "0.1.0"
__author__ = "TML Team"

from tml.core.config import Config
from tml.core.model import TransactionModel

# Optional imports that require additional dependencies
try:
    from tml.core.registry import ModelRegistry
    _REGISTRY_AVAILABLE = True
except ImportError:
    ModelRegistry = None
    _REGISTRY_AVAILABLE = False

__all__ = [
    "Config",
    "TransactionModel",
]

if _REGISTRY_AVAILABLE:
    __all__.append("ModelRegistry")
