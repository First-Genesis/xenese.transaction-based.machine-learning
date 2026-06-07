using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using TML.MLOps.DriftDetection;
using TML.Storage.Repositories;
using StackExchange.Redis;
using System.Text.Json;
using TML.Core.Domain;

namespace TML.API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class DriftController : ControllerBase
    {
        private readonly ILogger<DriftController> _logger;
        private readonly IDriftDetector _driftDetector;
        private readonly IConnectionMultiplexer _redis;
        private readonly ITransactionRepository _transactionRepo;
        private readonly IModelRepository _modelRepo;

        public DriftController(
            ILogger<DriftController> logger,
            IDriftDetector driftDetector,
            IConnectionMultiplexer redis,
            ITransactionRepository transactionRepo,
            IModelRepository modelRepo)
        {
            _logger = logger;
            _driftDetector = driftDetector;
            _redis = redis;
            _transactionRepo = transactionRepo;
            _modelRepo = modelRepo;
        }

        /// <summary>
        /// Health check for drift detection service
        /// </summary>
        [HttpGet("health")]
        public async Task<IActionResult> GetDriftServiceHealth()
        {
            var health = new
            {
                service = "Drift Detection",
                status = "healthy",
                timestamp = DateTime.UtcNow,
                components = new
                {
                    redis = await CheckRedisHealth(),
                    database = await CheckDatabaseHealth(),
                    drift_detector = CheckDriftDetectorHealth()
                }
            };

            var allHealthy = health.components.redis && health.components.database && health.components.drift_detector;
            
            return allHealthy ? Ok(health) : StatusCode(503, health);
        }

        /// <summary>
        /// Get drift summary across all models
        /// </summary>
        [HttpGet("summary")]
        public async Task<IActionResult> GetDriftSummary()
        {
            try
            {
                var db = _redis.GetDatabase();
                var summaryJson = await db.StringGetAsync("drift:summary:latest");

                if (summaryJson.HasValue)
                {
                    var summary = JsonSerializer.Deserialize<DriftSummary>(summaryJson!);
                    return Ok(summary);
                }

                // If no cached data, try to get real-time data from repositories
                try
                {
                    var activeModels = await _modelRepo.GetByStatusAsync(ModelStatus.Active, 10000); // Increase limit to handle large datasets
                    
                    var summary = new DriftSummary
                    {
                        Timestamp = DateTime.UtcNow,
                        TotalModelsMonitored = activeModels.Count(),
                        ModelsWithDrift = 0, // Will be calculated by monitoring service
                        AverageDataDriftScore = 0.0,
                        AverageConceptDriftScore = 0.0,
                        CriticalModels = 0
                    };

                    // Cache the summary
                    await db.StringSetAsync(
                        "drift:summary:latest",
                        JsonSerializer.Serialize(summary),
                        expiry: TimeSpan.FromMinutes(5));

                    return Ok(summary);
                }
                catch (Exception dbEx)
                {
                    _logger.LogWarning(dbEx, "Could not access database, returning default summary");
                    
                    // Return minimal default summary if database is unavailable
                    return Ok(new DriftSummary
                    {
                        Timestamp = DateTime.UtcNow,
                        TotalModelsMonitored = 0,
                        ModelsWithDrift = 0,
                        AverageDataDriftScore = 0.0,
                        AverageConceptDriftScore = 0.0,
                        CriticalModels = 0
                    });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving drift summary");
                return StatusCode(500, new { 
                    error = "Internal server error", 
                    details = ex.Message,
                    suggestion = "Try initializing the drift service using POST /api/drift/initialize"
                });
            }
        }

        /// <summary>
        /// Get drift metrics for a specific model
        /// </summary>
        [HttpGet("model/{modelId}")]
        public async Task<IActionResult> GetModelDriftMetrics(Guid modelId)
        {
            try
            {
                var db = _redis.GetDatabase();
                var metricsKey = $"drift:metrics:{modelId}";
                var metricsJson = await db.StringGetAsync(metricsKey);

                if (metricsJson.HasValue)
                {
                    var metrics = JsonSerializer.Deserialize<DriftMetrics>(metricsJson!);
                    return Ok(metrics);
                }

                return NotFound($"No drift metrics found for model {modelId}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error retrieving drift metrics for model {modelId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Get drift history for a model
        /// </summary>
        [HttpGet("model/{modelId}/history")]
        public async Task<IActionResult> GetModelDriftHistory(Guid modelId, [FromQuery] int limit = 100)
        {
            try
            {
                var db = _redis.GetDatabase();
                var timeSeriesKey = $"drift:timeseries:{modelId}";
                var history = await db.SortedSetRangeByScoreAsync(
                    timeSeriesKey,
                    order: Order.Descending,
                    take: limit);

                var metrics = history
                    .Select(h => JsonSerializer.Deserialize<DriftMetrics>(h!))
                    .ToList();

                return Ok(new
                {
                    modelId,
                    count = metrics.Count,
                    metrics
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error retrieving drift history for model {modelId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Get recent drift alerts
        /// </summary>
        [HttpGet("alerts")]
        public async Task<IActionResult> GetDriftAlerts([FromQuery] int limit = 50)
        {
            try
            {
                var db = _redis.GetDatabase();
                var alertsKey = "drift:alerts:history";
                var alerts = await db.ListRangeAsync(alertsKey, 0, limit - 1);

                var alertList = alerts
                    .Where(a => a.HasValue)
                    .Select(a => JsonSerializer.Deserialize<DriftAlert>(a!))
                    .ToList();

                return Ok(new
                {
                    count = alertList.Count,
                    alerts = alertList
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving drift alerts");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Manually check drift for specific data
        /// </summary>
        [HttpPost("check")]
        public async Task<IActionResult> CheckDrift([FromBody] DriftCheckRequest request)
        {
            try
            {
                // Get baseline transactions
                var baselineEnd = DateTimeOffset.UtcNow.AddDays(-request.BaselineDaysAgo);
                var baselineStart = baselineEnd.AddDays(-request.WindowSizeDays);
                var baselineTransactions = await _transactionRepo.GetByTimeRangeAsync(
                    baselineStart, baselineEnd);

                // Get current transactions
                var currentEnd = DateTimeOffset.UtcNow;
                var currentStart = currentEnd.AddDays(-request.WindowSizeDays);
                var currentTransactions = await _transactionRepo.GetByTimeRangeAsync(
                    currentStart, currentEnd);

                if (!baselineTransactions.Any() || !currentTransactions.Any())
                {
                    return BadRequest("Insufficient data for drift detection");
                }

                // Perform drift detection
                var result = await _driftDetector.DetectDataDriftAsync(
                    baselineTransactions.Select(t => t.Data),
                    currentTransactions.Select(t => t.Data),
                    new DriftDetectionConfig
                    {
                        DriftThreshold = request.DriftThreshold ?? 0.1,
                        PSIThreshold = request.PSIThreshold ?? 0.2
                    });

                return Ok(new
                {
                    checkTimestamp = DateTime.UtcNow,
                    baselinePeriod = new { start = baselineStart, end = baselineEnd },
                    currentPeriod = new { start = currentStart, end = currentEnd },
                    baselineSamples = baselineTransactions.Count,
                    currentSamples = currentTransactions.Count,
                    driftDetected = result.IsDriftDetected,
                    driftScore = result.DriftScore,
                    severity = result.Severity.ToString(),
                    affectedFeatures = result.AffectedFeatures,
                    featureScores = result.FeatureDriftScores,
                    description = result.Description
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking drift");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Get feature drift analysis
        /// </summary>
        [HttpGet("features/{featureName}")]
        public async Task<IActionResult> GetFeatureDrift(
            string featureName,
            [FromQuery] int hours = 24)
        {
            try
            {
                var endTime = DateTimeOffset.UtcNow;
                var startTime = endTime.AddHours(-hours);
                
                // Get transactions in time window
                var transactions = await _transactionRepo.GetByTimeRangeAsync(startTime, endTime);
                
                if (!transactions.Any())
                {
                    return Ok(new { message = "No data available for analysis" });
                }

                // Extract feature values
                var featureValues = ExtractFeatureValues(transactions, featureName);
                
                if (!featureValues.Any())
                {
                    return BadRequest($"Feature '{featureName}' not found");
                }

                // Monitor feature drift
                var report = await _driftDetector.MonitorFeatureDriftAsync(
                    featureName,
                    featureValues,
                    startTime.DateTime,
                    endTime.DateTime);

                return Ok(new
                {
                    feature = featureName,
                    timeWindow = new { start = startTime, end = endTime },
                    samples = featureValues.Count,
                    driftScore = report.DriftScore,
                    meanShift = report.MeanShift,
                    varianceShift = report.VarianceShift,
                    timeline = report.DriftTimeline?.Take(100) // Limit timeline points
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error analyzing feature drift for {featureName}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Initialize drift detection service with sample data
        /// </summary>
        [HttpPost("initialize")]
        public async Task<IActionResult> InitializeDriftService()
        {
            try
            {
                var db = _redis.GetDatabase();
                
                // Initialize drift summary with default values
                var summary = new DriftSummary
                {
                    Timestamp = DateTime.UtcNow,
                    TotalModelsMonitored = 0,
                    ModelsWithDrift = 0,
                    AverageDataDriftScore = 0.0,
                    AverageConceptDriftScore = 0.0,
                    CriticalModels = 0
                };

                await db.StringSetAsync(
                    "drift:summary:latest",
                    JsonSerializer.Serialize(summary),
                    expiry: TimeSpan.FromHours(1));

                _logger.LogInformation("Drift detection service initialized successfully");

                return Ok(new
                {
                    message = "Drift detection service initialized successfully",
                    summary = summary,
                    timestamp = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error initializing drift detection service");
                return StatusCode(500, new { error = "Failed to initialize drift service", details = ex.Message });
            }
        }

        /// <summary>
        /// Trigger model retraining
        /// </summary>
        [HttpPost("retrain/{modelId}")]
        public async Task<IActionResult> TriggerRetraining(Guid modelId, [FromBody] RetrainRequest request)
        {
            try
            {
                var model = await _modelRepo.GetByIdAsync(modelId);
                if (model == null)
                {
                    return NotFound($"Model {modelId} not found");
                }

                var db = _redis.GetDatabase();
                var retrainQueue = "model:retrain:queue";
                
                var retrainRequest = new ModelRetrainRequest
                {
                    ModelId = modelId,
                    RequestedAt = DateTime.UtcNow,
                    Reason = request?.Reason ?? "Manual retraining request",
                    Priority = request?.Priority ?? "Normal"
                };

                await db.ListLeftPushAsync(
                    retrainQueue,
                    JsonSerializer.Serialize(retrainRequest));

                _logger.LogInformation($"Retraining triggered for model {modelId}: {retrainRequest.Reason}");

                return Ok(new
                {
                    message = "Retraining request queued successfully",
                    modelId,
                    requestId = Guid.NewGuid(),
                    timestamp = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error triggering retraining for model {modelId}");
                return StatusCode(500, "Internal server error");
            }
        }

        private List<double> ExtractFeatureValues(IEnumerable<Transaction> transactions, string featureName)
        {
            var values = new List<double>();

            foreach (var transaction in transactions)
            {
                switch (featureName.ToLower())
                {
                    case "thickness":
                        values.Add(transaction.Data.Thickness);
                        break;
                    case "xcoord":
                        values.Add(transaction.Data.XCoord);
                        break;
                    case "ycoord":
                        values.Add(transaction.Data.YCoord);
                        break;
                    case "quality":
                        values.Add(transaction.Data.Quality);
                        break;
                    case "minthickness":
                        values.Add(transaction.Data.MinThickness);
                        break;
                    default:
                        // Check features dictionary
                        if (transaction.Data.Features?.ContainsKey(featureName) == true)
                        {
                            values.Add(transaction.Data.Features[featureName]);
                        }
                        break;
                }
            }

            return values;
        }

        private async Task<bool> CheckRedisHealth()
        {
            try
            {
                var db = _redis.GetDatabase();
                await db.PingAsync();
                return true;
            }
            catch
            {
                return false;
            }
        }

        private async Task<bool> CheckDatabaseHealth()
        {
            try
            {
                await _modelRepo.GetByStatusAsync(ModelStatus.Active, 1);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private bool CheckDriftDetectorHealth()
        {
            try
            {
                return _driftDetector != null;
            }
            catch
            {
                return false;
            }
        }
    }

    public class DriftCheckRequest
    {
        public int BaselineDaysAgo { get; set; } = 7;
        public int WindowSizeDays { get; set; } = 1;
        public double? DriftThreshold { get; set; }
        public double? PSIThreshold { get; set; }
    }

    public class RetrainRequest
    {
        public string? Reason { get; set; }
        public string Priority { get; set; } = "Normal";
    }
}
