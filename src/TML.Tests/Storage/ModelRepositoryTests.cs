using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Moq;
using TML.Core.Domain;
using TML.Storage.Data;
using TML.Storage.Repositories;
using Xunit;

namespace TML.Tests.Storage;

public class ModelRepositoryTests : IDisposable
{
    private readonly TMLDbContext _context;
    private readonly ModelRepository _repository;
    private readonly Mock<ILogger<ModelRepository>> _mockLogger;

    public ModelRepositoryTests()
    {
        var options = new DbContextOptionsBuilder<TMLDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new TMLDbContext(options);
        _mockLogger = new Mock<ILogger<ModelRepository>>();
        _repository = new ModelRepository(_context, _mockLogger.Object);
    }

    [Fact]
    public async Task CreateAsync_ValidModel_ShouldCreateSuccessfully()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var model = CreateValidModel(transaction.Id);
        
        await _context.Transactions.AddAsync(transaction);
        await _context.SaveChangesAsync();

        // Act
        var result = await _repository.CreateAsync(model);

        // Assert
        result.Should().NotBeNull();
        result.Id.Should().Be(model.Id);
        
        var savedModel = await _context.Models.FindAsync(model.Id);
        savedModel.Should().NotBeNull();
        savedModel!.Status.Should().Be(ModelStatus.Active);
    }

    [Fact]
    public async Task GetByIdAsync_ExistingModel_ShouldReturnModel()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var model = CreateValidModel(transaction.Id);
        
        await _context.Transactions.AddAsync(transaction);
        await _context.Models.AddAsync(model);
        await _context.SaveChangesAsync();

        // Act
        var result = await _repository.GetByIdAsync(model.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(model.Id);
        result.TransactionId.Should().Be(transaction.Id);
        result.Parameters.Algorithm.Should().Be("LinearRegression");
    }

    [Fact]
    public async Task GetByTransactionIdAsync_ExistingTransaction_ShouldReturnModels()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var model1 = CreateValidModel(transaction.Id);
        var model2 = CreateValidModel(transaction.Id);
        
        await _context.Transactions.AddAsync(transaction);
        await _context.Models.AddRangeAsync(model1, model2);
        await _context.SaveChangesAsync();

        // Act
        var results = await _repository.GetByTransactionIdAsync(transaction.Id);

        // Assert
        results.Should().HaveCount(2);
        results.All(m => m.TransactionId == transaction.Id).Should().BeTrue();
    }

    [Fact]
    public async Task FindSpatialNeighborsAsync_WithinRadius_ShouldReturnNearbyModels()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        var model1 = CreateValidModel(transaction1.Id) with 
        { 
            Location = new SpatialLocation { X = 100.0, Y = 100.0, GridId = "grid_10_10" } 
        };
        
        var model2 = CreateValidModel(transaction2.Id) with 
        { 
            Location = new SpatialLocation { X = 105.0, Y = 105.0, GridId = "grid_10_10" } 
        };
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2);
        await _context.Models.AddRangeAsync(model1, model2);
        await _context.SaveChangesAsync();

        // Act
        var results = await _repository.FindSpatialNeighborsAsync(100.0, 100.0, 10.0, 5);

        // Assert
        results.Should().HaveCount(2);
        results.Should().Contain(m => m.Id == model1.Id);
        results.Should().Contain(m => m.Id == model2.Id);
    }

    [Fact]
    public async Task GetInheritanceChainAsync_WithParentChild_ShouldReturnChain()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        var parentModel = CreateValidModel(transaction1.Id) with { InheritanceDepth = 0 };
        
        var childModel = CreateValidModel(transaction2.Id) with 
        { 
            ParentModelId = parentModel.Id, 
            InheritanceDepth = 1 
        };
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2);
        await _context.Models.AddRangeAsync(parentModel, childModel);
        await _context.SaveChangesAsync();

        // Act
        var chain = await _repository.GetInheritanceChainAsync(childModel.Id);

        // Assert
        chain.Should().HaveCount(2);
        chain.First().Id.Should().Be(parentModel.Id); // Root first
        chain.Last().Id.Should().Be(childModel.Id);   // Child last
    }

    [Fact]
    public async Task GetByStatusAsync_FiltersByStatus_ShouldReturnCorrectModels()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        var activeModel = CreateValidModel(transaction1.Id);
        activeModel.Status = ModelStatus.Active;
        
        var trainingModel = CreateValidModel(transaction2.Id);
        trainingModel.Status = ModelStatus.Training;
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2);
        await _context.Models.AddRangeAsync(activeModel, trainingModel);
        await _context.SaveChangesAsync();

        // Act
        var activeResults = await _repository.GetByStatusAsync(ModelStatus.Active);
        var trainingResults = await _repository.GetByStatusAsync(ModelStatus.Training);

        // Assert
        activeResults.Should().HaveCount(1);
        activeResults.First().Status.Should().Be(ModelStatus.Active);
        
        trainingResults.Should().HaveCount(1);
        trainingResults.First().Status.Should().Be(ModelStatus.Training);
    }

    [Fact]
    public async Task GetByInheritanceDepthAsync_FiltersByDepth_ShouldReturnCorrectModels()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        var rootModel = CreateValidModel(transaction1.Id) with { InheritanceDepth = 0 };
        
        var childModel = CreateValidModel(transaction2.Id) with 
        { 
            InheritanceDepth = 1, 
            ParentModelId = rootModel.Id 
        };
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2);
        await _context.Models.AddRangeAsync(rootModel, childModel);
        await _context.SaveChangesAsync();

        // Act
        var rootResults = await _repository.GetByInheritanceDepthAsync(0);
        var childResults = await _repository.GetByInheritanceDepthAsync(1);

        // Assert
        rootResults.Should().HaveCount(1);
        rootResults.First().InheritanceDepth.Should().Be(0);
        
        childResults.Should().HaveCount(1);
        childResults.First().InheritanceDepth.Should().Be(1);
    }

    [Fact]
    public async Task GetStatisticsAsync_WithData_ShouldReturnCorrectStatistics()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        var transaction3 = CreateValidTransaction();
        
        var activeModel = CreateValidModel(transaction1.Id) with 
        { 
            Status = ModelStatus.Active, 
            InheritanceDepth = 0,
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.05,
                RootMeanSquaredError = 0.22,
                MeanAbsoluteError = 0.18,
                RSquared = 0.85,
                Confidence = 0.9,
                TrainingDataPoints = 1000
            }
        };
        
        var trainingModel = CreateValidModel(transaction2.Id) with 
        { 
            Status = ModelStatus.Training, 
            InheritanceDepth = 1,
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.08,
                RootMeanSquaredError = 0.28,
                MeanAbsoluteError = 0.22,
                RSquared = 0.75,
                Confidence = 0.8,
                TrainingDataPoints = 800
            }
        };
        
        var failedModel = CreateValidModel(transaction3.Id) with 
        { 
            Status = ModelStatus.Failed, 
            InheritanceDepth = 0,
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.15,
                RootMeanSquaredError = 0.39,
                MeanAbsoluteError = 0.32,
                RSquared = 0.3,
                Confidence = 0.5,
                TrainingDataPoints = 500
            }
        };
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2, transaction3);
        await _context.Models.AddRangeAsync(activeModel, trainingModel, failedModel);
        await _context.SaveChangesAsync();

        // Act
        var stats = await _repository.GetStatisticsAsync();

        // Assert
        stats.Should().NotBeNull();
        stats.TotalCount.Should().Be(3);
        stats.ActiveCount.Should().Be(1);
        stats.TrainingCount.Should().Be(1);
        stats.FailedCount.Should().Be(1);
        stats.MaxInheritanceDepth.Should().Be(1);
        stats.AverageConfidence.Should().BeApproximately(0.73, 0.01);
        stats.AverageRSquared.Should().BeApproximately(0.63, 0.01);
    }

    [Fact]
    public async Task SearchAsync_WithCriteria_ShouldReturnFilteredResults()
    {
        // Arrange
        var transaction1 = CreateValidTransaction();
        var transaction2 = CreateValidTransaction();
        
        var highConfidenceModel = CreateValidModel(transaction1.Id) with 
        { 
            Status = ModelStatus.Active,
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.02,
                RootMeanSquaredError = 0.14,
                MeanAbsoluteError = 0.12,
                RSquared = 0.92,
                Confidence = 0.9,
                TrainingDataPoints = 1200
            }
        };
        
        var lowConfidenceModel = CreateValidModel(transaction2.Id) with 
        { 
            Status = ModelStatus.Training,
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.12,
                RootMeanSquaredError = 0.35,
                MeanAbsoluteError = 0.28,
                RSquared = 0.65,
                Confidence = 0.5,
                TrainingDataPoints = 600
            }
        };
        
        await _context.Transactions.AddRangeAsync(transaction1, transaction2);
        await _context.Models.AddRangeAsync(highConfidenceModel, lowConfidenceModel);
        await _context.SaveChangesAsync();

        var criteria = new ModelSearchCriteria
        {
            Status = ModelStatus.Active,
            MinConfidence = 0.8,
            Limit = 10
        };

        // Act
        var results = await _repository.SearchAsync(criteria);

        // Assert
        results.Should().HaveCount(1);
        results.First().Id.Should().Be(highConfidenceModel.Id);
        results.First().Metrics.Confidence.Should().BeGreaterOrEqualTo(0.8);
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

    public void Dispose()
    {
        _context.Dispose();
    }
}
