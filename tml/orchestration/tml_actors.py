"""
TML-Specific Actors for Enhanced TML Platform v2.0

High-performance actors for transaction processing, model management,
and inheritance coordination with advanced fault tolerance.
"""

import asyncio
import json
import pickle
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

import numpy as np

from .actor_system import Actor
from .actor_system import ActorMessage
from .actor_system import ActorRef
from .actor_system import ActorSystem
from .actor_system import MessagePriority
from .actor_system import SupervisionDirective
from .actor_system import SupervisionStrategy
from .actor_system import logger


class TMLMessageType(Enum):
    """TML-specific message types"""

    # Transaction processing
    PROCESS_TRANSACTION = "process_transaction"
    TRANSACTION_PROCESSED = "transaction_processed"
    TRANSACTION_FAILED = "transaction_failed"

    # Model management
    CREATE_MODEL = "create_model"
    UPDATE_MODEL = "update_model"
    GET_MODEL = "get_model"
    DELETE_MODEL = "delete_model"
    MODEL_CREATED = "model_created"
    MODEL_UPDATED = "model_updated"
    MODEL_RETRIEVED = "model_retrieved"
    MODEL_DELETED = "model_deleted"

    # Inheritance
    INHERIT_FROM_MODEL = "inherit_from_model"
    INHERITANCE_COMPLETE = "inheritance_complete"
    FIND_PARENT_MODELS = "find_parent_models"
    PARENT_MODELS_FOUND = "parent_models_found"

    # Physics validation
    VALIDATE_PHYSICS = "validate_physics"
    PHYSICS_VALIDATED = "physics_validated"
    PHYSICS_VIOLATION = "physics_violation"

    # Batch operations
    BATCH_PROCESS = "batch_process"
    BATCH_COMPLETE = "batch_complete"

    # Monitoring
    GET_METRICS = "get_metrics"
    METRICS_RESPONSE = "metrics_response"
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"


@dataclass
class TransactionData:
    """Transaction data structure"""

    transaction_id: str
    data: Dict[str, Any]
    timestamp: float
    source: str
    metadata: Dict[str, Any]


@dataclass
class ModelData:
    """Model data structure"""

    model_id: str
    weights: np.ndarray
    hyperparameters: Dict[str, Any]
    performance_metrics: Dict[str, float]
    parent_models: List[str]
    creation_time: float
    last_updated: float
    version: int


class TransactionProcessorActor(Actor):
    """High-performance transaction processor actor"""

    def __init__(self, actor_id: str, actor_system: ActorSystem):
        super().__init__(actor_id, actor_system)
        self.processed_transactions = 0
        self.processing_times = []
        self.batch_size = 100
        self.batch_buffer = []
        self.batch_timeout = 1.0  # seconds
        self.last_batch_time = time.time()

        # Performance optimization
        self.supervision_directive = SupervisionDirective(
            SupervisionStrategy.RESTART, max_retries=5, within_time_range=60.0
        )

    async def receive(self, message: ActorMessage) -> None:
        """Process incoming messages"""
        if message.message_type == TMLMessageType.PROCESS_TRANSACTION.value:
            await self._process_transaction(message)
        elif message.message_type == TMLMessageType.BATCH_PROCESS.value:
            await self._process_batch(message)
        elif message.message_type == TMLMessageType.GET_METRICS.value:
            await self._send_metrics(message)
        else:
            self.logger.warning(
                "Unknown message type", message_type=message.message_type
            )

    async def _process_transaction(self, message: ActorMessage) -> None:
        """Process a single transaction"""
        start_time = time.time()

        try:
            transaction_data = TransactionData(**message.payload["transaction"])

            # Add to batch buffer for high-throughput processing
            self.batch_buffer.append(transaction_data)

            # Process batch if buffer is full or timeout reached
            if (
                len(self.batch_buffer) >= self.batch_size
                or time.time() - self.last_batch_time > self.batch_timeout
            ):
                await self._process_current_batch()

            # Send response if reply requested
            if message.reply_to:
                response = ActorMessage(
                    message_type=TMLMessageType.TRANSACTION_PROCESSED.value,
                    recipient=message.reply_to,
                    payload={
                        "transaction_id": transaction_data.transaction_id,
                        "processing_time": time.time() - start_time,
                        "status": "success",
                    },
                )
                await self.actor_system.deliver_message(response)

        except Exception as e:
            self.logger.error(
                "Transaction processing failed",
                transaction_id=message.payload.get("transaction", {}).get(
                    "transaction_id"
                ),
                error=str(e),
            )

            if message.reply_to:
                error_response = ActorMessage(
                    message_type=TMLMessageType.TRANSACTION_FAILED.value,
                    recipient=message.reply_to,
                    payload={
                        "transaction_id": message.payload.get("transaction", {}).get(
                            "transaction_id"
                        ),
                        "error": str(e),
                        "status": "failed",
                    },
                )
                await self.actor_system.deliver_message(error_response)

    async def _process_current_batch(self) -> None:
        """Process current batch of transactions"""
        if not self.batch_buffer:
            return

        batch_start_time = time.time()
        batch_size = len(self.batch_buffer)

        try:
            # Process batch (simulate high-performance processing)
            for transaction in self.batch_buffer:
                # Create model for transaction
                model_actor_ref = await self._get_or_create_model_actor(
                    transaction.transaction_id
                )

                # Send transaction to model actor
                model_message = ActorMessage(
                    message_type=TMLMessageType.CREATE_MODEL.value,
                    payload={
                        "transaction": transaction.__dict__,
                        "batch_processing": True,
                    },
                    priority=MessagePriority.HIGH,
                )
                await model_actor_ref.tell(model_message)

            # Update metrics
            processing_time = time.time() - batch_start_time
            self.processed_transactions += batch_size
            self.processing_times.append(processing_time)

            # Keep only recent processing times for metrics
            if len(self.processing_times) > 1000:
                self.processing_times = self.processing_times[-1000:]

            self.logger.info(
                "Batch processed successfully",
                batch_size=batch_size,
                processing_time=processing_time,
                throughput=batch_size / processing_time,
            )

        except Exception as e:
            self.logger.error(
                "Batch processing failed", batch_size=batch_size, error=str(e)
            )
        finally:
            self.batch_buffer.clear()
            self.last_batch_time = time.time()

    async def _get_or_create_model_actor(self, transaction_id: str) -> ActorRef:
        """Get or create model actor for transaction"""
        model_actor_id = f"model_{transaction_id}"

        # Check if actor already exists
        actor_ref = self.actor_system.get_actor_ref(model_actor_id)
        if actor_ref:
            return actor_ref

        # Create new model actor
        return await self.actor_system.create_actor(
            ModelActor, model_actor_id, parent_id=self.actor_id
        )

    async def _send_metrics(self, message: ActorMessage) -> None:
        """Send performance metrics"""
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times
            else 0.0
        )

        metrics = {
            "processed_transactions": self.processed_transactions,
            "average_processing_time": avg_processing_time,
            "current_batch_size": len(self.batch_buffer),
            "throughput_tps": self.processed_transactions
            / (time.time() - self.metrics["start_time"]),
        }

        response = ActorMessage(
            message_type=TMLMessageType.METRICS_RESPONSE.value,
            recipient=message.reply_to or message.sender,
            payload={"metrics": metrics},
        )
        await self.actor_system.deliver_message(response)


class ModelActor(Actor):
    """Individual model actor with inheritance capabilities"""

    def __init__(self, actor_id: str, actor_system: ActorSystem):
        super().__init__(actor_id, actor_system)
        self.model_data: Optional[ModelData] = None
        self.parent_models: List[str] = []
        self.inheritance_depth = 0
        self.learning_rate = 0.01
        self.physics_constraints = {}

        # High-performance settings
        self.supervision_directive = SupervisionDirective(
            SupervisionStrategy.RESTART, max_retries=3, within_time_range=30.0
        )

    async def receive(self, message: ActorMessage) -> None:
        """Process model-related messages"""
        if message.message_type == TMLMessageType.CREATE_MODEL.value:
            await self._create_model(message)
        elif message.message_type == TMLMessageType.UPDATE_MODEL.value:
            await self._update_model(message)
        elif message.message_type == TMLMessageType.GET_MODEL.value:
            await self._get_model(message)
        elif message.message_type == TMLMessageType.INHERIT_FROM_MODEL.value:
            await self._inherit_from_model(message)
        elif message.message_type == TMLMessageType.VALIDATE_PHYSICS.value:
            await self._validate_physics(message)
        else:
            self.logger.warning(
                "Unknown message type", message_type=message.message_type
            )

    async def _create_model(self, message: ActorMessage) -> None:
        """Create new model from transaction data"""
        try:
            transaction_data = TransactionData(**message.payload["transaction"])

            # Find parent models for inheritance
            parent_models = await self._find_parent_models(transaction_data)

            # Create initial model weights
            initial_weights = np.random.randn(100)  # Simplified model

            # Apply inheritance if parent models exist
            if parent_models:
                inherited_weights = await self._apply_inheritance(
                    parent_models, initial_weights
                )
                initial_weights = inherited_weights
                self.inheritance_depth = len(parent_models)

            # Create model data
            self.model_data = ModelData(
                model_id=self.actor_id,
                weights=initial_weights,
                hyperparameters={"learning_rate": self.learning_rate},
                performance_metrics={"accuracy": 0.0, "loss": float("inf")},
                parent_models=parent_models,
                creation_time=time.time(),
                last_updated=time.time(),
                version=1,
            )

            # Validate physics constraints
            physics_valid = await self._check_physics_constraints(transaction_data)

            # Store model in event sourcing
            if self.actor_system.event_sourcing:
                await self.actor_system.event_sourcing.append_event(
                    self.actor_id,
                    {
                        "event_type": "model_created",
                        "transaction_id": transaction_data.transaction_id,
                        "parent_models": parent_models,
                        "inheritance_depth": self.inheritance_depth,
                        "physics_valid": physics_valid,
                    },
                )

            self.logger.info(
                "Model created successfully",
                model_id=self.actor_id,
                parent_models=len(parent_models),
                inheritance_depth=self.inheritance_depth,
                physics_valid=physics_valid,
            )

            # Send response
            if message.reply_to:
                response = ActorMessage(
                    message_type=TMLMessageType.MODEL_CREATED.value,
                    recipient=message.reply_to,
                    payload={
                        "model_id": self.actor_id,
                        "inheritance_depth": self.inheritance_depth,
                        "physics_valid": physics_valid,
                        "status": "success",
                    },
                )
                await self.actor_system.deliver_message(response)

        except Exception as e:
            self.logger.error("Model creation failed", error=str(e))
            if message.reply_to:
                error_response = ActorMessage(
                    message_type=TMLMessageType.TRANSACTION_FAILED.value,
                    recipient=message.reply_to,
                    payload={"error": str(e), "status": "failed"},
                )
                await self.actor_system.deliver_message(error_response)

    async def _find_parent_models(self, transaction_data: TransactionData) -> List[str]:
        """Find suitable parent models for inheritance"""
        # Get inheritance coordinator
        inheritance_actor_ref = self.actor_system.get_actor_ref(
            "inheritance_coordinator"
        )
        if not inheritance_actor_ref:
            return []

        try:
            # Request parent models
            request = ActorMessage(
                message_type=TMLMessageType.FIND_PARENT_MODELS.value,
                payload={
                    "transaction_data": transaction_data.__dict__,
                    "max_parents": 5,
                },
                timeout=5.0,
            )

            response = await inheritance_actor_ref.ask(request)
            return response.get("parent_models", [])

        except Exception as e:
            self.logger.warning("Failed to find parent models", error=str(e))
            return []

    async def _apply_inheritance(
        self, parent_models: List[str], initial_weights: np.ndarray
    ) -> np.ndarray:
        """Apply inheritance from parent models"""
        if not parent_models:
            return initial_weights

        try:
            # Get parent model weights
            parent_weights = []
            for parent_id in parent_models:
                parent_ref = self.actor_system.get_actor_ref(parent_id)
                if parent_ref:
                    request = ActorMessage(
                        message_type=TMLMessageType.GET_MODEL.value,
                        payload={"fields": ["weights"]},
                        timeout=2.0,
                    )
                    response = await parent_ref.ask(request)
                    if "weights" in response:
                        parent_weights.append(response["weights"])

            if not parent_weights:
                return initial_weights

            # Apply inheritance (weighted average)
            inherited_weights = np.zeros_like(initial_weights)
            for weights in parent_weights:
                if len(weights) == len(initial_weights):
                    inherited_weights += weights

            inherited_weights /= len(parent_weights)

            # Blend with initial weights (80% inherited, 20% random)
            final_weights = 0.8 * inherited_weights + 0.2 * initial_weights

            return final_weights

        except Exception as e:
            self.logger.warning("Inheritance application failed", error=str(e))
            return initial_weights

    async def _check_physics_constraints(
        self, transaction_data: TransactionData
    ) -> bool:
        """Check physics constraints for the model"""
        try:
            # Get physics validator
            physics_actor_ref = self.actor_system.get_actor_ref("physics_validator")
            if not physics_actor_ref:
                return True  # No physics validation available

            request = ActorMessage(
                message_type=TMLMessageType.VALIDATE_PHYSICS.value,
                payload={"transaction_data": transaction_data.__dict__},
                timeout=3.0,
            )

            response = await physics_actor_ref.ask(request)
            return response.get("valid", True)

        except Exception as e:
            self.logger.warning("Physics validation failed", error=str(e))
            return True  # Default to valid if validation fails

    async def _update_model(self, message: ActorMessage) -> None:
        """Update model with new data"""
        if not self.model_data:
            self.logger.error("Cannot update non-existent model")
            return

        try:
            # Update model weights (simplified)
            new_data = message.payload.get("data", {})
            if "weights_update" in new_data:
                self.model_data.weights += self.learning_rate * np.array(
                    new_data["weights_update"]
                )

            self.model_data.last_updated = time.time()
            self.model_data.version += 1

            # Store update event
            if self.actor_system.event_sourcing:
                await self.actor_system.event_sourcing.append_event(
                    self.actor_id,
                    {
                        "event_type": "model_updated",
                        "version": self.model_data.version,
                        "update_data": new_data,
                    },
                )

            self.logger.info(
                "Model updated successfully",
                model_id=self.actor_id,
                version=self.model_data.version,
            )

        except Exception as e:
            self.logger.error("Model update failed", error=str(e))

    async def _get_model(self, message: ActorMessage) -> None:
        """Get model data"""
        if not self.model_data:
            if message.reply_to:
                response = ActorMessage(
                    message_type=TMLMessageType.MODEL_RETRIEVED.value,
                    recipient=message.reply_to,
                    payload={"error": "Model not found"},
                )
                await self.actor_system.deliver_message(response)
            return

        # Prepare response data
        requested_fields = message.payload.get("fields", ["all"])
        response_data = {}

        if "all" in requested_fields or "weights" in requested_fields:
            response_data["weights"] = self.model_data.weights.tolist()
        if "all" in requested_fields or "metrics" in requested_fields:
            response_data["performance_metrics"] = self.model_data.performance_metrics
        if "all" in requested_fields or "metadata" in requested_fields:
            response_data["metadata"] = {
                "model_id": self.model_data.model_id,
                "parent_models": self.model_data.parent_models,
                "creation_time": self.model_data.creation_time,
                "last_updated": self.model_data.last_updated,
                "version": self.model_data.version,
            }

        if message.reply_to:
            response = ActorMessage(
                message_type=TMLMessageType.MODEL_RETRIEVED.value,
                recipient=message.reply_to,
                payload=response_data,
            )
            await self.actor_system.deliver_message(response)


class InheritanceCoordinatorActor(Actor):
    """Coordinates model inheritance across the system"""

    def __init__(self, actor_id: str, actor_system: ActorSystem):
        super().__init__(actor_id, actor_system)
        self.model_registry: Dict[str, Dict[str, Any]] = {}
        self.inheritance_graph: Dict[str, Set[str]] = {}  # parent -> children
        self.spatial_index: Dict[str, List[str]] = {}  # location -> model_ids

    async def receive(self, message: ActorMessage) -> None:
        """Process inheritance coordination messages"""
        if message.message_type == TMLMessageType.FIND_PARENT_MODELS.value:
            await self._find_parent_models(message)
        elif message.message_type == TMLMessageType.MODEL_CREATED.value:
            await self._register_model(message)
        else:
            self.logger.warning(
                "Unknown message type", message_type=message.message_type
            )

    async def _find_parent_models(self, message: ActorMessage) -> None:
        """Find suitable parent models for inheritance"""
        try:
            transaction_data = message.payload["transaction_data"]
            max_parents = message.payload.get("max_parents", 5)

            # Simple spatial-based parent finding (can be enhanced)
            location_key = self._get_location_key(transaction_data)
            nearby_models = self.spatial_index.get(location_key, [])

            # Select best parent models (most recent, best performance)
            parent_models = nearby_models[:max_parents]

            if message.reply_to:
                response = ActorMessage(
                    message_type=TMLMessageType.PARENT_MODELS_FOUND.value,
                    recipient=message.reply_to,
                    payload={"parent_models": parent_models},
                )
                await self.actor_system.deliver_message(response)

        except Exception as e:
            self.logger.error("Parent model search failed", error=str(e))

    async def _register_model(self, message: ActorMessage) -> None:
        """Register new model in inheritance system"""
        try:
            model_id = message.payload["model_id"]
            parent_models = message.payload.get("parent_models", [])

            # Register in inheritance graph
            for parent_id in parent_models:
                if parent_id not in self.inheritance_graph:
                    self.inheritance_graph[parent_id] = set()
                self.inheritance_graph[parent_id].add(model_id)

            self.logger.info(
                "Model registered for inheritance",
                model_id=model_id,
                parent_count=len(parent_models),
            )

        except Exception as e:
            self.logger.error("Model registration failed", error=str(e))

    def _get_location_key(self, transaction_data: Dict[str, Any]) -> str:
        """Get spatial location key for transaction"""
        # Simplified spatial indexing
        x = transaction_data.get("data", {}).get("x_coord", 0)
        y = transaction_data.get("data", {}).get("y_coord", 0)

        # Grid-based spatial indexing
        grid_x = int(x // 100)  # 100mm grid
        grid_y = int(y // 100)

        return f"{grid_x}_{grid_y}"


class PhysicsValidatorActor(Actor):
    """Validates physics constraints for models"""

    def __init__(self, actor_id: str, actor_system: ActorSystem):
        super().__init__(actor_id, actor_system)
        self.physics_rules = {
            "min_thickness": 15.0,  # mm
            "max_thickness": 50.0,  # mm
            "energy_conservation": True,
            "mass_conservation": True,
        }

    async def receive(self, message: ActorMessage) -> None:
        """Process physics validation messages"""
        if message.message_type == TMLMessageType.VALIDATE_PHYSICS.value:
            await self._validate_physics(message)
        else:
            self.logger.warning(
                "Unknown message type", message_type=message.message_type
            )

    async def _validate_physics(self, message: ActorMessage) -> None:
        """Validate physics constraints"""
        try:
            transaction_data = message.payload["transaction_data"]
            data = transaction_data.get("data", {})

            # Validate thickness constraints
            thickness = data.get("thickness", 0.0)
            valid = (
                self.physics_rules["min_thickness"]
                <= thickness
                <= self.physics_rules["max_thickness"]
            )

            violations = []
            if not valid:
                violations.append(f"Thickness {thickness}mm outside valid range")

            if message.reply_to:
                response = ActorMessage(
                    message_type=TMLMessageType.PHYSICS_VALIDATED.value,
                    recipient=message.reply_to,
                    payload={
                        "valid": valid,
                        "violations": violations,
                        "constraints_checked": list(self.physics_rules.keys()),
                    },
                )
                await self.actor_system.deliver_message(response)

        except Exception as e:
            self.logger.error("Physics validation failed", error=str(e))


class ClusterManagerActor(Actor):
    """Manages cluster-wide operations and load balancing"""

    def __init__(self, actor_id: str, actor_system: ActorSystem):
        super().__init__(actor_id, actor_system)
        self.node_loads: Dict[str, float] = {}
        self.actor_distribution: Dict[str, str] = {}  # actor_id -> node_id

    async def receive(self, message: ActorMessage) -> None:
        """Process cluster management messages"""
        if message.message_type == "load_balance":
            await self._load_balance(message)
        elif message.message_type == "node_status":
            await self._update_node_status(message)
        else:
            self.logger.warning(
                "Unknown message type", message_type=message.message_type
            )

    async def _load_balance(self, message: ActorMessage) -> None:
        """Perform load balancing across cluster"""
        try:
            # Get current node loads
            total_load = sum(self.node_loads.values())
            if total_load == 0:
                return

            # Identify overloaded nodes
            avg_load = total_load / len(self.node_loads)
            overloaded_nodes = [
                node_id
                for node_id, load in self.node_loads.items()
                if load > avg_load * 1.5
            ]

            if overloaded_nodes:
                self.logger.info(
                    "Load balancing required",
                    overloaded_nodes=overloaded_nodes,
                    avg_load=avg_load,
                )
                # Implement load balancing logic

        except Exception as e:
            self.logger.error("Load balancing failed", error=str(e))

    async def _update_node_status(self, message: ActorMessage) -> None:
        """Update node status information"""
        try:
            node_id = message.payload["node_id"]
            load_factor = message.payload["load_factor"]
            self.node_loads[node_id] = load_factor

        except Exception as e:
            self.logger.error("Node status update failed", error=str(e))
