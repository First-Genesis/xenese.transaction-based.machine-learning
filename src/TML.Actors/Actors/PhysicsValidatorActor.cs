using Microsoft.Extensions.Logging;
using Proto;
using System.Diagnostics;
using TML.Actors.Messages;
using TML.Core.Domain;

namespace TML.Actors.Actors;

/// <summary>
/// Physics validation actor responsible for validating physics constraints
/// and ensuring model predictions comply with physical laws.
/// </summary>
public class PhysicsValidatorActor : IActor
{
    private readonly ILogger<PhysicsValidatorActor> _logger;
    private readonly string _actorId;
    private readonly PhysicsRules _physicsRules;
    
    // Performance tracking
    private long _validationsPerformed;
    private long _validationsPassed;
    private long _validationsFailed;
    private double _totalValidationTimeMs;
    private readonly Stopwatch _uptimeStopwatch;

    public PhysicsValidatorActor(ILogger<PhysicsValidatorActor> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _actorId = $"physics-validator-{Guid.NewGuid():N}";
        _physicsRules = new PhysicsRules();
        _uptimeStopwatch = Stopwatch.StartNew();
        
        _logger.LogInformation("PhysicsValidatorActor {ActorId} initialized", _actorId);
    }

    public async Task ReceiveAsync(IContext context)
    {
        try
        {
            switch (context.Message)
            {
                case ValidatePhysics msg:
                    await HandleValidatePhysics(context, msg);
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
                    _logger.LogInformation("PhysicsValidatorActor {ActorId} started", _actorId);
                    break;
                    
                case Stopped:
                    _logger.LogInformation("PhysicsValidatorActor {ActorId} stopped", _actorId);
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
                var errorResponse = new PhysicsValidated(
                    new PhysicsValidation { IsValid = false, Violations = new List<string> { ex.Message } },
                    false,
                    new List<string> { ex.Message });
                context.Respond(errorResponse);
            }
        }
    }

    private async Task HandleValidatePhysics(IContext context, ValidatePhysics message)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            _logger.LogDebug("Validating physics for data at ({X}, {Y})", 
                message.Data.XCoord, message.Data.YCoord);
            
            var validation = await PerformPhysicsValidation(message.Data, message.ParentModel);
            
            stopwatch.Stop();
            var validationTime = stopwatch.Elapsed.TotalMilliseconds;
            
            // Update metrics
            Interlocked.Increment(ref _validationsPerformed);
            _totalValidationTimeMs += validationTime;
            
            if (validation.IsValid)
            {
                Interlocked.Increment(ref _validationsPassed);
            }
            else
            {
                Interlocked.Increment(ref _validationsFailed);
            }
            
            var response = new PhysicsValidated(
                validation,
                validation.IsValid,
                validation.Violations);
            
            context.Respond(response);
            
            _logger.LogDebug("Physics validation completed in {ValidationTime}ms, Result: {IsValid}", 
                validationTime, validation.IsValid);
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Failed to validate physics for data at ({X}, {Y})", 
                message.Data.XCoord, message.Data.YCoord);
            
            var errorValidation = new PhysicsValidation
            {
                IsValid = false,
                ThicknessValid = false,
                EnergyConservationValid = false,
                MassConservationValid = false,
                Violations = new List<string> { $"Validation error: {ex.Message}" },
                ValidationScore = 0.0
            };
            
            var errorResponse = new PhysicsValidated(
                errorValidation,
                false,
                errorValidation.Violations);
            
            context.Respond(errorResponse);
        }
    }

    private async Task<PhysicsValidation> PerformPhysicsValidation(TransactionData data, Model? parentModel)
    {
        var violations = new List<string>();
        var validationResults = new Dictionary<string, bool>();
        
        // 1. Thickness Validation
        var thicknessValid = await ValidateThickness(data, violations);
        validationResults["thickness"] = thicknessValid;
        
        // 2. Energy Conservation Validation
        var energyValid = await ValidateEnergyConservation(data, parentModel, violations);
        validationResults["energy"] = energyValid;
        
        // 3. Mass Conservation Validation
        var massValid = await ValidateMassConservation(data, parentModel, violations);
        validationResults["mass"] = massValid;
        
        // 4. Spatial Continuity Validation
        var spatialValid = await ValidateSpatialContinuity(data, parentModel, violations);
        validationResults["spatial"] = spatialValid;
        
        // 5. Material Properties Validation
        var materialValid = await ValidateMaterialProperties(data, violations);
        validationResults["material"] = materialValid;
        
        // Calculate overall validation score
        var validationScore = CalculateValidationScore(validationResults);
        var overallValid = validationScore >= _physicsRules.MinValidationScore;
        
        return new PhysicsValidation
        {
            IsValid = overallValid,
            ThicknessValid = thicknessValid,
            EnergyConservationValid = energyValid,
            MassConservationValid = massValid,
            Violations = violations,
            ValidationScore = validationScore
        };
    }

    private async Task<bool> ValidateThickness(TransactionData data, List<string> violations)
    {
        await Task.Delay(1); // Simulate async validation
        
        var isValid = true;
        
        // Check minimum thickness
        if (data.Thickness < _physicsRules.MinThickness)
        {
            violations.Add($"Thickness {data.Thickness:F2}mm below minimum {_physicsRules.MinThickness:F2}mm");
            isValid = false;
        }
        
        // Check maximum thickness
        if (data.Thickness > _physicsRules.MaxThickness)
        {
            violations.Add($"Thickness {data.Thickness:F2}mm above maximum {_physicsRules.MaxThickness:F2}mm");
            isValid = false;
        }
        
        // Check thickness gradient (rate of change)
        var thicknessGradient = CalculateThicknessGradient(data);
        if (Math.Abs(thicknessGradient) > _physicsRules.MaxThicknessGradient)
        {
            violations.Add($"Thickness gradient {thicknessGradient:F4} exceeds maximum {_physicsRules.MaxThicknessGradient:F4}");
            isValid = false;
        }
        
        return isValid;
    }

    private async Task<bool> ValidateEnergyConservation(TransactionData data, Model? parentModel, List<string> violations)
    {
        await Task.Delay(1); // Simulate async validation
        
        // Energy conservation validation based on ultrasonic wave propagation
        var energyBalance = CalculateEnergyBalance(data, parentModel);
        
        if (Math.Abs(energyBalance) > _physicsRules.MaxEnergyImbalance)
        {
            violations.Add($"Energy imbalance {energyBalance:F4} exceeds threshold {_physicsRules.MaxEnergyImbalance:F4}");
            return false;
        }
        
        return true;
    }

    private async Task<bool> ValidateMassConservation(TransactionData data, Model? parentModel, List<string> violations)
    {
        await Task.Delay(1); // Simulate async validation
        
        // Mass conservation validation for material density
        var massBalance = CalculateMassBalance(data, parentModel);
        
        if (Math.Abs(massBalance) > _physicsRules.MaxMassImbalance)
        {
            violations.Add($"Mass imbalance {massBalance:F4} exceeds threshold {_physicsRules.MaxMassImbalance:F4}");
            return false;
        }
        
        return true;
    }

    private async Task<bool> ValidateSpatialContinuity(TransactionData data, Model? parentModel, List<string> violations)
    {
        await Task.Delay(1); // Simulate async validation
        
        if (parentModel == null) return true; // No parent to compare with
        
        // Check spatial continuity with parent model
        var spatialDistance = CalculateSpatialDistance(data, parentModel);
        var thicknessDifference = Math.Abs(data.Thickness - GetParentThickness(parentModel));
        
        // Thickness should change gradually over space
        var expectedThicknessChange = spatialDistance * _physicsRules.MaxThicknessChangeRate;
        
        if (thicknessDifference > expectedThicknessChange)
        {
            violations.Add($"Thickness change {thicknessDifference:F2}mm over distance {spatialDistance:F2}mm " +
                          $"exceeds expected rate {expectedThicknessChange:F2}mm");
            return false;
        }
        
        return true;
    }

    private async Task<bool> ValidateMaterialProperties(TransactionData data, List<string> violations)
    {
        await Task.Delay(1); // Simulate async validation
        
        // Validate material-specific properties
        var density = CalculateMaterialDensity(data);
        var elasticity = CalculateElasticModulus(data);
        
        if (density < _physicsRules.MinMaterialDensity || density > _physicsRules.MaxMaterialDensity)
        {
            violations.Add($"Material density {density:F2} outside valid range " +
                          $"[{_physicsRules.MinMaterialDensity:F2}, {_physicsRules.MaxMaterialDensity:F2}]");
            return false;
        }
        
        if (elasticity < _physicsRules.MinElasticModulus || elasticity > _physicsRules.MaxElasticModulus)
        {
            violations.Add($"Elastic modulus {elasticity:F2} outside valid range " +
                          $"[{_physicsRules.MinElasticModulus:F2}, {_physicsRules.MaxElasticModulus:F2}]");
            return false;
        }
        
        return true;
    }

    private double CalculateValidationScore(Dictionary<string, bool> results)
    {
        var weights = new Dictionary<string, double>
        {
            ["thickness"] = 0.3,
            ["energy"] = 0.25,
            ["mass"] = 0.25,
            ["spatial"] = 0.15,
            ["material"] = 0.05
        };
        
        return results.Sum(kvp => weights.GetValueOrDefault(kvp.Key, 0.0) * (kvp.Value ? 1.0 : 0.0));
    }

    private double CalculateThicknessGradient(TransactionData data)
    {
        // Simplified gradient calculation (would use neighboring points in real implementation)
        return data.Features.GetValueOrDefault("thickness_gradient", 0.0);
    }

    private double CalculateEnergyBalance(TransactionData data, Model? parentModel)
    {
        // Simplified energy balance calculation
        var baseEnergy = data.Thickness * 0.1; // Simplified energy calculation
        var parentEnergy = parentModel?.Parameters.Weights.Sum() ?? 0.0;
        return Math.Abs(baseEnergy - parentEnergy * 0.1);
    }

    private double CalculateMassBalance(TransactionData data, Model? parentModel)
    {
        // Simplified mass balance calculation
        var density = CalculateMaterialDensity(data);
        var volume = data.Thickness * 1.0; // Assume unit area
        var mass = density * volume;
        
        var parentMass = parentModel?.Parameters.Bias ?? 1.0;
        return Math.Abs(mass - parentMass) / Math.Max(mass, parentMass);
    }

    private double CalculateSpatialDistance(TransactionData data, Model parentModel)
    {
        var dx = data.XCoord - parentModel.Location.X;
        var dy = data.YCoord - parentModel.Location.Y;
        return Math.Sqrt(dx * dx + dy * dy);
    }

    private double GetParentThickness(Model parentModel)
    {
        // Extract thickness from parent model (simplified)
        return parentModel.Parameters.Weights.FirstOrDefault() * 20.0; // Simplified extraction
    }

    private double CalculateMaterialDensity(TransactionData data)
    {
        // Simplified density calculation based on thickness and features
        var baseDensity = 7.85; // Steel density in g/cm³
        var thicknessFactor = data.Thickness / 20.0; // Normalize around 20mm
        return baseDensity * thicknessFactor * data.Quality;
    }

    private double CalculateElasticModulus(TransactionData data)
    {
        // Simplified elastic modulus calculation
        var baseModulus = 200.0; // Steel elastic modulus in GPa
        var qualityFactor = data.Quality;
        return baseModulus * qualityFactor;
    }

    private async Task HandleGetMetrics(IContext context)
    {
        var avgValidationTime = _validationsPerformed > 0 
            ? _totalValidationTimeMs / _validationsPerformed 
            : 0;
        
        var successRate = _validationsPerformed > 0
            ? (double)_validationsPassed / _validationsPerformed
            : 0;
        
        var customMetrics = new Dictionary<string, double>
        {
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds,
            ["validations_performed"] = _validationsPerformed,
            ["validations_passed"] = _validationsPassed,
            ["validations_failed"] = _validationsFailed,
            ["success_rate"] = successRate,
            ["total_validation_time_ms"] = _totalValidationTimeMs
        };
        
        var response = new MetricsResponse(
            _actorId,
            _validationsPerformed,
            avgValidationTime,
            0, // No throughput calculation for validator
            customMetrics);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleGetHealthStatus(IContext context)
    {
        var successRate = _validationsPerformed > 0
            ? (double)_validationsPassed / _validationsPerformed
            : 1.0;
        
        var isHealthy = successRate >= 0.5; // Consider healthy if >50% validations pass
        
        var metrics = new Dictionary<string, object>
        {
            ["validations_performed"] = _validationsPerformed,
            ["validations_passed"] = _validationsPassed,
            ["validations_failed"] = _validationsFailed,
            ["success_rate"] = successRate,
            ["uptime_seconds"] = _uptimeStopwatch.Elapsed.TotalSeconds,
            ["is_healthy"] = isHealthy
        };
        
        var response = new HealthStatusResponse(
            _actorId,
            isHealthy,
            metrics,
            DateTimeOffset.UtcNow);
        
        context.Respond(response);
        await Task.CompletedTask;
    }

    private async Task HandleShutdown(IContext context, Shutdown message)
    {
        _logger.LogInformation("PhysicsValidatorActor {ActorId} shutting down: {Reason}", 
            _actorId, message.Reason);
        
        // Log final statistics
        _logger.LogInformation("Final validation statistics - Performed: {Performed}, " +
                              "Passed: {Passed}, Failed: {Failed}, Success Rate: {SuccessRate:P2}",
            _validationsPerformed, _validationsPassed, _validationsFailed,
            _validationsPerformed > 0 ? (double)_validationsPassed / _validationsPerformed : 0);
        
        // Stop the actor
        context.Stop(context.Self);
        await Task.CompletedTask;
    }
}

/// <summary>
/// Physics rules and constraints for validation
/// </summary>
public class PhysicsRules
{
    // Thickness constraints (mm)
    public double MinThickness { get; } = 5.0;
    public double MaxThickness { get; } = 50.0;
    public double MaxThicknessGradient { get; } = 0.1; // mm per unit distance
    public double MaxThicknessChangeRate { get; } = 0.05; // mm per mm distance
    
    // Energy conservation constraints
    public double MaxEnergyImbalance { get; } = 0.1; // 10% tolerance
    
    // Mass conservation constraints
    public double MaxMassImbalance { get; } = 0.05; // 5% tolerance
    
    // Material property constraints
    public double MinMaterialDensity { get; } = 6.0; // g/cm³
    public double MaxMaterialDensity { get; } = 9.0; // g/cm³
    public double MinElasticModulus { get; } = 150.0; // GPa
    public double MaxElasticModulus { get; } = 250.0; // GPa
    
    // Overall validation
    public double MinValidationScore { get; } = 0.7; // 70% minimum score to pass
}
