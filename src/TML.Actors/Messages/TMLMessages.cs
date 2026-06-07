using TML.Core.Domain;

namespace TML.Actors.Messages;

/// <summary>
/// Base interface for all TML actor messages
/// </summary>
public interface ITMLMessage
{
    /// <summary>
    /// Unique message identifier
    /// </summary>
    Guid MessageId { get; }

    /// <summary>
    /// Message timestamp
    /// </summary>
    DateTimeOffset Timestamp { get; }

    /// <summary>
    /// Correlation ID for tracing
    /// </summary>
    string? CorrelationId { get; }
}

/// <summary>
/// Base record for TML messages with common properties
/// </summary>
public abstract record TMLMessage : ITMLMessage
{
    public Guid MessageId { get; init; } = Guid.NewGuid();
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;
    public string? CorrelationId { get; init; }
}

// Transaction Processing Messages

/// <summary>
/// Message to process a single transaction
/// </summary>
public sealed record ProcessTransaction(Transaction Transaction) : TMLMessage;

/// <summary>
/// Message to process multiple transactions in batch
/// </summary>
public sealed record ProcessTransactionBatch(IReadOnlyList<Transaction> Transactions) : TMLMessage;

/// <summary>
/// Response message for transaction processing
/// </summary>
public sealed record TransactionProcessed(
    Guid TransactionId,
    bool Success,
    Model? Model = null,
    string? ErrorMessage = null,
    double ProcessingTimeMs = 0) : TMLMessage;

/// <summary>
/// Response message for batch transaction processing
/// </summary>
public sealed record TransactionBatchProcessed(
    IReadOnlyList<TransactionProcessed> Results,
    int SuccessCount,
    int FailureCount,
    double TotalProcessingTimeMs) : TMLMessage;

// Model Management Messages

/// <summary>
/// Message to create a new model
/// </summary>
public sealed record CreateModel(
    Guid TransactionId,
    TransactionData Data,
    Guid? ParentModelId = null) : TMLMessage;

/// <summary>
/// Message to update an existing model
/// </summary>
public sealed record UpdateModel(
    Guid ModelId,
    TransactionData NewData) : TMLMessage;

/// <summary>
/// Message to retrieve a model
/// </summary>
public sealed record GetModel(Guid ModelId) : TMLMessage;

/// <summary>
/// Response message for model operations
/// </summary>
public sealed record ModelResponse(
    Guid ModelId,
    Model? Model = null,
    bool Success = true,
    string? ErrorMessage = null) : TMLMessage;

/// <summary>
/// Message to find spatial neighbors for a model
/// </summary>
public sealed record FindSpatialNeighbors(
    double X,
    double Y,
    double SearchRadius = 50.0,
    int MaxNeighbors = 5) : TMLMessage;

/// <summary>
/// Response message for spatial neighbor search
/// </summary>
public sealed record SpatialNeighborsFound(
    IReadOnlyList<Model> Neighbors) : TMLMessage;

// Physics Validation Messages

/// <summary>
/// Message to validate physics constraints
/// </summary>
public sealed record ValidatePhysics(
    TransactionData Data,
    Model? ParentModel = null) : TMLMessage;

/// <summary>
/// Response message for physics validation
/// </summary>
public sealed record PhysicsValidated(
    PhysicsValidation Validation,
    bool IsValid,
    IReadOnlyList<string> Violations) : TMLMessage;

// System Management Messages

/// <summary>
/// Message to get actor system health status
/// </summary>
public sealed record GetHealthStatus() : TMLMessage;

/// <summary>
/// Response message for health status
/// </summary>
public sealed record HealthStatusResponse(
    string ActorId,
    bool IsHealthy,
    Dictionary<string, object> Metrics,
    DateTimeOffset LastUpdate) : TMLMessage;

/// <summary>
/// Message to get performance metrics
/// </summary>
public sealed record GetMetrics() : TMLMessage;

/// <summary>
/// Response message for performance metrics
/// </summary>
public sealed record MetricsResponse(
    string ActorId,
    long ProcessedTransactions,
    double AverageProcessingTimeMs,
    double ThroughputTPS,
    Dictionary<string, double> CustomMetrics) : TMLMessage;

/// <summary>
/// Message to shutdown an actor gracefully
/// </summary>
public sealed record Shutdown(string Reason = "Normal shutdown") : TMLMessage;

/// <summary>
/// Message to restart an actor
/// </summary>
public sealed record Restart(string Reason = "Manual restart") : TMLMessage;

// Cluster Management Messages

/// <summary>
/// Message to join the cluster
/// </summary>
public sealed record JoinCluster(string NodeId, string Address) : TMLMessage;

/// <summary>
/// Message to leave the cluster
/// </summary>
public sealed record LeaveCluster(string NodeId, string Reason) : TMLMessage;

/// <summary>
/// Message to get cluster status
/// </summary>
public sealed record GetClusterStatus() : TMLMessage;

/// <summary>
/// Response message for cluster status
/// </summary>
public sealed record ClusterStatusResponse(
    IReadOnlyList<string> ActiveNodes,
    string LeaderNode,
    Dictionary<string, object> ClusterMetrics) : TMLMessage;
