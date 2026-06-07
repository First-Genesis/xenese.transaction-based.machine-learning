using Amazon;
using Amazon.S3;
using Amazon.S3.Model;
using Microsoft.Extensions.Options;
using Microsoft.Extensions.Logging;

namespace TML.Storage.Services;

/// <summary>
/// Factory for creating S3 clients with MinIO support
/// </summary>
public class S3ClientFactory : IS3ClientFactory
{
    private readonly S3Configuration _configuration;
    private readonly ILogger<S3ClientFactory> _logger;
    private IAmazonS3? _client;

    public S3ClientFactory(IOptions<S3Configuration> configuration, ILogger<S3ClientFactory> logger)
    {
        _configuration = configuration?.Value ?? throw new ArgumentNullException(nameof(configuration));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Create or get cached S3 client configured for MinIO or AWS S3
    /// </summary>
    public IAmazonS3 CreateClient()
    {
        if (_client != null)
            return _client;

        if (_configuration.UseMinIO)
        {
            _logger.LogInformation("Creating MinIO S3 client with endpoint: {ServiceUrl}", _configuration.ServiceUrl);
            
            var config = new AmazonS3Config
            {
                ServiceURL = _configuration.ServiceUrl,
                ForcePathStyle = _configuration.ForcePathStyle,
                SignatureVersion = "4",
                RegionEndpoint = RegionEndpoint.USEast1,
                UseHttp = !_configuration.ServiceUrl?.StartsWith("https") ?? true,
                Timeout = _configuration.RequestTimeout
            };

            _client = new AmazonS3Client(
                _configuration.AccessKey,
                _configuration.SecretKey,
                config
            );
        }
        else if (_configuration.UseLocalStack)
        {
            _logger.LogInformation("Creating LocalStack S3 client with endpoint: {ServiceUrl}", _configuration.ServiceUrl);
            
            var config = new AmazonS3Config
            {
                ServiceURL = _configuration.ServiceUrl ?? "http://localhost:4566",
                ForcePathStyle = true,
                AuthenticationRegion = _configuration.Region,
                UseHttp = true
            };

            _client = new AmazonS3Client(
                "test",
                "test",
                config
            );
        }
        else
        {
            _logger.LogInformation("Creating AWS S3 client for region: {Region}", _configuration.Region);
            
            var config = new AmazonS3Config
            {
                RegionEndpoint = RegionEndpoint.GetBySystemName(_configuration.Region),
                Timeout = _configuration.RequestTimeout
            };

            // Use AWS credentials from environment or IAM role
            _client = new AmazonS3Client(config);
        }

        return _client;
    }

    /// <summary>
    /// Ensure bucket exists (useful for MinIO/LocalStack)
    /// </summary>
    public async Task EnsureBucketExistsAsync(CancellationToken cancellationToken = default)
    {
        var client = CreateClient();
        
        try
        {
            // Check if bucket exists
            await client.GetBucketLocationAsync(_configuration.BucketName);
            _logger.LogDebug("Bucket {BucketName} already exists", _configuration.BucketName);
        }
        catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            // Create bucket if it doesn't exist (for MinIO/LocalStack)
            if (_configuration.UseMinIO || _configuration.UseLocalStack)
            {
                _logger.LogInformation("Creating bucket {BucketName}", _configuration.BucketName);
                
                await client.PutBucketAsync(new PutBucketRequest
                {
                    BucketName = _configuration.BucketName
                }, cancellationToken);
                
                // Enable versioning for the bucket
                await client.PutBucketVersioningAsync(new PutBucketVersioningRequest
                {
                    BucketName = _configuration.BucketName,
                    VersioningConfig = new S3BucketVersioningConfig
                    {
                        Status = VersionStatus.Enabled
                    }
                }, cancellationToken);
                
                _logger.LogInformation("Bucket {BucketName} created successfully", _configuration.BucketName);
            }
            else
            {
                throw;
            }
        }
    }

    public void Dispose()
    {
        _client?.Dispose();
    }
}

/// <summary>
/// Interface for S3 client factory
/// </summary>
public interface IS3ClientFactory : IDisposable
{
    IAmazonS3 CreateClient();
    Task EnsureBucketExistsAsync(CancellationToken cancellationToken = default);
}
