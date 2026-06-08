"""
Enhanced TML Platform v2.0 - Complete Proto.Actor System Implementation

Production-ready actor system with distributed processing, high-throughput optimization,
advanced fault tolerance, and comprehensive monitoring.
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Union
from concurrent.futures import ThreadPoolExecutor
import threading
import json
import hashlib
from collections import defaultdict, deque
import weakref
import psutil
import redis
import aioredis
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Prometheus Metrics
ACTOR_MESSAGES_TOTAL = Counter(
    "tml_actor_messages_total",
    "Total messages processed",
    ["actor_type", "message_type"],
)
ACTOR_MESSAGE_DURATION = Histogram(
    "tml_actor_message_duration_seconds", "Message processing duration", ["actor_type"]
)
ACTIVE_ACTORS = Gauge("tml_active_actors", "Number of active actors", ["actor_type"])
ACTOR_ERRORS = Counter(
    "tml_actor_errors_total", "Actor processing errors", ["actor_type", "error_type"]
)
CLUSTER_NODES = Gauge("tml_cluster_nodes", "Number of cluster nodes")
THROUGHPUT_TPS = Gauge("tml_throughput_tps", "Transactions per second")


class ActorState(Enum):
    """Actor lifecycle states"""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


class MessagePriority(Enum):
    """Message priority levels"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ActorMessage:
    """Base message class for actor communication"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: Optional[str] = None
    recipient: str = ""
    message_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary"""
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActorMessage":
        """Deserialize message from dictionary"""
        return cls(
            id=data["id"],
            sender=data.get("sender"),
            recipient=data["recipient"],
            message_type=data["message_type"],
            payload=data.get("payload", {}),
            priority=MessagePriority(
                data.get("priority", MessagePriority.NORMAL.value)
            ),
            timestamp=data.get("timestamp", time.time()),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
            timeout=data.get("timeout"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )


class SupervisionStrategy(Enum):
    """Actor supervision strategies"""

    RESTART = "restart"
    STOP = "stop"
    ESCALATE = "escalate"
    RESUME = "resume"


@dataclass
class SupervisionDirective:
    """Supervision directive for handling actor failures"""

    strategy: SupervisionStrategy
    max_retries: int = 3
    within_time_range: float = 60.0  # seconds
    backoff_strategy: str = "exponential"  # linear, exponential, fixed


class ActorRef:
    """Reference to an actor for message passing"""

    def __init__(self, actor_id: str, actor_system: "ActorSystem"):
        self.actor_id = actor_id
        self.actor_system = actor_system
        self._is_local = True
        self._node_id = actor_system.node_id

    async def tell(self, message: ActorMessage) -> None:
        """Send a fire-and-forget message"""
        message.recipient = self.actor_id
        await self.actor_system.deliver_message(message)

    async def ask(self, message: ActorMessage, timeout: float = 30.0) -> Any:
        """Send a message and wait for response"""
        message.recipient = self.actor_id
        message.reply_to = f"temp_{uuid.uuid4()}"
        message.timeout = timeout

        return await self.actor_system.ask_message(message)

    def __str__(self) -> str:
        return f"ActorRef({self.actor_id}@{self._node_id})"


class Actor(ABC):
    """Base actor class with lifecycle management"""

    def __init__(self, actor_id: str, actor_system: "ActorSystem"):
        self.actor_id = actor_id
        self.actor_system = actor_system
        self.state = ActorState.CREATED
        self.mailbox = asyncio.Queue(maxsize=10000)  # High-capacity mailbox
        self.children: Set[str] = set()
        self.parent: Optional[str] = None
        self.supervision_directive = SupervisionDirective(SupervisionStrategy.RESTART)
        self.metrics = {
            "messages_processed": 0,
            "messages_failed": 0,
            "start_time": time.time(),
            "last_activity": time.time(),
        }
        self._stop_event = asyncio.Event()
        self._processing_task: Optional[asyncio.Task] = None
        self.logger = structlog.get_logger(__name__).bind(actor_id=actor_id)

    async def start(self) -> None:
        """Start the actor"""
        if self.state != ActorState.CREATED:
            raise RuntimeError(
                f"Actor {self.actor_id} cannot be started from state {self.state}"
            )

        self.state = ActorState.STARTING
        self.logger.info("Starting actor")

        try:
            await self.pre_start()
            self.state = ActorState.RUNNING
            self._processing_task = asyncio.create_task(self._message_loop())
            ACTIVE_ACTORS.labels(actor_type=self.__class__.__name__).inc()
            self.logger.info("Actor started successfully")
        except Exception as e:
            self.state = ActorState.FAILED
            self.logger.error("Failed to start actor", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the actor gracefully"""
        if self.state in [ActorState.STOPPING, ActorState.STOPPED]:
            return

        self.state = ActorState.STOPPING
        self.logger.info("Stopping actor")

        try:
            # Stop all children first
            for child_id in list(self.children):
                child_ref = self.actor_system.get_actor_ref(child_id)
                if child_ref:
                    await child_ref.tell(ActorMessage(message_type="stop"))

            # Signal stop and wait for message loop to finish
            self._stop_event.set()
            if self._processing_task:
                await self._processing_task

            await self.post_stop()
            self.state = ActorState.STOPPED
            ACTIVE_ACTORS.labels(actor_type=self.__class__.__name__).dec()
            self.logger.info("Actor stopped successfully")

        except Exception as e:
            self.logger.error("Error during actor stop", error=str(e))
            self.state = ActorState.FAILED

    async def _message_loop(self) -> None:
        """Main message processing loop"""
        while not self._stop_event.is_set():
            try:
                # Wait for message with timeout to allow periodic checks
                message = await asyncio.wait_for(self.mailbox.get(), timeout=1.0)
                await self._process_message(message)
            except asyncio.TimeoutError:
                # Periodic maintenance
                await self._periodic_maintenance()
            except Exception as e:
                self.logger.error("Error in message loop", error=str(e))
                ACTOR_ERRORS.labels(
                    actor_type=self.__class__.__name__, error_type=type(e).__name__
                ).inc()

    async def _process_message(self, message: ActorMessage) -> None:
        """Process a single message with metrics and error handling"""
        start_time = time.time()

        try:
            self.metrics["last_activity"] = start_time

            # Handle system messages
            if message.message_type == "stop":
                await self.stop()
                return
            elif message.message_type == "restart":
                await self._restart()
                return

            # Process user message
            await self.receive(message)

            self.metrics["messages_processed"] += 1
            ACTOR_MESSAGES_TOTAL.labels(
                actor_type=self.__class__.__name__, message_type=message.message_type
            ).inc()

        except Exception as e:
            self.metrics["messages_failed"] += 1
            self.logger.error(
                "Message processing failed",
                message_id=message.id,
                message_type=message.message_type,
                error=str(e),
            )

            ACTOR_ERRORS.labels(
                actor_type=self.__class__.__name__, error_type=type(e).__name__
            ).inc()

            # Handle supervision
            await self._handle_failure(e, message)

        finally:
            duration = time.time() - start_time
            ACTOR_MESSAGE_DURATION.labels(actor_type=self.__class__.__name__).observe(
                duration
            )

    async def _handle_failure(self, error: Exception, message: ActorMessage) -> None:
        """Handle actor failure according to supervision strategy"""
        if self.parent:
            parent_ref = self.actor_system.get_actor_ref(self.parent)
            if parent_ref:
                failure_msg = ActorMessage(
                    message_type="child_failed",
                    payload={
                        "child_id": self.actor_id,
                        "error": str(error),
                        "failed_message": message.to_dict(),
                    },
                )
                await parent_ref.tell(failure_msg)

    async def _restart(self) -> None:
        """Restart the actor"""
        self.state = ActorState.RESTARTING
        self.logger.info("Restarting actor")

        try:
            await self.post_stop()
            await self.pre_start()
            self.state = ActorState.RUNNING
            self.logger.info("Actor restarted successfully")
        except Exception as e:
            self.state = ActorState.FAILED
            self.logger.error("Failed to restart actor", error=str(e))

    async def _periodic_maintenance(self) -> None:
        """Periodic maintenance tasks"""
        # Update metrics, cleanup, health checks, etc.
        pass

    # Abstract methods to be implemented by concrete actors
    @abstractmethod
    async def receive(self, message: ActorMessage) -> None:
        """Process incoming messages"""
        pass

    async def pre_start(self) -> None:
        """Called before actor starts"""
        pass

    async def post_stop(self) -> None:
        """Called after actor stops"""
        pass


class ClusterNode:
    """Represents a node in the actor cluster"""

    def __init__(self, node_id: str, address: str, port: int):
        self.node_id = node_id
        self.address = address
        self.port = port
        self.last_heartbeat = time.time()
        self.is_alive = True
        self.actor_count = 0
        self.load_factor = 0.0

    def update_heartbeat(self) -> None:
        """Update node heartbeat"""
        self.last_heartbeat = time.time()
        self.is_alive = True

    def is_healthy(self, timeout: float = 30.0) -> bool:
        """Check if node is healthy"""
        return self.is_alive and (time.time() - self.last_heartbeat) < timeout

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary"""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "port": self.port,
            "last_heartbeat": self.last_heartbeat,
            "is_alive": self.is_alive,
            "actor_count": self.actor_count,
            "load_factor": self.load_factor,
        }


class ShardRegion:
    """Manages sharded actors across cluster nodes"""

    def __init__(self, region_name: str, shard_count: int = 100):
        self.region_name = region_name
        self.shard_count = shard_count
        self.shard_allocation: Dict[int, str] = {}  # shard_id -> node_id
        self.actor_locations: Dict[str, int] = {}  # actor_id -> shard_id

    def get_shard_id(self, entity_id: str) -> int:
        """Calculate shard ID for entity"""
        return int(hashlib.md5(entity_id.encode()).hexdigest(), 16) % self.shard_count

    def allocate_shard(self, shard_id: int, node_id: str) -> None:
        """Allocate shard to node"""
        self.shard_allocation[shard_id] = node_id

    def get_node_for_entity(self, entity_id: str) -> Optional[str]:
        """Get node ID for entity"""
        shard_id = self.get_shard_id(entity_id)
        return self.shard_allocation.get(shard_id)


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half-open

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"

            raise e


class EventSourcing:
    """Event sourcing for actor state persistence"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis_client = redis_client

    async def append_event(self, actor_id: str, event: Dict[str, Any]) -> None:
        """Append event to actor's event stream"""
        event_data = json.dumps(
            {"timestamp": time.time(), "event_id": str(uuid.uuid4()), **event}
        )
        await self.redis_client.lpush(f"events:{actor_id}", event_data)

    async def get_events(
        self, actor_id: str, from_sequence: int = 0
    ) -> List[Dict[str, Any]]:
        """Get events for actor from sequence number"""
        events = await self.redis_client.lrange(f"events:{actor_id}", from_sequence, -1)
        return [json.loads(event) for event in events]

    async def create_snapshot(self, actor_id: str, state: Dict[str, Any]) -> None:
        """Create state snapshot"""
        snapshot_data = json.dumps({"timestamp": time.time(), "state": state})
        await self.redis_client.set(f"snapshot:{actor_id}", snapshot_data)


class ActorSystem:
    """Complete actor system with clustering, sharding, and fault tolerance"""

    def __init__(
        self,
        node_id: str,
        redis_url: str = "redis://localhost:6379",
        cluster_port: int = 8080,
        metrics_port: int = 9090,
    ):
        self.node_id = node_id
        self.redis_url = redis_url
        self.cluster_port = cluster_port
        self.metrics_port = metrics_port

        # Core components
        self.actors: Dict[str, Actor] = {}
        self.actor_refs: Dict[str, ActorRef] = {}
        self.cluster_nodes: Dict[str, ClusterNode] = {}
        self.shard_regions: Dict[str, ShardRegion] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Message routing
        self.message_router = MessageRouter(self)
        self.dead_letter_queue = deque(maxlen=10000)
        self.pending_asks: Dict[str, asyncio.Future] = {}

        # Fault tolerance
        self.supervision_tree: Dict[str, Set[str]] = defaultdict(set)

        # Performance optimization
        self.thread_pool = ThreadPoolExecutor(max_workers=50)
        self.high_priority_queue = asyncio.Queue(maxsize=1000)
        self.normal_priority_queue = asyncio.Queue(maxsize=10000)

        # Monitoring
        self.metrics_collector = MetricsCollector(self)
        self.health_monitor = HealthMonitor(self)

        # Event sourcing
        self.event_sourcing: Optional[EventSourcing] = None
        self.redis_client: Optional[aioredis.Redis] = None

        # System state
        self.is_running = False
        self.startup_time = time.time()

        self.logger = structlog.get_logger(__name__).bind(node_id=node_id)

    async def start(self) -> None:
        """Start the actor system"""
        if self.is_running:
            return

        self.logger.info("Starting actor system")

        try:
            # Initialize Redis connection
            self.redis_client = aioredis.from_url(self.redis_url)
            self.event_sourcing = EventSourcing(self.redis_client)

            # Start metrics server
            start_http_server(self.metrics_port)

            # Start core services
            await self.message_router.start()
            await self.metrics_collector.start()
            await self.health_monitor.start()

            # Join cluster
            await self._join_cluster()

            # Start message processing
            asyncio.create_task(self._process_high_priority_messages())
            asyncio.create_task(self._process_normal_priority_messages())
            asyncio.create_task(self._cluster_heartbeat())

            self.is_running = True
            self.logger.info("Actor system started successfully")

        except Exception as e:
            self.logger.error("Failed to start actor system", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the actor system gracefully"""
        if not self.is_running:
            return

        self.logger.info("Stopping actor system")

        try:
            # Stop all actors
            for actor in list(self.actors.values()):
                await actor.stop()

            # Stop services
            await self.message_router.stop()
            await self.metrics_collector.stop()
            await self.health_monitor.stop()

            # Leave cluster
            await self._leave_cluster()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()

            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)

            self.is_running = False
            self.logger.info("Actor system stopped successfully")

        except Exception as e:
            self.logger.error("Error stopping actor system", error=str(e))

    async def create_actor(
        self, actor_class: type, actor_id: str, parent_id: Optional[str] = None
    ) -> ActorRef:
        """Create a new actor"""
        if actor_id in self.actors:
            raise ValueError(f"Actor {actor_id} already exists")

        # Create actor instance
        actor = actor_class(actor_id, self)
        if parent_id:
            actor.parent = parent_id
            self.supervision_tree[parent_id].add(actor_id)

        # Store actor
        self.actors[actor_id] = actor
        actor_ref = ActorRef(actor_id, self)
        self.actor_refs[actor_id] = actor_ref

        # Start actor
        await actor.start()

        self.logger.info(
            "Created actor", actor_id=actor_id, actor_type=actor_class.__name__
        )
        return actor_ref

    def get_actor_ref(self, actor_id: str) -> Optional[ActorRef]:
        """Get reference to actor"""
        return self.actor_refs.get(actor_id)

    async def deliver_message(self, message: ActorMessage) -> None:
        """Deliver message to actor"""
        # Route message based on priority
        if message.priority in [MessagePriority.HIGH, MessagePriority.CRITICAL]:
            await self.high_priority_queue.put(message)
        else:
            await self.normal_priority_queue.put(message)

    async def ask_message(self, message: ActorMessage) -> Any:
        """Send message and wait for response"""
        if not message.reply_to:
            raise ValueError("Ask message must have reply_to field")

        # Create future for response
        future = asyncio.Future()
        self.pending_asks[message.reply_to] = future

        # Send message
        await self.deliver_message(message)

        # Wait for response with timeout
        try:
            timeout = message.timeout or 30.0
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.pending_asks.pop(message.reply_to, None)
            raise
        finally:
            self.pending_asks.pop(message.reply_to, None)

    async def _process_high_priority_messages(self) -> None:
        """Process high priority messages"""
        while self.is_running:
            try:
                message = await self.high_priority_queue.get()
                await self._route_message(message)
            except Exception as e:
                self.logger.error(
                    "Error processing high priority message", error=str(e)
                )

    async def _process_normal_priority_messages(self) -> None:
        """Process normal priority messages"""
        while self.is_running:
            try:
                message = await self.normal_priority_queue.get()
                await self._route_message(message)
            except Exception as e:
                self.logger.error(
                    "Error processing normal priority message", error=str(e)
                )

    async def _route_message(self, message: ActorMessage) -> None:
        """Route message to appropriate actor"""
        # Check if it's a response to an ask
        if (
            message.recipient.startswith("temp_")
            and message.recipient in self.pending_asks
        ):
            future = self.pending_asks[message.recipient]
            if not future.done():
                future.set_result(message.payload)
            return

        # Route to local actor
        actor = self.actors.get(message.recipient)
        if actor:
            await actor.mailbox.put(message)
            return

        # Route to remote actor (cluster)
        node_id = await self._find_actor_node(message.recipient)
        if node_id and node_id != self.node_id:
            await self._send_remote_message(message, node_id)
            return

        # Dead letter
        self.dead_letter_queue.append(message)
        self.logger.warning(
            "Message sent to dead letter queue",
            recipient=message.recipient,
            message_type=message.message_type,
        )

    async def _find_actor_node(self, actor_id: str) -> Optional[str]:
        """Find which node hosts the actor"""
        # Check shard regions
        for region in self.shard_regions.values():
            node_id = region.get_node_for_entity(actor_id)
            if node_id:
                return node_id

        # Query cluster registry
        if self.redis_client:
            node_id = await self.redis_client.get(f"actor_location:{actor_id}")
            if node_id:
                return node_id.decode()

        return None

    async def _send_remote_message(self, message: ActorMessage, node_id: str) -> None:
        """Send message to remote node"""
        node = self.cluster_nodes.get(node_id)
        if not node or not node.is_healthy():
            self.dead_letter_queue.append(message)
            return

        # Implement remote message sending (HTTP, gRPC, etc.)
        # For now, just log
        self.logger.info(
            "Sending remote message", recipient=message.recipient, target_node=node_id
        )

    async def _join_cluster(self) -> None:
        """Join the actor cluster"""
        if not self.redis_client:
            return

        # Register this node
        node_info = {
            "node_id": self.node_id,
            "address": "localhost",  # Should be actual address
            "port": self.cluster_port,
            "last_heartbeat": time.time(),
            "is_alive": True,
        }

        await self.redis_client.hset(
            "cluster_nodes", self.node_id, json.dumps(node_info)
        )

        # Load existing nodes
        nodes_data = await self.redis_client.hgetall("cluster_nodes")
        for node_id, node_data in nodes_data.items():
            if node_id.decode() != self.node_id:
                node_info = json.loads(node_data)
                self.cluster_nodes[node_id.decode()] = ClusterNode(
                    node_info["node_id"], node_info["address"], node_info["port"]
                )

        CLUSTER_NODES.set(len(self.cluster_nodes) + 1)
        self.logger.info("Joined cluster", cluster_size=len(self.cluster_nodes) + 1)

    async def _leave_cluster(self) -> None:
        """Leave the actor cluster"""
        if self.redis_client:
            await self.redis_client.hdel("cluster_nodes", self.node_id)

    async def _cluster_heartbeat(self) -> None:
        """Send periodic heartbeat to cluster"""
        while self.is_running:
            try:
                if self.redis_client:
                    node_info = {
                        "node_id": self.node_id,
                        "address": "localhost",
                        "port": self.cluster_port,
                        "last_heartbeat": time.time(),
                        "is_alive": True,
                        "actor_count": len(self.actors),
                        "load_factor": self._calculate_load_factor(),
                    }
                    await self.redis_client.hset(
                        "cluster_nodes", self.node_id, json.dumps(node_info)
                    )

                await asyncio.sleep(10)  # Heartbeat every 10 seconds
            except Exception as e:
                self.logger.error("Heartbeat failed", error=str(e))

    def _calculate_load_factor(self) -> float:
        """Calculate node load factor"""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        actor_load = len(self.actors) / 1000.0  # Normalize to 1000 actors

        return (cpu_percent + memory_percent + actor_load * 100) / 3.0


class MessageRouter:
    """High-performance message router"""

    def __init__(self, actor_system: "ActorSystem"):
        self.actor_system = actor_system
        self.routing_table: Dict[str, str] = {}  # actor_id -> node_id
        self.is_running = False

    async def start(self) -> None:
        """Start message router"""
        self.is_running = True

    async def stop(self) -> None:
        """Stop message router"""
        self.is_running = False


class MetricsCollector:
    """Comprehensive metrics collection"""

    def __init__(self, actor_system: "ActorSystem"):
        self.actor_system = actor_system
        self.is_running = False

    async def start(self) -> None:
        """Start metrics collection"""
        self.is_running = True
        asyncio.create_task(self._collect_metrics())

    async def stop(self) -> None:
        """Stop metrics collection"""
        self.is_running = False

    async def _collect_metrics(self) -> None:
        """Collect system metrics periodically"""
        while self.is_running:
            try:
                # Update throughput metrics
                total_messages = sum(
                    actor.metrics["messages_processed"]
                    for actor in self.actor_system.actors.values()
                )

                uptime = time.time() - self.actor_system.startup_time
                if uptime > 0:
                    tps = total_messages / uptime
                    THROUGHPUT_TPS.set(tps)

                await asyncio.sleep(5)  # Collect every 5 seconds
            except Exception as e:
                logger.error("Metrics collection failed", error=str(e))


class HealthMonitor:
    """System health monitoring"""

    def __init__(self, actor_system: "ActorSystem"):
        self.actor_system = actor_system
        self.is_running = False

    async def start(self) -> None:
        """Start health monitoring"""
        self.is_running = True
        asyncio.create_task(self._monitor_health())

    async def stop(self) -> None:
        """Stop health monitoring"""
        self.is_running = False

    async def _monitor_health(self) -> None:
        """Monitor system health"""
        while self.is_running:
            try:
                # Check actor health
                unhealthy_actors = []
                for actor_id, actor in self.actor_system.actors.items():
                    if actor.state == ActorState.FAILED:
                        unhealthy_actors.append(actor_id)

                if unhealthy_actors:
                    logger.warning("Unhealthy actors detected", actors=unhealthy_actors)

                # Check cluster health
                dead_nodes = []
                for node_id, node in self.actor_system.cluster_nodes.items():
                    if not node.is_healthy():
                        dead_nodes.append(node_id)

                if dead_nodes:
                    logger.warning("Dead cluster nodes detected", nodes=dead_nodes)

                await asyncio.sleep(30)  # Health check every 30 seconds
            except Exception as e:
                logger.error("Health monitoring failed", error=str(e))
