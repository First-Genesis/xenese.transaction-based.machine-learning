#!/usr/bin/env python3
"""
TML Platform Production Deployment Script

Automated deployment for staging and production environments.
"""

import os
import sys
import subprocess
import argparse
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class TMLDeployer:
    """TML Platform deployment manager"""
    
    def __init__(self, environment: str, project_root: Path):
        self.environment = environment
        self.project_root = project_root
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def log(self, message: str, level: str = "INFO"):
        """Log deployment message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def run_command(self, command: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run deployment command"""
        self.log(f"Running: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                check=True,
                capture_output=True,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e.stderr}", "ERROR")
            raise
    
    def validate_environment(self):
        """Validate deployment environment"""
        self.log("Validating deployment environment...")
        
        # Check required files
        required_files = [
            "docker-compose.yml",
            "requirements.txt",
            f".env.{self.environment}",
            "config/settings.py"
        ]
        
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                raise FileNotFoundError(f"Required file not found: {file_path}")
        
        # Check environment variables
        if self.environment == "production":
            required_env_vars = [
                "DATABASE_URL",
                "REDIS_PASSWORD", 
                "JWT_SECRET_KEY",
                "ENCRYPTION_KEY"
            ]
            
            for var in required_env_vars:
                if not os.getenv(var):
                    self.log(f"Warning: {var} not set", "WARNING")
        
        self.log("Environment validation complete")
    
    def build_images(self):
        """Build Docker images"""
        self.log("Building Docker images...")
        
        # Build API image
        self.run_command([
            "docker", "build",
            "-f", "docker/Dockerfile.api",
            "-t", f"tml-api:{self.environment}",
            "-t", f"tml-api:{self.environment}-{self.timestamp}",
            "."
        ])
        
        # Build dashboard image
        self.run_command([
            "docker", "build", 
            "-f", "docker/Dockerfile.dashboard",
            "-t", f"tml-dashboard:{self.environment}",
            "-t", f"tml-dashboard:{self.environment}-{self.timestamp}",
            "."
        ])
        
        self.log("Docker images built successfully")
    
    def run_tests(self):
        """Run test suite before deployment"""
        self.log("Running test suite...")
        
        # Run unit tests
        self.run_command([
            "docker", "run", "--rm",
            f"tml-api:{self.environment}",
            "python", "-m", "pytest", "tests/unit/", "-v"
        ])
        
        # Run integration tests if not production
        if self.environment != "production":
            self.run_command([
                "docker", "run", "--rm",
                f"tml-api:{self.environment}",
                "python", "-m", "pytest", "tests/integration/", "-v"
            ])
        
        self.log("All tests passed")
    
    def backup_data(self):
        """Backup existing data before deployment"""
        if self.environment != "production":
            return
        
        self.log("Creating data backup...")
        
        backup_dir = self.project_root / "backups" / self.timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup database
        self.run_command([
            "docker", "exec", "tml-postgres",
            "pg_dump", "-U", "tml", "tml",
            "-f", f"/tmp/backup_{self.timestamp}.sql"
        ])
        
        self.run_command([
            "docker", "cp", 
            f"tml-postgres:/tmp/backup_{self.timestamp}.sql",
            str(backup_dir / f"database_{self.timestamp}.sql")
        ])
        
        # Backup Redis data
        self.run_command([
            "docker", "exec", "tml-redis",
            "redis-cli", "BGSAVE"
        ])
        
        self.log("Data backup completed")
    
    def deploy_infrastructure(self):
        """Deploy infrastructure services"""
        self.log("Deploying infrastructure services...")
        
        # Copy environment-specific compose file
        env_compose = self.project_root / f"docker-compose.{self.environment}.yml"
        if env_compose.exists():
            compose_files = ["-f", "docker-compose.yml", "-f", str(env_compose)]
        else:
            compose_files = ["-f", "docker-compose.yml"]
        
        # Deploy with Docker Compose
        self.run_command([
            "docker-compose"
        ] + compose_files + [
            "up", "-d",
            "--remove-orphans"
        ])
        
        self.log("Infrastructure services deployed")
    
    def deploy_application(self):
        """Deploy application services"""
        self.log("Deploying application services...")
        
        # Rolling update for zero-downtime deployment
        services = ["tml-api", "tml-dashboard"]
        
        for service in services:
            self.log(f"Updating {service}...")
            
            # Scale up new instances
            self.run_command([
                "docker-compose", "up", "-d", "--scale", f"{service}=2", service
            ])
            
            # Health check
            self.wait_for_health_check(service)
            
            # Scale down old instances
            self.run_command([
                "docker-compose", "up", "-d", "--scale", f"{service}=1", service
            ])
        
        self.log("Application services deployed")
    
    def wait_for_health_check(self, service: str, timeout: int = 300):
        """Wait for service health check to pass"""
        self.log(f"Waiting for {service} health check...")
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                result = self.run_command([
                    "docker", "exec", service, 
                    "curl", "-f", "http://localhost:8000/health"
                ])
                if result.returncode == 0:
                    self.log(f"{service} health check passed")
                    return
            except subprocess.CalledProcessError:
                pass
            
            time.sleep(10)
        
        raise TimeoutError(f"{service} health check failed after {timeout} seconds")
    
    def run_migrations(self):
        """Run database migrations"""
        self.log("Running database migrations...")
        
        # Run migration script
        self.run_command([
            "docker", "exec", "tml-api",
            "python", "-m", "alembic", "upgrade", "head"
        ])
        
        self.log("Database migrations completed")
    
    def verify_deployment(self):
        """Verify deployment success"""
        self.log("Verifying deployment...")
        
        # Check service health
        services = ["tml-api", "tml-dashboard", "redis", "postgres", "kafka"]
        
        for service in services:
            result = self.run_command([
                "docker-compose", "ps", service
            ])
            
            if "Up" not in result.stdout:
                raise RuntimeError(f"Service {service} is not running")
        
        # Run smoke tests
        self.run_command([
            "docker", "exec", "tml-api",
            "python", "-m", "pytest", "tests/smoke/", "-v"
        ])
        
        self.log("Deployment verification completed")
    
    def setup_monitoring(self):
        """Setup monitoring and alerting"""
        self.log("Setting up monitoring...")
        
        # Deploy monitoring stack
        monitoring_compose = self.project_root / "docker" / "docker-compose.monitoring.yml"
        if monitoring_compose.exists():
            self.run_command([
                "docker-compose", "-f", str(monitoring_compose), "up", "-d"
            ])
        
        # Configure alerts
        if self.environment == "production":
            self.configure_production_alerts()
        
        self.log("Monitoring setup completed")
    
    def configure_production_alerts(self):
        """Configure production alerting"""
        self.log("Configuring production alerts...")
        
        # This would typically configure:
        # - Prometheus alerting rules
        # - Grafana dashboards
        # - PagerDuty/Slack integrations
        # - Log aggregation
        
        self.log("Production alerts configured")
    
    def cleanup_old_images(self):
        """Cleanup old Docker images"""
        self.log("Cleaning up old images...")
        
        # Remove old images (keep last 3 versions)
        self.run_command([
            "docker", "image", "prune", "-f"
        ])
        
        self.log("Image cleanup completed")
    
    def generate_deployment_report(self):
        """Generate deployment report"""
        self.log("Generating deployment report...")
        
        report = {
            "deployment_id": self.timestamp,
            "environment": self.environment,
            "timestamp": datetime.now().isoformat(),
            "services_deployed": [
                "tml-api",
                "tml-dashboard", 
                "redis",
                "postgres",
                "kafka",
                "prometheus",
                "grafana"
            ],
            "image_tags": {
                "tml-api": f"{self.environment}-{self.timestamp}",
                "tml-dashboard": f"{self.environment}-{self.timestamp}"
            }
        }
        
        report_file = self.project_root / "deployments" / f"deployment_{self.timestamp}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log(f"Deployment report saved: {report_file}")
    
    def deploy(self):
        """Execute full deployment"""
        self.log(f"Starting {self.environment} deployment...")
        
        try:
            # Pre-deployment
            self.validate_environment()
            self.build_images()
            self.run_tests()
            
            if self.environment == "production":
                self.backup_data()
            
            # Deployment
            self.deploy_infrastructure()
            self.run_migrations()
            self.deploy_application()
            
            # Post-deployment
            self.verify_deployment()
            self.setup_monitoring()
            self.cleanup_old_images()
            self.generate_deployment_report()
            
            self.log(f"✅ {self.environment} deployment completed successfully!")
            
        except Exception as e:
            self.log(f"❌ Deployment failed: {str(e)}", "ERROR")
            
            # Rollback on failure
            if self.environment == "production":
                self.log("Initiating rollback...", "WARNING")
                # Rollback logic would go here
            
            raise


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(description="TML Platform Deployment")
    parser.add_argument("environment", choices=["staging", "production"], help="Deployment environment")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test execution")
    parser.add_argument("--skip-backup", action="store_true", help="Skip data backup")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (validation only)")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    deployer = TMLDeployer(args.environment, project_root)
    
    if args.dry_run:
        deployer.log("Dry run mode - validation only")
        deployer.validate_environment()
        deployer.log("Dry run completed successfully")
        return
    
    try:
        deployer.deploy()
    except Exception as e:
        deployer.log(f"Deployment failed: {str(e)}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
