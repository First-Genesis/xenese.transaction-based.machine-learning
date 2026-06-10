"""
Advanced Drift Detection with Statistical Significance Testing
Enhanced drift detection system for TML Platform with rigorous statistical analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
import json
import time
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

from scipy import stats
from scipy.stats import ks_2samp, chi2_contingency, mannwhitneyu, anderson_ksamp
import warnings

warnings.filterwarnings("ignore")

from loguru import logger


class DriftType(Enum):
    """Types of drift that can be detected"""

    COVARIATE_DRIFT = "covariate_drift"  # Input distribution change
    CONCEPT_DRIFT = "concept_drift"  # Input-output relationship change
    LABEL_DRIFT = "label_drift"  # Output distribution change
    PREDICTION_DRIFT = "prediction_drift"  # Model prediction distribution change


class DriftSeverity(Enum):
    """Severity levels for detected drift"""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftTestResult:
    """Result from a single drift test"""

    test_name: str
    test_statistic: float
    p_value: float
    critical_value: float
    is_significant: bool
    effect_size: float
    confidence_interval: Tuple[float, float]
    interpretation: str


@dataclass
class DriftDetectionResult:
    """Comprehensive drift detection result"""

    model_id: str
    drift_type: DriftType
    drift_severity: DriftSeverity
    overall_p_value: float
    is_drift_detected: bool
    individual_tests: List[DriftTestResult]
    feature_drift_scores: Dict[str, float]
    drift_magnitude: float
    statistical_power: float
    confidence_level: float
    detection_metadata: Dict[str, Any]
    timestamp: float
    recommendations: List[str]


@dataclass
class DriftMonitoringConfig:
    """Configuration for drift monitoring"""

    significance_level: float = 0.05
    min_samples: int = 100
    window_size: int = 1000
    overlap_ratio: float = 0.5
    statistical_tests: List[str] = None
    bonferroni_correction: bool = True
    effect_size_threshold: float = 0.2
    power_analysis: bool = True
    adaptive_thresholds: bool = True


class StatisticalDriftTests:
    """Collection of statistical tests for drift detection"""

    @staticmethod
    def kolmogorov_smirnov_test(
        reference: np.ndarray, current: np.ndarray
    ) -> DriftTestResult:
        """Kolmogorov-Smirnov test for distribution comparison"""
        try:
            statistic, p_value = ks_2samp(reference, current)

            # Calculate effect size (Cohen's d approximation)
            effect_size = abs(np.mean(current) - np.mean(reference)) / np.sqrt(
                (np.var(reference) + np.var(current)) / 2
            )

            # Critical value approximation
            n1, n2 = len(reference), len(current)
            critical_value = 1.36 * np.sqrt((n1 + n2) / (n1 * n2))

            is_significant = p_value < 0.05

            # Confidence interval (bootstrap approximation)
            ci_lower = statistic - 1.96 * np.sqrt(
                statistic * (1 - statistic) / min(n1, n2)
            )
            ci_upper = statistic + 1.96 * np.sqrt(
                statistic * (1 - statistic) / min(n1, n2)
            )

            interpretation = f"KS statistic: {statistic:.4f}, " + (
                "Significant drift detected"
                if is_significant
                else "No significant drift"
            )

            return DriftTestResult(
                test_name="Kolmogorov-Smirnov",
                test_statistic=statistic,
                p_value=p_value,
                critical_value=critical_value,
                is_significant=is_significant,
                effect_size=effect_size,
                confidence_interval=(ci_lower, ci_upper),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.warning(f"KS test failed: {e}")
            return DriftTestResult(
                test_name="Kolmogorov-Smirnov",
                test_statistic=0.0,
                p_value=1.0,
                critical_value=0.0,
                is_significant=False,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                interpretation=f"Test failed: {e}",
            )

    @staticmethod
    def mann_whitney_u_test(
        reference: np.ndarray, current: np.ndarray
    ) -> DriftTestResult:
        """Mann-Whitney U test for non-parametric comparison"""
        try:
            statistic, p_value = mannwhitneyu(
                reference, current, alternative="two-sided"
            )

            # Effect size (rank-biserial correlation)
            n1, n2 = len(reference), len(current)
            effect_size = 1 - (2 * statistic) / (n1 * n2)

            # Critical value approximation
            mean_u = n1 * n2 / 2
            std_u = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
            critical_value = stats.norm.ppf(0.975) * std_u + mean_u

            is_significant = p_value < 0.05

            # Confidence interval for effect size
            se_effect = np.sqrt((n1 + n2 + 1) / (3 * n1 * n2))
            ci_lower = effect_size - 1.96 * se_effect
            ci_upper = effect_size + 1.96 * se_effect

            interpretation = f"Mann-Whitney U: {statistic:.4f}, " + (
                "Significant rank difference detected"
                if is_significant
                else "No significant rank difference"
            )

            return DriftTestResult(
                test_name="Mann-Whitney U",
                test_statistic=statistic,
                p_value=p_value,
                critical_value=critical_value,
                is_significant=is_significant,
                effect_size=abs(effect_size),
                confidence_interval=(ci_lower, ci_upper),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.warning(f"Mann-Whitney U test failed: {e}")
            return DriftTestResult(
                test_name="Mann-Whitney U",
                test_statistic=0.0,
                p_value=1.0,
                critical_value=0.0,
                is_significant=False,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                interpretation=f"Test failed: {e}",
            )

    @staticmethod
    def anderson_darling_test(
        reference: np.ndarray, current: np.ndarray
    ) -> DriftTestResult:
        """Anderson-Darling test for distribution comparison"""
        try:
            # Combine samples for Anderson-Darling k-sample test
            samples = [reference, current]
            statistic, critical_values, p_value = anderson_ksamp(samples)

            # Use 5% significance level critical value
            critical_value = (
                critical_values[2] if len(critical_values) > 2 else critical_values[-1]
            )

            is_significant = statistic > critical_value

            # Effect size approximation
            effect_size = abs(np.mean(current) - np.mean(reference)) / np.sqrt(
                (np.var(reference) + np.var(current)) / 2
            )

            # Confidence interval (approximation)
            n1, n2 = len(reference), len(current)
            se = np.sqrt(1 / n1 + 1 / n2)
            ci_lower = statistic - 1.96 * se
            ci_upper = statistic + 1.96 * se

            interpretation = f"Anderson-Darling: {statistic:.4f}, " + (
                "Significant distribution difference detected"
                if is_significant
                else "No significant distribution difference"
            )

            return DriftTestResult(
                test_name="Anderson-Darling",
                test_statistic=statistic,
                p_value=p_value
                if p_value is not None
                else (0.01 if is_significant else 0.1),
                critical_value=critical_value,
                is_significant=is_significant,
                effect_size=effect_size,
                confidence_interval=(ci_lower, ci_upper),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.warning(f"Anderson-Darling test failed: {e}")
            return DriftTestResult(
                test_name="Anderson-Darling",
                test_statistic=0.0,
                p_value=1.0,
                critical_value=0.0,
                is_significant=False,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                interpretation=f"Test failed: {e}",
            )

    @staticmethod
    def population_stability_index(
        reference: np.ndarray, current: np.ndarray, bins: int = 10
    ) -> DriftTestResult:
        """Population Stability Index (PSI) for drift detection"""
        try:
            # Create bins based on reference data
            bin_edges = np.percentile(reference, np.linspace(0, 100, bins + 1))
            bin_edges[0] = -np.inf
            bin_edges[-1] = np.inf

            # Calculate distributions
            ref_counts, _ = np.histogram(reference, bins=bin_edges)
            cur_counts, _ = np.histogram(current, bins=bin_edges)

            # Convert to proportions
            ref_props = ref_counts / len(reference)
            cur_props = cur_counts / len(current)

            # Avoid division by zero
            ref_props = np.where(ref_props == 0, 0.0001, ref_props)
            cur_props = np.where(cur_props == 0, 0.0001, cur_props)

            # Calculate PSI
            psi_values = (cur_props - ref_props) * np.log(cur_props / ref_props)
            psi_score = np.sum(psi_values)

            # PSI interpretation thresholds
            if psi_score < 0.1:
                interpretation = "No significant change"
                is_significant = False
            elif psi_score < 0.2:
                interpretation = "Minor change detected"
                is_significant = True
            else:
                interpretation = "Major change detected"
                is_significant = True

            # Effect size is the PSI score itself
            effect_size = psi_score

            # Confidence interval (bootstrap approximation)
            ci_lower = max(0, psi_score - 0.05)
            ci_upper = psi_score + 0.05

            return DriftTestResult(
                test_name="Population Stability Index",
                test_statistic=psi_score,
                p_value=0.01 if psi_score > 0.2 else (0.05 if psi_score > 0.1 else 0.5),
                critical_value=0.1,
                is_significant=is_significant,
                effect_size=effect_size,
                confidence_interval=(ci_lower, ci_upper),
                interpretation=f"PSI: {psi_score:.4f}, {interpretation}",
            )

        except Exception as e:
            logger.warning(f"PSI calculation failed: {e}")
            return DriftTestResult(
                test_name="Population Stability Index",
                test_statistic=0.0,
                p_value=1.0,
                critical_value=0.1,
                is_significant=False,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                interpretation=f"Test failed: {e}",
            )

    @staticmethod
    def chi_square_test(
        reference: np.ndarray, current: np.ndarray, bins: int = 10
    ) -> DriftTestResult:
        """Chi-square test for categorical or binned continuous data"""
        try:
            # Create bins for continuous data
            if len(np.unique(reference)) > bins:
                bin_edges = np.percentile(
                    np.concatenate([reference, current]), np.linspace(0, 100, bins + 1)
                )
                ref_binned = np.digitize(reference, bin_edges)
                cur_binned = np.digitize(current, bin_edges)
            else:
                ref_binned = reference
                cur_binned = current

            # Create contingency table
            all_categories = np.unique(np.concatenate([ref_binned, cur_binned]))
            ref_counts = np.array([np.sum(ref_binned == cat) for cat in all_categories])
            cur_counts = np.array([np.sum(cur_binned == cat) for cat in all_categories])

            # Ensure no zero counts (add small constant)
            ref_counts = ref_counts + 1
            cur_counts = cur_counts + 1

            contingency_table = np.array([ref_counts, cur_counts])

            # Perform chi-square test
            chi2_stat, p_value, dof, expected = chi2_contingency(contingency_table)

            # Critical value
            critical_value = stats.chi2.ppf(0.95, dof)

            is_significant = p_value < 0.05

            # Effect size (Cramér's V)
            n = np.sum(contingency_table)
            effect_size = np.sqrt(chi2_stat / (n * (min(contingency_table.shape) - 1)))

            # Confidence interval (approximation)
            se = np.sqrt(2 * dof)
            ci_lower = chi2_stat - 1.96 * se
            ci_upper = chi2_stat + 1.96 * se

            interpretation = f"Chi-square: {chi2_stat:.4f}, " + (
                "Significant categorical distribution change"
                if is_significant
                else "No significant categorical change"
            )

            return DriftTestResult(
                test_name="Chi-square",
                test_statistic=chi2_stat,
                p_value=p_value,
                critical_value=critical_value,
                is_significant=is_significant,
                effect_size=effect_size,
                confidence_interval=(ci_lower, ci_upper),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.warning(f"Chi-square test failed: {e}")
            return DriftTestResult(
                test_name="Chi-square",
                test_statistic=0.0,
                p_value=1.0,
                critical_value=0.0,
                is_significant=False,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                interpretation=f"Test failed: {e}",
            )


class AdvancedDriftDetector:
    """
    Advanced drift detection system with statistical significance testing
    Provides comprehensive drift analysis with multiple statistical tests
    """

    def __init__(self, config: DriftMonitoringConfig = None):
        self.config = config or DriftMonitoringConfig()

        # Statistical tests registry
        self.available_tests = {
            "kolmogorov_smirnov": StatisticalDriftTests.kolmogorov_smirnov_test,
            "mann_whitney_u": StatisticalDriftTests.mann_whitney_u_test,
            "anderson_darling": StatisticalDriftTests.anderson_darling_test,
            "population_stability_index": StatisticalDriftTests.population_stability_index,
            "chi_square": StatisticalDriftTests.chi_square_test,
        }

        # Default test suite
        if self.config.statistical_tests is None:
            self.config.statistical_tests = [
                "kolmogorov_smirnov",
                "mann_whitney_u",
                "population_stability_index",
            ]

        # Drift detection history
        self.detection_history: List[DriftDetectionResult] = []

        # Reference data storage
        self.reference_data: Dict[str, np.ndarray] = {}

        # Performance tracking
        self.detection_stats = {
            "total_detections": 0,
            "drift_detected_count": 0,
            "false_positive_rate": 0.0,
            "avg_detection_time": 0.0,
        }

        logger.info("Advanced Drift Detector initialized")

    def set_reference_data(self, model_id: str, reference_data: Dict[str, np.ndarray]):
        """Set reference data for drift detection"""
        self.reference_data[model_id] = reference_data
        logger.info(
            f"Reference data set for model {model_id}: {len(reference_data)} features"
        )

    async def detect_drift(
        self,
        model_id: str,
        current_data: Dict[str, np.ndarray],
        drift_type: DriftType = DriftType.COVARIATE_DRIFT,
    ) -> DriftDetectionResult:
        """
        Detect drift using comprehensive statistical analysis
        """
        start_time = time.time()

        if model_id not in self.reference_data:
            raise ValueError(f"No reference data found for model {model_id}")

        logger.info(
            f"Starting drift detection for model {model_id}, type: {drift_type.value}"
        )

        reference_data = self.reference_data[model_id]

        # Validate data compatibility
        if not self._validate_data_compatibility(reference_data, current_data):
            raise ValueError("Reference and current data are not compatible")

        # Run statistical tests for each feature
        feature_results = {}
        all_test_results = []

        for feature_name in reference_data.keys():
            if feature_name in current_data:
                feature_tests = await self._run_feature_tests(
                    reference_data[feature_name],
                    current_data[feature_name],
                    feature_name,
                )
                feature_results[feature_name] = feature_tests
                all_test_results.extend(feature_tests)

        # Apply multiple testing correction
        if self.config.bonferroni_correction and len(all_test_results) > 1:
            corrected_alpha = self.config.significance_level / len(all_test_results)
            for test_result in all_test_results:
                test_result.is_significant = test_result.p_value < corrected_alpha

        # Aggregate results
        aggregated_result = self._aggregate_test_results(
            model_id, drift_type, all_test_results, feature_results
        )

        # Calculate statistical power
        if self.config.power_analysis:
            aggregated_result.statistical_power = self._calculate_statistical_power(
                reference_data, current_data
            )

        # Generate recommendations
        aggregated_result.recommendations = self._generate_recommendations(
            aggregated_result
        )

        # Update statistics
        detection_time = time.time() - start_time
        self.detection_stats["total_detections"] += 1
        if aggregated_result.is_drift_detected:
            self.detection_stats["drift_detected_count"] += 1

        self.detection_stats["avg_detection_time"] = (
            self.detection_stats["avg_detection_time"]
            * (self.detection_stats["total_detections"] - 1)
            + detection_time
        ) / self.detection_stats["total_detections"]

        # Store result
        self.detection_history.append(aggregated_result)

        logger.info(
            f"Drift detection completed for {model_id}: "
            f"Drift={'Yes' if aggregated_result.is_drift_detected else 'No'}, "
            f"Severity={aggregated_result.drift_severity.value}, "
            f"Time={detection_time:.3f}s"
        )

        return aggregated_result

    async def _run_feature_tests(
        self, reference: np.ndarray, current: np.ndarray, feature_name: str
    ) -> List[DriftTestResult]:
        """Run all configured statistical tests for a single feature"""

        # Ensure minimum sample size
        if (
            len(reference) < self.config.min_samples
            or len(current) < self.config.min_samples
        ):
            logger.warning(f"Insufficient samples for feature {feature_name}")
            return []

        test_results = []

        # Run tests in parallel
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=len(self.config.statistical_tests))

        tasks = []
        for test_name in self.config.statistical_tests:
            if test_name in self.available_tests:
                test_func = self.available_tests[test_name]
                task = loop.run_in_executor(executor, test_func, reference, current)
                tasks.append(task)

        # Collect results
        test_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = [
            result for result in test_results if isinstance(result, DriftTestResult)
        ]

        executor.shutdown(wait=False)

        return valid_results

    def _validate_data_compatibility(
        self, reference_data: Dict[str, np.ndarray], current_data: Dict[str, np.ndarray]
    ) -> bool:
        """Validate that reference and current data are compatible"""

        # Check if there are common features
        common_features = set(reference_data.keys()) & set(current_data.keys())
        if len(common_features) == 0:
            return False

        # Check data types and shapes
        for feature in common_features:
            ref_data = reference_data[feature]
            cur_data = current_data[feature]

            # Check if both are numeric
            if not (
                np.issubdtype(ref_data.dtype, np.number)
                and np.issubdtype(cur_data.dtype, np.number)
            ):
                logger.warning(f"Non-numeric data detected for feature {feature}")

        return True

    def _aggregate_test_results(
        self,
        model_id: str,
        drift_type: DriftType,
        all_test_results: List[DriftTestResult],
        feature_results: Dict[str, List[DriftTestResult]],
    ) -> DriftDetectionResult:
        """Aggregate individual test results into overall drift assessment"""

        if not all_test_results:
            return DriftDetectionResult(
                model_id=model_id,
                drift_type=drift_type,
                drift_severity=DriftSeverity.NONE,
                overall_p_value=1.0,
                is_drift_detected=False,
                individual_tests=[],
                feature_drift_scores={},
                drift_magnitude=0.0,
                statistical_power=0.0,
                confidence_level=self.config.significance_level,
                detection_metadata={},
                timestamp=time.time(),
                recommendations=[],
            )

        # Calculate overall p-value using Fisher's method
        p_values = [result.p_value for result in all_test_results if result.p_value > 0]
        if p_values:
            # Fisher's combined probability test
            chi2_stat = -2 * np.sum(np.log(p_values))
            overall_p_value = 1 - stats.chi2.cdf(chi2_stat, 2 * len(p_values))
        else:
            overall_p_value = 1.0

        # Determine if drift is detected
        significant_tests = [
            result for result in all_test_results if result.is_significant
        ]
        is_drift_detected = (
            len(significant_tests) > len(all_test_results) * 0.5
        )  # Majority rule

        # Calculate drift magnitude (average effect size)
        effect_sizes = [
            result.effect_size for result in all_test_results if result.effect_size > 0
        ]
        drift_magnitude = np.mean(effect_sizes) if effect_sizes else 0.0

        # Determine drift severity
        drift_severity = self._determine_drift_severity(
            drift_magnitude, overall_p_value
        )

        # Calculate feature-level drift scores
        feature_drift_scores = {}
        for feature_name, feature_tests in feature_results.items():
            if feature_tests:
                feature_p_values = [
                    test.p_value for test in feature_tests if test.p_value > 0
                ]
                if feature_p_values:
                    # Use minimum p-value as feature drift score
                    feature_drift_scores[feature_name] = min(feature_p_values)
                else:
                    feature_drift_scores[feature_name] = 1.0

        # Detection metadata
        detection_metadata = {
            "total_tests": len(all_test_results),
            "significant_tests": len(significant_tests),
            "tests_used": list(set(result.test_name for result in all_test_results)),
            "bonferroni_corrected": self.config.bonferroni_correction,
            "significance_level": self.config.significance_level,
        }

        return DriftDetectionResult(
            model_id=model_id,
            drift_type=drift_type,
            drift_severity=drift_severity,
            overall_p_value=overall_p_value,
            is_drift_detected=is_drift_detected,
            individual_tests=all_test_results,
            feature_drift_scores=feature_drift_scores,
            drift_magnitude=drift_magnitude,
            statistical_power=0.0,  # Will be calculated separately
            confidence_level=1 - self.config.significance_level,
            detection_metadata=detection_metadata,
            timestamp=time.time(),
            recommendations=[],  # Will be generated separately
        )

    def _determine_drift_severity(
        self, drift_magnitude: float, p_value: float
    ) -> DriftSeverity:
        """Determine drift severity based on magnitude and significance"""

        if not (p_value < self.config.significance_level):
            return DriftSeverity.NONE

        if drift_magnitude < 0.2:
            return DriftSeverity.LOW
        elif drift_magnitude < 0.5:
            return DriftSeverity.MODERATE
        elif drift_magnitude < 0.8:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL

    def _calculate_statistical_power(
        self, reference_data: Dict[str, np.ndarray], current_data: Dict[str, np.ndarray]
    ) -> float:
        """Calculate statistical power of the drift detection"""

        # Simplified power calculation based on sample sizes and effect sizes
        powers = []

        for feature_name in reference_data.keys():
            if feature_name in current_data:
                ref_data = reference_data[feature_name]
                cur_data = current_data[feature_name]

                # Calculate effect size (Cohen's d)
                pooled_std = np.sqrt((np.var(ref_data) + np.var(cur_data)) / 2)
                if pooled_std > 0:
                    effect_size = (
                        abs(np.mean(cur_data) - np.mean(ref_data)) / pooled_std
                    )

                    # Approximate power calculation
                    n1, n2 = len(ref_data), len(cur_data)
                    n_harmonic = 2 / (1 / n1 + 1 / n2)

                    # Power approximation for two-sample t-test
                    delta = effect_size * np.sqrt(n_harmonic / 2)
                    power = 1 - stats.norm.cdf(
                        stats.norm.ppf(1 - self.config.significance_level / 2) - delta
                    )
                    powers.append(power)

        return np.mean(powers) if powers else 0.0

    def _generate_recommendations(self, result: DriftDetectionResult) -> List[str]:
        """Generate actionable recommendations based on drift detection results"""

        recommendations = []

        if not result.is_drift_detected:
            recommendations.append(
                "No significant drift detected. Continue monitoring."
            )
            return recommendations

        # Severity-based recommendations
        if result.drift_severity == DriftSeverity.LOW:
            recommendations.extend(
                [
                    "Low-level drift detected. Increase monitoring frequency.",
                    "Consider collecting more recent training data.",
                    "Monitor model performance metrics closely.",
                ]
            )

        elif result.drift_severity == DriftSeverity.MODERATE:
            recommendations.extend(
                [
                    "Moderate drift detected. Consider model retraining.",
                    "Investigate root causes of distributional changes.",
                    "Implement adaptive learning mechanisms.",
                    "Update feature preprocessing pipelines.",
                ]
            )

        elif result.drift_severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
            recommendations.extend(
                [
                    "Significant drift detected. Immediate model retraining recommended.",
                    "Investigate data quality and collection processes.",
                    "Consider emergency fallback to previous model version.",
                    "Implement real-time model adaptation strategies.",
                    "Review and update model architecture if necessary.",
                ]
            )

        # Feature-specific recommendations
        top_drifted_features = sorted(
            result.feature_drift_scores.items(), key=lambda x: x[1]
        )[
            :3
        ]  # Top 3 most drifted features

        if top_drifted_features:
            feature_names = [feat for feat, _ in top_drifted_features]
            recommendations.append(
                f"Focus attention on features with highest drift: {', '.join(feature_names)}"
            )

        # Statistical power recommendations
        if result.statistical_power < 0.8:
            recommendations.append(
                "Low statistical power detected. Consider increasing sample sizes for more reliable detection."
            )

        return recommendations

    def get_drift_trends(
        self, model_id: str, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze drift trends over time for a specific model"""

        cutoff_time = time.time() - (lookback_hours * 3600)
        recent_detections = [
            result
            for result in self.detection_history
            if result.model_id == model_id and result.timestamp > cutoff_time
        ]

        if not recent_detections:
            return {}

        # Calculate trend metrics
        drift_counts = {severity.value: 0 for severity in DriftSeverity}
        p_values = []
        drift_magnitudes = []

        for detection in recent_detections:
            drift_counts[detection.drift_severity.value] += 1
            p_values.append(detection.overall_p_value)
            drift_magnitudes.append(detection.drift_magnitude)

        # Trend analysis
        trend_direction = "stable"
        if len(drift_magnitudes) > 1:
            recent_avg = np.mean(drift_magnitudes[-3:])  # Last 3 detections
            earlier_avg = np.mean(drift_magnitudes[:-3])  # Earlier detections

            if recent_avg > earlier_avg * 1.2:
                trend_direction = "increasing"
            elif recent_avg < earlier_avg * 0.8:
                trend_direction = "decreasing"

        return {
            "model_id": model_id,
            "lookback_hours": lookback_hours,
            "total_detections": len(recent_detections),
            "drift_severity_counts": drift_counts,
            "avg_p_value": np.mean(p_values),
            "avg_drift_magnitude": np.mean(drift_magnitudes),
            "trend_direction": trend_direction,
            "latest_detection": recent_detections[-1].timestamp
            if recent_detections
            else None,
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""

        drift_rate = (
            self.detection_stats["drift_detected_count"]
            / max(1, self.detection_stats["total_detections"])
            * 100
        )

        return {
            "total_detections": self.detection_stats["total_detections"],
            "drift_detected_count": self.detection_stats["drift_detected_count"],
            "drift_detection_rate": drift_rate,
            "avg_detection_time": self.detection_stats["avg_detection_time"],
            "available_tests": list(self.available_tests.keys()),
            "configured_tests": self.config.statistical_tests,
            "significance_level": self.config.significance_level,
            "bonferroni_correction": self.config.bonferroni_correction,
            "models_monitored": len(self.reference_data),
            "detection_history_size": len(self.detection_history),
        }

    def clear_history(self, older_than_hours: int = 168):  # Default: 1 week
        """Clear old detection history"""
        cutoff_time = time.time() - (older_than_hours * 3600)

        initial_count = len(self.detection_history)
        self.detection_history = [
            result
            for result in self.detection_history
            if result.timestamp > cutoff_time
        ]

        cleared_count = initial_count - len(self.detection_history)
        logger.info(f"Cleared {cleared_count} old detection results")

    def export_detection_results(self, model_id: str = None) -> List[Dict[str, Any]]:
        """Export detection results for analysis"""

        if model_id:
            results = [
                result
                for result in self.detection_history
                if result.model_id == model_id
            ]
        else:
            results = self.detection_history

        return [asdict(result) for result in results]
