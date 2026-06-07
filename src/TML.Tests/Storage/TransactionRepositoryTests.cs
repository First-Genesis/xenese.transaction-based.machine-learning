using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Moq;
using TML.Core.Domain;
using TML.Storage.Data;
using TML.Storage.Repositories;
using Xunit;

namespace TML.Tests.Storage;

public class TransactionRepositoryTests : IDisposable
{
    private readonly TMLDbContext _context;
    private readonly TransactionRepository _repository;
    private readonly Mock<ILogger<TransactionRepository>> _mockLogger;

    public TransactionRepositoryTests()
    {
        var options = new DbContextOptionsBuilder<TMLDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new TMLDbContext(options);
        _mockLogger = new Mock<ILogger<TransactionRepository>>();
        _repository = new TransactionRepository(_context, _mockLogger.Object);
    }

    [Fact]
    public async Task CreateAsync_ValidTransaction_ShouldCreateSuccessfully()
    {
        // Arrange
        var transaction = CreateValidTransaction();

        // Act
        var result = await _repository.CreateAsync(transaction);

        // Assert
        result.Should().NotBeNull();
        result.Id.Should().Be(transaction.Id);
        
        var savedTransaction = await _context.Transactions.FindAsync(transaction.Id);
        savedTransaction.Should().NotBeNull();
        savedTransaction!.Source.Should().Be("unit-test");
    }

    [Fact]
    public async Task GetByIdAsync_ExistingTransaction_ShouldReturnTransaction()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        await _repository.CreateAsync(transaction);

        // Act
        var result = await _repository.GetByIdAsync(transaction.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(transaction.Id);
        result.Data.XCoord.Should().Be(100.5);
        result.Data.YCoord.Should().Be(200.3);
    }

    [Fact]
    public async Task GetByIdAsync_NonExistentTransaction_ShouldReturnNull()
    {
        // Arrange
        var nonExistentId = Guid.NewGuid();

        // Act
        var result = await _repository.GetByIdAsync(nonExistentId);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task UpdateAsync_ExistingTransaction_ShouldUpdateSuccessfully()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        await _repository.CreateAsync(transaction);
        
        transaction.Status = TransactionStatus.Completed;
        transaction.ProcessedAt = DateTimeOffset.UtcNow;
        transaction.ProcessingTimeMs = 150.5;

        // Act
        var result = await _repository.UpdateAsync(transaction);

        // Assert
        result.Should().NotBeNull();
        result.Status.Should().Be(TransactionStatus.Completed);
        result.ProcessedAt.Should().NotBeNull();
        result.ProcessingTimeMs.Should().Be(150.5);
    }

    [Fact]
    public async Task GetByStatusAsync_FiltersByStatus_ShouldReturnCorrectTransactions()
    {
        // Arrange
        var pendingTransaction = CreateValidTransaction();
        var completedTransaction = CreateValidTransaction();
        completedTransaction.Status = TransactionStatus.Completed;

        await _repository.CreateAsync(pendingTransaction);
        await _repository.CreateAsync(completedTransaction);

        // Act
        var pendingResults = await _repository.GetByStatusAsync(TransactionStatus.Pending);
        var completedResults = await _repository.GetByStatusAsync(TransactionStatus.Completed);

        // Assert
        pendingResults.Should().HaveCount(1);
        pendingResults.First().Status.Should().Be(TransactionStatus.Pending);
        
        completedResults.Should().HaveCount(1);
        completedResults.First().Status.Should().Be(TransactionStatus.Completed);
    }

    [Fact]
    public async Task GetByTimeRangeAsync_FiltersByDateRange_ShouldReturnCorrectTransactions()
    {
        // Arrange
        var now = DateTimeOffset.UtcNow;
        var oldTransaction = CreateValidTransaction();
        oldTransaction.CreatedAt = now.AddDays(-2);
        
        var recentTransaction = CreateValidTransaction();
        recentTransaction.CreatedAt = now.AddHours(-1);

        await _repository.CreateAsync(oldTransaction);
        await _repository.CreateAsync(recentTransaction);

        // Act
        var results = await _repository.GetByTimeRangeAsync(
            now.AddDays(-1), 
            now.AddHours(1));

        // Assert
        results.Should().HaveCount(1);
        results.First().Id.Should().Be(recentTransaction.Id);
    }

    [Fact]
    public async Task CreateBatchAsync_MultipleTransactions_ShouldCreateAllSuccessfully()
    {
        // Arrange
        var transactions = new List<Transaction>
        {
            CreateValidTransaction(),
            CreateValidTransaction(),
            CreateValidTransaction()
        };

        // Act
        var results = await _repository.CreateBatchAsync(transactions);

        // Assert
        results.Should().HaveCount(3);
        
        var savedCount = await _context.Transactions.CountAsync();
        savedCount.Should().Be(3);
    }

    [Fact]
    public async Task GetStatisticsAsync_WithData_ShouldReturnCorrectStatistics()
    {
        // Arrange
        var transactions = new List<Transaction>
        {
            CreateValidTransaction(), // Pending
            CreateValidTransaction(), // Pending
            CreateValidTransaction()  // Will be set to Completed
        };
        
        transactions[2].Status = TransactionStatus.Completed;
        transactions[2].ProcessingTimeMs = 100.0;

        foreach (var transaction in transactions)
        {
            await _repository.CreateAsync(transaction);
        }

        // Act
        var stats = await _repository.GetStatisticsAsync();

        // Assert
        stats.Should().NotBeNull();
        stats.TotalCount.Should().Be(3);
        stats.PendingCount.Should().Be(2);
        stats.CompletedCount.Should().Be(1);
        stats.FailedCount.Should().Be(0);
        stats.AverageProcessingTimeMs.Should().BeGreaterThan(0);
    }

    [Theory]
    [InlineData(50.0, 50.0, 100.0, 1)] // Should find transaction at (100.5, 200.3)
    [InlineData(200.0, 300.0, 50.0, 0)] // Should not find any transactions
    public async Task GetBySpatialRangeAsync_WithinRange_ShouldReturnCorrectCount(
        double centerX, double centerY, double radius, int expectedCount)
    {
        // Arrange
        var transaction = CreateValidTransaction(); // At (100.5, 200.3)
        await _repository.CreateAsync(transaction);

        // Act
        var results = await _repository.GetBySpatialRangeAsync(centerX, centerY, radius);

        // Assert
        results.Should().HaveCount(expectedCount);
    }

    [Fact]
    public async Task DeleteAsync_ExistingTransaction_ShouldDeleteSuccessfully()
    {
        // Arrange
        var transaction = CreateValidTransaction();
        await _repository.CreateAsync(transaction);

        // Act
        var result = await _repository.DeleteAsync(transaction.Id);

        // Assert
        result.Should().BeTrue();
        
        var deletedTransaction = await _context.Transactions.FindAsync(transaction.Id);
        deletedTransaction.Should().BeNull();
    }

    [Fact]
    public async Task DeleteAsync_NonExistentTransaction_ShouldReturnFalse()
    {
        // Arrange
        var nonExistentId = Guid.NewGuid();

        // Act
        var result = await _repository.DeleteAsync(nonExistentId);

        // Assert
        result.Should().BeFalse();
    }

    private Transaction CreateValidTransaction()
    {
        return new Transaction
        {
            Id = Guid.NewGuid(),
            Data = new TransactionData
            {
                XCoord = 100.5,
                YCoord = 200.3,
                Thickness = 25.7,
                MinThickness = 15.0,
                Features = new Dictionary<string, double>
                {
                    ["temperature"] = 22.5,
                    ["pressure"] = 101.3
                },
                Quality = 0.95
            },
            Source = "unit-test",
            Metadata = new Dictionary<string, object>
            {
                ["test_run"] = true,
                ["batch_id"] = Guid.NewGuid().ToString()
            },
            Status = TransactionStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow
        };
    }

    public void Dispose()
    {
        _context.Dispose();
    }
}
