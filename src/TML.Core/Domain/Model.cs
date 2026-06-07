using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace TML.Core.Domain;

/// <summary>
/// Represents a machine learning model created from a transaction.
/// Each model can inherit from a parent model and has its own learning state.
/// </summary>
public sealed record Model
{
    /// <summary>
    /// Unique identifier for the model
    /// </summary>
    [Required]
    public Guid Id { get; init; } = Guid.NewGuid();

    /// <summary>
    /// Transaction that created this model
    /// </summary>
    [Required]
    public Guid TransactionId { get; init; }

    /// <summary>
    /// Parent model for inheritance (null for root models)
    /// </summary>
    public Guid? ParentModelId { get; init; }

    /// <summary>
    /// Depth in the inheritance hierarchy (0 for root models)
    /// </summary>
    [Range(0, int.MaxValue)]
    public int InheritanceDepth { get; init; }

    /// <summary>
    /// Model parameters and weights
    /// </summary>
    [Required]
    public ModelParameters Parameters { get; init; } = null!;

    /// <summary>
    /// Physics validation results
    /// </summary>
    [Required]
    public PhysicsValidation PhysicsValidation { get; init; } = null!;

    /// <summary>
    /// Model performance metrics
    /// </summary>
    [Required]
    public ModelMetrics Metrics { get; init; } = null!;

    /// <summary>
    /// Spatial location of the model
    /// </summary>
    [Required]
    public SpatialLocation Location { get; init; } = null!;

    /// <summary>
    /// Model creation timestamp
    /// </summary>
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;

    /// <summary>
    /// Last update timestamp
    /// </summary>
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;

    /// <summary>
    /// Model version for tracking updates
    /// </summary>
    [Range(1, int.MaxValue)]
    public int Version { get; set; } = 1;

    /// <summary>
    /// Current model status
    /// </summary>
    public ModelStatus Status { get; set; } = ModelStatus.Active;

    /// <summary>
    /// Storage location for model artifacts (S3 path, etc.)
    /// </summary>
    public string? ArtifactLocation { get; set; }
}

/// <summary>
/// Model parameters and learned weights
/// </summary>
public sealed class ModelParameters
{
    /// <summary>
    /// Linear regression weights
    /// </summary>
    public double[] Weights { get; init; } = Array.Empty<double>();

    /// <summary>
    /// Bias term
    /// </summary>
    public double Bias { get; init; }

    /// <summary>
    /// Learning rate used for training
    /// </summary>
    [Range(0.0, 1.0)]
    public double LearningRate { get; init; } = 0.01;

    /// <summary>
    /// Regularization parameter
    /// </summary>
    [Range(0.0, 1.0)]
    public double Regularization { get; init; } = 0.001;

    /// <summary>
    /// Number of training iterations
    /// </summary>
    [Range(0, int.MaxValue)]
    public int Iterations { get; init; }

    /// <summary>
    /// Convergence threshold
    /// </summary>
    [Range(0.0, 1.0)]
    public double ConvergenceThreshold { get; init; } = 0.0001;
}

/// <summary>
/// Physics validation results for the model
/// </summary>
public sealed class PhysicsValidation
{
    /// <summary>
    /// Whether the model passes physics constraints
    /// </summary>
    public bool IsValid { get; init; }

    /// <summary>
    /// Thickness validation result
    /// </summary>
    public bool ThicknessValid { get; init; }

    /// <summary>
    /// Energy conservation validation
    /// </summary>
    public bool EnergyConservationValid { get; init; }

    /// <summary>
    /// Mass conservation validation
    /// </summary>
    public bool MassConservationValid { get; init; }

    /// <summary>
    /// List of validation violations
    /// </summary>
    public List<string> Violations { get; init; } = new();

    /// <summary>
    /// Physics validation score (0.0 to 1.0)
    /// </summary>
    [Range(0.0, 1.0)]
    public double ValidationScore { get; init; }
}

/// <summary>
/// Model performance metrics
/// </summary>
public sealed class ModelMetrics
{
    /// <summary>
    /// Mean Squared Error
    /// </summary>
    [Range(0.0, double.MaxValue)]
    public double MeanSquaredError { get; init; }

    /// <summary>
    /// Root Mean Squared Error
    /// </summary>
    [Range(0.0, double.MaxValue)]
    public double RootMeanSquaredError { get; init; }

    /// <summary>
    /// Mean Absolute Error
    /// </summary>
    [Range(0.0, double.MaxValue)]
    public double MeanAbsoluteError { get; init; }

    /// <summary>
    /// R-squared coefficient of determination
    /// </summary>
    [Range(-1.0, 1.0)]
    public double RSquared { get; init; }

    /// <summary>
    /// Prediction confidence (0.0 to 1.0)
    /// </summary>
    [Range(0.0, 1.0)]
    public double Confidence { get; init; }

    /// <summary>
    /// Number of data points used for training
    /// </summary>
    [Range(1, int.MaxValue)]
    public int TrainingDataPoints { get; init; }
}

/// <summary>
/// Spatial location information for the model
/// </summary>
public sealed class SpatialLocation
{
    /// <summary>
    /// X coordinate
    /// </summary>
    public double X { get; init; }

    /// <summary>
    /// Y coordinate
    /// </summary>
    public double Y { get; init; }

    /// <summary>
    /// Z coordinate (optional)
    /// </summary>
    public double? Z { get; init; }

    /// <summary>
    /// Spatial grid identifier
    /// </summary>
    public string? GridId { get; init; }

    /// <summary>
    /// Neighboring model IDs for spatial relationships
    /// </summary>
    public List<Guid> Neighbors { get; init; } = new();
}

/// <summary>
/// Model status enumeration
/// </summary>
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum ModelStatus
{
    /// <summary>
    /// Model is active and can be used for predictions
    /// </summary>
    Active,

    /// <summary>
    /// Model is being trained or updated
    /// </summary>
    Training,

    /// <summary>
    /// Model has been archived
    /// </summary>
    Archived,

    /// <summary>
    /// Model has been deprecated
    /// </summary>
    Deprecated,

    /// <summary>
    /// Model has failed validation
    /// </summary>
    Failed
}
