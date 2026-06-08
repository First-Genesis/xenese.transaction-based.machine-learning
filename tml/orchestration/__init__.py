"""
Enhanced TML Platform v2.0 - Proto.Actor Orchestration Layer

Complete production-ready actor system implementation with distributed processing,
high-throughput optimization, advanced fault tolerance, and comprehensive monitoring.
"""

from .actor_system import (
    ActorSystem,
    Actor,
    ActorRef,
    ActorMessage,
    ActorState,
    MessagePriority,
    SupervisionStrategy,
    SupervisionDirective,
    ClusterNode,
    ShardRegion,
    CircuitBreaker,
    EventSourcing,
)

from .tml_actors import (
    TransactionProcessorActor,
    ModelActor,
    InheritanceCoordinatorActor,
    PhysicsValidatorActor,
    ClusterManagerActor,
    TMLMessageType,
    TransactionData,
    ModelData,
)

from .cluster_manager import (
    TMLClusterManager,
    ServiceDiscovery,
    ServiceEndpoint,
    AutoScaler,
    ScalingRule,
    ScalingPolicy,
    DeploymentStrategy,
    ContainerOrchestrator,
)

from .monitoring import (
    TMLMonitoringSystem,
    TMLMetrics,
    DistributedTracing,
    AlertManager,
    Alert,
    AlertSeverity,
    PerformanceAnalyzer,
    MonitoringDashboard,
)

__version__ = "2.0.0"
__all__ = [
    # Actor System Core
    "ActorSystem",
    "Actor",
    "ActorRef",
    "ActorMessage",
    "ActorState",
    "MessagePriority",
    "SupervisionStrategy",
    "SupervisionDirective",
    "ClusterNode",
    "ShardRegion",
    "CircuitBreaker",
    "EventSourcing",
    # TML Actors
    "TransactionProcessorActor",
    "ModelActor",
    "InheritanceCoordinatorActor",
    "PhysicsValidatorActor",
    "ClusterManagerActor",
    "TMLMessageType",
    "TransactionData",
    "ModelData",
    # Cluster Management
    "TMLClusterManager",
    "ServiceDiscovery",
    "ServiceEndpoint",
    "AutoScaler",
    "ScalingRule",
    "ScalingPolicy",
    "DeploymentStrategy",
    "ContainerOrchestrator",
    # Monitoring
    "TMLMonitoringSystem",
    "TMLMetrics",
    "DistributedTracing",
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "PerformanceAnalyzer",
    "MonitoringDashboard",
]
