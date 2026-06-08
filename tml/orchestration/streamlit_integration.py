"""
Streamlit-compatible Proto.Actor Integration

This module provides a simplified Proto.Actor integration that works
properly with Streamlit's event loop management.
"""

import asyncio
import threading
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import aioredis
import structlog
from concurrent.futures import ThreadPoolExecutor, Future
import queue

from .actor_system import ActorSystem
from .tml_actors import TransactionProcessorActor, ModelActor, PhysicsValidatorActor

logger = structlog.get_logger(__name__)


@dataclass
class StreamlitTMLConfig:
    """Configuration for Streamlit-compatible TML Platform"""

    node_id: str = "streamlit-node-01"
    redis_url: str = "redis://localhost:6379"
    transaction_processor_replicas: int = 2
    model_actor_replicas: int = 3
    physics_validator_replicas: int = 1
    use_thread_pool: bool = True
    max_workers: int = 4


class StreamlitTMLPlatform:
    """
    Streamlit-compatible TML Platform that handles event loop conflicts gracefully
    """

    def __init__(self, config: StreamlitTMLConfig = None):
        self.config = config or StreamlitTMLConfig()
        self.actor_system = None
        self.redis_client = None
        self.is_running = False
        self.transaction_processors = []
        self.model_actors = []
        self.physics_validator = None

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._async_thread = None
        self._loop = None
        self._startup_future = None

        logger.info("StreamlitTMLPlatform initialized", node_id=self.config.node_id)

    def start(self, timeout: float = 10.0) -> bool:
        """
        Start the platform in a way compatible with Streamlit

        Args:
            timeout: Maximum time to wait for startup

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            return True

        try:
            # Start platform in separate thread with its own event loop
            self._startup_future = Future()
            self._async_thread = threading.Thread(
                target=self._run_async_loop, daemon=True
            )
            self._async_thread.start()

            # Wait for startup to complete
            result = self._startup_future.result(timeout=timeout)

            if result:
                self.is_running = True
                logger.info("Platform started successfully")
                return True
            else:
                logger.error("Platform failed to start")
                return False

        except Exception as e:
            logger.error(f"Platform startup error: {e}")
            return False

    def _run_async_loop(self):
        """Run the async event loop in a separate thread"""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Start the platform
            self._loop.run_until_complete(self._async_start())

            # Keep the loop running for processing
            self._loop.run_forever()

        except Exception as e:
            logger.error(f"Async loop error: {e}")
            if self._startup_future and not self._startup_future.done():
                self._startup_future.set_result(False)
        finally:
            self._loop.close()

    async def _async_start(self):
        """Async startup routine"""
        try:
            # Initialize Redis connection
            self.redis_client = aioredis.from_url(self.config.redis_url)
            await self.redis_client.ping()

            # Initialize actor system
            self.actor_system = ActorSystem(
                node_id=self.config.node_id, redis_url=self.config.redis_url
            )
            await self.actor_system.start()

            # Deploy actors
            await self._deploy_actors()

            # Signal successful startup
            if self._startup_future:
                self._startup_future.set_result(True)

            logger.info("Async startup complete")

        except Exception as e:
            logger.error(f"Async startup error: {e}")
            if self._startup_future and not self._startup_future.done():
                self._startup_future.set_result(False)

    async def _deploy_actors(self):
        """Deploy the core actors"""
        # Deploy transaction processors
        for i in range(self.config.transaction_processor_replicas):
            actor_id = f"tx_processor_{i}"
            await self.actor_system.create_actor(TransactionProcessorActor, actor_id)
            self.transaction_processors.append(actor_id)

        # Deploy model actors
        for i in range(self.config.model_actor_replicas):
            actor_id = f"model_actor_{i}"
            await self.actor_system.create_actor(ModelActor, actor_id)
            self.model_actors.append(actor_id)

        # Deploy physics validator
        if self.config.physics_validator_replicas > 0:
            actor_id = "physics_validator"
            await self.actor_system.create_actor(PhysicsValidatorActor, actor_id)
            self.physics_validator = actor_id

        logger.info(
            "Actors deployed",
            tx_processors=len(self.transaction_processors),
            model_actors=len(self.model_actors),
        )

    def process_transaction_sync(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a transaction synchronously (for Streamlit)

        Args:
            transaction: Transaction to process

        Returns:
            Processing result
        """
        if not self.is_running:
            return {
                "status": "error",
                "transaction_id": transaction.get("id"),
                "error": "Platform not running",
            }

        try:
            # Submit async work to the platform's event loop
            future = asyncio.run_coroutine_threadsafe(
                self._process_transaction_async(transaction), self._loop
            )

            # Wait for result with timeout
            result = future.result(timeout=5.0)
            return result

        except Exception as e:
            logger.error(f"Transaction processing error: {e}")
            return {
                "status": "error",
                "transaction_id": transaction.get("id"),
                "error": str(e),
            }

    async def _process_transaction_async(
        self, transaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Async transaction processing"""
        if not self.transaction_processors:
            return {
                "status": "error",
                "transaction_id": transaction.get("id"),
                "error": "No transaction processors available",
            }

        # Round-robin processor selection
        processor_idx = hash(transaction.get("id", "")) % len(
            self.transaction_processors
        )
        processor_id = self.transaction_processors[processor_idx]

        # Get actor reference
        processor_ref = self.actor_system.get_actor_ref(processor_id)
        if not processor_ref:
            return {
                "status": "error",
                "transaction_id": transaction.get("id"),
                "error": "Processor not found",
            }

        # Create message and send to processor
        from .actor_system import ActorMessage
        from .tml_actors import TMLMessageType

        # Format transaction for Proto.Actor
        formatted_transaction = {
            "transaction_id": transaction.get("id", str(hash(str(transaction)))),
            "data": transaction.get("data", {}),
            "timestamp": transaction.get("timestamp", time.time()),
            "source": transaction.get("source", "streamlit"),
            "metadata": transaction.get("metadata", {}),
        }

        message = ActorMessage(
            sender="streamlit_client",
            recipient=processor_id,
            message_type=TMLMessageType.PROCESS_TRANSACTION.value,
            payload={"transaction": formatted_transaction},
        )

        # Use ask for request-response pattern
        result = await processor_ref.ask(message, timeout=5.0)

        # Validate physics if validator available
        if self.physics_validator and result.get("status") == "success":
            validator_ref = self.actor_system.get_actor_ref(self.physics_validator)
            if validator_ref:
                from .tml_actors import TMLMessageType

                physics_message = ActorMessage(
                    sender="streamlit_client",
                    recipient=self.physics_validator,
                    message_type=TMLMessageType.VALIDATE_PHYSICS.value,
                    payload={"transaction_data": {"data": transaction.get("data", {})}},
                )
                physics_result = await validator_ref.ask(physics_message, timeout=5.0)
                result["physics_valid"] = physics_result.get("valid", True)

        return result

    def batch_process_sync(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple transactions synchronously

        Args:
            transactions: List of transactions to process

        Returns:
            List of processing results
        """
        if not self.is_running:
            return [
                {
                    "status": "error",
                    "transaction_id": t.get("id"),
                    "error": "Platform not running",
                }
                for t in transactions
            ]

        try:
            # Submit batch to async loop
            future = asyncio.run_coroutine_threadsafe(
                self._batch_process_async(transactions), self._loop
            )

            # Wait for results
            results = future.result(timeout=30.0)
            return results

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return [
                {"status": "error", "transaction_id": t.get("id"), "error": str(e)}
                for t in transactions
            ]

    async def _batch_process_async(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Async batch processing"""
        tasks = [
            self._process_transaction_async(transaction) for transaction in transactions
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "status": "error",
                        "transaction_id": transactions[i].get("id"),
                        "error": str(result),
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    def get_status(self) -> Dict[str, Any]:
        """
        Get platform status (synchronous)

        Returns:
            Platform status information
        """
        return {
            "is_running": self.is_running,
            "node_id": self.config.node_id,
            "actor_system": {
                "total_actors": len(self.transaction_processors)
                + len(self.model_actors)
                + (1 if self.physics_validator else 0),
                "transaction_processors": len(self.transaction_processors),
                "model_actors": len(self.model_actors),
                "physics_validator": self.physics_validator is not None,
            },
        }

    def stop(self):
        """Stop the platform gracefully"""
        if not self.is_running:
            return

        try:
            # Stop the event loop
            if self._loop and self._loop.is_running():
                # Schedule stop
                asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop).result(
                    timeout=5.0
                )

                # Stop the loop
                self._loop.call_soon_threadsafe(self._loop.stop)

            # Wait for thread to finish
            if self._async_thread:
                self._async_thread.join(timeout=5.0)

            # Shutdown executor
            self.executor.shutdown(wait=True)

            self.is_running = False
            logger.info("Platform stopped")

        except Exception as e:
            logger.error(f"Error stopping platform: {e}")

    async def _async_stop(self):
        """Async cleanup"""
        try:
            if self.actor_system:
                await self.actor_system.stop()

            if self.redis_client:
                await self.redis_client.close()

        except Exception as e:
            logger.error(f"Async stop error: {e}")

    def __del__(self):
        """Cleanup on deletion"""
        if self.is_running:
            self.stop()
