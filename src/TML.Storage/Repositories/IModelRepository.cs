using TML.Core.Domain;

namespace TML.Storage.Repositories;

/// <summary>
/// Repository interface for Model data access
/// </summary>
public interface IModelRepository
{
    /// <summary>
    /// Create a new model
    /// </summary>
    Task<Model> CreateAsync(Model model, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Update an existing model
    /// </summary>
    Task<Model> UpdateAsync(Model model, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get model by ID
    /// </summary>
    Task<Model?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get models by transaction ID
    /// </summary>
    Task<IReadOnlyList<Model>> GetByTransactionIdAsync(Guid transactionId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get models by parent model ID (inheritance chain)
    /// </summary>
    Task<IReadOnlyList<Model>> GetByParentModelIdAsync(Guid parentModelId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Find spatial neighbors within radius
    /// </summary>
    Task<IReadOnlyList<Model>> FindSpatialNeighborsAsync(double x, double y, double radius, int maxResults = 10, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get models in spatial grid
    /// </summary>
    Task<IReadOnlyList<Model>> GetByGridIdAsync(string gridId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get models by status
    /// </summary>
    Task<IReadOnlyList<Model>> GetByStatusAsync(ModelStatus status, int limit = 100, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get models by inheritance depth
    /// </summary>
    Task<IReadOnlyList<Model>> GetByInheritanceDepthAsync(int depth, int limit = 100, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get inheritance chain for a model
    /// </summary>
    Task<IReadOnlyList<Model>> GetInheritanceChainAsync(Guid modelId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get model statistics
    /// </summary>
    Task<ModelStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Delete model by ID
    /// </summary>
    Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Batch create models
    /// </summary>
    Task<IReadOnlyList<Model>> CreateBatchAsync(IEnumerable<Model> models, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Search models by criteria
    /// </summary>
    Task<IReadOnlyList<Model>> SearchAsync(ModelSearchCriteria criteria, CancellationToken cancellationToken = default);
}

/// <summary>
/// Model statistics
/// </summary>
public class ModelStatistics
{
    public long TotalCount { get; set; }
    public long ActiveCount { get; set; }
    public long TrainingCount { get; set; }
    public long ArchivedCount { get; set; }
    public long DeprecatedCount { get; set; }
    public long FailedCount { get; set; }
    public int MaxInheritanceDepth { get; set; }
    public double AverageInheritanceDepth { get; set; }
    public double AverageConfidence { get; set; }
    public double AverageRSquared { get; set; }
    public DateTimeOffset? OldestModel { get; set; }
    public DateTimeOffset? NewestModel { get; set; }
}

/// <summary>
/// Model search criteria
/// </summary>
public class ModelSearchCriteria
{
    public ModelStatus? Status { get; set; }
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
    public string? OrderBy { get; set; } = "CreatedAt";
    public bool Descending { get; set; } = true;
}
