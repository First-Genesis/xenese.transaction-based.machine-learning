#!/usr/bin/env python3
"""
Simple HTTP server for TML Platform UI

This server serves the UI files and optionally connects to the TML API backend.
"""

import http.server
import socketserver
import os
import sys
import json
from pathlib import Path

# Add project root to path for API integration (optional)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

PORT = 8080

class TMLUIHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for TML UI with API proxy capabilities."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def end_headers(self):
        # Add CORS headers for API access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        """Custom log format."""
        sys.stdout.write(f"[UI Server] {self.address_string()} - {format % args}\n")


def main():
    """Start the UI server."""
    print("=" * 60)
    print("🚀 TML Platform UI Server")
    print("=" * 60)
    
    # Check if we can import TML modules for integrated mode
    integrated_mode = False
    try:
        from tml.core.model import TransactionModel
        integrated_mode = True
        print("✅ Integrated Mode: TML modules detected")
    except ImportError:
        print("⚠️  Standalone Mode: Running UI only (install dependencies for full integration)")
    
    print(f"\n📍 Starting server on http://localhost:{PORT}")
    print("🌐 Open your browser to http://localhost:{PORT} to view the UI")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Start the server
    with socketserver.TCPServer(("", PORT), TMLUIHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n⏹️  Server stopped by user")
            sys.exit(0)


if __name__ == "__main__":
    main()
