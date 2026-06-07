using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using TML.MLOps.ABTesting;
using TML.Storage.Repositories;

namespace TML.API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ExperimentController : ControllerBase
    {
        private readonly ILogger<ExperimentController> _logger;
        private readonly IExperimentManager _experimentManager;
        private readonly IModelRepository _modelRepository;

        public ExperimentController(
            ILogger<ExperimentController> logger,
            IExperimentManager experimentManager,
            IModelRepository modelRepository)
        {
            _logger = logger;
            _experimentManager = experimentManager;
            _modelRepository = modelRepository;
        }

        /// <summary>
        /// Create a new A/B test experiment
        /// </summary>
        [HttpPost]
        public async Task<IActionResult> CreateExperiment([FromBody] CreateExperimentRequest request)
        {
            try
            {
                // Validate models exist
                foreach (var variant in request.Variants)
                {
                    var model = await _modelRepository.GetByIdAsync(variant.ModelId);
                    if (model == null)
                    {
                        return BadRequest($"Model {variant.ModelId} not found");
                    }
                }

                // Create experiment configuration
                var config = new ExperimentConfig
                {
                    Name = request.Name,
                    Description = request.Description,
                    Variants = request.Variants.Select(v => new VariantConfig
                    {
                        Id = Guid.NewGuid().ToString(),
                        Name = v.Name,
                        ModelId = v.ModelId,
                        TrafficPercentage = v.TrafficPercentage,
                        IsControl = v.IsControl,
                        Parameters = v.Parameters
                    }).ToList(),
                    TrafficAllocation = new TrafficAllocation
                    {
                        Type = request.AllocationType,
                        UseStickySessions = request.UseStickySessions
                    },
                    SuccessMetrics = new SuccessMetrics
                    {
                        PrimaryMetric = request.PrimaryMetric,
                        SecondaryMetrics = request.SecondaryMetrics,
                        MinimumDetectableEffect = request.MinimumDetectableEffect ?? 0.05
                    },
                    MinDuration = TimeSpan.FromDays(request.MinDurationDays ?? 7),
                    MinSampleSize = request.MinSampleSize ?? 1000,
                    ConfidenceLevel = request.ConfidenceLevel ?? 0.95
                };

                var experiment = await _experimentManager.CreateExperimentAsync(config);

                return Ok(new
                {
                    experimentId = experiment.Id,
                    name = experiment.Name,
                    status = experiment.Status.ToString(),
                    startedAt = experiment.StartedAt,
                    variants = experiment.Variants.Select(v => new
                    {
                        id = v.Id,
                        name = v.Name,
                        modelId = v.ModelId,
                        trafficPercentage = v.TrafficPercentage,
                        isControl = v.IsControl
                    })
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating experiment");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Get experiment by ID
        /// </summary>
        [HttpGet("{experimentId}")]
        public async Task<IActionResult> GetExperiment(Guid experimentId)
        {
            try
            {
                var experiments = await _experimentManager.GetExperimentsAsync();
                var experiment = experiments.FirstOrDefault(e => e.Id == experimentId);

                if (experiment == null)
                {
                    return NotFound($"Experiment {experimentId} not found");
                }

                return Ok(experiment);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error retrieving experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// List all experiments
        /// </summary>
        [HttpGet]
        public async Task<IActionResult> ListExperiments([FromQuery] ExperimentStatus? status = null)
        {
            try
            {
                var experiments = await _experimentManager.GetExperimentsAsync(status);

                return Ok(new
                {
                    count = experiments.Count,
                    experiments = experiments.Select(e => new
                    {
                        id = e.Id,
                        name = e.Name,
                        status = e.Status.ToString(),
                        startedAt = e.StartedAt,
                        endedAt = e.EndedAt,
                        variantCount = e.Variants?.Count ?? 0,
                        winner = e.WinnerVariantId
                    })
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error listing experiments");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Route a request to get variant assignment
        /// </summary>
        [HttpPost("{experimentId}/route")]
        public async Task<IActionResult> RouteRequest(
            Guid experimentId,
            [FromBody] RouteRequest request)
        {
            try
            {
                var variant = await _experimentManager.RouteRequestAsync(
                    experimentId,
                    request?.UserId ?? string.Empty,
                    request?.Context ?? new Dictionary<string, object>());

                if (variant == null)
                {
                    return NotFound("Experiment not found or not running");
                }

                return Ok(new
                {
                    variantId = variant.Id,
                    variantName = variant.Name,
                    modelId = variant.ModelId,
                    parameters = variant.Parameters
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error routing request for experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Record conversion/outcome for an experiment
        /// </summary>
        [HttpPost("{experimentId}/outcome")]
        public async Task<IActionResult> RecordOutcome(
            Guid experimentId,
            [FromBody] RecordOutcomeRequest request)
        {
            try
            {
                var outcome = new ExperimentOutcome
                {
                    MetricName = request.MetricName,
                    Value = request.Value,
                    Timestamp = DateTime.UtcNow,
                    UserId = request.UserId ?? string.Empty,
                    Context = request.Context ?? new Dictionary<string, object>()
                };

                await _experimentManager.RecordOutcomeAsync(
                    experimentId,
                    request.VariantId,
                    outcome);

                return Ok(new
                {
                    message = "Outcome recorded successfully",
                    timestamp = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error recording outcome for experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Analyze experiment results
        /// </summary>
        [HttpGet("{experimentId}/results")]
        public async Task<IActionResult> AnalyzeExperiment(Guid experimentId)
        {
            try
            {
                var results = await _experimentManager.AnalyzeExperimentAsync(experimentId);

                return Ok(new
                {
                    experimentId = results.ExperimentId,
                    analyzedAt = results.AnalyzedAt,
                    totalSamples = results.TotalSamples,
                    recommendedWinner = results.RecommendedWinner,
                    isSignificant = results.Significance?.IsSignificant ?? false,
                    pValue = results.Significance?.PValue ?? 1.0,
                    powerAnalysis = results.PowerAnalysis,
                    confidenceInterval = results.ConfidenceInterval,
                    variants = results.VariantResults.Select(v => new
                    {
                        variantId = v.Key,
                        sampleSize = v.Value.SampleSize,
                        conversionRate = v.Value.ConversionRate,
                        lift = v.Value.Lift,
                        pValue = v.Value.PValue,
                        isSignificant = v.Value.IsStatisticallySignificant
                    }),
                    warnings = results.Warnings
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error analyzing experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Conclude an experiment
        /// </summary>
        [HttpPost("{experimentId}/conclude")]
        public async Task<IActionResult> ConcludeExperiment(
            Guid experimentId,
            [FromQuery] bool autoPromote = true)
        {
            try
            {
                var conclusion = await _experimentManager.ConcludeExperimentAsync(
                    experimentId,
                    autoPromote);

                return Ok(new
                {
                    experimentId = conclusion.ExperimentId,
                    winner = conclusion.WinnerVariantId,
                    lift = conclusion.WinnerLift,
                    confidence = conclusion.Confidence,
                    reason = conclusion.ConclusionReason,
                    wasAutoPromoted = conclusion.WasAutoPromoted,
                    concludedAt = conclusion.ConcludedAt
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error concluding experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Stop an experiment
        /// </summary>
        [HttpPost("{experimentId}/stop")]
        public async Task<IActionResult> StopExperiment(
            Guid experimentId,
            [FromBody] StopExperimentRequest request)
        {
            try
            {
                await _experimentManager.StopExperimentAsync(
                    experimentId,
                    request?.Reason ?? "Manual stop");

                return Ok(new
                {
                    message = "Experiment stopped successfully",
                    experimentId,
                    stoppedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error stopping experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }

        /// <summary>
        /// Get experiment recommendations based on current performance
        /// </summary>
        [HttpGet("{experimentId}/recommendations")]
        public async Task<IActionResult> GetRecommendations(Guid experimentId)
        {
            try
            {
                var results = await _experimentManager.AnalyzeExperimentAsync(experimentId);
                var experiments = await _experimentManager.GetExperimentsAsync();
                var experiment = experiments.FirstOrDefault(e => e.Id == experimentId);

                if (experiment == null)
                {
                    return NotFound($"Experiment {experimentId} not found");
                }

                var recommendations = new List<string>();
                var duration = DateTime.UtcNow - experiment.StartedAt;

                // Check if we can conclude
                if (results.Significance?.IsSignificant == true && 
                    results.TotalSamples >= experiment.Configuration.MinSampleSize)
                {
                    recommendations.Add("✅ Experiment has reached statistical significance and can be concluded");
                }

                // Check sample size
                if (results.TotalSamples < experiment.Configuration.MinSampleSize)
                {
                    var needed = experiment.Configuration.MinSampleSize - results.TotalSamples;
                    recommendations.Add($"📊 Need {needed} more samples to reach minimum sample size");
                }

                // Check duration
                if (duration < experiment.Configuration.MinDuration)
                {
                    var remaining = experiment.Configuration.MinDuration - duration;
                    recommendations.Add($"⏱️ Need to run for {remaining.TotalDays:F1} more days to reach minimum duration");
                }

                // Check power
                if (results.PowerAnalysis < 0.8)
                {
                    recommendations.Add($"⚡ Statistical power is low ({results.PowerAnalysis:P0}), consider increasing sample size");
                }

                // Check for sample ratio mismatch
                if (results.Warnings?.Any(w => w.Contains("ratio mismatch")) == true)
                {
                    recommendations.Add("⚠️ Sample ratio mismatch detected, check traffic allocation");
                }

                return Ok(new
                {
                    experimentId,
                    status = experiment.Status.ToString(),
                    duration = duration.TotalDays,
                    totalSamples = results.TotalSamples,
                    recommendations,
                    canConclude = results.Significance?.IsSignificant == true && 
                                 results.TotalSamples >= experiment.Configuration.MinSampleSize &&
                                 duration >= experiment.Configuration.MinDuration
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting recommendations for experiment {experimentId}");
                return StatusCode(500, "Internal server error");
            }
        }
    }

    public class CreateExperimentRequest
    {
        public string Name { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public List<CreateVariantRequest> Variants { get; set; } = new();
        public AllocationType AllocationType { get; set; } = AllocationType.Random;
        public bool UseStickySessions { get; set; } = true;
        public string PrimaryMetric { get; set; } = string.Empty;
        public List<string> SecondaryMetrics { get; set; } = new();
        public double? MinimumDetectableEffect { get; set; }
        public int? MinDurationDays { get; set; }
        public int? MinSampleSize { get; set; }
        public double? ConfidenceLevel { get; set; }
    }

    public class CreateVariantRequest
    {
        public string Name { get; set; } = string.Empty;
        public Guid ModelId { get; set; }
        public double TrafficPercentage { get; set; }
        public bool IsControl { get; set; }
        public Dictionary<string, object> Parameters { get; set; } = new();
    }

    public class RouteRequest
    {
        public string? UserId { get; set; }
        public Dictionary<string, object>? Context { get; set; }
    }

    public class RecordOutcomeRequest
    {
        public string VariantId { get; set; } = string.Empty;
        public string MetricName { get; set; } = string.Empty;
        public double Value { get; set; }
        public string? UserId { get; set; }
        public Dictionary<string, object>? Context { get; set; }
    }

    public class StopExperimentRequest
    {
        public string? Reason { get; set; }
    }
}
