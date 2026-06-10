"""
Automated Hyperparameter Optimization for Model Inheritance
Advanced optimization system for TML Platform model parameters
"""

import asyncio
import json
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import joblib
import numpy as np
import optuna
from loguru import logger
from optuna.pruners import HyperbandPruner, MedianPruner
from optuna.samplers import CmaEsSampler, TPESampler
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import cross_val_score


@dataclass
class OptimizationConfig:
    """Configuration for hyperparameter optimization"""

    optimization_method: str = "tpe"  # tpe, cmaes, random, grid
    n_trials: int = 100
    timeout: Optional[float] = 3600  # 1 hour timeout
    n_jobs: int = 4
    cv_folds: int = 5
    early_stopping_rounds: int = 10
    pruning_enabled: bool = True
    study_direction: str = "maximize"  # maximize or minimize
    sampler_params: Dict[str, Any] = None
    pruner_params: Dict[str, Any] = None


@dataclass
class OptimizationResult:
    """Result from hyperparameter optimization"""

    best_params: Dict[str, Any]
    best_score: float
    n_trials: int
    optimization_time: float
    convergence_history: List[float]
    parameter_importance: Dict[str, float]
    study_statistics: Dict[str, Any]
    inheritance_improvement: float
    model_id: str
    timestamp: float


@dataclass
class HyperparameterSpace:
    """Defines the hyperparameter search space"""

    param_name: str
    param_type: str  # int, float, categorical, bool
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[Any]] = None
    log: bool = False
    step: Optional[float] = None


class InheritanceAwareObjective:
    """
    Objective function that considers both model performance and inheritance quality
    """

    def __init__(
        self,
        base_model_trainer: Callable,
        inheritance_evaluator: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
        inheritance_weight: float = 0.3,
    ):
        self.base_model_trainer = base_model_trainer
        self.inheritance_evaluator = inheritance_evaluator
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.inheritance_weight = inheritance_weight

        self.trial_count = 0
        self.best_score = -np.inf

    def __call__(self, trial: optuna.Trial) -> float:
        """Evaluate hyperparameters considering both performance and inheritance"""
        self.trial_count += 1

        try:
            # Get hyperparameters from trial
            params = self._suggest_hyperparameters(trial)

            # Train model with suggested hyperparameters
            model = self.base_model_trainer(params)

            # Evaluate base performance
            if self.X_val is not None and self.y_val is not None:
                # Use validation set
                model.fit(self.X_train, self.y_train)
                y_pred = model.predict(self.X_val)
                base_score = f1_score(self.y_val, y_pred, average="weighted")
            else:
                # Use cross-validation
                cv_scores = cross_val_score(
                    model, self.X_train, self.y_train, cv=5, scoring="f1_weighted"
                )
                base_score = np.mean(cv_scores)

            # Evaluate inheritance quality
            inheritance_score = self.inheritance_evaluator(model, params)

            # Combined objective
            combined_score = (
                1 - self.inheritance_weight
            ) * base_score + self.inheritance_weight * inheritance_score

            # Update best score for pruning
            if combined_score > self.best_score:
                self.best_score = combined_score

            # Report intermediate value for pruning
            trial.report(combined_score, self.trial_count)

            # Check if trial should be pruned
            if trial.should_prune():
                raise optuna.TrialPruned()

            return combined_score

        except Exception as e:
            logger.warning(f"Trial {trial.number} failed: {e}")
            return -np.inf

    def _suggest_hyperparameters(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Suggest hyperparameters based on predefined space"""
        # This will be overridden by specific model implementations
        return {}


class RiverMLHyperparameterOptimizer:
    """
    Hyperparameter optimizer specifically designed for River ML models
    with inheritance awareness
    """

    def __init__(self, config: OptimizationConfig = None):
        self.config = config or OptimizationConfig()

        # Optimization state
        self.studies: Dict[str, optuna.Study] = {}
        self.optimization_results: Dict[str, OptimizationResult] = {}

        # Performance tracking
        self.optimization_stats = {
            "total_optimizations": 0,
            "successful_optimizations": 0,
            "avg_improvement": 0.0,
            "total_optimization_time": 0.0,
        }

        logger.info("River ML Hyperparameter Optimizer initialized")

    def define_river_ml_search_space(
        self, model_type: str
    ) -> List[HyperparameterSpace]:
        """Define search space for different River ML model types"""

        if model_type == "adaptive_random_forest":
            return [
                HyperparameterSpace("n_models", "int", 10, 100),
                HyperparameterSpace("max_features", "float", 0.1, 1.0),
                HyperparameterSpace("lambda_value", "float", 1, 10),
                HyperparameterSpace(
                    "metric", "categorical", choices=["gini", "hellinger"]
                ),
                HyperparameterSpace(
                    "drift_detector", "categorical", choices=["adwin", "ddm", "eddm"]
                ),
                HyperparameterSpace(
                    "warning_detector", "categorical", choices=["adwin", "ddm", None]
                ),
            ]

        elif model_type == "hoeffding_tree":
            return [
                HyperparameterSpace("max_depth", "int", 5, 50),
                HyperparameterSpace("min_samples_split", "int", 2, 20),
                HyperparameterSpace("confidence", "float", 0.0001, 0.1, log=True),
                HyperparameterSpace("tie_threshold", "float", 0.01, 0.1),
                HyperparameterSpace(
                    "leaf_prediction", "categorical", choices=["mc", "nb", "nba"]
                ),
                HyperparameterSpace("nb_threshold", "int", 0, 10),
            ]

        elif model_type == "sgd_classifier":
            return [
                HyperparameterSpace("learning_rate", "float", 0.0001, 0.1, log=True),
                HyperparameterSpace("l2", "float", 0.0001, 1.0, log=True),
                HyperparameterSpace(
                    "loss", "categorical", choices=["log", "hinge", "perceptron"]
                ),
                HyperparameterSpace("intercept_lr", "float", 0.001, 0.1, log=True),
            ]

        elif model_type == "passive_aggressive":
            return [
                HyperparameterSpace("C", "float", 0.01, 10.0, log=True),
                HyperparameterSpace("mode", "categorical", choices=[1, 2]),
                HyperparameterSpace(
                    "loss", "categorical", choices=["hinge", "squared_hinge"]
                ),
            ]

        else:
            # Generic search space
            return [
                HyperparameterSpace("learning_rate", "float", 0.001, 0.1, log=True),
                HyperparameterSpace("regularization", "float", 0.0001, 1.0, log=True),
            ]

    def create_river_ml_objective(
        self,
        model_type: str,
        model_factory: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        inheritance_candidates: List[Dict] = None,
    ) -> InheritanceAwareObjective:
        """Create objective function for River ML model optimization"""

        def train_model(params: Dict[str, Any]):
            """Train River ML model with given parameters"""
            return model_factory(**params)

        def evaluate_inheritance(model, params: Dict[str, Any]) -> float:
            """Evaluate inheritance quality for River ML models"""
            if not inheritance_candidates:
                return 0.5  # Neutral score if no inheritance candidates

            inheritance_score = 0.0

            for candidate in inheritance_candidates:
                # Evaluate parameter similarity
                param_similarity = self._compute_parameter_similarity(
                    params, candidate.get("params", {})
                )

                # Evaluate performance similarity
                performance_similarity = candidate.get("similarity_score", 0.0)

                # Combined inheritance score
                candidate_score = 0.6 * performance_similarity + 0.4 * param_similarity
                inheritance_score = max(inheritance_score, candidate_score)

            return inheritance_score

        return InheritanceAwareObjective(
            base_model_trainer=train_model,
            inheritance_evaluator=evaluate_inheritance,
            X_train=X_train,
            y_train=y_train,
            inheritance_weight=0.3,
        )

    def _compute_parameter_similarity(
        self, params1: Dict[str, Any], params2: Dict[str, Any]
    ) -> float:
        """Compute similarity between parameter sets"""
        if not params1 or not params2:
            return 0.0

        common_params = set(params1.keys()) & set(params2.keys())
        if not common_params:
            return 0.0

        similarities = []

        for param in common_params:
            val1, val2 = params1[param], params2[param]

            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Numerical similarity
                max_val = max(abs(val1), abs(val2), 1e-8)
                similarity = 1.0 - abs(val1 - val2) / max_val
            elif val1 == val2:
                # Exact match for categorical
                similarity = 1.0
            else:
                # Different categorical values
                similarity = 0.0

            similarities.append(similarity)

        return float(np.mean(similarities))

    def optimize_hyperparameters(
        self,
        model_id: str,
        model_type: str,
        model_factory: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        inheritance_candidates: List[Dict] = None,
        custom_search_space: List[HyperparameterSpace] = None,
    ) -> OptimizationResult:
        """
        Optimize hyperparameters for a specific model with inheritance awareness
        """

        logger.info(f"Starting hyperparameter optimization for model {model_id}")
        start_time = time.time()

        # Define search space
        search_space = custom_search_space or self.define_river_ml_search_space(
            model_type
        )

        # Create objective function
        objective = self.create_river_ml_objective(
            model_type, model_factory, X_train, y_train, inheritance_candidates
        )

        # Configure sampler
        if self.config.optimization_method == "tpe":
            sampler = TPESampler(**(self.config.sampler_params or {}))
        elif self.config.optimization_method == "cmaes":
            sampler = CmaEsSampler(**(self.config.sampler_params or {}))
        else:
            sampler = TPESampler()  # Default

        # Configure pruner
        if self.config.pruning_enabled:
            if self.config.pruner_params:
                pruner = MedianPruner(**self.config.pruner_params)
            else:
                pruner = MedianPruner(n_startup_trials=5, n_warmup_steps=10)
        else:
            pruner = optuna.pruners.NopPruner()

        # Create study
        study = optuna.create_study(
            direction=self.config.study_direction, sampler=sampler, pruner=pruner
        )

        # Add search space to objective
        def enhanced_objective(trial: optuna.Trial) -> float:
            # Suggest hyperparameters based on search space
            params = {}
            for space in search_space:
                if space.param_type == "int":
                    params[space.param_name] = trial.suggest_int(
                        space.param_name,
                        int(space.low),
                        int(space.high),
                        step=int(space.step) if space.step else 1,
                    )
                elif space.param_type == "float":
                    params[space.param_name] = trial.suggest_float(
                        space.param_name,
                        space.low,
                        space.high,
                        log=space.log,
                        step=space.step,
                    )
                elif space.param_type == "categorical":
                    params[space.param_name] = trial.suggest_categorical(
                        space.param_name, space.choices
                    )
                elif space.param_type == "bool":
                    params[space.param_name] = trial.suggest_categorical(
                        space.param_name, [True, False]
                    )

            # Override objective's parameter suggestion
            objective._suggest_hyperparameters = lambda t: params

            return objective(trial)

        # Run optimization
        try:
            study.optimize(
                enhanced_objective,
                n_trials=self.config.n_trials,
                timeout=self.config.timeout,
                n_jobs=1,  # River ML models are not thread-safe
            )

            optimization_time = time.time() - start_time

            # Calculate parameter importance
            try:
                importance = optuna.importance.get_param_importances(study)
            except Exception:
                importance = {}

            # Calculate convergence history
            convergence_history = [
                trial.value for trial in study.trials if trial.value is not None
            ]

            # Calculate inheritance improvement
            baseline_score = convergence_history[0] if convergence_history else 0.0
            best_score = study.best_value
            inheritance_improvement = (
                (best_score - baseline_score) / max(abs(baseline_score), 1e-8)
            ) * 100

            # Create result
            result = OptimizationResult(
                best_params=study.best_params,
                best_score=best_score,
                n_trials=len(study.trials),
                optimization_time=optimization_time,
                convergence_history=convergence_history,
                parameter_importance=importance,
                study_statistics={
                    "n_complete_trials": len(
                        [
                            t
                            for t in study.trials
                            if t.state == optuna.trial.TrialState.COMPLETE
                        ]
                    ),
                    "n_pruned_trials": len(
                        [
                            t
                            for t in study.trials
                            if t.state == optuna.trial.TrialState.PRUNED
                        ]
                    ),
                    "n_failed_trials": len(
                        [
                            t
                            for t in study.trials
                            if t.state == optuna.trial.TrialState.FAIL
                        ]
                    ),
                },
                inheritance_improvement=inheritance_improvement,
                model_id=model_id,
                timestamp=time.time(),
            )

            # Store results
            self.studies[model_id] = study
            self.optimization_results[model_id] = result

            # Update statistics
            self.optimization_stats["total_optimizations"] += 1
            self.optimization_stats["successful_optimizations"] += 1
            self.optimization_stats["avg_improvement"] = (
                self.optimization_stats["avg_improvement"]
                * (self.optimization_stats["successful_optimizations"] - 1)
                + inheritance_improvement
            ) / self.optimization_stats["successful_optimizations"]
            self.optimization_stats["total_optimization_time"] += optimization_time

            logger.info(
                f"✅ Optimization completed for {model_id}: "
                f"Best score: {best_score:.4f}, "
                f"Improvement: {inheritance_improvement:.2f}%, "
                f"Time: {optimization_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Optimization failed for model {model_id}: {e}")
            self.optimization_stats["total_optimizations"] += 1
            raise

    async def optimize_multiple_models(
        self, optimization_tasks: List[Dict[str, Any]]
    ) -> Dict[str, OptimizationResult]:
        """Optimize hyperparameters for multiple models in parallel"""

        logger.info(
            f"Starting parallel optimization for {len(optimization_tasks)} models"
        )

        # Create executor for parallel optimization
        executor = ThreadPoolExecutor(max_workers=self.config.n_jobs)

        # Submit optimization tasks
        futures = []
        for task in optimization_tasks:
            future = executor.submit(self.optimize_hyperparameters, **task)
            futures.append((task["model_id"], future))

        # Collect results
        results = {}
        for model_id, future in futures:
            try:
                result = future.result(timeout=self.config.timeout)
                results[model_id] = result
            except Exception as e:
                logger.error(f"Parallel optimization failed for {model_id}: {e}")

        executor.shutdown(wait=True)

        logger.info(
            f"✅ Parallel optimization completed: {len(results)}/{len(optimization_tasks)} successful"
        )

        return results

    def get_optimization_insights(self, model_id: str) -> Dict[str, Any]:
        """Get detailed insights from optimization process"""
        if model_id not in self.studies:
            return {}

        study = self.studies[model_id]
        result = self.optimization_results[model_id]

        # Analyze trial distribution
        trial_values = [
            trial.value for trial in study.trials if trial.value is not None
        ]

        insights = {
            "best_parameters": result.best_params,
            "parameter_importance": result.parameter_importance,
            "convergence_analysis": {
                "trials_to_best": next(
                    i
                    for i, v in enumerate(result.convergence_history)
                    if v == result.best_score
                ),
                "improvement_rate": np.diff(result.convergence_history[:10]).mean()
                if len(result.convergence_history) > 10
                else 0,
                "stability_score": 1.0
                - np.std(result.convergence_history[-10:])
                / np.mean(result.convergence_history[-10:])
                if len(result.convergence_history) >= 10
                else 0,
            },
            "trial_statistics": {
                "mean_score": np.mean(trial_values),
                "std_score": np.std(trial_values),
                "score_range": np.max(trial_values) - np.min(trial_values),
                "success_rate": len(trial_values) / len(study.trials),
            },
            "optimization_efficiency": {
                "time_per_trial": result.optimization_time / result.n_trials,
                "improvement_per_second": result.inheritance_improvement
                / result.optimization_time,
                "trials_efficiency": result.inheritance_improvement / result.n_trials,
            },
        }

        return insights

    def suggest_next_optimization_strategy(self, model_id: str) -> Dict[str, Any]:
        """Suggest optimization strategy for next iteration"""
        if model_id not in self.optimization_results:
            return {"strategy": "initial_optimization"}

        result = self.optimization_results[model_id]
        insights = self.get_optimization_insights(model_id)

        # Analyze optimization quality
        improvement = result.inheritance_improvement
        stability = insights["convergence_analysis"]["stability_score"]
        efficiency = insights["optimization_efficiency"]["improvement_per_second"]

        if improvement < 5.0:
            strategy = "expand_search_space"
            recommendations = [
                "Increase search space bounds",
                "Add more hyperparameters",
                "Try different optimization algorithm",
            ]
        elif stability < 0.8:
            strategy = "increase_trials"
            recommendations = [
                "Increase number of trials",
                "Enable more aggressive pruning",
                "Use ensemble of optimizers",
            ]
        elif efficiency < 0.1:
            strategy = "optimize_efficiency"
            recommendations = [
                "Reduce search space",
                "Use faster evaluation metrics",
                "Implement early stopping",
            ]
        else:
            strategy = "fine_tuning"
            recommendations = [
                "Focus on most important parameters",
                "Use local search around best parameters",
                "Implement multi-objective optimization",
            ]

        return {
            "strategy": strategy,
            "recommendations": recommendations,
            "current_performance": {
                "improvement": improvement,
                "stability": stability,
                "efficiency": efficiency,
            },
            "suggested_config": self._generate_suggested_config(strategy),
        }

    def _generate_suggested_config(self, strategy: str) -> OptimizationConfig:
        """Generate suggested configuration based on strategy"""
        base_config = self.config

        if strategy == "expand_search_space":
            return OptimizationConfig(
                optimization_method="cmaes",
                n_trials=base_config.n_trials * 2,
                timeout=base_config.timeout * 1.5,
                pruning_enabled=False,
            )
        elif strategy == "increase_trials":
            return OptimizationConfig(
                optimization_method="tpe",
                n_trials=base_config.n_trials * 3,
                timeout=base_config.timeout * 2,
                pruning_enabled=True,
                pruner_params={"n_startup_trials": 10, "n_warmup_steps": 20},
            )
        elif strategy == "optimize_efficiency":
            return OptimizationConfig(
                optimization_method="tpe",
                n_trials=base_config.n_trials // 2,
                timeout=base_config.timeout // 2,
                pruning_enabled=True,
                early_stopping_rounds=5,
            )
        else:  # fine_tuning
            return OptimizationConfig(
                optimization_method="tpe",
                n_trials=50,
                timeout=base_config.timeout // 3,
                pruning_enabled=True,
            )

    def save_optimization_state(self, filepath: str):
        """Save optimization state and results"""
        state = {
            "optimization_results": {
                k: asdict(v) for k, v in self.optimization_results.items()
            },
            "optimization_stats": self.optimization_stats,
            "config": asdict(self.config),
        }

        with open(filepath, "w") as f:
            json.dump(state, f, default=str)

        # Save studies separately (they contain complex objects)
        studies_path = filepath.replace(".json", "_studies.pkl")
        with open(studies_path, "wb") as f:
            pickle.dump(self.studies, f)

        logger.info(f"Optimization state saved to {filepath}")

    def load_optimization_state(self, filepath: str):
        """Load optimization state and results"""
        with open(filepath, "r") as f:
            state = json.load(f)

        # Restore results
        self.optimization_results = {}
        for model_id, result_dict in state["optimization_results"].items():
            self.optimization_results[model_id] = OptimizationResult(**result_dict)

        self.optimization_stats = state["optimization_stats"]

        # Load studies if available
        studies_path = filepath.replace(".json", "_studies.pkl")
        try:
            with open(studies_path, "rb") as f:
                self.studies = pickle.load(f)
        except FileNotFoundError:
            self.studies = {}

        logger.info(f"Optimization state loaded from {filepath}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "total_optimizations": self.optimization_stats["total_optimizations"],
            "successful_optimizations": self.optimization_stats[
                "successful_optimizations"
            ],
            "success_rate": (
                self.optimization_stats["successful_optimizations"]
                / max(1, self.optimization_stats["total_optimizations"])
                * 100
            ),
            "avg_improvement": self.optimization_stats["avg_improvement"],
            "total_optimization_time": self.optimization_stats[
                "total_optimization_time"
            ],
            "avg_optimization_time": (
                self.optimization_stats["total_optimization_time"]
                / max(1, self.optimization_stats["successful_optimizations"])
            ),
            "active_studies": len(self.studies),
            "config": asdict(self.config),
        }
