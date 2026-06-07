using FluentAssertions;
using Microsoft.Extensions.Logging;
using Moq;
using Proto;
using TML.Actors.Actors;
using TML.Actors.Messages;
using TML.Core.Domain;
using Xunit;

namespace TML.Tests.Actors;

public class TransactionProcessorActorTests
{
    private readonly Mock<ILogger<TransactionProcessorActor>> _mockLogger;
    private readonly TransactionProcessorActor _actor;

    public TransactionProcessorActorTests()
    {
        _mockLogger = new Mock<ILogger<TransactionProcessorActor>>();
        _actor = new TransactionProcessorActor(_mockLogger.Object);
    }

    [Fact]
    public async Task ProcessTransaction_ValidTransaction_ReturnsSuccess()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        var message = new ProcessTransaction(transaction);
        var context = CreateMockContext();

        // Act
        await _actor.ReceiveAsync(context);

        // Assert
        // Verify that the actor processes the transaction correctly
        _mockLogger.Verify(
            x => x.Log(
                LogLevel.Information,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("Processing transaction")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }

    [Fact]
    public async Task ProcessTransactionBatch_ValidBatch_ProcessesAllTransactions()
    {
        // Arrange
        var transactions = new List<Transaction>
        {
            CreateValidTransaction(),
            CreateValidTransaction(),
            CreateValidTransaction()
        };
        var message = new ProcessTransactionBatch(transactions);
        var context = CreateMockContext();

        // Act
        await _actor.ReceiveAsync(context);

        // Assert
        transactions.Should().HaveCount(3);
        _mockLogger.Verify(
            x => x.Log(
                LogLevel.Information,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("Processing batch")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }

    [Fact]
    public void CreateValidTransaction_ShouldHaveValidProperties()
    {
        // Act
        var transaction = CreateValidTransaction();

        // Assert
        transaction.Should().NotBeNull();
        transaction.Id.Should().NotBeEmpty();
        transaction.Data.Should().NotBeNull();
        transaction.Data.XCoord.Should().BeGreaterThan(0);
        transaction.Data.YCoord.Should().BeGreaterThan(0);
        transaction.Data.Thickness.Should().BeGreaterThan(0);
        transaction.Status.Should().Be(TransactionStatus.Pending);
    }

    [Theory]
    [InlineData(0, 100, 25.0)] // Invalid X coordinate
    [InlineData(100, 0, 25.0)] // Invalid Y coordinate
    [InlineData(100, 100, 0)]  // Invalid thickness
    public void ValidateTransaction_InvalidData_ShouldFail(double x, double y, double thickness)
    {
        // Arrange
        var transaction = new Transaction
        {
            Id = Guid.NewGuid(),
            Data = new TransactionData
            {
                XCoord = x,
                YCoord = y,
                Thickness = thickness,
                MinThickness = 15.0,
                Features = new Dictionary<string, double>(),
                Quality = 1.0
            },
            Source = "test",
            Metadata = new Dictionary<string, object>(),
            Status = TransactionStatus.Pending
        };

        // Act & Assert
        var isValid = ValidateTransactionData(transaction);
        isValid.Should().BeFalse();
    }

    [Fact]
    public void ModelInheritance_ShouldCreateChildModel()
    {
        // Arrange
        var parentModel = CreateValidModel();
        var transaction = CreateValidTransaction();

        // Act
        var childModel = CreateChildModel(parentModel, transaction);

        // Assert
        childModel.Should().NotBeNull();
        childModel.ParentModelId.Should().Be(parentModel.Id);
        childModel.InheritanceDepth.Should().Be(parentModel.InheritanceDepth + 1);
        childModel.TransactionId.Should().Be(transaction.Id);
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
                    ["pressure"] = 101.3,
                    ["humidity"] = 45.2
                },
                Quality = 0.95
            },
            Source = "unit-test",
            Metadata = new Dictionary<string, object>
            {
                ["test_run"] = true,
                ["batch_id"] = "test-batch-001"
            },
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

    private Model CreateChildModel(Model parentModel, Transaction transaction)
    {
        return parentModel with
        {
            Id = Guid.NewGuid(),
            TransactionId = transaction.Id,
            ParentModelId = parentModel.Id,
            InheritanceDepth = parentModel.InheritanceDepth + 1,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow,
            Version = 1
        };
    }

    private bool ValidateTransactionData(Transaction transaction)
    {
        return transaction.Data.XCoord > 0 &&
               transaction.Data.YCoord > 0 &&
               transaction.Data.Thickness > 0 &&
               transaction.Data.Thickness >= transaction.Data.MinThickness;
    }

    private IContext CreateMockContext()
    {
        var mockContext = new Mock<IContext>();
        mockContext.Setup(x => x.Self).Returns(new PID("test", "test"));
        return mockContext.Object;
    }
}
