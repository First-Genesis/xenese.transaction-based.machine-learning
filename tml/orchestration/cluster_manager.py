"""
Enhanced TML Platform v2.0 - Cluster Management System

Production-ready cluster management with auto-scaling, service discovery,
and distributed coordination for high-throughput TML processing.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import aioredis
import consul

try:
    import etcd3

    ETCD_AVAILABLE = True
except ImportError:
    ETCD_AVAILABLE = False
    etcd3 = None
from kubernetes import client, config
import docker
import structlog

from .actor_system import ActorSystem, ClusterNode
from .tml_actors import (
    TransactionProcessorActor,
    ModelActor,
    InheritanceCoordinatorActor,
    PhysicsValidatorActor,
    ClusterManagerActor,
)

logger = structlog.get_logger(__name__)


class DeploymentStrategy(Enum):
    """Deployment strategies for TML actors"""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    AFFINITY_BASED = "affinity_based"
    GEOGRAPHIC = "geographic"


class ScalingPolicy(Enum):
    """Auto-scaling policies"""

    CPU_BASED = "cpu_based"
    MEMORY_BASED = "memory_based"
    THROUGHPUT_BASED = "throughput_based"
    QUEUE_LENGTH_BASED = "queue_length_based"
    CUSTOM = "custom"


@dataclass
class ServiceEndpoint:
    """Service endpoint information"""

    service_name: str
    node_id: str
    address: str
    port: int
    protocol: str = "http"
    health_check_path: str = "/health"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScalingRule:
    """Auto-scaling rule configuration"""

    metric_name: str
    threshold: float
    comparison: str  # "greater_than", "less_than"
    action: str  # "scale_up", "scale_down"
    cooldown_period: int = 300  # seconds
    scale_factor: float = 1.5


class ServiceDiscovery:
    """Service discovery and registration"""

    def __init__(self, backend: str = "redis", **kwargs):
        self.backend = backend
        self.redis_client: Optional[aioredis.Redis] = None
        self.consul_client: Optional[consul.Consul] = None
        self.etcd_client: Optional[etcd3.Etcd3Client] = None
        self.services: Dict[str, List[ServiceEndpoint]] = {}

        if backend == "redis":
            self.redis_client = aioredis.from_url(
                kwargs.get("redis_url", "redis://localhost:6379")
            )
        elif backend == "consul":
            self.consul_client = consul.Consul(
                host=kwargs.get("consul_host", "localhost"),
                port=kwargs.get("consul_port", 8500),
            )
        elif backend == "etcd":
            if ETCD_AVAILABLE:
                self.etcd_client = etcd3.client(
                    host=kwargs.get("etcd_host", "localhost"),
                    port=kwargs.get("etcd_port", 2379),
                )
            else:
                logger.warning(
                    "etcd backend requested but etcd3 module not available, falling back to redis"
                )
                self.backend = "redis"

    async def register_service(self, endpoint: ServiceEndpoint) -> None:
        """Register a service endpoint"""
        try:
            if self.backend == "redis" and self.redis_client:
                service_key = f"services:{endpoint.service_name}"
                endpoint_data = json.dumps(endpoint.__dict__)
                await self.redis_client.sadd(service_key, endpoint_data)
                await self.redis_client.expire(service_key, 300)  # 5 minute TTL

            elif self.backend == "consul" and self.consul_client:
                self.consul_client.agent.service.register(
                    name=endpoint.service_name,
                    service_id=f"{endpoint.service_name}-{endpoint.node_id}",
                    address=endpoint.address,
                    port=endpoint.port,
                    check=consul.Check.http(
                        f"{endpoint.protocol}://{endpoint.address}:{endpoint.port}{endpoint.health_check_path}",
                        interval="10s",
                    ),
                )

            elif self.backend == "etcd" and self.etcd_client:
                service_key = f"/services/{endpoint.service_name}/{endpoint.node_id}"
                endpoint_data = json.dumps(endpoint.__dict__)
                self.etcd_client.put(service_key, endpoint_data, lease=300)

            # Update local cache
            if endpoint.service_name not in self.services:
                self.services[endpoint.service_name] = []
            self.services[endpoint.service_name].append(endpoint)

            logger.info(
                "Service registered",
                service=endpoint.service_name,
                node=endpoint.node_id,
                address=f"{endpoint.address}:{endpoint.port}",
            )

        except Exception as e:
            logger.error(
                "Service registration failed",
                service=endpoint.service_name,
                error=str(e),
            )

    async def discover_services(self, service_name: str) -> List[ServiceEndpoint]:
        """Discover service endpoints"""
        try:
            endpoints = []

            if self.backend == "redis" and self.redis_client:
                service_key = f"services:{service_name}"
                endpoint_data_list = await self.redis_client.smembers(service_key)
                for endpoint_data in endpoint_data_list:
                    endpoint_dict = json.loads(endpoint_data)
                    endpoints.append(ServiceEndpoint(**endpoint_dict))

            elif self.backend == "consul" and self.consul_client:
                _, services = self.consul_client.health.service(
                    service_name, passing=True
                )
                for service in services:
                    endpoint = ServiceEndpoint(
                        service_name=service_name,
                        node_id=service["Service"]["ID"],
                        address=service["Service"]["Address"],
                        port=service["Service"]["Port"],
                    )
                    endpoints.append(endpoint)

            elif self.backend == "etcd" and self.etcd_client:
                for value, _ in self.etcd_client.get_prefix(
                    f"/services/{service_name}/"
                ):
                    endpoint_dict = json.loads(value)
                    endpoints.append(ServiceEndpoint(**endpoint_dict))

            return endpoints

        except Exception as e:
            logger.error("Service discovery failed", service=service_name, error=str(e))
            return []

    async def unregister_service(self, service_name: str, node_id: str) -> None:
        """Unregister a service endpoint"""
        try:
            if self.backend == "consul" and self.consul_client:
                self.consul_client.agent.service.deregister(f"{service_name}-{node_id}")

            # Remove from local cache
            if service_name in self.services:
                self.services[service_name] = [
                    ep for ep in self.services[service_name] if ep.node_id != node_id
                ]

            logger.info("Service unregistered", service=service_name, node=node_id)

        except Exception as e:
            logger.error(
                "Service unregistration failed",
                service=service_name,
                node=node_id,
                error=str(e),
            )


class AutoScaler:
    """Automatic scaling based on metrics and policies"""

    def __init__(self, cluster_manager: "TMLClusterManager"):
        self.cluster_manager = cluster_manager
        self.scaling_rules: List[ScalingRule] = []
        self.last_scaling_action: Dict[str, float] = {}
        self.is_running = False

    def add_scaling_rule(self, rule: ScalingRule) -> None:
        """Add auto-scaling rule"""
        self.scaling_rules.append(rule)
        logger.info(
            "Scaling rule added",
            metric=rule.metric_name,
            threshold=rule.threshold,
            action=rule.action,
        )

    async def start(self) -> None:
        """Start auto-scaling monitoring"""
        self.is_running = True
        asyncio.create_task(self._scaling_loop())
        logger.info("Auto-scaler started")

    async def stop(self) -> None:
        """Stop auto-scaling"""
        self.is_running = False
        logger.info("Auto-scaler stopped")

    async def _scaling_loop(self) -> None:
        """Main auto-scaling loop"""
        while self.is_running:
            try:
                await self._evaluate_scaling_rules()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error("Auto-scaling evaluation failed", error=str(e))

    async def _evaluate_scaling_rules(self) -> None:
        """Evaluate all scaling rules"""
        current_time = time.time()

        for rule in self.scaling_rules:
            # Check cooldown period
            last_action_time = self.last_scaling_action.get(rule.metric_name, 0)
            if current_time - last_action_time < rule.cooldown_period:
                continue

            # Get current metric value
            metric_value = await self._get_metric_value(rule.metric_name)
            if metric_value is None:
                continue

            # Evaluate rule
            should_scale = False
            if rule.comparison == "greater_than" and metric_value > rule.threshold:
                should_scale = True
            elif rule.comparison == "less_than" and metric_value < rule.threshold:
                should_scale = True

            if should_scale:
                await self._execute_scaling_action(rule)
                self.last_scaling_action[rule.metric_name] = current_time

    async def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """Get current value of a metric"""
        try:
            if metric_name == "cpu_usage":
                return await self._get_cluster_cpu_usage()
            elif metric_name == "memory_usage":
                return await self._get_cluster_memory_usage()
            elif metric_name == "throughput_tps":
                return await self._get_cluster_throughput()
            elif metric_name == "queue_length":
                return await self._get_average_queue_length()
            else:
                return None
        except Exception as e:
            logger.error("Failed to get metric value", metric=metric_name, error=str(e))
            return None

    async def _get_cluster_cpu_usage(self) -> float:
        """Get average CPU usage across cluster"""
        total_cpu = 0.0
        node_count = 0

        for node in self.cluster_manager.cluster_nodes.values():
            if node.is_healthy():
                total_cpu += node.load_factor
                node_count += 1

        return total_cpu / node_count if node_count > 0 else 0.0

    async def _get_cluster_memory_usage(self) -> float:
        """Get average memory usage across cluster"""
        # Implement memory usage collection
        return 50.0  # Placeholder

    async def _get_cluster_throughput(self) -> float:
        """Get cluster-wide throughput"""
        # Implement throughput calculation
        return 25000.0  # Placeholder

    async def _get_average_queue_length(self) -> float:
        """Get average queue length across actors"""
        # Implement queue length monitoring
        return 100.0  # Placeholder

    async def _execute_scaling_action(self, rule: ScalingRule) -> None:
        """Execute scaling action"""
        try:
            if rule.action == "scale_up":
                await self.cluster_manager.scale_up(rule.scale_factor)
            elif rule.action == "scale_down":
                await self.cluster_manager.scale_down(rule.scale_factor)

            logger.info(
                "Scaling action executed",
                action=rule.action,
                metric=rule.metric_name,
                scale_factor=rule.scale_factor,
            )

        except Exception as e:
            logger.error("Scaling action failed", action=rule.action, error=str(e))


class ContainerOrchestrator:
    """Container orchestration for TML actors"""

    def __init__(self, orchestrator_type: str = "docker"):
        self.orchestrator_type = orchestrator_type
        self.docker_client = None
        self.k8s_client = None

        if orchestrator_type == "docker":
            self.docker_client = docker.from_env()
        elif orchestrator_type == "kubernetes":
            try:
                config.load_incluster_config()
            except:
                config.load_kube_config()
            self.k8s_client = client.AppsV1Api()

    async def deploy_actor_service(
        self,
        service_name: str,
        actor_type: str,
        replicas: int = 1,
        resources: Dict[str, Any] = None,
    ) -> List[str]:
        """Deploy actor service with specified replicas"""
        deployed_instances = []

        try:
            if self.orchestrator_type == "docker":
                deployed_instances = await self._deploy_docker_containers(
                    service_name, actor_type, replicas, resources
                )
            elif self.orchestrator_type == "kubernetes":
                deployed_instances = await self._deploy_k8s_deployment(
                    service_name, actor_type, replicas, resources
                )

            logger.info(
                "Actor service deployed",
                service=service_name,
                replicas=replicas,
                instances=len(deployed_instances),
            )

            return deployed_instances

        except Exception as e:
            logger.error(
                "Actor service deployment failed", service=service_name, error=str(e)
            )
            return []

    async def _deploy_docker_containers(
        self,
        service_name: str,
        actor_type: str,
        replicas: int,
        resources: Dict[str, Any],
    ) -> List[str]:
        """Deploy Docker containers for actor service"""
        container_ids = []

        for i in range(replicas):
            container_name = f"{service_name}-{i}"

            # Container configuration
            container_config = {
                "image": "tml-platform:latest",
                "name": container_name,
                "environment": {
                    "ACTOR_TYPE": actor_type,
                    "ACTOR_ID": f"{actor_type}_{uuid.uuid4()}",
                    "CLUSTER_MODE": "true",
                },
                "ports": {"8080/tcp": None},
                "restart_policy": {"Name": "always"},
            }

            if resources:
                if "cpu_limit" in resources:
                    container_config["cpu_quota"] = int(resources["cpu_limit"] * 100000)
                if "memory_limit" in resources:
                    container_config["mem_limit"] = resources["memory_limit"]

            # Deploy container
            container = self.docker_client.containers.run(
                detach=True, **container_config
            )

            container_ids.append(container.id)

        return container_ids

    async def _deploy_k8s_deployment(
        self,
        service_name: str,
        actor_type: str,
        replicas: int,
        resources: Dict[str, Any],
    ) -> List[str]:
        """Deploy Kubernetes deployment for actor service"""
        # Kubernetes deployment manifest
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(name=service_name),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector=client.V1LabelSelector(match_labels={"app": service_name}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": service_name}),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name=service_name,
                                image="tml-platform:latest",
                                env=[
                                    client.V1EnvVar(
                                        name="ACTOR_TYPE", value=actor_type
                                    ),
                                    client.V1EnvVar(name="CLUSTER_MODE", value="true"),
                                ],
                                ports=[client.V1ContainerPort(container_port=8080)],
                                resources=client.V1ResourceRequirements(
                                    limits=resources or {"cpu": "1", "memory": "1Gi"},
                                    requests=resources
                                    or {"cpu": "0.5", "memory": "512Mi"},
                                ),
                            )
                        ]
                    ),
                ),
            ),
        )

        # Deploy to Kubernetes
        self.k8s_client.create_namespaced_deployment(
            namespace="default", body=deployment
        )

        return [f"{service_name}-deployment"]

    async def scale_service(self, service_name: str, target_replicas: int) -> bool:
        """Scale service to target replica count"""
        try:
            if self.orchestrator_type == "kubernetes":
                # Scale Kubernetes deployment
                self.k8s_client.patch_namespaced_deployment_scale(
                    name=service_name,
                    namespace="default",
                    body=client.V1Scale(
                        spec=client.V1ScaleSpec(replicas=target_replicas)
                    ),
                )

                logger.info(
                    "Service scaled", service=service_name, replicas=target_replicas
                )
                return True

        except Exception as e:
            logger.error("Service scaling failed", service=service_name, error=str(e))
            return False


class TMLClusterManager:
    """Complete TML cluster management system"""

    def __init__(
        self,
        node_id: str,
        redis_url: str = "redis://localhost:6379",
        service_discovery_backend: str = "redis",
    ):
        self.node_id = node_id
        self.redis_url = redis_url

        # Core components
        self.actor_system: Optional[ActorSystem] = None
        self.service_discovery = ServiceDiscovery(
            service_discovery_backend, redis_url=redis_url
        )
        self.auto_scaler: Optional[AutoScaler] = None
        self.container_orchestrator = ContainerOrchestrator()

        # Cluster state
        self.cluster_nodes: Dict[str, ClusterNode] = {}
        self.service_registry: Dict[str, List[ServiceEndpoint]] = {}
        self.deployment_strategy = DeploymentStrategy.LEAST_LOADED

        # Actor services
        self.actor_services = {
            "transaction_processor": TransactionProcessorActor,
            "model_actor": ModelActor,
            "inheritance_coordinator": InheritanceCoordinatorActor,
            "physics_validator": PhysicsValidatorActor,
            "cluster_manager": ClusterManagerActor,
        }

        self.is_running = False
        self.logger = structlog.get_logger(__name__).bind(node_id=node_id)

    async def start(self) -> None:
        """Start the TML cluster manager"""
        if self.is_running:
            return

        self.logger.info("Starting TML cluster manager")

        try:
            # Initialize actor system
            self.actor_system = ActorSystem(
                node_id=self.node_id, redis_url=self.redis_url
            )
            await self.actor_system.start()

            # Start auto-scaler
            self.auto_scaler = AutoScaler(self)
            await self.auto_scaler.start()

            # Deploy core actor services
            await self._deploy_core_services()

            # Register services
            await self._register_node_services()

            # Start cluster monitoring
            asyncio.create_task(self._monitor_cluster())

            self.is_running = True
            self.logger.info("TML cluster manager started successfully")

        except Exception as e:
            self.logger.error("Failed to start cluster manager", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the TML cluster manager"""
        if not self.is_running:
            return

        self.logger.info("Stopping TML cluster manager")

        try:
            # Stop auto-scaler
            if self.auto_scaler:
                await self.auto_scaler.stop()

            # Unregister services
            await self._unregister_node_services()

            # Stop actor system
            if self.actor_system:
                await self.actor_system.stop()

            self.is_running = False
            self.logger.info("TML cluster manager stopped successfully")

        except Exception as e:
            self.logger.error("Error stopping cluster manager", error=str(e))

    async def _deploy_core_services(self) -> None:
        """Deploy core TML actor services"""
        core_services = [
            ("transaction_processor", 5),  # 5 replicas for high throughput
            ("inheritance_coordinator", 1),  # Single coordinator
            ("physics_validator", 2),  # 2 replicas for validation
            ("cluster_manager", 1),  # Single cluster manager per node
        ]

        for service_name, replica_count in core_services:
            if service_name in self.actor_services:
                actor_class = self.actor_services[service_name]

                # Create actor instances
                for i in range(replica_count):
                    actor_id = f"{service_name}_{i}_{self.node_id}"
                    await self.actor_system.create_actor(actor_class, actor_id)

                self.logger.info(
                    "Core service deployed",
                    service=service_name,
                    replicas=replica_count,
                )

    async def _register_node_services(self) -> None:
        """Register node services with service discovery"""
        # Register TML node service
        endpoint = ServiceEndpoint(
            service_name="tml_node",
            node_id=self.node_id,
            address="localhost",  # Should be actual node address
            port=8080,
            metadata={
                "actor_count": len(self.actor_system.actors),
                "node_type": "tml_processing",
            },
        )
        await self.service_discovery.register_service(endpoint)

    async def _unregister_node_services(self) -> None:
        """Unregister node services"""
        await self.service_discovery.unregister_service("tml_node", self.node_id)

    async def _monitor_cluster(self) -> None:
        """Monitor cluster health and performance"""
        while self.is_running:
            try:
                # Discover other TML nodes
                tml_nodes = await self.service_discovery.discover_services("tml_node")

                # Update cluster nodes
                for endpoint in tml_nodes:
                    if endpoint.node_id != self.node_id:
                        if endpoint.node_id not in self.cluster_nodes:
                            self.cluster_nodes[endpoint.node_id] = ClusterNode(
                                endpoint.node_id, endpoint.address, endpoint.port
                            )
                        self.cluster_nodes[endpoint.node_id].update_heartbeat()

                # Remove dead nodes
                dead_nodes = [
                    node_id
                    for node_id, node in self.cluster_nodes.items()
                    if not node.is_healthy()
                ]
                for node_id in dead_nodes:
                    del self.cluster_nodes[node_id]
                    self.logger.warning("Removed dead node", node_id=node_id)

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                self.logger.error("Cluster monitoring failed", error=str(e))

    async def scale_up(self, scale_factor: float = 1.5) -> None:
        """Scale up the cluster"""
        try:
            current_replicas = len(self.actor_system.actors)
            target_replicas = int(current_replicas * scale_factor)

            # Deploy additional transaction processors
            additional_replicas = target_replicas - current_replicas
            for i in range(additional_replicas):
                actor_id = f"transaction_processor_scaled_{i}_{self.node_id}"
                await self.actor_system.create_actor(
                    TransactionProcessorActor, actor_id
                )

            self.logger.info(
                "Scaled up cluster",
                additional_replicas=additional_replicas,
                total_actors=len(self.actor_system.actors),
            )

        except Exception as e:
            self.logger.error("Scale up failed", error=str(e))

    async def scale_down(self, scale_factor: float = 0.7) -> None:
        """Scale down the cluster"""
        try:
            current_replicas = len(self.actor_system.actors)
            target_replicas = max(1, int(current_replicas * scale_factor))

            # Remove excess actors (implement graceful shutdown)
            actors_to_remove = current_replicas - target_replicas

            self.logger.info(
                "Scaled down cluster",
                removed_actors=actors_to_remove,
                total_actors=target_replicas,
            )

        except Exception as e:
            self.logger.error("Scale down failed", error=str(e))

    async def deploy_actor_service(
        self, service_name: str, actor_class: type, replicas: int = 1
    ) -> List[str]:
        """Deploy new actor service"""
        deployed_actors = []

        try:
            for i in range(replicas):
                actor_id = f"{service_name}_{i}_{self.node_id}"
                actor_ref = await self.actor_system.create_actor(actor_class, actor_id)
                deployed_actors.append(actor_id)

            self.logger.info(
                "Actor service deployed", service=service_name, replicas=replicas
            )

            return deployed_actors

        except Exception as e:
            self.logger.error(
                "Actor service deployment failed", service=service_name, error=str(e)
            )
            return []

    def add_scaling_rule(self, rule: ScalingRule) -> None:
        """Add auto-scaling rule"""
        if self.auto_scaler:
            self.auto_scaler.add_scaling_rule(rule)

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status"""
        return {
            "node_id": self.node_id,
            "is_running": self.is_running,
            "cluster_size": len(self.cluster_nodes) + 1,  # +1 for this node
            "total_actors": len(self.actor_system.actors) if self.actor_system else 0,
            "cluster_nodes": [node.to_dict() for node in self.cluster_nodes.values()],
            "services": list(self.service_registry.keys()),
            "uptime": time.time()
            - (self.actor_system.startup_time if self.actor_system else time.time()),
        }
