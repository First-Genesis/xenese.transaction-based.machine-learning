"""
Enhanced TML Platform v2.0 - Proto.Actor Test Suite

Comprehensive tests for the complete Proto.Actor implementation including
distributed processing, fault tolerance, and high-throughput performance.
"""

import asyncio
import random
import time
from typing import Any
from typing import Dict
from typing import List

import numpy as np
import pytest
import structlog

from .actor_system import Actor
from .actor_system import ActorMessage
from .actor_system import ActorState
from .actor_system import ActorSystem
from .actor_system import MessagePriority
from .actor_system import SupervisionDirective
from .actor_system import SupervisionStrategy
from .integration import TMLPlatform
from .integration import TMLPlatformBuilder
from .integration import TMLPlatformConfig
from .tml_actors import InheritanceCoordinatorActor
from .tml_actors import ModelActor
from .tml_actors import PhysicsValidatorActor
from .tml_actors import TMLMessageType
from .tml_actors import TransactionData
from .tml_actors import TransactionProcessorActor

logger = structlog.get_logger(__name__)


# Test fixtures
@pytest.fixture
async def actor_system():
    """Create and start an actor system for testing"""
    system = ActorSystem(node_id="test-node", redis_url="redis://localhost:6379")
    await system.start()
    yield system
    await system.stop()


@pytest.fixture
async def tml_platform():
    """Create and start a TML platform for testing"""
    platform = (
        TMLPlatformBuilder()
        .with_node_id("test-platform-node")
        .with_redis("redis://localhost:6379")
        .with_replicas(2, 5, 1)
        .build()
    )
    await platform.start()
    yield platform
    await platform.stop()


class TestActorSystem:
    """Test core actor system functionality"""

    @pytest.mark.asyncio
    async def test_actor_creation(self, actor_system):
        """Test basic actor creation and lifecycle"""

        # Create a simple test actor
        class TestActor(Actor):
            async def receive(self, message: ActorMessage) -> None:
                if message.reply_to:
                    response = ActorMessage(
                        recipient=message.reply_to, payload={"echo": message.payload}
                    )
                    await self.actor_system.deliver_message(response)

        # Create actor
        actor_ref = await actor_system.create_actor(TestActor, "test-actor-1")
        assert actor_ref is not None
        assert "test-actor-1" in actor_system.actors

        # Send message and get response
        message = ActorMessage(message_type="test", payload={"data": "test_value"})
        response = await actor_ref.ask(message, timeout=5.0)
        assert response["echo"]["data"] == "test_value"

    @pytest.mark.asyncio
    async def test_message_priority(self, actor_system):
        """Test message priority handling"""
        results = []

        class PriorityTestActor(Actor):
            async def receive(self, message: ActorMessage) -> None:
                results.append(message.payload["order"])

        actor_ref = await actor_system.create_actor(PriorityTestActor, "priority-actor")

        # Send messages with different priorities
        messages = [
            ActorMessage(payload={"order": 1}, priority=MessagePriority.LOW),
            ActorMessage(payload={"order": 2}, priority=MessagePriority.CRITICAL),
            ActorMessage(payload={"order": 3}, priority=MessagePriority.HIGH),
            ActorMessage(payload={"order": 4}, priority=MessagePriority.NORMAL),
        ]

        for msg in messages:
            await actor_ref.tell(msg)

        # Wait for processing
        await asyncio.sleep(1)

        # Critical and high priority should be processed first
        assert results[0] in [2, 3]  # Critical or High priority

    @pytest.mark.asyncio
    async def test_supervision_strategy(self, actor_system):
        """Test actor supervision and fault tolerance"""
        restart_count = [0]

        class FailingActor(Actor):
            async def receive(self, message: ActorMessage) -> None:
                if message.payload.get("fail", False):
                    raise Exception("Simulated failure")

            async def pre_start(self) -> None:
                restart_count[0] += 1

        # Create actor with restart supervision
        actor = FailingActor("failing-actor", actor_system)
        actor.supervision_directive = SupervisionDirective(
            SupervisionStrategy.RESTART, max_retries=3
        )
        actor_system.actors["failing-actor"] = actor
        await actor.start()

        # Send failing message
        fail_msg = ActorMessage(payload={"fail": True})
        await actor.mailbox.put(fail_msg)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Actor should still be running after failure
        assert actor.state in [ActorState.RUNNING, ActorState.RESTARTING]


class TestTMLActors:
    """Test TML-specific actors"""

    @pytest.mark.asyncio
    async def test_transaction_processor(self, actor_system):
        """Test transaction processing actor"""
        # Create transaction processor
        processor_ref = await actor_system.create_actor(
            TransactionProcessorActor, "tx-processor-1"
        )

        # Create transaction
        transaction = TransactionData(
            transaction_id="tx_001",
            data={"x_coord": 100, "y_coord": 200, "thickness": 20.5},
            timestamp=time.time(),
            source="test",
            metadata={},
        )

        # Process transaction
        message = ActorMessage(
            message_type=TMLMessageType.PROCESS_TRANSACTION.value,
            payload={"transaction": transaction.__dict__},
        )

        response = await processor_ref.ask(message, timeout=10.0)
        assert response["status"] == "success"
        assert response["transaction_id"] == "tx_001"

    @pytest.mark.asyncio
    async def test_model_actor_creation(self, actor_system):
        """Test model actor creation with inheritance"""
        # Create inheritance coordinator first
        await actor_system.create_actor(
            InheritanceCoordinatorActor, "inheritance_coordinator"
        )

        # Create physics validator
        await actor_system.create_actor(PhysicsValidatorActor, "physics_validator")

        # Create model actor
        model_ref = await actor_system.create_actor(ModelActor, "model_001")

        # Create model from transaction
        transaction = TransactionData(
            transaction_id="tx_001",
            data={"x_coord": 100, "y_coord": 200, "thickness": 20.5},
            timestamp=time.time(),
            source="test",
            metadata={},
        )

        message = ActorMessage(
            message_type=TMLMessageType.CREATE_MODEL.value,
            payload={"transaction": transaction.__dict__},
        )

        response = await model_ref.ask(message, timeout=10.0)
        assert response["status"] == "success"
        assert response["model_id"] == "model_001"
        assert "physics_valid" in response

    @pytest.mark.asyncio
    async def test_inheritance_chain(self, actor_system):
        """Test model inheritance chain"""
        # Create inheritance coordinator
        coordinator_ref = await actor_system.create_actor(
            InheritanceCoordinatorActor, "inheritance_coordinator"
        )

        # Create parent models
        for i in range(3):
            model_ref = await actor_system.create_actor(ModelActor, f"parent_model_{i}")

            # Register model
            register_msg = ActorMessage(
                message_type=TMLMessageType.MODEL_CREATED.value,
                payload={"model_id": f"parent_model_{i}", "parent_models": []},
            )
            await coordinator_ref.tell(register_msg)

        # Find parent models for new transaction
        transaction_data = {
            "transaction_id": "tx_new",
            "data": {"x_coord": 100, "y_coord": 200, "thickness": 20.0},
        }

        find_parents_msg = ActorMessage(
            message_type=TMLMessageType.FIND_PARENT_MODELS.value,
            payload={"transaction_data": transaction_data},
        )

        response = await coordinator_ref.ask(find_parents_msg, timeout=5.0)
        assert "parent_models" in response
        # Should find some parent models based on spatial proximity

    @pytest.mark.asyncio
    async def test_physics_validation(self, actor_system):
        """Test physics validation actor"""
        # Create physics validator
        validator_ref = await actor_system.create_actor(
            PhysicsValidatorActor, "physics_validator"
        )

        # Test valid physics
        valid_transaction = {
            "transaction_id": "tx_valid",
            "data": {"thickness": 20.0},  # Within valid range
        }

        validate_msg = ActorMessage(
            message_type=TMLMessageType.VALIDATE_PHYSICS.value,
            payload={"transaction_data": valid_transaction},
        )

        response = await validator_ref.ask(validate_msg, timeout=5.0)
        assert response["valid"] == True

        # Test invalid physics
        invalid_transaction = {
            "transaction_id": "tx_invalid",
            "data": {"thickness": 5.0},  # Below minimum
        }

        validate_msg = ActorMessage(
            message_type=TMLMessageType.VALIDATE_PHYSICS.value,
            payload={"transaction_data": invalid_transaction},
        )

        response = await validator_ref.ask(validate_msg, timeout=5.0)
        assert response["valid"] == False
        assert len(response["violations"]) > 0


class TestTMLPlatformIntegration:
    """Test complete TML platform integration"""

    @pytest.mark.asyncio
    async def test_platform_startup(self):
        """Test platform startup and initialization"""
        platform = TMLPlatform(
            TMLPlatformConfig(
                node_id="test-startup-node",
                enable_monitoring=False,
                enable_distributed=False,
            )
        )

        await platform.start()
        assert platform.is_running
        assert len(platform.transaction_processors) > 0
        assert len(platform.model_actors) > 0

        await platform.stop()
        assert not platform.is_running

    @pytest.mark.asyncio
    async def test_single_transaction_processing(self, tml_platform):
        """Test processing a single transaction"""
        transaction = {
            "id": "test_tx_001",
            "data": {
                "x_coord": 100,
                "y_coord": 200,
                "thickness": 20.5,
                "temperature": 25.0,
            },
            "source": "test",
            "metadata": {"test": True},
        }

        result = await tml_platform.process_transaction(transaction)
        assert result["status"] == "success"
        assert result["transaction_id"] == "test_tx_001"

    @pytest.mark.asyncio
    async def test_batch_transaction_processing(self, tml_platform):
        """Test batch transaction processing"""
        transactions = [
            {
                "id": f"batch_tx_{i}",
                "data": {
                    "x_coord": i * 10,
                    "y_coord": i * 20,
                    "thickness": 19.0 + random.random() * 2,
                    "temperature": 20.0 + random.random() * 10,
                },
                "source": "batch_test",
                "metadata": {"batch_id": "test_batch_001"},
            }
            for i in range(50)
        ]

        results = await tml_platform.batch_process_transactions(transactions)

        successful = sum(1 for r in results if r["status"] == "success")
        assert successful == len(transactions)

    @pytest.mark.asyncio
    async def test_platform_status(self, tml_platform):
        """Test platform status reporting"""
        status = await tml_platform.get_platform_status()

        assert "is_running" in status
        assert status["is_running"] == True
        assert "node_id" in status
        assert "actor_system" in status
        assert status["actor_system"]["transaction_processors"] > 0


class TestPerformance:
    """Performance and throughput tests"""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_throughput_performance(self):
        """Test platform throughput performance"""
        platform = (
            TMLPlatformBuilder()
            .with_node_id("perf-test-node")
            .with_replicas(10, 20, 5)
            .with_target_throughput(41000)
            .build()
        )

        await platform.start()

        try:
            # Generate test transactions
            num_transactions = 10000
            transactions = [
                {
                    "id": f"perf_tx_{i}",
                    "data": {
                        "x_coord": random.randint(0, 3700),
                        "y_coord": random.randint(0, 880),
                        "thickness": 15.0 + random.random() * 10,
                        "temperature": 20.0 + random.random() * 10,
                    },
                    "source": "performance_test",
                }
                for i in range(num_transactions)
            ]

            # Measure throughput
            start_time = time.time()

            # Process in batches for efficiency
            batch_size = 1000
            for i in range(0, num_transactions, batch_size):
                batch = transactions[i : i + batch_size]
                await platform.batch_process_transactions(batch)

            end_time = time.time()
            duration = end_time - start_time
            throughput = num_transactions / duration

            logger.info(
                "Throughput performance test",
                transactions=num_transactions,
                duration=duration,
                throughput_tps=throughput,
            )

            # Assert minimum throughput (accounting for test environment)
            assert throughput > 5000  # At least 5000 TPS in test environment

        finally:
            await platform.stop()

    @pytest.mark.asyncio
    async def test_latency_performance(self, tml_platform):
        """Test transaction processing latency"""
        latencies = []

        for i in range(100):
            transaction = {
                "id": f"latency_tx_{i}",
                "data": {"x_coord": 100, "y_coord": 200, "thickness": 20.0},
            }

            start = time.time()
            result = await tml_platform.process_transaction(transaction)
            end = time.time()

            if result["status"] == "success":
                latencies.append((end - start) * 1000)  # Convert to ms

        # Calculate statistics
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)

        logger.info(
            "Latency performance test",
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            samples=len(latencies),
        )

        # Assert latency requirements
        assert p50 < 10  # P50 under 10ms
        assert p95 < 50  # P95 under 50ms
        assert p99 < 100  # P99 under 100ms


class TestFaultTolerance:
    """Fault tolerance and resilience tests"""

    @pytest.mark.asyncio
    async def test_actor_failure_recovery(self, actor_system):
        """Test actor failure and recovery"""
        failures = [0]
        recoveries = [0]

        class ResilientActor(Actor):
            async def receive(self, message: ActorMessage) -> None:
                if message.payload.get("fail_count", 0) < 3:
                    failures[0] += 1
                    raise Exception(f"Simulated failure {failures[0]}")
                else:
                    if message.reply_to:
                        response = ActorMessage(
                            recipient=message.reply_to, payload={"recovered": True}
                        )
                        await self.actor_system.deliver_message(response)

            async def pre_start(self) -> None:
                recoveries[0] += 1

        # Create resilient actor with restart supervision
        actor_ref = await actor_system.create_actor(ResilientActor, "resilient-actor")

        # Send messages that will fail then succeed
        for i in range(4):
            message = ActorMessage(payload={"fail_count": i})

            if i == 3:  # Last one should succeed
                response = await actor_ref.ask(message, timeout=5.0)
                assert response["recovered"] == True
            else:
                await actor_ref.tell(message)
                await asyncio.sleep(0.5)

        # Verify failures and recoveries
        assert failures[0] == 3
        assert recoveries[0] >= 1  # At least one restart

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, actor_system):
        """Test circuit breaker functionality"""
        from .actor_system import CircuitBreaker

        circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

        # Function that fails initially
        call_count = [0]

        async def failing_function():
            call_count[0] += 1
            if call_count[0] <= 3:
                raise Exception("Service unavailable")
            return "Success"

        # Test circuit breaker opening
        for i in range(3):
            try:
                await circuit_breaker.call(failing_function)
            except:
                pass

        assert circuit_breaker.state == "open"

        # Circuit should be open, preventing calls
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await circuit_breaker.call(failing_function)

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Circuit should be half-open, allowing test call
        result = await circuit_breaker.call(failing_function)
        assert result == "Success"
        assert circuit_breaker.state == "closed"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
