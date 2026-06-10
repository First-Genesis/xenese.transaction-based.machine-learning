#!/usr/bin/env python3
"""TML Platform Port Configuration Checker."""

import socket
import subprocess
import sys
from typing import Dict, List, Tuple

# TML Platform Port Configuration
TML_PORTS = {
    # Infrastructure
    5432: "PostgreSQL Database",
    6379: "Redis Cache", 
    29092: "Kafka External (USE THIS)",
    9092: "Kafka Internal (Docker only)",
    2181: "Zookeeper",
    
    # TML Services
    8000: "TML API Server (FastAPI)",
    8001: "TML Actor System Metrics",
    8081: "TML Dashboard",
    5003: "MLflow Server (Python)",
    5001: "C# TML API",
    
    # Monitoring
    9090: "Prometheus",
    3000: "Grafana",
    5002: "MLflow Docker (BROKEN)",
}

CRITICAL_PORTS = [29092, 5003, 8000, 8001]  # Must be available for UAT
CONFLICTING_PORTS = [5000]  # Should be occupied (ControlCenter)


def check_port(port: int) -> Tuple[bool, str]:
    """Check if a port is in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                return True, "IN USE"
            else:
                return False, "AVAILABLE"
    except Exception as e:
        return False, f"ERROR: {e}"


def get_port_process(port: int) -> str:
    """Get the process using a port."""
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split('\n')[0]
            
            # Get process name
            proc_result = subprocess.run(
                ['ps', '-p', pid, '-o', 'comm='], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if proc_result.returncode == 0:
                return proc_result.stdout.strip()
        return "Unknown"
    except Exception:
        return "Unknown"


def check_tml_ports():
    """Check all TML platform ports."""
    print("🔍 TML Platform Port Configuration Check")
    print("=" * 60)
    
    issues = []
    
    for port, service in TML_PORTS.items():
        in_use, status = check_port(port)
        process = get_port_process(port) if in_use else ""
        
        # Determine status icon
        if port in CRITICAL_PORTS:
            if in_use:
                icon = "✅" if "kafka" in process.lower() or "mlflow" in process.lower() or "uvicorn" in process.lower() else "⚠️"
            else:
                icon = "❌"
                issues.append(f"Critical port {port} ({service}) is not running")
        elif port in CONFLICTING_PORTS:
            icon = "✅" if in_use else "⚠️"
            if not in_use:
                issues.append(f"Port {port} should be occupied by ControlCenter")
        else:
            icon = "✅" if in_use else "⚪"
        
        print(f"{icon} Port {port:5d}: {service:25s} | {status:10s} | {process}")
    
    print("\n" + "=" * 60)
    
    # Check environment variables
    print("🔧 Environment Variables Check")
    import os
    
    env_vars = {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:29092",
        "MLFLOW_TRACKING_URI": "http://localhost:5003",
    }
    
    for var, expected in env_vars.items():
        actual = os.environ.get(var, "NOT SET")
        icon = "✅" if actual == expected else "❌"
        print(f"{icon} {var}: {actual}")
        if actual != expected:
            issues.append(f"Environment variable {var} should be '{expected}', got '{actual}'")
    
    # Summary
    print("\n" + "=" * 60)
    if issues:
        print("❌ Issues Found:")
        for issue in issues:
            print(f"   • {issue}")
        print(f"\n💡 Run: export KAFKA_BOOTSTRAP_SERVERS=localhost:29092")
        print(f"💡 Run: export MLFLOW_TRACKING_URI=http://localhost:5003")
        return False
    else:
        print("✅ All TML ports configured correctly!")
        return True


def test_kafka_connectivity():
    """Test Kafka connectivity on the correct port."""
    print("\n🔌 Testing Kafka Connectivity")
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            request_timeout_ms=5000
        )
        producer.close()
        print("✅ Kafka connection successful on port 29092")
        return True
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        return False


def test_mlflow_connectivity():
    """Test MLflow connectivity."""
    print("\n🧪 Testing MLflow Connectivity")
    try:
        import requests
        response = requests.get("http://localhost:5003/health", timeout=5)
        if response.status_code == 200:
            print("✅ MLflow connection successful on port 5003")
            return True
        else:
            print(f"❌ MLflow returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ MLflow connection failed: {e}")
        return False


def main():
    """Main port checker."""
    print("🚀 TML Platform Port Configuration Checker")
    print("This tool verifies all ports are correctly configured for UAT\n")
    
    # Check ports
    ports_ok = check_tml_ports()
    
    # Test connectivity
    kafka_ok = test_kafka_connectivity()
    mlflow_ok = test_mlflow_connectivity()
    
    # Final summary
    print("\n" + "=" * 60)
    print("📋 UAT Readiness Summary")
    print(f"✅ Port Configuration: {'PASS' if ports_ok else 'FAIL'}")
    print(f"✅ Kafka Connectivity: {'PASS' if kafka_ok else 'FAIL'}")
    print(f"✅ MLflow Connectivity: {'PASS' if mlflow_ok else 'FAIL'}")
    
    if ports_ok and kafka_ok and mlflow_ok:
        print("\n🎉 TML Platform is ready for UAT!")
        return 0
    else:
        print("\n⚠️ TML Platform has configuration issues. Fix before UAT.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
