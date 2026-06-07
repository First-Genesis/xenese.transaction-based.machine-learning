using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;
using TML.Core.Domain;
using TML.Storage.Repositories;
using StackExchange.Redis;
using System.Text.Json;

namespace TML.MLOps.DriftDetection
{
    /// <summary>
    /// Background service for continuous drift monitoring
    /// </summary>
    public class DriftMonitoringService : BackgroundService
    {
        private readonly IServiceProvider _serviceProvider;
        private readonly ILogger<DriftMonitoringService> _logger;
        private readonly IConnectionMultiplexer _redis;
        private readonly ConcurrentDictionary<Guid, ModelDriftState> _modelStates;
        private readonly TimeSpan _monitoringInterval = TimeSpan.FromMinutes(5);
        private readonly TimeSpan _alertCooldown = TimeSpan.FromHours(1);

        public DriftMonitoringService(
            IServiceProvider serviceProvider,
            ILogger<DriftMonitoringService> logger,
            IConnectionMultiplexer redis)
        {
            _serviceProvider = serviceProvider;
            _logger = logger;
            _redis = redis;
            _modelStates = new ConcurrentDictionary<Guid, ModelDriftState>();
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("Drift Monitoring Service started");

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await MonitorAllModelsAsync(stoppingToken);
                    await Task.Delay(_monitoringInterval, stoppingToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in drift monitoring cycle");
                    await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
                }
            }

            _logger.LogInformation("Drift Monitoring Service stopped");
        }

        private async Task MonitorAllModelsAsync(CancellationToken cancellationToken)
        {
            using var scope = _serviceProvider.CreateScope();
            var modelRepo = scope.ServiceProvider.GetRequiredService<IModelRepository>();
            var transactionRepo = scope.ServiceProvider.GetRequiredService<ITransactionRepository>();

            // Get active models
            var activeModels = await modelRepo.GetByStatusAsync(ModelStatus.Active);
            _logger.LogDebug($"Monitoring {activeModels.Count} active models for drift");

            var tasks = new List<Task>();
            foreach (var model in activeModels.Take(100)) // Process up to 100 models in parallel
            {
                tasks.Add(MonitorModelDriftAsync(model, transactionRepo, cancellationToken));
            }

            await Task.WhenAll(tasks);

            // Publish drift summary to Redis
            await PublishDriftSummaryAsync();
        }

        private async Task MonitorModelDriftAsync(
            Model model, 
            ITransactionRepository transactionRepo,
            CancellationToken cancellationToken)
        {
            try
            {
                // Get or create model state
                var state = _modelStates.GetOrAdd(model.Id, new ModelDriftState
                {
                    ModelId = model.Id,
                    LastChecked = DateTime.UtcNow,
                    BaselineMetrics = ExtractBaselineMetrics(model)
                });

                // Skip if recently checked
                if (DateTime.UtcNow - state.LastChecked < TimeSpan.FromMinutes(15))
                    return;

                // Get recent transactions for this model
                var recentTransactions = await GetRecentTransactionsAsync(model.TransactionId, transactionRepo, cancellationToken);
                if (!recentTransactions.Any())
                    return;

                // Get baseline transactions
                var baselineTransactions = await GetBaselineTransactionsAsync(model.TransactionId, transactionRepo, cancellationToken);
                if (!baselineTransactions.Any())
                    return;

                // Get drift detector from service provider
                using var scope = _serviceProvider.CreateScope();
                var driftDetector = scope.ServiceProvider.GetRequiredService<IDriftDetector>();

                // Detect data drift
                var driftResult = await driftDetector.DetectDataDriftAsync(
                    baselineTransactions.Select(t => t.Data),
                    recentTransactions.Select(t => t.Data));

                // Detect concept drift
                var currentMetrics = CalculateCurrentMetrics(model);
                var conceptDriftResult = await driftDetector.DetectConceptDriftAsync(
                    model.Id,
                    currentMetrics,
                    state.BaselineMetrics);

                // Update state
                state.LastChecked = DateTime.UtcNow;
                state.DataDriftScore = driftResult.DriftScore;
                state.ConceptDriftScore = conceptDriftResult.PerformanceDegradation;
                state.IsDriftDetected = driftResult.IsDriftDetected || conceptDriftResult.IsConceptDriftDetected;
                state.LastDriftDetected = state.IsDriftDetected ? DateTime.UtcNow : state.LastDriftDetected;

                // Handle drift detection
                if (state.IsDriftDetected)
                {
                    await HandleDriftDetectedAsync(model, driftResult, conceptDriftResult);
                }

                // Store drift metrics
                await StoreDriftMetricsAsync(model.Id, state, driftResult, conceptDriftResult);

                _logger.LogDebug($"Model {model.Id}: DataDrift={driftResult.DriftScore:F3}, ConceptDrift={conceptDriftResult.PerformanceDegradation:F3}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error monitoring drift for model {model.Id}");
            }
        }

        private async Task HandleDriftDetectedAsync(
            Model model,
            DriftDetectionResult dataDrift,
            ConceptDriftResult conceptDrift)
        {
            var state = _modelStates[model.Id];

            // Check alert cooldown
            if (state.LastAlertSent != null && 
                DateTime.UtcNow - state.LastAlertSent.Value < _alertCooldown)
                return;

            // Create drift alert
            var alert = new DriftAlert
            {
                ModelId = model.Id,
                Timestamp = DateTime.UtcNow,
                DataDriftScore = dataDrift.DriftScore,
                ConceptDriftScore = conceptDrift.PerformanceDegradation,
                Severity = dataDrift.Severity,
                AffectedFeatures = dataDrift.AffectedFeatures,
                RecommendedAction = conceptDrift.RecommendedAction,
                Description = $"Drift detected for model {model.Id}. {dataDrift.Description}"
            };

            // Publish alert to Redis
            await PublishDriftAlertAsync(alert);

            // Log alert
            _logger.LogWarning($"DRIFT ALERT: Model {model.Id} - {alert.Description}");

            // Update state
            state.LastAlertSent = DateTime.UtcNow;

            // Trigger auto-retraining if configured
            if (dataDrift.Severity >= DriftSeverity.High || conceptDrift.PerformanceDegradation > 0.15)
            {
                await TriggerModelRetrainingAsync(model.Id);
            }
        }

        private async Task StoreDriftMetricsAsync(
            Guid modelId,
            ModelDriftState state,
            DriftDetectionResult dataDrift,
            ConceptDriftResult conceptDrift)
        {
            var db = _redis.GetDatabase();
            
            // Store current drift metrics
            var metricsKey = $"drift:metrics:{modelId}";
            var metrics = new DriftMetrics
            {
                ModelId = modelId,
                Timestamp = DateTime.UtcNow,
                DataDriftScore = dataDrift.DriftScore,
                ConceptDriftScore = conceptDrift.PerformanceDegradation,
                FeatureDriftScores = dataDrift.FeatureDriftScores,
                IsDriftDetected = state.IsDriftDetected,
                Severity = dataDrift.Severity
            };

            await db.StringSetAsync(
                metricsKey,
                JsonSerializer.Serialize(metrics),
                expiry: TimeSpan.FromDays(7));

            // Store in time series for historical tracking
            var timeSeriesKey = $"drift:timeseries:{modelId}";
            await db.SortedSetAddAsync(
                timeSeriesKey,
                JsonSerializer.Serialize(metrics),
                DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());

            // Trim old entries (keep last 1000)
            await db.SortedSetRemoveRangeByRankAsync(timeSeriesKey, 0, -1001);
        }

        private async Task PublishDriftAlertAsync(DriftAlert alert)
        {
            var db = _redis.GetDatabase();
            var channel = "drift:alerts";
            
            await db.PublishAsync(
                channel,
                JsonSerializer.Serialize(alert));

            // Also store in a list for persistence
            var alertsKey = "drift:alerts:history";
            await db.ListLeftPushAsync(
                alertsKey,
                JsonSerializer.Serialize(alert));
            
            // Keep only last 100 alerts
            await db.ListTrimAsync(alertsKey, 0, 99);
        }

        private async Task PublishDriftSummaryAsync()
        {
            var summary = new DriftSummary
            {
                Timestamp = DateTime.UtcNow,
                TotalModelsMonitored = _modelStates.Count,
                ModelsWithDrift = _modelStates.Count(m => m.Value.IsDriftDetected),
                AverageDataDriftScore = _modelStates.Values.Average(m => m.DataDriftScore),
                AverageConceptDriftScore = _modelStates.Values.Average(m => m.ConceptDriftScore),
                CriticalModels = _modelStates.Values.Count(m => m.DataDriftScore > 0.5 || m.ConceptDriftScore > 0.2)
            };

            var db = _redis.GetDatabase();
            await db.StringSetAsync(
                "drift:summary:latest",
                JsonSerializer.Serialize(summary),
                expiry: TimeSpan.FromHours(1));

            _logger.LogInformation($"Drift Summary: {summary.ModelsWithDrift}/{summary.TotalModelsMonitored} models with drift, {summary.CriticalModels} critical");
        }

        private async Task TriggerModelRetrainingAsync(Guid modelId)
        {
            var db = _redis.GetDatabase();
            var retrainQueue = "model:retrain:queue";
            
            var retrainRequest = new ModelRetrainRequest
            {
                ModelId = modelId,
                RequestedAt = DateTime.UtcNow,
                Reason = "Automatic retraining due to drift detection",
                Priority = "High"
            };

            await db.ListLeftPushAsync(
                retrainQueue,
                JsonSerializer.Serialize(retrainRequest));

            _logger.LogInformation($"Triggered automatic retraining for model {modelId} due to drift");
        }

        private async Task<List<Transaction>> GetRecentTransactionsAsync(
            Guid transactionId,
            ITransactionRepository repo,
            CancellationToken cancellationToken)
        {
            var endTime = DateTimeOffset.UtcNow;
            var startTime = endTime.AddHours(-24);
            
            return (await repo.GetByTimeRangeAsync(startTime, endTime, cancellationToken))
                .Where(t => t.ModelId != null)
                .Take(100)
                .ToList();
        }

        private async Task<List<Transaction>> GetBaselineTransactionsAsync(
            Guid transactionId,
            ITransactionRepository repo,
            CancellationToken cancellationToken)
        {
            var endTime = DateTimeOffset.UtcNow.AddDays(-7);
            var startTime = endTime.AddDays(-7);
            
            return (await repo.GetByTimeRangeAsync(startTime, endTime, cancellationToken))
                .Where(t => t.ModelId != null)
                .Take(100)
                .ToList();
        }

        private ModelPerformanceMetrics ExtractBaselineMetrics(Model model)
        {
            return new ModelPerformanceMetrics
            {
                Accuracy = model.Metrics?.RSquared ?? 0.9,
                Precision = 0.9,
                Recall = 0.9,
                F1Score = 0.9,
                AverageConfidence = model.Metrics?.Confidence ?? 0.9,
                SampleSize = model.Metrics?.TrainingDataPoints ?? 100,
                MeasuredAt = model.CreatedAt.DateTime
            };
        }

        private ModelPerformanceMetrics CalculateCurrentMetrics(Model model)
        {
            // In production, this would calculate actual performance metrics
            // For now, we simulate with slight degradation
            var baseline = ExtractBaselineMetrics(model);
            var degradation = (DateTime.UtcNow - model.CreatedAt).TotalDays * 0.001;
            
            return new ModelPerformanceMetrics
            {
                Accuracy = Math.Max(0.5, baseline.Accuracy - degradation),
                Precision = Math.Max(0.5, baseline.Precision - degradation),
                Recall = Math.Max(0.5, baseline.Recall - degradation),
                F1Score = Math.Max(0.5, baseline.F1Score - degradation),
                AverageConfidence = Math.Max(0.5, baseline.AverageConfidence - degradation * 2),
                SampleSize = baseline.SampleSize + 50,
                MeasuredAt = DateTime.UtcNow
            };
        }
    }

    internal class ModelDriftState
    {
        public Guid ModelId { get; set; }
        public DateTime LastChecked { get; set; }
        public DateTime? LastDriftDetected { get; set; }
        public DateTime? LastAlertSent { get; set; }
        public double DataDriftScore { get; set; }
        public double ConceptDriftScore { get; set; }
        public bool IsDriftDetected { get; set; }
        public ModelPerformanceMetrics BaselineMetrics { get; set; }
    }

    public class DriftAlert
    {
        public Guid ModelId { get; set; }
        public DateTime Timestamp { get; set; }
        public double DataDriftScore { get; set; }
        public double ConceptDriftScore { get; set; }
        public DriftSeverity Severity { get; set; }
        public List<string> AffectedFeatures { get; set; }
        public string RecommendedAction { get; set; }
        public string Description { get; set; }
    }

    public class DriftMetrics
    {
        public Guid ModelId { get; set; }
        public DateTime Timestamp { get; set; }
        public double DataDriftScore { get; set; }
        public double ConceptDriftScore { get; set; }
        public Dictionary<string, double> FeatureDriftScores { get; set; }
        public bool IsDriftDetected { get; set; }
        public DriftSeverity Severity { get; set; }
    }

    public class DriftSummary
    {
        public DateTime Timestamp { get; set; }
        public int TotalModelsMonitored { get; set; }
        public int ModelsWithDrift { get; set; }
        public double AverageDataDriftScore { get; set; }
        public double AverageConceptDriftScore { get; set; }
        public int CriticalModels { get; set; }
    }

    public class ModelRetrainRequest
    {
        public Guid ModelId { get; set; }
        public DateTime RequestedAt { get; set; }
        public string Reason { get; set; }
        public string Priority { get; set; }
    }
}
