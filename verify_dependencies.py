#!/usr/bin/env python3
"""
Dependency Verification Script for Enhanced TML Platform v2.0

Verifies all required dependencies are properly installed and importable.
"""

import sys
import importlib

def test_import(module_name, description=""):
    """Test if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name:<20} - {description}")
        return True
    except ImportError as e:
        print(f"❌ {module_name:<20} - FAILED: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {module_name:<20} - ERROR: {e}")
        return False

def main():
    """Main verification function"""
    print("🔍 Enhanced TML Platform v2.0 - Dependency Verification")
    print("=" * 60)
    
    # Core Python libraries
    print("\n📦 Core Libraries:")
    core_modules = [
        ("numpy", "Numerical computing"),
        ("pandas", "Data manipulation"),
        ("scipy", "Scientific computing"),
        ("matplotlib", "Plotting and visualization"),
        ("sympy", "Symbolic mathematics"),
        ("asyncio", "Asynchronous programming"),
        ("json", "JSON handling"),
        ("datetime", "Date and time utilities"),
        ("dataclasses", "Data classes"),
        ("typing", "Type hints"),
        ("abc", "Abstract base classes"),
        ("enum", "Enumerations"),
        ("logging", "Logging framework")
    ]
    
    core_success = 0
    for module, desc in core_modules:
        if test_import(module, desc):
            core_success += 1
    
    # Machine Learning libraries
    print("\n🧠 Machine Learning Libraries:")
    ml_modules = [
        ("sklearn", "Scikit-learn ML library"),
        ("river", "Online machine learning"),
        ("vowpalwabbit", "Fast online learning")
    ]
    
    ml_success = 0
    for module, desc in ml_modules:
        if test_import(module, desc):
            ml_success += 1
    
    # Testing libraries
    print("\n🧪 Testing Libraries:")
    test_modules = [
        ("pytest", "Testing framework"),
        ("pytest_asyncio", "Async testing support")
    ]
    
    test_success = 0
    for module, desc in test_modules:
        if test_import(module, desc):
            test_success += 1
    
    # Summary
    total_modules = len(core_modules) + len(ml_modules) + len(test_modules)
    total_success = core_success + ml_success + test_success
    
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("-" * 30)
    print(f"Core Libraries: {core_success}/{len(core_modules)}")
    print(f"ML Libraries: {ml_success}/{len(ml_modules)}")
    print(f"Test Libraries: {test_success}/{len(test_modules)}")
    print(f"Total: {total_success}/{total_modules}")
    
    if total_success == total_modules:
        print("\n🎉 All dependencies verified successfully!")
        print("✅ Ready to run Enhanced TML Platform v2.0 tests")
        return True
    else:
        missing = total_modules - total_success
        print(f"\n⚠️  {missing} dependencies missing or failed to import")
        print("❌ Some tests may fail due to missing dependencies")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
