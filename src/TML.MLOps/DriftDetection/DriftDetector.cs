using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using TML.Core.Domain;
using MathNet.Numerics.Statistics;
using MathNet.Numerics.Distributions;

namespace TML.MLOps.DriftDetection
{
    /// <summary>
    /// Advanced drift detection implementation for TML models
    /// </summary>
    public class DriftDetector : IDriftDetector
    {
        private readonly ILogger<DriftDetector> _logger;
        private readonly Dictionary<string, List<double>> _featureBaselines;
        private readonly Dictionary<Guid, Queue<ModelPerformanceMetrics>> _performanceHistory;
        
        public DriftDetector(ILogger<DriftDetector> logger)
        {
            _logger = logger;
            _featureBaselines = new Dictionary<string, List<double>>();
            _performanceHistory = new Dictionary<Guid, Queue<ModelPerformanceMetrics>>();
        }

        public async Task<DriftDetectionResult> DetectDataDriftAsync(
            IEnumerable<TransactionData> referenceData,
            IEnumerable<TransactionData> currentData,
            DriftDetectionConfig config = null)
        {
            config ??= new DriftDetectionConfig();
            var result = new DriftDetectionResult
            {
                FeatureDriftScores = new Dictionary<string, double>(),
                AffectedFeatures = new List<string>(),
                DetectedAt = DateTime.UtcNow
            };

            try
            {
                // Extract features from both datasets
                var refFeatures = ExtractFeatures(referenceData);
                var currFeatures = ExtractFeatures(currentData);

                // Check each feature for drift
                foreach (var feature in refFeatures.Keys)
                {
                    if (!currFeatures.ContainsKey(feature)) continue;

                    // Calculate PSI for the feature
                    var psi = CalculatePSI(refFeatures[feature], currFeatures[feature]);
                    result.FeatureDriftScores[feature] = psi;

                    // Perform KS test
                    var ksResult = PerformKSTest(refFeatures[feature], currFeatures[feature]);

                    // Determine if drift is detected for this feature
                    if (psi > config.PSIThreshold || ksResult.RejectNull)
                    {
                        result.AffectedFeatures.Add(feature);
                    }
                }

                // Overall drift detection
                result.IsDriftDetected = result.AffectedFeatures.Any();
                result.DriftScore = result.FeatureDriftScores.Values.DefaultIfEmpty(0).Average();
                result.Type = result.IsDriftDetected ? DriftType.DataDrift : DriftType.None;
                result.Severity = DetermineSeverity(result.DriftScore);
                result.Description = GenerateDriftDescription(result);

                _logger.LogInformation($"Data drift detection completed. Drift detected: {result.IsDriftDetected}, Score: {result.DriftScore:F3}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error detecting data drift");
                throw;
            }

            return await Task.FromResult(result);
        }

        public async Task<ConceptDriftResult> DetectConceptDriftAsync(
            Guid modelId,
            ModelPerformanceMetrics currentMetrics,
            ModelPerformanceMetrics baselineMetrics)
        {
            var result = new ConceptDriftResult
            {
                DetectedAt = DateTime.UtcNow
            };

            try
            {
                // Track performance history
                if (!_performanceHistory.ContainsKey(modelId))
                {
                    _performanceHistory[modelId] = new Queue<ModelPerformanceMetrics>(100);
                }
                _performanceHistory[modelId].Enqueue(currentMetrics);

                // Calculate performance degradation
                var accuracyDrop = baselineMetrics.Accuracy - currentMetrics.Accuracy;
                var confidenceDrop = baselineMetrics.AverageConfidence - currentMetrics.AverageConfidence;
                var f1Drop = baselineMetrics.F1Score - currentMetrics.F1Score;

                result.PerformanceDegradation = Math.Max(accuracyDrop, Math.Max(confidenceDrop, f1Drop));
                result.ConfidenceScore = currentMetrics.AverageConfidence;

                // Detect concept drift using Page-Hinkley test
                var driftDetected = PageHinkleyTest(
                    _performanceHistory[modelId].Select(m => m.Accuracy).ToList(),
                    delta: 0.005,
                    lambda: 50);

                result.IsConceptDriftDetected = driftDetected || result.PerformanceDegradation > 0.1;

                // Recommend action
                result.RecommendedAction = DetermineRecommendedAction(result.PerformanceDegradation, driftDetected);

                _logger.LogInformation($"Concept drift detection for model {modelId}. Drift: {result.IsConceptDriftDetected}, Degradation: {result.PerformanceDegradation:F3}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error detecting concept drift for model {modelId}");
                throw;
            }

            return await Task.FromResult(result);
        }

        public double CalculatePSI(IEnumerable<double> expected, IEnumerable<double> actual, int bins = 10)
        {
            var expectedList = expected.ToList();
            var actualList = actual.ToList();

            if (!expectedList.Any() || !actualList.Any())
                return 0;

            // Create bins
            var min = Math.Min(expectedList.Min(), actualList.Min());
            var max = Math.Max(expectedList.Max(), actualList.Max());
            var binWidth = (max - min) / bins;
            var binEdges = Enumerable.Range(0, bins + 1).Select(i => min + i * binWidth).ToList();

            // Calculate distributions
            var expectedDist = CalculateDistribution(expectedList, binEdges);
            var actualDist = CalculateDistribution(actualList, binEdges);

            // Calculate PSI
            double psi = 0;
            for (int i = 0; i < bins; i++)
            {
                var expected_pct = expectedDist[i];
                var actual_pct = actualDist[i];

                // Avoid division by zero
                if (expected_pct == 0 || actual_pct == 0)
                {
                    expected_pct = 0.0001;
                    actual_pct = 0.0001;
                }

                psi += (actual_pct - expected_pct) * Math.Log(actual_pct / expected_pct);
            }

            return Math.Abs(psi);
        }

        public KSTestResult PerformKSTest(IEnumerable<double> sample1, IEnumerable<double> sample2)
        {
            var s1 = sample1.OrderBy(x => x).ToList();
            var s2 = sample2.OrderBy(x => x).ToList();

            if (!s1.Any() || !s2.Any())
            {
                return new KSTestResult { Statistic = 0, PValue = 1, RejectNull = false };
            }

            // Calculate empirical CDFs
            var allValues = s1.Concat(s2).Distinct().OrderBy(x => x).ToList();
            double maxDiff = 0;

            foreach (var value in allValues)
            {
                var cdf1 = s1.Count(x => x <= value) / (double)s1.Count;
                var cdf2 = s2.Count(x => x <= value) / (double)s2.Count;
                maxDiff = Math.Max(maxDiff, Math.Abs(cdf1 - cdf2));
            }

            // Calculate critical value and p-value (simplified)
            var n1 = s1.Count;
            var n2 = s2.Count;
            var alpha = 0.05;
            var criticalValue = Math.Sqrt(-0.5 * Math.Log(alpha / 2)) * Math.Sqrt((n1 + n2) / (double)(n1 * n2));
            
            // Approximate p-value using Kolmogorov distribution
            var lambda = maxDiff * Math.Sqrt(n1 * n2 / (double)(n1 + n2));
            var pValue = 2 * Math.Exp(-2 * lambda * lambda);

            return new KSTestResult
            {
                Statistic = maxDiff,
                CriticalValue = criticalValue,
                PValue = pValue,
                RejectNull = maxDiff > criticalValue
            };
        }

        public async Task<FeatureDriftReport> MonitorFeatureDriftAsync(
            string featureName,
            IEnumerable<double> featureValues,
            DateTime windowStart,
            DateTime windowEnd)
        {
            var report = new FeatureDriftReport
            {
                FeatureName = featureName,
                DriftTimeline = new List<DriftPoint>()
            };

            try
            {
                var values = featureValues.ToList();
                
                // Store baseline if not exists
                if (!_featureBaselines.ContainsKey(featureName))
                {
                    _featureBaselines[featureName] = values.Take(100).ToList();
                }

                var baseline = _featureBaselines[featureName];
                
                // Calculate statistics
                var baselineMean = baseline.Average();
                var baselineStd = CalculateStandardDeviation(baseline);
                var currentMean = values.Average();
                var currentStd = CalculateStandardDeviation(values);

                report.MeanShift = Math.Abs(currentMean - baselineMean) / (baselineStd + 1e-7);
                report.VarianceShift = Math.Abs(currentStd - baselineStd) / (baselineStd + 1e-7);
                
                // Calculate drift score using Wasserstein distance
                report.DriftScore = CalculateWassersteinDistance(baseline, values);

                // Generate timeline
                var windowSize = 20;
                for (int i = windowSize; i < values.Count; i++)
                {
                    var window = values.Skip(i - windowSize).Take(windowSize).ToList();
                    var driftScore = CalculatePSI(baseline, window, bins: 5);
                    
                    report.DriftTimeline.Add(new DriftPoint
                    {
                        Timestamp = windowStart.AddSeconds(i * (windowEnd - windowStart).TotalSeconds / values.Count),
                        Value = values[i],
                        DriftScore = driftScore
                    });
                }

                _logger.LogInformation($"Feature drift monitoring for {featureName}: Score={report.DriftScore:F3}, MeanShift={report.MeanShift:F3}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error monitoring feature drift for {featureName}");
                throw;
            }

            return await Task.FromResult(report);
        }

        #region Private Methods

        private Dictionary<string, List<double>> ExtractFeatures(IEnumerable<TransactionData> data)
        {
            var features = new Dictionary<string, List<double>>
            {
                ["thickness"] = new List<double>(),
                ["xCoord"] = new List<double>(),
                ["yCoord"] = new List<double>(),
                ["quality"] = new List<double>(),
                ["minThickness"] = new List<double>()
            };

            foreach (var transaction in data)
            {
                features["thickness"].Add(transaction.Thickness);
                features["xCoord"].Add(transaction.XCoord);
                features["yCoord"].Add(transaction.YCoord);
                features["quality"].Add(transaction.Quality);
                features["minThickness"].Add(transaction.MinThickness);
            }

            return features;
        }

        private List<double> CalculateDistribution(List<double> values, List<double> binEdges)
        {
            var distribution = new List<double>();
            var total = values.Count;

            for (int i = 0; i < binEdges.Count - 1; i++)
            {
                var count = values.Count(v => v >= binEdges[i] && v < binEdges[i + 1]);
                distribution.Add(count / (double)total);
            }

            return distribution;
        }

        private double CalculateStandardDeviation(List<double> values)
        {
            if (!values.Any()) return 0;
            var mean = values.Average();
            var variance = values.Select(v => Math.Pow(v - mean, 2)).Average();
            return Math.Sqrt(variance);
        }

        private double CalculateWassersteinDistance(List<double> dist1, List<double> dist2)
        {
            var sorted1 = dist1.OrderBy(x => x).ToList();
            var sorted2 = dist2.OrderBy(x => x).ToList();
            
            // Resample to same size
            var size = Math.Min(sorted1.Count, sorted2.Count);
            var resampled1 = ResampleDistribution(sorted1, size);
            var resampled2 = ResampleDistribution(sorted2, size);
            
            // Calculate Wasserstein distance
            return resampled1.Zip(resampled2, (a, b) => Math.Abs(a - b)).Average();
        }

        private List<double> ResampleDistribution(List<double> distribution, int newSize)
        {
            var result = new List<double>();
            var step = distribution.Count / (double)newSize;
            
            for (int i = 0; i < newSize; i++)
            {
                var index = (int)(i * step);
                result.Add(distribution[Math.Min(index, distribution.Count - 1)]);
            }
            
            return result;
        }

        private bool PageHinkleyTest(List<double> values, double delta = 0.005, double lambda = 50)
        {
            if (values.Count < 30) return false;

            double sum = 0;
            double min_sum = double.MaxValue;
            
            for (int i = 1; i < values.Count; i++)
            {
                sum += values[i] - values[i - 1] - delta;
                min_sum = Math.Min(min_sum, sum);
                
                if (sum - min_sum > lambda)
                {
                    return true; // Drift detected
                }
            }
            
            return false;
        }

        private DriftSeverity DetermineSeverity(double driftScore)
        {
            if (driftScore < 0.1) return DriftSeverity.None;
            if (driftScore < 0.2) return DriftSeverity.Low;
            if (driftScore < 0.3) return DriftSeverity.Medium;
            if (driftScore < 0.5) return DriftSeverity.High;
            return DriftSeverity.Critical;
        }

        private string GenerateDriftDescription(DriftDetectionResult result)
        {
            if (!result.IsDriftDetected)
                return "No significant drift detected";

            var severity = result.Severity.ToString().ToLower();
            var features = string.Join(", ", result.AffectedFeatures.Take(3));
            
            return $"{severity} data drift detected affecting features: {features}. " +
                   $"Overall drift score: {result.DriftScore:F3}. " +
                   $"Immediate action {(result.Severity >= DriftSeverity.High ? "required" : "recommended")}.";
        }

        private string DetermineRecommendedAction(double degradation, bool driftDetected)
        {
            if (degradation > 0.2)
                return "Immediate model retraining required";
            if (degradation > 0.1)
                return "Schedule model retraining within 24 hours";
            if (driftDetected)
                return "Monitor closely and consider retraining if degradation continues";
            if (degradation > 0.05)
                return "Continue monitoring, prepare retraining pipeline";
            
            return "No action required, continue monitoring";
        }

        #endregion
    }
}
