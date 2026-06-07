#!/usr/bin/env python3
"""
Convert TML Technical Guide to Word Document

Creates a properly formatted Word document from the markdown technical guide.
"""

import os
import subprocess
import sys
from pathlib import Path

def check_pandoc():
    """Check if pandoc is installed"""
    try:
        result = subprocess.run(['pandoc', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Pandoc is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Pandoc not found")
    return False

def install_pandoc_instructions():
    """Provide instructions for installing pandoc"""
    print("\n📦 To install Pandoc:")
    print("🍎 macOS: brew install pandoc")
    print("🐧 Linux: sudo apt install pandoc")
    print("🪟 Windows: Download from https://pandoc.org/installing.html")
    print("\nOr use the alternative method below...")

def convert_to_word():
    """Convert markdown to Word document using pandoc"""
    input_file = Path("docs/TML_Platform_Technical_Guide_For_Students.md")
    output_file = Path("docs/TML_Platform_Technical_Guide_For_Students.docx")
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return False
    
    try:
        # Convert with pandoc
        cmd = [
            'pandoc',
            str(input_file),
            '-o', str(output_file),
            '--from', 'markdown',
            '--to', 'docx',
            '--reference-doc', 'docs/word_template.docx' if Path('docs/word_template.docx').exists() else None,
            '--toc',
            '--toc-depth=3'
        ]
        
        # Remove None values
        cmd = [x for x in cmd if x is not None]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Successfully created Word document: {output_file}")
            print(f"📄 File size: {output_file.stat().st_size / 1024:.1f} KB")
            return True
        else:
            print(f"❌ Pandoc error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error converting to Word: {e}")
        return False

def create_simple_word_alternative():
    """Create a simple RTF file that can be opened in Word"""
    input_file = Path("docs/TML_Platform_Technical_Guide_For_Students.md")
    output_file = Path("docs/TML_Platform_Technical_Guide_For_Students.rtf")
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return False
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple RTF conversion
        rtf_content = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0 Times New Roman;}}
{\colortbl;\red0\green0\blue0;\red0\green0\blue255;}
\f0\fs24
""" + content.replace('\n', r'\par ').replace('#', r'\b ').replace('**', r'\b ') + r'\par }'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(rtf_content)
        
        print(f"✅ Created RTF document: {output_file}")
        print("📝 This RTF file can be opened in Microsoft Word")
        return True
        
    except Exception as e:
        print(f"❌ Error creating RTF: {e}")
        return False

def main():
    """Main conversion function"""
    print("📄 TML Technical Guide → Word Document Converter")
    print("=" * 60)
    
    # Check if pandoc is available
    if check_pandoc():
        print("\n🔄 Converting with Pandoc...")
        if convert_to_word():
            print("\n🎉 Word document created successfully!")
            print("📁 Location: docs/TML_Platform_Technical_Guide_For_Students.docx")
            return
    else:
        install_pandoc_instructions()
    
    # Fallback to RTF
    print("\n🔄 Creating RTF alternative...")
    if create_simple_word_alternative():
        print("\n📝 RTF document created!")
        print("📁 Location: docs/TML_Platform_Technical_Guide_For_Students.rtf")
        print("💡 Open this file in Microsoft Word to convert to .docx format")
    else:
        print("\n❌ Could not create Word document")
        print("📄 The markdown file is available at:")
        print("   docs/TML_Platform_Technical_Guide_For_Students.md")

if __name__ == "__main__":
    main()
