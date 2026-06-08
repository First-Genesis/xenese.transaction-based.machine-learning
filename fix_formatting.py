#!/usr/bin/env python3
"""
Fix all code formatting issues for CI/CD pipeline
"""
import subprocess
import sys
import os

def run_command(cmd):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd="/Users/rwattyfirstgenesis.com/TML"
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def main():
    print("🎨 Fixing code formatting for CI/CD pipeline...")
    
    # Change to TML directory
    os.chdir("/Users/rwattyfirstgenesis.com/TML")
    
    # Run Black formatting
    print("\n1. Running Black formatter...")
    code, stdout, stderr = run_command("python3 -m black tml/ tests/")
    print(f"Black output: {stdout}")
    if stderr:
        print(f"Black stderr: {stderr}")
    
    # Run isort
    print("\n2. Running isort...")
    code, stdout, stderr = run_command("python3 -m isort tml/ tests/")
    print(f"isort output: {stdout}")
    if stderr:
        print(f"isort stderr: {stderr}")
    
    # Check if Black is satisfied
    print("\n3. Verifying Black formatting...")
    code, stdout, stderr = run_command("python3 -m black --check tml/ tests/")
    if code == 0:
        print("✅ Black formatting check passed!")
    else:
        print("❌ Black formatting check failed:")
        print(stdout)
        print(stderr)
        return 1
    
    # Check if isort is satisfied
    print("\n4. Verifying isort...")
    code, stdout, stderr = run_command("python3 -m isort --check-only tml/ tests/")
    if code == 0:
        print("✅ isort check passed!")
    else:
        print("❌ isort check failed:")
        print(stdout)
        print(stderr)
        return 1
    
    print("\n🎉 All formatting checks passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
