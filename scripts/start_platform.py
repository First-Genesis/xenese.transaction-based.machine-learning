#!/usr/bin/env python3
"""Script to start the TML platform components."""

import asyncio
import subprocess
import sys
import time
import signal
from pathlib import Path
from typing import List, Dict, Any

import click
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tml.core.config import config
from tml.serving.api_server import run_server
from tml.ingestion.kafka_consumer import TransactionProcessor


class PlatformManager:
    """Manager for TML platform components."""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
    
    def start_infrastructure(self):
        """Start infrastructure services using Docker Compose."""
        logger.info("Starting infrastructure services...")
        
        docker_compose_path = project_root / "docker" / "docker-compose.yml"
        
        try:
            result = subprocess.run([
                "docker-compose", "-f", str(docker_compose_path), "up", "-d"
            ], check=True, capture_output=True, text=True)
            
            logger.info("Infrastructure services started successfully")
            logger.info("Waiting for services to be ready...")
            time.sleep(30)  # Wait for services to initialize
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start infrastructure: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Docker Compose not found. Please install Docker and Docker Compose.")
            return False
    
    def stop_infrastructure(self):
        """Stop infrastructure services."""
        logger.info("Stopping infrastructure services...")
        
        docker_compose_path = project_root / "docker" / "docker-compose.yml"
        
        try:
            subprocess.run([
                "docker-compose", "-f", str(docker_compose_path), "down"
            ], check=True)
            
            logger.info("Infrastructure services stopped")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop infrastructure: {e}")
            return False
    
    def start_api_server(self, port: int = 8000):
        """Start the API server."""
        logger.info(f"Starting API server on port {port}...")
        
        try:
            # Start API server in a subprocess
            cmd = [
                sys.executable, "-m", "uvicorn",
                "tml.serving.api_server:app",
                "--host", "0.0.0.0",
                "--port", str(port),
                "--reload" if config.debug else "--no-reload"
            ]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["api_server"] = process
            logger.info(f"API server started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            return False
    
    def start_kafka_processor(self):
        """Start the Kafka transaction processor."""
        logger.info("Starting Kafka transaction processor...")
        
        try:
            cmd = [
                sys.executable, "-c",
                "from tml.ingestion.kafka_consumer import TransactionProcessor; "
                "processor = TransactionProcessor(); processor.start()"
            ]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["kafka_processor"] = process
            logger.info(f"Kafka processor started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Kafka processor: {e}")
            return False
    
    def start_flink_job(self):
        """Start the Flink processing job."""
        logger.info("Starting Flink processing job...")
        
        try:
            cmd = [
                sys.executable, "-c",
                "from tml.ingestion.flink_processor import FlinkTransactionProcessor; "
                "processor = FlinkTransactionProcessor(); processor.run()"
            ]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["flink_job"] = process
            logger.info(f"Flink job started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Flink job: {e}")
            return False
    
    def check_health(self) -> Dict[str, bool]:
        """Check health of all components."""
        health_status = {}
        
        # Check processes
        for name, process in self.processes.items():
            if process.poll() is None:  # Process is running
                health_status[name] = True
            else:
                health_status[name] = False
                logger.warning(f"Process {name} is not running")
        
        return health_status
    
    def stop_all(self):
        """Stop all platform components."""
        logger.info("Stopping all platform components...")
        
        # Stop processes
        for name, process in self.processes.items():
            try:
                logger.info(f"Stopping {name}...")
                process.terminate()
                process.wait(timeout=10)
                logger.info(f"Stopped {name}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {name}...")
                process.kill()
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        self.processes.clear()
        self.running = False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop_all()
        sys.exit(0)


@click.group()
def cli():
    """TML Platform Management CLI."""
    pass


@cli.command()
@click.option('--with-infra', is_flag=True, help='Start infrastructure services')
@click.option('--api-port', default=8000, help='API server port')
@click.option('--with-kafka', is_flag=True, help='Start Kafka processor')
@click.option('--with-flink', is_flag=True, help='Start Flink job')
def start(with_infra: bool, api_port: int, with_kafka: bool, with_flink: bool):
    """Start TML platform components."""
    manager = PlatformManager()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, manager.signal_handler)
    signal.signal(signal.SIGTERM, manager.signal_handler)
    
    try:
        # Start infrastructure if requested
        if with_infra:
            if not manager.start_infrastructure():
                logger.error("Failed to start infrastructure")
                return
        
        # Start API server
        if not manager.start_api_server(api_port):
            logger.error("Failed to start API server")
            return
        
        # Start Kafka processor if requested
        if with_kafka:
            if not manager.start_kafka_processor():
                logger.error("Failed to start Kafka processor")
                return
        
        # Start Flink job if requested
        if with_flink:
            if not manager.start_flink_job():
                logger.error("Failed to start Flink job")
                return
        
        manager.running = True
        logger.info("TML Platform started successfully!")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running and monitor health
        while manager.running:
            time.sleep(10)
            health = manager.check_health()
            
            # Log health status periodically
            if any(not status for status in health.values()):
                logger.warning(f"Health check: {health}")
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Platform error: {e}")
    finally:
        manager.stop_all()


@cli.command()
def stop():
    """Stop TML platform components."""
    manager = PlatformManager()
    manager.stop_infrastructure()
    logger.info("Platform stopped")


@cli.command()
def status():
    """Check platform status."""
    # This is a simplified status check
    # In practice, you'd check actual service health
    
    services = [
        ("API Server", "http://localhost:8000/health"),
        ("Kafka", "localhost:9092"),
        ("Redis", "localhost:6379"),
        ("Cassandra", "localhost:9042"),
        ("MLflow", "http://localhost:5000"),
        ("Prometheus", "http://localhost:9090"),
        ("Grafana", "http://localhost:3000"),
    ]
    
    logger.info("TML Platform Status:")
    logger.info("-" * 40)
    
    for service_name, endpoint in services:
        # Simple check - in practice, implement proper health checks
        logger.info(f"{service_name:15} | {endpoint}")


@cli.command()
def logs():
    """Show platform logs."""
    docker_compose_path = project_root / "docker" / "docker-compose.yml"
    
    try:
        subprocess.run([
            "docker-compose", "-f", str(docker_compose_path), "logs", "-f"
        ])
    except KeyboardInterrupt:
        logger.info("Stopped following logs")


@cli.command()
@click.argument('count', default=10)
def demo(count: int):
    """Run a demo with synthetic transactions."""
    logger.info(f"Running demo with {count} transactions...")
    
    # Import here to avoid circular imports
    from tml.ingestion.kafka_producer import TransactionProducer, TransactionEventGenerator
    
    try:
        producer = TransactionProducer()
        generator = TransactionEventGenerator()
        
        # Generate and send transactions
        events = generator.generate_batch(count)
        success_count = producer.send_batch_transactions(events)
        
        logger.info(f"Demo completed: {success_count}/{count} transactions sent")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    finally:
        producer.close()


if __name__ == "__main__":
    cli()
