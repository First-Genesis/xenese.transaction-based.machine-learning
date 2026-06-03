#!/usr/bin/env python3
"""
Simple HTTP server for Drilling Dashboard

Serves the drilling dashboard and handles CORS issues.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8081

class DrillingDashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for drilling dashboard."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from (TML root)
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Disable caching for development
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        """Custom log format."""
        sys.stdout.write(f"[Drilling Server] {self.address_string()} - {format % args}\n")


def main():
    """Start the drilling dashboard server."""
    print("=" * 60)
    print("🛢️  Drilling Dashboard Server")
    print("=" * 60)
    
    print(f"📍 Starting server on http://localhost:{PORT}")
    print(f"🌐 Dashboard URL: http://localhost:{PORT}/drilling_dashboard.html")
    print(f"📊 IoT Dashboard: http://localhost:{PORT}/iot_dashboard.html")
    print(f"🎛️  TML UI: http://localhost:{PORT}/ui/index.html")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Start the server
    with socketserver.TCPServer(("", PORT), DrillingDashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n⏹️  Server stopped by user")
            sys.exit(0)


if __name__ == "__main__":
    main()
