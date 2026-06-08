# Security Hardening Guide

## Vulnerable Packages Disabled

The following packages have been disabled due to persistent security vulnerabilities:

### MLflow (DISABLED)
- **Reason**: Multiple unpatched RCE, path traversal, and authentication bypass vulnerabilities
- **Alternative**: Weights & Biases (wandb) for experiment tracking
- **If MLflow Required**: 
  - Deploy in isolated network segment
  - Enable authentication and authorization
  - Use reverse proxy with strict filtering
  - Regular security audits

### Ray Serve (DISABLED)  
- **Reason**: Arbitrary code execution via jobs API, authentication disabled by default
- **Alternative**: Direct FastAPI + Uvicorn for model serving
- **If Ray Required**:
  - Enable token authentication
  - Disable jobs API
  - Network isolation
  - Strict firewall rules

### BentoML (DISABLED)
- **Reason**: Persistent deserialization RCE vulnerabilities
- **Alternative**: Custom FastAPI endpoints for model serving
- **If BentoML Required**:
  - Sandbox execution environment
  - Input validation and sanitization
  - Container isolation

### Transformers (DISABLED)
- **Reason**: Multiple deserialization vulnerabilities
- **Alternative**: Use with strict input validation or consider ONNX models
- **If Transformers Required**:
  - Validate all model files
  - Use trusted model sources only
  - Sandbox model loading

## Security Controls Implemented

1. **Package Replacement**: Vulnerable packages replaced with secure alternatives
2. **Dependency Reduction**: Removed non-essential packages with security issues
3. **Documentation**: Clear guidance for secure usage if vulnerable packages needed

## Production Deployment Security

1. **Network Isolation**: Deploy services in isolated network segments
2. **Authentication**: Enable strong authentication for all services
3. **Input Validation**: Strict validation of all external inputs
4. **Monitoring**: Continuous security monitoring and alerting
5. **Updates**: Regular security updates and vulnerability scanning
