using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using TML.Core.Domain;
using TML.Storage.Data;

namespace TML.Storage.Repositories;

/// <summary>
/// PostgreSQL implementation of transaction repository
/// </summary>
public class TransactionRepository : ITransactionRepository
{
    private readonly TMLDbContext _context;
    private readonly ILogger<TransactionRepository> _logger;

    public TransactionRepository(TMLDbContext context, ILogger<TransactionRepository> logger)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<Transaction> CreateAsync(Transaction transaction, CancellationToken cancellationToken = default)
    {
        try
        {
            _context.Transactions.Add(transaction);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Created transaction {TransactionId}", transaction.Id);
            return transaction;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create transaction {TransactionId}", transaction.Id);
            throw;
        }
    }

    public async Task<Transaction> UpdateAsync(Transaction transaction, CancellationToken cancellationToken = default)
    {
        try
        {
            _context.Transactions.Update(transaction);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Updated transaction {TransactionId}", transaction.Id);
            return transaction;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to update transaction {TransactionId}", transaction.Id);
            throw;
        }
    }

    public async Task<Transaction?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        try
        {
            var transaction = await _context.Transactions
                .FirstOrDefaultAsync(t => t.Id == id, cancellationToken);
            
            _logger.LogDebug("Retrieved transaction {TransactionId}: {Found}", 
                id, transaction != null ? "Found" : "Not Found");
            
            return transaction;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transaction {TransactionId}", id);
            throw;
        }
    }

    public async Task<IReadOnlyList<Transaction>> GetByStatusAsync(TransactionStatus status, int limit = 100, CancellationToken cancellationToken = default)
    {
        try
        {
            var transactions = await _context.Transactions
                .Where(t => t.Status == status)
                .OrderBy(t => t.CreatedAt)
                .Take(limit)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} transactions with status {Status}", 
                transactions.Count, status);
            
            return transactions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transactions by status {Status}", status);
            throw;
        }
    }

    public async Task<IReadOnlyList<Transaction>> GetInSpatialAreaAsync(double minX, double minY, double maxX, double maxY, CancellationToken cancellationToken = default)
    {
        try
        {
            // Use raw SQL query for JSONB property filtering
            var sql = @"
                SELECT * FROM ""Transactions""
                WHERE (""Data""->>'XCoord')::float >= {0}
                  AND (""Data""->>'XCoord')::float <= {1}
                  AND (""Data""->>'YCoord')::float >= {2}
                  AND (""Data""->>'YCoord')::float <= {3}
                ORDER BY ""CreatedAt""";
            
            var transactions = await _context.Transactions
                .FromSqlRaw(sql, minX, maxX, minY, maxY)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} transactions in spatial area ({MinX},{MinY}) to ({MaxX},{MaxY})", 
                transactions.Count, minX, minY, maxX, maxY);
            
            return transactions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transactions in spatial area ({MinX},{MinY}) to ({MaxX},{MaxY})", 
                minX, minY, maxX, maxY);
            throw;
        }
    }

    public async Task<IReadOnlyList<Transaction>> GetBySourceAsync(string source, int limit = 100, CancellationToken cancellationToken = default)
    {
        try
        {
            var transactions = await _context.Transactions
                .Where(t => t.Source == source)
                .OrderByDescending(t => t.CreatedAt)
                .Take(limit)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} transactions from source {Source}", 
                transactions.Count, source);
            
            return transactions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transactions by source {Source}", source);
            throw;
        }
    }

    public async Task<IReadOnlyList<Transaction>> GetByTimeRangeAsync(DateTimeOffset from, DateTimeOffset to, CancellationToken cancellationToken = default)
    {
        try
        {
            var transactions = await _context.Transactions
                .Where(t => t.CreatedAt >= from && t.CreatedAt <= to)
                .OrderBy(t => t.CreatedAt)
                .ToListAsync(cancellationToken);
            
            _logger.LogDebug("Retrieved {Count} transactions from {From} to {To}", 
                transactions.Count, from, to);
            
            return transactions;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transactions by time range {From} to {To}", from, to);
            throw;
        }
    }

    public async Task<TransactionStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var stats = await _context.Transactions
                .GroupBy(t => 1)
                .Select(g => new TransactionStatistics
                {
                    TotalCount = g.Count(),
                    PendingCount = g.Count(t => t.Status == TransactionStatus.Pending),
                    ProcessingCount = g.Count(t => t.Status == TransactionStatus.Processing),
                    CompletedCount = g.Count(t => t.Status == TransactionStatus.Completed),
                    FailedCount = g.Count(t => t.Status == TransactionStatus.Failed),
                    CancelledCount = g.Count(t => t.Status == TransactionStatus.Cancelled),
                    AverageProcessingTimeMs = g.Where(t => t.ProcessingTimeMs.HasValue)
                                               .Average(t => t.ProcessingTimeMs) ?? 0,
                    OldestTransaction = g.Min(t => t.CreatedAt),
                    NewestTransaction = g.Max(t => t.CreatedAt)
                })
                .FirstOrDefaultAsync(cancellationToken);
            
            var result = stats ?? new TransactionStatistics();
            
            _logger.LogDebug("Retrieved transaction statistics: Total={Total}, Completed={Completed}, Failed={Failed}", 
                result.TotalCount, result.CompletedCount, result.FailedCount);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get transaction statistics");
            throw;
        }
    }

    public async Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default)
    {
        try
        {
            var transaction = await _context.Transactions
                .FirstOrDefaultAsync(t => t.Id == id, cancellationToken);
            
            if (transaction == null)
            {
                _logger.LogWarning("Transaction {TransactionId} not found for deletion", id);
                return false;
            }
            
            _context.Transactions.Remove(transaction);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Deleted transaction {TransactionId}", id);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete transaction {TransactionId}", id);
            throw;
        }
    }

    public async Task<IReadOnlyList<Transaction>> CreateBatchAsync(IEnumerable<Transaction> transactions, CancellationToken cancellationToken = default)
    {
        try
        {
            var transactionList = transactions.ToList();
            
            _context.Transactions.AddRange(transactionList);
            await _context.SaveChangesAsync(cancellationToken);
            
            _logger.LogDebug("Created batch of {Count} transactions", transactionList.Count);
            return transactionList;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create batch of {Count} transactions", transactions.Count());
            throw;
        }
    }
}
