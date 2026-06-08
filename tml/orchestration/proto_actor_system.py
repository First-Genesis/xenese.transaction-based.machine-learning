"""
Proto.Actor System for TML Model Orchestration

This module implements the stateful orchestration layer using Proto.Actor
for managing millions of transaction-specific models with inheritance chains.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelInheritanceMessage:
    """Message for model inheritance coordination"""

    parent_model_id: str
    child_model_id: str
    transaction_data: Dict[str, Any]
    inheritance_weights: Dict[str, float]
    physics_constraints: Optional[Dict[str, Any]] = None


@dataclass
class TransactionProcessingMessage:
    """Message for processing individual transactions"""

    transaction_id: str
    model_id: str
    features: Dict[str, Any]
    target: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ModelStateSnapshot:
    """Model state for persistence"""

    model_id: str
    weights: Dict[str, Any]
    metadata: Dict[str, Any]
    parent_id: Optional[str]
    children_ids: List[str]
    creation_timestamp: datetime
    last_updated: datetime


class BaseActor(ABC):
    """Base actor class for TML system"""

    def __init__(self, actor_id: str):
        self.actor_id = actor_id
        self.mailbox: asyncio.Queue[Any] = asyncio.Queue()
        self.running = False

    async def start(self):
        """Start the actor message processing loop"""
        self.running = True
        while self.running:
            try:
                message = await asyncio.wait_for(self.mailbox.get(), timeout=1.0)
                await self.handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Actor {self.actor_id} error: {e}")

    async def stop(self):
        """Stop the actor"""
        self.running = False

    async def send_message(self, message: Any):
        """Send message to this actor"""
        await self.mailbox.put(message)

    @abstractmethod
    async def handle_message(self, message: Any):
        """Handle incoming messages - must be implemented by subclasses"""
        pass


class TransactionModelActor(BaseActor):
    """Actor representing a single transaction-specific model"""

    def __init__(self, model_id: str, parent_id: Optional[str] = None):
        super().__init__(model_id)
        self.model_id = model_id
        self.parent_id = parent_id
        self.children_ids: List[str] = []
        self.model_weights: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.physics_constraints: Dict[str, Any] = {}
        self.creation_time = datetime.now()
        self.last_updated = datetime.now()

    async def handle_message(self, message: Any):
        """Handle messages for model operations"""
        if isinstance(message, ModelInheritanceMessage):
            await self._handle_inheritance(message)
        elif isinstance(message, TransactionProcessingMessage):
            await self._handle_transaction_processing(message)
        elif isinstance(message, dict) and message.get("type") == "get_state":
            await self._handle_get_state(message)
        elif isinstance(message, dict) and message.get("type") == "snapshot":
            await self._handle_snapshot(message)
        else:
            logger.warning(f"Unknown message type: {type(message)}")

    async def _handle_inheritance(self, message: ModelInheritanceMessage):
        """Handle knowledge inheritance from parent model"""
        logger.info(f"Model {self.model_id} inheriting from {message.parent_model_id}")

        # Inherit weights from parent
        self.model_weights = message.inheritance_weights.copy()

        # Set parent relationship
        self.parent_id = message.parent_model_id

        # Inherit physics constraints
        if message.physics_constraints:
            self.physics_constraints = message.physics_constraints.copy()

        # Process the transaction that spawned this model
        if message.transaction_data:
            await self._learn_from_transaction(message.transaction_data)

        self.last_updated = datetime.now()

    async def _handle_transaction_processing(
        self, message: TransactionProcessingMessage
    ):
        """Handle processing of new transactions"""
        logger.info(
            f"Model {self.model_id} processing transaction {message.transaction_id}"
        )

        # Apply incremental learning
        await self._learn_from_transaction(
            {
                "features": message.features,
                "target": message.target,
                "context": message.context,
            }
        )

        self.last_updated = datetime.now()

    async def _learn_from_transaction(self, transaction_data: Dict[str, Any]):
        """Apply incremental learning from transaction data"""
        # This would integrate with the AI/ML layer
        # For now, simulate learning by updating metadata
        self.metadata["transactions_processed"] = (
            self.metadata.get("transactions_processed", 0) + 1
        )
        self.metadata["last_transaction"] = transaction_data

        # Apply EWC-based learning (placeholder)
        # In real implementation, this would call the learning algorithms
        logger.debug(f"Model {self.model_id} learned from transaction")

    async def _handle_get_state(self, message: Dict[str, Any]):
        """Return current model state"""
        state = {
            "model_id": self.model_id,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "weights": self.model_weights,
            "metadata": self.metadata,
            "physics_constraints": self.physics_constraints,
            "creation_time": self.creation_time.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }

        # Send response back (in real implementation, would use proper actor messaging)
        if "response_queue" in message:
            await message["response_queue"].put(state)

    async def _handle_snapshot(self, message: Dict[str, Any]):
        """Create model snapshot for persistence"""
        snapshot = ModelStateSnapshot(
            model_id=self.model_id,
            weights=self.model_weights,
            metadata=self.metadata,
            parent_id=self.parent_id,
            children_ids=self.children_ids,
            creation_timestamp=self.creation_time,
            last_updated=self.last_updated,
        )

        # In real implementation, would persist to storage
        logger.info(f"Created snapshot for model {self.model_id}")

        if "response_queue" in message:
            await message["response_queue"].put(snapshot)


class ModelSupervisorActor(BaseActor):
    """Supervisor actor for managing model actor lifecycle"""

    def __init__(self):
        super().__init__("model_supervisor")
        self.model_actors: Dict[str, TransactionModelActor] = {}
        self.model_lineage: Dict[str, str] = {}  # child_id -> parent_id
        self.active_models: set = set()

    async def handle_message(self, message: Any):
        """Handle supervisor messages"""
        if isinstance(message, dict):
            msg_type = message.get("type")

            if msg_type == "spawn_model":
                await self._spawn_model(message)
            elif msg_type == "get_model":
                await self._get_model(message)
            elif msg_type == "deactivate_model":
                await self._deactivate_model(message)
            elif msg_type == "get_lineage":
                await self._get_lineage(message)
            else:
                logger.warning(f"Unknown supervisor message type: {msg_type}")

    async def _spawn_model(self, message: Dict[str, Any]):
        """Spawn a new model actor with inheritance"""
        model_id = message["model_id"]
        parent_id = message.get("parent_id")
        transaction_data = message.get("transaction_data", {})

        logger.info(f"Spawning model {model_id} with parent {parent_id}")

        # Create new model actor
        model_actor = TransactionModelActor(model_id, parent_id)
        self.model_actors[model_id] = model_actor

        # Start the actor
        asyncio.create_task(model_actor.start())

        # Set up inheritance if parent exists
        if parent_id and parent_id in self.model_actors:
            parent_actor = self.model_actors[parent_id]

            # Get parent state for inheritance
            response_queue: asyncio.Queue[Any] = asyncio.Queue()
            await parent_actor.send_message(
                {"type": "get_state", "response_queue": response_queue}
            )

            try:
                parent_state = await asyncio.wait_for(response_queue.get(), timeout=5.0)

                # Send inheritance message to new model
                inheritance_msg = ModelInheritanceMessage(
                    parent_model_id=parent_id,
                    child_model_id=model_id,
                    transaction_data=transaction_data,
                    inheritance_weights=parent_state.get("weights", {}),
                    physics_constraints=parent_state.get("physics_constraints", {}),
                )

                await model_actor.send_message(inheritance_msg)

                # Update lineage tracking
                self.model_lineage[model_id] = parent_id
                parent_actor.children_ids.append(model_id)

            except asyncio.TimeoutError:
                logger.error(f"Timeout getting parent state for model {model_id}")

        self.active_models.add(model_id)

        # Send response if requested
        if "response_queue" in message:
            await message["response_queue"].put(
                {"status": "success", "model_id": model_id}
            )

    async def _get_model(self, message: Dict[str, Any]):
        """Get reference to model actor"""
        model_id = message["model_id"]

        if model_id in self.model_actors:
            model_actor = self.model_actors[model_id]
            if "response_queue" in message:
                await message["response_queue"].put(model_actor)
        else:
            if "response_queue" in message:
                await message["response_queue"].put(None)

    async def _deactivate_model(self, message: Dict[str, Any]):
        """Deactivate a model actor (move to cold storage)"""
        model_id = message["model_id"]

        if model_id in self.model_actors:
            model_actor = self.model_actors[model_id]

            # Create snapshot before deactivation
            response_queue: asyncio.Queue[Any] = asyncio.Queue()
            await model_actor.send_message(
                {"type": "snapshot", "response_queue": response_queue}
            )

            try:
                snapshot = await asyncio.wait_for(response_queue.get(), timeout=5.0)
                # In real implementation, would persist snapshot to cold storage
                logger.info(f"Deactivated model {model_id}, snapshot created")

                # Stop the actor
                await model_actor.stop()
                del self.model_actors[model_id]
                self.active_models.discard(model_id)

            except asyncio.TimeoutError:
                logger.error(f"Timeout creating snapshot for model {model_id}")

    async def _get_lineage(self, message: Dict[str, Any]):
        """Get model lineage chain"""
        model_id = message["model_id"]
        lineage = []

        current_id = model_id
        while current_id and current_id in self.model_lineage:
            lineage.append(current_id)
            current_id = self.model_lineage[current_id]

        if current_id:  # Add the root model
            lineage.append(current_id)

        lineage.reverse()  # Return from root to current

        if "response_queue" in message:
            await message["response_queue"].put(lineage)


class TMLActorSystem:
    """Main TML Actor System orchestrating all components"""

    def __init__(self):
        self.supervisor = ModelSupervisorActor()
        self.running = False

    async def start(self):
        """Start the actor system"""
        self.running = True

        # Start supervisor
        asyncio.create_task(self.supervisor.start())

        logger.info("TML Actor System started")

    async def stop(self):
        """Stop the actor system"""
        self.running = False
        await self.supervisor.stop()

        logger.info("TML Actor System stopped")

    async def spawn_transaction_model(
        self,
        transaction_id: str,
        parent_model_id: Optional[str] = None,
        transaction_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Spawn a new model for a transaction"""
        model_id = f"model_{transaction_id}"

        response_queue: asyncio.Queue[Any] = asyncio.Queue()
        await self.supervisor.send_message(
            {
                "type": "spawn_model",
                "model_id": model_id,
                "parent_id": parent_model_id,
                "transaction_data": transaction_data or {},
                "response_queue": response_queue,
            }
        )

        try:
            result = await asyncio.wait_for(response_queue.get(), timeout=10.0)
            return result["model_id"]
        except asyncio.TimeoutError:
            raise Exception(f"Timeout spawning model for transaction {transaction_id}")

    async def process_transaction(
        self, model_id: str, transaction_data: Dict[str, Any]
    ):
        """Process a transaction with an existing model"""
        response_queue: asyncio.Queue[Any] = asyncio.Queue()
        await self.supervisor.send_message(
            {
                "type": "get_model",
                "model_id": model_id,
                "response_queue": response_queue,
            }
        )

        try:
            model_actor = await asyncio.wait_for(response_queue.get(), timeout=5.0)
            if model_actor:
                processing_msg = TransactionProcessingMessage(
                    transaction_id=transaction_data.get("transaction_id", "unknown"),
                    model_id=model_id,
                    features=transaction_data.get("features", {}),
                    target=transaction_data.get("target"),
                    context=transaction_data.get("context", {}),
                )
                await model_actor.send_message(processing_msg)
            else:
                raise Exception(f"Model {model_id} not found")

        except asyncio.TimeoutError:
            raise Exception(f"Timeout processing transaction for model {model_id}")

    async def get_model_lineage(self, model_id: str) -> List[str]:
        """Get the inheritance lineage for a model"""
        response_queue: asyncio.Queue[Any] = asyncio.Queue()
        await self.supervisor.send_message(
            {
                "type": "get_lineage",
                "model_id": model_id,
                "response_queue": response_queue,
            }
        )

        try:
            lineage = await asyncio.wait_for(response_queue.get(), timeout=5.0)
            return lineage
        except asyncio.TimeoutError:
            raise Exception(f"Timeout getting lineage for model {model_id}")


# Example usage and testing
async def main():
    """Example usage of the TML Actor System"""
    system = TMLActorSystem()
    await system.start()

    try:
        # Spawn first model (no parent)
        model_1 = await system.spawn_transaction_model("txn_001")
        print(f"Created model: {model_1}")

        # Spawn second model inheriting from first
        model_2 = await system.spawn_transaction_model(
            "txn_002", parent_model_id=model_1
        )
        print(f"Created model: {model_2}")

        # Process some transactions
        await system.process_transaction(
            model_1,
            {
                "transaction_id": "txn_001_update",
                "features": {"amount": 100.0, "merchant": "grocery"},
                "target": 0.95,
            },
        )

        # Get lineage
        lineage = await system.get_model_lineage(model_2)
        print(f"Model lineage: {lineage}")

    finally:
        await system.stop()


if __name__ == "__main__":
    asyncio.run(main())
