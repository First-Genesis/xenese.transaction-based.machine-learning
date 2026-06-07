using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using TML.Core.Domain;

namespace TML.MLOps.ABTesting
{
    /// <summary>
    /// Interface for managing A/B testing experiments
    /// </summary>
    public interface IExperimentManager
    {
        /// <summary>
        /// Create a new A/B test experiment
        /// </summary>
        Task<Experiment> CreateExperimentAsync(ExperimentConfig config);

        /// <summary>
        /// Get active experiment for a model
        /// </summary>
        Task<Experiment> GetActiveExperimentAsync(Guid modelId);

        /// <summary>
        /// Route request to appropriate variant
        /// </summary>
        Task<ExperimentVariant> RouteRequestAsync(
            Guid experimentId, 
            string userId = null,
            Dictionary<string, object> context = null);

        /// <summary>
        /// Record experiment outcome/metric
        /// </summary>
        Task RecordOutcomeAsync(
            Guid experimentId,
            string variantId,
            ExperimentOutcome outcome);

        /// <summary>
        /// Analyze experiment results
        /// </summary>
        Task<ExperimentResults> AnalyzeExperimentAsync(Guid experimentId);

        /// <summary>
        /// Conclude experiment and select winner
        /// </summary>
        Task<ExperimentConclusion> ConcludeExperimentAsync(
            Guid experimentId,
            bool autoPromoteWinner = true);

        /// <summary>
        /// Get all experiments
        /// </summary>
        Task<IReadOnlyList<Experiment>> GetExperimentsAsync(
            ExperimentStatus? status = null,
            int limit = 100);

        /// <summary>
        /// Stop an experiment
        /// </summary>
        Task StopExperimentAsync(Guid experimentId, string reason = null);
    }

    public class Experiment
    {
        public Guid Id { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public ExperimentStatus Status { get; set; }
        public List<ExperimentVariant> Variants { get; set; }
        public ExperimentConfig Configuration { get; set; }
        public DateTime StartedAt { get; set; }
        public DateTime? EndedAt { get; set; }
        public ExperimentMetrics Metrics { get; set; }
        public string WinnerVariantId { get; set; }
        public Dictionary<string, object> Metadata { get; set; }
    }

    public class ExperimentConfig
    {
        public string Name { get; set; }
        public string Description { get; set; }
        public List<VariantConfig> Variants { get; set; }
        public TrafficAllocation TrafficAllocation { get; set; }
        public SuccessMetrics SuccessMetrics { get; set; }
        public TimeSpan MinDuration { get; set; } = TimeSpan.FromDays(7);
        public int MinSampleSize { get; set; } = 1000;
        public double ConfidenceLevel { get; set; } = 0.95;
        public bool EnableEarlyStopping { get; set; } = true;
        public Dictionary<string, object> Metadata { get; set; }
    }

    public class VariantConfig
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public Guid ModelId { get; set; }
        public double TrafficPercentage { get; set; }
        public Dictionary<string, object> Parameters { get; set; }
        public bool IsControl { get; set; }
    }

    public class ExperimentVariant
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public Guid ModelId { get; set; }
        public double TrafficPercentage { get; set; }
        public bool IsControl { get; set; }
        public VariantMetrics Metrics { get; set; }
        public Model Model { get; set; }
        public Dictionary<string, object> Parameters { get; set; }
    }

    public class TrafficAllocation
    {
        public AllocationType Type { get; set; } = AllocationType.Random;
        public Dictionary<string, double> VariantWeights { get; set; }
        public bool UseStickySessions { get; set; } = true;
        public int StickySessionDurationMinutes { get; set; } = 1440; // 24 hours
        public List<string> SegmentationRules { get; set; }
    }

    public class SuccessMetrics
    {
        public string PrimaryMetric { get; set; }
        public List<string> SecondaryMetrics { get; set; }
        public MetricDirection OptimizationDirection { get; set; } = MetricDirection.Maximize;
        public double MinimumDetectableEffect { get; set; } = 0.05; // 5% improvement
        public StatisticalTest TestType { get; set; } = StatisticalTest.TTest;
    }

    public class ExperimentOutcome
    {
        public string MetricName { get; set; }
        public double Value { get; set; }
        public DateTime Timestamp { get; set; }
        public string UserId { get; set; }
        public Dictionary<string, object> Context { get; set; }
    }

    public class ExperimentResults
    {
        public Guid ExperimentId { get; set; }
        public DateTime AnalyzedAt { get; set; }
        public int TotalSamples { get; set; }
        public Dictionary<string, VariantResults> VariantResults { get; set; }
        public StatisticalSignificance Significance { get; set; }
        public string RecommendedWinner { get; set; }
        public double PowerAnalysis { get; set; }
        public ConfidenceInterval ConfidenceInterval { get; set; }
        public List<string> Warnings { get; set; }
    }

    public class VariantResults
    {
        public string VariantId { get; set; }
        public int SampleSize { get; set; }
        public double ConversionRate { get; set; }
        public double AverageValue { get; set; }
        public double StandardDeviation { get; set; }
        public double StandardError { get; set; }
        public double Lift { get; set; } // Relative to control
        public double PValue { get; set; }
        public bool IsStatisticallySignificant { get; set; }
        public Dictionary<string, double> SecondaryMetrics { get; set; }
    }

    public class StatisticalSignificance
    {
        public bool IsSignificant { get; set; }
        public double PValue { get; set; }
        public double ChiSquareStatistic { get; set; }
        public double TStatistic { get; set; }
        public double DegreesOfFreedom { get; set; }
        public double EffectSize { get; set; }
        public string Interpretation { get; set; }
    }

    public class ConfidenceInterval
    {
        public double Lower { get; set; }
        public double Upper { get; set; }
        public double Level { get; set; }
    }

    public class ExperimentConclusion
    {
        public Guid ExperimentId { get; set; }
        public string WinnerVariantId { get; set; }
        public double WinnerLift { get; set; }
        public double Confidence { get; set; }
        public string ConclusionReason { get; set; }
        public bool WasAutoPromoted { get; set; }
        public DateTime ConcludedAt { get; set; }
        public ExperimentResults FinalResults { get; set; }
    }

    public class ExperimentMetrics
    {
        public int TotalImpressions { get; set; }
        public int TotalConversions { get; set; }
        public double OverallConversionRate { get; set; }
        public Dictionary<string, VariantMetrics> VariantMetrics { get; set; }
        public DateTime LastUpdated { get; set; }
    }

    public class VariantMetrics
    {
        public int Impressions { get; set; }
        public int Conversions { get; set; }
        public double ConversionRate { get; set; }
        public double AverageResponseTime { get; set; }
        public double ErrorRate { get; set; }
        public Dictionary<string, double> CustomMetrics { get; set; }
    }

    public enum ExperimentStatus
    {
        Draft,
        Running,
        Paused,
        Concluded,
        Cancelled
    }

    public enum AllocationType
    {
        Random,
        RoundRobin,
        Weighted,
        UserBased,
        FeatureBased
    }

    public enum MetricDirection
    {
        Maximize,
        Minimize
    }

    public enum StatisticalTest
    {
        TTest,
        ChiSquare,
        MannWhitneyU,
        ANOVA,
        BayesianAB
    }
}
