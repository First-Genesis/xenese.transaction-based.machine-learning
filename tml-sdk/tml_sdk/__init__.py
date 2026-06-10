"""
TML SDK - Transaction-based Machine Learning Platform
Official Python SDK for the TML Platform

Example usage:
    from tml_sdk import TMLClient
    
    client = TMLClient(api_url="http://localhost:8000", api_key="your-key")
    model = client.models.create("fraud_detection", model_type="river_classifier")
    
    for transaction in client.transactions.stream("live-transactions"):
        prediction = model.predict(transaction.features)
        model.learn(transaction.features, transaction.label)
"""

__version__ = "1.0.0"
__author__ = "TML Platform Team"
__email__ = "team@tml-platform.com"

# Core imports
from .client.tml_client import TMLClient
from .client.config import TMLConfig
from .client.exceptions import (
    TMLException,
    TMLConnectionError,
    TMLAuthenticationError,
    TMLValidationError,
    TMLModelError,
    TMLTransactionError
)

# Model types
from .models.base import BaseModel
from .models.river_model import RiverModel
from .models.sklearn_model import SklearnModel

# Transaction types
from .transactions.transaction import Transaction, create_transaction
from .transactions.stream import TransactionStream

# Spatial inheritance (placeholder imports)
try:
    from .spatial.spatial_manager import SpatialManager as SpatialInheritance
    from .spatial.spatial_manager import SpatialManager as SimilarityCalculator
except ImportError:
    SpatialInheritance = None
    SimilarityCalculator = None

# Federated learning (placeholder imports)
try:
    from .federated.federated_manager import FederatedManager as FederatedCoordinator
    from .federated.federated_manager import FederatedManager as FederatedNode
except ImportError:
    FederatedCoordinator = None
    FederatedNode = None

# Monitoring (placeholder imports)
try:
    from .monitoring.monitoring_manager import MonitoringManager as DriftDetector
    from .monitoring.monitoring_manager import MonitoringManager as MetricsCollector
except ImportError:
    DriftDetector = None
    MetricsCollector = None

# Utilities
from .utils.logger import get_logger
from .utils.config_loader import load_config

# Public API
__all__ = [
    # Core
    "TMLClient",
    "TMLConfig",
    
    # Exceptions
    "TMLException",
    "TMLConnectionError", 
    "TMLAuthenticationError",
    "TMLValidationError",
    "TMLModelError",
    "TMLTransactionError",
    
    # Models
    "BaseModel",
    "RiverModel",
    "SklearnModel",
    
    # Transactions
    "Transaction",
    "create_transaction",
    "TransactionStream",
    
    # Spatial
    "SpatialInheritance",
    "SimilarityCalculator",
    
    # Federated
    "FederatedCoordinator",
    "FederatedNode",
    
    # Monitoring
    "DriftDetector",
    "MetricsCollector",
    
    # Utilities
    "get_logger",
    "load_config",
]

# SDK metadata
SDK_INFO = {
    "name": "tml-sdk",
    "version": __version__,
    "description": "Official SDK for Transaction-based Machine Learning Platform",
    "author": __author__,
    "email": __email__,
    "url": "https://github.com/tml-platform/tml-sdk",
    "license": "MIT",
    "python_requires": ">=3.8",
}
