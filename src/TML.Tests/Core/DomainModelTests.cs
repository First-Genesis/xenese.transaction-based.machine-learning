using FluentAssertions;
using TML.Core.Domain;
using Xunit;

namespace TML.Tests.Core;

public class DomainModelTests
{
    [Fact]
    public void Transaction_ShouldInitializeWithCorrectDefaults()
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
                Features = new Dictionary<string, double>
                {
                    ["temperature"] = 22.5,
                    ["pressure"] = 101.3
                },
                Quality = 0.95
            },
            Source = "unit-test",
            Metadata = new Dictionary<string, object>
            {
                ["test_id"] = "test-001"
            },
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };

        // Assert
        transaction.Should().NotBeNull();
        transaction.Id.Should().NotBeEmpty();
        transaction.Data.Should().NotBeNull();
        transaction.Data.XCoord.Should().Be(100.0);
        transaction.Data.YCoord.Should().Be(200.0);
        transaction.Data.Thickness.Should().Be(25.0);
        transaction.Data.MinThickness.Should().Be(15.0);
        transaction.Data.Quality.Should().Be(0.95);
        transaction.Status.Should().Be(TransactionStatus.Pending);
        transaction.ProcessedAt.Should().BeNull();
        transaction.ModelId.Should().BeNull();
    }

    [Fact]
    public void Model_ShouldInitializeWithCorrectDefaults()
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
        model.TransactionId.Should().NotBeEmpty();
        model.ParentModelId.Should().BeNull();
        model.InheritanceDepth.Should().Be(0);
        model.Status.Should().Be(ModelStatus.Active);
        model.Version.Should().Be(1);
        
        model.Parameters.Should().NotBeNull();
        model.Parameters.Weights.Should().HaveCount(3);
        model.Parameters.LearningRate.Should().Be(0.01);
        
        model.Location.Should().NotBeNull();
        model.Location.X.Should().Be(100.0);
        model.Location.Y.Should().Be(200.0);
        model.Location.GridId.Should().Be("grid_10_20");
        
        model.Metrics.Should().NotBeNull();
        model.Metrics.Confidence.Should().Be(0.92);
        model.Metrics.RSquared.Should().Be(0.85);
        
        model.PhysicsValidation.Should().NotBeNull();
        model.PhysicsValidation.IsValid.Should().BeTrue();
    }

    [Fact]
    public void Model_WithInheritance_ShouldCreateChildModel()
    {
        // Arrange
        var parentModel = new Model
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
            Location = new SpatialLocation { X = 100.0, Y = 200.0, GridId = "grid_10_20" },
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

        // Act
        var childModel = parentModel with
        {
            Id = Guid.NewGuid(),
            TransactionId = Guid.NewGuid(),
            ParentModelId = parentModel.Id,
            InheritanceDepth = parentModel.InheritanceDepth + 1,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow,
            Version = 1
        };

        // Assert
        childModel.Should().NotBeNull();
        childModel.Id.Should().NotBe(parentModel.Id);
        childModel.ParentModelId.Should().Be(parentModel.Id);
        childModel.InheritanceDepth.Should().Be(1);
        childModel.Parameters.Should().BeSameAs(parentModel.Parameters); // Record copy semantics
        childModel.Location.Should().BeSameAs(parentModel.Location);
        childModel.Metrics.Should().BeSameAs(parentModel.Metrics);
    }

    [Theory]
    [InlineData(25.0, 15.0, true)]  // Valid thickness
    [InlineData(10.0, 15.0, false)] // Invalid - below minimum
    [InlineData(15.0, 15.0, true)]  // Valid - at minimum
    public void TransactionData_ThicknessValidation_ShouldWork(double thickness, double minThickness, bool expectedValid)
    {
        // Arrange
        var data = new TransactionData
        {
            XCoord = 100.0,
            YCoord = 200.0,
            Thickness = thickness,
            MinThickness = minThickness,
            Features = new Dictionary<string, double>(),
            Quality = 1.0
        };

        // Act
        var isValid = data.Thickness >= data.MinThickness;

        // Assert
        isValid.Should().Be(expectedValid);
    }

    [Theory]
    [InlineData(0.95, true)]  // High confidence
    [InlineData(0.80, true)]  // Medium confidence
    [InlineData(0.50, false)] // Low confidence
    public void ModelMetrics_ConfidenceThreshold_ShouldWork(double confidence, bool expectedHighConfidence)
    {
        // Arrange
        var metrics = new ModelMetrics
        {
            MeanSquaredError = 0.05,
            RootMeanSquaredError = 0.22,
            MeanAbsoluteError = 0.18,
            RSquared = 0.85,
            Confidence = confidence,
            TrainingDataPoints = 1000
        };

        // Act
        var isHighConfidence = metrics.Confidence >= 0.8;

        // Assert
        isHighConfidence.Should().Be(expectedHighConfidence);
    }

    [Fact]
    public void PhysicsValidation_WithViolations_ShouldBeInvalid()
    {
        // Arrange & Act
        var validation = new PhysicsValidation
        {
            IsValid = false,
            ValidationScore = 0.45,
            ThicknessValid = true,
            EnergyConservationValid = false,
            MassConservationValid = false,
            Violations = new List<string>
            {
                "Energy conservation failed",
                "Mass conservation failed"
            }
        };

        // Assert
        validation.IsValid.Should().BeFalse();
        validation.Violations.Should().HaveCount(2);
        validation.EnergyConservationValid.Should().BeFalse();
        validation.MassConservationValid.Should().BeFalse();
        validation.ValidationScore.Should().BeLessThan(0.5);
    }

    [Fact]
    public void SpatialLocation_GridIdCalculation_ShouldWork()
    {
        // Arrange
        var location = new SpatialLocation
        {
            X = 156.7,
            Y = 289.3,
            Z = null,
            GridId = null
        };

        // Act
        var gridSize = 10.0;
        var gridX = (int)(location.X / gridSize);
        var gridY = (int)(location.Y / gridSize);
        var calculatedGridId = $"grid_{gridX}_{gridY}";

        // Assert
        calculatedGridId.Should().Be("grid_15_28");
    }

    [Theory]
    [InlineData(100.0, 100.0, 105.0, 105.0, 7.07)] // Diagonal distance
    [InlineData(100.0, 100.0, 110.0, 100.0, 10.0)] // Horizontal distance
    [InlineData(100.0, 100.0, 100.0, 110.0, 10.0)] // Vertical distance
    public void SpatialDistance_Calculation_ShouldBeAccurate(double x1, double y1, double x2, double y2, double expectedDistance)
    {
        // Act
        var distance = Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));

        // Assert
        distance.Should().BeApproximately(expectedDistance, 0.01);
    }

    [Fact]
    public void ModelParameters_WeightUpdate_ShouldWork()
    {
        // Arrange
        var parameters = new ModelParameters
        {
            Weights = new double[] { 0.5, 0.3, 0.2 },
            LearningRate = 0.01,
            Regularization = 0.001,
            Iterations = 100,
            ConvergenceThreshold = 0.0001
        };

        // Act - Simulate weight update
        var updatedWeights = new double[parameters.Weights.Length];
        for (int i = 0; i < parameters.Weights.Length; i++)
        {
            updatedWeights[i] = parameters.Weights[i] - parameters.LearningRate * 0.1; // Gradient descent step
        }

        // Assert
        updatedWeights[0].Should().BeApproximately(0.499, 0.001);
        updatedWeights[1].Should().BeApproximately(0.299, 0.001);
        updatedWeights[2].Should().BeApproximately(0.199, 0.001);
    }
}
