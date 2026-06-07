using Amazon.S3;
using Amazon.S3.Model;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using System.IO.Compression;
using System.Text;
using System.Text.Json;

namespace TML.Storage.Services;

/// <summary>
/// S3 implementation for model artifact storage with compression and encryption
/// </summary>
public class S3ModelArtifactService : IS3ModelArtifactService
{
    private readonly IAmazonS3 _s3Client;
    private readonly ILogger<S3ModelArtifactService> _logger;
    private readonly S3Configuration _configuration;

    public S3ModelArtifactService(
        IAmazonS3 s3Client,
        ILogger<S3ModelArtifactService> logger,
        IOptions<S3Configuration> configuration)
    {
        _s3Client = s3Client ?? throw new ArgumentNullException(nameof(s3Client));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _configuration = configuration?.Value ?? throw new ArgumentNullException(nameof(configuration));
    }

    public async Task<string> StoreModelArtifactsAsync(Guid modelId, ModelArtifacts artifacts, CancellationToken cancellationToken = default)
    {
        return await StoreVersionedModelArtifactsAsync(modelId, 1, artifacts, cancellationToken);
    }

    public async Task<string> StoreVersionedModelArtifactsAsync(Guid modelId, int version, ModelArtifacts artifacts, CancellationToken cancellationToken = default)
    {
        try
        {
            var s3Key = GenerateS3Key(modelId, version);
            _logger.LogDebug("Storing model artifacts for {ModelId} version {Version} to {S3Key}", 
                modelId, version, s3Key);

            // Serialize and compress artifacts
            var artifactData = await SerializeAndCompressArtifacts(artifacts);

            // Prepare S3 request
            var request = new PutObjectRequest
            {
                BucketName = _configuration.BucketName,
                Key = s3Key,
                InputStream = new MemoryStream(artifactData),
                ContentType = "application/octet-stream",
                StorageClass = S3StorageClass.Standard,
                ServerSideEncryptionMethod = ServerSideEncryptionMethod.AES256
            };

            // Add metadata
            request.Metadata.Add("model-id", modelId.ToString());
            request.Metadata.Add("version", version.ToString());
            request.Metadata.Add("compression", artifacts.Compression.ToString());
            request.Metadata.Add("encrypted", artifacts.IsEncrypted.ToString());
            request.Metadata.Add("created-at", DateTimeOffset.UtcNow.ToString("O"));

            // Add tags
            request.TagSet = new List<Tag>
            {
                new() { Key = "ModelId", Value = modelId.ToString() },
                new() { Key = "Version", Value = version.ToString() },
                new() { Key = "Type", Value = "ModelArtifacts" },
                new() { Key = "Environment", Value = _configuration.Environment }
            };

            // Upload to S3
            var response = await _s3Client.PutObjectAsync(request, cancellationToken);
            
            var s3Location = $"s3://{_configuration.BucketName}/{s3Key}";
            
            _logger.LogInformation("Successfully stored model artifacts for {ModelId} version {Version} at {S3Location}, ETag: {ETag}", 
                modelId, version, s3Location, response.ETag);

            return s3Location;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to store model artifacts for {ModelId} version {Version}", 
                modelId, version);
            throw;
        }
    }

    public async Task<ModelArtifacts?> RetrieveModelArtifactsAsync(string s3Location, CancellationToken cancellationToken = default)
    {
        try
        {
            var (bucketName, key) = ParseS3Location(s3Location);
            
            _logger.LogDebug("Retrieving model artifacts from {S3Location}", s3Location);

            var request = new GetObjectRequest
            {
                BucketName = bucketName,
                Key = key
            };

            using var response = await _s3Client.GetObjectAsync(request, cancellationToken);
            using var memoryStream = new MemoryStream();
            
            await response.ResponseStream.CopyToAsync(memoryStream, cancellationToken);
            var artifactData = memoryStream.ToArray();

            // Extract compression type from metadata
            var compressionType = CompressionType.Gzip; // Default
            if (response.Metadata.Keys.Contains("x-amz-meta-compression"))
            {
                compressionType = Enum.Parse<CompressionType>(response.Metadata["x-amz-meta-compression"]);
            }

            // Decompress and deserialize
            var artifacts = await DecompressAndDeserializeArtifacts(artifactData, compressionType);

            _logger.LogDebug("Successfully retrieved model artifacts from {S3Location}, Size: {Size} bytes", 
                s3Location, artifactData.Length);

            return artifacts;
        }
        catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            _logger.LogWarning("Model artifacts not found at {S3Location}", s3Location);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to retrieve model artifacts from {S3Location}", s3Location);
            throw;
        }
    }

    public async Task<bool> DeleteModelArtifactsAsync(string s3Location, CancellationToken cancellationToken = default)
    {
        try
        {
            var (bucketName, key) = ParseS3Location(s3Location);
            
            _logger.LogDebug("Deleting model artifacts at {S3Location}", s3Location);

            var request = new DeleteObjectRequest
            {
                BucketName = bucketName,
                Key = key
            };

            await _s3Client.DeleteObjectAsync(request, cancellationToken);
            
            _logger.LogInformation("Successfully deleted model artifacts at {S3Location}", s3Location);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete model artifacts at {S3Location}", s3Location);
            return false;
        }
    }

    public async Task<bool> ExistsAsync(string s3Location, CancellationToken cancellationToken = default)
    {
        try
        {
            var (bucketName, key) = ParseS3Location(s3Location);

            var request = new GetObjectMetadataRequest
            {
                BucketName = bucketName,
                Key = key
            };

            await _s3Client.GetObjectMetadataAsync(request, cancellationToken);
            return true;
        }
        catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to check existence of model artifacts at {S3Location}", s3Location);
            throw;
        }
    }

    public async Task<string> GetDownloadUrlAsync(string s3Location, TimeSpan expiration, CancellationToken cancellationToken = default)
    {
        try
        {
            var (bucketName, key) = ParseS3Location(s3Location);

            var request = new GetPreSignedUrlRequest
            {
                BucketName = bucketName,
                Key = key,
                Verb = HttpVerb.GET,
                Expires = DateTime.UtcNow.Add(expiration)
            };

            var url = await _s3Client.GetPreSignedURLAsync(request);
            
            _logger.LogDebug("Generated pre-signed URL for {S3Location}, expires in {Expiration}", 
                s3Location, expiration);

            return url;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to generate download URL for {S3Location}", s3Location);
            throw;
        }
    }

    public async Task<IReadOnlyList<ModelArtifactVersion>> ListModelVersionsAsync(Guid modelId, CancellationToken cancellationToken = default)
    {
        try
        {
            var prefix = $"models/{modelId}/";
            var versions = new List<ModelArtifactVersion>();

            var request = new ListObjectsV2Request
            {
                BucketName = _configuration.BucketName,
                Prefix = prefix
            };

            ListObjectsV2Response response;
            do
            {
                response = await _s3Client.ListObjectsV2Async(request, cancellationToken);

                foreach (var obj in response.S3Objects)
                {
                    // Extract version from key
                    var keyParts = obj.Key.Split('/');
                    if (keyParts.Length >= 3 && keyParts[0] == "models" && 
                        Guid.TryParse(keyParts[1], out var parsedModelId) && parsedModelId == modelId &&
                        int.TryParse(keyParts[2].Replace(".artifacts", ""), out var version))
                    {
                        versions.Add(new ModelArtifactVersion
                        {
                            ModelId = modelId,
                            Version = version,
                            S3Location = $"s3://{_configuration.BucketName}/{obj.Key}",
                            SizeBytes = obj.Size,
                            CreatedAt = obj.LastModified,
                            StorageClass = obj.StorageClass?.Value ?? "STANDARD",
                            ETag = obj.ETag
                        });
                    }
                }

                request.ContinuationToken = response.NextContinuationToken;
            } while (response.IsTruncated);

            // Sort by version descending
            versions.Sort((a, b) => b.Version.CompareTo(a.Version));

            _logger.LogDebug("Listed {Count} versions for model {ModelId}", versions.Count, modelId);
            return versions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to list versions for model {ModelId}", modelId);
            throw;
        }
    }

    public async Task ArchiveOldVersionsAsync(Guid modelId, int keepLatestVersions = 5, CancellationToken cancellationToken = default)
    {
        try
        {
            var versions = await ListModelVersionsAsync(modelId, cancellationToken);
            var versionsToArchive = versions.Skip(keepLatestVersions).ToList();

            if (!versionsToArchive.Any())
            {
                _logger.LogDebug("No versions to archive for model {ModelId}", modelId);
                return;
            }

            var archiveTasks = versionsToArchive.Select(async version =>
            {
                try
                {
                    var (bucketName, key) = ParseS3Location(version.S3Location);
                    
                    var request = new CopyObjectRequest
                    {
                        SourceBucket = bucketName,
                        SourceKey = key,
                        DestinationBucket = bucketName,
                        DestinationKey = key,
                        StorageClass = S3StorageClass.Glacier,
                        MetadataDirective = S3MetadataDirective.COPY
                    };

                    await _s3Client.CopyObjectAsync(request, cancellationToken);
                    
                    _logger.LogDebug("Archived model version {ModelId} v{Version} to Glacier", 
                        modelId, version.Version);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to archive model version {ModelId} v{Version}", 
                        modelId, version.Version);
                }
            });

            await Task.WhenAll(archiveTasks);
            
            _logger.LogInformation("Archived {Count} old versions for model {ModelId}", 
                versionsToArchive.Count, modelId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to archive old versions for model {ModelId}", modelId);
            throw;
        }
    }

    private string GenerateS3Key(Guid modelId, int version)
    {
        return $"models/{modelId}/{version}.artifacts";
    }

    private (string bucketName, string key) ParseS3Location(string s3Location)
    {
        if (!s3Location.StartsWith("s3://"))
            throw new ArgumentException("Invalid S3 location format", nameof(s3Location));

        var parts = s3Location.Substring(5).Split('/', 2);
        if (parts.Length != 2)
            throw new ArgumentException("Invalid S3 location format", nameof(s3Location));

        return (parts[0], parts[1]);
    }

    private async Task<byte[]> SerializeAndCompressArtifacts(ModelArtifacts artifacts)
    {
        // Serialize to JSON
        var json = JsonSerializer.Serialize(artifacts, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        });
        
        var jsonBytes = Encoding.UTF8.GetBytes(json);

        // Compress based on compression type
        return artifacts.Compression switch
        {
            CompressionType.None => jsonBytes,
            CompressionType.Gzip => await CompressGzip(jsonBytes),
            CompressionType.Brotli => await CompressBrotli(jsonBytes),
            CompressionType.Lz4 => throw new NotImplementedException("LZ4 compression not implemented"),
            _ => await CompressGzip(jsonBytes)
        };
    }

    private async Task<ModelArtifacts> DecompressAndDeserializeArtifacts(byte[] data, CompressionType compressionType)
    {
        // Decompress based on compression type
        var jsonBytes = compressionType switch
        {
            CompressionType.None => data,
            CompressionType.Gzip => await DecompressGzip(data),
            CompressionType.Brotli => await DecompressBrotli(data),
            CompressionType.Lz4 => throw new NotImplementedException("LZ4 decompression not implemented"),
            _ => await DecompressGzip(data)
        };

        var json = Encoding.UTF8.GetString(jsonBytes);
        
        return JsonSerializer.Deserialize<ModelArtifacts>(json, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        }) ?? throw new InvalidOperationException("Failed to deserialize model artifacts");
    }

    private async Task<byte[]> CompressGzip(byte[] data)
    {
        using var output = new MemoryStream();
        using (var gzip = new GZipStream(output, CompressionLevel.Optimal))
        {
            await gzip.WriteAsync(data);
        }
        return output.ToArray();
    }

    private async Task<byte[]> DecompressGzip(byte[] data)
    {
        using var input = new MemoryStream(data);
        using var gzip = new GZipStream(input, CompressionMode.Decompress);
        using var output = new MemoryStream();
        
        await gzip.CopyToAsync(output);
        return output.ToArray();
    }

    private async Task<byte[]> CompressBrotli(byte[] data)
    {
        using var output = new MemoryStream();
        using (var brotli = new BrotliStream(output, CompressionLevel.Optimal))
        {
            await brotli.WriteAsync(data);
        }
        return output.ToArray();
    }

    private async Task<byte[]> DecompressBrotli(byte[] data)
    {
        using var input = new MemoryStream(data);
        using var brotli = new BrotliStream(input, CompressionMode.Decompress);
        using var output = new MemoryStream();
        
        await brotli.CopyToAsync(output);
        return output.ToArray();
    }
}

/// <summary>
/// S3 configuration settings with MinIO support
/// </summary>
public class S3Configuration
{
    public string BucketName { get; set; } = string.Empty;
    public string Region { get; set; } = "us-east-1";
    public string Environment { get; set; } = "development";
    
    // MinIO/LocalStack Support
    public bool UseMinIO { get; set; } = false;
    public bool UseLocalStack { get; set; } = false;
    public string? ServiceUrl { get; set; } // MinIO endpoint (e.g., "http://localhost:9000")
    public string? AccessKey { get; set; }
    public string? SecretKey { get; set; }
    public bool ForcePathStyle { get; set; } = true; // Required for MinIO
    
    // Offline Support
    public bool EnableOfflineMode { get; set; } = false;
    public string? LocalCachePath { get; set; } = "./cache/models";
    
    // Performance Settings
    public int MaxConcurrentUploads { get; set; } = 10;
    public int UploadPartSizeMB { get; set; } = 5;
    public TimeSpan RequestTimeout { get; set; } = TimeSpan.FromMinutes(5);
}
