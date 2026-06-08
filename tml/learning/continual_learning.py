"""Continual learning techniques to prevent catastrophic forgetting."""

import copy
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from loguru import logger


@dataclass
class TaskMemory:
    """Memory structure for storing task-specific information."""

    task_id: str
    features: List[Dict[str, Any]]
    targets: List[Any]
    importance_weights: Optional[Dict[str, float]] = None
    fisher_information: Optional[Dict[str, float]] = None


class ContinualLearningStrategy(ABC):
    """Abstract base class for continual learning strategies."""

    @abstractmethod
    def before_task(self, task_id: str, model: Any) -> None:
        """Called before learning a new task."""
        pass

    @abstractmethod
    def after_task(self, task_id: str, model: Any) -> None:
        """Called after learning a task."""
        pass

    @abstractmethod
    def compute_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Compute regularized loss for continual learning."""
        pass


class ElasticWeightConsolidation(ContinualLearningStrategy):
    """Elastic Weight Consolidation (EWC) for preventing catastrophic forgetting."""

    def __init__(self, lambda_reg: float = 0.4, fisher_samples: int = 1000):
        self.lambda_reg = lambda_reg
        self.fisher_samples = fisher_samples
        self.task_memories: Dict[str, TaskMemory] = {}
        self.previous_params: Dict[str, torch.Tensor] = {}
        self.fisher_information: Dict[str, torch.Tensor] = {}

    def before_task(self, task_id: str, model: Any) -> None:
        """Prepare for learning a new task."""
        if hasattr(model, "parameters"):
            # Store current parameters for PyTorch models
            self.previous_params = {
                name: param.clone().detach()
                for name, param in model.named_parameters()
                if param.requires_grad
            }
        logger.info(f"EWC: Prepared for task {task_id}")

    def after_task(self, task_id: str, model: Any) -> None:
        """Compute Fisher Information Matrix after task completion."""
        if hasattr(model, "parameters"):
            self._compute_fisher_information(model, task_id)
        logger.info(f"EWC: Completed task {task_id}")

    def compute_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Compute EWC regularized loss."""
        if not self.fisher_information or not hasattr(model, "parameters"):
            return base_loss

        ewc_loss = 0.0
        for name, param in model.named_parameters():
            if name in self.fisher_information and name in self.previous_params:
                fisher = self.fisher_information[name]
                prev_param = self.previous_params[name]
                ewc_loss += (fisher * (param - prev_param) ** 2).sum()

        total_loss = base_loss + (self.lambda_reg / 2) * ewc_loss
        return total_loss.item() if hasattr(total_loss, "item") else total_loss

    def _compute_fisher_information(self, model: Any, task_id: str) -> None:
        """Compute Fisher Information Matrix for the current task."""
        if task_id not in self.task_memories:
            logger.warning(f"No memory found for task {task_id}")
            return

        memory = self.task_memories[task_id]
        model.eval()

        fisher_dict = {}
        for name, param in model.named_parameters():
            if param.requires_grad:
                fisher_dict[name] = torch.zeros_like(param)

        # Sample from task memory to compute Fisher Information
        sample_size = min(self.fisher_samples, len(memory.features))
        indices = np.random.choice(len(memory.features), sample_size, replace=False)

        for idx in indices:
            features = memory.features[idx]
            target = memory.targets[idx]

            # Convert to tensors (simplified - adapt based on your model)
            if isinstance(features, dict):
                # Convert dict features to tensor
                feature_tensor = torch.tensor(
                    [
                        float(v)
                        for v in features.values()
                        if isinstance(v, (int, float))
                    ],
                    dtype=torch.float32,
                )
            else:
                feature_tensor = torch.tensor(features, dtype=torch.float32)

            target_tensor = torch.tensor([target], dtype=torch.float32)

            # Forward pass
            model.zero_grad()
            output = model(feature_tensor.unsqueeze(0))
            loss = nn.functional.mse_loss(output, target_tensor.unsqueeze(0))

            # Backward pass
            loss.backward()

            # Accumulate squared gradients (Fisher Information)
            for name, param in model.named_parameters():
                if param.grad is not None:
                    fisher_dict[name] += param.grad.data**2

        # Average over samples
        for name in fisher_dict:
            fisher_dict[name] /= sample_size

        self.fisher_information.update(fisher_dict)
        model.train()

    def store_task_memory(
        self, task_id: str, features: List[Dict[str, Any]], targets: List[Any]
    ) -> None:
        """Store memory for a task."""
        self.task_memories[task_id] = TaskMemory(
            task_id=task_id, features=features, targets=targets
        )


class PackNet(ContinualLearningStrategy):
    """PackNet: Adding Multiple Tasks to a Single Network by Iterative Pruning."""

    def __init__(self, prune_ratio: float = 0.5):
        self.prune_ratio = prune_ratio
        self.task_masks: Dict[str, Dict[str, torch.Tensor]] = {}
        self.current_task_id: Optional[str] = None

    def before_task(self, task_id: str, model: Any) -> None:
        """Prepare for learning a new task."""
        self.current_task_id = task_id
        if hasattr(model, "parameters"):
            # Initialize mask for new task
            self.task_masks[task_id] = {}
            for name, param in model.named_parameters():
                if (
                    param.requires_grad and len(param.shape) > 1
                ):  # Only for weight matrices
                    self.task_masks[task_id][name] = torch.ones_like(param)
        logger.info(f"PackNet: Prepared for task {task_id}")

    def after_task(self, task_id: str, model: Any) -> None:
        """Prune network after task completion."""
        if hasattr(model, "parameters"):
            self._prune_network(model, task_id)
        logger.info(f"PackNet: Completed task {task_id}")

    def compute_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Apply task-specific masks during training."""
        if self.current_task_id and hasattr(model, "named_parameters"):
            self._apply_masks(model, self.current_task_id)
        return base_loss

    def _prune_network(self, model: Any, task_id: str) -> None:
        """Prune network weights for the current task."""
        if task_id not in self.task_masks:
            return

        for name, param in model.named_parameters():
            if name in self.task_masks[task_id]:
                # Calculate importance scores (magnitude-based pruning)
                importance = torch.abs(param.data)

                # Determine pruning threshold
                flat_importance = importance.flatten()
                threshold_idx = int(len(flat_importance) * self.prune_ratio)
                threshold = torch.kthvalue(flat_importance, threshold_idx).values

                # Create mask (keep important weights)
                mask = (importance >= threshold).float()

                # Update task mask
                self.task_masks[task_id][name] = mask

                # Apply mask to parameters
                param.data *= mask

    def _apply_masks(self, model: Any, task_id: str) -> None:
        """Apply task-specific masks to model parameters."""
        if task_id not in self.task_masks:
            return

        for name, param in model.named_parameters():
            if name in self.task_masks[task_id]:
                param.data *= self.task_masks[task_id][name]


class ExperienceReplay(ContinualLearningStrategy):
    """Experience Replay for continual learning."""

    def __init__(self, memory_size: int = 1000, replay_ratio: float = 0.2):
        self.memory_size = memory_size
        self.replay_ratio = replay_ratio
        self.memory_buffer: List[Tuple[Dict[str, Any], Any]] = []
        self.current_task_samples: List[Tuple[Dict[str, Any], Any]] = []

    def before_task(self, task_id: str, model: Any) -> None:
        """Prepare for learning a new task."""
        self.current_task_samples = []
        logger.info(f"Experience Replay: Prepared for task {task_id}")

    def after_task(self, task_id: str, model: Any) -> None:
        """Update memory buffer after task completion."""
        # Add samples from current task to memory buffer
        self.memory_buffer.extend(self.current_task_samples)

        # Maintain memory size limit
        if len(self.memory_buffer) > self.memory_size:
            # Random sampling to maintain diversity
            indices = np.random.choice(
                len(self.memory_buffer), self.memory_size, replace=False
            )
            self.memory_buffer = [self.memory_buffer[i] for i in indices]

        logger.info(f"Experience Replay: Memory buffer size: {len(self.memory_buffer)}")

    def compute_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Compute loss with experience replay."""
        # Store current sample
        self.current_task_samples.append((features, target))

        # No additional loss computation needed here
        # Replay samples should be mixed in during training
        return base_loss

    def get_replay_samples(self, batch_size: int) -> List[Tuple[Dict[str, Any], Any]]:
        """Get samples for experience replay."""
        if not self.memory_buffer:
            return []

        replay_size = int(batch_size * self.replay_ratio)
        if replay_size == 0:
            return []

        indices = np.random.choice(
            len(self.memory_buffer),
            min(replay_size, len(self.memory_buffer)),
            replace=False,
        )

        return [self.memory_buffer[i] for i in indices]


class ContinualLearningManager:
    """Manager for applying continual learning strategies."""

    def __init__(self, strategy: ContinualLearningStrategy):
        self.strategy = strategy
        self.current_task_id: Optional[str] = None
        self.task_history: List[str] = []

    def start_task(self, task_id: str, model: Any) -> None:
        """Start learning a new task."""
        if self.current_task_id:
            # Finish previous task
            self.finish_task(model)

        self.current_task_id = task_id
        self.strategy.before_task(task_id, model)
        logger.info(f"Started continual learning task: {task_id}")

    def finish_task(self, model: Any) -> None:
        """Finish the current task."""
        if self.current_task_id:
            self.strategy.after_task(self.current_task_id, model)
            self.task_history.append(self.current_task_id)
            logger.info(f"Finished continual learning task: {self.current_task_id}")
            self.current_task_id = None

    def compute_regularized_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Compute loss with continual learning regularization."""
        return self.strategy.compute_loss(model, features, target, base_loss)

    def get_task_history(self) -> List[str]:
        """Get history of completed tasks."""
        return self.task_history.copy()


class AdaptiveContinualLearner:
    """Adaptive continual learner that can switch strategies based on performance."""

    def __init__(self):
        self.strategies = {
            "ewc": ElasticWeightConsolidation(),
            "packnet": PackNet(),
            "replay": ExperienceReplay(),
        }
        self.current_strategy = "ewc"
        self.manager = ContinualLearningManager(self.strategies[self.current_strategy])
        self.performance_history: Dict[str, List[float]] = {}

    def switch_strategy(self, strategy_name: str) -> None:
        """Switch to a different continual learning strategy."""
        if strategy_name in self.strategies:
            self.current_strategy = strategy_name
            self.manager = ContinualLearningManager(self.strategies[strategy_name])
            logger.info(f"Switched to continual learning strategy: {strategy_name}")
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def evaluate_and_adapt(self, task_id: str, performance: float) -> None:
        """Evaluate performance and potentially adapt strategy."""
        if task_id not in self.performance_history:
            self.performance_history[task_id] = []

        self.performance_history[task_id].append(performance)

        # Simple adaptation logic: switch if performance is declining
        if len(self.performance_history[task_id]) >= 3:
            recent_perf = self.performance_history[task_id][-3:]
            if all(
                recent_perf[i] > recent_perf[i + 1] for i in range(len(recent_perf) - 1)
            ):
                # Performance is declining, try different strategy
                strategies = list(self.strategies.keys())
                current_idx = strategies.index(self.current_strategy)
                next_strategy = strategies[(current_idx + 1) % len(strategies)]

                logger.info(
                    f"Performance declining, switching from {self.current_strategy} to {next_strategy}"
                )
                self.switch_strategy(next_strategy)

    def start_task(self, task_id: str, model: Any) -> None:
        """Start learning a new task."""
        self.manager.start_task(task_id, model)

    def finish_task(self, model: Any) -> None:
        """Finish the current task."""
        self.manager.finish_task(model)

    def compute_regularized_loss(
        self, model: Any, features: Dict[str, Any], target: Any, base_loss: float
    ) -> float:
        """Compute loss with continual learning regularization."""
        return self.manager.compute_regularized_loss(model, features, target, base_loss)
