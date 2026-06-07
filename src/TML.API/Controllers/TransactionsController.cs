using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using TML.Core.Domain;
using TML.Storage.Repositories;
using TML.Actors.Services;
using TML.Actors.Messages;
using Proto;

namespace TML.API.Controllers;

/// <summary>
/// API controller for transaction processing
/// </summary>
[ApiController]
[Route("api/[controller]")]
// [Authorize] // Temporarily disabled for testing
public class TransactionsController : ControllerBase
{
    private readonly ITransactionRepository _transactionRepository;
    private readonly ActorSystemService _actorSystem;
    private readonly ILogger<TransactionsController> _logger;

    public TransactionsController(
        ITransactionRepository transactionRepository,
        ActorSystemService actorSystem,
        ILogger<TransactionsController> logger)
    {
        _transactionRepository = transactionRepository ?? throw new ArgumentNullException(nameof(transactionRepository));
        _actorSystem = actorSystem ?? throw new ArgumentNullException(nameof(actorSystem));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Get all transactions with optional filtering
    /// </summary>
    [HttpGet]
    [ProducesResponseType(typeof(IEnumerable<TransactionDetails>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<ActionResult<IEnumerable<TransactionDetails>>> GetTransactions(
        [FromQuery] int? limit = 100,
        [FromQuery] int? offset = 0,
        [FromQuery] string? status = null)
    {
        try
        {
            IEnumerable<Transaction> transactions;
            
            // Get transactions based on status filter
            if (!string.IsNullOrEmpty(status) && Enum.TryParse<TransactionStatus>(status, out var statusEnum))
            {
                transactions = await _transactionRepository.GetByStatusAsync(statusEnum, limit ?? 100);
            }
            else
            {
                // Get recent transactions
                var to = DateTimeOffset.UtcNow;
                var from = to.AddDays(-30); // Last 30 days
                transactions = await _transactionRepository.GetByTimeRangeAsync(from, to);
            }
            
            // Apply pagination
            transactions = transactions
                .OrderByDescending(t => t.CreatedAt)
                .Skip(offset ?? 0)
                .Take(Math.Min(limit ?? 100, 1000));
            
            var result = transactions.Select(t => new TransactionDetails
            {
                Id = t.Id,
                Data = t.Data,
                Source = t.Source,
                Metadata = t.Metadata,
                Status = t.Status.ToString(),
                CreatedAt = t.CreatedAt,
                ProcessedAt = t.ProcessedAt,
                ProcessingTimeMs = t.ProcessingTimeMs,
                ModelId = t.ModelId,
                ErrorDetails = t.ErrorDetails
            }).ToList();
            
            return result.Any() ? Ok(result) : NoContent();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving transactions");
            return StatusCode(500, "Internal server error");
        }
    }
    
    /// <summary>
    /// Get transaction statistics
    /// </summary>
    [HttpGet("statistics")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    public async Task<ActionResult> GetStatistics()
    {
        try
        {
            var stats = await _transactionRepository.GetStatisticsAsync();
            
            // Get recent transactions for additional info
            var recentTransactions = await _transactionRepository.GetByTimeRangeAsync(
                DateTimeOffset.UtcNow.AddHours(-24), 
                DateTimeOffset.UtcNow);
            
            var enrichedStats = new
            {
                stats.TotalCount,
                stats.AverageProcessingTimeMs,
                RecentTransactions = recentTransactions
                    .OrderByDescending(t => t.CreatedAt)
                    .Take(10)
                    .Select(t => new
                    {
                        t.Id,
                        Status = t.Status.ToString(),
                        t.CreatedAt,
                        t.ProcessingTimeMs
                    }),
                HourlyTrend = recentTransactions
                    .GroupBy(t => t.CreatedAt.Hour)
                    .OrderBy(g => g.Key)
                    .Select(g => new
                    {
                        Hour = g.Key,
                        Count = g.Count()
                    })
            };
            
            return Ok(enrichedStats);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calculating statistics");
            return StatusCode(500, "Internal server error");
        }
    }
    
    /// <summary>
    /// Process a single transaction through the TML platform
    /// </summary>
    [HttpPost]
    [ProducesResponseType(typeof(TransactionResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<TransactionResponse>> ProcessTransaction([FromBody] TransactionRequest request)
    {
        try
        {
            // Validate request
            if (request?.Data == null)
                return BadRequest("Transaction data is required");

            // Create transaction entity
            var transaction = new Transaction
            {
                Id = Guid.NewGuid(),
                Data = new TransactionData
                {
                    XCoord = request.Data.XCoord,
                    YCoord = request.Data.YCoord,
                    Thickness = request.Data.Thickness,
                    MinThickness = request.Data.MinThickness,
                    Features = request.Data.Features ?? new Dictionary<string, double>(),
                    Quality = request.Data.Quality
                },
                Source = request.Source ?? "api",
                Metadata = request.Metadata ?? new Dictionary<string, object>(),
                Status = TransactionStatus.Pending
            };

            // Save to database
            transaction = await _transactionRepository.CreateAsync(transaction);

            // Get actor reference
            var processor = _actorSystem.GetTransactionProcessor();
            if (processor == null)
            {
                _logger.LogError("No transaction processor available");
                return StatusCode(503, "Service temporarily unavailable");
            }

            // Send to Proto.Actor for processing
            var actorMessage = new ProcessTransaction(transaction);
            var response = await _actorSystem.Root.RequestAsync<TransactionProcessed>(
                processor, 
                actorMessage, 
                TimeSpan.FromSeconds(30));

            // Update transaction status
            transaction.Status = response.Success ? TransactionStatus.Completed : TransactionStatus.Failed;
            transaction.ProcessedAt = DateTimeOffset.UtcNow;
            transaction.ProcessingTimeMs = response.ProcessingTimeMs;
            transaction.ModelId = response.Model?.Id;
            transaction.ErrorDetails = response.ErrorMessage;

            await _transactionRepository.UpdateAsync(transaction);

            return Ok(new TransactionResponse
            {
                TransactionId = transaction.Id,
                Status = transaction.Status.ToString(),
                ModelId = response.Model?.Id,
                ProcessingTimeMs = response.ProcessingTimeMs,
                PhysicsValid = response.Model?.PhysicsValidation.IsValid ?? false,
                InheritanceDepth = response.Model?.InheritanceDepth ?? 0,
                Confidence = response.Model?.Metrics.Confidence ?? 0
            });
        }
        catch (TimeoutException)
        {
            _logger.LogError("Transaction processing timeout");
            return StatusCode(504, "Processing timeout");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing transaction");
            return StatusCode(500, "Internal server error");
        }
    }

    /// <summary>
    /// Process multiple transactions in batch
    /// </summary>
    [HttpPost("batch")]
    [ProducesResponseType(typeof(BatchTransactionResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<BatchTransactionResponse>> ProcessBatch([FromBody] BatchTransactionRequest request)
    {
        try
        {
            if (request?.Transactions == null || !request.Transactions.Any())
                return BadRequest("Transactions are required");

            if (request.Transactions.Count > 1000)
                return BadRequest("Maximum batch size is 1000 transactions");

            // Create transaction entities
            var transactions = request.Transactions.Select(t => new Transaction
            {
                Id = Guid.NewGuid(),
                Data = new TransactionData
                {
                    XCoord = t.Data.XCoord,
                    YCoord = t.Data.YCoord,
                    Thickness = t.Data.Thickness,
                    MinThickness = t.Data.MinThickness,
                    Features = t.Data.Features ?? new Dictionary<string, double>(),
                    Quality = t.Data.Quality
                },
                Source = t.Source ?? "api-batch",
                Metadata = t.Metadata ?? new Dictionary<string, object>(),
                Status = TransactionStatus.Pending
            }).ToList();

            // Save to database
            transactions = (await _transactionRepository.CreateBatchAsync(transactions)).ToList();

            // Get actor reference
            var processor = _actorSystem.GetTransactionProcessor();
            if (processor == null)
            {
                _logger.LogError("No transaction processor available");
                return StatusCode(503, "Service temporarily unavailable");
            }

            // Send batch to Proto.Actor
            var actorMessage = new ProcessTransactionBatch(transactions);
            var response = await _actorSystem.Root.RequestAsync<TransactionBatchProcessed>(
                processor, 
                actorMessage, 
                TimeSpan.FromMinutes(5));

            // Update transaction statuses
            for (int i = 0; i < transactions.Count; i++)
            {
                var transaction = transactions[i];
                var result = response.Results.ElementAtOrDefault(i);
                
                if (result != null)
                {
                    transaction.Status = result.Success ? TransactionStatus.Completed : TransactionStatus.Failed;
                    transaction.ProcessedAt = DateTimeOffset.UtcNow;
                    transaction.ProcessingTimeMs = result.ProcessingTimeMs;
                    transaction.ModelId = result.Model?.Id;
                    transaction.ErrorDetails = result.ErrorMessage;
                    
                    await _transactionRepository.UpdateAsync(transaction);
                }
            }

            return Ok(new BatchTransactionResponse
            {
                TotalCount = response.Results.Count,
                SuccessCount = response.SuccessCount,
                FailureCount = response.FailureCount,
                TotalProcessingTimeMs = response.TotalProcessingTimeMs,
                Results = response.Results.Select(r => new TransactionResponse
                {
                    TransactionId = r.TransactionId,
                    Status = r.Success ? "Completed" : "Failed",
                    ModelId = r.Model?.Id,
                    ProcessingTimeMs = r.ProcessingTimeMs,
                    PhysicsValid = r.Model?.PhysicsValidation.IsValid ?? false,
                    InheritanceDepth = r.Model?.InheritanceDepth ?? 0,
                    Confidence = r.Model?.Metrics.Confidence ?? 0
                }).ToList()
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing batch");
            return StatusCode(500, "Internal server error");
        }
    }

    /// <summary>
    /// Get transaction by ID
    /// </summary>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(TransactionDetails), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<TransactionDetails>> GetTransaction(Guid id)
    {
        var transaction = await _transactionRepository.GetByIdAsync(id);
        if (transaction == null)
            return NotFound();

        return Ok(new TransactionDetails
        {
            Id = transaction.Id,
            Data = transaction.Data,
            Source = transaction.Source,
            Metadata = transaction.Metadata,
            Status = transaction.Status.ToString(),
            CreatedAt = transaction.CreatedAt,
            ProcessedAt = transaction.ProcessedAt,
            ProcessingTimeMs = transaction.ProcessingTimeMs,
            ModelId = transaction.ModelId,
            ErrorDetails = transaction.ErrorDetails
        });
    }

}

// Request/Response DTOs

public class TransactionRequest
{
    public TransactionDataDto Data { get; set; } = null!;
    public string? Source { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
}

public class TransactionDataDto
{
    public double XCoord { get; set; }
    public double YCoord { get; set; }
    public double Thickness { get; set; }
    public double MinThickness { get; set; } = 15.0;
    public Dictionary<string, double>? Features { get; set; }
    public double Quality { get; set; } = 1.0;
}

public class TransactionResponse
{
    public Guid TransactionId { get; set; }
    public string Status { get; set; } = string.Empty;
    public Guid? ModelId { get; set; }
    public double ProcessingTimeMs { get; set; }
    public bool PhysicsValid { get; set; }
    public int InheritanceDepth { get; set; }
    public double Confidence { get; set; }
}

public class BatchTransactionRequest
{
    public List<TransactionRequest> Transactions { get; set; } = new();
}

public class BatchTransactionResponse
{
    public int TotalCount { get; set; }
    public int SuccessCount { get; set; }
    public int FailureCount { get; set; }
    public double TotalProcessingTimeMs { get; set; }
    public List<TransactionResponse> Results { get; set; } = new();
}

public class TransactionDetails
{
    public Guid Id { get; set; }
    public TransactionData Data { get; set; } = null!;
    public string Source { get; set; } = string.Empty;
    public Dictionary<string, object> Metadata { get; set; } = new();
    public string Status { get; set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? ProcessedAt { get; set; }
    public double? ProcessingTimeMs { get; set; }
    public Guid? ModelId { get; set; }
    public string? ErrorDetails { get; set; }
}
