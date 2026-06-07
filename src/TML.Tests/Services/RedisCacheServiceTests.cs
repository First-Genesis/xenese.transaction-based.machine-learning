using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using StackExchange.Redis;
using TML.Core.Domain;
using TML.Storage.Services;
using Xunit;

namespace TML.Tests.Services;

public class RedisCacheServiceTests : IDisposable
{
    private readonly Mock<IConnectionMultiplexer> _mockRedis;
    private readonly Mock<IDatabase> _mockDatabase;
    private readonly Mock<ISubscriber> _mockSubscriber;
    private readonly Mock<ILogger<RedisCacheService>> _mockLogger;
    private readonly RedisCacheService _service;
    private readonly RedisConfiguration _config;

    public RedisCacheServiceTests()
    {
        _mockRedis = new Mock<IConnectionMultiplexer>();
        _mockDatabase = new Mock<IDatabase>();
        _mockSubscriber = new Mock<ISubscriber>();
        _mockLogger = new Mock<ILogger<RedisCacheService>>();
        
        _config = new RedisConfiguration
        {
            ConnectionString = "localhost:6379",
            DatabaseIndex = 0,
            KeyPrefix = "test",
            DefaultExpiration = TimeSpan.FromMinutes(30)
        };

        _mockRedis.Setup(r => r.GetDatabase(_config.DatabaseIndex, null))
               .Returns(_mockDatabase.Object);
        _mockRedis.Setup(r => r.GetSubscriber(null))
               .Returns(_mockSubscriber.Object);

        var options = Options.Create(_config);
        _service = new RedisCacheService(_mockRedis.Object, _mockLogger.Object, options);
    }

    [Fact]
    public async Task SetTransactionAsync_ValidTransaction_ShouldCacheSuccessfully()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var expectedKey = $"{_config.KeyPrefix}:transaction:{transaction.Id}";
        
        _mockDatabase.Setup(d => d.StringSetAsync(
            expectedKey, 
            It.IsAny<RedisValue>(), 
            It.IsAny<TimeSpan?>(), 
            It.IsAny<When>(), 
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        await _service.SetTransactionAsync(transaction.Id, transaction);

        // Assert
        _mockDatabase.Verify(d => d.StringSetAsync(
            expectedKey,
            It.IsAny<RedisValue>(),
            It.IsAny<TimeSpan?>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task GetTransactionAsync_ExistingTransaction_ShouldReturnTransaction()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var expectedKey = $"{_config.KeyPrefix}:transaction:{transaction.Id}";
        var serializedTransaction = System.Text.Json.JsonSerializer.Serialize(transaction, new System.Text.Json.JsonSerializerOptions
        {
            PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase
        });

        _mockDatabase.Setup(d => d.StringGetAsync(expectedKey, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(new RedisValue(serializedTransaction));

        // Act
        var result = await _service.GetTransactionAsync(transaction.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(transaction.Id);
        result.Source.Should().Be(transaction.Source);
    }

    [Fact]
    public async Task GetTransactionAsync_NonExistentTransaction_ShouldReturnNull()
    {
        // Arrange
        var transactionId = Guid.NewGuid();
        var expectedKey = $"{_config.KeyPrefix}:transaction:{transactionId}";

        _mockDatabase.Setup(d => d.StringGetAsync(expectedKey, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(RedisValue.Null);

        // Act
        var result = await _service.GetTransactionAsync(transactionId);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task SetModelAsync_ValidModel_ShouldCacheSuccessfully()
    {
        // Arrange
        var model = CreateValidModel();
        var expectedKey = $"{_config.KeyPrefix}:model:{model.Id}";
        
        _mockDatabase.Setup(d => d.StringSetAsync(
            expectedKey, 
            It.IsAny<RedisValue>(), 
            It.IsAny<TimeSpan?>(), 
            It.IsAny<When>(), 
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        await _service.SetModelAsync(model.Id, model);

        // Assert
        _mockDatabase.Verify(d => d.StringSetAsync(
            expectedKey,
            It.IsAny<RedisValue>(),
            It.IsAny<TimeSpan?>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task SetSpatialNeighborsAsync_ValidNeighbors_ShouldCacheSuccessfully()
    {
        // Arrange
        var locationKey = "100.0_200.0_50.0";
        var neighborIds = new List<Guid> { Guid.NewGuid(), Guid.NewGuid() };
        var expectedKey = $"{_config.KeyPrefix}:spatial:{locationKey}";
        
        _mockDatabase.Setup(d => d.StringSetAsync(
            expectedKey, 
            It.IsAny<RedisValue>(), 
            It.IsAny<TimeSpan?>(), 
            It.IsAny<When>(), 
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        await _service.SetSpatialNeighborsAsync(locationKey, neighborIds);

        // Assert
        _mockDatabase.Verify(d => d.StringSetAsync(
            expectedKey,
            It.IsAny<RedisValue>(),
            It.IsAny<TimeSpan?>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task IncrementAsync_ValidKey_ShouldIncrementCounter()
    {
        // Arrange
        var key = "test-counter";
        var incrementValue = 5L;
        var expectedResult = 10L;

        _mockDatabase.Setup(d => d.StringIncrementAsync(key, incrementValue, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(expectedResult);

        // Act
        var result = await _service.IncrementAsync(key, incrementValue);

        // Assert
        result.Should().Be(expectedResult);
        _mockDatabase.Verify(d => d.StringIncrementAsync(key, incrementValue, It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task ExistsAsync_ExistingKey_ShouldReturnTrue()
    {
        // Arrange
        var key = "existing-key";
        _mockDatabase.Setup(d => d.KeyExistsAsync(key, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(true);

        // Act
        var result = await _service.ExistsAsync(key);

        // Assert
        result.Should().BeTrue();
    }

    [Fact]
    public async Task ExistsAsync_NonExistentKey_ShouldReturnFalse()
    {
        // Arrange
        var key = "non-existent-key";
        _mockDatabase.Setup(d => d.KeyExistsAsync(key, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(false);

        // Act
        var result = await _service.ExistsAsync(key);

        // Assert
        result.Should().BeFalse();
    }

    [Fact]
    public async Task GetOrSetAsync_CacheHit_ShouldReturnCachedValue()
    {
        // Arrange
        var key = "cache-key";
        var cachedValue = "cached-data";
        var serializedValue = System.Text.Json.JsonSerializer.Serialize(cachedValue);

        _mockDatabase.Setup(d => d.StringGetAsync(key, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(new RedisValue(serializedValue));

        var factoryCalled = false;
        Func<Task<string?>> factory = () =>
        {
            factoryCalled = true;
            return Task.FromResult<string?>("factory-data");
        };

        // Act
        var result = await _service.GetOrSetAsync(key, factory);

        // Assert
        result.Should().Be(cachedValue);
        factoryCalled.Should().BeFalse(); // Factory should not be called on cache hit
    }

    [Fact]
    public async Task GetOrSetAsync_CacheMiss_ShouldCallFactoryAndCache()
    {
        // Arrange
        var key = "cache-key";
        var factoryValue = "factory-data";

        _mockDatabase.Setup(d => d.StringGetAsync(key, It.IsAny<CommandFlags>()))
                    .ReturnsAsync(RedisValue.Null);

        _mockDatabase.Setup(d => d.StringSetAsync(
            key, 
            It.IsAny<RedisValue>(), 
            It.IsAny<TimeSpan?>(), 
            It.IsAny<When>(), 
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        var factoryCalled = false;
        Func<Task<string?>> factory = () =>
        {
            factoryCalled = true;
            return Task.FromResult<string?>(factoryValue);
        };

        // Act
        var result = await _service.GetOrSetAsync(key, factory);

        // Assert
        result.Should().Be(factoryValue);
        factoryCalled.Should().BeTrue(); // Factory should be called on cache miss
        
        _mockDatabase.Verify(d => d.StringSetAsync(
            key,
            It.IsAny<RedisValue>(),
            It.IsAny<TimeSpan?>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    private Transaction CreateValidTransaction()
    {
        return new Transaction
        {
            Id = Guid.NewGuid(),
            Data = new TransactionData
            {
                XCoord = 100.0,
                YCoord = 200.0,
                Thickness = 25.0,
                MinThickness = 15.0,
                Features = new Dictionary<string, double>(),
                Quality = 1.0
            },
            Source = "unit-test",
            Metadata = new Dictionary<string, object>(),
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };
    }

    private Model CreateValidModel()
    {
        return new Model
        {
            Id = Guid.NewGuid(),
            TransactionId = Guid.NewGuid(),
            ParentModelId = null,
            InheritanceDepth = 0,
            Status = ModelStatus.Active,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow,
            Version = 1,
            Parameters = new ModelParameters
            {
                Weights = new double[] { 0.5, 0.3, 0.2 },
                LearningRate = 0.01,
                Regularization = 0.001,
                Iterations = 100,
                ConvergenceThreshold = 0.0001
            },
            Location = new SpatialLocation
            {
                X = 100.0,
                Y = 200.0,
                GridId = "grid_10_20"
            },
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.05,
                RootMeanSquaredError = 0.22,
                MeanAbsoluteError = 0.18,
                RSquared = 0.85,
                Confidence = 0.92,
                TrainingDataPoints = 1000
            },
            PhysicsValidation = new PhysicsValidation
            {
                IsValid = true,
                ValidationScore = 0.88,
                ThicknessValid = true,
                EnergyConservationValid = true,
                MassConservationValid = true,
                Violations = new List<string>()
            }
        };
    }

    public void Dispose()
    {
        _service?.Dispose();
    }
}
