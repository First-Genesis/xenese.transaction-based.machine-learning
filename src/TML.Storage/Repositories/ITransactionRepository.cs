using TML.Core.Domain;

namespace TML.Storage.Repositories;

/// <summary>
/// Repository interface for Transaction data access
/// </summary>
public interface ITransactionRepository
{
    /// <summary>
    /// Create a new transaction
    /// </summary>
    Task<Transaction> CreateAsync(Transaction transaction, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Update an existing transaction
    /// </summary>
    Task<Transaction> UpdateAsync(Transaction transaction, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transaction by ID
    /// </summary>
    Task<Transaction?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transactions by status
    /// </summary>
    Task<IReadOnlyList<Transaction>> GetByStatusAsync(TransactionStatus status, int limit = 100, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transactions in spatial area
    /// </summary>
    Task<IReadOnlyList<Transaction>> GetInSpatialAreaAsync(double minX, double minY, double maxX, double maxY, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transactions by source
    /// </summary>
    Task<IReadOnlyList<Transaction>> GetBySourceAsync(string source, int limit = 100, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transactions created within time range
    /// </summary>
    Task<IReadOnlyList<Transaction>> GetByTimeRangeAsync(DateTimeOffset from, DateTimeOffset to, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get transaction statistics
    /// </summary>
    Task<TransactionStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Delete transaction by ID
    /// </summary>
    Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Batch create transactions
    /// </summary>
    Task<IReadOnlyList<Transaction>> CreateBatchAsync(IEnumerable<Transaction> transactions, CancellationToken cancellationToken = default);
}

/// <summary>
/// Transaction statistics
/// </summary>
public class TransactionStatistics
{
    public long TotalCount { get; set; }
    public long PendingCount { get; set; }
    public long ProcessingCount { get; set; }
    public long CompletedCount { get; set; }
    public long FailedCount { get; set; }
    public long CancelledCount { get; set; }
    public double AverageProcessingTimeMs { get; set; }
    public DateTimeOffset? OldestTransaction { get; set; }
    public DateTimeOffset? NewestTransaction { get; set; }
}
