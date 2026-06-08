#!/usr/bin/env python3
"""
Security verification script to ensure vulnerable libraries are not installed
and secure replacements are in place.
"""

import subprocess
import sys
from typing import List, Tuple, Dict
import json

# Vulnerable libraries that should NOT be installed
VULNERABLE_LIBRARIES = [
    "mlflow",      # Multiple deserialization vulnerabilities
    "bentoml",     # Persistent deserialization vulnerabilities  
    "ray[serve]",  # RCE vulnerabilities
    "ray-serve",   # Alternative package name
    "feast",       # Deserialization and CORS vulnerabilities
    "feast-core",  # Related feast package
    "dgl",         # RCE via pickle deserialization
    "dgl-cuda",    # CUDA version of DGL
]

# Required secure replacements
SECURE_REPLACEMENTS = {
    "wandb": "Replacement for MLflow",
    "fastapi": "Replacement for BentoML",
    "uvicorn": "ASGI server for FastAPI",
    "torch-geometric": "Replacement for DGL",
    "redis": "Part of custom feature store",
    "cassandra-driver": "Part of custom feature store",
    "aioredis": "Part of custom actor system",
    "aiokafka": "Part of custom actor system",
}

# Libraries with known vulnerabilities that need specific versions
MINIMUM_VERSIONS = {
    "torch": "2.2.0",  # Must be >= 2.2.0 for security patches
    "numpy": "1.24.0",  # Must be >= 1.24.0
    "cryptography": "41.0.0",  # Must be >= 41.0.0
    "urllib3": "2.0.0",  # Must be >= 2.0.0
    "pillow": "10.0.0",  # Must be >= 10.0.0
    "pyyaml": "6.0.0",  # Must be >= 6.0.0
}


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def check_installed_packages() -> Dict[str, str]:
    """Get list of all installed packages with versions."""
    code, stdout, stderr = run_command(["pip", "list", "--format=json"])
    if code != 0:
        print(f"Error getting package list: {stderr}")
        return {}
    
    try:
        packages = json.loads(stdout)
        return {pkg["name"].lower(): pkg["version"] for pkg in packages}
    except json.JSONDecodeError:
        print("Error parsing package list")
        return {}


def parse_version(version_str: str) -> tuple:
    """Parse version string into comparable tuple."""
    try:
        parts = version_str.split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except:
        return (0, 0, 0)


def check_vulnerable_libraries(installed: Dict[str, str]) -> List[str]:
    """Check if any vulnerable libraries are installed."""
    found_vulnerable = []
    
    for lib in VULNERABLE_LIBRARIES:
        if lib.lower() in installed:
            found_vulnerable.append(f"{lib} (version {installed[lib.lower()]})")
    
    return found_vulnerable


def check_replacements(installed: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """Check if secure replacements are installed."""
    found = []
    missing = []
    
    for lib, description in SECURE_REPLACEMENTS.items():
        if lib.lower() in installed:
            found.append(f"{lib} {installed[lib.lower()]} - {description}")
        else:
            missing.append(f"{lib} - {description}")
    
    return found, missing


def check_versions(installed: Dict[str, str]) -> List[str]:
    """Check if installed packages meet minimum version requirements."""
    issues = []
    
    for lib, min_version in MINIMUM_VERSIONS.items():
        if lib.lower() in installed:
            installed_version = installed[lib.lower()]
            if parse_version(installed_version) < parse_version(min_version):
                issues.append(
                    f"{lib}: installed {installed_version}, "
                    f"need >= {min_version} for security"
                )
    
    return issues


def run_security_audit():
    """Run pip-audit if available."""
    print("\n" + "="*60)
    print("Running pip-audit security scan...")
    print("="*60)
    
    code, stdout, stderr = run_command(["pip-audit"])
    if code == 0:
        print("✅ pip-audit passed!")
        if stdout:
            print(stdout)
    else:
        if "command not found" in stderr or "No module named" in stderr:
            print("⚠️  pip-audit not installed. Install with: pip install pip-audit")
        else:
            print(f"❌ pip-audit found issues:\n{stdout}")


def main():
    """Main verification function."""
    print("="*60)
    print("TML SECURITY VERIFICATION")
    print("="*60)
    
    # Get installed packages
    print("\nChecking installed packages...")
    installed = check_installed_packages()
    
    if not installed:
        print("❌ Could not get package list")
        return 1
    
    print(f"Found {len(installed)} installed packages")
    
    # Check for vulnerable libraries
    print("\n" + "="*60)
    print("CHECKING FOR VULNERABLE LIBRARIES")
    print("="*60)
    
    vulnerable = check_vulnerable_libraries(installed)
    if vulnerable:
        print("❌ CRITICAL: Found vulnerable libraries installed:")
        for lib in vulnerable:
            print(f"   - {lib}")
        print("\nThese must be uninstalled immediately!")
        print("Run: pip uninstall " + " ".join([v.split()[0] for v in vulnerable]))
    else:
        print("✅ No vulnerable libraries found")
    
    # Check for replacements
    print("\n" + "="*60)
    print("CHECKING SECURE REPLACEMENTS")
    print("="*60)
    
    found, missing = check_replacements(installed)
    
    if found:
        print("✅ Found secure replacements:")
        for lib in found:
            print(f"   - {lib}")
    
    if missing:
        print("\n⚠️  Missing replacements:")
        for lib in missing:
            print(f"   - {lib}")
    
    # Check versions
    print("\n" + "="*60)
    print("CHECKING VERSION REQUIREMENTS")
    print("="*60)
    
    version_issues = check_versions(installed)
    if version_issues:
        print("⚠️  Version issues found:")
        for issue in version_issues:
            print(f"   - {issue}")
    else:
        print("✅ All version requirements met")
    
    # Run security audit
    run_security_audit()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_issues = len(vulnerable) + len(missing) + len(version_issues)
    
    if total_issues == 0:
        print("🎉 ALL SECURITY CHECKS PASSED!")
        print("Your TML platform is using secure libraries.")
        return 0
    else:
        print(f"⚠️  Found {total_issues} issues:")
        print(f"   - {len(vulnerable)} vulnerable libraries")
        print(f"   - {len(missing)} missing replacements")
        print(f"   - {len(version_issues)} version issues")
        
        if vulnerable:
            print("\n🚨 CRITICAL: Remove vulnerable libraries first!")
            return 1
        else:
            print("\n📋 Review and address the issues above")
            return 0


if __name__ == "__main__":
    sys.exit(main())
