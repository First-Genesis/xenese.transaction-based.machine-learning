#!/usr/bin/env python3
"""
TML Advanced AI Dashboard Launcher
Quick launcher for the Streamlit dashboard demonstrating all advanced AI features
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Launch the TML Advanced AI Dashboard"""
    
    print("🧠 TML Advanced AI Dashboard Launcher")
    print("="*50)
    
    # Get the dashboard path
    dashboard_path = Path(__file__).parent / "tml" / "ui" / "advanced_ai_dashboard.py"
    
    if not dashboard_path.exists():
        print(f"❌ Dashboard file not found: {dashboard_path}")
        return 1
    
    print(f"📂 Dashboard location: {dashboard_path}")
    print("🚀 Starting Streamlit server...")
    print("📱 Dashboard will open in your browser automatically")
    print("🔗 URL: http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the server")
    print("="*50)
    
    try:
        # Launch Streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port=8501",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false"
        ]
        
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start dashboard: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
