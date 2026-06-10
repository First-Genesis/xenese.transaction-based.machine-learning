"""
Enhanced Cluster Manager for TML Platform
Implements distributed actor clustering with load balancing and sharding
"""

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import aioredis
from loguru import logger

from .actor_system import ActorMessage, ActorSystem, ClusterNode, ShardRegion
from .tml_actors import ModelActor, TransactionProcessorActor


class ClusterStrategy(Enum):
    """Clustering strategies"""

    ROUND_ROBIN = "round_robin"
    LOAD_BALANCED = "load_balanced"
    SHARDED = "sharded"
    GEOGRAPHIC = "geographic"


@dataclass
class ClusterConfig:
    """Configuration for cluster management"""

    strategy: ClusterStrategy = ClusterStrategy.LOAD_BALANCED
    max_nodes: int = 10
    min_nodes: int = 2
    replication_factor: int = 2
    shard_count: int = 100
    heartbeat_interval: float = 10.0
    health_check_timeout: float = 30.0
    auto_scaling: bool = True


class EnhancedClusterManager:
    """
    Enhanced cluster manager for distributed actor processing
    Provides load balancing, sharding, and automatic scaling
    """

    def __init__(self, actor_system: ActorSystem, config: ClusterConfig = None):
        self.actor_system = actor_system
        self.config = config or ClusterConfig()

        # Cluster state
        self.nodes: Dict[str, ClusterNode] = {}
        self.shard_regions: Dict[str, ShardRegion] = {}
        self.load_balancer = LoadBalancer(self)

        # Actor distribution
        self.actor_distribution: Dict[str, str] = {}  # actor_id -> node_id
        self.node_loads: Dict[str, float] = {}

        # Cluster metrics
        self.cluster_metrics = {
            "total_nodes": 0,
            "healthy_nodes": 0,
            "total_actors": 0,
            "messages_routed": 0,
            "load_balance_operations": 0,
            "shard_migrations": 0,
        }

        logger.info(
            f"Enhanced Cluster Manager initialized with strategy: {self.config.strategy.value}"
        )

    async def initialize_cluster(self):
        """Initialize cluster with current node"""
        # Create transaction processor shard region
        self.shard_regions["transaction_processors"] = ShardRegion(
            "transaction_processors", self.config.shard_count
        )

        # Create model actor shard region
        self.shard_regions["model_actors"] = ShardRegion(
            "model_actors", self.config.shard_count
        )

        # Register current node
        await self._register_node()

        # Start cluster services
        asyncio.create_task(self._cluster_monitor())
        asyncio.create_task(self._load_balancer_service())

        logger.info("✅ Cluster initialized successfully")

    async def _register_node(self):
        """Register this node in the cluster"""
        node = ClusterNode(
            node_id=self.actor_system.node_id,
            address="localhost",  # In production, use actual IP
            port=self.actor_system.cluster_port,
        )

        self.nodes[self.actor_system.node_id] = node

        # Update Redis cluster registry
        if self.actor_system.redis_client:
            await self.actor_system.redis_client.hset(
                "enhanced_cluster_nodes",
                self.actor_system.node_id,
                json.dumps(node.to_dict()),
            )

        logger.info(f"✅ Node registered: {self.actor_system.node_id}")

    async def create_distributed_actor(
        self, actor_class, actor_id: str, **kwargs
    ) -> str:
        """Create actor with cluster-aware placement"""
        # Determine target node based on strategy
        target_node = await self._select_target_node(actor_id, actor_class)

        if target_node == self.actor_system.node_id:
            # Create locally
            actor_ref = await self.actor_system.create_actor(
                actor_class, actor_id, **kwargs
            )
            self.actor_distribution[actor_id] = self.actor_system.node_id
            logger.info(f"✅ Created local actor: {actor_id}")
            return self.actor_system.node_id
        else:
            # Create remotely
            await self._create_remote_actor(
                target_node, actor_class, actor_id, **kwargs
            )
            self.actor_distribution[actor_id] = target_node
            logger.info(f"✅ Created remote actor: {actor_id} on {target_node}")
            return target_node

    async def _select_target_node(self, actor_id: str, actor_class) -> str:
        """Select target node based on clustering strategy"""
        if self.config.strategy == ClusterStrategy.ROUND_ROBIN:
            return self._round_robin_selection()

        elif self.config.strategy == ClusterStrategy.LOAD_BALANCED:
            return await self._load_balanced_selection()

        elif self.config.strategy == ClusterStrategy.SHARDED:
            return self._sharded_selection(actor_id, actor_class)

        else:
            # Default to local
            return self.actor_system.node_id

    def _round_robin_selection(self) -> str:
        """Round-robin node selection"""
        healthy_nodes = [
            node_id for node_id, node in self.nodes.items() if node.is_healthy()
        ]
        if not healthy_nodes:
            return self.actor_system.node_id

        # Simple round-robin based on current time
        index = int(time.time()) % len(healthy_nodes)
        return healthy_nodes[index]

    async def _load_balanced_selection(self) -> str:
        """Load-balanced node selection"""
        # Update node loads
        await self._update_node_loads()

        # Find node with lowest load
        min_load = float("inf")
        target_node = self.actor_system.node_id

        for node_id, node in self.nodes.items():
            if node.is_healthy():
                load = self.node_loads.get(node_id, 0.0)
                if load < min_load:
                    min_load = load
                    target_node = node_id

        return target_node

    def _sharded_selection(self, actor_id: str, actor_class) -> str:
        """Sharded node selection based on actor type"""
        # Determine shard region
        if issubclass(actor_class, TransactionProcessorActor):
            region = self.shard_regions["transaction_processors"]
        elif issubclass(actor_class, ModelActor):
            region = self.shard_regions["model_actors"]
        else:
            # Default to transaction processors
            region = self.shard_regions["transaction_processors"]

        # Calculate shard
        shard_id = region.get_shard_id(actor_id)

        # Get or assign node for shard
        if shard_id not in region.shard_allocation:
            # Assign to least loaded node
            target_node = self._get_least_loaded_node()
            region.allocate_shard(shard_id, target_node)

        return region.shard_allocation[shard_id]

    def _get_least_loaded_node(self) -> str:
        """Get the node with the least load"""
        min_load = float("inf")
        target_node = self.actor_system.node_id

        for node_id, node in self.nodes.items():
            if node.is_healthy():
                load = node.load_factor
                if load < min_load:
                    min_load = load
                    target_node = node_id

        return target_node

    async def _update_node_loads(self):
        """Update load information for all nodes"""
        if not self.actor_system.redis_client:
            return

        # Get all node information from Redis
        nodes_data = await self.actor_system.redis_client.hgetall(
            "enhanced_cluster_nodes"
        )

        for node_id_bytes, node_data_bytes in nodes_data.items():
            node_id = node_id_bytes.decode()
            node_data = json.loads(node_data_bytes)

            # Update local node cache
            if node_id not in self.nodes:
                self.nodes[node_id] = ClusterNode(
                    node_data["node_id"], node_data["address"], node_data["port"]
                )

            node = self.nodes[node_id]
            node.actor_count = node_data.get("actor_count", 0)
            node.load_factor = node_data.get("load_factor", 0.0)
            node.last_heartbeat = node_data.get("last_heartbeat", time.time())

            self.node_loads[node_id] = node.load_factor

    async def _create_remote_actor(
        self, target_node: str, actor_class, actor_id: str, **kwargs
    ):
        """Create actor on remote node"""
        # In a full implementation, this would send a message to the remote node
        # For now, we'll simulate by updating the distribution
        logger.info(f"Simulating remote actor creation: {actor_id} on {target_node}")

        # Update cluster registry
        if self.actor_system.redis_client:
            await self.actor_system.redis_client.set(
                f"actor_location:{actor_id}", target_node
            )

    async def route_message_to_actor(self, message: ActorMessage) -> bool:
        """Route message to correct node based on actor location"""
        actor_id = message.recipient

        # Check if actor is local
        if actor_id in self.actor_system.actors:
            await self.actor_system.deliver_message(message)
            self.cluster_metrics["messages_routed"] += 1
            return True

        # Check distribution cache
        if actor_id in self.actor_distribution:
            target_node = self.actor_distribution[actor_id]
            if target_node == self.actor_system.node_id:
                await self.actor_system.deliver_message(message)
            else:
                await self._send_remote_message(message, target_node)
            self.cluster_metrics["messages_routed"] += 1
            return True

        # Query Redis for actor location
        if self.actor_system.redis_client:
            target_node = await self.actor_system.redis_client.get(
                f"actor_location:{actor_id}"
            )
            if target_node:
                target_node = target_node.decode()
                self.actor_distribution[actor_id] = target_node

                if target_node == self.actor_system.node_id:
                    await self.actor_system.deliver_message(message)
                else:
                    await self._send_remote_message(message, target_node)

                self.cluster_metrics["messages_routed"] += 1
                return True

        # Actor not found
        logger.warning(f"Actor not found in cluster: {actor_id}")
        return False

    async def _send_remote_message(self, message: ActorMessage, target_node: str):
        """Send message to remote node"""
        # In a full implementation, this would use network communication
        # For now, we'll log the routing
        logger.info(f"Routing message {message.id} to node {target_node}")

    async def _cluster_monitor(self):
        """Monitor cluster health and perform maintenance"""
        while self.actor_system.is_running:
            try:
                await self._update_node_loads()
                await self._check_cluster_health()
                await self._rebalance_if_needed()

                # Update metrics
                self.cluster_metrics["total_nodes"] = len(self.nodes)
                self.cluster_metrics["healthy_nodes"] = sum(
                    1 for node in self.nodes.values() if node.is_healthy()
                )

                await asyncio.sleep(self.config.heartbeat_interval)

            except Exception as e:
                logger.error(f"Cluster monitor error: {e}")
                await asyncio.sleep(5)

    async def _check_cluster_health(self):
        """Check health of all cluster nodes"""
        unhealthy_nodes = []

        for node_id, node in self.nodes.items():
            if not node.is_healthy(self.config.health_check_timeout):
                unhealthy_nodes.append(node_id)

        if unhealthy_nodes:
            logger.warning(f"Unhealthy nodes detected: {unhealthy_nodes}")
            await self._handle_node_failures(unhealthy_nodes)

    async def _handle_node_failures(self, failed_nodes: List[str]):
        """Handle failed nodes by redistributing their actors"""
        for node_id in failed_nodes:
            # Find actors on failed node
            failed_actors = [
                actor_id
                for actor_id, assigned_node in self.actor_distribution.items()
                if assigned_node == node_id
            ]

            # Redistribute actors
            for actor_id in failed_actors:
                new_node = await self._select_target_node(actor_id, None)
                self.actor_distribution[actor_id] = new_node

                # Update Redis
                if self.actor_system.redis_client:
                    await self.actor_system.redis_client.set(
                        f"actor_location:{actor_id}", new_node
                    )

            logger.info(
                f"Redistributed {len(failed_actors)} actors from failed node {node_id}"
            )

    async def _rebalance_if_needed(self):
        """Rebalance cluster if load is uneven"""
        if self.config.strategy != ClusterStrategy.LOAD_BALANCED:
            return

        # Calculate load variance
        loads = list(self.node_loads.values())
        if not loads:
            return

        avg_load = sum(loads) / len(loads)
        max_load = max(loads)

        # Rebalance if max load is significantly higher than average
        if max_load > avg_load * 1.5:
            await self._perform_load_balancing()

    async def _perform_load_balancing(self):
        """Perform load balancing across cluster"""
        logger.info("Performing cluster load balancing...")

        # Find overloaded and underloaded nodes
        overloaded = []
        underloaded = []

        avg_load = sum(self.node_loads.values()) / len(self.node_loads)

        for node_id, load in self.node_loads.items():
            if load > avg_load * 1.3:
                overloaded.append(node_id)
            elif load < avg_load * 0.7:
                underloaded.append(node_id)

        # Move actors from overloaded to underloaded nodes
        for overloaded_node in overloaded:
            if not underloaded:
                break

            # Find actors to move
            actors_to_move = [
                actor_id
                for actor_id, node_id in self.actor_distribution.items()
                if node_id == overloaded_node
            ]

            # Move some actors
            move_count = min(len(actors_to_move) // 4, 5)  # Move up to 25% or 5 actors
            for i in range(move_count):
                if not underloaded:
                    break

                actor_id = actors_to_move[i]
                target_node = underloaded[i % len(underloaded)]

                # Update distribution
                self.actor_distribution[actor_id] = target_node

                # Update Redis
                if self.actor_system.redis_client:
                    await self.actor_system.redis_client.set(
                        f"actor_location:{actor_id}", target_node
                    )

        self.cluster_metrics["load_balance_operations"] += 1
        logger.info("✅ Load balancing completed")

    async def _load_balancer_service(self):
        """Background service for load balancing"""
        while self.actor_system.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._rebalance_if_needed()
            except Exception as e:
                logger.error(f"Load balancer service error: {e}")
                await asyncio.sleep(30)

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status"""
        return {
            "config": asdict(self.config),
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "metrics": self.cluster_metrics,
            "actor_distribution": dict(self.actor_distribution),
            "shard_regions": {
                name: {
                    "shard_count": region.shard_count,
                    "allocated_shards": len(region.shard_allocation),
                    "actors": len(region.actor_locations),
                }
                for name, region in self.shard_regions.items()
            },
        }


class LoadBalancer:
    """Load balancer for cluster management"""

    def __init__(self, cluster_manager: EnhancedClusterManager):
        self.cluster_manager = cluster_manager
        self.request_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}

    def record_request(self, node_id: str, response_time: float):
        """Record request for load balancing metrics"""
        if node_id not in self.request_counts:
            self.request_counts[node_id] = 0
            self.response_times[node_id] = []

        self.request_counts[node_id] += 1
        self.response_times[node_id].append(response_time)

        # Keep only recent response times
        if len(self.response_times[node_id]) > 100:
            self.response_times[node_id] = self.response_times[node_id][-100:]

    def get_node_performance(self, node_id: str) -> Dict[str, float]:
        """Get performance metrics for a node"""
        if node_id not in self.request_counts:
            return {"requests": 0, "avg_response_time": 0.0}

        avg_response_time = (
            sum(self.response_times[node_id]) / len(self.response_times[node_id])
            if self.response_times[node_id]
            else 0.0
        )

        return {
            "requests": self.request_counts[node_id],
            "avg_response_time": avg_response_time,
        }
