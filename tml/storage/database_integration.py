"""Database integration for TML models to sync with PostgreSQL."""

import json
import uuid
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import Optional

import psycopg2
from loguru import logger


class TMLDatabaseIntegration:
    """Handles saving TML models to PostgreSQL database for drift detection."""

    def __init__(
        self,
        connection_string: str = "host=localhost port=5432 dbname=tml user=tml password=tml123",
    ):
        self.connection_string = connection_string

    def save_model_to_database(self, model_data: Dict[str, Any]) -> bool:
        """Save a TML model to the PostgreSQL database."""
        try:
            with psycopg2.connect(self.connection_string) as conn:
                with conn.cursor() as cursor:
                    # Generate UUIDs for the model and transaction
                    model_id = str(uuid.uuid4())
                    transaction_id = str(uuid.uuid4())

                    # Prepare model data for database
                    now = datetime.now(timezone.utc)

                    # Create minimal required JSON structures
                    parameters = {
                        "weights": (
                            model_data.get("weights", []).tolist()
                            if hasattr(model_data.get("weights", []), "tolist")
                            else model_data.get("weights", [])
                        ),
                        "bias": model_data.get("bias", 0.0),
                        "model_type": model_data.get(
                            "model_type", "logistic_regression"
                        ),
                    }

                    location = {
                        "x": model_data.get("x_coord", 0.0),
                        "y": model_data.get("y_coord", 0.0),
                    }

                    metrics = {
                        "accuracy": model_data.get("accuracy", 0.0),
                        "totalUpdates": model_data.get("total_updates", 0),
                        "totalPredictions": model_data.get("total_predictions", 0),
                        "driftScore": model_data.get("drift_score", 0.0),
                    }

                    physics_validation = {
                        "isValid": True,
                        "violations": 0,
                        "validatedAt": now.isoformat(),
                    }

                    # Insert into Models table
                    insert_query = """
                    INSERT INTO "Models" (
                        "Id", "TransactionId", "ParentModelId", "InheritanceDepth", 
                        "Status", "CreatedAt", "UpdatedAt", "Version",
                        "Parameters", "Location", "Metrics", "PhysicsValidation"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """

                    cursor.execute(
                        insert_query,
                        (
                            model_id,
                            transaction_id,
                            model_data.get("parent_model_id"),  # Can be None
                            model_data.get("inheritance_depth", 0),
                            0,  # Status: 0 = Active
                            now,
                            now,
                            1,  # Version
                            json.dumps(parameters),
                            json.dumps(location),
                            json.dumps(metrics),
                            json.dumps(physics_validation),
                        ),
                    )

                    conn.commit()
                    logger.info(f"Successfully saved model {model_id} to database")
                    return True

        except Exception as e:
            logger.error(f"Failed to save model to database: {e}")
            return False

    def save_transaction_model(self, transaction_model) -> bool:
        """Save a TransactionModel instance to the database."""
        try:
            # Extract data from TransactionModel object
            model_data = {
                "model_id": transaction_model.model_id,
                "parent_model_id": transaction_model.parent_model_id,
                "inheritance_depth": transaction_model.inheritance_depth,
                "weights": (
                    getattr(transaction_model.model, "weights", [])
                    if hasattr(transaction_model, "model")
                    else []
                ),
                "bias": (
                    getattr(transaction_model.model, "bias", 0.0)
                    if hasattr(transaction_model, "model")
                    else 0.0
                ),
                "accuracy": transaction_model.metrics.accuracy,
                "total_updates": transaction_model.metrics.total_updates,
                "total_predictions": transaction_model.metrics.total_predictions,
                "drift_score": transaction_model.metrics.drift_score,
                "x_coord": (
                    getattr(transaction_model.context, "x_coord", 0.0)
                    if hasattr(transaction_model, "context")
                    else 0.0
                ),
                "y_coord": (
                    getattr(transaction_model.context, "y_coord", 0.0)
                    if hasattr(transaction_model, "context")
                    else 0.0
                ),
                "model_type": "transaction_model",
            }

            return self.save_model_to_database(model_data)

        except Exception as e:
            logger.error(f"Failed to save TransactionModel to database: {e}")
            return False

    def get_model_count(self) -> int:
        """Get the total number of models in the database."""
        try:
            with psycopg2.connect(self.connection_string) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) FROM "Models" WHERE "Status" = 0')
                    return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get model count: {e}")
            return 0


# Global instance for easy access
db_integration = TMLDatabaseIntegration()
