#!/usr/bin/env python3
"""
Open TML Demo in Browser
"""

import webbrowser
import time
import subprocess
import sys

def open_demo():
    """Open the demo in the default browser"""
    urls = [
        "http://localhost:8501",
        "http://localhost:8502"
    ]
    
    print("🌐 Opening TML Platform Demo in your browser...")
    
    for url in urls:
        print(f"🔗 Trying: {url}")
        try:
            webbrowser.open(url)
            print(f"✅ Opened {url}")
            break
        except Exception as e:
            print(f"❌ Failed to open {url}: {e}")
    
    print("\n🎯 If the demo doesn't load automatically:")
    print("1. Open your web browser manually")
    print("2. Navigate to: http://localhost:8501 or http://localhost:8502")
    print("3. The TML Platform Demo should appear")

if __name__ == "__main__":
    open_demo()
