#!/usr/bin/env python3
"""
Open TML Technical Guide Word Document
"""

import subprocess
import sys
from pathlib import Path

def open_word_document():
    """Open the Word document"""
    word_file = Path("docs/TML_Platform_Technical_Guide_For_Students.docx")
    
    if not word_file.exists():
        print(f"❌ Word document not found: {word_file}")
        print("🔄 Run 'python3 create_word_doc.py' to create it")
        return False
    
    try:
        # Open with default application (Word)
        subprocess.run(['open', str(word_file)], check=True)
        print(f"✅ Opened Word document: {word_file}")
        print(f"📄 File size: {word_file.stat().st_size / 1024:.1f} KB")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Could not open {word_file}")
        print("💡 Try opening it manually from the docs/ folder")
        return False
    except FileNotFoundError:
        print("❌ 'open' command not found (macOS only)")
        print(f"📁 Document location: {word_file.absolute()}")
        return False

if __name__ == "__main__":
    print("📄 Opening TML Technical Guide Word Document...")
    open_word_document()
