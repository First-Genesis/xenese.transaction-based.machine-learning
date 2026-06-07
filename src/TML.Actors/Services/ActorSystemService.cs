using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Proto;
using Proto.Cluster;
using Proto.Cluster.Consul;
using Proto.DependencyInjection;
using System.Collections.Concurrent;
using TML.Actors.Actors;
using TML.Actors.Messages;

namespace TML.Actors.Services;

/// <summary>
/// Hosted service that manages the Proto.Actor system lifecycle.
/// Handles actor creation, clustering, and graceful shutdown.
/// </summary>
public class ActorSystemService : IHostedService, IDisposable
{
    private readonly ILogger<ActorSystemService> _logger;
    private readonly IServiceProvider _serviceProvider;
    private readonly ActorSystemConfiguration _configuration;
    
    private ActorSystem? _actorSystem;
    private Cluster? _cluster;
    private readonly ConcurrentDictionary<string, PID> _actors;
    private readonly CancellationTokenSource _cancellationTokenSource;
    
    // Actor pools
    private readonly List<PID> _transactionProcessors;
    private readonly List<PID> _modelActors;
    private readonly List<PID> _physicsValidators;

    /// <summary>
    /// Gets the root context for the actor system
    /// </summary>
    public IRootContext Root => _actorSystem?.Root ?? throw new InvalidOperationException("Actor system not initialized");

    public ActorSystemService(
        ILogger<ActorSystemService> logger,
        IServiceProvider serviceProvider,
        ActorSystemConfiguration configuration)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        
        _actors = new ConcurrentDictionary<string, PID>();
        _cancellationTokenSource = new CancellationTokenSource();
        _transactionProcessors = new List<PID>();
        _modelActors = new List<PID>();
        _physicsValidators = new List<PID>();
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogInformation("Starting TML Actor System...");
            
            // Create actor system
            await CreateActorSystem();
            
            // Setup clustering if enabled
            if (_configuration.EnableClustering)
            {
                await SetupClustering();
            }
            
            // Deploy core actors
            await DeployActors();
            
            _logger.LogInformation("TML Actor System started successfully with {ActorCount} actors", 
                _actors.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start TML Actor System");
            throw;
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogInformation("Stopping TML Actor System...");
            
            _cancellationTokenSource.Cancel();
            
            // Gracefully shutdown actors
            await ShutdownActors();
            
            // Stop cluster
            if (_cluster != null)
            {
                await _cluster.ShutdownAsync();
                _cluster = null;
            }
            
            // Stop actor system
            if (_actorSystem != null)
            {
                await _actorSystem.ShutdownAsync();
                _actorSystem = null;
            }
            
            _logger.LogInformation("TML Actor System stopped successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping TML Actor System");
        }
    }

    private async Task CreateActorSystem()
    {
        _actorSystem = new ActorSystem();
        
        _logger.LogInformation("Actor System created with configuration: {Config}", 
            _configuration.ToString());
        
        await Task.CompletedTask;
    }

    private async Task SetupClustering()
    {
        if (_actorSystem == null)
            throw new InvalidOperationException("Actor system must be created before clustering");
        
        // Clustering disabled for now - using local actors only
        // TODO: Implement proper clustering with Proto.Cluster when needed
        
        _logger.LogInformation("Clustering disabled - using local actors only");
        await Task.CompletedTask;
    }

    private async Task DeployActors()
    {
        if (_actorSystem == null)
            throw new InvalidOperationException("Actor system must be created before deploying actors");
        
        // Deploy Transaction Processors
        for (int i = 0; i < _configuration.TransactionProcessorCount; i++)
        {
            var props = Props.FromProducer(() => 
                ActivatorUtilities.CreateInstance<TransactionProcessorActor>(_serviceProvider));
            
            var pid = _actorSystem.Root.Spawn(props);
            var actorId = $"transaction-processor-{i}";
            
            _actors.TryAdd(actorId, pid);
            _transactionProcessors.Add(pid);
            
            _logger.LogDebug("Deployed TransactionProcessorActor: {ActorId}", actorId);
        }
        
        // Deploy Model Actors
        for (int i = 0; i < _configuration.ModelActorCount; i++)
        {
            var props = Props.FromProducer(() => 
                ActivatorUtilities.CreateInstance<ModelActor>(_serviceProvider));
            
            var pid = _actorSystem.Root.Spawn(props);
            var actorId = $"model-actor-{i}";
            
            _actors.TryAdd(actorId, pid);
            _modelActors.Add(pid);
            
            _logger.LogDebug("Deployed ModelActor: {ActorId}", actorId);
        }
        
        // Deploy Physics Validators
        for (int i = 0; i < _configuration.PhysicsValidatorCount; i++)
        {
            var props = Props.FromProducer(() => 
                ActivatorUtilities.CreateInstance<PhysicsValidatorActor>(_serviceProvider));
            
            var pid = _actorSystem.Root.Spawn(props);
            var actorId = $"physics-validator-{i}";
            
            _actors.TryAdd(actorId, pid);
            _physicsValidators.Add(pid);
            
            _logger.LogDebug("Deployed PhysicsValidatorActor: {ActorId}", actorId);
        }
        
        await Task.CompletedTask;
        
        _logger.LogInformation("Deployed {TransactionProcessors} transaction processors, " +
                              "{ModelActors} model actors, {PhysicsValidators} physics validators",
            _transactionProcessors.Count, _modelActors.Count, _physicsValidators.Count);
    }

    private async Task ShutdownActors()
    {
        if (_actorSystem == null) return;
        
        var shutdownTasks = new List<Task>();
        
        // Send shutdown messages to all actors
        foreach (var (actorId, pid) in _actors)
        {
            try
            {
                var shutdownMessage = new Shutdown("System shutdown");
                _actorSystem.Root.Send(pid, shutdownMessage);
                
                // Add a task to wait for actor to stop (with timeout)
                shutdownTasks.Add(Task.Run(async () =>
                {
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                    try
                    {
                        await _actorSystem.Root.StopAsync(pid);
                        _logger.LogDebug("Actor {ActorId} stopped gracefully", actorId);
                    }
                    catch (OperationCanceledException)
                    {
                        _logger.LogWarning("Actor {ActorId} shutdown timed out", actorId);
                    }
                }));
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error shutting down actor {ActorId}", actorId);
            }
        }
        
        // Wait for all actors to shutdown (with overall timeout)
        try
        {
            await Task.WhenAll(shutdownTasks).WaitAsync(TimeSpan.FromMinutes(2));
        }
        catch (TimeoutException)
        {
            _logger.LogWarning("Actor shutdown timed out, forcing termination");
        }
        
        _actors.Clear();
        _transactionProcessors.Clear();
        _modelActors.Clear();
        _physicsValidators.Clear();
    }

    /// <summary>
    /// Get a transaction processor actor using round-robin selection
    /// </summary>
    public PID? GetTransactionProcessor()
    {
        if (_transactionProcessors.Count == 0) return null;
        
        var index = Random.Shared.Next(_transactionProcessors.Count);
        return _transactionProcessors[index];
    }

    /// <summary>
    /// Get a model actor using round-robin selection
    /// </summary>
    public PID? GetModelActor()
    {
        if (_modelActors.Count == 0) return null;
        
        var index = Random.Shared.Next(_modelActors.Count);
        return _modelActors[index];
    }

    /// <summary>
    /// Get a physics validator actor
    /// </summary>
    public PID? GetPhysicsValidator()
    {
        if (_physicsValidators.Count == 0) return null;
        
        var index = Random.Shared.Next(_physicsValidators.Count);
        return _physicsValidators[index];
    }

    /// <summary>
    /// Get all active actors
    /// </summary>
    public IReadOnlyDictionary<string, PID> GetAllActors()
    {
        return _actors.AsReadOnly();
    }

    /// <summary>
    /// Get actor system health status
    /// </summary>
    public async Task<ActorSystemHealth> GetHealthStatusAsync()
    {
        var health = new ActorSystemHealth
        {
            IsHealthy = _actorSystem != null,
            ActorCount = _actors.Count,
            TransactionProcessorCount = _transactionProcessors.Count,
            ModelActorCount = _modelActors.Count,
            PhysicsValidatorCount = _physicsValidators.Count,
            ClusterEnabled = _configuration.EnableClustering,
            ClusterHealthy = _cluster?.System != null
        };
        
        // Check individual actor health (sample a few actors)
        var healthCheckTasks = new List<Task<bool>>();
        var actorsToCheck = _actors.Values.Take(5); // Check first 5 actors
        
        foreach (var pid in actorsToCheck)
        {
            healthCheckTasks.Add(CheckActorHealth(pid));
        }
        
        if (healthCheckTasks.Count > 0)
        {
            var healthResults = await Task.WhenAll(healthCheckTasks);
            health.ActorHealthyCount = healthResults.Count(h => h);
        }
        
        return health;
    }

    private async Task<bool> CheckActorHealth(PID pid)
    {
        try
        {
            if (_actorSystem == null) return false;
            
            var healthMessage = new GetHealthStatus();
            var response = await _actorSystem.Root.RequestAsync<HealthStatusResponse>(
                pid, healthMessage, TimeSpan.FromSeconds(5));
            
            return response.IsHealthy;
        }
        catch
        {
            return false;
        }
    }

    public void Dispose()
    {
        _cancellationTokenSource?.Dispose();
    }
}

/// <summary>
/// Configuration for the Actor System
/// </summary>
public class ActorSystemConfiguration
{
    public string ClusterName { get; set; } = "tml-cluster";
    public bool EnableClustering { get; set; } = false;
    public string ConsulHost { get; set; } = "localhost";
    public int ConsulPort { get; set; } = 8500;
    
    public int TransactionProcessorCount { get; set; } = 3;
    public int ModelActorCount { get; set; } = 5;
    public int PhysicsValidatorCount { get; set; } = 2;
    
    public override string ToString()
    {
        return $"Cluster: {ClusterName}, Clustering: {EnableClustering}, " +
               $"TxProcessors: {TransactionProcessorCount}, Models: {ModelActorCount}, " +
               $"Validators: {PhysicsValidatorCount}";
    }
}

/// <summary>
/// Actor system health information
/// </summary>
public class ActorSystemHealth
{
    public bool IsHealthy { get; set; }
    public int ActorCount { get; set; }
    public int ActorHealthyCount { get; set; }
    public int TransactionProcessorCount { get; set; }
    public int ModelActorCount { get; set; }
    public int PhysicsValidatorCount { get; set; }
    public bool ClusterEnabled { get; set; }
    public bool ClusterHealthy { get; set; }
    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.UtcNow;
}
