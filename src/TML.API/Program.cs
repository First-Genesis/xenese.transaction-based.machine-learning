using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Serilog;
using StackExchange.Redis;
using System.Text;
using TML.Actors.Services;
using TML.API.Extensions;
using TML.API.Middleware;

var builder = WebApplication.CreateBuilder(args);

// Configure Serilog
Log.Logger = new LoggerConfiguration()
    .ReadFrom.Configuration(builder.Configuration)
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .WriteTo.File("logs/tml-api-.txt", rollingInterval: RollingInterval.Day)
    .CreateLogger();

builder.Host.UseSerilog();

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() { 
        Title = "TML Platform API", 
        Version = "v1",
        Description = "Transaction-based Machine Learning Platform API"
    });
    
    // Include XML comments
    var xmlFile = $"{System.Reflection.Assembly.GetExecutingAssembly().GetName().Name}.xml";
    var xmlPath = Path.Combine(AppContext.BaseDirectory, xmlFile);
    c.IncludeXmlComments(xmlPath);
});

// Configure JWT Authentication
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],
            ValidAudience = builder.Configuration["Jwt:Audience"],
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(builder.Configuration["Jwt:Key"] ?? 
                    throw new InvalidOperationException("JWT Key not configured")))
        };
    });

builder.Services.AddAuthorization();

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

// Add Database context
builder.Services.AddDbContext<TML.Storage.Data.TMLDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

// Add repositories
builder.Services.AddScoped<TML.Storage.Repositories.ITransactionRepository, TML.Storage.Repositories.TransactionRepository>();
builder.Services.AddScoped<TML.Storage.Repositories.IModelRepository, TML.Storage.Repositories.ModelRepository>();

// Add storage services
builder.Services.AddSingleton<TML.Storage.Services.IS3ClientFactory, TML.Storage.Services.S3ClientFactory>();
builder.Services.AddSingleton<Amazon.S3.IAmazonS3>(provider => 
    provider.GetRequiredService<TML.Storage.Services.IS3ClientFactory>().CreateClient());
builder.Services.AddScoped<TML.Storage.Services.IS3ModelArtifactService, TML.Storage.Services.S3ModelArtifactService>();

// Add Redis cache
builder.Services.AddSingleton<StackExchange.Redis.IConnectionMultiplexer>(provider =>
{
    var configuration = builder.Configuration["Redis:ConnectionString"] ?? "tml-redis-test:6379";
    var logger = provider.GetService<ILogger<Program>>();
    
    logger?.LogInformation("Attempting to connect to Redis at: {Configuration}", configuration);
    
    var options = ConfigurationOptions.Parse(configuration);
    options.AbortOnConnectFail = false; // Allow retries
    options.ConnectTimeout = 10000; // 10 seconds
    options.SyncTimeout = 5000; // 5 seconds
    
    var multiplexer = ConnectionMultiplexer.Connect(options);
    
    logger?.LogInformation("Successfully connected to Redis");
    return multiplexer;
});
builder.Services.AddScoped<TML.Storage.Services.IRedisCacheService, TML.Storage.Services.RedisCacheService>();

// Configure S3 settings
builder.Services.Configure<TML.Storage.Services.S3Configuration>(
    builder.Configuration.GetSection("S3"));

// Configure Redis settings
builder.Services.Configure<TML.Storage.Services.RedisConfiguration>(
    builder.Configuration.GetSection("Redis"));

// Add Health Checks
builder.Services.AddHealthChecks()
    .AddCheck<ActorSystemHealthCheck>("actor-system")
    .AddCheck("self", () => Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy());

// Configure Actor System
var actorConfig = new ActorSystemConfiguration();
builder.Configuration.GetSection("ActorSystem").Bind(actorConfig);
builder.Services.AddSingleton(actorConfig);

// Add Actor System Service
builder.Services.AddSingleton<ActorSystemService>();
builder.Services.AddHostedService(provider => provider.GetRequiredService<ActorSystemService>());

// Add MediatR
builder.Services.AddMediatR(cfg => cfg.RegisterServicesFromAssembly(typeof(Program).Assembly));

// Add AutoMapper
builder.Services.AddAutoMapper(typeof(Program));

// Add MLOps - Drift Detection Services
builder.Services.AddScoped<TML.MLOps.DriftDetection.IDriftDetector, TML.MLOps.DriftDetection.DriftDetector>();
builder.Services.AddHostedService<TML.MLOps.DriftDetection.DriftMonitoringService>();

// Add MLOps - A/B Testing Services
builder.Services.AddScoped<TML.MLOps.ABTesting.IExperimentManager, TML.MLOps.ABTesting.ExperimentManager>();

// Add FluentValidation - removed as package needs configuration

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(c =>
    {
        c.SwaggerEndpoint("/swagger/v1/swagger.json", "TML Platform API v1");
        c.RoutePrefix = string.Empty; // Serve Swagger UI at root
    });
}

// Add custom middleware
app.UseMiddleware<RequestLoggingMiddleware>();
app.UseMiddleware<ExceptionHandlingMiddleware>();

app.UseHttpsRedirection();
app.UseCors("AllowAll");

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.MapHealthChecks("/health");

// Add metrics endpoint
app.MapGet("/metrics", async (ActorSystemService actorSystem) =>
{
    var health = await actorSystem.GetHealthStatusAsync();
    return Results.Ok(new
    {
        timestamp = DateTimeOffset.UtcNow,
        system = new
        {
            healthy = health.IsHealthy,
            actors = new
            {
                total = health.ActorCount,
                healthy = health.ActorHealthyCount,
                transaction_processors = health.TransactionProcessorCount,
                model_actors = health.ModelActorCount,
                physics_validators = health.PhysicsValidatorCount
            },
            cluster = new
            {
                enabled = health.ClusterEnabled,
                healthy = health.ClusterHealthy
            }
        }
    });
});

try
{
    Log.Information("Starting TML Platform API");
    
    // Run database migrations
    using (var scope = app.Services.CreateScope())
    {
        var dbContext = scope.ServiceProvider.GetRequiredService<TML.Storage.Data.TMLDbContext>();
        Log.Information("Running database migrations...");
        await dbContext.Database.MigrateAsync();
        Log.Information("Database migrations completed successfully");
    }
    
    await app.RunAsync();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();
}

public partial class Program { } // Make Program accessible for tests
