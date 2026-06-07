using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using TML.Core.Domain;
using TML.Storage.Repositories;
using TML.Storage.Services;
using TML.Actors.Services;
using TML.Actors.Messages;
using Proto;

namespace TML.API.Controllers;

/// <summary>
/// API controller for model management
/// </summary>
[ApiController]
[Route("api/[controller]")]
// [Authorize] // Temporarily disabled for testing
public class ModelsController : ControllerBase
{
    private readonly IModelRepository _modelRepository;
    private readonly IS3ModelArtifactService _s3Service;
    private readonly IRedisCacheService _cacheService;
    private readonly ActorSystemService _actorSystem;
    private readonly ILogger<ModelsController> _logger;

    public ModelsController(
        IModelRepository modelRepository,
        IS3ModelArtifactService s3Service,
        IRedisCacheService cacheService,
        ActorSystemService actorSystem,
        ILogger<ModelsController> logger)
    {
        _modelRepository = modelRepository ?? throw new ArgumentNullException(nameof(modelRepository));
        _s3Service = s3Service ?? throw new ArgumentNullException(nameof(s3Service));
        _cacheService = cacheService ?? throw new ArgumentNullException(nameof(cacheService));
        _actorSystem = actorSystem ?? throw new ArgumentNullException(nameof(actorSystem));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Get all models with optional filtering
    /// </summary>
    [HttpGet]
    [ProducesResponseType(typeof(IEnumerable<ModelResponse>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<ActionResult<IEnumerable<ModelResponse>>> GetModels(
        [FromQuery] int? limit = 100,
        [FromQuery] int? offset = 0,
        [FromQuery] string? status = null)
    {
        try
        {
            IEnumerable<Model> models;
            
            // Get models based on status filter
            if (!string.IsNullOrEmpty(status) && Enum.TryParse<ModelStatus>(status, out var statusEnum))
            {
                models = await _modelRepository.GetByStatusAsync(statusEnum, limit ?? 100);
            }
            else
            {
                // Get active models as default
                models = await _modelRepository.GetByStatusAsync(ModelStatus.Active, limit ?? 100);
            }
            
            // Apply pagination
            models = models
                .OrderByDescending(m => m.CreatedAt)
                .Skip(offset ?? 0)
                .Take(Math.Min(limit ?? 100, 1000));
            
            var result = models.Select(MapToModelResponse).ToList();
            
            return result.Any() ? Ok(result) : NoContent();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving models");
            return StatusCode(500, "Internal server error");
        }
    }
    
    /// <summary>
    /// Get model statistics
    /// </summary>
    [HttpGet("statistics")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    public async Task<ActionResult> GetStatistics()
    {
        try
        {
            var modelStats = await _modelRepository.GetStatisticsAsync();
            var recentModels = await _modelRepository.GetByStatusAsync(ModelStatus.Active, 10);
            
            var enrichedStats = new
            {
                modelStats.TotalCount,
                modelStats.AverageInheritanceDepth,
                modelStats.AverageConfidence,
                modelStats.AverageRSquared,
                RecentModels = recentModels
                    .OrderByDescending(m => m.CreatedAt)
                    .Take(10)
                    .Select(m => new
                    {
                        m.Id,
                        Status = m.Status.ToString(),
                        m.InheritanceDepth,
                        Confidence = m.Metrics.Confidence,
                        m.CreatedAt
                    })
            };
            
            return Ok(enrichedStats);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calculating model statistics");
            return StatusCode(500, "Internal server error");
        }
    }
    
    /// <summary>
    /// Find models within spatial radius
    /// </summary>
    [HttpGet("spatial/neighbors")]
    [ProducesResponseType(typeof(IEnumerable<ModelResponse>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<ActionResult<IEnumerable<ModelResponse>>> GetSpatialNeighbors(
        [FromQuery] double x,
        [FromQuery] double y,
        [FromQuery] double radius,
        [FromQuery] int maxResults = 10)
    {
        try
        {
            if (radius <= 0 || radius > 1000)
                return BadRequest("Radius must be between 0 and 1000");
            
            if (maxResults <= 0 || maxResults > 100)
                return BadRequest("MaxResults must be between 1 and 100");
            
            // Use the repository's spatial search method
            var neighbors = await _modelRepository.FindSpatialNeighborsAsync(x, y, radius, maxResults);
            
            var result = neighbors
                .Select(MapToModelResponse)
                .ToList();
            
            return result.Any() ? Ok(result) : NoContent();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error finding spatial neighbors");
            return StatusCode(500, "Internal server error");
        }
    }
    
    /// <summary>
    /// Get model by ID
    /// </summary>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(ModelResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ModelResponse>> GetModel(Guid id)
    {
        // Try cache first
        var model = await _cacheService.GetModelAsync(id);
        
        if (model == null)
        {
            // Load from database
            model = await _modelRepository.GetByIdAsync(id);
            
            if (model == null)
                return NotFound();
            
            // Cache for future requests
            await _cacheService.SetModelAsync(id, model, TimeSpan.FromMinutes(30));
        }

        return Ok(MapToModelResponse(model));
    }

    /// <summary>
    /// Search models by criteria
    /// </summary>
    [HttpPost("search")]
    [ProducesResponseType(typeof(List<ModelResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<List<ModelResponse>>> SearchModels([FromBody] ModelSearchRequest request)
    {
        var criteria = new ModelSearchCriteria
        {
            Status = request.Status != null ? Enum.Parse<ModelStatus>(request.Status) : null,
            MinInheritanceDepth = request.MinInheritanceDepth,
            MaxInheritanceDepth = request.MaxInheritanceDepth,
            MinConfidence = request.MinConfidence,
            MaxConfidence = request.MaxConfidence,
            MinRSquared = request.MinRSquared,
            MaxRSquared = request.MaxRSquared,
            CreatedAfter = request.CreatedAfter,
            CreatedBefore = request.CreatedBefore,
            GridId = request.GridId,
            SpatialX = request.SpatialX,
            SpatialY = request.SpatialY,
            SpatialRadius = request.SpatialRadius,
            PhysicsValid = request.PhysicsValid,
            Limit = request.Limit,
            Offset = request.Offset,
            OrderBy = request.OrderBy,
            Descending = request.Descending
        };

        var models = await _modelRepository.SearchAsync(criteria);
        return Ok(models.Select(MapToModelResponse).ToList());
    }

    /// <summary>
    /// Find spatial neighbors for a location
    /// </summary>
    [HttpGet("spatial-neighbors")]
    [ProducesResponseType(typeof(List<ModelResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<List<ModelResponse>>> FindSpatialNeighbors(
        [FromQuery] double x, 
        [FromQuery] double y, 
        [FromQuery] double radius = 50.0, 
        [FromQuery] int maxResults = 10)
    {
        // Check cache for this location
        var cacheKey = $"{x:F2}_{y:F2}_{radius:F2}";
        var cachedNeighbors = await _cacheService.GetSpatialNeighborsAsync(cacheKey);
        
        List<Model> models;
        if (cachedNeighbors != null)
        {
            // Load models from cache
            models = new List<Model>();
            foreach (var modelId in cachedNeighbors)
            {
                var model = await _cacheService.GetModelAsync(modelId) ?? 
                           await _modelRepository.GetByIdAsync(modelId);
                if (model != null)
                    models.Add(model);
            }
        }
        else
        {
            // Find from database
            models = (await _modelRepository.FindSpatialNeighborsAsync(x, y, radius, maxResults)).ToList();
            
            // Cache the result
            var modelIds = models.Select(m => m.Id).ToList();
            await _cacheService.SetSpatialNeighborsAsync(cacheKey, modelIds, TimeSpan.FromMinutes(15));
        }

        return Ok(models.Select(MapToModelResponse).ToList());
    }

    /// <summary>
    /// Get model inheritance chain
    /// </summary>
    [HttpGet("{id}/inheritance-chain")]
    [ProducesResponseType(typeof(List<ModelResponse>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<List<ModelResponse>>> GetInheritanceChain(Guid id)
    {
        var chain = await _modelRepository.GetInheritanceChainAsync(id);
        if (!chain.Any())
            return NotFound();

        return Ok(chain.Select(MapToModelResponse).ToList());
    }

    /// <summary>
    /// Download model artifacts from S3
    /// </summary>
    [HttpGet("{id}/artifacts")]
    [ProducesResponseType(typeof(string), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<string>> GetModelArtifacts(Guid id)
    {
        var model = await _modelRepository.GetByIdAsync(id);
        if (model == null || string.IsNullOrEmpty(model.ArtifactLocation))
            return NotFound();

        // Generate pre-signed URL for download
        var downloadUrl = await _s3Service.GetDownloadUrlAsync(
            model.ArtifactLocation, 
            TimeSpan.FromHours(1));

        return Ok(new { downloadUrl });
    }

    /// <summary>
    /// List all versions of a model's artifacts
    /// </summary>
    [HttpGet("{id}/versions")]
    [ProducesResponseType(typeof(List<ModelArtifactVersion>), StatusCodes.Status200OK)]
    public async Task<ActionResult<List<ModelArtifactVersion>>> ListModelVersions(Guid id)
    {
        var versions = await _s3Service.ListModelVersionsAsync(id);
        return Ok(versions);
    }

    /// <summary>
    /// Archive old model versions to cheaper storage
    /// </summary>
    [HttpPost("{id}/archive")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> ArchiveModelVersions(Guid id, [FromQuery] int keepLatestVersions = 5)
    {
        var model = await _modelRepository.GetByIdAsync(id);
        if (model == null)
            return NotFound();

        await _s3Service.ArchiveOldVersionsAsync(id, keepLatestVersions);
        
        _logger.LogInformation("Archived old versions for model {ModelId}, keeping {KeepVersions} latest", 
            id, keepLatestVersions);
        
        return NoContent();
    }

    /// <summary>
    /// Validate physics for a model
    /// </summary>
    [HttpPost("{id}/validate-physics")]
    [ProducesResponseType(typeof(PhysicsValidationResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<PhysicsValidationResponse>> ValidatePhysics(Guid id)
    {
        var model = await _modelRepository.GetByIdAsync(id);
        if (model == null)
            return NotFound();

        // Get physics validator actor
        var validator = _actorSystem.GetPhysicsValidator();
        if (validator == null)
        {
            _logger.LogError("No physics validator available");
            return StatusCode(503, "Service temporarily unavailable");
        }

        // Get transaction data for validation
        var transaction = await _modelRepository.GetByTransactionIdAsync(model.TransactionId);
        if (!transaction.Any())
            return NotFound("Transaction data not found");

        var transactionData = transaction.First().Location; // Get transaction location data

        // Send validation request
        var validationMessage = new ValidatePhysics(
            new TransactionData
            {
                XCoord = model.Location.X,
                YCoord = model.Location.Y,
                Thickness = model.Parameters.Weights.FirstOrDefault() * 20.0, // Simplified
                MinThickness = 15.0,
                Features = new Dictionary<string, double>(),
                Quality = model.Metrics.Confidence
            },
            model
        );

        var response = await _actorSystem.Root.RequestAsync<PhysicsValidated>(
            validator,
            validationMessage,
            TimeSpan.FromSeconds(10));

        return Ok(new PhysicsValidationResponse
        {
            IsValid = response.IsValid,
            ValidationScore = response.Validation.ValidationScore,
            ThicknessValid = response.Validation.ThicknessValid,
            EnergyConservationValid = response.Validation.EnergyConservationValid,
            MassConservationValid = response.Validation.MassConservationValid,
            Violations = response.Violations
        });
    }

    private ModelResponse MapToModelResponse(Model model)
    {
        return new ModelResponse
        {
            Id = model.Id,
            TransactionId = model.TransactionId,
            ParentModelId = model.ParentModelId,
            InheritanceDepth = model.InheritanceDepth,
            Status = model.Status.ToString(),
            CreatedAt = model.CreatedAt,
            UpdatedAt = model.UpdatedAt,
            Version = model.Version,
            Location = new LocationDto
            {
                X = model.Location.X,
                Y = model.Location.Y,
                Z = model.Location.Z,
                GridId = model.Location.GridId
            },
            Metrics = new MetricsDto
            {
                MeanSquaredError = model.Metrics.MeanSquaredError,
                RootMeanSquaredError = model.Metrics.RootMeanSquaredError,
                MeanAbsoluteError = model.Metrics.MeanAbsoluteError,
                RSquared = model.Metrics.RSquared,
                Confidence = model.Metrics.Confidence,
                TrainingDataPoints = model.Metrics.TrainingDataPoints
            },
            PhysicsValidation = new PhysicsDto
            {
                IsValid = model.PhysicsValidation.IsValid,
                ValidationScore = model.PhysicsValidation.ValidationScore,
                Violations = model.PhysicsValidation.Violations
            },
            ArtifactLocation = model.ArtifactLocation
        };
    }
}

// Request/Response DTOs

public class ModelSearchRequest
{
    public string? Status { get; set; }
    public int? MinInheritanceDepth { get; set; }
    public int? MaxInheritanceDepth { get; set; }
    public double? MinConfidence { get; set; }
    public double? MaxConfidence { get; set; }
    public double? MinRSquared { get; set; }
    public double? MaxRSquared { get; set; }
    public DateTimeOffset? CreatedAfter { get; set; }
    public DateTimeOffset? CreatedBefore { get; set; }
    public string? GridId { get; set; }
    public double? SpatialX { get; set; }
    public double? SpatialY { get; set; }
    public double? SpatialRadius { get; set; }
    public bool? PhysicsValid { get; set; }
    public int Limit { get; set; } = 100;
    public int Offset { get; set; } = 0;
    public string OrderBy { get; set; } = "CreatedAt";
    public bool Descending { get; set; } = true;
}

public class ModelResponse
{
    public Guid Id { get; set; }
    public Guid TransactionId { get; set; }
    public Guid? ParentModelId { get; set; }
    public int InheritanceDepth { get; set; }
    public string Status { get; set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int Version { get; set; }
    public LocationDto Location { get; set; } = null!;
    public MetricsDto Metrics { get; set; } = null!;
    public PhysicsDto PhysicsValidation { get; set; } = null!;
    public string? ArtifactLocation { get; set; }
}

public class LocationDto
{
    public double X { get; set; }
    public double Y { get; set; }
    public double? Z { get; set; }
    public string? GridId { get; set; }
}

public class MetricsDto
{
    public double MeanSquaredError { get; set; }
    public double RootMeanSquaredError { get; set; }
    public double MeanAbsoluteError { get; set; }
    public double RSquared { get; set; }
    public double Confidence { get; set; }
    public int TrainingDataPoints { get; set; }
}

public class PhysicsDto
{
    public bool IsValid { get; set; }
    public double ValidationScore { get; set; }
    public List<string> Violations { get; set; } = new();
}

public class PhysicsValidationResponse
{
    public bool IsValid { get; set; }
    public double ValidationScore { get; set; }
    public bool ThicknessValid { get; set; }
    public bool EnergyConservationValid { get; set; }
    public bool MassConservationValid { get; set; }
    public IReadOnlyList<string> Violations { get; set; } = new List<string>();
}
