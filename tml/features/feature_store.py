"""Feature store implementation using Feast."""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import pyarrow as pa
from feast import Entity, FeatureStore, FeatureView, Field, FileSource, ValueType
from feast.types import Bool, Float32, Float64, Int32, Int64, String
from loguru import logger

from tml.core.config import config


@dataclass
class FeatureDefinition:
    """Definition of a feature for the feature store."""

    name: str
    value_type: ValueType
    description: str = ""
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class TMLFeatureStore:
    """TML-specific feature store implementation."""

    def __init__(self, repo_path: str = "./feature_repo"):
        self.repo_path = repo_path
        self.store: Optional[FeatureStore] = None
        self._initialize_store()

    def _initialize_store(self):
        """Initialize the Feast feature store."""
        try:
            # Try to load existing store
            self.store = FeatureStore(repo_path=self.repo_path)
            logger.info(f"Loaded existing feature store from {self.repo_path}")
        except Exception as e:
            logger.warning(f"Could not load existing feature store: {e}")
            logger.info("Creating new feature store...")
            self._create_feature_store()

    def _create_feature_store(self):
        """Create a new feature store with TML-specific entities and features."""
        try:
            # This would typically be done via feast CLI, but we'll document the process
            logger.info("Feature store creation requires manual setup via Feast CLI")
            logger.info(
                "Run: feast init feature_repo && cd feature_repo && feast apply"
            )

            # For now, create a minimal store
            self.store = FeatureStore(repo_path=self.repo_path)

        except Exception as e:
            logger.error(f"Failed to create feature store: {e}")
            self.store = None

    def define_user_features(self) -> List[FeatureDefinition]:
        """Define user-related features."""
        return [
            FeatureDefinition("user_age", Int32, "User age in years"),
            FeatureDefinition("user_country", String, "User country code"),
            FeatureDefinition("user_signup_days", Int32, "Days since user signup"),
            FeatureDefinition(
                "user_total_purchases", Int32, "Total number of purchases"
            ),
            FeatureDefinition("user_avg_order_value", Float32, "Average order value"),
            FeatureDefinition(
                "user_last_purchase_days", Int32, "Days since last purchase"
            ),
            FeatureDefinition(
                "user_preferred_category", String, "Most purchased category"
            ),
            FeatureDefinition(
                "user_is_premium", Bool, "Whether user has premium status"
            ),
        ]

    def define_session_features(self) -> List[FeatureDefinition]:
        """Define session-related features."""
        return [
            FeatureDefinition(
                "session_duration_minutes", Float32, "Session duration in minutes"
            ),
            FeatureDefinition(
                "session_page_views", Int32, "Number of page views in session"
            ),
            FeatureDefinition(
                "session_device_type", String, "Device type (mobile/desktop/tablet)"
            ),
            FeatureDefinition("session_browser", String, "Browser type"),
            FeatureDefinition(
                "session_referrer_type", String, "Referrer type (organic/paid/direct)"
            ),
            FeatureDefinition("session_time_of_day", Int32, "Hour of day (0-23)"),
            FeatureDefinition("session_day_of_week", Int32, "Day of week (0-6)"),
            FeatureDefinition(
                "session_is_weekend", Bool, "Whether session is on weekend"
            ),
        ]

    def define_transaction_features(self) -> List[FeatureDefinition]:
        """Define transaction-related features."""
        return [
            FeatureDefinition("transaction_amount", Float32, "Transaction amount"),
            FeatureDefinition("transaction_category", String, "Product category"),
            FeatureDefinition(
                "transaction_payment_method", String, "Payment method used"
            ),
            FeatureDefinition(
                "transaction_discount_applied", Bool, "Whether discount was applied"
            ),
            FeatureDefinition(
                "transaction_is_mobile", Bool, "Whether transaction was on mobile"
            ),
            FeatureDefinition("transaction_hour", Int32, "Hour of transaction"),
            FeatureDefinition(
                "transaction_items_count", Int32, "Number of items in transaction"
            ),
        ]

    def define_contextual_features(self) -> List[FeatureDefinition]:
        """Define contextual features (time, location, etc.)."""
        return [
            FeatureDefinition("context_hour_of_day", Int32, "Current hour (0-23)"),
            FeatureDefinition(
                "context_day_of_week", Int32, "Current day of week (0-6)"
            ),
            FeatureDefinition(
                "context_is_weekend", Bool, "Whether current time is weekend"
            ),
            FeatureDefinition(
                "context_is_holiday", Bool, "Whether current date is holiday"
            ),
            FeatureDefinition("context_season", String, "Current season"),
            FeatureDefinition("context_weather_temp", Float32, "Current temperature"),
            FeatureDefinition("context_weather_condition", String, "Weather condition"),
        ]

    def get_user_features(
        self, user_id: str, feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get features for a specific user."""
        if not self.store:
            return self._get_mock_user_features(user_id, feature_names)

        try:
            # In a real implementation, this would query the feature store
            entity_df = pd.DataFrame(
                {"user_id": [user_id], "event_timestamp": [datetime.now()]}
            )

            # Get features from store
            features = self.store.get_historical_features(
                entity_df=entity_df,
                features=feature_names
                or [
                    "user_features:user_age",
                    "user_features:user_country",
                    "user_features:user_total_purchases",
                    "user_features:user_avg_order_value",
                ],
            ).to_df()

            if not features.empty:
                return features.iloc[0].to_dict()
            else:
                return self._get_mock_user_features(user_id, feature_names)

        except Exception as e:
            logger.error(f"Error getting user features: {e}")
            return self._get_mock_user_features(user_id, feature_names)

    def get_session_features(
        self, session_id: str, feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get features for a specific session."""
        if not self.store:
            return self._get_mock_session_features(session_id, feature_names)

        try:
            # Similar implementation as user features
            return self._get_mock_session_features(session_id, feature_names)
        except Exception as e:
            logger.error(f"Error getting session features: {e}")
            return self._get_mock_session_features(session_id, feature_names)

    def get_contextual_features(
        self, timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get contextual features for a given timestamp."""
        if timestamp is None:
            timestamp = time.time()

        dt = datetime.fromtimestamp(timestamp)

        return {
            "context_hour_of_day": dt.hour,
            "context_day_of_week": dt.weekday(),
            "context_is_weekend": dt.weekday() >= 5,
            "context_is_holiday": self._is_holiday(dt),
            "context_season": self._get_season(dt),
            # Weather features would require external API integration
            "context_weather_temp": 20.0,  # Mock value
            "context_weather_condition": "clear",  # Mock value
        }

    def get_enriched_features(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        transaction_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get enriched features combining multiple sources."""
        features = {}

        # Add contextual features
        features.update(self.get_contextual_features(timestamp))

        # Add user features if user_id provided
        if user_id:
            user_features = self.get_user_features(user_id)
            features.update({f"user_{k}": v for k, v in user_features.items()})

        # Add session features if session_id provided
        if session_id:
            session_features = self.get_session_features(session_id)
            features.update({f"session_{k}": v for k, v in session_features.items()})

        # Add transaction features if transaction_data provided
        if transaction_data:
            transaction_features = self._extract_transaction_features(transaction_data)
            features.update(
                {f"transaction_{k}": v for k, v in transaction_features.items()}
            )

        return features

    def store_features(
        self,
        entity_type: str,
        entity_id: str,
        features: Dict[str, Any],
        timestamp: Optional[float] = None,
    ):
        """Store features for an entity."""
        if not self.store:
            logger.warning("Feature store not available, features not stored")
            return

        try:
            # Convert to DataFrame format expected by Feast
            if timestamp is None:
                timestamp = time.time()

            df = pd.DataFrame(
                [
                    {
                        f"{entity_type}_id": entity_id,
                        "event_timestamp": pd.to_datetime(timestamp, unit="s"),
                        **features,
                    }
                ]
            )

            # In a real implementation, you would push to the feature store
            logger.debug(
                f"Would store features for {entity_type} {entity_id}: {features}"
            )

        except Exception as e:
            logger.error(f"Error storing features: {e}")

    def _get_mock_user_features(
        self, user_id: str, feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate mock user features for testing."""
        import hashlib

        # Use user_id hash to generate consistent mock data
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)

        mock_features = {
            "user_age": 18 + (hash_val % 50),
            "user_country": ["US", "UK", "CA", "DE", "FR"][hash_val % 5],
            "user_signup_days": hash_val % 1000,
            "user_total_purchases": hash_val % 100,
            "user_avg_order_value": 50.0 + (hash_val % 200),
            "user_last_purchase_days": hash_val % 30,
            "user_preferred_category": ["electronics", "clothing", "books", "home"][
                hash_val % 4
            ],
            "user_is_premium": (hash_val % 10) < 2,  # 20% premium users
        }

        if feature_names:
            return {k: v for k, v in mock_features.items() if k in feature_names}

        return mock_features

    def _get_mock_session_features(
        self, session_id: str, feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate mock session features for testing."""
        import hashlib

        hash_val = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)

        mock_features = {
            "session_duration_minutes": 1 + (hash_val % 120),  # 1-120 minutes
            "session_page_views": 1 + (hash_val % 50),
            "session_device_type": ["mobile", "desktop", "tablet"][hash_val % 3],
            "session_browser": ["chrome", "firefox", "safari", "edge"][hash_val % 4],
            "session_referrer_type": ["organic", "paid", "direct", "social"][
                hash_val % 4
            ],
            "session_time_of_day": hash_val % 24,
            "session_day_of_week": hash_val % 7,
            "session_is_weekend": (hash_val % 7) >= 5,
        }

        if feature_names:
            return {k: v for k, v in mock_features.items() if k in feature_names}

        return mock_features

    def _extract_transaction_features(
        self, transaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features from transaction data."""
        features = {}

        # Direct mappings
        if "amount" in transaction_data:
            features["amount"] = float(transaction_data["amount"])

        if "category" in transaction_data:
            features["category"] = str(transaction_data["category"])

        if "payment_method" in transaction_data:
            features["payment_method"] = str(transaction_data["payment_method"])

        # Derived features
        if "items" in transaction_data:
            features["items_count"] = len(transaction_data["items"])

        if "discount" in transaction_data:
            features["discount_applied"] = bool(transaction_data["discount"])

        if "device_type" in transaction_data:
            features["is_mobile"] = transaction_data["device_type"] == "mobile"

        # Time-based features
        if "timestamp" in transaction_data:
            dt = datetime.fromtimestamp(transaction_data["timestamp"])
            features["hour"] = dt.hour

        return features

    def _is_holiday(self, dt: datetime) -> bool:
        """Check if a date is a holiday (simplified implementation)."""
        # This is a simplified implementation
        # In practice, you'd use a proper holiday library
        major_holidays = [
            (1, 1),  # New Year's Day
            (7, 4),  # Independence Day (US)
            (12, 25),  # Christmas
        ]

        return (dt.month, dt.day) in major_holidays

    def _get_season(self, dt: datetime) -> str:
        """Get season for a given date."""
        month = dt.month

        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get statistics about feature usage and performance."""
        return {
            "total_features_defined": len(
                self.define_user_features()
                + self.define_session_features()
                + self.define_transaction_features()
                + self.define_contextual_features()
            ),
            "feature_store_status": "mock" if not self.store else "active",
            "last_update": time.time(),
        }


# Global feature store instance
feature_store = TMLFeatureStore()
