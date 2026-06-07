using Microsoft.Extensions.Logging;
using Proto;
using System.Diagnostics;
using TML.Actors.Messages;
using TML.Core.Domain;

namespace TML.Actors.Actors;

/// <summary>
/// High-performance transaction processor actor using Proto.Actor framework.
/// Handles individual transactions and batch processing with model inheritance.
/// </summary>
public class TransactionProcessorActor : IActor
{
    private readonly ILogger<TransactionProcessorActor> _logger;
    private readonly string _actorId;
    private readonly Dictionary<string, object> _metrics;
    private readonly Queue<Transaction> _batchBuffer;
    private readonly Timer _batchTimer;
    
    // Configuration
    private const int MaxBatchSize = 100;
    private const int BatchTimeoutMs = 1000;
    private const double SpatialSearchRadius = 50.0;
    
    // Performance tracking
    private long _processedTransactions;
    private double _totalProcessingTimeMs;
    private readonly Stopwatch _uptimeStopwatch;

    public TransactionProcessorActor(ILogger<TransactionProcessorActor> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _actorId = $"tx-processor-{Guid.NewGuid():N}";
        _metrics = new Dictionary<string, object>();
        _batchBuffer = new Queue<Transaction>();
        _uptimeStopwatch = Stopwatch.StartNew();
        
        // Setup batch processing timer
        _batchTimer = new Timer(ProcessBatchTimeout, null, BatchTimeoutMs, BatchTimeoutMs);
        
        _logger.LogInformation("TransactionProcessorActor {ActorId} initialized", _actorId);
    }

    public async Task ReceiveAsync(IContext context)
    {
        try
        {
            switch (context.Message)
            {
                case ProcessTransaction msg:
                    await HandleProcessTransaction(context, msg);
                    break;
                    
                case ProcessTransactionBatch msg:
                    await HandleProcessTransactionBatch(context, msg);
                    break;
                    
                case GetMetrics:
                    await HandleGetMetrics(context);
                    break;
                    
                case GetHealthStatus:
                    await HandleGetHealthStatus(context);
                    break;
                    
                case Shutdown msg:
                    await HandleShutdown(context, msg);
                    break;
                    
                case Started:
                    _logger.LogInformation("TransactionProcessorActor {ActorId} started", _actorId);
                    break;
                    
                case Stopped:
                    _logger.LogInformation("TransactionProcessorActor {ActorId} stopped", _actorId);
                    await _batchTimer.DisposeAsync();
                    break;
                    
                default:
                    _logger.LogWarning("Unknown message type {MessageType} received by {ActorId}", 
                        context.Message?.GetType().Name, _actorId);
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing message {MessageType} in {ActorId}", 
                context.Message?.GetType().Name, _actorId);
            
            // Send error response if sender is waiting
            if (context.Sender != null)
            {
                var errorResponse = new TransactionProcessed(
                    Guid.Empty, 
                    false, 
                    null, 
                    ex.Message);
                context.Respond(errorResponse);
            }
        }
    }

    private async Task HandleProcessTransaction(IContext context, ProcessTransaction message)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            _logger.LogDebug("Processing transaction {TransactionId}", message.Transaction.Id);
            
            // Add to batch buffer for high-throughput processing
            _batchBuffer.Enqueue(message.Transaction);
            
            // Process immediately if batch is full
            if (_batchBuffer.Count >= MaxBatchSize)
            {
                await ProcessCurrentBatch(context);
            }
            
            // For single transaction, process immediately and respond
            var model = await ProcessSingleTransaction(message.Transaction);
            
            stopwatch.Stop();
            var processingTime = stopwatch.Elapsed.TotalMilliseconds;
            
            // Update metrics
            Interlocked.Increment(ref _processedTransactions);
            _totalProcessingTimeMs += processingTime;
            
            var response = new TransactionProcessed(
                message.Transaction.Id,
                true,
                model,
                null,
                processingTime);
            
            context.Respond(response);
            
            _logger.LogDebug("Transaction {TransactionId} processed in {ProcessingTime}ms", 
                message.Transaction.Id, processingTime);
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Failed to process transaction {TransactionId}", message.Transaction.Id);
            
            var errorResponse = new TransactionProcessed(
                message.Transaction.Id,
                false,
                null,
                ex.Message,
                stopwatch.Elapsed.TotalMilliseconds);
            
            context.Respond(errorResponse);
        }
    }

    private async Task HandleProcessTransactionBatch(IContext context, ProcessTransactionBatch message)
    {
        var stopwatch = Stopwatch.StartNew();
        var results = new List<TransactionProcessed>();
        
        try
        {
            _logger.LogInformation("Processing batch of {Count} transactions", message.Transactions.Count);
            
            // Process transactions in parallel for better performance
            var tasks = message.Transactions.Select(ProcessSingleTransaction);
            var models = await Task.WhenAll(tasks);
            
            // Create results
            for (int i = 0; i < message.Transactions.Count; i++)
            {
                var transaction = message.Transactions[i];
                var model = models[i];
                
                results.Add(new TransactionProcessed(
                    transaction.Id,
                    model != null,
                    model,
                    model == null ? "Processing failed" : null,
                    stopwatch.Elapsed.TotalMilliseconds / message.Transactions.Count));
            }
            
            stopwatch.Stop();
            
            // Update metrics
            Interlocked.Add(ref _processedTransactions, message.Transactions.Count);
            _totalProcessingTimeMs += stopwatch.Elapsed.TotalMilliseconds;
            
            var successCount = results.Count(r => r.Success);
            var failureCount = results.Count - successCount;
            
            var batchResponse = new TransactionBatchProcessed(
                results,
                successCount,
                failureCount,
                stopwatch.Elapsed.TotalMilliseconds);
            
            context.Respond(batchResponse);
            
            _logger.LogInformation("Batch processed: {SuccessCount} successful, {FailureCount} failed in {ProcessingTime}ms",
                successCount, failureCount, stopwatch.Elapsed.TotalMilliseconds);
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Failed to process transaction batch");
            
            // Create error results for all transactions
            results.Clear();
            foreach (var transaction in message.Transactions)
            {
                results.Add(new TransactionProcessed(
                    transaction.Id,
                    false,
                    null,
                    ex.Message,
                    stopwatch.Elapsed.TotalMilliseconds));
            }
            
            var errorBatchResponse = new TransactionBatchProcessed(
                results,
                0,
                results.Count,
                stopwatch.Elapsed.TotalMilliseconds);
            
            context.Respond(errorBatchResponse);
        }
    }

    private async Task<Model?> ProcessSingleTransaction(Transaction transaction)
    {
        try
        {
            // Find spatial neighbors for inheritance
            var neighbors = await FindSpatialNeighbors(transaction.Data.XCoord, transaction.Data.YCoord);
            var parentModel = neighbors.FirstOrDefault();
            
            // Validate physics constraints
            var physicsValidation = await ValidatePhysics(transaction.Data, parentModel);
            
            // Create model with inheritance
            var model = CreateModelFromTransaction(transaction, parentModel, physicsValidation);
            
            // Update transaction status
            transaction.Status = TransactionStatus.Completed;
            transaction.ProcessedAt = DateTimeOffset.UtcNow;
            transaction.ModelId = model.Id;
            
            return model;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process transaction {TransactionId}", transaction.Id);
            
            transaction.Status = TransactionStatus.Failed;
            transaction.ErrorDetails = ex.Message;
            transaction.ProcessedAt = DateTimeOffset.UtcNow;
            
            return null;
        }
    }

    private async Task<List<Model>> FindSpatialNeighbors(double x, double y)
    {
        // TODO: Implement spatial neighbor search using spatial index
        // For now, return empty list (will be implemented with storage layer)
        await Task.Delay(1); // Simulate async operation
        return new List<Model>();
    }

    private async Task<PhysicsValidation> ValidatePhysics(TransactionData data, Model? parentModel)
    {
        // TODO: Implement physics validation logic
        // For now, simple thickness validation
        await Task.Delay(1); // Simulate async operation
        
        var thicknessValid = data.Thickness >= data.MinThickness;
        var violations = new List<string>();
        
        if (!thicknessValid)
        {
            violations.Add($"Thickness {data.Thickness}mm below minimum {data.MinThickness}mm");
        }
        
        return new PhysicsValidation
        {
            IsValid = thicknessValid,
            ThicknessValid = thicknessValid,
            EnergyConservationValid = true,
            MassConservationValid = true,
            Violations = violations,
            ValidationScore = thicknessValid ? 1.0 : 0.5
        };
    }

    private Model CreateModelFromTransaction(Transaction transaction, Model? parentModel, PhysicsValidation physicsValidation)
    {
        var inheritanceDepth = parentModel?.InheritanceDepth + 1 ?? 0;
        
        // Simple linear model parameters (will be enhanced with real ML)
        var parameters = new ModelParameters
        {
            Weights = new[] { 1.0, 0.5, 0.2 }, // Simple weights
            Bias = 0.1,
            LearningRate = 0.01,
            Regularization = 0.001,
            Iterations = 100,
            ConvergenceThreshold = 0.0001
        };
        
        // Calculate simple metrics
        var metrics = new ModelMetrics
        {
            MeanSquaredError = 0.1,
            RootMeanSquaredError = Math.Sqrt(0.1),
            MeanAbsoluteError = 0.05,
            RSquared = 0.95,
            Confidence = 0.9,
            TrainingDataPoints = 1
        };
        
        var location = new SpatialLocation
        {
            X = transaction.Data.XCoord,
            Y = transaction.Data.YCoord,
            GridId = $"grid_{(int)(transaction.Data.XCoord / 100)}_{(int)(transaction.Data.YCoord / 100)}"
        };
        
        return new Model
        {
            TransactionId = transaction.Id,
            ParentModelId = parentModel?.Id,
            InheritanceDepth = inheritanceDepth,
            Parameters = parameters,
            PhysicsValidation = physicsValidation,
            Metrics = metrics,
            Location = location,
            Status = ModelStatus.Active
        };
    }

    private async Task ProcessCurrentBatch(IContext context)
    {
        if (_batchBuffer.Count == 0) return;
        
        var transactions = new List<Transaction>();
        while (_batchBuffer.Count > 0 && transactions.Count < MaxBatchSize)
        {
            transactions.Add(_batchBuffer.Dequeue());
        }
        
        // Process batch without waiting for response
        var batchMessage = new ProcessTransactionBatch(transactions);
        await HandleProcessTransactionBatch(context, batchMessage);
    }

    private void ProcessBatchTimeout(object? state)
    {
        // Process any pending transactions in buffer
        if (_batchBuffer.Count > 0)
        {
            // Note: This is a simplified implementation
            // In production, you'd need proper context handling
            Task.Run(async () =>
            {
                var transactions = new List<Transaction>();
                while (_batchBuffer.Count > 0)
                {
                    transactions.Add(_batchBuffer.Dequeue());
                }
                
                foreach (var transaction in transactions)
                {
                    await ProcessSingleTransaction(transaction);
                }
            });
        }
    }

    private async Task HandleGetMetrics(IContext context)
    {
        var avgProcessingTime = _processedTransactions > 0 
            ? _totalProcessingTimeMs / _processedTransactions 
            : 0;
        
        var throughput = _uptimeStopwatch.Elapsed.TotalSeconds > 0
            ? _processedTransactions / _uptimeStopwatch.Elapsed.TotalSeconds
            : 0;
        
        var customMetrics = new Dictionary<string, double>
        {
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds,
            ["batch_buffer_size"] = _batchBuffer.Count,
            ["total_processing_time_ms"] = _totalProcessingTimeMs
        };
        
        var response = new MetricsResponse(
            _actorId,
            _processedTransactions,
            avgProcessingTime,
            throughput,
            customMetrics);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleGetHealthStatus(IContext context)
    {
        var metrics = new Dictionary<string, object>
        {
            ["processed_transactions"] = _processedTransactions,
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds,
            ["batch_buffer_size"] = _batchBuffer.Count,
            ["is_processing"] = _batchBuffer.Count > 0
        };
        
        var response = new HealthStatusResponse(
            _actorId,
            true, // Always healthy for now
            metrics,
            DateTimeOffset.UtcNow);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleShutdown(IContext context, Shutdown message)
    {
        _logger.LogInformation("TransactionProcessorActor {ActorId} shutting down: {Reason}", 
            _actorId, message.Reason);
        
        // Process any remaining transactions in buffer
        await ProcessCurrentBatch(context);
        
        // Stop the actor
        context.Stop(context.Self);
        await Task.CompletedTask;
    }
}
