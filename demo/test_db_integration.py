#!/usr/bin/env python3
"""
Test script to verify database integration works independently
"""

import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_integration():
    """Test the database integration functionality"""
    logger.info("=== Testing Database Integration ===")
    
    try:
        # Import database integration
        from database_integration import db_integration
        logger.info("✅ Database integration imported successfully")
        
        # Test connection
        initial_count = db_integration.get_model_count()
        logger.info(f"Initial model count: {initial_count}")
        
        # Test saving a model
        test_model = {
            "model_id": "test_standalone_001",
            "parent_model_id": None,
            "inheritance_depth": 0,
            "x_coord": 100.0,
            "y_coord": 200.0,
            "accuracy": 0.85,
            "total_updates": 1,
            "total_predictions": 0,
            "drift_score": 0.0,
            "model_type": "test_standalone"
        }
        
        logger.info("Attempting to save test model...")
        result = db_integration.save_model_to_database(test_model)
        logger.info(f"Save result: {result}")
        
        # Check if count increased
        final_count = db_integration.get_model_count()
        logger.info(f"Final model count: {final_count}")
        
        if final_count > initial_count:
            logger.info("✅ Database integration is working correctly!")
            return True
        else:
            logger.error("❌ Model count did not increase - database save failed")
            return False
            
    except ImportError as e:
        logger.error(f"❌ Failed to import database integration: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_tml_processor():
    """Test the TML processor database integration"""
    logger.info("=== Testing TML Processor Database Integration ===")
    
    try:
        # Add parent directory to path for imports
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Import database integration
        from database_integration import db_integration
        DATABASE_INTEGRATION_AVAILABLE = True
        logger.info("✅ Database integration available")
        
        # Simulate the TML processor class initialization
        class TestTMLProcessor:
            def __init__(self):
                self.models = {}
                self.database_integration_available = DATABASE_INTEGRATION_AVAILABLE
                self.models_saved_to_db = 0
                if self.database_integration_available:
                    try:
                        self.db_integration = db_integration
                        logger.info("Database integration initialized in TestTMLProcessor")
                    except Exception as e:
                        logger.error(f"Failed to initialize database integration: {e}")
                        self.database_integration_available = False
            
            def test_process_transaction(self):
                """Simulate processing a transaction"""
                model_id = "test_processor_001"
                
                # Create model (simulate the actual code)
                model = {
                    'model_id': model_id,
                    'x_coord': 150.0,
                    'y_coord': 250.0,
                    'thickness': 20.5,
                    'parent_model': None,
                    'inheritance_depth': 0,
                    'physics_valid': True
                }
                
                self.models[model_id] = model
                logger.info(f"Creating model {model_id} - DB Integration Available: {self.database_integration_available}")
                
                # Save model to database for drift detection
                if self.database_integration_available:
                    try:
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
                            "model_type": "test_processor"
                        }
                        success = self.db_integration.save_model_to_database(model_data)
                        if success:
                            self.models_saved_to_db += 1
                            logger.info(f"✅ Successfully saved model {model_id} to database (Total: {self.models_saved_to_db})")
                            return True
                        else:
                            logger.error(f"❌ Failed to save model {model_id} to database")
                            return False
                    except Exception as e:
                        logger.error(f"❌ Exception saving model {model_id} to database: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return False
                else:
                    logger.warning(f"❌ Database integration not available - model {model_id} not saved to database")
                    return False
        
        # Test the processor
        processor = TestTMLProcessor()
        result = processor.test_process_transaction()
        
        if result:
            logger.info("✅ TML Processor database integration is working!")
        else:
            logger.error("❌ TML Processor database integration failed!")
            
        return result
        
    except Exception as e:
        logger.error(f"❌ TML Processor test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting database integration tests...")
    
    # Test 1: Direct database integration
    test1_result = test_database_integration()
    
    # Test 2: TML processor simulation
    test2_result = test_tml_processor()
    
    # Summary
    logger.info("=== Test Summary ===")
    logger.info(f"Direct DB Integration: {'✅ PASS' if test1_result else '❌ FAIL'}")
    logger.info(f"TML Processor Integration: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        logger.info("🎉 All tests passed! Database integration should work in Streamlit.")
    else:
        logger.error("💥 Tests failed! There's an issue with the database integration.")
