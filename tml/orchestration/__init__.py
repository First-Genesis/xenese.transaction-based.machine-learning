"""
Enhanced TML Platform v2.0 - Proto.Actor Orchestration Layer

Complete production-ready actor system implementation with distributed processing,
high-throughput optimization, advanced fault tolerance, and comprehensive monitoring.
"""

from .actor_system import (Actor, ActorMessage, ActorRef, ActorState,
                           ActorSystem, CircuitBreaker, ClusterNode,
                           EventSourcing, MessagePriority, ShardRegion,
                           SupervisionDirective, SupervisionStrategy)
from .cluster_manager import (AutoScaler, ContainerOrchestrator,
                              DeploymentStrategy, ScalingPolicy, ScalingRule,
                              ServiceDiscovery, ServiceEndpoint,
                              TMLClusterManager)
from .monitoring import (Alert, AlertManager, AlertSeverity,
                         DistributedTracing, MonitoringDashboard,
                         PerformanceAnalyzer, TMLMetrics, TMLMonitoringSystem)
from .tml_actors import (ClusterManagerActor, InheritanceCoordinatorActor,
                         ModelActor, ModelData, PhysicsValidatorActor,
                         TMLMessageType, TransactionData,
                         TransactionProcessorActor)

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
