using TML.Core.Domain;

namespace TML.Storage.Services;

/// <summary>
/// Interface for S3 model artifact storage service
/// </summary>
public interface IS3ModelArtifactService
{
    /// <summary>
    /// Store model artifacts in S3
    /// </summary>
    Task<string> StoreModelArtifactsAsync(Guid modelId, ModelArtifacts artifacts, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Retrieve model artifacts from S3
    /// </summary>
    Task<ModelArtifacts?> RetrieveModelArtifactsAsync(string s3Location, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Delete model artifacts from S3
    /// </summary>
    Task<bool> DeleteModelArtifactsAsync(string s3Location, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Check if model artifacts exist in S3
    /// </summary>
    Task<bool> ExistsAsync(string s3Location, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get pre-signed URL for model artifact download
    /// </summary>
    Task<string> GetDownloadUrlAsync(string s3Location, TimeSpan expiration, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Store model artifacts with versioning
    /// </summary>
    Task<string> StoreVersionedModelArtifactsAsync(Guid modelId, int version, ModelArtifacts artifacts, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// List all versions of model artifacts
    /// </summary>
    Task<IReadOnlyList<ModelArtifactVersion>> ListModelVersionsAsync(Guid modelId, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Archive old model versions (move to cheaper storage class)
    /// </summary>
    Task ArchiveOldVersionsAsync(Guid modelId, int keepLatestVersions = 5, CancellationToken cancellationToken = default);
}

/// <summary>
/// Model artifacts for storage
/// </summary>
public class ModelArtifacts
{
    /// <summary>
    /// Serialized model parameters
    /// </summary>
    public byte[] ModelData { get; set; } = Array.Empty<byte>();
    
    /// <summary>
    /// Model metadata (JSON)
    /// </summary>
    public string Metadata { get; set; } = string.Empty;
    
    /// <summary>
    /// Training history and metrics
    /// </summary>
    public byte[]? TrainingHistory { get; set; }
    
    /// <summary>
    /// Feature importance data
    /// </summary>
    public byte[]? FeatureImportance { get; set; }
    
    /// <summary>
    /// Model visualization plots
    /// </summary>
    public Dictionary<string, byte[]> Visualizations { get; set; } = new();
    
    /// <summary>
    /// Additional files (configs, logs, etc.)
    /// </summary>
    public Dictionary<string, byte[]> AdditionalFiles { get; set; } = new();
    
    /// <summary>
    /// Compression type used
    /// </summary>
    public CompressionType Compression { get; set; } = CompressionType.Gzip;
    
    /// <summary>
    /// Encryption status
    /// </summary>
    public bool IsEncrypted { get; set; } = true;
}

/// <summary>
/// Model artifact version information
/// </summary>
public class ModelArtifactVersion
{
    public Guid ModelId { get; set; }
    public int Version { get; set; }
    public string S3Location { get; set; } = string.Empty;
    public long SizeBytes { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public string StorageClass { get; set; } = "STANDARD";
    public string ETag { get; set; } = string.Empty;
    public Dictionary<string, string> Tags { get; set; } = new();
}

/// <summary>
/// Compression types for model artifacts
/// </summary>
public enum CompressionType
{
    None,
    Gzip,
    Brotli,
    Lz4
}
