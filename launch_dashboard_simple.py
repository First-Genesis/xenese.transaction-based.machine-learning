#!/usr/bin/env python3
"""
Simple TML Dashboard Launcher (bypasses Streamlit welcome screen)
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def main():
    """Launch the dashboard with automatic welcome screen bypass"""
    
    print("🧠 TML Advanced AI Dashboard - Simple Launcher")
    print("="*60)
    
    dashboard_path = Path(__file__).parent / "tml" / "ui" / "advanced_ai_dashboard.py"
    
    if not dashboard_path.exists():
        print(f"❌ Dashboard not found: {dashboard_path}")
        return 1
    
    print("🚀 Starting dashboard on port 8504...")
    print("🌐 URL: http://localhost:8504")
    print("⏹️  Press Ctrl+C to stop")
    print("="*60)
    
    try:
        # Use echo to bypass welcome screen
        cmd = f"""
        cd {Path(__file__).parent} && 
        source venv/bin/activate && 
        echo "" | streamlit run {dashboard_path} \
            --server.port=8504 \
            --server.address=0.0.0.0 \
            --browser.gatherUsageStats=false \
            --server.headless=true
        """
        
        subprocess.run(cmd, shell=True, check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
