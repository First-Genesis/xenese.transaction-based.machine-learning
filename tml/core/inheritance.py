"""
Advanced Spatial Model Inheritance for TML Platform

This module implements the proprietary spatial inheritance algorithms that enable
models to learn from spatially and contextually similar predecessor models.

Copyright (c) 2024 First Genesis. All rights reserved.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import time
import logging
from sklearn.neighbors import KDTree
from scipy.spatial.distance import euclidean
import json

logger = logging.getLogger(__name__)


@dataclass
class SpatialContext:
    """
    Spatial and contextual information for inheritance decisions.

    This class encapsulates all the information needed to determine
    which models should inherit from which predecessors.
    """

    x_coord: float
    y_coord: float
    z_coord: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    domain: str = "general"
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> np.ndarray:
        """Convert spatial context to vector for similarity computation."""
        vector = [self.x_coord, self.y_coord]

        if self.z_coord is not None:
            vector.append(self.z_coord)

        # Add normalized timestamp (hours since epoch)
        vector.append(self.timestamp / 3600.0)

        return np.array(vector)

    def distance_to(self, other: "SpatialContext") -> float:
        """Calculate Euclidean distance to another spatial context."""
        return euclidean(self.to_vector(), other.to_vector())


class SimilarityCalculator:
    """
    Advanced similarity calculation for spatial inheritance.

    Uses multiple metrics to determine how similar two spatial contexts are,
    enabling intelligent inheritance decisions.
    """

    def __init__(
        self,
        spatial_weight: float = 0.4,
        temporal_weight: float = 0.3,
        domain_weight: float = 0.2,
        feature_weight: float = 0.1,
    ):
        self.spatial_weight = spatial_weight
        self.temporal_weight = temporal_weight
        self.domain_weight = domain_weight
        self.feature_weight = feature_weight

    def calculate_similarity(
        self, context1: SpatialContext, context2: SpatialContext
    ) -> float:
        """
        Calculate comprehensive similarity between two spatial contexts.

        Returns:
            float: Similarity score between 0 and 1 (1 = identical)
        """
        # Spatial similarity (inverse of normalized distance)
        spatial_dist = context1.distance_to(context2)
        max_spatial_dist = 1000.0  # Normalize to reasonable range
        spatial_sim = max(0, 1 - (spatial_dist / max_spatial_dist))

        # Temporal similarity (inverse of time difference)
        time_diff = abs(context1.timestamp - context2.timestamp)
        max_time_diff = 86400.0  # 24 hours in seconds
        temporal_sim = max(0, 1 - (time_diff / max_time_diff))

        # Domain similarity (exact match or related domains)
        domain_sim = 1.0 if context1.domain == context2.domain else 0.3

        # Feature similarity (cosine similarity of feature vectors)
        feature_sim = self._calculate_feature_similarity(
            context1.features, context2.features
        )

        # Weighted combination
        total_similarity = (
            self.spatial_weight * spatial_sim
            + self.temporal_weight * temporal_sim
            + self.domain_weight * domain_sim
            + self.feature_weight * feature_sim
        )

        return min(1.0, max(0.0, total_similarity))

    def _calculate_feature_similarity(
        self, features1: Dict[str, Any], features2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between feature dictionaries."""
        if not features1 or not features2:
            return 0.0

        # Convert to normalized vectors
        all_keys = set(features1.keys()) | set(features2.keys())

        vec1 = []
        vec2 = []

        for key in all_keys:
            val1 = features1.get(key, 0)
            val2 = features2.get(key, 0)

            # Convert to numeric if possible
            try:
                val1 = float(val1)
                val2 = float(val2)
            except (ValueError, TypeError):
                val1 = hash(str(val1)) % 1000 / 1000.0
                val2 = hash(str(val2)) % 1000 / 1000.0

            vec1.append(val1)
            vec2.append(val2)

        # Normalize vectors
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
            return 0.0

        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)

        # Cosine similarity
        return max(0.0, np.dot(vec1_norm, vec2_norm))


class SpatialInheritanceEngine:
    """
    Core engine for spatial model inheritance.

    This is the heart of the TML platform's spatial inheritance system,
    using advanced algorithms to determine optimal inheritance relationships.
    """

    def __init__(
        self,
        max_parents: int = 5,
        similarity_threshold: float = 0.3,
        inheritance_decay: float = 0.9,
    ):
        self.max_parents = max_parents
        self.similarity_threshold = similarity_threshold
        self.inheritance_decay = inheritance_decay
        self.similarity_calculator = SimilarityCalculator()
        self.model_contexts: Dict[str, SpatialContext] = {}
        self.spatial_index: Optional[KDTree] = None
        self.model_ids: List[str] = []

    def register_model(self, model_id: str, context: SpatialContext):
        """Register a new model with its spatial context."""
        self.model_contexts[model_id] = context
        self._rebuild_spatial_index()

    def _rebuild_spatial_index(self):
        """Rebuild the KD-tree spatial index for efficient neighbor search."""
        if len(self.model_contexts) < 2:
            return

        contexts = list(self.model_contexts.values())
        vectors = [ctx.to_vector() for ctx in contexts]
        self.model_ids = list(self.model_contexts.keys())

        try:
            self.spatial_index = KDTree(vectors)
        except Exception as e:
            logger.warning(f"Failed to build spatial index: {e}")
            self.spatial_index = None

    def find_parent_models(
        self, context: SpatialContext, exclude_models: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Find the best parent models for inheritance.

        Returns:
            List of (model_id, similarity_score) tuples, sorted by similarity
        """
        if not self.model_contexts:
            return []

        exclude_models = exclude_models or []
        candidates = []

        # Use spatial index for efficient neighbor search if available
        if self.spatial_index and len(self.model_contexts) > 10:
            candidates = self._find_spatial_neighbors(context, exclude_models)
        else:
            # Brute force search for smaller datasets
            for model_id, model_context in self.model_contexts.items():
                if model_id in exclude_models:
                    continue

                similarity = self.similarity_calculator.calculate_similarity(
                    context, model_context
                )

                if similarity >= self.similarity_threshold:
                    candidates.append((model_id, similarity))

        # Sort by similarity (descending) and limit to max_parents
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[: self.max_parents]

    def _find_spatial_neighbors(
        self, context: SpatialContext, exclude_models: List[str]
    ) -> List[Tuple[str, float]]:
        """Use KD-tree to find spatial neighbors efficiently."""
        if not self.spatial_index:
            return []

        query_vector = context.to_vector().reshape(1, -1)

        # Find k nearest neighbors (k = max_parents * 3 for filtering)
        k = min(len(self.model_ids), self.max_parents * 3)
        distances, indices = self.spatial_index.query(query_vector, k=k)

        candidates = []
        for dist, idx in zip(distances[0], indices[0]):
            model_id = self.model_ids[idx]

            if model_id in exclude_models:
                continue

            # Calculate full similarity (not just spatial distance)
            model_context = self.model_contexts[model_id]
            similarity = self.similarity_calculator.calculate_similarity(
                context, model_context
            )

            if similarity >= self.similarity_threshold:
                candidates.append((model_id, similarity))

        return candidates

    def calculate_inheritance_weights(
        self, parent_similarities: List[Tuple[str, float]]
    ) -> Dict[str, float]:
        """
        Calculate inheritance weights for parent models.

        Uses softmax normalization to ensure weights sum to 1.
        """
        if not parent_similarities:
            return {}

        # Apply decay to similarities
        decayed_similarities = [
            (model_id, sim * (self.inheritance_decay**i))
            for i, (model_id, sim) in enumerate(parent_similarities)
        ]

        # Softmax normalization
        similarities = [sim for _, sim in decayed_similarities]
        exp_sims = np.exp(
            np.array(similarities) - np.max(similarities)
        )  # Numerical stability
        softmax_weights = exp_sims / np.sum(exp_sims)

        return {
            model_id: weight
            for (model_id, _), weight in zip(decayed_similarities, softmax_weights)
        }


class AdaptiveInheritance:
    """
    Adaptive inheritance strategy that learns from model performance.

    Adjusts inheritance parameters based on how well inherited models perform.
    """

    def __init__(self, learning_rate: float = 0.01):
        self.learning_rate = learning_rate
        self.performance_history: Dict[str, List[float]] = {}
        self.inheritance_success: Dict[str, float] = {}

    def record_performance(self, model_id: str, performance_score: float):
        """Record performance score for a model."""
        if model_id not in self.performance_history:
            self.performance_history[model_id] = []

        self.performance_history[model_id].append(performance_score)

        # Keep only recent history
        if len(self.performance_history[model_id]) > 100:
            self.performance_history[model_id] = self.performance_history[model_id][
                -100:
            ]

    def update_inheritance_success(
        self,
        child_model_id: str,
        parent_model_ids: List[str],
        performance_improvement: float,
    ):
        """Update inheritance success rates based on performance improvement."""
        for parent_id in parent_model_ids:
            if parent_id not in self.inheritance_success:
                self.inheritance_success[parent_id] = 0.5  # Neutral start

            # Update using exponential moving average
            current_success = self.inheritance_success[parent_id]
            new_success = current_success + self.learning_rate * (
                performance_improvement - current_success
            )
            self.inheritance_success[parent_id] = max(0.0, min(1.0, new_success))

    def get_adaptive_similarity_threshold(self, base_threshold: float = 0.3) -> float:
        """Get adaptive similarity threshold based on historical success."""
        if not self.inheritance_success:
            return base_threshold

        avg_success = np.mean(list(self.inheritance_success.values()))

        # Adjust threshold based on average success
        if avg_success > 0.7:
            return (
                base_threshold * 0.8
            )  # Lower threshold if inheritance is working well
        elif avg_success < 0.3:
            return (
                base_threshold * 1.2
            )  # Higher threshold if inheritance is not working
        else:
            return base_threshold

    def get_model_inheritance_score(self, model_id: str) -> float:
        """Get inheritance score for a model (how good it is as a parent)."""
        return self.inheritance_success.get(model_id, 0.5)


# Main inheritance coordinator
class SpatialInheritanceCoordinator:
    """
    Main coordinator for the spatial inheritance system.

    Orchestrates all components to provide a unified inheritance interface.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}

        self.engine = SpatialInheritanceEngine(
            max_parents=config.get("max_parents", 5),
            similarity_threshold=config.get("similarity_threshold", 0.3),
            inheritance_decay=config.get("inheritance_decay", 0.9),
        )

        self.adaptive = AdaptiveInheritance(
            learning_rate=config.get("learning_rate", 0.01)
        )

        self.inheritance_history: Dict[str, Dict[str, Any]] = {}

    def process_inheritance(
        self, model_id: str, context: SpatialContext
    ) -> Dict[str, Any]:
        """
        Process inheritance for a new model.

        Returns:
            Dictionary containing inheritance information
        """
        # Register the model
        self.engine.register_model(model_id, context)

        # Get adaptive threshold
        threshold = self.adaptive.get_adaptive_similarity_threshold(
            self.engine.similarity_threshold
        )

        # Find parent models
        parents = self.engine.find_parent_models(context)

        # Calculate inheritance weights
        weights = self.engine.calculate_inheritance_weights(parents)

        # Record inheritance decision
        inheritance_info = {
            "model_id": model_id,
            "context": context,
            "parents": parents,
            "weights": weights,
            "threshold_used": threshold,
            "timestamp": time.time(),
        }

        self.inheritance_history[model_id] = inheritance_info

        return inheritance_info

    def update_model_performance(self, model_id: str, performance_score: float):
        """Update performance information for adaptive learning."""
        self.adaptive.record_performance(model_id, performance_score)

        # Update inheritance success if this model inherited from others
        if model_id in self.inheritance_history:
            inheritance_info = self.inheritance_history[model_id]
            parent_ids = [parent_id for parent_id, _ in inheritance_info["parents"]]

            if parent_ids:
                # Calculate performance improvement (simplified)
                baseline_performance = 0.5  # Assume baseline
                improvement = performance_score - baseline_performance

                self.adaptive.update_inheritance_success(
                    model_id, parent_ids, improvement
                )

    def get_inheritance_statistics(self) -> Dict[str, Any]:
        """Get statistics about the inheritance system."""
        return {
            "total_models": len(self.engine.model_contexts),
            "inheritance_decisions": len(self.inheritance_history),
            "avg_parents_per_model": (
                np.mean(
                    [len(info["parents"]) for info in self.inheritance_history.values()]
                )
                if self.inheritance_history
                else 0
            ),
            "inheritance_success_rates": dict(self.adaptive.inheritance_success),
            "spatial_index_size": (
                len(self.engine.model_ids) if self.engine.spatial_index else 0
            ),
        }


# Export main classes
__all__ = [
    "SpatialContext",
    "SimilarityCalculator",
    "SpatialInheritanceEngine",
    "AdaptiveInheritance",
    "SpatialInheritanceCoordinator",
]
