using Microsoft.Extensions.Diagnostics.HealthChecks;
using TML.Actors.Services;

namespace TML.API.Extensions;

/// <summary>
/// Health check for the Actor System
/// </summary>
public class ActorSystemHealthCheck : IHealthCheck
{
    private readonly ActorSystemService _actorSystemService;
    private readonly ILogger<ActorSystemHealthCheck> _logger;

    public ActorSystemHealthCheck(ActorSystemService actorSystemService, ILogger<ActorSystemHealthCheck> logger)
    {
        _actorSystemService = actorSystemService ?? throw new ArgumentNullException(nameof(actorSystemService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default)
    {
        try
        {
            var health = await _actorSystemService.GetHealthStatusAsync();
            
            var data = new Dictionary<string, object>
            {
                ["isHealthy"] = health.IsHealthy,
                ["actorCount"] = health.ActorCount,
                ["actorHealthyCount"] = health.ActorHealthyCount,
                ["transactionProcessorCount"] = health.TransactionProcessorCount,
                ["modelActorCount"] = health.ModelActorCount,
                ["physicsValidatorCount"] = health.PhysicsValidatorCount,
                ["clusterEnabled"] = health.ClusterEnabled,
                ["clusterHealthy"] = health.ClusterHealthy,
                ["timestamp"] = health.Timestamp
            };

            if (health.IsHealthy)
            {
                return HealthCheckResult.Healthy("Actor system is healthy", data);
            }
            else
            {
                return HealthCheckResult.Unhealthy("Actor system is not healthy", null, data);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Health check failed for actor system");
            return HealthCheckResult.Unhealthy("Actor system health check failed", ex);
        }
    }
}
