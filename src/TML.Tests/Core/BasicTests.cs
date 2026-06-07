using FluentAssertions;
using TML.Core.Domain;
using Xunit;

namespace TML.Tests.Core;

public class BasicTests
{
    [Fact]
    public void Transaction_Creation_ShouldWork()
    {
        // Arrange & Act
        var transaction = new Transaction
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
            Source = "test",
            Metadata = new Dictionary<string, object>(),
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };

        // Assert
        transaction.Should().NotBeNull();
        transaction.Id.Should().NotBeEmpty();
        transaction.Data.XCoord.Should().Be(100.0);
        transaction.Data.YCoord.Should().Be(200.0);
        transaction.Status.Should().Be(TransactionStatus.Pending);
    }

    [Fact]
    public void Model_Creation_ShouldWork()
    {
        // Arrange & Act
        var model = new Model
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

        // Assert
        model.Should().NotBeNull();
        model.Id.Should().NotBeEmpty();
        model.Parameters.Weights.Should().HaveCount(3);
        model.Location.X.Should().Be(100.0);
        model.Metrics.Confidence.Should().Be(0.92);
        model.PhysicsValidation.IsValid.Should().BeTrue();
    }

    [Fact]
    public void Model_WithExpression_ShouldWork()
    {
        // Arrange
        var originalModel = new Model
        {
            Id = Guid.NewGuid(),
            TransactionId = Guid.NewGuid(),
            InheritanceDepth = 0,
            Status = ModelStatus.Training,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow,
            Version = 1,
            Parameters = new ModelParameters
            {
                Weights = new double[] { 0.1, 0.2, 0.3 },
                LearningRate = 0.01,
                Regularization = 0.001,
                Iterations = 50,
                ConvergenceThreshold = 0.0001
            },
            Location = new SpatialLocation { X = 50.0, Y = 100.0, GridId = "grid_5_10" },
            Metrics = new ModelMetrics
            {
                MeanSquaredError = 0.1,
                RootMeanSquaredError = 0.32,
                MeanAbsoluteError = 0.25,
                RSquared = 0.75,
                Confidence = 0.8,
                TrainingDataPoints = 500
            },
            PhysicsValidation = new PhysicsValidation
            {
                IsValid = false,
                ValidationScore = 0.6,
                ThicknessValid = true,
                EnergyConservationValid = false,
                MassConservationValid = true,
                Violations = new List<string> { "Energy conservation failed" }
            }
        };

        // Act - Use 'with' expression to create updated model
        var updatedModel = originalModel with 
        { 
            Status = ModelStatus.Active,
            InheritanceDepth = 1,
            Version = 2
        };

        // Assert
        updatedModel.Should().NotBeNull();
        updatedModel.Id.Should().Be(originalModel.Id); // Same ID
        updatedModel.Status.Should().Be(ModelStatus.Active); // Updated
        updatedModel.InheritanceDepth.Should().Be(1); // Updated
        updatedModel.Version.Should().Be(2); // Updated
        updatedModel.Parameters.Should().Be(originalModel.Parameters); // Same reference
        updatedModel.Location.Should().Be(originalModel.Location); // Same reference
    }

    [Theory]
    [InlineData(TransactionStatus.Pending)]
    [InlineData(TransactionStatus.Completed)]
    [InlineData(TransactionStatus.Failed)]
    public void TransactionStatus_AllValues_ShouldBeValid(TransactionStatus status)
    {
        // Act & Assert
        Enum.IsDefined(typeof(TransactionStatus), status).Should().BeTrue();
    }

    [Theory]
    [InlineData(ModelStatus.Training)]
    [InlineData(ModelStatus.Active)]
    [InlineData(ModelStatus.Archived)]
    [InlineData(ModelStatus.Failed)]
    public void ModelStatus_AllValues_ShouldBeValid(ModelStatus status)
    {
        // Act & Assert
        Enum.IsDefined(typeof(ModelStatus), status).Should().BeTrue();
    }
}
