using Microsoft.Extensions.Logging;
using Proto;
using System.Collections.Concurrent;
using System.Diagnostics;
using TML.Actors.Messages;
using TML.Core.Domain;

namespace TML.Actors.Actors;

/// <summary>
/// Model management actor responsible for creating, updating, and retrieving ML models.
/// Handles model inheritance, spatial relationships, and persistence.
/// </summary>
public class ModelActor : IActor
{
    private readonly ILogger<ModelActor> _logger;
    private readonly string _actorId;
    private readonly ConcurrentDictionary<Guid, Model> _modelCache;
    private readonly ConcurrentDictionary<string, List<Guid>> _spatialIndex;
    
    // Performance tracking
    private long _modelsCreated;
    private long _modelsUpdated;
    private long _modelsRetrieved;
    private readonly Stopwatch _uptimeStopwatch;
    
    // Configuration
    private const int MaxCacheSize = 10000;
    private const double SpatialGridSize = 100.0; // Grid size for spatial indexing

    public ModelActor(ILogger<ModelActor> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _actorId = $"model-actor-{Guid.NewGuid():N}";
        _modelCache = new ConcurrentDictionary<Guid, Model>();
        _spatialIndex = new ConcurrentDictionary<string, List<Guid>>();
        _uptimeStopwatch = Stopwatch.StartNew();
        
        _logger.LogInformation("ModelActor {ActorId} initialized", _actorId);
    }

    public async Task ReceiveAsync(IContext context)
    {
        try
        {
            switch (context.Message)
            {
                case CreateModel msg:
                    await HandleCreateModel(context, msg);
                    break;
                    
                case UpdateModel msg:
                    await HandleUpdateModel(context, msg);
                    break;
                    
                case GetModel msg:
                    await HandleGetModel(context, msg);
                    break;
                    
                case FindSpatialNeighbors msg:
                    await HandleFindSpatialNeighbors(context, msg);
                    break;
                    
                case GetMetrics:
                    await HandleGetMetrics(context);
                    break;
                    
                case GetHealthStatus:
                    await HandleGetHealthStatus(context);
                    break;
                    
                case Shutdown msg:
                    await HandleShutdown(context, msg);
                    break;
                    
                case Started:
                    _logger.LogInformation("ModelActor {ActorId} started", _actorId);
                    break;
                    
                case Stopped:
                    _logger.LogInformation("ModelActor {ActorId} stopped", _actorId);
                    break;
                    
                default:
                    _logger.LogWarning("Unknown message type {MessageType} received by {ActorId}", 
                        context.Message?.GetType().Name, _actorId);
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing message {MessageType} in {ActorId}", 
                context.Message?.GetType().Name, _actorId);
            
            // Send error response if sender is waiting
            if (context.Sender != null)
            {
                var errorResponse = new ModelResponse(
                    Guid.Empty, 
                    null, 
                    false, 
                    ex.Message);
                context.Respond(errorResponse);
            }
        }
    }

    private async Task HandleCreateModel(IContext context, CreateModel message)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            _logger.LogDebug("Creating model for transaction {TransactionId}", message.TransactionId);
            
            // Find parent model if specified
            Model? parentModel = null;
            if (message.ParentModelId.HasValue)
            {
                parentModel = await GetModelFromCache(message.ParentModelId.Value);
            }
            
            // Create the model
            var model = await CreateModelFromData(message.TransactionId, message.Data, parentModel);
            
            // Store in cache
            _modelCache.TryAdd(model.Id, model);
            
            // Update spatial index
            UpdateSpatialIndex(model);
            
            // Manage cache size
            await ManageCacheSize();
            
            stopwatch.Stop();
            Interlocked.Increment(ref _modelsCreated);
            
            var response = new ModelResponse(model.Id, model, true);
            context.Respond(response);
            
            _logger.LogDebug("Model {ModelId} created in {ProcessingTime}ms", 
                model.Id, stopwatch.Elapsed.TotalMilliseconds);
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Failed to create model for transaction {TransactionId}", message.TransactionId);
            
            var errorResponse = new ModelResponse(
                Guid.Empty,
                null,
                false,
                ex.Message);
            
            context.Respond(errorResponse);
        }
    }

    private async Task HandleUpdateModel(IContext context, UpdateModel message)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            _logger.LogDebug("Updating model {ModelId}", message.ModelId);
            
            // Get existing model
            var existingModel = await GetModelFromCache(message.ModelId);
            if (existingModel == null)
            {
                var notFoundResponse = new ModelResponse(
                    message.ModelId,
                    null,
                    false,
                    "Model not found");
                
                context.Respond(notFoundResponse);
                return;
            }
            
            // Update model with new data
            var updatedModel = await UpdateModelWithNewData(existingModel, message.NewData);
            
            // Update cache
            _modelCache.TryUpdate(message.ModelId, updatedModel, existingModel);
            
            // Update spatial index if location changed
            if (HasLocationChanged(existingModel, updatedModel))
            {
                RemoveFromSpatialIndex(existingModel);
                UpdateSpatialIndex(updatedModel);
            }
            
            stopwatch.Stop();
            Interlocked.Increment(ref _modelsUpdated);
            
            var response = new ModelResponse(updatedModel.Id, updatedModel, true);
            context.Respond(response);
            
            _logger.LogDebug("Model {ModelId} updated in {ProcessingTime}ms", 
                message.ModelId, stopwatch.Elapsed.TotalMilliseconds);
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Failed to update model {ModelId}", message.ModelId);
            
            var errorResponse = new ModelResponse(
                message.ModelId,
                null,
                false,
                ex.Message);
            
            context.Respond(errorResponse);
        }
    }

    private async Task HandleGetModel(IContext context, GetModel message)
    {
        try
        {
            _logger.LogDebug("Retrieving model {ModelId}", message.ModelId);
            
            var model = await GetModelFromCache(message.ModelId);
            
            Interlocked.Increment(ref _modelsRetrieved);
            
            var response = new ModelResponse(
                message.ModelId,
                model,
                model != null,
                model == null ? "Model not found" : null);
            
            context.Respond(response);
            
            _logger.LogDebug("Model {ModelId} retrieval completed", message.ModelId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to retrieve model {ModelId}", message.ModelId);
            
            var errorResponse = new ModelResponse(
                message.ModelId,
                null,
                false,
                ex.Message);
            
            context.Respond(errorResponse);
        }
    }

    private async Task HandleFindSpatialNeighbors(IContext context, FindSpatialNeighbors message)
    {
        try
        {
            _logger.LogDebug("Finding spatial neighbors for location ({X}, {Y})", message.X, message.Y);
            
            var neighbors = await FindNeighborsInRadius(message.X, message.Y, message.SearchRadius, message.MaxNeighbors);
            
            var response = new SpatialNeighborsFound(neighbors);
            context.Respond(response);
            
            _logger.LogDebug("Found {Count} spatial neighbors", neighbors.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to find spatial neighbors for location ({X}, {Y})", message.X, message.Y);
            
            var errorResponse = new SpatialNeighborsFound(new List<Model>());
            context.Respond(errorResponse);
        }
    }

    private async Task<Model> CreateModelFromData(Guid transactionId, TransactionData data, Model? parentModel)
    {
        var inheritanceDepth = parentModel?.InheritanceDepth + 1 ?? 0;
        
        // Create model parameters with inheritance from parent
        var parameters = CreateModelParameters(data, parentModel);
        
        // Validate physics constraints
        var physicsValidation = await ValidateModelPhysics(data, parentModel);
        
        // Calculate model metrics
        var metrics = CalculateModelMetrics(data, parentModel);
        
        // Create spatial location
        var location = new SpatialLocation
        {
            X = data.XCoord,
            Y = data.YCoord,
            GridId = GetSpatialGridId(data.XCoord, data.YCoord),
            Neighbors = await GetNearbyModelIds(data.XCoord, data.YCoord)
        };
        
        return new Model
        {
            TransactionId = transactionId,
            ParentModelId = parentModel?.Id,
            InheritanceDepth = inheritanceDepth,
            Parameters = parameters,
            PhysicsValidation = physicsValidation,
            Metrics = metrics,
            Location = location,
            Status = ModelStatus.Active
        };
    }

    private ModelParameters CreateModelParameters(TransactionData data, Model? parentModel)
    {
        // Initialize with parent parameters or defaults
        var baseWeights = parentModel?.Parameters.Weights ?? new[] { 1.0, 0.5, 0.2 };
        var baseBias = parentModel?.Parameters.Bias ?? 0.1;
        var baseLearningRate = parentModel?.Parameters.LearningRate ?? 0.01;
        
        // Apply incremental learning with new data
        var weights = new double[baseWeights.Length];
        for (int i = 0; i < baseWeights.Length; i++)
        {
            // Simple gradient update (will be replaced with real ML algorithms)
            weights[i] = baseWeights[i] + baseLearningRate * (data.Thickness - 20.0) * 0.01;
        }
        
        return new ModelParameters
        {
            Weights = weights,
            Bias = baseBias + baseLearningRate * (data.Thickness - 20.0) * 0.001,
            LearningRate = baseLearningRate,
            Regularization = 0.001,
            Iterations = (parentModel?.Parameters.Iterations ?? 0) + 10,
            ConvergenceThreshold = 0.0001
        };
    }

    private async Task<PhysicsValidation> ValidateModelPhysics(TransactionData data, Model? parentModel)
    {
        // Implement physics validation logic
        await Task.Delay(1); // Simulate async validation
        
        var thicknessValid = data.Thickness >= data.MinThickness && data.Thickness <= 50.0;
        var energyValid = true; // Placeholder for energy conservation check
        var massValid = true;   // Placeholder for mass conservation check
        
        var violations = new List<string>();
        if (!thicknessValid)
        {
            violations.Add($"Thickness {data.Thickness}mm outside valid range [{data.MinThickness}, 50.0]mm");
        }
        
        var validationScore = (thicknessValid ? 0.4 : 0.0) + 
                             (energyValid ? 0.3 : 0.0) + 
                             (massValid ? 0.3 : 0.0);
        
        return new PhysicsValidation
        {
            IsValid = thicknessValid && energyValid && massValid,
            ThicknessValid = thicknessValid,
            EnergyConservationValid = energyValid,
            MassConservationValid = massValid,
            Violations = violations,
            ValidationScore = validationScore
        };
    }

    private ModelMetrics CalculateModelMetrics(TransactionData data, Model? parentModel)
    {
        // Calculate metrics based on data and parent model performance
        var baseError = parentModel?.Metrics.MeanSquaredError ?? 1.0;
        var improvement = Math.Max(0.1, 1.0 - (data.Quality * 0.1));
        
        var mse = baseError * improvement;
        var rmse = Math.Sqrt(mse);
        var mae = rmse * 0.8;
        var rSquared = Math.Max(0.0, Math.Min(1.0, 1.0 - mse));
        var confidence = data.Quality * (parentModel?.Metrics.Confidence ?? 0.5);
        
        return new ModelMetrics
        {
            MeanSquaredError = mse,
            RootMeanSquaredError = rmse,
            MeanAbsoluteError = mae,
            RSquared = rSquared,
            Confidence = confidence,
            TrainingDataPoints = (parentModel?.Metrics.TrainingDataPoints ?? 0) + 1
        };
    }

    private async Task<Model> UpdateModelWithNewData(Model existingModel, TransactionData newData)
    {
        // Create updated parameters with incremental learning
        var updatedParameters = CreateModelParameters(newData, existingModel);
        
        // Recalculate metrics
        var updatedMetrics = CalculateModelMetrics(newData, existingModel);
        
        // Update physics validation
        var updatedPhysicsValidation = await ValidateModelPhysics(newData, existingModel);
        
        // Create updated model
        return existingModel with
        {
            Parameters = updatedParameters,
            Metrics = updatedMetrics,
            PhysicsValidation = updatedPhysicsValidation,
            UpdatedAt = DateTimeOffset.UtcNow,
            Version = existingModel.Version + 1
        };
    }

    private async Task<Model?> GetModelFromCache(Guid modelId)
    {
        // Try cache first
        if (_modelCache.TryGetValue(modelId, out var cachedModel))
        {
            return cachedModel;
        }
        
        // TODO: Load from persistent storage if not in cache
        await Task.Delay(1); // Simulate async storage access
        
        return null;
    }

    private Task<List<Model>> FindNeighborsInRadius(double x, double y, double radius, int maxNeighbors)
    {
        var neighbors = new List<Model>();
        
        // Calculate grid cells to search
        var gridIds = GetGridIdsInRadius(x, y, radius);
        
        foreach (var gridId in gridIds)
        {
            if (_spatialIndex.TryGetValue(gridId, out var modelIds))
            {
                foreach (var modelId in modelIds)
                {
                    if (_modelCache.TryGetValue(modelId, out var model))
                    {
                        var distance = CalculateDistance(x, y, model.Location.X, model.Location.Y);
                        if (distance <= radius)
                        {
                            neighbors.Add(model);
                        }
                    }
                }
            }
        }
        
        // Sort by distance and take top N
        var result = neighbors
            .OrderBy(m => CalculateDistance(x, y, m.Location.X, m.Location.Y))
            .Take(maxNeighbors)
            .ToList();
        
        return Task.FromResult(result);
    }

    private void UpdateSpatialIndex(Model model)
    {
        var gridId = GetSpatialGridId(model.Location.X, model.Location.Y);
        _spatialIndex.AddOrUpdate(
            gridId,
            new List<Guid> { model.Id },
            (key, existing) =>
            {
                if (!existing.Contains(model.Id))
                {
                    existing.Add(model.Id);
                }
                return existing;
            });
    }

    private void RemoveFromSpatialIndex(Model model)
    {
        var gridId = GetSpatialGridId(model.Location.X, model.Location.Y);
        if (_spatialIndex.TryGetValue(gridId, out var modelIds))
        {
            modelIds.Remove(model.Id);
            if (modelIds.Count == 0)
            {
                _spatialIndex.TryRemove(gridId, out _);
            }
        }
    }

    private string GetSpatialGridId(double x, double y)
    {
        var gridX = (int)(x / SpatialGridSize);
        var gridY = (int)(y / SpatialGridSize);
        return $"{gridX}_{gridY}";
    }

    private List<string> GetGridIdsInRadius(double x, double y, double radius)
    {
        var gridIds = new List<string>();
        var gridRadius = (int)Math.Ceiling(radius / SpatialGridSize);
        var centerGridX = (int)(x / SpatialGridSize);
        var centerGridY = (int)(y / SpatialGridSize);
        
        for (int dx = -gridRadius; dx <= gridRadius; dx++)
        {
            for (int dy = -gridRadius; dy <= gridRadius; dy++)
            {
                gridIds.Add($"{centerGridX + dx}_{centerGridY + dy}");
            }
        }
        
        return gridIds;
    }

    private async Task<List<Guid>> GetNearbyModelIds(double x, double y)
    {
        var neighbors = await FindNeighborsInRadius(x, y, 100.0, 5);
        return neighbors.Select(m => m.Id).ToList();
    }

    private static double CalculateDistance(double x1, double y1, double x2, double y2)
    {
        return Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));
    }

    private static bool HasLocationChanged(Model oldModel, Model newModel)
    {
        return Math.Abs(oldModel.Location.X - newModel.Location.X) > 0.001 ||
               Math.Abs(oldModel.Location.Y - newModel.Location.Y) > 0.001;
    }

    private async Task ManageCacheSize()
    {
        if (_modelCache.Count > MaxCacheSize)
        {
            // Remove oldest 10% of models (simple LRU-like strategy)
            var modelsToRemove = _modelCache.Values
                .OrderBy(m => m.UpdatedAt)
                .Take(_modelCache.Count / 10)
                .ToList();
            
            foreach (var model in modelsToRemove)
            {
                _modelCache.TryRemove(model.Id, out _);
                RemoveFromSpatialIndex(model);
            }
            
            _logger.LogInformation("Cache cleanup: removed {Count} models", modelsToRemove.Count);
        }
        
        await Task.CompletedTask;
    }

    private async Task HandleGetMetrics(IContext context)
    {
        var customMetrics = new Dictionary<string, double>
        {
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds,
            ["cache_size"] = _modelCache.Count,
            ["spatial_index_size"] = _spatialIndex.Count,
            ["models_created"] = _modelsCreated,
            ["models_updated"] = _modelsUpdated,
            ["models_retrieved"] = _modelsRetrieved
        };
        
        var response = new MetricsResponse(
            _actorId,
            _modelsCreated + _modelsUpdated,
            0, // No processing time tracking for models
            0, // No throughput calculation
            customMetrics);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleGetHealthStatus(IContext context)
    {
        var metrics = new Dictionary<string, object>
        {
            ["models_created"] = _modelsCreated,
            ["models_updated"] = _modelsUpdated,
            ["models_retrieved"] = _modelsRetrieved,
            ["cache_size"] = _modelCache.Count,
            ["spatial_index_size"] = _spatialIndex.Count,
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds
        };
        
        var response = new HealthStatusResponse(
            _actorId,
            true, // Always healthy for now
            metrics,
            DateTimeOffset.UtcNow);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleShutdown(IContext context, Shutdown message)
    {
        _logger.LogInformation("ModelActor {ActorId} shutting down: {Reason}", 
            _actorId, message.Reason);
        
        // TODO: Persist cache to storage before shutdown
        
        // Stop the actor
        context.Stop(context.Self);
        await Task.CompletedTask;
    }
}
