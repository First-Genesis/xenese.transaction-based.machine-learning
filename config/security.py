"""
TML Platform Security Configuration

Authentication, authorization, and security policies.
"""

import os
import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseSettings, Field
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


class SecuritySettings(BaseSettings):
    """Security configuration"""
    
    # JWT Configuration
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="JWT_SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # API Security
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")
    api_keys: List[str] = Field(default_factory=list, env="API_KEYS")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=1000, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # CORS
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    cors_methods: List[str] = Field(default=["*"], env="CORS_METHODS")
    cors_headers: List[str] = Field(default=["*"], env="CORS_HEADERS")
    
    # Security Headers
    enable_security_headers: bool = Field(default=True, env="ENABLE_SECURITY_HEADERS")
    
    # Encryption
    encryption_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="ENCRYPTION_KEY")
    
    class Config:
        env_file = ".env"


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security = HTTPBearer()


class SecurityManager:
    """Centralized security management"""
    
    def __init__(self, settings: SecuritySettings):
        self.settings = settings
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.settings.secret_key, algorithm=self.settings.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.settings.secret_key, algorithms=[self.settings.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key"""
        return api_key in self.settings.api_keys
    
    def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """Get current user from token"""
        token = credentials.credentials
        payload = self.verify_token(token)
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        return {"user_id": user_id, "payload": payload}


# Security middleware configurations
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
}

# Input validation patterns
VALIDATION_PATTERNS = {
    "model_id": r"^[a-zA-Z0-9_-]{1,64}$",
    "user_id": r"^[a-zA-Z0-9_-]{1,32}$",
    "session_id": r"^[a-zA-Z0-9_-]{1,64}$",
    "transaction_id": r"^[a-zA-Z0-9_-]{1,128}$"
}

# Rate limiting configurations
RATE_LIMIT_RULES = {
    "default": {"requests": 1000, "window": 60},
    "auth": {"requests": 10, "window": 60},
    "prediction": {"requests": 10000, "window": 60},
    "training": {"requests": 1000, "window": 60}
}

# Audit log configuration
AUDIT_EVENTS = {
    "model_created",
    "model_deleted", 
    "model_trained",
    "prediction_made",
    "user_login",
    "user_logout",
    "api_key_used",
    "security_violation"
}


class AuditLogger:
    """Security audit logging"""
    
    def __init__(self):
        self.events = []
    
    def log_event(self, event_type: str, user_id: Optional[str], details: Dict[str, Any]):
        """Log security event"""
        if event_type not in AUDIT_EVENTS:
            return
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details,
            "ip_address": details.get("ip_address"),
            "user_agent": details.get("user_agent")
        }
        
        self.events.append(event)
        
        # In production, this would write to a secure audit log
        print(f"AUDIT: {event}")
    
    def get_events(self, event_type: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict]:
        """Retrieve audit events"""
        events = self.events
        
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        
        if user_id:
            events = [e for e in events if e["user_id"] == user_id]
        
        return events


# Data sanitization
class DataSanitizer:
    """Input data sanitization"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Remove null bytes and control characters
        value = value.replace('\x00', '').strip()
        
        # Limit length
        if len(value) > max_length:
            raise ValueError(f"Input too long (max {max_length} characters)")
        
        return value
    
    @staticmethod
    def sanitize_features(features: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize feature dictionary"""
        if not isinstance(features, dict):
            raise ValueError("Features must be a dictionary")
        
        if len(features) > 1000:
            raise ValueError("Too many features (max 1000)")
        
        sanitized = {}
        for key, value in features.items():
            # Sanitize key
            if not isinstance(key, str) or len(key) > 100:
                raise ValueError("Invalid feature key")
            
            # Sanitize value
            if isinstance(value, (int, float)):
                if abs(value) > 1e10:
                    raise ValueError("Feature value too large")
                sanitized[key] = value
            elif isinstance(value, str):
                sanitized[key] = DataSanitizer.sanitize_string(value, 100)
            else:
                raise ValueError("Invalid feature value type")
        
        return sanitized


# Model access control
class ModelAccessControl:
    """Model-level access control"""
    
    def __init__(self):
        self.permissions = {}
    
    def grant_permission(self, user_id: str, model_id: str, permission: str):
        """Grant permission to user for model"""
        if user_id not in self.permissions:
            self.permissions[user_id] = {}
        
        if model_id not in self.permissions[user_id]:
            self.permissions[user_id][model_id] = set()
        
        self.permissions[user_id][model_id].add(permission)
    
    def check_permission(self, user_id: str, model_id: str, permission: str) -> bool:
        """Check if user has permission for model"""
        return (
            user_id in self.permissions and
            model_id in self.permissions[user_id] and
            permission in self.permissions[user_id][model_id]
        )
    
    def revoke_permission(self, user_id: str, model_id: str, permission: str):
        """Revoke permission from user for model"""
        if (user_id in self.permissions and 
            model_id in self.permissions[user_id]):
            self.permissions[user_id][model_id].discard(permission)


# Initialize security components
security_settings = SecuritySettings()
security_manager = SecurityManager(security_settings)
audit_logger = AuditLogger()
data_sanitizer = DataSanitizer()
model_access_control = ModelAccessControl()


# Security decorators
def require_auth(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        # Implementation would check for valid token
        return func(*args, **kwargs)
    return wrapper


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Implementation would check permission
            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(rule: str = "default"):
    """Decorator for rate limiting"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Implementation would check rate limits
            return func(*args, **kwargs)
        return wrapper
    return decorator
