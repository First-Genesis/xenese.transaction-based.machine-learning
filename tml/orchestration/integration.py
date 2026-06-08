"""
Enhanced TML Platform v2.0 - Proto.Actor Integration Module

Complete integration layer that brings together all Proto.Actor components
for production-ready transaction-based machine learning.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import structlog

from .actor_system import ActorMessage
from .actor_system import ActorSystem
from .actor_system import MessagePriority
from .cluster_manager import ScalingPolicy
from .cluster_manager import ScalingRule
from .cluster_manager import TMLClusterManager
from .monitoring import Alert
from .monitoring import AlertSeverity
from .monitoring import TMLMonitoringSystem
from .tml_actors import InheritanceCoordinatorActor
from .tml_actors import ModelActor
from .tml_actors import PhysicsValidatorActor
from .tml_actors import TMLMessageType
from .tml_actors import TransactionData
from .tml_actors import TransactionProcessorActor

logger = structlog.get_logger(__name__)


@dataclass
class TMLPlatformConfig:
    """Configuration for TML platform"""

    node_id: str = "tml-node-01"
    redis_url: str = "redis://localhost:6379"
    cluster_port: int = 8080
    metrics_port: int = 9090
    enable_monitoring: bool = True
    enable_auto_scaling: bool = True
    enable_distributed: bool = True
    transaction_processor_replicas: int = 5
    model_actor_replicas: int = 10
    physics_validator_replicas: int = 2
    batch_size: int = 100
    target_throughput_tps: int = 41000


class TMLPlatform:
    """
    Complete TML Platform with Proto.Actor implementation

    This class provides a high-level interface to the Enhanced TML Platform v2.0
    with full Proto.Actor capabilities including distributed processing,
    high-throughput optimization, advanced fault tolerance, and monitoring.
    """

    def __init__(self, config: Optional[TMLPlatformConfig] = None):
        self.config = config or TMLPlatformConfig()

        # Core components
        self.actor_system: Optional[ActorSystem] = None
        self.cluster_manager: Optional[TMLClusterManager] = None
        self.monitoring_system: Optional[TMLMonitoringSystem] = None

        # Actor references
        self.transaction_processors: List[str] = []
        self.model_actors: List[str] = []
        self.inheritance_coordinator: Optional[str] = None
        self.physics_validator: Optional[str] = None

        # Platform state
        self.is_running = False
        self.startup_time = 0.0

        self.logger = structlog.get_logger(__name__).bind(node_id=self.config.node_id)

    async def start(self) -> None:
        """
        Start the TML platform with all components
        """
        if self.is_running:
            self.logger.warning("Platform already running")
            return

        self.logger.info("Starting Enhanced TML Platform v2.0")

        try:
            # Initialize actor system
            self.actor_system = ActorSystem(
                node_id=self.config.node_id,
                redis_url=self.config.redis_url,
                cluster_port=self.config.cluster_port,
                metrics_port=self.config.metrics_port,
            )
            await self.actor_system.start()

            # Initialize cluster manager if distributed
            if self.config.enable_distributed:
                self.cluster_manager = TMLClusterManager(
                    node_id=self.config.node_id, redis_url=self.config.redis_url
                )
                await self.cluster_manager.start()

                # Setup auto-scaling rules
                if self.config.enable_auto_scaling:
                    await self._setup_auto_scaling()

            # Initialize monitoring if enabled
            if self.config.enable_monitoring:
                self.monitoring_system = TMLMonitoringSystem(
                    service_name=f"tml-platform-{self.config.node_id}",
                    metrics_port=self.config.metrics_port,
                )
                await self.monitoring_system.start()

                # Setup alerts
                await self._setup_alerts()

            # Deploy core actors
            await self._deploy_core_actors()

            self.is_running = True
            self.startup_time = asyncio.get_event_loop().time()

            self.logger.info(
                "Enhanced TML Platform started successfully",
                transaction_processors=len(self.transaction_processors),
                model_actors=len(self.model_actors),
                distributed=self.config.enable_distributed,
                monitoring=self.config.enable_monitoring,
            )

        except Exception as e:
            self.logger.error("Failed to start TML platform", error=str(e))
            raise

    async def stop(self) -> None:
        """
        Stop the TML platform gracefully
        """
        if not self.is_running:
            return

        self.logger.info("Stopping Enhanced TML Platform")

        try:
            # Stop monitoring
            if self.monitoring_system:
                await self.monitoring_system.stop()

            # Stop cluster manager
            if self.cluster_manager:
                await self.cluster_manager.stop()

            # Stop actor system
            if self.actor_system:
                await self.actor_system.stop()

            self.is_running = False

            self.logger.info("Enhanced TML Platform stopped successfully")

        except Exception as e:
            self.logger.error("Error stopping TML platform", error=str(e))

    async def process_transaction(
        self, transaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a single transaction through the TML platform

        Args:
            transaction_data: Transaction data dictionary

        Returns:
            Processing result with model information
        """
        if not self.is_running:
            raise RuntimeError("Platform is not running")

        try:
            # Create transaction message
            transaction = TransactionData(
                transaction_id=transaction_data.get("id", ""),
                data=transaction_data.get("data", {}),
                timestamp=transaction_data.get(
                    "timestamp", asyncio.get_event_loop().time()
                ),
                source=transaction_data.get("source", "api"),
                metadata=transaction_data.get("metadata", {}),
            )

            # Select transaction processor (round-robin)
            processor_id = self.transaction_processors[
                hash(transaction.transaction_id) % len(self.transaction_processors)
            ]

            # Send to processor
            processor_ref = self.actor_system.get_actor_ref(processor_id)
            if not processor_ref:
                raise RuntimeError(f"Transaction processor {processor_id} not found")

            # Create message
            message = ActorMessage(
                message_type=TMLMessageType.PROCESS_TRANSACTION.value,
                payload={"transaction": transaction.__dict__},
                priority=MessagePriority.HIGH,
            )

            # Process with timeout
            result = await processor_ref.ask(message, timeout=30.0)

            return {
                "status": "success",
                "transaction_id": transaction.transaction_id,
                "result": result,
            }

        except Exception as e:
            self.logger.error(
                "Transaction processing failed",
                transaction_id=transaction_data.get("id"),
                error=str(e),
            )
            return {
                "status": "failed",
                "transaction_id": transaction_data.get("id"),
                "error": str(e),
            }

    async def batch_process_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of transactions for high throughput

        Args:
            transactions: List of transaction data dictionaries

        Returns:
            List of processing results
        """
        if not self.is_running:
            raise RuntimeError("Platform is not running")

        # Process transactions in parallel
        tasks = [self.process_transaction(transaction) for transaction in transactions]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "status": "failed",
                        "transaction_id": transactions[i].get("id"),
                        "error": str(result),
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def get_platform_status(self) -> Dict[str, Any]:
        """
        Get comprehensive platform status

        Returns:
            Platform status information
        """
        status = {
            "is_running": self.is_running,
            "node_id": self.config.node_id,
            "uptime": (
                asyncio.get_event_loop().time() - self.startup_time
                if self.is_running
                else 0
            ),
        }

        if self.actor_system:
            status["actor_system"] = {
                "total_actors": len(self.actor_system.actors),
                "transaction_processors": len(self.transaction_processors),
                "model_actors": len(self.model_actors),
            }

        if self.cluster_manager:
            status["cluster"] = await self.cluster_manager.get_cluster_status()

        if self.monitoring_system:
            status["monitoring"] = await self.monitoring_system.get_system_status()

        return status

    async def _deploy_core_actors(self) -> None:
        """
        Deploy core TML actors
        """
        # Deploy transaction processors
        for i in range(self.config.transaction_processor_replicas):
            actor_id = f"transaction_processor_{i}_{self.config.node_id}"
            await self.actor_system.create_actor(TransactionProcessorActor, actor_id)
            self.transaction_processors.append(actor_id)

        # Deploy model actors (pre-created pool)
        for i in range(self.config.model_actor_replicas):
            actor_id = f"model_actor_pool_{i}_{self.config.node_id}"
            await self.actor_system.create_actor(ModelActor, actor_id)
            self.model_actors.append(actor_id)

        # Deploy single inheritance coordinator
        self.inheritance_coordinator = f"inheritance_coordinator_{self.config.node_id}"
        await self.actor_system.create_actor(
            InheritanceCoordinatorActor, self.inheritance_coordinator
        )

        # Deploy physics validators
        physics_validators = []
        for i in range(self.config.physics_validator_replicas):
            actor_id = f"physics_validator_{i}_{self.config.node_id}"
            await self.actor_system.create_actor(PhysicsValidatorActor, actor_id)
            physics_validators.append(actor_id)

        self.physics_validator = physics_validators[0] if physics_validators else None

        self.logger.info(
            "Core actors deployed",
            transaction_processors=len(self.transaction_processors),
            model_actors=len(self.model_actors),
            physics_validators=len(physics_validators),
        )

    async def _setup_auto_scaling(self) -> None:
        """
        Setup auto-scaling rules for the platform
        """
        if not self.cluster_manager:
            return

        # Throughput-based scaling
        throughput_rule = ScalingRule(
            metric_name="throughput_tps",
            threshold=self.config.target_throughput_tps * 0.8,
            comparison="less_than",
            action="scale_up",
            cooldown_period=300,
            scale_factor=1.5,
        )
        self.cluster_manager.add_scaling_rule(throughput_rule)

        # CPU-based scaling
        cpu_rule = ScalingRule(
            metric_name="cpu_usage",
            threshold=80.0,
            comparison="greater_than",
            action="scale_up",
            cooldown_period=180,
            scale_factor=1.3,
        )
        self.cluster_manager.add_scaling_rule(cpu_rule)

        # Memory-based scaling
        memory_rule = ScalingRule(
            metric_name="memory_usage",
            threshold=85.0,
            comparison="greater_than",
            action="scale_up",
            cooldown_period=180,
            scale_factor=1.3,
        )
        self.cluster_manager.add_scaling_rule(memory_rule)

        # Scale down rules
        scale_down_rule = ScalingRule(
            metric_name="cpu_usage",
            threshold=30.0,
            comparison="less_than",
            action="scale_down",
            cooldown_period=600,
            scale_factor=0.7,
        )
        self.cluster_manager.add_scaling_rule(scale_down_rule)

        self.logger.info("Auto-scaling rules configured", rules_count=4)

    async def _setup_alerts(self) -> None:
        """
        Setup monitoring alerts for the platform
        """
        if not self.monitoring_system:
            return

        # High latency alert
        latency_alert = Alert(
            alert_id="high_latency",
            name="High Transaction Latency",
            description="Transaction processing latency above threshold",
            severity=AlertSeverity.WARNING,
            metric_name="tml_transaction_processing_seconds",
            condition="greater_than",
            threshold=1.0,  # 1 second
            actions=["log", "email"],
        )
        self.monitoring_system.alert_manager.add_alert(latency_alert)

        # Low throughput alert
        throughput_alert = Alert(
            alert_id="low_throughput",
            name="Low Throughput",
            description="Throughput below target",
            severity=AlertSeverity.WARNING,
            metric_name="tml_throughput_transactions_per_second",
            condition="less_than",
            threshold=self.config.target_throughput_tps * 0.5,
            actions=["log", "slack"],
        )
        self.monitoring_system.alert_manager.add_alert(throughput_alert)

        # Actor failure alert
        actor_failure_alert = Alert(
            alert_id="actor_failures",
            name="High Actor Failure Rate",
            description="Actor failure rate above threshold",
            severity=AlertSeverity.ERROR,
            metric_name="tml_actor_errors_total",
            condition="greater_than",
            threshold=100,  # 100 errors
            duration=60,  # in 60 seconds
            actions=["log", "email", "slack"],
        )
        self.monitoring_system.alert_manager.add_alert(actor_failure_alert)

        self.logger.info("Monitoring alerts configured", alerts_count=3)


class TMLPlatformBuilder:
    """
    Builder pattern for TML Platform configuration
    """

    def __init__(self):
        self.config = TMLPlatformConfig()

    def with_node_id(self, node_id: str) -> "TMLPlatformBuilder":
        self.config.node_id = node_id
        return self

    def with_redis(self, redis_url: str) -> "TMLPlatformBuilder":
        self.config.redis_url = redis_url
        return self

    def with_cluster(self, port: int = 8080) -> "TMLPlatformBuilder":
        self.config.cluster_port = port
        self.config.enable_distributed = True
        return self

    def with_monitoring(self, metrics_port: int = 9090) -> "TMLPlatformBuilder":
        self.config.metrics_port = metrics_port
        self.config.enable_monitoring = True
        return self

    def with_auto_scaling(self) -> "TMLPlatformBuilder":
        self.config.enable_auto_scaling = True
        return self

    def with_replicas(
        self,
        transaction_processors: int = 5,
        model_actors: int = 10,
        physics_validators: int = 2,
    ) -> "TMLPlatformBuilder":
        self.config.transaction_processor_replicas = transaction_processors
        self.config.model_actor_replicas = model_actors
        self.config.physics_validator_replicas = physics_validators
        return self

    def with_target_throughput(self, tps: int) -> "TMLPlatformBuilder":
        self.config.target_throughput_tps = tps
        return self

    def build(self) -> TMLPlatform:
        return TMLPlatform(self.config)


async def quick_start():
    """
    Quick start example for the TML Platform
    """
    # Build platform with default configuration
    platform = (
        TMLPlatformBuilder()
        .with_node_id("tml-demo-node")
        .with_redis("redis://localhost:6379")
        .with_cluster(8080)
        .with_monitoring(9090)
        .with_auto_scaling()
        .with_replicas(5, 10, 2)
        .with_target_throughput(41000)
        .build()
    )

    try:
        # Start platform
        await platform.start()

        # Process some sample transactions
        sample_transactions = [
            {
                "id": f"tx_{i}",
                "data": {
                    "x_coord": i * 10,
                    "y_coord": i * 5,
                    "thickness": 19.5 + (i * 0.1),
                    "temperature": 25.0,
                },
                "source": "pipeline_sensor",
                "metadata": {"sensor_id": f"sensor_{i % 10}"},
            }
            for i in range(100)
        ]

        # Batch process transactions
        results = await platform.batch_process_transactions(sample_transactions)

        # Print results
        successful = sum(1 for r in results if r["status"] == "success")
        logger.info(
            "Quick start processing complete", total=len(results), successful=successful
        )

        # Get platform status
        status = await platform.get_platform_status()
        logger.info("Platform status", status=status)

        # Keep running for monitoring
        await asyncio.sleep(60)

    finally:
        # Stop platform
        await platform.stop()


if __name__ == "__main__":
    # Run quick start example
    asyncio.run(quick_start())
