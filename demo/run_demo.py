#!/usr/bin/env python3
"""
TML Platform Demo Launcher

Easy launcher for the TML Pipeline Inspection demonstration.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['streamlit', 'pandas', 'numpy', 'plotly']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} is missing")
    
    return missing_packages

def install_dependencies():
    """Install missing dependencies"""
    print("📦 Installing demo dependencies...")
    
    # Get the directory containing this script
    demo_dir = Path(__file__).parent
    requirements_file = demo_dir / "requirements.txt"
    
    if requirements_file.exists():
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            print("✅ Dependencies installed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    else:
        print("❌ requirements.txt not found")
        return False

def launch_demo():
    """Launch the Streamlit demo application"""
    print("🚀 Launching TML Platform Demo...")
    
    # Get the directory containing this script
    demo_dir = Path(__file__).parent
    app_file = demo_dir / "app.py"
    
    if app_file.exists():
        try:
            # Launch Streamlit
            subprocess.run([
                sys.executable, "-m", "streamlit", "run", str(app_file),
                "--server.port", "8501",
                "--server.address", "localhost"
            ])
        except KeyboardInterrupt:
            print("\n👋 Demo stopped by user")
        except Exception as e:
            print(f"❌ Failed to launch demo: {e}")
    else:
        print("❌ app.py not found")

def main():
    """Main launcher function"""
    print("🔧 TML Platform Demo Launcher")
    print("=" * 50)
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    missing = check_dependencies()
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        install_choice = input("Install missing dependencies? (y/n): ").lower().strip()
        
        if install_choice in ['y', 'yes']:
            if not install_dependencies():
                print("❌ Failed to install dependencies. Exiting.")
                sys.exit(1)
        else:
            print("❌ Cannot run demo without required dependencies. Exiting.")
            sys.exit(1)
    
    print("\n🎯 All dependencies are ready!")
    print("\n" + "=" * 50)
    print("🚀 Starting TML Platform Demo...")
    print("📱 The demo will open in your web browser")
    print("🔗 URL: http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the demo")
    print("=" * 50)
    
    # Launch the demo
    launch_demo()

if __name__ == "__main__":
    main()
