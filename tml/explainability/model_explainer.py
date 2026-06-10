"""
Real-time Model Explainability and Interpretability for TML Platform
Advanced explainability system for understanding model decisions and inheritance
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import lime
import lime.lime_tabular

# For visualization
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import shap
from loguru import logger
from plotly.subplots import make_subplots
from sklearn.inspection import permutation_importance
from sklearn.tree import export_text


@dataclass
class ExplanationResult:
    """Result from model explanation"""

    model_id: str
    explanation_type: str
    feature_importance: Dict[str, float]
    local_explanations: List[Dict[str, Any]]
    global_explanations: Dict[str, Any]
    confidence_scores: Dict[str, float]
    explanation_metadata: Dict[str, Any]
    computation_time: float
    timestamp: float


@dataclass
class InheritanceExplanation:
    """Explanation of model inheritance decisions"""

    target_model_id: str
    source_model_id: str
    inheritance_weight: float
    feature_contribution_changes: Dict[str, float]
    performance_impact: Dict[str, float]
    inheritance_rationale: List[str]
    similarity_breakdown: Dict[str, float]
    timestamp: float


class BaseExplainer(ABC):
    """Base class for model explainers"""

    @abstractmethod
    def explain_prediction(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain individual predictions"""
        pass

    @abstractmethod
    def explain_model(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain overall model behavior"""
        pass


class SHAPExplainer(BaseExplainer):
    """SHAP-based explainer for tree and linear models"""

    def __init__(self):
        self.explainers = {}

    def explain_prediction(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain predictions using SHAP values"""
        try:
            # Get or create explainer for this model
            model_id = id(model)
            if model_id not in self.explainers:
                self.explainers[model_id] = self._create_shap_explainer(model, X)

            explainer = self.explainers[model_id]

            # Calculate SHAP values
            shap_values = explainer.shap_values(X)

            # Handle multi-class case
            if isinstance(shap_values, list):
                # Multi-class: take the first class for now
                shap_values = shap_values[0]

            # Create explanations for each instance
            explanations = []
            for i in range(len(X)):
                explanation = {
                    "instance_id": i,
                    "shap_values": dict(zip(feature_names, shap_values[i])),
                    "base_value": explainer.expected_value
                    if hasattr(explainer, "expected_value")
                    else 0.0,
                    "prediction": model.predict(X[i : i + 1])[0]
                    if hasattr(model, "predict")
                    else None,
                }
                explanations.append(explanation)

            return {
                "method": "shap",
                "explanations": explanations,
                "feature_importance": dict(
                    zip(feature_names, np.mean(np.abs(shap_values), axis=0))
                ),
            }

        except Exception as e:
            logger.warning(f"SHAP explanation failed: {e}")
            return {"method": "shap", "error": str(e)}

    def explain_model(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain overall model using SHAP"""
        try:
            model_id = id(model)
            if model_id not in self.explainers:
                self.explainers[model_id] = self._create_shap_explainer(model, X)

            explainer = self.explainers[model_id]
            shap_values = explainer.shap_values(X)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            # Global feature importance
            feature_importance = dict(
                zip(feature_names, np.mean(np.abs(shap_values), axis=0))
            )

            # Feature interactions (if available)
            interactions = {}
            try:
                interaction_values = explainer.shap_interaction_values(
                    X[: min(100, len(X))]
                )
                if interaction_values is not None:
                    for i, feat1 in enumerate(feature_names):
                        for j, feat2 in enumerate(feature_names):
                            if i < j:  # Avoid duplicates
                                interaction_key = f"{feat1}_x_{feat2}"
                                interactions[interaction_key] = np.mean(
                                    np.abs(interaction_values[:, i, j])
                                )
            except:
                pass

            return {
                "method": "shap_global",
                "feature_importance": feature_importance,
                "feature_interactions": interactions,
                "summary_statistics": {
                    "mean_abs_shap": np.mean(np.abs(shap_values)),
                    "max_abs_shap": np.max(np.abs(shap_values)),
                    "feature_coverage": len(
                        [f for f in feature_importance.values() if f > 0.001]
                    ),
                },
            }

        except Exception as e:
            logger.warning(f"SHAP global explanation failed: {e}")
            return {"method": "shap_global", "error": str(e)}

    def _create_shap_explainer(self, model, X: np.ndarray):
        """Create appropriate SHAP explainer based on model type"""
        try:
            # Try TreeExplainer first (for tree-based models)
            return shap.TreeExplainer(model)
        except:
            try:
                # Try LinearExplainer for linear models
                return shap.LinearExplainer(model, X)
            except:
                # Fallback to KernelExplainer (model-agnostic but slower)
                return shap.KernelExplainer(model.predict, X[: min(100, len(X))])


class LIMEExplainer(BaseExplainer):
    """LIME-based explainer for tabular data"""

    def __init__(self):
        self.explainers = {}

    def explain_prediction(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain predictions using LIME"""
        try:
            # Create LIME explainer
            explainer = lime.lime_tabular.LimeTabularExplainer(
                X,
                feature_names=feature_names,
                mode="classification"
                if hasattr(model, "predict_proba")
                else "regression",
                discretize_continuous=True,
            )

            explanations = []
            for i in range(min(len(X), 10)):  # Limit to 10 instances for performance
                if hasattr(model, "predict_proba"):
                    explanation = explainer.explain_instance(
                        X[i], model.predict_proba, num_features=len(feature_names)
                    )
                else:
                    explanation = explainer.explain_instance(
                        X[i], model.predict, num_features=len(feature_names)
                    )

                # Extract feature contributions
                feature_contributions = dict(explanation.as_list())

                explanations.append(
                    {
                        "instance_id": i,
                        "feature_contributions": feature_contributions,
                        "prediction": model.predict(X[i : i + 1])[0]
                        if hasattr(model, "predict")
                        else None,
                        "confidence": explanation.score
                        if hasattr(explanation, "score")
                        else None,
                    }
                )

            # Calculate overall feature importance
            all_contributions = {}
            for exp in explanations:
                for feat, contrib in exp["feature_contributions"].items():
                    if feat not in all_contributions:
                        all_contributions[feat] = []
                    all_contributions[feat].append(abs(contrib))

            feature_importance = {
                feat: np.mean(contribs) for feat, contribs in all_contributions.items()
            }

            return {
                "method": "lime",
                "explanations": explanations,
                "feature_importance": feature_importance,
            }

        except Exception as e:
            logger.warning(f"LIME explanation failed: {e}")
            return {"method": "lime", "error": str(e)}

    def explain_model(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain overall model using LIME on sample"""
        # LIME is primarily for local explanations, so we aggregate local explanations
        local_explanations = self.explain_prediction(
            model, X[: min(50, len(X))], feature_names
        )

        if "error" in local_explanations:
            return local_explanations

        return {
            "method": "lime_global",
            "feature_importance": local_explanations["feature_importance"],
            "sample_size": len(local_explanations["explanations"]),
            "aggregation_method": "mean_absolute_contribution",
        }


class PermutationExplainer(BaseExplainer):
    """Permutation-based feature importance explainer"""

    def explain_prediction(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Permutation importance is global, so redirect to explain_model"""
        return self.explain_model(model, X, feature_names)

    def explain_model(
        self, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Explain model using permutation importance"""
        try:
            # Create dummy y for permutation importance (use predictions)
            y_pred = model.predict(X)

            # Calculate permutation importance
            perm_importance = permutation_importance(
                model, X, y_pred, n_repeats=5, random_state=42
            )

            feature_importance = dict(
                zip(feature_names, perm_importance.importances_mean)
            )
            feature_std = dict(zip(feature_names, perm_importance.importances_std))

            return {
                "method": "permutation",
                "feature_importance": feature_importance,
                "feature_importance_std": feature_std,
                "n_repeats": 5,
            }

        except Exception as e:
            logger.warning(f"Permutation importance failed: {e}")
            return {"method": "permutation", "error": str(e)}


class RealTimeModelExplainer:
    """
    Real-time model explainability system for TML Platform
    Provides comprehensive explanations for model decisions and inheritance
    """

    def __init__(self):
        # Initialize explainers
        self.explainers = {
            "shap": SHAPExplainer(),
            "lime": LIMEExplainer(),
            "permutation": PermutationExplainer(),
        }

        # Explanation cache for performance
        self.explanation_cache: Dict[str, ExplanationResult] = {}
        self.cache_ttl = 300  # 5 minutes

        # Performance tracking
        self.explanation_stats = {
            "total_explanations": 0,
            "cache_hits": 0,
            "avg_computation_time": 0.0,
            "explanation_methods_used": {
                method: 0 for method in self.explainers.keys()
            },
        }

        # Async executor for non-blocking explanations
        self.executor = ThreadPoolExecutor(max_workers=4)

        logger.info("Real-time Model Explainer initialized")

    async def explain_model_decision(
        self,
        model_id: str,
        model,
        X: np.ndarray,
        feature_names: List[str],
        explanation_methods: List[str] = None,
        cache_key: str = None,
    ) -> ExplanationResult:
        """
        Provide comprehensive explanation for model decisions
        """
        start_time = time.time()

        if explanation_methods is None:
            explanation_methods = ["shap", "permutation"]

        # Check cache
        if cache_key and self._check_cache(cache_key):
            self.explanation_stats["cache_hits"] += 1
            cached_result: ExplanationResult = self.explanation_cache[cache_key]
            return cached_result

        # Run explanations in parallel
        explanation_tasks = []
        for method in explanation_methods:
            if method in self.explainers:
                task = asyncio.create_task(
                    self._run_explanation_async(method, model, X, feature_names)
                )
                explanation_tasks.append((method, task))

        # Collect results
        local_explanations = []
        global_explanations = {}
        feature_importance = {}
        confidence_scores = {}

        for method, task in explanation_tasks:
            try:
                result = await task

                if "error" not in result:
                    if "explanations" in result:
                        local_explanations.extend(result["explanations"])

                    global_explanations[method] = result

                    if "feature_importance" in result:
                        feature_importance[method] = result["feature_importance"]

                    # Calculate confidence based on explanation consistency
                    confidence_scores[method] = self._calculate_explanation_confidence(
                        result
                    )

                    self.explanation_stats["explanation_methods_used"][method] += 1

            except Exception as e:
                logger.warning(f"Explanation method {method} failed: {e}")

        # Aggregate feature importance across methods
        aggregated_importance = self._aggregate_feature_importance(
            feature_importance, feature_names
        )

        # Create explanation result
        computation_time = time.time() - start_time

        result: ExplanationResult = ExplanationResult(
            model_id=model_id,
            explanation_type="comprehensive",
            feature_importance=aggregated_importance,
            local_explanations=local_explanations,
            global_explanations=global_explanations,
            confidence_scores=confidence_scores,
            explanation_metadata={
                "methods_used": explanation_methods,
                "n_instances": len(X),
                "n_features": len(feature_names),
                "feature_names": feature_names,
            },
            computation_time=computation_time,
            timestamp=time.time(),
        )

        # Cache result
        if cache_key:
            self.explanation_cache[cache_key] = result

        # Update statistics
        self.explanation_stats["total_explanations"] += 1
        self.explanation_stats["avg_computation_time"] = (
            self.explanation_stats["avg_computation_time"]
            * (self.explanation_stats["total_explanations"] - 1)
            + computation_time
        ) / self.explanation_stats["total_explanations"]

        logger.info(
            f"Model explanation completed for {model_id} in {computation_time:.3f}s"
        )

        return result  # type: ignore[return-value]

    async def _run_explanation_async(
        self, method: str, model, X: np.ndarray, feature_names: List[str]
    ) -> Dict[str, Any]:
        """Run explanation method asynchronously"""
        loop = asyncio.get_event_loop()

        def run_explanation():
            explainer = self.explainers[method]
            local_result = explainer.explain_prediction(model, X, feature_names)
            global_result = explainer.explain_model(model, X, feature_names)

            # Combine results
            combined_result = {**local_result, **global_result}
            return combined_result

        return await loop.run_in_executor(self.executor, run_explanation)

    def _aggregate_feature_importance(
        self, importance_dict: Dict[str, Dict[str, float]], feature_names: List[str]
    ) -> Dict[str, float]:
        """Aggregate feature importance across different explanation methods"""
        if not importance_dict:
            return {name: 0.0 for name in feature_names}

        # Normalize importance scores for each method
        normalized_importance = {}
        for method, importance in importance_dict.items():
            max_importance = max(importance.values()) if importance.values() else 1.0
            normalized_importance[method] = {
                feat: imp / max_importance for feat, imp in importance.items()
            }

        # Calculate weighted average (equal weights for now)
        aggregated = {}
        for feature in feature_names:
            scores = []
            for method_importance in normalized_importance.values():
                if feature in method_importance:
                    scores.append(method_importance[feature])

            aggregated[feature] = float(np.mean(scores)) if scores else 0.0

        return aggregated

    def _calculate_explanation_confidence(
        self, explanation_result: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for explanation quality"""
        confidence = 0.5  # Base confidence

        # Increase confidence if we have feature importance
        if "feature_importance" in explanation_result:
            importance_values = list(explanation_result["feature_importance"].values())
            if importance_values:
                # Higher confidence if importance values are well-distributed
                importance_std = np.std(importance_values)
                importance_mean = np.mean(importance_values)
                if importance_mean > 0:
                    confidence += min(0.3, importance_std / importance_mean)

        # Increase confidence if we have local explanations
        if "explanations" in explanation_result:
            confidence += min(0.2, len(explanation_result["explanations"]) / 100)

        return min(1.0, confidence)

    def _check_cache(self, cache_key: str) -> bool:
        """Check if explanation is cached and still valid"""
        if cache_key not in self.explanation_cache:
            return False

        cached_result = self.explanation_cache[cache_key]
        age = time.time() - cached_result.timestamp

        if age > self.cache_ttl:
            del self.explanation_cache[cache_key]
            return False

        return True

    async def explain_inheritance_decision(
        self,
        target_model_id: str,
        source_model_id: str,
        inheritance_data: Dict[str, Any],
    ) -> InheritanceExplanation:
        """
        Explain why and how model inheritance was performed
        """
        logger.info(f"Explaining inheritance: {source_model_id} -> {target_model_id}")

        # Extract inheritance information
        inheritance_weight = inheritance_data.get("inheritance_weight", 0.0)
        similarity_score = inheritance_data.get("similarity_score", 0.0)

        # Analyze feature contribution changes
        feature_contribution_changes = inheritance_data.get("feature_changes", {})

        # Analyze performance impact
        performance_impact = {
            "expected_improvement": inheritance_data.get(
                "performance_improvement_estimate", 0.0
            ),
            "confidence": inheritance_data.get("inheritance_confidence", 0.0),
        }

        # Generate inheritance rationale
        rationale = self._generate_inheritance_rationale(
            inheritance_weight, similarity_score, performance_impact
        )

        # Break down similarity components
        similarity_breakdown = {
            "spatial_similarity": inheritance_data.get("spatial_similarity", 0.0),
            "performance_similarity": inheritance_data.get(
                "performance_similarity", 0.0
            ),
            "domain_similarity": inheritance_data.get("domain_similarity", 0.0),
            "temporal_similarity": inheritance_data.get("temporal_similarity", 0.0),
        }

        explanation = InheritanceExplanation(
            target_model_id=target_model_id,
            source_model_id=source_model_id,
            inheritance_weight=inheritance_weight,
            feature_contribution_changes=feature_contribution_changes,
            performance_impact=performance_impact,
            inheritance_rationale=rationale,
            similarity_breakdown=similarity_breakdown,
            timestamp=time.time(),
        )

        logger.info(
            f"Inheritance explanation generated: weight={inheritance_weight:.3f}, "
            f"similarity={similarity_score:.3f}"
        )

        return explanation

    def _generate_inheritance_rationale(
        self,
        inheritance_weight: float,
        similarity_score: float,
        performance_impact: Dict[str, float],
    ) -> List[str]:
        """Generate human-readable rationale for inheritance decision"""
        rationale = []

        # Weight-based rationale
        if inheritance_weight > 0.8:
            rationale.append(
                "High inheritance weight indicates strong model similarity and compatibility"
            )
        elif inheritance_weight > 0.5:
            rationale.append(
                "Moderate inheritance weight suggests partial model compatibility"
            )
        else:
            rationale.append(
                "Low inheritance weight indicates limited model compatibility"
            )

        # Similarity-based rationale
        if similarity_score > 0.8:
            rationale.append("Models show high spatial and feature similarity")
        elif similarity_score > 0.5:
            rationale.append("Models share moderate similarity in learned patterns")
        else:
            rationale.append(
                "Models have limited similarity but may share some useful patterns"
            )

        # Performance-based rationale
        expected_improvement = performance_impact.get("expected_improvement", 0.0)
        if expected_improvement > 0.1:
            rationale.append(
                "Inheritance expected to provide significant performance improvement"
            )
        elif expected_improvement > 0.05:
            rationale.append("Inheritance may provide modest performance benefits")
        else:
            rationale.append(
                "Inheritance provides knowledge transfer with minimal performance impact"
            )

        return rationale

    def generate_explanation_visualization(
        self, explanation_result: ExplanationResult
    ) -> Dict[str, Any]:
        """Generate visualization data for explanation results"""

        visualizations = {}

        # Feature importance bar chart
        if explanation_result.feature_importance:
            importance_data = explanation_result.feature_importance

            fig_importance = go.Figure(
                data=[
                    go.Bar(
                        x=list(importance_data.keys()),
                        y=list(importance_data.values()),
                        marker_color="lightblue",
                    )
                ]
            )
            fig_importance.update_layout(
                title="Feature Importance",
                xaxis_title="Features",
                yaxis_title="Importance Score",
            )

            visualizations["feature_importance"] = fig_importance.to_json()

        # Method comparison radar chart
        if explanation_result.confidence_scores:
            confidence_data = explanation_result.confidence_scores

            fig_radar = go.Figure()
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=list(confidence_data.values()),
                    theta=list(confidence_data.keys()),
                    fill="toself",
                    name="Confidence Scores",
                )
            )
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                title="Explanation Method Confidence",
            )

            visualizations["method_confidence"] = fig_radar.to_json()

        # Local explanation heatmap (if available)
        if explanation_result.local_explanations:
            local_data = explanation_result.local_explanations[
                :10
            ]  # Limit to 10 instances

            if local_data and "shap_values" in local_data[0]:
                # Create heatmap data
                features = list(local_data[0]["shap_values"].keys())
                instances = [f"Instance {i}" for i in range(len(local_data))]

                heatmap_data = []
                for instance_data in local_data:
                    row = [
                        instance_data["shap_values"].get(feat, 0) for feat in features
                    ]
                    heatmap_data.append(row)

                fig_heatmap = go.Figure(
                    data=go.Heatmap(
                        z=heatmap_data,
                        x=features,
                        y=instances,
                        colorscale="RdBu",
                        zmid=0,
                    )
                )
                fig_heatmap.update_layout(
                    title="Local Explanation Heatmap (SHAP Values)",
                    xaxis_title="Features",
                    yaxis_title="Instances",
                )

                visualizations["local_explanations"] = fig_heatmap.to_json()

        return visualizations

    def get_explanation_summary(self, model_id: str) -> Dict[str, Any]:
        """Get summary of explanations for a specific model"""
        model_explanations = [
            result
            for result in self.explanation_cache.values()
            if result.model_id == model_id
        ]

        if not model_explanations:
            return {}

        # Aggregate statistics
        total_explanations = len(model_explanations)
        avg_computation_time = np.mean(
            [exp.computation_time for exp in model_explanations]
        )

        # Most important features across explanations
        all_importance = {}
        for exp in model_explanations:
            for feature, importance in exp.feature_importance.items():
                if feature not in all_importance:
                    all_importance[feature] = []
                all_importance[feature].append(importance)

        avg_importance = {
            feature: np.mean(importances)
            for feature, importances in all_importance.items()
        }

        # Sort by importance
        top_features = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        return {
            "model_id": model_id,
            "total_explanations": total_explanations,
            "avg_computation_time": avg_computation_time,
            "top_features": dict(top_features),
            "explanation_coverage": len(all_importance),
            "latest_explanation": max(
                model_explanations, key=lambda x: x.timestamp
            ).timestamp,
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "total_explanations": self.explanation_stats["total_explanations"],
            "cache_size": len(self.explanation_cache),
            "cache_hit_rate": (
                self.explanation_stats["cache_hits"]
                / max(1, self.explanation_stats["total_explanations"])
                * 100
            ),
            "avg_computation_time": self.explanation_stats["avg_computation_time"],
            "explanation_methods_usage": self.explanation_stats[
                "explanation_methods_used"
            ],
            "available_explainers": list(self.explainers.keys()),
            "cache_ttl": self.cache_ttl,
        }

    def clear_cache(self):
        """Clear explanation cache"""
        self.explanation_cache.clear()
        logger.info("Explanation cache cleared")

    async def shutdown(self):
        """Graceful shutdown"""
        self.executor.shutdown(wait=True)
        self.clear_cache()
        logger.info("Model explainer shutdown complete")
