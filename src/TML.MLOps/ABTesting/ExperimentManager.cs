using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;
using System.Text.Json;
using MathNet.Numerics.Statistics;
using MathNet.Numerics.Distributions;
using TML.Core.Domain;
using TML.Storage.Repositories;

namespace TML.MLOps.ABTesting
{
    /// <summary>
    /// Manages A/B testing experiments for models
    /// </summary>
    public class ExperimentManager : IExperimentManager
    {
        private readonly ILogger<ExperimentManager> _logger;
        private readonly IConnectionMultiplexer _redis;
        private readonly IModelRepository _modelRepository;
        private readonly ConcurrentDictionary<Guid, Experiment> _activeExperiments;
        private readonly Random _random;

        public ExperimentManager(
            ILogger<ExperimentManager> logger,
            IConnectionMultiplexer redis,
            IModelRepository modelRepository)
        {
            _logger = logger;
            _redis = redis;
            _modelRepository = modelRepository;
            _activeExperiments = new ConcurrentDictionary<Guid, Experiment>();
            _random = new Random();
        }

        public async Task<Experiment> CreateExperimentAsync(ExperimentConfig config)
        {
            try
            {
                // Validate configuration
                ValidateExperimentConfig(config);

                // Create experiment
                var experiment = new Experiment
                {
                    Id = Guid.NewGuid(),
                    Name = config.Name,
                    Description = config.Description,
                    Status = ExperimentStatus.Running,
                    Configuration = config,
                    StartedAt = DateTime.UtcNow,
                    Variants = new List<ExperimentVariant>(),
                    Metrics = new ExperimentMetrics
                    {
                        VariantMetrics = new Dictionary<string, VariantMetrics>()
                    },
                    Metadata = config.Metadata ?? new Dictionary<string, object>()
                };

                // Initialize variants
                foreach (var variantConfig in config.Variants)
                {
                    var model = await _modelRepository.GetByIdAsync(variantConfig.ModelId);
                    if (model == null)
                    {
                        throw new InvalidOperationException($"Model {variantConfig.ModelId} not found");
                    }

                    var variant = new ExperimentVariant
                    {
                        Id = variantConfig.Id,
                        Name = variantConfig.Name,
                        ModelId = variantConfig.ModelId,
                        Model = model,
                        TrafficPercentage = variantConfig.TrafficPercentage,
                        IsControl = variantConfig.IsControl,
                        Parameters = variantConfig.Parameters,
                        Metrics = new VariantMetrics
                        {
                            CustomMetrics = new Dictionary<string, double>()
                        }
                    };

                    experiment.Variants.Add(variant);
                    experiment.Metrics.VariantMetrics[variant.Id] = variant.Metrics;
                }

                // Store in cache and Redis
                _activeExperiments[experiment.Id] = experiment;
                await StoreExperimentAsync(experiment);

                _logger.LogInformation($"Created experiment {experiment.Id}: {experiment.Name}");
                return experiment;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error creating experiment: {config.Name}");
                throw;
            }
        }

        public async Task<Experiment> GetActiveExperimentAsync(Guid modelId)
        {
            try
            {
                // Check cache first
                var cachedExperiment = _activeExperiments.Values
                    .FirstOrDefault(e => e.Status == ExperimentStatus.Running &&
                                       e.Variants.Any(v => v.ModelId == modelId));

                if (cachedExperiment != null)
                    return cachedExperiment;

                // Check Redis
                var db = _redis.GetDatabase();
                var experiments = await db.SetMembersAsync("experiments:active");

                foreach (var experimentId in experiments)
                {
                    var experimentJson = await db.StringGetAsync($"experiment:{experimentId}");
                    if (experimentJson.HasValue)
                    {
                        var experiment = JsonSerializer.Deserialize<Experiment>(experimentJson);
                        if (experiment.Variants.Any(v => v.ModelId == modelId))
                        {
                            _activeExperiments[experiment.Id] = experiment;
                            return experiment;
                        }
                    }
                }

                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting active experiment for model {modelId}");
                throw;
            }
        }

        public async Task<ExperimentVariant> RouteRequestAsync(
            Guid experimentId,
            string userId = null,
            Dictionary<string, object> context = null)
        {
            try
            {
                var experiment = await GetExperimentAsync(experimentId);
                if (experiment == null || experiment.Status != ExperimentStatus.Running)
                {
                    return null;
                }

                // Check for sticky session
                if (experiment.Configuration.TrafficAllocation.UseStickySessions && !string.IsNullOrEmpty(userId))
                {
                    var variant = await GetStickyVariantAsync(experimentId, userId);
                    if (variant != null)
                    {
                        return variant;
                    }
                }

                // Route based on allocation type
                var selectedVariant = experiment.Configuration.TrafficAllocation.Type switch
                {
                    AllocationType.Random => RouteRandomly(experiment),
                    AllocationType.RoundRobin => RouteRoundRobin(experiment),
                    AllocationType.Weighted => RouteWeighted(experiment),
                    AllocationType.UserBased => RouteByUser(experiment, userId),
                    AllocationType.FeatureBased => RouteByFeatures(experiment, context),
                    _ => RouteRandomly(experiment)
                };

                // Store sticky session if enabled
                if (experiment.Configuration.TrafficAllocation.UseStickySessions && !string.IsNullOrEmpty(userId))
                {
                    await StoreStickySessionAsync(experimentId, userId, selectedVariant.Id);
                }

                // Update impressions
                await RecordImpressionAsync(experimentId, selectedVariant.Id);

                return selectedVariant;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error routing request for experiment {experimentId}");
                throw;
            }
        }

        public async Task RecordOutcomeAsync(Guid experimentId, string variantId, ExperimentOutcome outcome)
        {
            try
            {
                var db = _redis.GetDatabase();
                
                // Store outcome
                var outcomeKey = $"experiment:{experimentId}:outcomes:{variantId}";
                var outcomeJson = JsonSerializer.Serialize(outcome);
                await db.ListLeftPushAsync(outcomeKey, outcomeJson);
                
                // Update metrics
                var metricsKey = $"experiment:{experimentId}:metrics:{variantId}";
                await db.HashIncrementAsync(metricsKey, "conversions");
                await db.HashIncrementAsync(metricsKey, $"metric:{outcome.MetricName}:count");
                await db.HashIncrementAsync(metricsKey, $"metric:{outcome.MetricName}:sum", outcome.Value);

                // Update experiment cache
                if (_activeExperiments.TryGetValue(experimentId, out var experiment))
                {
                    if (experiment.Metrics.VariantMetrics.TryGetValue(variantId, out var variantMetrics))
                    {
                        variantMetrics.Conversions++;
                        variantMetrics.ConversionRate = (double)variantMetrics.Conversions / Math.Max(variantMetrics.Impressions, 1);
                        
                        if (!variantMetrics.CustomMetrics.ContainsKey(outcome.MetricName))
                        {
                            variantMetrics.CustomMetrics[outcome.MetricName] = 0;
                        }
                        variantMetrics.CustomMetrics[outcome.MetricName] += outcome.Value;
                    }
                }

                _logger.LogDebug($"Recorded outcome for experiment {experimentId}, variant {variantId}: {outcome.MetricName}={outcome.Value}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error recording outcome for experiment {experimentId}");
                throw;
            }
        }

        public async Task<ExperimentResults> AnalyzeExperimentAsync(Guid experimentId)
        {
            try
            {
                var experiment = await GetExperimentAsync(experimentId);
                if (experiment == null)
                {
                    throw new InvalidOperationException($"Experiment {experimentId} not found");
                }

                var results = new ExperimentResults
                {
                    ExperimentId = experimentId,
                    AnalyzedAt = DateTime.UtcNow,
                    VariantResults = new Dictionary<string, VariantResults>(),
                    Warnings = new List<string>()
                };

                // Get control variant
                var controlVariant = experiment.Variants.FirstOrDefault(v => v.IsControl);
                if (controlVariant == null)
                {
                    controlVariant = experiment.Variants.First();
                    results.Warnings.Add("No control variant specified, using first variant as control");
                }

                // Analyze each variant
                foreach (var variant in experiment.Variants)
                {
                    var variantResult = await AnalyzeVariantAsync(experiment, variant, controlVariant);
                    results.VariantResults[variant.Id] = variantResult;
                    results.TotalSamples += variantResult.SampleSize;
                }

                // Perform statistical tests
                results.Significance = PerformStatisticalTest(
                    results.VariantResults,
                    controlVariant.Id,
                    experiment.Configuration.SuccessMetrics);

                // Determine winner
                results.RecommendedWinner = DetermineWinner(results, experiment.Configuration);

                // Power analysis
                results.PowerAnalysis = CalculatePower(results, experiment.Configuration);

                // Confidence interval
                results.ConfidenceInterval = CalculateConfidenceInterval(
                    results,
                    experiment.Configuration.ConfidenceLevel);

                // Check for warnings
                CheckForWarnings(results, experiment.Configuration);

                _logger.LogInformation($"Analyzed experiment {experimentId}: Winner={results.RecommendedWinner}, Significant={results.Significance.IsSignificant}");

                return results;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error analyzing experiment {experimentId}");
                throw;
            }
        }

        public async Task<ExperimentConclusion> ConcludeExperimentAsync(Guid experimentId, bool autoPromoteWinner = true)
        {
            try
            {
                var experiment = await GetExperimentAsync(experimentId);
                if (experiment == null)
                {
                    throw new InvalidOperationException($"Experiment {experimentId} not found");
                }

                // Analyze final results
                var results = await AnalyzeExperimentAsync(experimentId);

                var conclusion = new ExperimentConclusion
                {
                    ExperimentId = experimentId,
                    WinnerVariantId = results.RecommendedWinner,
                    ConcludedAt = DateTime.UtcNow,
                    FinalResults = results,
                    WasAutoPromoted = false
                };

                // Calculate winner lift
                if (!string.IsNullOrEmpty(results.RecommendedWinner) && 
                    results.VariantResults.TryGetValue(results.RecommendedWinner, out var winnerResult))
                {
                    conclusion.WinnerLift = winnerResult.Lift;
                    conclusion.Confidence = 1 - winnerResult.PValue;
                }

                // Determine conclusion reason
                conclusion.ConclusionReason = DetermineConclusionReason(experiment, results);

                // Update experiment status
                experiment.Status = ExperimentStatus.Concluded;
                experiment.EndedAt = DateTime.UtcNow;
                experiment.WinnerVariantId = conclusion.WinnerVariantId;
                await StoreExperimentAsync(experiment);

                // Auto-promote winner if configured
                if (autoPromoteWinner && !string.IsNullOrEmpty(conclusion.WinnerVariantId))
                {
                    await PromoteWinnerAsync(experiment, conclusion.WinnerVariantId);
                    conclusion.WasAutoPromoted = true;
                }

                _logger.LogInformation($"Concluded experiment {experimentId}: Winner={conclusion.WinnerVariantId}, Lift={conclusion.WinnerLift:P2}");

                return conclusion;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error concluding experiment {experimentId}");
                throw;
            }
        }

        public async Task<IReadOnlyList<Experiment>> GetExperimentsAsync(ExperimentStatus? status = null, int limit = 100)
        {
            try
            {
                var db = _redis.GetDatabase();
                var experimentIds = await db.SetMembersAsync("experiments:all");
                var experiments = new List<Experiment>();

                foreach (var id in experimentIds.Take(limit))
                {
                    var experimentJson = await db.StringGetAsync($"experiment:{id}");
                    if (experimentJson.HasValue)
                    {
                        var experiment = JsonSerializer.Deserialize<Experiment>(experimentJson);
                        if (!status.HasValue || experiment.Status == status.Value)
                        {
                            experiments.Add(experiment);
                        }
                    }
                }

                return experiments.OrderByDescending(e => e.StartedAt).ToList();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving experiments");
                throw;
            }
        }

        public async Task StopExperimentAsync(Guid experimentId, string reason = null)
        {
            try
            {
                var experiment = await GetExperimentAsync(experimentId);
                if (experiment == null)
                {
                    throw new InvalidOperationException($"Experiment {experimentId} not found");
                }

                experiment.Status = ExperimentStatus.Cancelled;
                experiment.EndedAt = DateTime.UtcNow;
                experiment.Metadata["cancellation_reason"] = reason ?? "Manually stopped";

                await StoreExperimentAsync(experiment);
                _activeExperiments.TryRemove(experimentId, out _);

                _logger.LogInformation($"Stopped experiment {experimentId}: {reason}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error stopping experiment {experimentId}");
                throw;
            }
        }

        #region Private Methods

        private void ValidateExperimentConfig(ExperimentConfig config)
        {
            if (config.Variants == null || config.Variants.Count < 2)
            {
                throw new ArgumentException("Experiment must have at least 2 variants");
            }

            var totalTraffic = config.Variants.Sum(v => v.TrafficPercentage);
            if (Math.Abs(totalTraffic - 100) > 0.01)
            {
                throw new ArgumentException($"Traffic percentages must sum to 100, got {totalTraffic}");
            }

            if (!config.Variants.Any(v => v.IsControl))
            {
                _logger.LogWarning("No control variant specified, first variant will be used as control");
            }
        }

        private async Task<Experiment> GetExperimentAsync(Guid experimentId)
        {
            if (_activeExperiments.TryGetValue(experimentId, out var cached))
            {
                return cached;
            }

            var db = _redis.GetDatabase();
            var experimentJson = await db.StringGetAsync($"experiment:{experimentId}");
            if (experimentJson.HasValue)
            {
                return JsonSerializer.Deserialize<Experiment>(experimentJson);
            }

            return null;
        }

        private async Task StoreExperimentAsync(Experiment experiment)
        {
            var db = _redis.GetDatabase();
            var key = $"experiment:{experiment.Id}";
            var json = JsonSerializer.Serialize(experiment);
            
            await db.StringSetAsync(key, json);
            await db.SetAddAsync("experiments:all", experiment.Id.ToString());
            
            if (experiment.Status == ExperimentStatus.Running)
            {
                await db.SetAddAsync("experiments:active", experiment.Id.ToString());
            }
            else
            {
                await db.SetRemoveAsync("experiments:active", experiment.Id.ToString());
            }
        }

        private ExperimentVariant RouteRandomly(Experiment experiment)
        {
            var rand = _random.NextDouble() * 100;
            double cumulative = 0;

            foreach (var variant in experiment.Variants)
            {
                cumulative += variant.TrafficPercentage;
                if (rand < cumulative)
                {
                    return variant;
                }
            }

            return experiment.Variants.Last();
        }

        private ExperimentVariant RouteRoundRobin(Experiment experiment)
        {
            // Simple round-robin based on impression count
            var minImpressions = experiment.Variants
                .Min(v => v.Metrics?.Impressions ?? 0);

            return experiment.Variants
                .FirstOrDefault(v => (v.Metrics?.Impressions ?? 0) == minImpressions) 
                ?? experiment.Variants.First();
        }

        private ExperimentVariant RouteWeighted(Experiment experiment)
        {
            // Weighted random selection
            var weights = experiment.Configuration.TrafficAllocation.VariantWeights;
            if (weights == null || !weights.Any())
            {
                return RouteRandomly(experiment);
            }

            var totalWeight = weights.Values.Sum();
            var rand = _random.NextDouble() * totalWeight;
            double cumulative = 0;

            foreach (var variant in experiment.Variants)
            {
                if (weights.TryGetValue(variant.Id, out var weight))
                {
                    cumulative += weight;
                    if (rand < cumulative)
                    {
                        return variant;
                    }
                }
            }

            return experiment.Variants.Last();
        }

        private ExperimentVariant RouteByUser(Experiment experiment, string userId)
        {
            if (string.IsNullOrEmpty(userId))
            {
                return RouteRandomly(experiment);
            }

            // Consistent hashing based on user ID
            var hash = userId.GetHashCode();
            var index = Math.Abs(hash) % experiment.Variants.Count;
            return experiment.Variants[index];
        }

        private ExperimentVariant RouteByFeatures(Experiment experiment, Dictionary<string, object> context)
        {
            // Simple feature-based routing (can be enhanced)
            if (context == null || !context.Any())
            {
                return RouteRandomly(experiment);
            }

            // For now, just use hash of features
            var featureHash = JsonSerializer.Serialize(context).GetHashCode();
            var index = Math.Abs(featureHash) % experiment.Variants.Count;
            return experiment.Variants[index];
        }

        private async Task<ExperimentVariant> GetStickyVariantAsync(Guid experimentId, string userId)
        {
            var db = _redis.GetDatabase();
            var key = $"experiment:{experimentId}:sticky:{userId}";
            var variantId = await db.StringGetAsync(key);

            if (variantId.HasValue)
            {
                var experiment = await GetExperimentAsync(experimentId);
                return experiment?.Variants.FirstOrDefault(v => v.Id == variantId.ToString());
            }

            return null;
        }

        private async Task StoreStickySessionAsync(Guid experimentId, string userId, string variantId)
        {
            var db = _redis.GetDatabase();
            var key = $"experiment:{experimentId}:sticky:{userId}";
            var expiry = TimeSpan.FromMinutes(1440); // 24 hours default
            await db.StringSetAsync(key, variantId, expiry);
        }

        private async Task RecordImpressionAsync(Guid experimentId, string variantId)
        {
            var db = _redis.GetDatabase();
            var metricsKey = $"experiment:{experimentId}:metrics:{variantId}";
            await db.HashIncrementAsync(metricsKey, "impressions");

            if (_activeExperiments.TryGetValue(experimentId, out var experiment))
            {
                if (experiment.Metrics.VariantMetrics.TryGetValue(variantId, out var metrics))
                {
                    metrics.Impressions++;
                }
            }
        }

        private async Task<VariantResults> AnalyzeVariantAsync(Experiment experiment, ExperimentVariant variant, ExperimentVariant control)
        {
            var db = _redis.GetDatabase();
            var metricsKey = $"experiment:{experiment.Id}:metrics:{variant.Id}";
            var metrics = await db.HashGetAllAsync(metricsKey);

            var impressions = metrics.FirstOrDefault(m => m.Name == "impressions").Value.TryParse(out long imp) ? imp : 0;
            var conversions = metrics.FirstOrDefault(m => m.Name == "conversions").Value.TryParse(out long conv) ? conv : 0;

            var result = new VariantResults
            {
                VariantId = variant.Id,
                SampleSize = (int)impressions,
                ConversionRate = impressions > 0 ? (double)conversions / impressions : 0,
                SecondaryMetrics = new Dictionary<string, double>()
            };

            // Calculate statistics
            result.StandardError = Math.Sqrt(result.ConversionRate * (1 - result.ConversionRate) / Math.Max(result.SampleSize, 1));
            
            // Calculate lift relative to control
            if (variant.Id != control.Id && control.Metrics != null)
            {
                var controlRate = control.Metrics.ConversionRate;
                result.Lift = controlRate > 0 ? (result.ConversionRate - controlRate) / controlRate : 0;
            }

            return result;
        }

        private StatisticalSignificance PerformStatisticalTest(
            Dictionary<string, VariantResults> variantResults,
            string controlId,
            SuccessMetrics metrics)
        {
            var control = variantResults[controlId];
            var treatments = variantResults.Where(v => v.Key != controlId).Select(v => v.Value).ToList();

            if (!treatments.Any())
            {
                return new StatisticalSignificance { IsSignificant = false };
            }

            // Perform appropriate test based on configuration
            return metrics.TestType switch
            {
                StatisticalTest.ChiSquare => PerformChiSquareTest(control, treatments),
                StatisticalTest.TTest => PerformTTest(control, treatments),
                _ => PerformChiSquareTest(control, treatments)
            };
        }

        private StatisticalSignificance PerformChiSquareTest(VariantResults control, List<VariantResults> treatments)
        {
            // Simplified chi-square test for conversion rates
            var treatment = treatments.First(); // For simplicity, compare with first treatment
            
            var n1 = control.SampleSize;
            var n2 = treatment.SampleSize;
            var p1 = control.ConversionRate;
            var p2 = treatment.ConversionRate;
            
            var pooledP = (p1 * n1 + p2 * n2) / (n1 + n2);
            var se = Math.Sqrt(pooledP * (1 - pooledP) * (1.0 / n1 + 1.0 / n2));
            var z = Math.Abs((p1 - p2) / se);
            var pValue = 2 * (1 - Normal.CDF(0, 1, z));
            
            return new StatisticalSignificance
            {
                IsSignificant = pValue < 0.05,
                PValue = pValue,
                ChiSquareStatistic = z * z,
                DegreesOfFreedom = 1,
                EffectSize = Math.Abs(p1 - p2),
                Interpretation = pValue < 0.05 
                    ? "There is a statistically significant difference between variants" 
                    : "No statistically significant difference detected"
            };
        }

        private StatisticalSignificance PerformTTest(VariantResults control, List<VariantResults> treatments)
        {
            var treatment = treatments.First();
            
            // Two-sample t-test
            var n1 = control.SampleSize;
            var n2 = treatment.SampleSize;
            var mean1 = control.AverageValue;
            var mean2 = treatment.AverageValue;
            var std1 = control.StandardDeviation;
            var std2 = treatment.StandardDeviation;
            
            var pooledStd = Math.Sqrt(((n1 - 1) * std1 * std1 + (n2 - 1) * std2 * std2) / (n1 + n2 - 2));
            var se = pooledStd * Math.Sqrt(1.0 / n1 + 1.0 / n2);
            var t = (mean1 - mean2) / se;
            var df = n1 + n2 - 2;
            
            // Approximate p-value using normal distribution for large samples
            var pValue = 2 * (1 - Normal.CDF(0, 1, Math.Abs(t)));
            
            return new StatisticalSignificance
            {
                IsSignificant = pValue < 0.05,
                PValue = pValue,
                TStatistic = t,
                DegreesOfFreedom = df,
                EffectSize = (mean1 - mean2) / pooledStd,
                Interpretation = pValue < 0.05
                    ? $"Significant difference detected (t={t:F2}, p={pValue:F4})"
                    : "No significant difference detected"
            };
        }

        private string DetermineWinner(ExperimentResults results, ExperimentConfig config)
        {
            if (!results.Significance.IsSignificant)
            {
                return null; // No clear winner
            }

            var controlId = results.VariantResults.FirstOrDefault(v => v.Value.Lift == 0).Key;
            if (string.IsNullOrEmpty(controlId))
            {
                controlId = results.VariantResults.First().Key;
            }

            // Find variant with best performance
            var bestVariant = config.SuccessMetrics.OptimizationDirection == MetricDirection.Maximize
                ? results.VariantResults.OrderByDescending(v => v.Value.ConversionRate).First()
                : results.VariantResults.OrderBy(v => v.Value.ConversionRate).First();

            // Check if improvement meets minimum detectable effect
            var improvement = Math.Abs(bestVariant.Value.Lift);
            if (improvement >= config.SuccessMetrics.MinimumDetectableEffect)
            {
                return bestVariant.Key;
            }

            return null;
        }

        private double CalculatePower(ExperimentResults results, ExperimentConfig config)
        {
            // Simplified power calculation
            var alpha = 1 - config.ConfidenceLevel;
            var minEffect = config.SuccessMetrics.MinimumDetectableEffect;
            var sampleSize = results.TotalSamples / results.VariantResults.Count;
            
            // Power = 1 - β (Type II error probability)
            var z_alpha = Normal.InvCDF(0, 1, 1 - alpha / 2);
            var z_beta = Math.Sqrt(sampleSize) * minEffect - z_alpha;
            var power = Normal.CDF(0, 1, z_beta);
            
            return Math.Max(0, Math.Min(1, power));
        }

        private ConfidenceInterval CalculateConfidenceInterval(ExperimentResults results, double confidenceLevel)
        {
            var bestVariant = results.VariantResults.Values.OrderByDescending(v => v.ConversionRate).First();
            var z = Normal.InvCDF(0, 1, 1 - (1 - confidenceLevel) / 2);
            var margin = z * bestVariant.StandardError;
            
            return new ConfidenceInterval
            {
                Lower = bestVariant.ConversionRate - margin,
                Upper = bestVariant.ConversionRate + margin,
                Level = confidenceLevel
            };
        }

        private void CheckForWarnings(ExperimentResults results, ExperimentConfig config)
        {
            // Check sample size
            foreach (var variant in results.VariantResults.Values)
            {
                if (variant.SampleSize < config.MinSampleSize)
                {
                    results.Warnings.Add($"Variant {variant.VariantId} has insufficient samples ({variant.SampleSize} < {config.MinSampleSize})");
                }
            }

            // Check for sample ratio mismatch
            var expectedRatio = 1.0 / results.VariantResults.Count;
            foreach (var variant in results.VariantResults.Values)
            {
                var actualRatio = (double)variant.SampleSize / results.TotalSamples;
                if (Math.Abs(actualRatio - expectedRatio) > 0.1)
                {
                    results.Warnings.Add($"Sample ratio mismatch for variant {variant.VariantId}");
                }
            }

            // Check power
            if (results.PowerAnalysis < 0.8)
            {
                results.Warnings.Add($"Low statistical power ({results.PowerAnalysis:P0}), more samples needed");
            }
        }

        private string DetermineConclusionReason(Experiment experiment, ExperimentResults results)
        {
            var duration = DateTime.UtcNow - experiment.StartedAt;
            
            if (results.Significance.IsSignificant)
            {
                return $"Statistical significance reached (p={results.Significance.PValue:F4})";
            }
            
            if (duration >= experiment.Configuration.MinDuration)
            {
                return $"Minimum duration reached ({duration.TotalDays:F1} days)";
            }
            
            if (results.TotalSamples >= experiment.Configuration.MinSampleSize * experiment.Variants.Count)
            {
                return "Minimum sample size reached";
            }
            
            return "Manually concluded";
        }

        private async Task PromoteWinnerAsync(Experiment experiment, string winnerVariantId)
        {
            try
            {
                var winner = experiment.Variants.FirstOrDefault(v => v.Id == winnerVariantId);
                if (winner == null) return;

                // Update model status or configuration to promote winner
                var model = await _modelRepository.GetByIdAsync(winner.ModelId);
                if (model != null)
                {
                    // Note: Model entity doesn't have Metadata property
                    // This would need to be implemented via a separate metadata table
                    // For now, we'll just update the model status
                    await _modelRepository.UpdateAsync(model);
                }

                _logger.LogInformation($"Promoted winner variant {winnerVariantId} from experiment {experiment.Id}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error promoting winner for experiment {experiment.Id}");
            }
        }

        #endregion
    }
}
