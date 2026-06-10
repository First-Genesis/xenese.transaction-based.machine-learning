#!/usr/bin/env python3
"""
TML Infrastructure Startup Script
Starts all required TML platform services for full-stack operation
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

class TMLInfrastructureManager:
    """Manages TML platform infrastructure services"""
    
    def __init__(self):
        self.processes = {}
        self.services = {
            'docker': {'name': 'Docker Services', 'required': True},
            'mlflow': {'name': 'MLflow Server', 'required': False},
            'actor_system': {'name': 'Proto.Actor System', 'required': False}
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down services...")
        self.shutdown_all()
        sys.exit(0)
    
    def start_docker_services(self):
        """Start Docker infrastructure services"""
        print("🐳 Starting Docker services...")
        
        try:
            # Check if docker-compose.yml exists
            compose_file = Path("docker-compose.yml")
            if not compose_file.exists():
                print("❌ docker-compose.yml not found")
                return False
            
            # Start Docker services
            result = subprocess.run([
                "docker-compose", "up", "-d", 
                "postgres", "redis", "kafka", "zookeeper"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Docker services started")
                return True
            else:
                print(f"❌ Docker services failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Docker startup timed out")
            return False
        except Exception as e:
            print(f"❌ Docker startup error: {e}")
            return False
    
    def start_mlflow_server(self):
        """Start MLflow tracking server"""
        print("📊 Starting MLflow server...")
        
        try:
            # Start MLflow server
            process = subprocess.Popen([
                sys.executable, "-m", "mlflow", "server",
                "--host", "0.0.0.0",
                "--port", "5003",
                "--backend-store-uri", "sqlite:///mlflow.db",
                "--default-artifact-root", "./mlflow-artifacts"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.processes['mlflow'] = process
            
            # Wait a moment and check if it's running
            time.sleep(3)
            if process.poll() is None:
                print("✅ MLflow server started on port 5003")
                return True
            else:
                print("❌ MLflow server failed to start")
                return False
                
        except Exception as e:
            print(f"❌ MLflow startup error: {e}")
            return False
    
    def start_actor_system(self):
        """Start Proto.Actor system"""
        print("🎭 Starting Proto.Actor system...")
        
        try:
            # Check if actor bridge exists
            actor_bridge = Path("run_actor_bridge.py")
            if not actor_bridge.exists():
                print("❌ run_actor_bridge.py not found")
                return False
            
            # Start actor system
            process = subprocess.Popen([
                sys.executable, "run_actor_bridge.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.processes['actor_system'] = process
            
            # Wait and check if it's running
            time.sleep(5)
            if process.poll() is None:
                print("✅ Proto.Actor system started")
                return True
            else:
                print("❌ Proto.Actor system failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Actor system startup error: {e}")
            return False
    
    def check_service_health(self, service_name):
        """Check if a service is healthy"""
        
        if service_name == 'docker':
            try:
                result = subprocess.run([
                    "docker-compose", "ps", "--services", "--filter", "status=running"
                ], capture_output=True, text=True, timeout=10)
                return len(result.stdout.strip().split('\n')) >= 4  # At least 4 services
            except:
                return False
        
        elif service_name == 'mlflow':
            try:
                import requests
                response = requests.get("http://localhost:5003/health", timeout=5)
                return response.status_code == 200
            except:
                return False
        
        elif service_name == 'actor_system':
            try:
                import requests
                response = requests.get("http://localhost:8001/metrics", timeout=5)
                return response.status_code == 200
            except:
                return False
        
        return False
    
    def start_all_services(self):
        """Start all TML infrastructure services"""
        print("🚀 TML Infrastructure Startup")
        print("="*50)
        
        success_count = 0
        total_count = 0
        
        # Start Docker services first (required)
        total_count += 1
        if self.start_docker_services():
            success_count += 1
            
            # Wait for Docker services to be ready
            print("⏳ Waiting for Docker services to be ready...")
            for i in range(30):  # Wait up to 30 seconds
                if self.check_service_health('docker'):
                    print("✅ Docker services are ready")
                    break
                time.sleep(1)
            else:
                print("⚠️  Docker services may not be fully ready")
        
        # Start optional services in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            
            # MLflow
            total_count += 1
            future_mlflow = executor.submit(self.start_mlflow_server)
            futures.append(('mlflow', future_mlflow))
            
            # Actor System
            total_count += 1
            future_actor = executor.submit(self.start_actor_system)
            futures.append(('actor_system', future_actor))
            
            # Wait for all to complete
            for service_name, future in futures:
                if future.result():
                    success_count += 1
        
        print("\n" + "="*50)
        print(f"📊 Infrastructure Status: {success_count}/{total_count} services started")
        
        if success_count == total_count:
            print("🎉 ALL SERVICES STARTED SUCCESSFULLY!")
            print("\n🌐 Available Services:")
            print("- PostgreSQL: localhost:5432")
            print("- Redis: localhost:6379") 
            print("- Kafka: localhost:29092")
            print("- MLflow: http://localhost:5003")
            print("- Proto.Actor: http://localhost:8001")
            print("\n✅ Ready for full-stack TML dashboard!")
            
        elif success_count >= 1:
            print("⚠️  PARTIAL SUCCESS - Some services may have limited functionality")
            
        else:
            print("❌ STARTUP FAILED - No services started successfully")
            return False
        
        return success_count > 0
    
    def shutdown_all(self):
        """Shutdown all started services"""
        print("\n🛑 Shutting down TML infrastructure...")
        
        # Stop Python processes
        for service_name, process in self.processes.items():
            if process and process.poll() is None:
                print(f"⏹️  Stopping {service_name}...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                    print(f"✅ {service_name} stopped")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print(f"🔪 {service_name} force killed")
        
        # Stop Docker services
        try:
            print("⏹️  Stopping Docker services...")
            subprocess.run([
                "docker-compose", "down"
            ], capture_output=True, timeout=30)
            print("✅ Docker services stopped")
        except:
            print("⚠️  Docker services may still be running")
        
        print("✅ Infrastructure shutdown complete")
    
    def monitor_services(self):
        """Monitor running services"""
        print("\n🔍 Monitoring services (Press Ctrl+C to stop)...")
        
        try:
            while True:
                print(f"\n📊 Service Health Check - {time.strftime('%H:%M:%S')}")
                
                for service in ['docker', 'mlflow', 'actor_system']:
                    if self.check_service_health(service):
                        print(f"✅ {service}: Healthy")
                    else:
                        print(f"❌ {service}: Not responding")
                
                time.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")

def main():
    """Main infrastructure startup"""
    
    manager = TMLInfrastructureManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        manager.shutdown_all()
        return 0
    
    # Start all services
    if manager.start_all_services():
        print("\n🎯 Next Steps:")
        print("1. Run: python launch_full_stack_dashboard.py")
        print("2. Access dashboard at: http://localhost:8505")
        print("3. Use Ctrl+C to stop all services")
        
        # Monitor services
        manager.monitor_services()
    else:
        print("\n❌ Infrastructure startup failed")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
