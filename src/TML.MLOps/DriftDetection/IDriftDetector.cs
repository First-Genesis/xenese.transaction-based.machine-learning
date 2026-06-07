using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using TML.Core.Domain;

namespace TML.MLOps.DriftDetection
{
    /// <summary>
    /// Interface for model drift detection
    /// </summary>
    public interface IDriftDetector
    {
        /// <summary>
        /// Detect data drift using statistical tests
        /// </summary>
        Task<DriftDetectionResult> DetectDataDriftAsync(
            IEnumerable<TransactionData> referenceData,
            IEnumerable<TransactionData> currentData,
            DriftDetectionConfig config = null);

        /// <summary>
        /// Detect concept drift based on model performance
        /// </summary>
        Task<ConceptDriftResult> DetectConceptDriftAsync(
            Guid modelId,
            ModelPerformanceMetrics currentMetrics,
            ModelPerformanceMetrics baselineMetrics);

        /// <summary>
        /// Calculate Population Stability Index (PSI)
        /// </summary>
        double CalculatePSI(
            IEnumerable<double> expected,
            IEnumerable<double> actual,
            int bins = 10);

        /// <summary>
        /// Perform Kolmogorov-Smirnov test for distribution shift
        /// </summary>
        KSTestResult PerformKSTest(
            IEnumerable<double> sample1,
            IEnumerable<double> sample2);

        /// <summary>
        /// Monitor feature drift over time
        /// </summary>
        Task<FeatureDriftReport> MonitorFeatureDriftAsync(
            string featureName,
            IEnumerable<double> featureValues,
            DateTime windowStart,
            DateTime windowEnd);
    }

    public class DriftDetectionResult
    {
        public bool IsDriftDetected { get; set; }
        public double DriftScore { get; set; }
        public DriftType Type { get; set; }
        public string Description { get; set; }
        public Dictionary<string, double> FeatureDriftScores { get; set; }
        public DateTime DetectedAt { get; set; }
        public DriftSeverity Severity { get; set; }
        public List<string> AffectedFeatures { get; set; }
    }

    public class ConceptDriftResult
    {
        public bool IsConceptDriftDetected { get; set; }
        public double PerformanceDegradation { get; set; }
        public double ConfidenceScore { get; set; }
        public string RecommendedAction { get; set; }
        public DateTime DetectedAt { get; set; }
    }

    public class KSTestResult
    {
        public double Statistic { get; set; }
        public double PValue { get; set; }
        public bool RejectNull { get; set; }
        public double CriticalValue { get; set; }
    }

    public class FeatureDriftReport
    {
        public string FeatureName { get; set; }
        public double DriftScore { get; set; }
        public double MeanShift { get; set; }
        public double VarianceShift { get; set; }
        public List<DriftPoint> DriftTimeline { get; set; }
    }

    public class DriftPoint
    {
        public DateTime Timestamp { get; set; }
        public double Value { get; set; }
        public double DriftScore { get; set; }
    }

    public class ModelPerformanceMetrics
    {
        public double Accuracy { get; set; }
        public double Precision { get; set; }
        public double Recall { get; set; }
        public double F1Score { get; set; }
        public double AverageConfidence { get; set; }
        public int SampleSize { get; set; }
        public DateTime MeasuredAt { get; set; }
    }

    public class DriftDetectionConfig
    {
        public double DriftThreshold { get; set; } = 0.1;
        public double PSIThreshold { get; set; } = 0.2;
        public double KSTestAlpha { get; set; } = 0.05;
        public int MinSampleSize { get; set; } = 100;
        public bool EnableAutoRetraining { get; set; } = false;
        public TimeSpan DetectionWindow { get; set; } = TimeSpan.FromHours(24);
    }

    public enum DriftType
    {
        None,
        DataDrift,
        ConceptDrift,
        Both
    }

    public enum DriftSeverity
    {
        None,
        Low,
        Medium,
        High,
        Critical
    }
}
