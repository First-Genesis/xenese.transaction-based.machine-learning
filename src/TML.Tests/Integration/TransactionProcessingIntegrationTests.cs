using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using TML.Actors.Services;
using TML.Core.Domain;
using TML.Storage.Data;
using TML.Storage.Repositories;
using Xunit;

namespace TML.Tests.Integration;

[Collection("Integration")]
public class TransactionProcessingIntegrationTests : IAsyncLifetime
{
    private readonly ServiceProvider _serviceProvider;
    private readonly TMLDbContext _context;
    private readonly ITransactionRepository _transactionRepository;
    private readonly IModelRepository _modelRepository;
    private readonly ActorSystemService _actorSystem;

    public TransactionProcessingIntegrationTests()
    {
        var services = new ServiceCollection();
        
        // Add logging
        services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Information));
        
        // Add in-memory database
        services.AddDbContext<TMLDbContext>(options =>
            options.UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString()));
        
        // Add repositories
        services.AddScoped<ITransactionRepository, TransactionRepository>();
        services.AddScoped<IModelRepository, ModelRepository>();
        
        // Add actor system
        var actorConfig = new ActorSystemConfiguration
        {
            ClusterName = "test-cluster",
            EnableClustering = false,
            TransactionProcessorCount = 1,
            ModelActorCount = 1,
            PhysicsValidatorCount = 1
        };
        services.AddSingleton(actorConfig);
        services.AddSingleton<ActorSystemService>();
        
        _serviceProvider = services.BuildServiceProvider();
        _context = _serviceProvider.GetRequiredService<TMLDbContext>();
        _transactionRepository = _serviceProvider.GetRequiredService<ITransactionRepository>();
        _modelRepository = _serviceProvider.GetRequiredService<IModelRepository>();
        _actorSystem = _serviceProvider.GetRequiredService<ActorSystemService>();
    }

    public async Task InitializeAsync()
    {
        await _context.Database.EnsureCreatedAsync();
        await _actorSystem.StartAsync(CancellationToken.None);
        
        // Wait for actor system to be ready
        await Task.Delay(1000);
    }

    public async Task DisposeAsync()
    {
        await _actorSystem.StopAsync(CancellationToken.None);
        await _context.Database.EnsureDeletedAsync();
        await _serviceProvider.DisposeAsync();
    }

    [Fact]
    public async Task EndToEnd_TransactionProcessing_ShouldCreateTransactionAndModel()
    {
        // Arrange
        var transaction = CreateValidTransaction();

        // Act - Create transaction in database
        var savedTransaction = await _transactionRepository.CreateAsync(transaction);

        // Assert - Transaction should be saved
        savedTransaction.Should().NotBeNull();
        savedTransaction.Id.Should().Be(transaction.Id);
        savedTransaction.Status.Should().Be(TransactionStatus.Pending);

        // Verify transaction exists in database
        var retrievedTransaction = await _transactionRepository.GetByIdAsync(transaction.Id);
        retrievedTransaction.Should().NotBeNull();
        retrievedTransaction!.Data.XCoord.Should().Be(100.5);
        retrievedTransaction.Data.YCoord.Should().Be(200.3);
    }

    [Fact]
    public async Task Repository_TransactionCRUD_ShouldWorkCorrectly()
    {
        // Arrange
        var transaction = CreateValidTransaction();

        // Act & Assert - Create
        var created = await _transactionRepository.CreateAsync(transaction);
        created.Should().NotBeNull();
        created.Id.Should().Be(transaction.Id);

        // Act & Assert - Read
        var retrieved = await _transactionRepository.GetByIdAsync(transaction.Id);
        retrieved.Should().NotBeNull();
        retrieved!.Source.Should().Be("integration-test");

        // Act & Assert - Update
        retrieved.Status = TransactionStatus.Completed;
        retrieved.ProcessedAt = DateTimeOffset.UtcNow;
        retrieved.ProcessingTimeMs = 123.45;

        var updated = await _transactionRepository.UpdateAsync(retrieved);
        updated.Should().NotBeNull();
        updated.Status.Should().Be(TransactionStatus.Completed);
        updated.ProcessingTimeMs.Should().Be(123.45);

        // Act & Assert - Delete
        var deleted = await _transactionRepository.DeleteAsync(transaction.Id);
        deleted.Should().BeTrue();

        var notFound = await _transactionRepository.GetByIdAsync(transaction.Id);
        notFound.Should().BeNull();
    }

    [Fact]
    public async Task Repository_ModelCRUD_ShouldWorkCorrectly()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        await _transactionRepository.CreateAsync(transaction);
        
        var model = CreateValidModel(transaction.Id);

        // Act & Assert - Create
        var created = await _modelRepository.CreateAsync(model);
        created.Should().NotBeNull();
        created.Id.Should().Be(model.Id);

        // Act & Assert - Read
        var retrieved = await _modelRepository.GetByIdAsync(model.Id);
        retrieved.Should().NotBeNull();
        retrieved!.Parameters.Algorithm.Should().Be("LinearRegression");
        retrieved.Location.X.Should().Be(100.0);
        retrieved.Location.Y.Should().Be(200.0);

        // Act & Assert - Update
        retrieved.Status = ModelStatus.Archived;
        retrieved.Version = 2;
        retrieved.UpdatedAt = DateTimeOffset.UtcNow;

        var updated = await _modelRepository.UpdateAsync(retrieved);
        updated.Should().NotBeNull();
        updated.Status.Should().Be(ModelStatus.Archived);
        updated.Version.Should().Be(2);
    }

    [Fact]
    public async Task Repository_ModelInheritance_ShouldWorkCorrectly()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        await _transactionRepository.CreateAsync(transaction1);
        await _transactionRepository.CreateAsync(transaction2);

        var parentModel = CreateValidModel(transaction1.Id);
        parentModel.InheritanceDepth = 0;
        parentModel.ParentModelId = null;

        var childModel = CreateValidModel(transaction2.Id);
        childModel.InheritanceDepth = 1;
        childModel.ParentModelId = parentModel.Id;

        // Act
        await _modelRepository.CreateAsync(parentModel);
        await _modelRepository.CreateAsync(childModel);

        // Assert - Get inheritance chain
        var chain = await _modelRepository.GetInheritanceChainAsync(childModel.Id);
        chain.Should().HaveCount(2);
        chain.First().Id.Should().Be(parentModel.Id);
        chain.Last().Id.Should().Be(childModel.Id);

        // Assert - Get by inheritance depth
        var rootModels = await _modelRepository.GetByInheritanceDepthAsync(0);
        var childModels = await _modelRepository.GetByInheritanceDepthAsync(1);

        rootModels.Should().HaveCount(1);
        rootModels.First().Id.Should().Be(parentModel.Id);

        childModels.Should().HaveCount(1);
        childModels.First().Id.Should().Be(childModel.Id);
    }

    [Fact]
    public async Task Repository_SpatialQueries_ShouldWorkCorrectly()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        var transaction3 = CreateValidTransaction();
        
        await _transactionRepository.CreateAsync(transaction1);
        await _transactionRepository.CreateAsync(transaction2);
        await _transactionRepository.CreateAsync(transaction3);

        var model1 = CreateValidModel(transaction1.Id);
        model1 = model1 with { Location = new SpatialLocation { X = 100.0, Y = 100.0, GridId = "grid_10_10" } };

        var model2 = CreateValidModel(transaction2.Id);
        model2 = model2 with { Location = new SpatialLocation { X = 105.0, Y = 105.0, GridId = "grid_10_10" } };

        var model3 = CreateValidModel(transaction3.Id);
        model3 = model3 with { Location = new SpatialLocation { X = 200.0, Y = 200.0, GridId = "grid_20_20" } };

        await _modelRepository.CreateAsync(model1);
        await _modelRepository.CreateAsync(model2);
        await _modelRepository.CreateAsync(model3);

        // Act - Find neighbors within 10 units of (100, 100)
        var nearbyModels = await _modelRepository.FindSpatialNeighborsAsync(100.0, 100.0, 10.0, 5);

        // Assert
        nearbyModels.Should().HaveCount(2);
        nearbyModels.Should().Contain(m => m.Id == model1.Id);
        nearbyModels.Should().Contain(m => m.Id == model2.Id);
        nearbyModels.Should().NotContain(m => m.Id == model3.Id);
    }

    [Fact]
    public async Task ActorSystem_HealthCheck_ShouldReturnHealthyStatus()
    {
        // Act
        var health = await _actorSystem.GetHealthStatusAsync();

        // Assert
        health.Should().NotBeNull();
        health.IsHealthy.Should().BeTrue();
        health.ActorCount.Should().BeGreaterThan(0);
        health.TransactionProcessorCount.Should().Be(1);
        health.ModelActorCount.Should().Be(1);
        health.PhysicsValidatorCount.Should().Be(1);
    }

    [Fact]
    public async Task Repository_Statistics_ShouldCalculateCorrectly()
    {
        // Arrange
        var transactions = new List<Transaction>();
        var models = new List<Model>();

        for (int i = 0; i < 5; i++)
        {
            var transaction = CreateValidTransaction();
            transaction.Status = i < 3 ? TransactionStatus.Completed : TransactionStatus.Pending;
            if (transaction.Status == TransactionStatus.Completed)
            {
                transaction.ProcessingTimeMs = 100.0 + i * 10;
            }
            
            transactions.Add(transaction);
            await _transactionRepository.CreateAsync(transaction);

            var model = CreateValidModel(transaction.Id);
            model = model with 
            {
                Status = i < 2 ? ModelStatus.Active : (i < 4 ? ModelStatus.Training : ModelStatus.Failed),
                InheritanceDepth = i % 3,
                Metrics = new ModelMetrics
                {
                    MeanSquaredError = 0.05 + (i * 0.01),
                    RootMeanSquaredError = 0.22 + (i * 0.02),
                    MeanAbsoluteError = 0.18 + (i * 0.01),
                    RSquared = 0.6 + (i * 0.08),
                    Confidence = 0.7 + (i * 0.05),
                    TrainingDataPoints = 1000 + (i * 100)
                }
            };
            
            models.Add(model);
            await _modelRepository.CreateAsync(model);
        }

        // Act
        var transactionStats = await _transactionRepository.GetStatisticsAsync();
        var modelStats = await _modelRepository.GetStatisticsAsync();

        // Assert - Transaction Statistics
        transactionStats.Should().NotBeNull();
        transactionStats.TotalCount.Should().Be(5);
        transactionStats.CompletedCount.Should().Be(3);
        transactionStats.PendingCount.Should().Be(2);
        transactionStats.FailedCount.Should().Be(0);
        transactionStats.AverageProcessingTimeMs.Should().BeGreaterThan(0);

        // Assert - Model Statistics
        modelStats.Should().NotBeNull();
        modelStats.TotalCount.Should().Be(5);
        modelStats.ActiveCount.Should().Be(2);
        modelStats.TrainingCount.Should().Be(2);
        modelStats.FailedCount.Should().Be(1);
        modelStats.MaxInheritanceDepth.Should().Be(2);
        modelStats.AverageConfidence.Should().BeApproximately(0.8, 0.1);
        modelStats.AverageRSquared.Should().BeApproximately(0.76, 0.1);
    }

    private Transaction CreateValidTransaction()
    {
        return new Transaction
        {
            Id = Guid.NewGuid(),
            Data = new TransactionData
            {
                XCoord = 100.5,
                YCoord = 200.3,
                Thickness = 25.7,
                MinThickness = 15.0,
                Features = new Dictionary<string, double>
                {
                    ["temperature"] = 22.5,
                    ["pressure"] = 101.3
                },
                Quality = 0.95
            },
            Source = "integration-test",
            Metadata = new Dictionary<string, object>
            {
                ["test_run"] = true,
                ["batch_id"] = Guid.NewGuid().ToString()
            },
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };
    }

    private Model CreateValidModel(Guid transactionId)
    {
        return new Model
        {
            Id = Guid.NewGuid(),
            TransactionId = transactionId,
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
                Z = null,
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
}
