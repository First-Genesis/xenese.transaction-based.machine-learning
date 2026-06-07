using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using TML.Core.Domain;
using TML.Storage.Data;

namespace TML.Storage.Repositories;

/// <summary>
/// PostgreSQL implementation of model repository with spatial indexing
/// </summary>
public class ModelRepository : IModelRepository
{
    private readonly TMLDbContext _context;
    private readonly ILogger<ModelRepository> _logger;

    public ModelRepository(TMLDbContext context, ILogger<ModelRepository> logger)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<Model> CreateAsync(Model model, CancellationToken cancellationToken = default)
    {
        try
        {
            _context.Models.Add(model);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Created model {ModelId} for transaction {TransactionId}", 
                model.Id, model.TransactionId);
            return model;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create model {ModelId}", model.Id);
            throw;
        }
    }

    public async Task<Model> UpdateAsync(Model model, CancellationToken cancellationToken = default)
    {
        try
        {
            _context.Models.Update(model);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Updated model {ModelId} to version {Version}", 
                model.Id, model.Version);
            return model;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to update model {ModelId}", model.Id);
            throw;
        }
    }

    public async Task<Model?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        try
        {
            var model = await _context.Models
                .FirstOrDefaultAsync(m => m.Id == id, cancellationToken);
            
            _logger.LogDebug("Retrieved model {ModelId}: {Found}", 
                id, model != null ? "Found" : "Not Found");
            
            return model;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get model {ModelId}", id);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetByTransactionIdAsync(Guid transactionId, CancellationToken cancellationToken = default)
    {
        try
        {
            var models = await _context.Models
                .Where(m => m.TransactionId == transactionId)
                .OrderBy(m => m.CreatedAt)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} models for transaction {TransactionId}", 
                models.Count, transactionId);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get models by transaction {TransactionId}", transactionId);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetByParentModelIdAsync(Guid parentModelId, CancellationToken cancellationToken = default)
    {
        try
        {
            var models = await _context.Models
                .Where(m => m.ParentModelId == parentModelId)
                .OrderBy(m => m.CreatedAt)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} child models for parent {ParentModelId}", 
                models.Count, parentModelId);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get models by parent {ParentModelId}", parentModelId);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> FindSpatialNeighborsAsync(double x, double y, double radius, int maxResults = 10, CancellationToken cancellationToken = default)
    {
        try
        {
            // First get active models, then filter in memory to avoid EF Core translation issues
            var models = await _context.Models
                .Where(m => m.Status == ModelStatus.Active)
                .ToListAsync(cancellationToken);
            
            // Apply spatial filtering in memory
            var neighbors = models
                .Where(m => m.Location != null)
                .Select(m => new { 
                    Model = m, 
                    Distance = Math.Sqrt(Math.Pow(m.Location.X - x, 2) + Math.Pow(m.Location.Y - y, 2))
                })
                .Where(m => m.Distance <= radius)
                .OrderBy(m => m.Distance)
                .Take(maxResults)
                .Select(m => m.Model)
                .ToList();
            
            _logger.LogDebug("Found {Count} spatial neighbors within {Radius} of ({X}, {Y})", 
                neighbors.Count, radius, x, y);
            
            return neighbors;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to find spatial neighbors at ({X}, {Y}) within radius {Radius}", 
                x, y, radius);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetByGridIdAsync(string gridId, CancellationToken cancellationToken = default)
    {
        try
        {
            // Load all models and filter in memory to avoid EF Core translation issues
            var allModels = await _context.Models
                .ToListAsync(cancellationToken);
            
            var models = allModels
                .Where(m => m.Location != null && m.Location.GridId == gridId)
                .OrderBy(m => m.CreatedAt)
                .ToList();
            
            _logger.LogDebug("Retrieved {Count} models in grid {GridId}", 
                models.Count, gridId);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get models by grid {GridId}", gridId);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetByStatusAsync(ModelStatus status, int limit = 100, CancellationToken cancellationToken = default)
    {
        try
        {
            var models = await _context.Models
                .Where(m => m.Status == status)
                .OrderByDescending(m => m.CreatedAt)
                .Take(limit)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} models with status {Status}", 
                models.Count, status);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get models by status {Status}", status);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetByInheritanceDepthAsync(int depth, int limit = 100, CancellationToken cancellationToken = default)
    {
        try
        {
            var models = await _context.Models
                .Where(m => m.InheritanceDepth == depth)
                .OrderByDescending(m => m.CreatedAt)
                .Take(limit)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} models at inheritance depth {Depth}", 
                models.Count, depth);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get models by inheritance depth {Depth}", depth);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> GetInheritanceChainAsync(Guid modelId, CancellationToken cancellationToken = default)
    {
        try
        {
            var chain = new List<Model>();
            var currentModelId = modelId;
            
            // Follow the parent chain up to the root
            while (currentModelId != Guid.Empty)
            {
                var model = await _context.Models
                    .FirstOrDefaultAsync(m => m.Id == currentModelId, cancellationToken);
                
                if (model == null) break;
                
                chain.Add(model);
                currentModelId = model.ParentModelId ?? Guid.Empty;
                
                // Prevent infinite loops
                if (chain.Count > 1000)
                {
                    _logger.LogWarning("Inheritance chain for model {ModelId} exceeds 1000 levels", modelId);
                    break;
                }
            }
            
            // Reverse to get root-to-leaf order
            chain.Reverse();
            
            _logger.LogDebug("Retrieved inheritance chain of {Count} models for {ModelId}", 
                chain.Count, modelId);
            
            return chain;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get inheritance chain for model {ModelId}", modelId);
            throw;
        }
    }

    public async Task<ModelStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var stats = await _context.Models
                .GroupBy(m => 1)
                .Select(g => new ModelStatistics
                {
                    TotalCount = g.Count(),
                    ActiveCount = g.Count(m => m.Status == ModelStatus.Active),
                    TrainingCount = g.Count(m => m.Status == ModelStatus.Training),
                    ArchivedCount = g.Count(m => m.Status == ModelStatus.Archived),
                    DeprecatedCount = g.Count(m => m.Status == ModelStatus.Deprecated),
                    FailedCount = g.Count(m => m.Status == ModelStatus.Failed),
                    MaxInheritanceDepth = g.Max(m => m.InheritanceDepth),
                    AverageInheritanceDepth = g.Average(m => m.InheritanceDepth),
                    AverageConfidence = g.Average(m => m.Metrics.Confidence),
                    AverageRSquared = g.Average(m => m.Metrics.RSquared),
                    OldestModel = g.Min(m => m.CreatedAt),
                    NewestModel = g.Max(m => m.CreatedAt)
                })
                .FirstOrDefaultAsync(cancellationToken);
            
            var result = stats ?? new ModelStatistics();
            
            _logger.LogDebug("Retrieved model statistics: Total={Total}, Active={Active}, MaxDepth={MaxDepth}", 
                result.TotalCount, result.ActiveCount, result.MaxInheritanceDepth);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get model statistics");
            throw;
        }
    }

    public async Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default)
    {
        try
        {
            var model = await _context.Models
                .FirstOrDefaultAsync(m => m.Id == id, cancellationToken);
            
            if (model == null)
            {
                _logger.LogWarning("Model {ModelId} not found for deletion", id);
                return false;
            }
            
            _context.Models.Remove(model);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Deleted model {ModelId}", id);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete model {ModelId}", id);
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> CreateBatchAsync(IEnumerable<Model> models, CancellationToken cancellationToken = default)
    {
        try
        {
            var modelList = models.ToList();
            
            _context.Models.AddRange(modelList);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Created batch of {Count} models", modelList.Count);
            return modelList;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create batch of {Count} models", models.Count());
            throw;
        }
    }

    public async Task<IReadOnlyList<Model>> SearchAsync(ModelSearchCriteria criteria, CancellationToken cancellationToken = default)
    {
        try
        {
            var query = _context.Models.AsQueryable();
            
            // Apply filters
            if (criteria.Status.HasValue)
                query = query.Where(m => m.Status == criteria.Status.Value);
            
            if (criteria.MinInheritanceDepth.HasValue)
                query = query.Where(m => m.InheritanceDepth >= criteria.MinInheritanceDepth.Value);
            
            if (criteria.MaxInheritanceDepth.HasValue)
                query = query.Where(m => m.InheritanceDepth <= criteria.MaxInheritanceDepth.Value);
            
            if (criteria.MinConfidence.HasValue)
                query = query.Where(m => m.Metrics.Confidence >= criteria.MinConfidence.Value);
            
            if (criteria.MaxConfidence.HasValue)
                query = query.Where(m => m.Metrics.Confidence <= criteria.MaxConfidence.Value);
            
            if (criteria.MinRSquared.HasValue)
                query = query.Where(m => m.Metrics.RSquared >= criteria.MinRSquared.Value);
            
            if (criteria.MaxRSquared.HasValue)
                query = query.Where(m => m.Metrics.RSquared <= criteria.MaxRSquared.Value);
            
            if (criteria.CreatedAfter.HasValue)
                query = query.Where(m => m.CreatedAt >= criteria.CreatedAfter.Value);
            
            if (criteria.CreatedBefore.HasValue)
                query = query.Where(m => m.CreatedAt <= criteria.CreatedBefore.Value);
            
            if (!string.IsNullOrEmpty(criteria.GridId))
                query = query.Where(m => m.Location.GridId == criteria.GridId);
            
            if (criteria.PhysicsValid.HasValue)
                query = query.Where(m => m.PhysicsValidation.IsValid == criteria.PhysicsValid.Value);
            
            // Spatial filter
            if (criteria.SpatialX.HasValue && criteria.SpatialY.HasValue && criteria.SpatialRadius.HasValue)
            {
                var x = criteria.SpatialX.Value;
                var y = criteria.SpatialY.Value;
                var radius = criteria.SpatialRadius.Value;
                
                query = query.Where(m => 
                    Math.Sqrt(Math.Pow(m.Location.X - x, 2) + Math.Pow(m.Location.Y - y, 2)) <= radius);
            }
            
            // Apply ordering
            query = criteria.OrderBy?.ToLower() switch
            {
                "createdat" => criteria.Descending ? query.OrderByDescending(m => m.CreatedAt) : query.OrderBy(m => m.CreatedAt),
                "updatedat" => criteria.Descending ? query.OrderByDescending(m => m.UpdatedAt) : query.OrderBy(m => m.UpdatedAt),
                "confidence" => criteria.Descending ? query.OrderByDescending(m => m.Metrics.Confidence) : query.OrderBy(m => m.Metrics.Confidence),
                "rsquared" => criteria.Descending ? query.OrderByDescending(m => m.Metrics.RSquared) : query.OrderBy(m => m.Metrics.RSquared),
                "inheritancedepth" => criteria.Descending ? query.OrderByDescending(m => m.InheritanceDepth) : query.OrderBy(m => m.InheritanceDepth),
                _ => criteria.Descending ? query.OrderByDescending(m => m.CreatedAt) : query.OrderBy(m => m.CreatedAt)
            };
            
            // Apply pagination
            var models = await query
                .Skip(criteria.Offset)
                .Take(criteria.Limit)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Search returned {Count} models with criteria: Status={Status}, Depth={MinDepth}-{MaxDepth}", 
                models.Count, criteria.Status, criteria.MinInheritanceDepth, criteria.MaxInheritanceDepth);
            
            return models;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to search models with criteria");
            throw;
        }
    }
}
