"""
Enhanced Supervision and Fault Tolerance Manager for TML Platform
Implements enterprise-grade supervision strategies and failure recovery
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import traceback

from loguru import logger
import aioredis

from .actor_system import (
    ActorSystem,
    Actor,
    ActorMessage,
    ActorState,
    SupervisionStrategy,
    SupervisionDirective,
)


class FaultType(Enum):
    """Types of faults that can occur"""

    ACTOR_CRASH = "actor_crash"
    MESSAGE_TIMEOUT = "message_timeout"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    DATA_CORRUPTION = "data_corruption"
    EXTERNAL_SERVICE_FAILURE = "external_service_failure"


class RecoveryAction(Enum):
    """Recovery actions for different fault types"""

    RESTART_ACTOR = "restart_actor"
    RESTART_SUBTREE = "restart_subtree"
    ESCALATE_TO_PARENT = "escalate_to_parent"
    ISOLATE_ACTOR = "isolate_actor"
    CIRCUIT_BREAK = "circuit_break"
    FAILOVER_TO_BACKUP = "failover_to_backup"


@dataclass
class FaultEvent:
    """Represents a fault event in the system"""

    fault_id: str
    fault_type: FaultType
    actor_id: str
    timestamp: float
    error_message: str
    stack_trace: str
    recovery_action: Optional[RecoveryAction] = None
    recovery_successful: bool = False
    retry_count: int = 0


@dataclass
class SupervisionPolicy:
    """Enhanced supervision policy"""

    strategy: SupervisionStrategy
    max_retries: int = 3
    retry_window: float = 60.0  # seconds
    backoff_multiplier: float = 1.5
    max_backoff: float = 30.0
    escalation_threshold: int = 5
    circuit_breaker_enabled: bool = True
    health_check_interval: float = 30.0
    recovery_timeout: float = 120.0


class SupervisionManager:
    """
    Enhanced supervision manager for fault tolerance
    Provides enterprise-grade supervision and recovery capabilities
    """

    def __init__(self, actor_system: ActorSystem):
        self.actor_system = actor_system

        # Fault tracking
        self.fault_history: Dict[str, List[FaultEvent]] = {}
        self.actor_policies: Dict[str, SupervisionPolicy] = {}
        self.recovery_strategies: Dict[FaultType, Callable] = {}

        # Circuit breakers per actor
        self.circuit_breakers: Dict[str, "EnhancedCircuitBreaker"] = {}

        # Supervision tree management
        self.supervision_tree: Dict[str, Set[str]] = {}  # parent -> children
        self.parent_map: Dict[str, str] = {}  # child -> parent

        # Health monitoring
        self.health_checks: Dict[str, float] = {}  # actor_id -> last_health_check
        self.unhealthy_actors: Set[str] = set()

        # Recovery statistics
        self.recovery_stats = {
            "total_faults": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "escalations": 0,
            "circuit_breaks": 0,
        }

        # Initialize recovery strategies
        self._initialize_recovery_strategies()

        logger.info("Enhanced Supervision Manager initialized")

    def _initialize_recovery_strategies(self):
        """Initialize recovery strategies for different fault types"""
        self.recovery_strategies = {
            FaultType.ACTOR_CRASH: self._recover_from_crash,
            FaultType.MESSAGE_TIMEOUT: self._recover_from_timeout,
            FaultType.RESOURCE_EXHAUSTION: self._recover_from_resource_exhaustion,
            FaultType.NETWORK_PARTITION: self._recover_from_network_partition,
            FaultType.DATA_CORRUPTION: self._recover_from_data_corruption,
            FaultType.EXTERNAL_SERVICE_FAILURE: self._recover_from_service_failure,
        }

    def register_actor_supervision(
        self,
        actor_id: str,
        parent_id: Optional[str] = None,
        policy: SupervisionPolicy = None,
    ):
        """Register an actor for supervision"""
        # Set default policy if none provided
        if policy is None:
            policy = SupervisionPolicy(
                strategy=SupervisionStrategy.RESTART,
                max_retries=3,
                circuit_breaker_enabled=True,
            )

        self.actor_policies[actor_id] = policy

        # Setup supervision tree
        if parent_id:
            if parent_id not in self.supervision_tree:
                self.supervision_tree[parent_id] = set()
            self.supervision_tree[parent_id].add(actor_id)
            self.parent_map[actor_id] = parent_id

        # Initialize circuit breaker
        if policy.circuit_breaker_enabled:
            self.circuit_breakers[actor_id] = EnhancedCircuitBreaker(
                failure_threshold=policy.escalation_threshold,
                recovery_timeout=policy.recovery_timeout,
            )

        # Initialize health tracking
        self.health_checks[actor_id] = time.time()

        logger.info(
            f"Registered actor {actor_id} for supervision with policy: {policy.strategy.value}"
        )

    async def handle_actor_failure(
        self,
        actor_id: str,
        error: Exception,
        fault_type: FaultType = FaultType.ACTOR_CRASH,
    ) -> bool:
        """Handle actor failure with enhanced supervision"""
        fault_event = FaultEvent(
            fault_id=f"fault_{int(time.time() * 1000)}",
            fault_type=fault_type,
            actor_id=actor_id,
            timestamp=time.time(),
            error_message=str(error),
            stack_trace=traceback.format_exc(),
        )

        # Record fault
        if actor_id not in self.fault_history:
            self.fault_history[actor_id] = []
        self.fault_history[actor_id].append(fault_event)

        self.recovery_stats["total_faults"] += 1

        logger.error(
            f"Actor failure detected: {actor_id}, Type: {fault_type.value}, Error: {error}"
        )

        # Get supervision policy
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )

        # Check circuit breaker
        if actor_id in self.circuit_breakers:
            circuit_breaker = self.circuit_breakers[actor_id]
            if circuit_breaker.is_open():
                logger.warning(
                    f"Circuit breaker open for {actor_id}, skipping recovery"
                )
                fault_event.recovery_action = RecoveryAction.CIRCUIT_BREAK
                self.recovery_stats["circuit_breaks"] += 1
                return False

        # Determine recovery action
        recovery_action = await self._determine_recovery_action(
            actor_id, fault_event, policy
        )
        fault_event.recovery_action = recovery_action

        # Execute recovery
        recovery_successful = await self._execute_recovery(
            actor_id, fault_event, policy
        )
        fault_event.recovery_successful = recovery_successful

        if recovery_successful:
            self.recovery_stats["successful_recoveries"] += 1
            logger.info(
                f"Successfully recovered actor {actor_id} using {recovery_action.value}"
            )
        else:
            self.recovery_stats["failed_recoveries"] += 1
            logger.error(f"Failed to recover actor {actor_id}")

        return recovery_successful

    async def _determine_recovery_action(
        self, actor_id: str, fault_event: FaultEvent, policy: SupervisionPolicy
    ) -> RecoveryAction:
        """Determine the appropriate recovery action"""
        # Check retry count within window
        recent_faults = self._get_recent_faults(actor_id, policy.retry_window)

        if len(recent_faults) >= policy.max_retries:
            # Too many retries, escalate
            if actor_id in self.parent_map:
                return RecoveryAction.ESCALATE_TO_PARENT
            else:
                return RecoveryAction.ISOLATE_ACTOR

        # Use fault-specific recovery strategy
        if fault_event.fault_type in self.recovery_strategies:
            return RecoveryAction.RESTART_ACTOR

        # Default based on supervision strategy
        if policy.strategy == SupervisionStrategy.RESTART:
            return RecoveryAction.RESTART_ACTOR
        elif policy.strategy == SupervisionStrategy.STOP:
            return RecoveryAction.ISOLATE_ACTOR
        elif policy.strategy == SupervisionStrategy.ESCALATE:
            return RecoveryAction.ESCALATE_TO_PARENT
        else:
            return RecoveryAction.RESTART_ACTOR

    async def _execute_recovery(
        self, actor_id: str, fault_event: FaultEvent, policy: SupervisionPolicy
    ) -> bool:
        """Execute the recovery action"""
        try:
            if fault_event.recovery_action == RecoveryAction.RESTART_ACTOR:
                return await self._restart_actor(actor_id, policy)

            elif fault_event.recovery_action == RecoveryAction.RESTART_SUBTREE:
                return await self._restart_subtree(actor_id)

            elif fault_event.recovery_action == RecoveryAction.ESCALATE_TO_PARENT:
                return await self._escalate_to_parent(actor_id, fault_event)

            elif fault_event.recovery_action == RecoveryAction.ISOLATE_ACTOR:
                return await self._isolate_actor(actor_id)

            elif fault_event.recovery_action == RecoveryAction.FAILOVER_TO_BACKUP:
                return await self._failover_to_backup(actor_id)

            else:
                logger.warning(
                    f"Unknown recovery action: {fault_event.recovery_action}"
                )
                return False

        except Exception as e:
            logger.error(f"Recovery execution failed for {actor_id}: {e}")
            return False

    async def _restart_actor(self, actor_id: str, policy: SupervisionPolicy) -> bool:
        """Restart a specific actor"""
        try:
            # Calculate backoff delay
            recent_faults = self._get_recent_faults(actor_id, policy.retry_window)
            backoff_delay = min(
                policy.backoff_multiplier ** len(recent_faults), policy.max_backoff
            )

            if backoff_delay > 0:
                logger.info(
                    f"Applying backoff delay of {backoff_delay}s for {actor_id}"
                )
                await asyncio.sleep(backoff_delay)

            # Get actor reference
            if actor_id in self.actor_system.actors:
                actor = self.actor_system.actors[actor_id]

                # Stop actor
                await actor.stop()

                # Restart actor
                await actor._restart()

                # Update health check
                self.health_checks[actor_id] = time.time()
                self.unhealthy_actors.discard(actor_id)

                logger.info(f"Successfully restarted actor {actor_id}")
                return True
            else:
                logger.warning(f"Actor {actor_id} not found for restart")
                return False

        except Exception as e:
            logger.error(f"Failed to restart actor {actor_id}: {e}")
            return False

    async def _restart_subtree(self, root_actor_id: str) -> bool:
        """Restart an actor and all its children"""
        success = True

        # Restart children first (bottom-up)
        if root_actor_id in self.supervision_tree:
            for child_id in self.supervision_tree[root_actor_id]:
                child_success = await self._restart_subtree(child_id)
                success = success and child_success

        # Restart root actor
        policy = self.actor_policies.get(
            root_actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        root_success = await self._restart_actor(root_actor_id, policy)

        return success and root_success

    async def _escalate_to_parent(self, actor_id: str, fault_event: FaultEvent) -> bool:
        """Escalate failure to parent actor"""
        if actor_id not in self.parent_map:
            logger.warning(f"No parent found for escalation from {actor_id}")
            return False

        parent_id = self.parent_map[actor_id]
        self.recovery_stats["escalations"] += 1

        logger.info(f"Escalating failure from {actor_id} to parent {parent_id}")

        # Create escalation fault for parent
        escalation_fault = FaultEvent(
            fault_id=f"escalation_{int(time.time() * 1000)}",
            fault_type=FaultType.ACTOR_CRASH,
            actor_id=parent_id,
            timestamp=time.time(),
            error_message=f"Child actor {actor_id} failed: {fault_event.error_message}",
            stack_trace=fault_event.stack_trace,
        )

        # Handle parent failure
        return await self.handle_actor_failure(
            parent_id, Exception(escalation_fault.error_message), FaultType.ACTOR_CRASH
        )

    async def _isolate_actor(self, actor_id: str) -> bool:
        """Isolate a problematic actor"""
        try:
            if actor_id in self.actor_system.actors:
                actor = self.actor_system.actors[actor_id]
                await actor.stop()

                # Remove from active actors but keep in supervision
                self.unhealthy_actors.add(actor_id)

                logger.info(f"Isolated actor {actor_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to isolate actor {actor_id}: {e}")
            return False

    async def _failover_to_backup(self, actor_id: str) -> bool:
        """Failover to backup actor (placeholder for future implementation)"""
        logger.info(f"Failover to backup not implemented for {actor_id}")
        return False

    def _get_recent_faults(
        self, actor_id: str, window_seconds: float
    ) -> List[FaultEvent]:
        """Get recent faults within time window"""
        if actor_id not in self.fault_history:
            return []

        current_time = time.time()
        return [
            fault
            for fault in self.fault_history[actor_id]
            if current_time - fault.timestamp <= window_seconds
        ]

    async def _recover_from_crash(self, actor_id: str, fault_event: FaultEvent) -> bool:
        """Recover from actor crash"""
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        return await self._restart_actor(actor_id, policy)

    async def _recover_from_timeout(
        self, actor_id: str, fault_event: FaultEvent
    ) -> bool:
        """Recover from message timeout"""
        # For timeouts, try restarting the actor
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        return await self._restart_actor(actor_id, policy)

    async def _recover_from_resource_exhaustion(
        self, actor_id: str, fault_event: FaultEvent
    ) -> bool:
        """Recover from resource exhaustion"""
        # Wait a bit for resources to free up, then restart
        await asyncio.sleep(5.0)
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        return await self._restart_actor(actor_id, policy)

    async def _recover_from_network_partition(
        self, actor_id: str, fault_event: FaultEvent
    ) -> bool:
        """Recover from network partition"""
        # Wait for network to recover, then restart
        await asyncio.sleep(10.0)
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        return await self._restart_actor(actor_id, policy)

    async def _recover_from_data_corruption(
        self, actor_id: str, fault_event: FaultEvent
    ) -> bool:
        """Recover from data corruption"""
        # For data corruption, restart the entire subtree
        return await self._restart_subtree(actor_id)

    async def _recover_from_service_failure(
        self, actor_id: str, fault_event: FaultEvent
    ) -> bool:
        """Recover from external service failure"""
        # Wait for service to recover, then restart
        await asyncio.sleep(15.0)
        policy = self.actor_policies.get(
            actor_id, SupervisionPolicy(SupervisionStrategy.RESTART)
        )
        return await self._restart_actor(actor_id, policy)

    async def health_check_loop(self):
        """Periodic health check loop"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)

    async def _perform_health_checks(self):
        """Perform health checks on all supervised actors"""
        current_time = time.time()

        for actor_id in list(self.actor_policies.keys()):
            try:
                # Check if actor is responsive
                if actor_id in self.actor_system.actors:
                    actor = self.actor_system.actors[actor_id]

                    # Simple health check - verify actor state
                    if actor.state in [ActorState.FAILED, ActorState.STOPPED]:
                        logger.warning(
                            f"Actor {actor_id} is in unhealthy state: {actor.state}"
                        )
                        await self.handle_actor_failure(
                            actor_id,
                            Exception(f"Actor in unhealthy state: {actor.state}"),
                            FaultType.ACTOR_CRASH,
                        )
                    else:
                        # Update health check timestamp
                        self.health_checks[actor_id] = current_time
                        self.unhealthy_actors.discard(actor_id)

            except Exception as e:
                logger.error(f"Health check failed for {actor_id}: {e}")
                await self.handle_actor_failure(actor_id, e, FaultType.ACTOR_CRASH)

    def get_supervision_status(self) -> Dict[str, Any]:
        """Get comprehensive supervision status"""
        return {
            "supervised_actors": len(self.actor_policies),
            "healthy_actors": len(self.actor_policies) - len(self.unhealthy_actors),
            "unhealthy_actors": len(self.unhealthy_actors),
            "circuit_breakers": {
                actor_id: {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time,
                }
                for actor_id, cb in self.circuit_breakers.items()
            },
            "recovery_stats": self.recovery_stats,
            "supervision_tree_depth": self._calculate_tree_depth(),
            "total_faults_last_hour": self._count_recent_faults(3600),
        }

    def _calculate_tree_depth(self) -> int:
        """Calculate maximum depth of supervision tree"""

        def get_depth(actor_id: str, visited: Set[str]) -> int:
            if actor_id in visited:
                return 0
            visited.add(actor_id)

            if actor_id not in self.supervision_tree:
                return 1

            max_child_depth = 0
            for child_id in self.supervision_tree[actor_id]:
                child_depth = get_depth(child_id, visited.copy())
                max_child_depth = max(max_child_depth, child_depth)

            return 1 + max_child_depth

        max_depth = 0
        root_actors = [
            actor_id
            for actor_id in self.actor_policies.keys()
            if actor_id not in self.parent_map
        ]

        for root_id in root_actors:
            depth = get_depth(root_id, set())
            max_depth = max(max_depth, depth)

        return max_depth

    def _count_recent_faults(self, seconds: float) -> int:
        """Count faults in recent time window"""
        current_time = time.time()
        count = 0

        for actor_faults in self.fault_history.values():
            for fault in actor_faults:
                if current_time - fault.timestamp <= seconds:
                    count += 1

        return count


class EnhancedCircuitBreaker:
    """Enhanced circuit breaker with multiple states"""

    class State(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = time.time()

    def record_success(self):
        """Record a successful operation"""
        self.failure_count = 0
        self.last_success_time = time.time()

        if self.state == self.State.HALF_OPEN:
            self.state = self.State.CLOSED

    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = self.State.OPEN

    def is_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.state == self.State.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.State.HALF_OPEN
                return False
            return True

        return False

    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        return not self.is_open()
