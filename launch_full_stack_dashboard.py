#!/usr/bin/env python3
"""
TML Full-Stack Dashboard Launcher
Launches the complete integrated dashboard with infrastructure checks
"""

import subprocess
import sys
import os
import time
import requests
import psycopg2
import redis
from pathlib import Path

def check_infrastructure():
    """Check if required infrastructure is running"""
    
    print("🔍 Checking TML Infrastructure...")
    
    checks = {
        'PostgreSQL': False,
        'Redis': False,
        'Kafka': False,
        'Proto.Actor': False,
        'MLflow': False,
        'Prometheus': False
    }
    
    # Check PostgreSQL
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, database="tml_platform",
            user="tml_user", password="tml_password", connect_timeout=3
        )
        conn.close()
        checks['PostgreSQL'] = True
        print("✅ PostgreSQL: Connected")
    except:
        print("❌ PostgreSQL: Not available")
    
    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6379, socket_timeout=3)
        r.ping()
        checks['Redis'] = True
        print("✅ Redis: Connected")
    except:
        print("❌ Redis: Not available")
    
    # Check Kafka (via simple connection test)
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            request_timeout_ms=3000
        )
        producer.close()
        checks['Kafka'] = True
        print("✅ Kafka: Connected")
    except:
        print("❌ Kafka: Not available")
    
    # Check Proto.Actor system
    try:
        response = requests.get("http://localhost:8001/metrics", timeout=3)
        if response.status_code == 200:
            checks['Proto.Actor'] = True
            print("✅ Proto.Actor: Running")
        else:
            print("❌ Proto.Actor: Not responding")
    except:
        print("❌ Proto.Actor: Not available")
    
    # Check MLflow
    try:
        response = requests.get("http://localhost:5003/api/2.0/mlflow/experiments/search", timeout=3)
        if response.status_code == 200:
            checks['MLflow'] = True
            print("✅ MLflow: Running")
        else:
            print("❌ MLflow: Not responding")
    except:
        print("❌ MLflow: Not available")
    
    # Check Prometheus
    try:
        response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=3)
        if response.status_code == 200:
            checks['Prometheus'] = True
            print("✅ Prometheus: Running")
        else:
            print("❌ Prometheus: Not responding")
    except:
        print("❌ Prometheus: Not available")
    
    return checks

def main():
    """Launch the full-stack dashboard with infrastructure validation"""
    
    print("🏗️ TML Full-Stack Dashboard Launcher")
    print("="*60)
    
    dashboard_path = Path(__file__).parent / "tml" / "ui" / "full_stack_dashboard.py"
    
    if not dashboard_path.exists():
        print(f"❌ Dashboard not found: {dashboard_path}")
        return 1
    
    # Check infrastructure
    infrastructure_status = check_infrastructure()
    available_services = sum(infrastructure_status.values())
    total_services = len(infrastructure_status)
    
    print(f"\n📊 Infrastructure Status: {available_services}/{total_services} services available")
    
    if available_services == 0:
        print("\n⚠️  WARNING: No infrastructure services detected!")
        print("The dashboard will run in limited mode with simulated data.")
        print("\nTo enable full functionality, start the required services:")
        print("- docker-compose up -d (PostgreSQL, Redis, Kafka)")
        print("- python run_actor_bridge.py (Proto.Actor system)")
        print("- mlflow server --host 0.0.0.0 --port 5003")
        print("- prometheus (if using monitoring)")
    elif available_services < total_services:
        print(f"\n⚠️  PARTIAL: {available_services}/{total_services} services available")
        print("Some features may have limited functionality.")
    else:
        print("\n🎉 ALL SERVICES AVAILABLE: Full-stack mode enabled!")
    
    print(f"\n🚀 Starting full-stack dashboard on port 8505...")
    print("🌐 URL: http://localhost:8505")
    print("⏹️  Press Ctrl+C to stop")
    print("="*60)
    
    try:
        cmd = f"""
        cd {Path(__file__).parent} && 
        source venv/bin/activate && 
        echo "" | streamlit run {dashboard_path} \
            --server.port=8505 \
            --server.address=0.0.0.0 \
            --browser.gatherUsageStats=false \
            --server.headless=true
        """
        
        subprocess.run(cmd, shell=True, check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Full-stack dashboard stopped")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
