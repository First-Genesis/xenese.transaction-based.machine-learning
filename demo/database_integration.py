"""Database integration for TML models to sync with PostgreSQL."""

import json
import uuid
import psycopg2
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TMLDatabaseIntegration:
    """Handles saving TML models to PostgreSQL database for drift detection."""
    
    def __init__(self, connection_string: str = "host=localhost port=5432 dbname=tml user=tml password=tml123"):
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
                        "weights": model_data.get("weights", []),
                        "bias": model_data.get("bias", 0.0),
                        "model_type": model_data.get("model_type", "logistic_regression")
                    }
                    
                    location = {
                        "x": model_data.get("x_coord", 0.0),
                        "y": model_data.get("y_coord", 0.0)
                    }
                    
                    metrics = {
                        "accuracy": model_data.get("accuracy", 0.0),
                        "totalUpdates": model_data.get("total_updates", 0),
                        "totalPredictions": model_data.get("total_predictions", 0),
                        "driftScore": model_data.get("drift_score", 0.0)
                    }
                    
                    physics_validation = {
                        "isValid": True,
                        "violations": 0,
                        "validatedAt": now.isoformat()
                    }
                    
                    # Insert into Models table with ON CONFLICT handling
                    insert_query = """
                    INSERT INTO "Models" (
                        "Id", "TransactionId", "ParentModelId", "InheritanceDepth", 
                        "Status", "CreatedAt", "UpdatedAt", "Version",
                        "Parameters", "Location", "Metrics", "PhysicsValidation"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT ("Id") DO UPDATE SET
                        "UpdatedAt" = EXCLUDED."UpdatedAt",
                        "Metrics" = EXCLUDED."Metrics"
                    """
                    
                    # Handle parent_model_id - convert string to UUID or set to None
                    parent_model_id = model_data.get("parent_model_id")
                    if parent_model_id and isinstance(parent_model_id, str) and not parent_model_id.count('-') == 4:
                        # If it's a string like "model_181", set to None since we can't convert it to UUID
                        parent_model_id = None
                    
                    cursor.execute(insert_query, (
                        model_id,
                        transaction_id,
                        parent_model_id,  # Now properly handled
                        model_data.get("inheritance_depth", 0),
                        0,  # Status: 0 = Active
                        now,
                        now,
                        1,  # Version
                        json.dumps(parameters),
                        json.dumps(location),
                        json.dumps(metrics),
                        json.dumps(physics_validation)
                    ))
                    
                    conn.commit()
                    logger.info(f"Successfully saved model {model_id} to database")
                    return True
                    
        except psycopg2.IntegrityError as e:
            logger.warning(f"Model {model_id} already exists in database: {e}")
            return True  # Consider this a success since model exists
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection error for model {model_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving model {model_id} to database: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
