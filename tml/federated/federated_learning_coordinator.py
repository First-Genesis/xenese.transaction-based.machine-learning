"""
Federated Learning Capabilities for TML Platform
Distributed learning across nodes with privacy preservation and spatial inheritance
"""

import asyncio
import numpy as np
import json
import time
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
import base64
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from loguru import logger

# For federated aggregation
from sklearn.base import BaseEstimator
import torch
import torch.nn as nn


class FederatedStrategy(Enum):
    """Federated learning strategies"""

    FEDERATED_AVERAGING = "federated_averaging"
    FEDERATED_SGD = "federated_sgd"
    SPATIAL_FEDERATED = "spatial_federated"
    ADAPTIVE_FEDERATED = "adaptive_federated"


class NodeRole(Enum):
    """Roles in federated learning"""

    COORDINATOR = "coordinator"
    PARTICIPANT = "participant"
    AGGREGATOR = "aggregator"


@dataclass
class FederatedNode:
    """Represents a node in the federated learning network"""

    node_id: str
    role: NodeRole
    address: str
    port: int
    public_key: str
    capabilities: Dict[str, Any]
    last_heartbeat: float
    is_active: bool
    data_samples: int
    model_version: int
    spatial_coordinates: Tuple[float, float]
    trust_score: float = 1.0


@dataclass
class ModelUpdate:
    """Represents a model update from a federated node"""

    node_id: str
    model_id: str
    update_data: bytes  # Encrypted model parameters
    metadata: Dict[str, Any]
    timestamp: float
    round_number: int
    data_samples: int
    validation_score: float
    signature: str
    spatial_weight: float = 1.0


@dataclass
class FederatedRound:
    """Represents a complete federated learning round"""

    round_number: int
    participating_nodes: List[str]
    aggregation_strategy: FederatedStrategy
    global_model_version: int
    updates_received: List[ModelUpdate]
    aggregated_model: Optional[bytes]
    performance_metrics: Dict[str, float]
    start_time: float
    end_time: Optional[float]
    convergence_score: float


@dataclass
class FederatedConfig:
    """Configuration for federated learning"""

    min_participants: int = 3
    max_participants: int = 100
    rounds_per_epoch: int = 10
    convergence_threshold: float = 0.001
    privacy_budget: float = 1.0
    differential_privacy: bool = True
    secure_aggregation: bool = True
    spatial_weighting: bool = True
    trust_threshold: float = 0.5
    timeout_seconds: int = 300


class SecureAggregator:
    """Secure aggregation with privacy preservation"""

    def __init__(self, privacy_budget: float = 1.0):
        self.privacy_budget = privacy_budget
        self.noise_scale = 1.0 / privacy_budget

    def add_differential_privacy_noise(self, parameters: np.ndarray) -> np.ndarray:
        """Add differential privacy noise to parameters"""
        noise = np.random.laplace(0, self.noise_scale, parameters.shape)
        return parameters + noise

    def secure_sum(
        self, parameter_list: List[np.ndarray], weights: List[float] = None
    ) -> np.ndarray:
        """Securely aggregate parameters with optional weighting"""
        if not parameter_list:
            return np.array([])

        if weights is None:
            weights = [1.0] * len(parameter_list)

        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Weighted sum
        aggregated = np.zeros_like(parameter_list[0])
        for params, weight in zip(parameter_list, normalized_weights):
            aggregated += params * weight

        return aggregated

    def federated_averaging(self, updates: List[ModelUpdate]) -> np.ndarray:
        """Standard federated averaging algorithm"""
        parameter_list = []
        weights = []

        for update in updates:
            # Decrypt and deserialize parameters
            params = self._deserialize_parameters(update.update_data)
            parameter_list.append(params)

            # Weight by number of data samples
            weights.append(update.data_samples)

        # Aggregate with sample-size weighting
        aggregated = self.secure_sum(parameter_list, weights)

        # Add differential privacy noise
        if len(updates) > 0:
            aggregated = self.add_differential_privacy_noise(aggregated)

        return aggregated

    def spatial_federated_averaging(
        self, updates: List[ModelUpdate], target_coordinates: Tuple[float, float] = None
    ) -> np.ndarray:
        """Spatial-aware federated averaging with inheritance weighting"""
        parameter_list = []
        weights = []

        for update in updates:
            params = self._deserialize_parameters(update.update_data)
            parameter_list.append(params)

            # Combine sample size and spatial weights
            base_weight = update.data_samples
            spatial_weight = update.spatial_weight

            # If target coordinates provided, calculate spatial similarity
            if target_coordinates and hasattr(update, "node_coordinates"):
                spatial_distance = np.linalg.norm(
                    np.array(target_coordinates) - np.array(update.node_coordinates)
                )
                spatial_similarity = 1.0 / (1.0 + spatial_distance)
                spatial_weight *= spatial_similarity

            combined_weight = base_weight * spatial_weight
            weights.append(combined_weight)

        # Aggregate with spatial weighting
        aggregated = self.secure_sum(parameter_list, weights)

        # Add privacy noise
        aggregated = self.add_differential_privacy_noise(aggregated)

        return aggregated

    def _serialize_parameters(self, parameters: np.ndarray) -> bytes:
        """Serialize parameters for transmission"""
        return pickle.dumps(parameters)

    def _deserialize_parameters(self, data: bytes) -> np.ndarray:
        """Deserialize parameters from transmission"""
        return pickle.loads(data)


class FederatedLearningCoordinator:
    """
    Federated Learning Coordinator for TML Platform
    Manages distributed learning across multiple nodes with spatial inheritance
    """

    def __init__(self, node_id: str, config: FederatedConfig = None):
        self.node_id = node_id
        self.config = config or FederatedConfig()

        # Network state
        self.nodes: Dict[str, FederatedNode] = {}
        self.active_rounds: Dict[str, FederatedRound] = {}
        self.completed_rounds: List[FederatedRound] = []

        # Security components
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.secure_aggregator = SecureAggregator(self.config.privacy_budget)

        # Model management
        self.global_models: Dict[str, bytes] = {}
        self.model_versions: Dict[str, int] = {}

        # Performance tracking
        self.federation_stats = {
            "total_rounds": 0,
            "successful_rounds": 0,
            "avg_participants": 0.0,
            "avg_convergence_time": 0.0,
            "privacy_budget_used": 0.0,
        }

        # Async components
        self.executor = ThreadPoolExecutor(max_workers=10)

        logger.info(f"Federated Learning Coordinator initialized: {node_id}")

    async def register_node(self, node: FederatedNode) -> bool:
        """Register a new node in the federation"""

        # Validate node capabilities
        if not self._validate_node_capabilities(node):
            logger.warning(f"Node {node.node_id} failed capability validation")
            return False

        # Check trust score
        if node.trust_score < self.config.trust_threshold:
            logger.warning(
                f"Node {node.node_id} below trust threshold: {node.trust_score}"
            )
            return False

        # Register node
        self.nodes[node.node_id] = node

        logger.info(
            f"Node registered: {node.node_id} ({node.role.value}) "
            f"with {node.data_samples} samples"
        )

        return True

    def _validate_node_capabilities(self, node: FederatedNode) -> bool:
        """Validate that node has required capabilities"""
        required_capabilities = ["model_training", "secure_communication"]

        for capability in required_capabilities:
            if capability not in node.capabilities:
                return False

        return True

    async def start_federated_round(
        self,
        model_id: str,
        strategy: FederatedStrategy = FederatedStrategy.SPATIAL_FEDERATED,
        target_coordinates: Tuple[float, float] = None,
    ) -> str:
        """Start a new federated learning round"""

        # Select participating nodes
        participants = self._select_participants(model_id, strategy)

        if len(participants) < self.config.min_participants:
            raise ValueError(
                f"Insufficient participants: {len(participants)} < {self.config.min_participants}"
            )

        # Create round
        round_number = len(self.completed_rounds) + len(self.active_rounds) + 1
        round_id = f"{model_id}_round_{round_number}"

        federated_round = FederatedRound(
            round_number=round_number,
            participating_nodes=[node.node_id for node in participants],
            aggregation_strategy=strategy,
            global_model_version=self.model_versions.get(model_id, 0),
            updates_received=[],
            aggregated_model=None,
            performance_metrics={},
            start_time=time.time(),
            end_time=None,
            convergence_score=0.0,
        )

        self.active_rounds[round_id] = federated_round

        # Send training requests to participants
        await self._send_training_requests(
            participants, model_id, round_id, target_coordinates
        )

        logger.info(
            f"Started federated round {round_id} with {len(participants)} participants"
        )

        return round_id

    def _select_participants(
        self, model_id: str, strategy: FederatedStrategy
    ) -> List[FederatedNode]:
        """Select nodes to participate in federated round"""

        # Get active nodes
        active_nodes = [
            node
            for node in self.nodes.values()
            if node.is_active and node.role == NodeRole.PARTICIPANT
        ]

        if strategy == FederatedStrategy.SPATIAL_FEDERATED:
            # Sort by spatial diversity and data quality
            active_nodes.sort(
                key=lambda n: (n.trust_score, n.data_samples), reverse=True
            )
        else:
            # Sort by data samples and trust score
            active_nodes.sort(
                key=lambda n: (n.data_samples, n.trust_score), reverse=True
            )

        # Select up to max_participants
        selected = active_nodes[: self.config.max_participants]

        return selected

    async def _send_training_requests(
        self,
        participants: List[FederatedNode],
        model_id: str,
        round_id: str,
        target_coordinates: Tuple[float, float] = None,
    ):
        """Send training requests to participating nodes"""

        # Get current global model
        global_model = self.global_models.get(model_id)

        # Send requests in parallel
        tasks = []
        for node in participants:
            task = asyncio.create_task(
                self._send_training_request(
                    node, model_id, round_id, global_model, target_coordinates
                )
            )
            tasks.append(task)

        # Wait for all requests to be sent
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_training_request(
        self,
        node: FederatedNode,
        model_id: str,
        round_id: str,
        global_model: Optional[bytes],
        target_coordinates: Tuple[float, float] = None,
    ):
        """Send training request to a specific node"""

        # Calculate spatial weight if coordinates provided
        spatial_weight = 1.0
        if target_coordinates and node.spatial_coordinates:
            spatial_distance = np.linalg.norm(
                np.array(target_coordinates) - np.array(node.spatial_coordinates)
            )
            spatial_weight = 1.0 / (1.0 + spatial_distance)

        # Create training request
        request = {
            "round_id": round_id,
            "model_id": model_id,
            "global_model": base64.b64encode(global_model).decode()
            if global_model
            else None,
            "spatial_weight": spatial_weight,
            "target_coordinates": target_coordinates,
            "timeout": self.config.timeout_seconds,
        }

        # In a real implementation, this would send via network
        logger.info(f"Training request sent to {node.node_id} for round {round_id}")

    async def receive_model_update(self, update: ModelUpdate) -> bool:
        """Receive and validate a model update from a participant"""

        # Find the corresponding round
        round_id = None
        for rid, round_obj in self.active_rounds.items():
            if update.node_id in round_obj.participating_nodes:
                round_id = rid
                break

        if not round_id:
            logger.warning(f"No active round found for update from {update.node_id}")
            return False

        # Validate update
        if not self._validate_model_update(update):
            logger.warning(f"Invalid update from {update.node_id}")
            return False

        # Add update to round
        federated_round = self.active_rounds[round_id]
        federated_round.updates_received.append(update)

        logger.info(
            f"Received update from {update.node_id} for round {round_id} "
            f"({len(federated_round.updates_received)}/{len(federated_round.participating_nodes)})"
        )

        # Check if round is complete
        if len(federated_round.updates_received) >= len(
            federated_round.participating_nodes
        ):
            await self._complete_federated_round(round_id)

        return True

    def _validate_model_update(self, update: ModelUpdate) -> bool:
        """Validate a model update for security and correctness"""

        # Check if node is registered
        if update.node_id not in self.nodes:
            return False

        node = self.nodes[update.node_id]

        # Check trust score
        if node.trust_score < self.config.trust_threshold:
            return False

        # Validate timestamp (not too old)
        if time.time() - update.timestamp > self.config.timeout_seconds:
            return False

        # Validate data samples
        if update.data_samples <= 0:
            return False

        # In a real implementation, would verify signature
        return True

    async def _complete_federated_round(self, round_id: str):
        """Complete a federated round by aggregating updates"""

        federated_round = self.active_rounds[round_id]

        try:
            # Aggregate model updates
            if (
                federated_round.aggregation_strategy
                == FederatedStrategy.SPATIAL_FEDERATED
            ):
                aggregated_params = self.secure_aggregator.spatial_federated_averaging(
                    federated_round.updates_received
                )
            else:
                aggregated_params = self.secure_aggregator.federated_averaging(
                    federated_round.updates_received
                )

            # Serialize aggregated model
            federated_round.aggregated_model = (
                self.secure_aggregator._serialize_parameters(aggregated_params)
            )

            # Update global model
            model_id = round_id.split("_round_")[0]
            self.global_models[model_id] = federated_round.aggregated_model
            self.model_versions[model_id] = self.model_versions.get(model_id, 0) + 1

            # Calculate performance metrics
            federated_round.performance_metrics = self._calculate_round_metrics(
                federated_round
            )

            # Calculate convergence score
            federated_round.convergence_score = self._calculate_convergence_score(
                federated_round
            )

            # Complete round
            federated_round.end_time = time.time()

            # Move to completed rounds
            self.completed_rounds.append(federated_round)
            del self.active_rounds[round_id]

            # Update statistics
            self._update_federation_stats(federated_round)

            logger.info(
                f"Completed federated round {round_id}: "
                f"convergence={federated_round.convergence_score:.4f}, "
                f"participants={len(federated_round.participating_nodes)}"
            )

            # Broadcast updated model to participants
            await self._broadcast_updated_model(
                model_id, federated_round.participating_nodes
            )

        except Exception as e:
            logger.error(f"Failed to complete federated round {round_id}: {e}")
            # Move failed round to completed with error status
            federated_round.end_time = time.time()
            federated_round.performance_metrics["error"] = str(e)
            self.completed_rounds.append(federated_round)
            del self.active_rounds[round_id]

    def _calculate_round_metrics(
        self, federated_round: FederatedRound
    ) -> Dict[str, float]:
        """Calculate performance metrics for a completed round"""

        metrics = {}

        # Participation metrics
        metrics["participation_rate"] = len(federated_round.updates_received) / len(
            federated_round.participating_nodes
        )

        # Data distribution metrics
        total_samples = sum(
            update.data_samples for update in federated_round.updates_received
        )
        metrics["total_samples"] = total_samples
        metrics["avg_samples_per_node"] = total_samples / len(
            federated_round.updates_received
        )

        # Performance metrics
        validation_scores = [
            update.validation_score for update in federated_round.updates_received
        ]
        metrics["avg_validation_score"] = np.mean(validation_scores)
        metrics["std_validation_score"] = np.std(validation_scores)

        # Timing metrics
        round_duration = federated_round.end_time - federated_round.start_time
        metrics["round_duration"] = round_duration

        # Spatial diversity (if applicable)
        if federated_round.aggregation_strategy == FederatedStrategy.SPATIAL_FEDERATED:
            spatial_weights = [
                update.spatial_weight for update in federated_round.updates_received
            ]
            metrics["spatial_diversity"] = np.std(spatial_weights)

        return metrics

    def _calculate_convergence_score(self, federated_round: FederatedRound) -> float:
        """Calculate convergence score for the round"""

        # Simple convergence metric based on validation score variance
        validation_scores = [
            update.validation_score for update in federated_round.updates_received
        ]

        if len(validation_scores) < 2:
            return 0.0

        # Lower variance indicates better convergence
        score_variance = np.var(validation_scores)
        convergence_score = 1.0 / (1.0 + score_variance)

        return convergence_score

    def _update_federation_stats(self, federated_round: FederatedRound):
        """Update federation statistics"""

        self.federation_stats["total_rounds"] += 1

        if federated_round.end_time:
            self.federation_stats["successful_rounds"] += 1

            # Update averages
            n_successful = self.federation_stats["successful_rounds"]

            # Average participants
            current_participants = len(federated_round.participating_nodes)
            self.federation_stats["avg_participants"] = (
                self.federation_stats["avg_participants"] * (n_successful - 1)
                + current_participants
            ) / n_successful

            # Average convergence time
            round_duration = federated_round.end_time - federated_round.start_time
            self.federation_stats["avg_convergence_time"] = (
                self.federation_stats["avg_convergence_time"] * (n_successful - 1)
                + round_duration
            ) / n_successful

    async def _broadcast_updated_model(
        self, model_id: str, participant_nodes: List[str]
    ):
        """Broadcast updated global model to participants"""

        updated_model = self.global_models.get(model_id)
        if not updated_model:
            return

        # Send updated model to each participant
        tasks = []
        for node_id in participant_nodes:
            if node_id in self.nodes:
                task = asyncio.create_task(
                    self._send_model_update(
                        self.nodes[node_id], model_id, updated_model
                    )
                )
                tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_model_update(
        self, node: FederatedNode, model_id: str, model_data: bytes
    ):
        """Send updated model to a specific node"""

        # In a real implementation, this would send via network
        logger.info(f"Updated model sent to {node.node_id} for model {model_id}")

    async def check_convergence(self, model_id: str) -> bool:
        """Check if federated learning has converged for a model"""

        # Get recent rounds for this model
        model_rounds = [
            round_obj
            for round_obj in self.completed_rounds[-10:]  # Last 10 rounds
            if round_obj.round_number > 0  # Valid rounds
        ]

        if len(model_rounds) < 3:
            return False

        # Check convergence based on recent convergence scores
        recent_scores = [round_obj.convergence_score for round_obj in model_rounds[-3:]]
        avg_convergence = np.mean(recent_scores)

        return avg_convergence > (1.0 - self.config.convergence_threshold)

    def get_federation_status(self) -> Dict[str, Any]:
        """Get comprehensive federation status"""

        active_nodes = [node for node in self.nodes.values() if node.is_active]

        return {
            "coordinator_id": self.node_id,
            "total_nodes": len(self.nodes),
            "active_nodes": len(active_nodes),
            "active_rounds": len(self.active_rounds),
            "completed_rounds": len(self.completed_rounds),
            "federation_stats": self.federation_stats,
            "global_models": list(self.global_models.keys()),
            "privacy_budget_remaining": max(
                0,
                self.config.privacy_budget
                - self.federation_stats["privacy_budget_used"],
            ),
            "node_distribution": {
                role.value: len([n for n in self.nodes.values() if n.role == role])
                for role in NodeRole
            },
        }

    def get_model_federation_history(self, model_id: str) -> List[Dict[str, Any]]:
        """Get federation history for a specific model"""

        model_rounds = [
            round_obj
            for round_obj in self.completed_rounds
            if model_id in round_obj.participating_nodes or True  # Simplified check
        ]

        history = []
        for round_obj in model_rounds:
            history.append(
                {
                    "round_number": round_obj.round_number,
                    "participants": len(round_obj.participating_nodes),
                    "convergence_score": round_obj.convergence_score,
                    "performance_metrics": round_obj.performance_metrics,
                    "duration": round_obj.end_time - round_obj.start_time
                    if round_obj.end_time
                    else None,
                    "strategy": round_obj.aggregation_strategy.value,
                }
            )

        return history

    async def update_node_trust_score(
        self, node_id: str, performance_feedback: Dict[str, float]
    ):
        """Update trust score for a node based on performance feedback"""

        if node_id not in self.nodes:
            return

        node = self.nodes[node_id]

        # Simple trust score update based on performance
        accuracy = performance_feedback.get("accuracy", 0.5)
        timeliness = performance_feedback.get("timeliness", 0.5)
        data_quality = performance_feedback.get("data_quality", 0.5)

        # Weighted average of performance factors
        performance_score = 0.4 * accuracy + 0.3 * timeliness + 0.3 * data_quality

        # Update trust score with exponential moving average
        alpha = 0.1  # Learning rate
        node.trust_score = (1 - alpha) * node.trust_score + alpha * performance_score

        # Ensure trust score stays in [0, 1]
        node.trust_score = max(0.0, min(1.0, node.trust_score))

        logger.info(f"Updated trust score for {node_id}: {node.trust_score:.3f}")

    async def shutdown(self):
        """Graceful shutdown of federated coordinator"""

        # Complete any active rounds
        for round_id in list(self.active_rounds.keys()):
            logger.info(f"Forcibly completing active round: {round_id}")
            await self._complete_federated_round(round_id)

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("Federated Learning Coordinator shutdown complete")

    def save_federation_state(self, filepath: str):
        """Save federation state for persistence"""

        state = {
            "node_id": self.node_id,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "completed_rounds": [asdict(r) for r in self.completed_rounds],
            "model_versions": self.model_versions,
            "federation_stats": self.federation_stats,
            "config": asdict(self.config),
        }

        with open(filepath, "w") as f:
            json.dump(state, f, default=str)

        # Save global models separately (binary data)
        models_path = filepath.replace(".json", "_models.pkl")
        with open(models_path, "wb") as f:
            pickle.dump(self.global_models, f)

        logger.info(f"Federation state saved to {filepath}")

    def load_federation_state(self, filepath: str):
        """Load federation state from persistence"""

        with open(filepath, "r") as f:
            state = json.load(f)

        # Restore basic state
        self.node_id = state["node_id"]
        self.model_versions = state["model_versions"]
        self.federation_stats = state["federation_stats"]

        # Restore nodes
        self.nodes = {}
        for node_id, node_data in state["nodes"].items():
            self.nodes[node_id] = FederatedNode(**node_data)

        # Restore completed rounds
        self.completed_rounds = []
        for round_data in state["completed_rounds"]:
            # Convert updates back to ModelUpdate objects
            updates = []
            for update_data in round_data.get("updates_received", []):
                updates.append(ModelUpdate(**update_data))
            round_data["updates_received"] = updates

            self.completed_rounds.append(FederatedRound(**round_data))

        # Load global models
        models_path = filepath.replace(".json", "_models.pkl")
        try:
            with open(models_path, "rb") as f:
                self.global_models = pickle.load(f)
        except FileNotFoundError:
            self.global_models = {}

        logger.info(f"Federation state loaded from {filepath}")


# Integration with TML Platform
class TMLFederatedLearningIntegration:
    """Integration layer for TML Platform federated learning"""

    def __init__(self, coordinator: FederatedLearningCoordinator):
        self.coordinator = coordinator
        self.spatial_inheritance_integration = True

    async def federated_spatial_inheritance(
        self,
        target_model_id: str,
        target_coordinates: Tuple[float, float],
        inheritance_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Perform federated learning with spatial inheritance awareness"""

        # Start federated round with spatial strategy
        round_id = await self.coordinator.start_federated_round(
            target_model_id, FederatedStrategy.SPATIAL_FEDERATED, target_coordinates
        )

        # Wait for round completion
        max_wait_time = self.coordinator.config.timeout_seconds * 2
        start_time = time.time()

        while round_id in self.coordinator.active_rounds:
            if time.time() - start_time > max_wait_time:
                logger.warning(f"Federated round {round_id} timed out")
                break
            await asyncio.sleep(1)

        # Get results
        completed_round = None
        for round_obj in self.coordinator.completed_rounds:
            if f"{target_model_id}_round_{round_obj.round_number}" == round_id:
                completed_round = round_obj
                break

        if completed_round:
            return {
                "round_id": round_id,
                "convergence_score": completed_round.convergence_score,
                "participants": len(completed_round.participating_nodes),
                "performance_metrics": completed_round.performance_metrics,
                "spatial_inheritance_applied": True,
                "global_model_updated": True,
            }
        else:
            return {
                "round_id": round_id,
                "error": "Round did not complete successfully",
                "spatial_inheritance_applied": False,
                "global_model_updated": False,
            }
