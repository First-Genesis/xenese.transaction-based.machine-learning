using TML.Core.Domain;

namespace TML.Storage.Services;

/// <summary>
/// Interface for Redis caching service
/// </summary>
public interface IRedisCacheService
{
    /// <summary>
    /// Cache a transaction
    /// </summary>
    Task SetTransactionAsync(Guid transactionId, Transaction transaction, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get cached transaction
    /// </summary>
    Task<Transaction?> GetTransactionAsync(Guid transactionId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Cache a model
    /// </summary>
    Task SetModelAsync(Guid modelId, Model model, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get cached model
    /// </summary>
    Task<Model?> GetModelAsync(Guid modelId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Cache spatial neighbors for a location
    /// </summary>
    Task SetSpatialNeighborsAsync(string locationKey, IReadOnlyList<Guid> neighborIds, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get cached spatial neighbors
    /// </summary>
    Task<IReadOnlyList<Guid>?> GetSpatialNeighborsAsync(string locationKey, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Cache processing metrics
    /// </summary>
    Task SetMetricsAsync(string metricsKey, object metrics, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get cached metrics
    /// </summary>
    Task<T?> GetMetricsAsync<T>(string metricsKey, CancellationToken cancellationToken = default) where T : class;
    
    /// <summary>
    /// Invalidate cache entry
    /// </summary>
    Task InvalidateAsync(string key, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Invalidate multiple cache entries by pattern
    /// </summary>
    Task InvalidatePatternAsync(string pattern, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Check if key exists in cache
    /// </summary>
    Task<bool> ExistsAsync(string key, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Set cache entry with sliding expiration
    /// </summary>
    Task SetWithSlidingExpirationAsync<T>(string key, T value, TimeSpan slidingExpiration, CancellationToken cancellationToken = default) where T : class;
    
    /// <summary>
    /// Get or set cache entry (cache-aside pattern)
    /// </summary>
    Task<T?> GetOrSetAsync<T>(string key, Func<Task<T?>> factory, TimeSpan? expiration = null, CancellationToken cancellationToken = default) where T : class;
    
    /// <summary>
    /// Increment counter
    /// </summary>
    Task<long> IncrementAsync(string key, long value = 1, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Add item to set
    /// </summary>
    Task<bool> SetAddAsync(string setKey, string value, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get all items from set
    /// </summary>
    Task<IReadOnlyList<string>> SetMembersAsync(string setKey, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Remove item from set
    /// </summary>
    Task<bool> SetRemoveAsync(string setKey, string value, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Add item to sorted set with score
    /// </summary>
    Task<bool> SortedSetAddAsync(string setKey, string value, double score, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get top N items from sorted set
    /// </summary>
    Task<IReadOnlyList<SortedSetEntry>> SortedSetTopAsync(string setKey, int count, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Publish message to channel
    /// </summary>
    Task PublishAsync(string channel, string message, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Subscribe to channel
    /// </summary>
    Task SubscribeAsync(string channel, Action<string, string> onMessage, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get cache statistics
    /// </summary>
    Task<CacheStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Sorted set entry
/// </summary>
public class SortedSetEntry
{
    public string Value { get; set; } = string.Empty;
    public double Score { get; set; }
}

/// <summary>
/// Cache statistics
/// </summary>
public class CacheStatistics
{
    public long TotalKeys { get; set; }
    public long UsedMemory { get; set; }
    public long MaxMemory { get; set; }
    public double MemoryUsagePercentage { get; set; }
    public long TotalConnections { get; set; }
    public long CommandsProcessed { get; set; }
    public double HitRate { get; set; }
    public TimeSpan Uptime { get; set; }
}
