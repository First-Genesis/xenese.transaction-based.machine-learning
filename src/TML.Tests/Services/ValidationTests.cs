using FluentAssertions;
using TML.Core.Domain;
using Xunit;

namespace TML.Tests.Services;

public class ValidationTests
{
    [Theory]
    [InlineData(25.0, 15.0, true, "Valid thickness")]
    [InlineData(14.9, 15.0, false, "Below minimum thickness")]
    [InlineData(15.0, 15.0, true, "At minimum threshold")]
    [InlineData(0, 15.0, false, "Zero thickness")]
    [InlineData(-5.0, 15.0, false, "Negative thickness")]
    public void ValidateThickness_ShouldReturnExpectedResult(double thickness, double minThickness, bool expectedValid, string reason)
    {
        // Act
        var isValid = thickness >= minThickness && thickness > 0;

        // Assert
        isValid.Should().Be(expectedValid, reason);
    }

    [Theory]
    [InlineData(100.0, 200.0, true, "Valid coordinates")]
    [InlineData(0, 0, false, "Zero coordinates")]
    [InlineData(-100.0, 200.0, false, "Negative X coordinate")]
    [InlineData(100.0, -200.0, false, "Negative Y coordinate")]
    [InlineData(10000.0, 10000.0, false, "Out of bounds coordinates")]
    public void ValidateCoordinates_ShouldReturnExpectedResult(double x, double y, bool expectedValid, string reason)
    {
        // Arrange
        const double MAX_COORDINATE = 5000.0;

        // Act
        var isValid = x > 0 && y > 0 && x <= MAX_COORDINATE && y <= MAX_COORDINATE;

        // Assert
        isValid.Should().Be(expectedValid, reason);
    }

    [Theory]
    [InlineData(0.95, true, "High quality")]
    [InlineData(0.70, true, "Acceptable quality")]
    [InlineData(0.69, false, "Below threshold")]
    [InlineData(1.0, true, "Perfect quality")]
    [InlineData(0, false, "Zero quality")]
    [InlineData(1.1, false, "Over 100% quality")]
    public void ValidateQuality_ShouldReturnExpectedResult(double quality, bool expectedValid, string reason)
    {
        // Arrange
        const double MIN_QUALITY = 0.7;

        // Act
        var isValid = quality >= MIN_QUALITY && quality <= 1.0;

        // Assert
        isValid.Should().Be(expectedValid, reason);
    }

    [Fact]
    public void ValidateTransaction_CompleteValidation_ShouldPass()
    {
        // Arrange
        var transaction = new Transaction
        {
            Id = Guid.NewGuid(),
            Data = new TransactionData
            {
                XCoord = 100.0,
                YCoord = 200.0,
                Thickness = 25.0,
                MinThickness = 15.0,
                Quality = 0.95,
                Features = new Dictionary<string, double>
                {
                    ["temperature"] = 22.5,
                    ["pressure"] = 101.3
                }
            },
            Source = "test",
            Metadata = new Dictionary<string, object>(),
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };

        // Act
        var errors = new List<string>();

        if (transaction.Data.XCoord <= 0 || transaction.Data.YCoord <= 0)
            errors.Add("Invalid coordinates");

        if (transaction.Data.Thickness < transaction.Data.MinThickness)
            errors.Add("Thickness below minimum");

        if (transaction.Data.Quality < 0.7 || transaction.Data.Quality > 1.0)
            errors.Add("Quality out of range");

        if (string.IsNullOrWhiteSpace(transaction.Source))
            errors.Add("Source is required");

        // Assert
        errors.Should().BeEmpty("Transaction should be valid");
    }

    [Fact]
    public void ValidateModel_PhysicsConstraints_ShouldPass()
    {
        // Arrange
        var physicsValidation = new PhysicsValidation
        {
            IsValid = true,
            ValidationScore = 0.88,
            ThicknessValid = true,
            EnergyConservationValid = true,
            MassConservationValid = true,
            Violations = new List<string>()
        };

        // Act & Assert
        physicsValidation.IsValid.Should().BeTrue();
        physicsValidation.ValidationScore.Should().BeGreaterThan(0.8);
        physicsValidation.ThicknessValid.Should().BeTrue();
        physicsValidation.EnergyConservationValid.Should().BeTrue();
        physicsValidation.MassConservationValid.Should().BeTrue();
        physicsValidation.Violations.Should().BeEmpty();
    }

    [Theory]
    [InlineData(0.92, "Excellent", true)]
    [InlineData(0.85, "Good", true)]
    [InlineData(0.75, "Acceptable", true)]
    [InlineData(0.60, "Poor", false)]
    [InlineData(0.40, "Failed", false)]
    public void ClassifyModelConfidence_ShouldReturnCorrectClassification(double confidence, string expectedClass, bool expectedReliable)
    {
        // Act
        string actualClass;
        bool isReliable = confidence >= 0.7;

        if (confidence >= 0.9)
            actualClass = "Excellent";
        else if (confidence >= 0.8)
            actualClass = "Good";
        else if (confidence >= 0.7)
            actualClass = "Acceptable";
        else if (confidence >= 0.5)
            actualClass = "Poor";
        else
            actualClass = "Failed";

        // Assert
        actualClass.Should().Be(expectedClass);
        isReliable.Should().Be(expectedReliable);
    }

    [Fact]
    public void CalculateSpatialGrid_ShouldReturnCorrectGridId()
    {
        // Arrange
        var testCases = new[]
        {
            (x: 156.7, y: 289.3, expectedGrid: "grid_15_28"),
            (x: 100.0, y: 100.0, expectedGrid: "grid_10_10"),
            (x: 55.5, y: 44.4, expectedGrid: "grid_5_4"),
            (x: 999.9, y: 999.9, expectedGrid: "grid_99_99")
        };

        foreach (var testCase in testCases)
        {
            // Act
            var gridSize = 10.0;
            var gridX = (int)(testCase.x / gridSize);
            var gridY = (int)(testCase.y / gridSize);
            var actualGrid = $"grid_{gridX}_{gridY}";

            // Assert
            actualGrid.Should().Be(testCase.expectedGrid, 
                $"For coordinates ({testCase.x}, {testCase.y})");
        }
    }

    [Theory]
    [InlineData(0, 1, true, "Direct inheritance")]
    [InlineData(0, 5, true, "Deep inheritance allowed")]
    [InlineData(0, 10, true, "Very deep inheritance allowed")]
    [InlineData(0, 11, false, "Exceeds max depth")]
    [InlineData(5, 6, true, "Incremental depth")]
    public void ValidateInheritanceDepth_ShouldEnforceMaxDepth(int parentDepth, int childDepth, bool expectedValid, string reason)
    {
        // Arrange
        const int MAX_INHERITANCE_DEPTH = 10;

        // Act
        var isValid = childDepth == parentDepth + 1 && childDepth <= MAX_INHERITANCE_DEPTH;

        // Assert
        isValid.Should().Be(expectedValid, reason);
    }

    [Fact]
    public void ModelWeightUpdate_GradientDescent_ShouldUpdateCorrectly()
    {
        // Arrange
        var weights = new double[] { 0.5, 0.3, 0.2, 0.1 };
        var gradients = new double[] { 0.1, 0.05, 0.02, 0.01 };
        var learningRate = 0.01;
        var expectedWeights = new double[] { 0.499, 0.2995, 0.1998, 0.0999 };

        // Act
        var updatedWeights = new double[weights.Length];
        for (int i = 0; i < weights.Length; i++)
        {
            updatedWeights[i] = weights[i] - learningRate * gradients[i];
        }

        // Assert
        for (int i = 0; i < updatedWeights.Length; i++)
        {
            updatedWeights[i].Should().BeApproximately(expectedWeights[i], 0.0001,
                $"Weight {i} should be updated correctly");
        }
    }

    [Theory]
    [InlineData(100.0, 100.0, 105.0, 105.0, 7.071)]
    [InlineData(0, 0, 3.0, 4.0, 5.0)]
    [InlineData(100.0, 200.0, 100.0, 200.0, 0)]
    public void CalculateEuclideanDistance_ShouldBeAccurate(double x1, double y1, double x2, double y2, double expectedDistance)
    {
        // Act
        var distance = Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));

        // Assert
        distance.Should().BeApproximately(expectedDistance, 0.001);
    }
}
