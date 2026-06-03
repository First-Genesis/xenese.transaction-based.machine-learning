#!/usr/bin/env python3
"""
Quick Test Runner for Enhanced TML Platform v2.0

Runs end-to-end tests with real data to validate the enhanced architecture.
This script can be run immediately to test the platform functionality.
"""

import asyncio
import sys
import os
import time
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import test components
from tests.data_generators import create_test_datasets
from tml.core.enhanced_platform import EnhancedTMLPlatform, EnhancedTransactionData, create_enhanced_tml_platform
from tml.physics.physics_engine import create_engineering_physics_engine


class QuickTester:
    """Quick testing framework for immediate validation"""
    
    def __init__(self):
        self.platform = None
        
    async def setup_test_platform(self):
        """Set up a test platform with minimal configuration"""
        print("🔧 Setting up Enhanced TML Platform for testing...")
        
        config = {
            "kafka": {
                "bootstrap_servers": ["localhost:9092"],
                "group_id": "tml_quick_test"
            },
            "physics": {
                "enable_validation": True,
                "constraint_tolerance": 1e-3  # Relaxed for testing
            },
            "learning": {
                "default_algorithm": "physics_informed_nn",
                "ewc_importance": 100.0  # Reduced for faster testing
            }
        }
        
        self.platform = create_enhanced_tml_platform(config)
        await self.platform.start()
        print("✅ Platform started successfully!")
        
    async def test_physics_engine(self):
        """Test physics engine functionality"""
        print("\n⚡ Testing Physics Engine...")
        
        physics_engine = create_engineering_physics_engine()
        
        # Test energy conservation
        test_data = {
            "energy_input": 1000.0,
            "energy_output": 950.0,
            "energy_stored": 50.0
        }
        
        validation = physics_engine.validate_transaction(test_data)
        print(f"  Energy conservation test: {'✅ PASS' if validation['valid'] else '❌ FAIL'}")
        
        # Test with violation
        violation_data = {
            "energy_input": 1000.0,
            "energy_output": 1200.0,  # Violation!
            "energy_stored": 0.0
        }
        
        violation_validation = physics_engine.validate_transaction(violation_data)
        print(f"  Physics violation detection: {'✅ PASS' if not violation_validation['valid'] else '❌ FAIL'}")
        
        return validation['valid'] and not violation_validation['valid']
        
    async def test_basic_transaction_processing(self):
        """Test basic transaction processing with inheritance"""
        print("\n🔄 Testing Transaction Processing...")
        
        # Create test transactions
        transactions = []
        
        for i in range(10):
            transaction = EnhancedTransactionData(
                transaction_id=f"test_txn_{i+1:03d}",
                features={
                    "temperature": 300.0 + i * 5,
                    "pressure": 101325.0 + i * 1000,
                    "flow_rate": 10.0 + i * 0.5
                },
                target=350.0 + i * 2,
                physics_parameters={
                    "energy_input": 1000.0 + i * 50,
                    "energy_output": 950.0 + i * 45,
                    "energy_stored": 50.0 + i * 5
                },
                context={
                    "equipment": "test_heat_exchanger",
                    "data_type": "streaming"
                }
            )
            transactions.append(transaction)
            
        # Process transactions
        successful_models = 0
        processing_times = []
        
        for i, transaction in enumerate(transactions):
            try:
                start_time = time.time()
                result = await self.platform.process_transaction(transaction)
                processing_time = time.time() - start_time
                processing_times.append(processing_time)
                
                if result.status == "success":
                    successful_models += 1
                    print(f"  Transaction {i+1}: ✅ Model {result.model_id} created "
                          f"(depth: {result.inheritance_depth}, time: {processing_time*1000:.1f}ms)")
                else:
                    print(f"  Transaction {i+1}: ❌ Failed - {result.status}")
                    
            except Exception as e:
                print(f"  Transaction {i+1}: ❌ Error - {e}")
                
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        print(f"\n  Results: {successful_models}/{len(transactions)} successful")
        print(f"  Average processing time: {avg_time*1000:.1f}ms")
        print(f"  Total models created: {len(self.platform.active_models)}")
        
        return successful_models >= 8  # Allow for some failures
        
    async def test_model_inheritance(self):
        """Test model inheritance functionality"""
        print("\n🔗 Testing Model Inheritance...")
        
        # Get model lineage for the last created model
        if self.platform.active_models:
            model_ids = list(self.platform.active_models.keys())
            last_model_id = model_ids[-1]
            
            try:
                lineage = await self.platform.get_model_lineage(last_model_id)
                print(f"  Model {last_model_id} lineage: {lineage}")
                print(f"  Inheritance depth: {len(lineage) - 1}")
                
                # Test prediction with inherited model
                test_features = {
                    "temperature": 320.0,
                    "pressure": 105000.0,
                    "flow_rate": 12.0
                }
                
                prediction = await self.platform.get_model_prediction(last_model_id, test_features)
                print(f"  Prediction test: {prediction}")
                
                return len(lineage) > 1 and "prediction" in prediction
                
            except Exception as e:
                print(f"  Inheritance test error: {e}")
                return False
        else:
            print("  No models available for inheritance testing")
            return False
            
    async def test_platform_metrics(self):
        """Test platform metrics and monitoring"""
        print("\n📊 Testing Platform Metrics...")
        
        metrics = self.platform.get_platform_metrics()
        
        print("  Platform Metrics:")
        for key, value in metrics.items():
            print(f"    {key}: {value}")
            
        # Check key metrics
        required_metrics = [
            "transactions_processed",
            "models_created", 
            "active_models",
            "physics_compliance_rate"
        ]
        
        has_all_metrics = all(metric in metrics for metric in required_metrics)
        print(f"  Metrics completeness: {'✅ PASS' if has_all_metrics else '❌ FAIL'}")
        
        return has_all_metrics
        
    async def run_quick_tests(self):
        """Run all quick tests"""
        print("🚀 Enhanced TML Platform v2.0 - Quick Test Suite")
        print("=" * 60)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        test_results = {}
        
        try:
            # Setup
            await self.setup_test_platform()
            
            # Run tests
            test_results["physics_engine"] = await self.test_physics_engine()
            test_results["transaction_processing"] = await self.test_basic_transaction_processing()
            test_results["model_inheritance"] = await self.test_model_inheritance()
            test_results["platform_metrics"] = await self.test_platform_metrics()
            
            # Summary
            print("\n" + "=" * 60)
            print("📋 TEST SUMMARY")
            print("-" * 30)
            
            passed_tests = 0
            total_tests = len(test_results)
            
            for test_name, passed in test_results.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {test_name.replace('_', ' ').title()}: {status}")
                if passed:
                    passed_tests += 1
                    
            print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
            
            if passed_tests == total_tests:
                print("\n🎉 All tests passed! Enhanced TML Platform v2.0 is working correctly!")
                print("✅ Physics validation: Working")
                print("✅ Model inheritance: Working") 
                print("✅ Transaction processing: Working")
                print("✅ Platform metrics: Working")
            else:
                print(f"\n⚠️  {total_tests - passed_tests} test(s) failed. Check the output above for details.")
                
        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup
            if self.platform:
                await self.platform.stop()
                print("\n🔧 Platform stopped and cleaned up.")
                
        return test_results


async def main():
    """Main test execution"""
    tester = QuickTester()
    results = await tester.run_quick_tests()
    
    # Exit with appropriate code
    all_passed = all(results.values()) if results else False
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    # Handle keyboard interrupt gracefully
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
