using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace TML.Core.Domain;

/// <summary>
/// Represents a single transaction in the TML system.
/// Each transaction creates one model with potential inheritance.
/// </summary>
public sealed class Transaction
{
    /// <summary>
    /// Unique identifier for the transaction
    /// </summary>
    [Required]
    public Guid Id { get; init; } = Guid.NewGuid();

    /// <summary>
    /// Transaction data payload
    /// </summary>
    [Required]
    public TransactionData Data { get; init; } = null!;

    /// <summary>
    /// Source system or component that created this transaction
    /// </summary>
    [Required]
    public string Source { get; init; } = string.Empty;

    /// <summary>
    /// Additional metadata for the transaction
    /// </summary>
    public Dictionary<string, object> Metadata { get; init; } = new();

    /// <summary>
    /// Timestamp when the transaction was created
    /// </summary>
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;

    /// <summary>
    /// Current processing status
    /// </summary>
    public TransactionStatus Status { get; set; } = TransactionStatus.Pending;

    /// <summary>
    /// Timestamp when processing was completed
    /// </summary>
    public DateTimeOffset? ProcessedAt { get; set; }

    /// <summary>
    /// Processing error details if any
    /// </summary>
    public string? ErrorDetails { get; set; }

    /// <summary>
    /// Processing duration in milliseconds
    /// </summary>
    public double? ProcessingTimeMs { get; set; }

    /// <summary>
    /// ID of the model created from this transaction
    /// </summary>
    public Guid? ModelId { get; set; }
}

/// <summary>
/// Transaction data containing the actual measurement or input data
/// </summary>
public sealed class TransactionData
{
    /// <summary>
    /// X coordinate for spatial data
    /// </summary>
    public double XCoord { get; init; }

    /// <summary>
    /// Y coordinate for spatial data
    /// </summary>
    public double YCoord { get; init; }

    /// <summary>
    /// Thickness measurement in millimeters
    /// </summary>
    [Range(0.0, 100.0)]
    public double Thickness { get; init; }

    /// <summary>
    /// Minimum acceptable thickness threshold
    /// </summary>
    [Range(0.0, 100.0)]
    public double MinThickness { get; init; } = 15.0;

    /// <summary>
    /// Additional sensor data or features
    /// </summary>
    public Dictionary<string, double> Features { get; init; } = new();

    /// <summary>
    /// Quality score of the measurement (0.0 to 1.0)
    /// </summary>
    [Range(0.0, 1.0)]
    public double Quality { get; init; } = 1.0;
}

/// <summary>
/// Transaction processing status enumeration
/// </summary>
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum TransactionStatus
{
    /// <summary>
    /// Transaction is waiting to be processed
    /// </summary>
    Pending,

    /// <summary>
    /// Transaction is currently being processed
    /// </summary>
    Processing,

    /// <summary>
    /// Transaction was processed successfully
    /// </summary>
    Completed,

    /// <summary>
    /// Transaction processing failed
    /// </summary>
    Failed,

    /// <summary>
    /// Transaction was cancelled
    /// </summary>
    Cancelled
}
