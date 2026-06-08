"""
Enhanced TML Platform v2.0 - Proto.Actor Deployment Script

Production deployment script for the complete TML Proto.Actor system.
"""

import asyncio
import click
import yaml
import os
import sys
from typing import Dict, Any, Optional
import structlog

from .integration import TMLPlatform, TMLPlatformBuilder

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG = {
    "node_id": "tml-node-01",
    "redis_url": "redis://localhost:6379",
    "cluster_port": 8080,
    "metrics_port": 9090,
    "enable_monitoring": True,
    "enable_auto_scaling": True,
    "enable_distributed": True,
    "transaction_processor_replicas": 10,
    "model_actor_replicas": 20,
    "physics_validator_replicas": 5,
    "batch_size": 100,
    "target_throughput_tps": 41000,
}


class TMLDeployment:
    """TML Platform deployment manager"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.platform: Optional[TMLPlatform] = None

    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if config_file and os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
                logger.info("Configuration loaded from file", config_file=config_file)
        else:
            config = DEFAULT_CONFIG.copy()
            logger.info("Using default configuration")

        # Override with environment variables
        env_mapping = {
            "TML_NODE_ID": "node_id",
            "TML_REDIS_URL": "redis_url",
            "TML_CLUSTER_PORT": "cluster_port",
            "TML_METRICS_PORT": "metrics_port",
            "TML_TARGET_TPS": "target_throughput_tps",
        }

        for env_var, config_key in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # Convert to appropriate type
                if config_key.endswith("_port") or config_key.endswith("_tps"):
                    value = int(value)
                elif config_key.startswith("enable_"):
                    value = value.lower() in ["true", "1", "yes"]

                config[config_key] = value
                logger.info(
                    f"Configuration overridden by environment",
                    key=config_key,
                    value=value,
                )

        return config

    async def deploy(self):
        """Deploy TML platform with configured settings"""
        logger.info("Starting TML Platform deployment", config=self.config)

        try:
            # Build platform
            builder = TMLPlatformBuilder()
            builder.with_node_id(self.config["node_id"])
            builder.with_redis(self.config["redis_url"])

            if self.config["enable_distributed"]:
                builder.with_cluster(self.config["cluster_port"])

            if self.config["enable_monitoring"]:
                builder.with_monitoring(self.config["metrics_port"])

            if self.config["enable_auto_scaling"]:
                builder.with_auto_scaling()

            builder.with_replicas(
                self.config["transaction_processor_replicas"],
                self.config["model_actor_replicas"],
                self.config["physics_validator_replicas"],
            )

            builder.with_target_throughput(self.config["target_throughput_tps"])

            self.platform = builder.build()

            # Start platform
            await self.platform.start()

            logger.info(
                "TML Platform deployed successfully",
                node_id=self.config["node_id"],
                target_tps=self.config["target_throughput_tps"],
            )

            # Print status
            status = await self.platform.get_platform_status()
            logger.info("Platform status", **status)

            if self.config["enable_monitoring"]:
                logger.info(
                    "Monitoring dashboard available",
                    url=f"http://localhost:{self.config['metrics_port']}",
                )

            return self.platform

        except Exception as e:
            logger.error("Deployment failed", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Perform platform health check"""
        if not self.platform or not self.platform.is_running:
            return False

        try:
            # Test transaction processing
            test_transaction = {
                "id": "health_check_tx",
                "data": {"x_coord": 100, "y_coord": 200, "thickness": 20.0},
                "source": "health_check",
            }

            result = await self.platform.process_transaction(test_transaction)

            if result["status"] != "success":
                logger.warning("Health check transaction failed", result=result)
                return False

            # Check platform status
            status = await self.platform.get_platform_status()

            # Verify components
            if status["actor_system"]["transaction_processors"] == 0:
                logger.warning("No transaction processors available")
                return False

            logger.info("Health check passed")
            return True

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False

    async def shutdown(self):
        """Gracefully shutdown the platform"""
        if self.platform:
            logger.info("Shutting down TML Platform")
            await self.platform.stop()
            logger.info("TML Platform shutdown complete")


@click.group()
def cli():
    """TML Platform deployment CLI"""
    pass


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
@click.option("--node-id", "-n", help="Node ID")
@click.option("--redis-url", "-r", help="Redis URL")
@click.option("--target-tps", "-t", type=int, help="Target throughput (TPS)")
def deploy(config, node_id, redis_url, target_tps):
    """Deploy TML Platform"""

    # Create deployment
    deployment = TMLDeployment(config)

    # Override with CLI arguments
    if node_id:
        deployment.config["node_id"] = node_id
    if redis_url:
        deployment.config["redis_url"] = redis_url
    if target_tps:
        deployment.config["target_throughput_tps"] = target_tps

    # Run deployment
    async def run():
        try:
            await deployment.deploy()

            # Keep running
            logger.info("Platform is running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await deployment.shutdown()

    asyncio.run(run())


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
def health(config):
    """Check platform health"""

    deployment = TMLDeployment(config)

    async def check():
        await deployment.deploy()
        is_healthy = await deployment.health_check()
        await deployment.shutdown()

        if is_healthy:
            click.echo("Platform is healthy ✓")
            sys.exit(0)
        else:
            click.echo("Platform health check failed ✗")
            sys.exit(1)

    asyncio.run(check())


@cli.command()
def generate_config():
    """Generate sample configuration file"""

    sample_config = """# TML Platform Configuration
node_id: tml-prod-node-01
redis_url: redis://localhost:6379

# Cluster Settings
cluster_port: 8080
enable_distributed: true

# Monitoring
metrics_port: 9090
enable_monitoring: true

# Auto-scaling
enable_auto_scaling: true
target_throughput_tps: 41000

# Actor Replicas
transaction_processor_replicas: 10
model_actor_replicas: 20
physics_validator_replicas: 5

# Processing Settings
batch_size: 100

# Advanced Settings
scaling_rules:
  - metric: throughput_tps
    threshold: 30000
    action: scale_up
    scale_factor: 1.5
    
  - metric: cpu_usage
    threshold: 80
    action: scale_up
    scale_factor: 1.3
    
  - metric: cpu_usage
    threshold: 30
    action: scale_down
    scale_factor: 0.7

alerts:
  - name: Low Throughput
    metric: throughput_tps
    threshold: 20000
    severity: warning
    
  - name: High Error Rate
    metric: error_rate
    threshold: 0.05
    severity: critical
"""

    with open("tml-platform-config.yaml", "w") as f:
        f.write(sample_config)

    click.echo("Sample configuration generated: tml-platform-config.yaml")


@cli.command()
@click.option(
    "--transactions",
    "-t",
    type=int,
    default=1000,
    help="Number of transactions to process",
)
@click.option(
    "--batch-size", "-b", type=int, default=100, help="Batch size for processing"
)
def benchmark(transactions, batch_size):
    """Run performance benchmark"""

    import time
    import random

    async def run_benchmark():
        # Deploy platform with optimized settings
        deployment = TMLDeployment()
        deployment.config["transaction_processor_replicas"] = 20
        deployment.config["model_actor_replicas"] = 40

        platform = await deployment.deploy()

        # Generate test transactions
        test_transactions = [
            {
                "id": f"bench_tx_{i}",
                "data": {
                    "x_coord": random.randint(0, 3700),
                    "y_coord": random.randint(0, 880),
                    "thickness": 15.0 + random.random() * 10,
                    "temperature": 20.0 + random.random() * 10,
                },
                "source": "benchmark",
            }
            for i in range(transactions)
        ]

        logger.info(
            "Starting benchmark", transactions=transactions, batch_size=batch_size
        )

        # Process transactions
        start_time = time.time()

        for i in range(0, transactions, batch_size):
            batch = test_transactions[i : i + batch_size]
            results = await platform.batch_process_transactions(batch)

            successful = sum(1 for r in results if r["status"] == "success")
            if successful != len(batch):
                logger.warning(
                    "Some transactions failed",
                    batch_size=len(batch),
                    successful=successful,
                )

        end_time = time.time()

        # Calculate metrics
        duration = end_time - start_time
        throughput = transactions / duration

        logger.info(
            "Benchmark complete",
            transactions=transactions,
            duration_seconds=round(duration, 2),
            throughput_tps=round(throughput, 2),
            avg_latency_ms=round((duration / transactions) * 1000, 2),
        )

        # Cleanup
        await deployment.shutdown()

    asyncio.run(run_benchmark())


if __name__ == "__main__":
    cli()
