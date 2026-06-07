using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using StackExchange.Redis;
using System.Text.Json;
using TML.Core.Domain;

namespace TML.Storage.Services;

/// <summary>
/// Redis implementation of caching service with high-performance operations
/// </summary>
public class RedisCacheService : IRedisCacheService, IDisposable
{
    private readonly IConnectionMultiplexer _redis;
    private readonly IDatabase _database;
    private readonly ISubscriber _subscriber;
    private readonly ILogger<RedisCacheService> _logger;
    private readonly RedisConfiguration _configuration;
    private readonly JsonSerializerOptions _jsonOptions;

    public RedisCacheService(
        IConnectionMultiplexer redis,
        ILogger<RedisCacheService> logger,
        IOptions<RedisConfiguration> configuration)
    {
        _redis = redis ?? throw new ArgumentNullException(nameof(redis));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _configuration = configuration?.Value ?? throw new ArgumentNullException(nameof(configuration));
        
        _database = _redis.GetDatabase(_configuration.DatabaseIndex);
        _subscriber = _redis.GetSubscriber();
        
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false
        };
    }

    public async Task SetTransactionAsync(Guid transactionId, Transaction transaction, TimeSpan? expiration = null, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetTransactionKey(transactionId);
            var value = JsonSerializer.Serialize(transaction, _jsonOptions);
            var exp = expiration ?? _configuration.DefaultTransactionExpiration;
            
            await _database.StringSetAsync(key, value, exp);
            
            _logger.LogDebug("Cached transaction {TransactionId} with expiration {Expiration}", 
                transactionId, exp);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to cache transaction {TransactionId}", transactionId);
            throw;
        }
    }

    public async Task<Transaction?> GetTransactionAsync(Guid transactionId, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetTransactionKey(transactionId);
            var value = await _database.StringGetAsync(key);
            
            if (!value.HasValue)
            {
                _logger.LogDebug("Transaction {TransactionId} not found in cache", transactionId);
                return null;
            }
            
            var transaction = JsonSerializer.Deserialize<Transaction>(value!, _jsonOptions);
            _logger.LogDebug("Retrieved transaction {TransactionId} from cache", transactionId);
            
            return transaction;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transaction {TransactionId} from cache", transactionId);
            throw;
        }
    }

    public async Task SetModelAsync(Guid modelId, Model model, TimeSpan? expiration = null, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetModelKey(modelId);
            var value = JsonSerializer.Serialize(model, _jsonOptions);
            var exp = expiration ?? _configuration.DefaultModelExpiration;
            
            await _database.StringSetAsync(key, value, exp);
            
            // Also cache in spatial index
            await UpdateSpatialIndex(model);
            
            _logger.LogDebug("Cached model {ModelId} with expiration {Expiration}", 
                modelId, exp);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to cache model {ModelId}", modelId);
            throw;
        }
    }

    public async Task<Model?> GetModelAsync(Guid modelId, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetModelKey(modelId);
            var value = await _database.StringGetAsync(key);
            
            if (!value.HasValue)
            {
                _logger.LogDebug("Model {ModelId} not found in cache", modelId);
                return null;
            }
            
            var model = JsonSerializer.Deserialize<Model>(value!, _jsonOptions);
            _logger.LogDebug("Retrieved model {ModelId} from cache", modelId);
            
            return model;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get model {ModelId} from cache", modelId);
            throw;
        }
    }

    public async Task SetSpatialNeighborsAsync(string locationKey, IReadOnlyList<Guid> neighborIds, TimeSpan? expiration = null, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetSpatialKey(locationKey);
            var value = JsonSerializer.Serialize(neighborIds, _jsonOptions);
            var exp = expiration ?? _configuration.DefaultSpatialExpiration;
            
            await _database.StringSetAsync(key, value, exp);
            
            _logger.LogDebug("Cached {Count} spatial neighbors for location {LocationKey}", 
                neighborIds.Count, locationKey);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to cache spatial neighbors for {LocationKey}", locationKey);
            throw;
        }
    }

    public async Task<IReadOnlyList<Guid>?> GetSpatialNeighborsAsync(string locationKey, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetSpatialKey(locationKey);
            var value = await _database.StringGetAsync(key);
            
            if (!value.HasValue)
            {
                _logger.LogDebug("Spatial neighbors for {LocationKey} not found in cache", locationKey);
                return null;
            }
            
            var neighbors = JsonSerializer.Deserialize<List<Guid>>(value!, _jsonOptions);
            _logger.LogDebug("Retrieved {Count} spatial neighbors for {LocationKey} from cache", 
                neighbors?.Count ?? 0, locationKey);
            
            return neighbors;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get spatial neighbors for {LocationKey} from cache", locationKey);
            throw;
        }
    }

    public async Task SetMetricsAsync(string metricsKey, object metrics, TimeSpan? expiration = null, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetMetricsKey(metricsKey);
            var value = JsonSerializer.Serialize(metrics, _jsonOptions);
            var exp = expiration ?? _configuration.DefaultMetricsExpiration;
            
            await _database.StringSetAsync(key, value, exp);
            
            _logger.LogDebug("Cached metrics {MetricsKey} with expiration {Expiration}", 
                metricsKey, exp);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to cache metrics {MetricsKey}", metricsKey);
            throw;
        }
    }

    public async Task<T?> GetMetricsAsync<T>(string metricsKey, CancellationToken cancellationToken = default) where T : class
    {
        try
        {
            var key = GetMetricsKey(metricsKey);
            var value = await _database.StringGetAsync(key);
            
            if (!value.HasValue)
            {
                _logger.LogDebug("Metrics {MetricsKey} not found in cache", metricsKey);
                return null;
            }
            
            var metrics = JsonSerializer.Deserialize<T>(value!, _jsonOptions);
            _logger.LogDebug("Retrieved metrics {MetricsKey} from cache", metricsKey);
            
            return metrics;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get metrics {MetricsKey} from cache", metricsKey);
            throw;
        }
    }

    public async Task InvalidateAsync(string key, CancellationToken cancellationToken = default)
    {
        try
        {
            await _database.KeyDeleteAsync(key);
            _logger.LogDebug("Invalidated cache key {Key}", key);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to invalidate cache key {Key}", key);
            throw;
        }
    }

    public async Task InvalidatePatternAsync(string pattern, CancellationToken cancellationToken = default)
    {
        try
        {
            var server = _redis.GetServer(_redis.GetEndPoints().First());
            var keys = server.Keys(_database.Database, pattern);
            
            var keyArray = keys.ToArray();
            if (keyArray.Length > 0)
            {
                await _database.KeyDeleteAsync(keyArray);
                _logger.LogDebug("Invalidated {Count} cache keys matching pattern {Pattern}", 
                    keyArray.Length, pattern);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to invalidate cache keys matching pattern {Pattern}", pattern);
            throw;
        }
    }

    public async Task<bool> ExistsAsync(string key, CancellationToken cancellationToken = default)
    {
        try
        {
            return await _database.KeyExistsAsync(key);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to check existence of cache key {Key}", key);
            throw;
        }
    }

    public async Task SetWithSlidingExpirationAsync<T>(string key, T value, TimeSpan slidingExpiration, CancellationToken cancellationToken = default) where T : class
    {
        try
        {
            var serializedValue = JsonSerializer.Serialize(value, _jsonOptions);
            await _database.StringSetAsync(key, serializedValue, slidingExpiration);
            
            _logger.LogDebug("Set cache key {Key} with sliding expiration {Expiration}", 
                key, slidingExpiration);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set cache key {Key} with sliding expiration", key);
            throw;
        }
    }

    public async Task<T?> GetOrSetAsync<T>(string key, Func<Task<T?>> factory, TimeSpan? expiration = null, CancellationToken cancellationToken = default) where T : class
    {
        try
        {
            // Try to get from cache first
            var cachedValue = await _database.StringGetAsync(key);
            if (cachedValue.HasValue)
            {
                var cached = JsonSerializer.Deserialize<T>(cachedValue!, _jsonOptions);
                _logger.LogDebug("Cache hit for key {Key}", key);
                return cached;
            }
            
            // Cache miss - get from factory
            _logger.LogDebug("Cache miss for key {Key}, calling factory", key);
            var value = await factory();
            
            if (value != null)
            {
                var serializedValue = JsonSerializer.Serialize(value, _jsonOptions);
                var exp = expiration ?? _configuration.DefaultExpiration;
                await _database.StringSetAsync(key, serializedValue, exp);
                
                _logger.LogDebug("Cached factory result for key {Key}", key);
            }
            
            return value;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get or set cache key {Key}", key);
            throw;
        }
    }

    public async Task<long> IncrementAsync(string key, long value = 1, TimeSpan? expiration = null, CancellationToken cancellationToken = default)
    {
        try
        {
            var result = await _database.StringIncrementAsync(key, value);
            
            if (expiration.HasValue)
            {
                await _database.KeyExpireAsync(key, expiration.Value);
            }
            
            _logger.LogDebug("Incremented counter {Key} by {Value}, new value: {Result}", 
                key, value, result);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to increment counter {Key}", key);
            throw;
        }
    }

    public async Task<bool> SetAddAsync(string setKey, string value, CancellationToken cancellationToken = default)
    {
        try
        {
            var result = await _database.SetAddAsync(setKey, value);
            _logger.LogDebug("Added {Value} to set {SetKey}: {Result}", value, setKey, result);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to add {Value} to set {SetKey}", value, setKey);
            throw;
        }
    }

    public async Task<IReadOnlyList<string>> SetMembersAsync(string setKey, CancellationToken cancellationToken = default)
    {
        try
        {
            var members = await _database.SetMembersAsync(setKey);
            var result = members.Select(m => m.ToString()).ToList();
            
            _logger.LogDebug("Retrieved {Count} members from set {SetKey}", result.Count, setKey);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get members from set {SetKey}", setKey);
            throw;
        }
    }

    public async Task<bool> SetRemoveAsync(string setKey, string value, CancellationToken cancellationToken = default)
    {
        try
        {
            var result = await _database.SetRemoveAsync(setKey, value);
            _logger.LogDebug("Removed {Value} from set {SetKey}: {Result}", value, setKey, result);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to remove {Value} from set {SetKey}", value, setKey);
            throw;
        }
    }

    public async Task<bool> SortedSetAddAsync(string setKey, string value, double score, CancellationToken cancellationToken = default)
    {
        try
        {
            var result = await _database.SortedSetAddAsync(setKey, value, score);
            _logger.LogDebug("Added {Value} with score {Score} to sorted set {SetKey}: {Result}", 
                value, score, setKey, result);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to add {Value} to sorted set {SetKey}", value, setKey);
            throw;
        }
    }

    public async Task<IReadOnlyList<SortedSetEntry>> SortedSetTopAsync(string setKey, int count, CancellationToken cancellationToken = default)
    {
        try
        {
            var entries = await _database.SortedSetRangeByRankWithScoresAsync(setKey, 0, count - 1, Order.Descending);
            var result = entries.Select(e => new SortedSetEntry 
            { 
                Value = e.Element!, 
                Score = e.Score 
            }).ToList();
            
            _logger.LogDebug("Retrieved top {Count} entries from sorted set {SetKey}", count, setKey);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get top entries from sorted set {SetKey}", setKey);
            throw;
        }
    }

    public async Task PublishAsync(string channel, string message, CancellationToken cancellationToken = default)
    {
        try
        {
            var subscribers = await _subscriber.PublishAsync(RedisChannel.Literal(channel), message);
            _logger.LogDebug("Published message to channel {Channel}, {Subscribers} subscribers", 
                channel, subscribers);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to publish message to channel {Channel}", channel);
            throw;
        }
    }

    public async Task SubscribeAsync(string channel, Action<string, string> onMessage, CancellationToken cancellationToken = default)
    {
        try
        {
            await _subscriber.SubscribeAsync(RedisChannel.Literal(channel), (ch, msg) => onMessage(ch!, msg!));
            _logger.LogDebug("Subscribed to channel {Channel}", channel);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to subscribe to channel {Channel}", channel);
            throw;
        }
    }

    public async Task<CacheStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var server = _redis.GetServer(_redis.GetEndPoints().First());
            var info = await server.InfoAsync();
            
            var stats = new CacheStatistics();
            
            foreach (var section in info)
            {
                foreach (var item in section)
                {
                    switch (item.Key.ToLower())
                    {
                        case "used_memory":
                            if (long.TryParse(item.Value, out var usedMemory))
                                stats.UsedMemory = usedMemory;
                            break;
                        case "maxmemory":
                            if (long.TryParse(item.Value, out var maxMemory))
                                stats.MaxMemory = maxMemory;
                            break;
                        case "connected_clients":
                            if (long.TryParse(item.Value, out var connections))
                                stats.TotalConnections = connections;
                            break;
                        case "total_commands_processed":
                            if (long.TryParse(item.Value, out var commands))
                                stats.CommandsProcessed = commands;
                            break;
                        case "uptime_in_seconds":
                            if (long.TryParse(item.Value, out var uptime))
                                stats.Uptime = TimeSpan.FromSeconds(uptime);
                            break;
                    }
                }
            }
            
            // Calculate memory usage percentage
            if (stats.MaxMemory > 0)
            {
                stats.MemoryUsagePercentage = (double)stats.UsedMemory / stats.MaxMemory * 100;
            }
            
            // Get key count
            var dbSizeResult = await _database.ExecuteAsync("DBSIZE");
            stats.TotalKeys = (long)dbSizeResult;
            
            _logger.LogDebug("Retrieved cache statistics: {UsedMemory}/{MaxMemory} bytes, {TotalKeys} keys", 
                stats.UsedMemory, stats.MaxMemory, stats.TotalKeys);
            
            return stats;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get cache statistics");
            throw;
        }
    }

    private async Task UpdateSpatialIndex(Model model)
    {
        try
        {
            var gridKey = $"spatial:grid:{model.Location.GridId}";
            await _database.SetAddAsync(gridKey, model.Id.ToString());
            
            // Set expiration on the spatial index
            await _database.KeyExpireAsync(gridKey, _configuration.DefaultSpatialExpiration);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to update spatial index for model {ModelId}", model.Id);
        }
    }

    private string GetTransactionKey(Guid transactionId) => $"{_configuration.KeyPrefix}:transaction:{transactionId}";
    private string GetModelKey(Guid modelId) => $"{_configuration.KeyPrefix}:model:{modelId}";
    private string GetSpatialKey(string locationKey) => $"{_configuration.KeyPrefix}:spatial:{locationKey}";
    private string GetMetricsKey(string metricsKey) => $"{_configuration.KeyPrefix}:metrics:{metricsKey}";

    public void Dispose()
    {
        _redis?.Dispose();
    }
}

/// <summary>
/// Redis configuration settings
/// </summary>
public class RedisConfiguration
{
    public string ConnectionString { get; set; } = "localhost:6379";
    public int DatabaseIndex { get; set; } = 0;
    public string KeyPrefix { get; set; } = "tml";
    public TimeSpan DefaultExpiration { get; set; } = TimeSpan.FromHours(1);
    public TimeSpan DefaultTransactionExpiration { get; set; } = TimeSpan.FromMinutes(30);
    public TimeSpan DefaultModelExpiration { get; set; } = TimeSpan.FromHours(2);
    public TimeSpan DefaultSpatialExpiration { get; set; } = TimeSpan.FromMinutes(15);
    public TimeSpan DefaultMetricsExpiration { get; set; } = TimeSpan.FromMinutes(5);
    public int MaxRetries { get; set; } = 3;
    public TimeSpan ConnectTimeout { get; set; } = TimeSpan.FromSeconds(30);
}
