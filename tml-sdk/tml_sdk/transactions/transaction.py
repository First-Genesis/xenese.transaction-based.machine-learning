"""
Transaction Data Structure
Represents a single transaction in the TML system
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
import json
import uuid
from dataclasses import dataclass, field, asdict

from ..client.exceptions import TMLValidationError


@dataclass
class Transaction:
    """
    Transaction data structure for TML Platform

    Represents a single transaction with features, labels, and metadata
    for real-time machine learning processing.

    Example:
        transaction = Transaction(
            transaction_id="tx_12345",
            features={
                "amount": 150.00,
                "merchant_category": "grocery",
                "hour": 14,
                "location": "US-CA"
            },
            label=0,  # 0 = legitimate, 1 = fraud
            metadata={
                "user_id": "user_789",
                "timestamp": "2024-01-15T14:30:00Z"
            }
        )
    """

    # Core transaction data
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    features: Dict[str, Any] = field(default_factory=dict)
    label: Optional[Union[int, float, str, bool]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None

    # Processing information
    model_predictions: Dict[str, Any] = field(default_factory=dict)
    processing_status: str = "pending"  # pending, processed, failed
    error_message: Optional[str] = None

    def __post_init__(self):
        """Validate transaction after initialization"""
        self.validate()

    def validate(self) -> None:
        """
        Validate transaction data

        Raises:
            TMLValidationError: If validation fails
        """
        if not self.transaction_id:
            raise TMLValidationError("transaction_id is required")

        if not isinstance(self.features, dict):
            raise TMLValidationError("features must be a dictionary")

        if not self.features:
            raise TMLValidationError("features cannot be empty")

        # Validate feature values
        for key, value in self.features.items():
            if not isinstance(key, str):
                raise TMLValidationError("feature keys must be strings")

            if value is None:
                raise TMLValidationError(f"feature '{key}' cannot be None")

        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise TMLValidationError("timestamp must be a datetime object")

        # Validate processing status
        valid_statuses = ["pending", "processed", "failed"]
        if self.processing_status not in valid_statuses:
            raise TMLValidationError(
                f"processing_status must be one of {valid_statuses}"
            )

    def add_prediction(
        self, model_id: str, prediction: Any, confidence: float = None
    ) -> None:
        """
        Add model prediction to transaction

        Args:
            model_id: Model identifier
            prediction: Model prediction
            confidence: Prediction confidence (optional)
        """
        prediction_data = {
            "prediction": prediction,
            "timestamp": datetime.now().isoformat(),
        }

        if confidence is not None:
            prediction_data["confidence"] = confidence

        self.model_predictions[model_id] = prediction_data

    def get_prediction(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get prediction from specific model

        Args:
            model_id: Model identifier

        Returns:
            Optional[Dict]: Prediction data or None
        """
        return self.model_predictions.get(model_id)

    def set_label(self, label: Union[int, float, str, bool]) -> None:
        """
        Set transaction label

        Args:
            label: True label for the transaction
        """
        self.label = label

    def set_status(self, status: str, error_message: str = None) -> None:
        """
        Set processing status

        Args:
            status: Processing status
            error_message: Error message if status is 'failed'
        """
        valid_statuses = ["pending", "processed", "failed"]
        if status not in valid_statuses:
            raise TMLValidationError(f"status must be one of {valid_statuses}")

        self.processing_status = status
        self.error_message = error_message

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata field

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_feature(self, feature_name: str, default: Any = None) -> Any:
        """
        Get feature value

        Args:
            feature_name: Name of the feature
            default: Default value if feature not found

        Returns:
            Any: Feature value
        """
        return self.features.get(feature_name, default)

    def has_feature(self, feature_name: str) -> bool:
        """
        Check if transaction has feature

        Args:
            feature_name: Name of the feature

        Returns:
            bool: True if feature exists
        """
        return feature_name in self.features

    def get_feature_names(self) -> list:
        """
        Get list of feature names

        Returns:
            list: List of feature names
        """
        return list(self.features.keys())

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert transaction to dictionary

        Returns:
            Dict: Transaction as dictionary
        """
        data = asdict(self)

        # Convert datetime to ISO string
        data["timestamp"] = self.timestamp.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """
        Create transaction from dictionary

        Args:
            data: Transaction data dictionary

        Returns:
            Transaction: Transaction instance
        """
        # Convert timestamp string to datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        return cls(**data)

    def to_json(self) -> str:
        """
        Convert transaction to JSON string

        Returns:
            str: JSON representation
        """
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "Transaction":
        """
        Create transaction from JSON string

        Args:
            json_str: JSON string

        Returns:
            Transaction: Transaction instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def copy(self) -> "Transaction":
        """
        Create a copy of the transaction

        Returns:
            Transaction: Copy of the transaction
        """
        return Transaction.from_dict(self.to_dict())

    def is_labeled(self) -> bool:
        """
        Check if transaction has a label

        Returns:
            bool: True if transaction has a label
        """
        return self.label is not None

    def is_processed(self) -> bool:
        """
        Check if transaction has been processed

        Returns:
            bool: True if transaction is processed
        """
        return self.processing_status == "processed"

    def has_predictions(self) -> bool:
        """
        Check if transaction has any predictions

        Returns:
            bool: True if transaction has predictions
        """
        return len(self.model_predictions) > 0

    def get_age_seconds(self) -> float:
        """
        Get transaction age in seconds

        Returns:
            float: Age in seconds
        """
        return (datetime.now() - self.timestamp).total_seconds()

    def __str__(self) -> str:
        """String representation"""
        return f"Transaction(id={self.transaction_id}, features={len(self.features)}, label={self.label})"

    def __repr__(self) -> str:
        """Detailed string representation"""
        return (
            f"Transaction(transaction_id='{self.transaction_id}', "
            f"features={self.features}, label={self.label}, "
            f"timestamp={self.timestamp.isoformat()})"
        )


# Utility functions for transaction processing
def create_transaction(
    features: Dict[str, Any],
    label: Any = None,
    transaction_id: str = None,
    source: str = None,
    **metadata,
) -> Transaction:
    """
    Convenience function to create a transaction

    Args:
        features: Transaction features
        label: Transaction label (optional)
        transaction_id: Transaction ID (optional, will generate if not provided)
        source: Data source (optional)
        **metadata: Additional metadata

    Returns:
        Transaction: Created transaction
    """
    return Transaction(
        transaction_id=transaction_id or str(uuid.uuid4()),
        features=features,
        label=label,
        source=source,
        metadata=metadata,
    )


def batch_create_transactions(
    features_list: list, labels_list: list = None, source: str = None, **common_metadata
) -> list:
    """
    Create multiple transactions from lists

    Args:
        features_list: List of feature dictionaries
        labels_list: List of labels (optional)
        source: Data source (optional)
        **common_metadata: Metadata applied to all transactions

    Returns:
        list: List of Transaction objects
    """
    transactions = []

    for i, features in enumerate(features_list):
        label = labels_list[i] if labels_list else None

        transaction = Transaction(
            features=features,
            label=label,
            source=source,
            metadata=common_metadata.copy(),
        )

        transactions.append(transaction)

    return transactions
