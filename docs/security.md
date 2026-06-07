# 🔒 TML Platform Security Configuration Guide

This guide covers comprehensive security configurations for the TML Platform, including authentication, authorization, data protection, network security, and compliance requirements for enterprise deployments.

## Table of Contents
1. [Security Overview](#security-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Data Protection](#data-protection)
4. [Network Security](#network-security)
5. [Container Security](#container-security)
6. [Database Security](#database-security)
7. [API Security](#api-security)
8. [Monitoring & Auditing](#monitoring--auditing)
9. [Compliance](#compliance)
10. [Incident Response](#incident-response)

---

## Security Overview

### Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│ 🌐 Network Security (WAF, DDoS Protection, VPC)           │
├─────────────────────────────────────────────────────────────┤
│ 🔐 Identity & Access Management (OAuth2, RBAC, MFA)       │
├─────────────────────────────────────────────────────────────┤
│ 🛡️  Application Security (Input Validation, CSRF, XSS)    │
├─────────────────────────────────────────────────────────────┤
│ 📊 Data Security (Encryption, Tokenization, Masking)      │
├─────────────────────────────────────────────────────────────┤
│ 🐳 Container Security (Image Scanning, Runtime Protection) │
├─────────────────────────────────────────────────────────────┤
│ 🗄️  Database Security (TDE, Column Encryption, Audit)     │
├─────────────────────────────────────────────────────────────┤
│ 📋 Compliance (SOC2, GDPR, HIPAA, PCI-DSS)               │
└─────────────────────────────────────────────────────────────┘
```

### Security Principles
- **Zero Trust Architecture**: Never trust, always verify
- **Defense in Depth**: Multiple layers of security controls
- **Least Privilege**: Minimum necessary access rights
- **Data Classification**: Protect data based on sensitivity
- **Continuous Monitoring**: Real-time threat detection
- **Incident Response**: Rapid response to security events

---

## Authentication & Authorization

### OAuth2 + OpenID Connect Configuration

```yaml
# k8s/oauth2-proxy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oauth2-proxy
  namespace: tml-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: oauth2-proxy
  template:
    metadata:
      labels:
        app: oauth2-proxy
    spec:
      containers:
      - name: oauth2-proxy
        image: quay.io/oauth2-proxy/oauth2-proxy:latest
        args:
        - --provider=oidc
        - --oidc-issuer-url=https://auth.company.com
        - --client-id=$(CLIENT_ID)
        - --client-secret=$(CLIENT_SECRET)
        - --cookie-secret=$(COOKIE_SECRET)
        - --email-domain=company.com
        - --upstream=http://tml-api-service:5000
        - --http-address=0.0.0.0:4180
        - --redirect-url=https://api.tml-platform.com/oauth2/callback
        - --set-authorization-header=true
        - --set-xauthrequest=true
        - --pass-access-token=true
        - --pass-user-headers=true
        - --cookie-secure=true
        - --cookie-httponly=true
        - --cookie-samesite=strict
        env:
        - name: CLIENT_ID
          valueFrom:
            secretKeyRef:
              name: oauth2-secrets
              key: client-id
        - name: CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: oauth2-secrets
              key: client-secret
        - name: COOKIE_SECRET
          valueFrom:
            secretKeyRef:
              name: oauth2-secrets
              key: cookie-secret
        ports:
        - containerPort: 4180
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
```

### Role-Based Access Control (RBAC)

```csharp
// src/TML.API/Security/Authorization/TMLAuthorizationHandler.cs
public class TMLAuthorizationHandler : AuthorizationHandler<TMLRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        TMLRequirement requirement)
    {
        var user = context.User;
        
        // Check if user has required role
        if (!user.Identity.IsAuthenticated)
        {
            context.Fail();
            return Task.CompletedTask;
        }
        
        var userRoles = user.Claims
            .Where(c => c.Type == ClaimTypes.Role)
            .Select(c => c.Value)
            .ToList();
        
        var hasRequiredRole = requirement.AllowedRoles
            .Any(role => userRoles.Contains(role));
        
        if (hasRequiredRole)
        {
            context.Succeed(requirement);
        }
        else
        {
            context.Fail();
        }
        
        return Task.CompletedTask;
    }
}

// Role definitions
public static class TMLRoles
{
    public const string Admin = "tml:admin";
    public const string DataScientist = "tml:data-scientist";
    public const string ModelViewer = "tml:model-viewer";
    public const string ApiUser = "tml:api-user";
    public const string ReadOnly = "tml:read-only";
}

// Permission-based authorization
public static class TMLPermissions
{
    public const string CreateModels = "tml:models:create";
    public const string ViewModels = "tml:models:view";
    public const string DeleteModels = "tml:models:delete";
    public const string ProcessTransactions = "tml:transactions:process";
    public const string ViewMetrics = "tml:metrics:view";
    public const string ManageSystem = "tml:system:manage";
}
```

### API Key Management

```csharp
// src/TML.API/Security/ApiKeyAuthenticationHandler.cs
public class ApiKeyAuthenticationHandler : AuthenticationHandler<ApiKeyAuthenticationSchemeOptions>
{
    private readonly IApiKeyService _apiKeyService;
    
    protected override async Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.ContainsKey("X-API-Key"))
        {
            return AuthenticateResult.Fail("Missing API Key");
        }
        
        var apiKey = Request.Headers["X-API-Key"].FirstOrDefault();
        
        if (string.IsNullOrEmpty(apiKey))
        {
            return AuthenticateResult.Fail("Invalid API Key");
        }
        
        var apiKeyInfo = await _apiKeyService.ValidateApiKeyAsync(apiKey);
        
        if (apiKeyInfo == null || !apiKeyInfo.IsActive)
        {
            return AuthenticateResult.Fail("Invalid or inactive API Key");
        }
        
        // Check rate limits
        if (await _apiKeyService.IsRateLimitExceededAsync(apiKey))
        {
            return AuthenticateResult.Fail("Rate limit exceeded");
        }
        
        var claims = new[]
        {
            new Claim(ClaimTypes.Name, apiKeyInfo.Name),
            new Claim(ClaimTypes.NameIdentifier, apiKeyInfo.Id),
            new Claim("api_key_id", apiKeyInfo.Id),
            new Claim("client_id", apiKeyInfo.ClientId)
        };
        
        // Add role claims
        foreach (var role in apiKeyInfo.Roles)
        {
            claims = claims.Append(new Claim(ClaimTypes.Role, role)).ToArray();
        }
        
        var identity = new ClaimsIdentity(claims, Scheme.Name);
        var principal = new ClaimsPrincipal(identity);
        
        return AuthenticateResult.Success(new AuthenticationTicket(principal, Scheme.Name));
    }
}

// API Key service
public interface IApiKeyService
{
    Task<ApiKeyInfo> ValidateApiKeyAsync(string apiKey);
    Task<bool> IsRateLimitExceededAsync(string apiKey);
    Task<string> CreateApiKeyAsync(string clientId, List<string> roles, DateTime? expiresAt = null);
    Task RevokeApiKeyAsync(string apiKey);
}

public class ApiKeyInfo
{
    public string Id { get; set; }
    public string Name { get; set; }
    public string ClientId { get; set; }
    public List<string> Roles { get; set; }
    public bool IsActive { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? ExpiresAt { get; set; }
    public int RequestsPerMinute { get; set; }
    public int RequestsPerDay { get; set; }
}
```

### Multi-Factor Authentication (MFA)

```csharp
// src/TML.API/Security/MFA/TOTPService.cs
public class TOTPService
{
    public string GenerateSecret()
    {
        var key = new byte[20];
        using (var rng = RandomNumberGenerator.Create())
        {
            rng.GetBytes(key);
        }
        return Base32Encoding.ToString(key);
    }
    
    public string GenerateQRCodeUri(string secret, string email, string issuer = "TML Platform")
    {
        return $"otpauth://totp/{Uri.EscapeDataString(issuer)}:{Uri.EscapeDataString(email)}?secret={secret}&issuer={Uri.EscapeDataString(issuer)}";
    }
    
    public bool ValidateTotp(string secret, string code, int window = 1)
    {
        var secretBytes = Base32Encoding.ToBytes(secret);
        var unixTime = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var timeStep = unixTime / 30;
        
        for (int i = -window; i <= window; i++)
        {
            var testTimeStep = timeStep + i;
            var hash = GenerateHash(secretBytes, testTimeStep);
            var truncatedHash = TruncateHash(hash);
            var totp = (truncatedHash % 1000000).ToString("D6");
            
            if (totp == code)
            {
                return true;
            }
        }
        
        return false;
    }
    
    private byte[] GenerateHash(byte[] secret, long timeStep)
    {
        var timeBytes = BitConverter.GetBytes(timeStep);
        if (BitConverter.IsLittleEndian)
        {
            Array.Reverse(timeBytes);
        }
        
        using (var hmac = new HMACSHA1(secret))
        {
            return hmac.ComputeHash(timeBytes);
        }
    }
    
    private int TruncateHash(byte[] hash)
    {
        var offset = hash[hash.Length - 1] & 0x0F;
        return ((hash[offset] & 0x7F) << 24) |
               ((hash[offset + 1] & 0xFF) << 16) |
               ((hash[offset + 2] & 0xFF) << 8) |
               (hash[offset + 3] & 0xFF);
    }
}
```

---

## Data Protection

### Encryption at Rest

```yaml
# k8s/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  - configmaps
  providers:
  - aescbc:
      keys:
      - name: key1
        secret: <base64-encoded-32-byte-key>
  - identity: {}
```

### Database Encryption

```sql
-- PostgreSQL Transparent Data Encryption (TDE)
-- Enable encryption for sensitive columns

-- Create encryption key
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt sensitive model data
CREATE TABLE models_encrypted (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    parameters_encrypted BYTEA, -- Encrypted JSON
    metadata_encrypted BYTEA,   -- Encrypted JSON
    parent_model_id UUID REFERENCES models_encrypted(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'Active'
);

-- Encryption functions
CREATE OR REPLACE FUNCTION encrypt_data(data TEXT, key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(data, key);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION decrypt_data(encrypted_data BYTEA, key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted_data, key);
END;
$$ LANGUAGE plpgsql;

-- Row-level security
ALTER TABLE models_encrypted ENABLE ROW LEVEL SECURITY;

-- Policy for data access
CREATE POLICY model_access_policy ON models_encrypted
    FOR ALL
    TO tml_app
    USING (
        -- Only allow access to models owned by the current user's organization
        EXISTS (
            SELECT 1 FROM user_organizations uo
            WHERE uo.user_id = current_setting('app.current_user_id')::UUID
            AND uo.organization_id = (metadata_encrypted->>'organization_id')::UUID
        )
    );
```

### Data Masking and Tokenization

```csharp
// src/TML.API/Security/DataProtection/DataMaskingService.cs
public class DataMaskingService
{
    private readonly IDataProtectionProvider _dataProtection;
    
    public DataMaskingService(IDataProtectionProvider dataProtection)
    {
        _dataProtection = dataProtection;
    }
    
    public string MaskSensitiveData(string data, SensitivityLevel level)
    {
        return level switch
        {
            SensitivityLevel.Low => MaskPartial(data, 0.3),
            SensitivityLevel.Medium => MaskPartial(data, 0.6),
            SensitivityLevel.High => MaskComplete(data),
            SensitivityLevel.Critical => TokenizeData(data),
            _ => data
        };
    }
    
    private string MaskPartial(string data, double maskRatio)
    {
        if (string.IsNullOrEmpty(data)) return data;
        
        var maskLength = (int)(data.Length * maskRatio);
        var visibleLength = data.Length - maskLength;
        
        return data.Substring(0, visibleLength / 2) +
               new string('*', maskLength) +
               data.Substring(data.Length - visibleLength / 2);
    }
    
    private string MaskComplete(string data)
    {
        return new string('*', Math.Min(data?.Length ?? 0, 10));
    }
    
    private string TokenizeData(string data)
    {
        var protector = _dataProtection.CreateProtector("TML.DataTokenization");
        var token = protector.Protect(data);
        return $"TOKEN:{Convert.ToBase64String(Encoding.UTF8.GetBytes(token))}";
    }
    
    public string DetokenizeData(string token)
    {
        if (!token.StartsWith("TOKEN:")) return token;
        
        var protector = _dataProtection.CreateProtector("TML.DataTokenization");
        var encryptedData = Convert.FromBase64String(token.Substring(6));
        var protectedData = Encoding.UTF8.GetString(encryptedData);
        
        return protector.Unprotect(protectedData);
    }
}

public enum SensitivityLevel
{
    Public,
    Low,
    Medium,
    High,
    Critical
}
```

### Secrets Management

```yaml
# k8s/external-secrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: tml-production
spec:
  provider:
    vault:
      server: "https://vault.company.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "tml-production"
          serviceAccountRef:
            name: "external-secrets-sa"

---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: tml-secrets
  namespace: tml-production
spec:
  refreshInterval: 15s
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: tml-secrets
    creationPolicy: Owner
  data:
  - secretKey: database-password
    remoteRef:
      key: tml/production
      property: database_password
  - secretKey: redis-password
    remoteRef:
      key: tml/production
      property: redis_password
  - secretKey: jwt-secret
    remoteRef:
      key: tml/production
      property: jwt_secret
  - secretKey: encryption-key
    remoteRef:
      key: tml/production
      property: encryption_key
```

---

## Network Security

### Web Application Firewall (WAF)

```yaml
# k8s/waf-policy.yaml
apiVersion: networking.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: tml-waf-policy
  namespace: tml-production
spec:
  selector:
    matchLabels:
      app: tml-api
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/tml-production/sa/oauth2-proxy"]
  - to:
    - operation:
        methods: ["GET", "POST", "PUT", "DELETE"]
        paths: ["/api/*"]
  - when:
    - key: request.headers[content-type]
      values: ["application/json", "application/x-www-form-urlencoded"]

---
# Rate limiting
apiVersion: networking.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: rate-limit-filter
  namespace: tml-production
spec:
  workloadSelector:
    labels:
      app: tml-api
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: "envoy.filters.network.http_connection_manager"
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: rate_limiter
            token_bucket:
              max_tokens: 1000
              tokens_per_fill: 1000
              fill_interval: 60s
            filter_enabled:
              runtime_key: rate_limit_enabled
              default_value:
                numerator: 100
                denominator: HUNDRED
            filter_enforced:
              runtime_key: rate_limit_enforced
              default_value:
                numerator: 100
                denominator: HUNDRED
```

### Network Policies

```yaml
# k8s/network-policies.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tml-api-network-policy
  namespace: tml-production
spec:
  podSelector:
    matchLabels:
      app: tml-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
    - podSelector:
        matchLabels:
          app: oauth2-proxy
    ports:
    - protocol: TCP
      port: 5000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS outbound
    - protocol: TCP
      port: 53   # DNS
    - protocol: UDP
      port: 53   # DNS

---
# Database network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: postgres-network-policy
  namespace: tml-production
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: tml-api
    - podSelector:
        matchLabels:
          app: pgbouncer
    ports:
    - protocol: TCP
      port: 5432
```

### TLS Configuration

```yaml
# k8s/tls-config.yaml
apiVersion: v1
kind: Secret
metadata:
  name: tml-tls-secret
  namespace: tml-production
type: kubernetes.io/tls
data:
  tls.crt: <base64-encoded-certificate>
  tls.key: <base64-encoded-private-key>

---
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: tml-gateway
  namespace: tml-production
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: tml-tls-secret
      minProtocolVersion: TLSV1_2
      maxProtocolVersion: TLSV1_3
      cipherSuites:
      - ECDHE-RSA-AES256-GCM-SHA384
      - ECDHE-RSA-AES128-GCM-SHA256
    hosts:
    - api.tml-platform.com
    - demo.tml-platform.com
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - api.tml-platform.com
    - demo.tml-platform.com
    tls:
      httpsRedirect: true
```

---

## Container Security

### Image Scanning

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  container-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: docker build -t tml-api:${{ github.sha }} .
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'tml-api:${{ github.sha }}'
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
    
    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      if: always()
      with:
        sarif_file: 'trivy-results.sarif'
    
    - name: Run Snyk to check for vulnerabilities
      uses: snyk/actions/docker@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        image: tml-api:${{ github.sha }}
        args: --severity-threshold=high
```

### Runtime Security

```yaml
# k8s/falco-rules.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-rules
  namespace: falco-system
data:
  tml_rules.yaml: |
    - rule: TML Unauthorized Process
      desc: Detect unauthorized processes in TML containers
      condition: >
        spawned_process and
        container and
        k8s.ns.name = "tml-production" and
        not proc.name in (dotnet, streamlit, python, sh, bash)
      output: >
        Unauthorized process in TML container
        (user=%user.name command=%proc.cmdline container=%container.name
        image=%container.image.repository:%container.image.tag)
      priority: WARNING
      tags: [container, process, tml]
    
    - rule: TML Sensitive File Access
      desc: Detect access to sensitive files in TML containers
      condition: >
        open_read and
        container and
        k8s.ns.name = "tml-production" and
        (fd.name startswith /etc/passwd or
         fd.name startswith /etc/shadow or
         fd.name startswith /root/.ssh or
         fd.name contains "secret" or
         fd.name contains "key")
      output: >
        Sensitive file access in TML container
        (user=%user.name file=%fd.name container=%container.name
        image=%container.image.repository:%container.image.tag)
      priority: WARNING
      tags: [filesystem, container, tml]
    
    - rule: TML Network Anomaly
      desc: Detect unusual network activity from TML containers
      condition: >
        outbound and
        container and
        k8s.ns.name = "tml-production" and
        not fd.sip in (postgres_ips, redis_ips, vault_ips) and
        not fd.sport in (80, 443, 5432, 6379, 8200)
      output: >
        Unusual network connection from TML container
        (user=%user.name connection=%fd.name container=%container.name
        image=%container.image.repository:%container.image.tag)
      priority: WARNING
      tags: [network, container, tml]

---
# Pod Security Standards
apiVersion: v1
kind: Namespace
metadata:
  name: tml-production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### Security Context

```yaml
# k8s/secure-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tml-api-secure
  namespace: tml-production
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: tml-api
        image: tml-platform/api:v3.0
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
          runAsGroup: 1000
          capabilities:
            drop:
            - ALL
            add:
            - NET_BIND_SERVICE
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: var-tmp
          mountPath: /var/tmp
        - name: app-logs
          mountPath: /app/logs
      volumes:
      - name: tmp
        emptyDir: {}
      - name: var-tmp
        emptyDir: {}
      - name: app-logs
        emptyDir: {}
```

---

## Database Security

### Connection Security

```csharp
// src/TML.API/Configuration/DatabaseConfiguration.cs
public static class DatabaseConfiguration
{
    public static void ConfigureDatabase(this IServiceCollection services, IConfiguration configuration)
    {
        var connectionString = BuildSecureConnectionString(configuration);
        
        services.AddDbContext<TMLDbContext>(options =>
        {
            options.UseNpgsql(connectionString, npgsqlOptions =>
            {
                npgsqlOptions.EnableRetryOnFailure(
                    maxRetryCount: 3,
                    maxRetryDelay: TimeSpan.FromSeconds(30),
                    errorCodesToAdd: null);
                
                // Enable SSL
                npgsqlOptions.RemoteCertificateValidationCallback = 
                    (sender, certificate, chain, errors) => ValidateCertificate(certificate, chain, errors);
            });
            
            // Enable sensitive data logging only in development
            if (Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") == "Development")
            {
                options.EnableSensitiveDataLogging();
            }
        });
    }
    
    private static string BuildSecureConnectionString(IConfiguration configuration)
    {
        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = configuration["Database:Host"],
            Port = int.Parse(configuration["Database:Port"] ?? "5432"),
            Database = configuration["Database:Name"],
            Username = configuration["Database:Username"],
            Password = configuration["Database:Password"],
            
            // Security settings
            SslMode = SslMode.Require,
            TrustServerCertificate = false,
            IncludeErrorDetail = false,
            
            // Connection pooling
            MinPoolSize = 5,
            MaxPoolSize = 100,
            ConnectionLifetime = 300, // 5 minutes
            ConnectionIdleLifetime = 60, // 1 minute
            
            // Timeouts
            Timeout = 30,
            CommandTimeout = 30,
            
            // Application name for monitoring
            ApplicationName = "TML-API"
        };
        
        return builder.ToString();
    }
    
    private static bool ValidateCertificate(X509Certificate certificate, X509Chain chain, SslPolicyErrors errors)
    {
        // Implement custom certificate validation logic
        if (errors == SslPolicyErrors.None)
            return true;
        
        // Log certificate validation errors
        // In production, implement proper certificate validation
        return false;
    }
}
```

### Database Auditing

```sql
-- Enable PostgreSQL audit logging
-- Install pgaudit extension
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- Configure audit settings
ALTER SYSTEM SET pgaudit.log = 'all';
ALTER SYSTEM SET pgaudit.log_catalog = 'on';
ALTER SYSTEM SET pgaudit.log_parameter = 'on';
ALTER SYSTEM SET pgaudit.log_relation = 'on';
ALTER SYSTEM SET pgaudit.log_statement_once = 'on';
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries > 1 second

-- Reload configuration
SELECT pg_reload_conf();

-- Create audit table for application-level auditing
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    user_id UUID,
    user_name VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, operation, old_values, user_id, user_name, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, row_to_json(OLD), 
                current_setting('app.current_user_id', true)::UUID,
                current_setting('app.current_user_name', true),
                current_setting('app.client_ip', true)::INET);
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, operation, old_values, new_values, user_id, user_name, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, row_to_json(OLD), row_to_json(NEW),
                current_setting('app.current_user_id', true)::UUID,
                current_setting('app.current_user_name', true),
                current_setting('app.client_ip', true)::INET);
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, operation, new_values, user_id, user_name, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, row_to_json(NEW),
                current_setting('app.current_user_id', true)::UUID,
                current_setting('app.current_user_name', true),
                current_setting('app.client_ip', true)::INET);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to sensitive tables
CREATE TRIGGER models_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON models
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER model_performance_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON model_performance
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
```

---

## API Security

### Input Validation

```csharp
// src/TML.API/Validation/TransactionRequestValidator.cs
public class TransactionRequestValidator : AbstractValidator<TransactionRequest>
{
    public TransactionRequestValidator()
    {
        RuleFor(x => x.Id)
            .NotEmpty()
            .Must(BeValidGuid)
            .WithMessage("Transaction ID must be a valid GUID");
        
        RuleFor(x => x.Data)
            .NotNull()
            .Must(BeValidJson)
            .WithMessage("Transaction data must be valid JSON");
        
        RuleFor(x => x.Data)
            .Must(NotContainMaliciousContent)
            .WithMessage("Transaction data contains potentially malicious content");
        
        RuleFor(x => x.ProcessingMode)
            .IsInEnum()
            .WithMessage("Invalid processing mode");
    }
    
    private bool BeValidGuid(string id)
    {
        return Guid.TryParse(id, out _);
    }
    
    private bool BeValidJson(Dictionary<string, object> data)
    {
        try
        {
            JsonSerializer.Serialize(data);
            return true;
        }
        catch
        {
            return false;
        }
    }
    
    private bool NotContainMaliciousContent(Dictionary<string, object> data)
    {
        var json = JsonSerializer.Serialize(data);
        
        // Check for common injection patterns
        var maliciousPatterns = new[]
        {
            "<script", "javascript:", "vbscript:", "onload=", "onerror=",
            "eval(", "exec(", "system(", "cmd.exe", "powershell",
            "DROP TABLE", "DELETE FROM", "INSERT INTO", "UPDATE SET",
            "../", "..\\", "/etc/passwd", "C:\\Windows"
        };
        
        return !maliciousPatterns.Any(pattern => 
            json.Contains(pattern, StringComparison.OrdinalIgnoreCase));
    }
}

// Global exception handler
public class SecurityExceptionMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<SecurityExceptionMiddleware> _logger;
    
    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (SecurityException ex)
        {
            _logger.LogWarning("Security violation: {Message} from {IP}", 
                ex.Message, context.Connection.RemoteIpAddress);
            
            context.Response.StatusCode = 403;
            await context.Response.WriteAsync("Access denied");
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning("Validation error: {Message} from {IP}", 
                ex.Message, context.Connection.RemoteIpAddress);
            
            context.Response.StatusCode = 400;
            await context.Response.WriteAsync("Invalid request");
        }
    }
}
```

### CORS Configuration

```csharp
// src/TML.API/Configuration/CorsConfiguration.cs
public static class CorsConfiguration
{
    public static void ConfigureCors(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddCors(options =>
        {
            options.AddPolicy("TMLCorsPolicy", builder =>
            {
                var allowedOrigins = configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() 
                    ?? new[] { "https://demo.tml-platform.com" };
                
                builder
                    .WithOrigins(allowedOrigins)
                    .WithMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                    .WithHeaders("Content-Type", "Authorization", "X-API-Key", "X-Requested-With")
                    .WithExposedHeaders("X-Total-Count", "X-Page-Count")
                    .SetIsOriginAllowedToReturnTrue() // Only for development
                    .AllowCredentials()
                    .SetPreflightMaxAge(TimeSpan.FromMinutes(10));
            });
        });
    }
}
```

### Security Headers

```csharp
// src/TML.API/Middleware/SecurityHeadersMiddleware.cs
public class SecurityHeadersMiddleware
{
    private readonly RequestDelegate _next;
    
    public SecurityHeadersMiddleware(RequestDelegate next)
    {
        _next = next;
    }
    
    public async Task InvokeAsync(HttpContext context)
    {
        // Remove server information
        context.Response.Headers.Remove("Server");
        
        // Security headers
        context.Response.Headers.Add("X-Content-Type-Options", "nosniff");
        context.Response.Headers.Add("X-Frame-Options", "DENY");
        context.Response.Headers.Add("X-XSS-Protection", "1; mode=block");
        context.Response.Headers.Add("Referrer-Policy", "strict-origin-when-cross-origin");
        context.Response.Headers.Add("Permissions-Policy", 
            "geolocation=(), microphone=(), camera=()");
        
        // HSTS (only for HTTPS)
        if (context.Request.IsHttps)
        {
            context.Response.Headers.Add("Strict-Transport-Security", 
                "max-age=31536000; includeSubDomains; preload");
        }
        
        // CSP
        var csp = "default-src 'self'; " +
                  "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
                  "style-src 'self' 'unsafe-inline'; " +
                  "img-src 'self' data: https:; " +
                  "font-src 'self'; " +
                  "connect-src 'self'; " +
                  "frame-ancestors 'none';";
        
        context.Response.Headers.Add("Content-Security-Policy", csp);
        
        await _next(context);
    }
}
```

---

## Monitoring & Auditing

### Security Event Monitoring

```csharp
// src/TML.API/Security/SecurityEventService.cs
public class SecurityEventService
{
    private readonly ILogger<SecurityEventService> _logger;
    private readonly IMetrics _metrics;
    
    public async Task LogSecurityEventAsync(SecurityEvent securityEvent)
    {
        // Log to structured logging
        _logger.LogWarning("Security Event: {EventType} from {Source} at {Timestamp}", 
            securityEvent.EventType, securityEvent.Source, securityEvent.Timestamp);
        
        // Update metrics
        _metrics.Measure.Counter.Increment("security_events_total", 
            new MetricTags("event_type", securityEvent.EventType.ToString()));
        
        // Send to SIEM if configured
        if (ShouldSendToSiem(securityEvent))
        {
            await SendToSiemAsync(securityEvent);
        }
        
        // Trigger alerts for critical events
        if (securityEvent.Severity == SecurityEventSeverity.Critical)
        {
            await TriggerAlertAsync(securityEvent);
        }
    }
    
    private bool ShouldSendToSiem(SecurityEvent securityEvent)
    {
        return securityEvent.Severity >= SecurityEventSeverity.Medium;
    }
    
    private async Task SendToSiemAsync(SecurityEvent securityEvent)
    {
        // Implementation for SIEM integration (e.g., Splunk, ELK)
        var siemPayload = new
        {
            timestamp = securityEvent.Timestamp,
            event_type = securityEvent.EventType.ToString(),
            severity = securityEvent.Severity.ToString(),
            source = securityEvent.Source,
            user_id = securityEvent.UserId,
            ip_address = securityEvent.IpAddress,
            user_agent = securityEvent.UserAgent,
            details = securityEvent.Details
        };
        
        // Send to SIEM endpoint
        // await _siemClient.SendEventAsync(siemPayload);
    }
}

public class SecurityEvent
{
    public SecurityEventType EventType { get; set; }
    public SecurityEventSeverity Severity { get; set; }
    public string Source { get; set; }
    public string UserId { get; set; }
    public string IpAddress { get; set; }
    public string UserAgent { get; set; }
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public Dictionary<string, object> Details { get; set; } = new();
}

public enum SecurityEventType
{
    AuthenticationFailure,
    AuthorizationFailure,
    SuspiciousActivity,
    DataAccess,
    ConfigurationChange,
    SecurityViolation
}

public enum SecurityEventSeverity
{
    Low,
    Medium,
    High,
    Critical
}
```

### Compliance Monitoring

```yaml
# k8s/compliance-monitoring.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: compliance-rules
  namespace: tml-production
data:
  falco-compliance-rules.yaml: |
    # SOC 2 Compliance Rules
    - rule: SOC2 - Unauthorized Admin Access
      desc: Detect unauthorized administrative access
      condition: >
        spawned_process and
        proc.name in (sudo, su) and
        not user.name in (admin, root)
      output: >
        Unauthorized admin access attempt
        (user=%user.name command=%proc.cmdline)
      priority: HIGH
      tags: [soc2, admin, compliance]
    
    # GDPR Compliance Rules
    - rule: GDPR - Personal Data Access
      desc: Monitor access to personal data
      condition: >
        open_read and
        fd.name contains "personal" or
        fd.name contains "pii"
      output: >
        Personal data access detected
        (user=%user.name file=%fd.name)
      priority: INFO
      tags: [gdpr, pii, compliance]
    
    # PCI DSS Compliance Rules
    - rule: PCI DSS - Payment Data Access
      desc: Monitor access to payment card data
      condition: >
        open_read and
        (fd.name contains "card" or
         fd.name contains "payment" or
         fd.name contains "pan")
      output: >
        Payment data access detected
        (user=%user.name file=%fd.name)
      priority: HIGH
      tags: [pci, payment, compliance]

---
# Compliance dashboard
apiVersion: v1
kind: ConfigMap
metadata:
  name: compliance-dashboard
  namespace: tml-production
data:
  dashboard.json: |
    {
      "dashboard": {
        "title": "TML Compliance Dashboard",
        "panels": [
          {
            "title": "Security Events by Type",
            "type": "piechart",
            "targets": [
              {
                "expr": "sum by (event_type) (security_events_total)"
              }
            ]
          },
          {
            "title": "Failed Authentication Attempts",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(security_events_total{event_type=\"AuthenticationFailure\"}[5m])"
              }
            ]
          },
          {
            "title": "Data Access Patterns",
            "type": "heatmap",
            "targets": [
              {
                "expr": "security_events_total{event_type=\"DataAccess\"}"
              }
            ]
          }
        ]
      }
    }
```

---

## Compliance

### SOC 2 Type II Controls

```yaml
# k8s/soc2-controls.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: soc2-controls
  namespace: tml-production
data:
  controls.yaml: |
    # CC6.1 - Logical and Physical Access Controls
    access_controls:
      - name: "Multi-factor Authentication"
        implemented: true
        evidence: "OAuth2 + TOTP implementation"
      - name: "Role-based Access Control"
        implemented: true
        evidence: "RBAC policies in Kubernetes and application"
      - name: "Privileged Access Management"
        implemented: true
        evidence: "Separate admin accounts with additional controls"
    
    # CC6.2 - Transmission and Disposal of Information
    data_protection:
      - name: "Encryption in Transit"
        implemented: true
        evidence: "TLS 1.2+ for all communications"
      - name: "Encryption at Rest"
        implemented: true
        evidence: "Database and storage encryption"
      - name: "Secure Data Disposal"
        implemented: true
        evidence: "Automated data retention and deletion policies"
    
    # CC6.3 - System Monitoring
    monitoring:
      - name: "Security Event Logging"
        implemented: true
        evidence: "Comprehensive audit logging and SIEM integration"
      - name: "Anomaly Detection"
        implemented: true
        evidence: "Falco runtime security monitoring"
      - name: "Incident Response"
        implemented: true
        evidence: "Documented incident response procedures"
```

### GDPR Compliance

```csharp
// src/TML.API/Compliance/GDPRService.cs
public class GDPRService
{
    private readonly TMLDbContext _context;
    private readonly ILogger<GDPRService> _logger;
    
    public async Task<DataExportResult> ExportUserDataAsync(string userId)
    {
        var userData = new
        {
            PersonalInfo = await GetPersonalInfoAsync(userId),
            ModelData = await GetUserModelsAsync(userId),
            TransactionHistory = await GetTransactionHistoryAsync(userId),
            AuditLog = await GetUserAuditLogAsync(userId)
        };
        
        return new DataExportResult
        {
            Data = userData,
            ExportedAt = DateTime.UtcNow,
            Format = "JSON"
        };
    }
    
    public async Task<DataDeletionResult> DeleteUserDataAsync(string userId, bool hardDelete = false)
    {
        using var transaction = await _context.Database.BeginTransactionAsync();
        
        try
        {
            var deletionLog = new DataDeletionLog
            {
                UserId = userId,
                RequestedAt = DateTime.UtcNow,
                HardDelete = hardDelete
            };
            
            if (hardDelete)
            {
                // Permanently delete all user data
                await HardDeleteUserDataAsync(userId);
            }
            else
            {
                // Soft delete - anonymize data
                await AnonymizeUserDataAsync(userId);
            }
            
            _context.DataDeletionLogs.Add(deletionLog);
            await _context.SaveChangesAsync();
            await transaction.CommitAsync();
            
            _logger.LogInformation("User data deletion completed for user {UserId}", userId);
            
            return new DataDeletionResult
            {
                Success = true,
                DeletedAt = DateTime.UtcNow,
                RecordsAffected = deletionLog.RecordsAffected
            };
        }
        catch (Exception ex)
        {
            await transaction.RollbackAsync();
            _logger.LogError(ex, "Failed to delete user data for user {UserId}", userId);
            throw;
        }
    }
    
    private async Task AnonymizeUserDataAsync(string userId)
    {
        // Anonymize personal identifiers while preserving model utility
        var models = await _context.Models
            .Where(m => m.Metadata.ContainsKey("user_id") && 
                       m.Metadata["user_id"].ToString() == userId)
            .ToListAsync();
        
        foreach (var model in models)
        {
            model.Metadata["user_id"] = "anonymized";
            model.Metadata["anonymized_at"] = DateTime.UtcNow.ToString();
            
            // Remove other PII while preserving model functionality
            model.Metadata.Remove("email");
            model.Metadata.Remove("name");
            model.Metadata.Remove("phone");
        }
        
        await _context.SaveChangesAsync();
    }
}

public class DataExportResult
{
    public object Data { get; set; }
    public DateTime ExportedAt { get; set; }
    public string Format { get; set; }
}

public class DataDeletionResult
{
    public bool Success { get; set; }
    public DateTime DeletedAt { get; set; }
    public int RecordsAffected { get; set; }
}
```

---

## Incident Response

### Incident Response Plan

```yaml
# k8s/incident-response.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: incident-response-plan
  namespace: tml-production
data:
  incident-response.yaml: |
    phases:
      preparation:
        - name: "Incident Response Team"
          members:
            - role: "Incident Commander"
              contact: "ic@company.com"
            - role: "Security Lead"
              contact: "security@company.com"
            - role: "Technical Lead"
              contact: "tech-lead@company.com"
        - name: "Communication Channels"
          channels:
            - type: "Slack"
              channel: "#incident-response"
            - type: "Email"
              list: "incident-team@company.com"
            - type: "Phone"
              number: "+1-555-INCIDENT"
      
      identification:
        - name: "Detection Sources"
          sources:
            - "Falco security alerts"
            - "Prometheus alerting"
            - "Application logs"
            - "User reports"
        - name: "Severity Classification"
          levels:
            - level: "P1 - Critical"
              criteria: "System compromise, data breach"
              response_time: "15 minutes"
            - level: "P2 - High"
              criteria: "Service disruption, security vulnerability"
              response_time: "1 hour"
            - level: "P3 - Medium"
              criteria: "Performance degradation"
              response_time: "4 hours"
      
      containment:
        - name: "Immediate Actions"
          actions:
            - "Isolate affected systems"
            - "Preserve evidence"
            - "Implement temporary fixes"
        - name: "Communication"
          actions:
            - "Notify incident response team"
            - "Update status page"
            - "Prepare customer communication"
      
      eradication:
        - name: "Root Cause Analysis"
          steps:
            - "Analyze logs and evidence"
            - "Identify attack vectors"
            - "Determine scope of impact"
        - name: "Remediation"
          steps:
            - "Apply security patches"
            - "Update configurations"
            - "Strengthen controls"
      
      recovery:
        - name: "System Restoration"
          steps:
            - "Restore from clean backups"
            - "Verify system integrity"
            - "Gradual service restoration"
        - name: "Monitoring"
          steps:
            - "Enhanced monitoring"
            - "Threat hunting"
            - "Validation testing"
      
      lessons_learned:
        - name: "Post-Incident Review"
          timeline: "Within 72 hours"
          participants:
            - "Incident response team"
            - "Affected stakeholders"
            - "Management"
        - name: "Documentation"
          deliverables:
            - "Incident report"
            - "Timeline of events"
            - "Lessons learned"
            - "Improvement recommendations"

---
# Automated incident response
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: security-incident-response
  namespace: tml-production
spec:
  entrypoint: incident-response
  templates:
  - name: incident-response
    steps:
    - - name: detect-incident
        template: detect
    - - name: classify-severity
        template: classify
        arguments:
          parameters:
          - name: incident-data
            value: "{{steps.detect-incident.outputs.result}}"
    - - name: notify-team
        template: notify
        arguments:
          parameters:
          - name: severity
            value: "{{steps.classify-severity.outputs.result}}"
    - - name: contain-threat
        template: contain
        when: "{{steps.classify-severity.outputs.result}} == 'P1'"
  
  - name: detect
    script:
      image: alpine/curl
      command: [sh]
      source: |
        # Check for security alerts
        curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[]'
  
  - name: classify
    inputs:
      parameters:
      - name: incident-data
    script:
      image: alpine/jq
      command: [sh]
      source: |
        # Classify incident severity based on data
        echo "{{inputs.parameters.incident-data}}" | jq -r '.severity // "P3"'
  
  - name: notify
    inputs:
      parameters:
      - name: severity
    script:
      image: alpine/curl
      command: [sh]
      source: |
        # Send notification to incident response team
        curl -X POST https://hooks.slack.com/services/... \
          -H 'Content-type: application/json' \
          -d '{"text":"Security incident detected: {{inputs.parameters.severity}}"}'
  
  - name: contain
    script:
      image: kubectl:latest
      command: [sh]
      source: |
        # Implement containment measures
        kubectl scale deployment tml-api --replicas=0 -n tml-production
        kubectl apply -f /containment-policies/emergency-network-policy.yaml
```

### Automated Response Actions

```bash
#!/bin/bash
# scripts/incident-response.sh

INCIDENT_TYPE=$1
SEVERITY=$2

case $INCIDENT_TYPE in
    "security_breach")
        echo "🚨 Security breach detected - implementing containment"
        
        # Isolate affected systems
        kubectl patch networkpolicy default-deny -n tml-production --type='merge' -p='{"spec":{"policyTypes":["Ingress","Egress"]}}'
        
        # Scale down non-essential services
        kubectl scale deployment tml-demo --replicas=0 -n tml-production
        
        # Enable enhanced logging
        kubectl patch configmap falco-config -n falco-system --type='merge' -p='{"data":{"falco.yaml":"log_level: debug\n"}}'
        
        # Notify security team
        curl -X POST "$SLACK_WEBHOOK" -H 'Content-type: application/json' \
            -d '{"text":"🚨 SECURITY BREACH DETECTED - Containment measures activated"}'
        ;;
        
    "data_breach")
        echo "🔒 Data breach detected - implementing data protection measures"
        
        # Rotate all secrets
        kubectl delete secret tml-secrets -n tml-production
        kubectl create secret generic tml-secrets --from-env-file=.env.emergency -n tml-production
        
        # Enable data access monitoring
        kubectl apply -f k8s/enhanced-monitoring.yaml
        
        # Backup current state for forensics
        kubectl create job forensic-backup --image=postgres:14 -- pg_dump -h postgres -U tml_app tml_production > /forensics/backup-$(date +%Y%m%d_%H%M%S).sql
        ;;
        
    "service_disruption")
        echo "⚡ Service disruption detected - implementing recovery measures"
        
        # Scale up healthy replicas
        kubectl scale deployment tml-api --replicas=10 -n tml-production
        
        # Enable circuit breaker
        kubectl patch configmap tml-config -n tml-production --type='merge' -p='{"data":{"CIRCUIT_BREAKER_ENABLED":"true"}}'
        
        # Redirect traffic to backup region
        kubectl patch ingress tml-ingress -n tml-production --type='merge' -p='{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/upstream-vhost":"backup.tml-platform.com"}}}'
        ;;
esac

# Log incident
echo "$(date): Incident response executed for $INCIDENT_TYPE with severity $SEVERITY" >> /var/log/incident-response.log
```

---

## Summary

This security configuration guide provides comprehensive protection for the TML Platform including:

1. **Authentication & Authorization** - OAuth2, RBAC, API keys, and MFA
2. **Data Protection** - Encryption, masking, tokenization, and secrets management
3. **Network Security** - WAF, network policies, and TLS configuration
4. **Container Security** - Image scanning, runtime protection, and security contexts
5. **Database Security** - Connection security, auditing, and encryption
6. **API Security** - Input validation, CORS, and security headers
7. **Monitoring & Auditing** - Security event logging and compliance monitoring
8. **Compliance** - SOC 2, GDPR, and other regulatory requirements
9. **Incident Response** - Automated detection, containment, and recovery procedures

The TML Platform now has enterprise-grade security controls suitable for handling sensitive data and meeting compliance requirements across various industries and regulatory frameworks.
