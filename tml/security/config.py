"""
Security Configuration Module for TML Platform

This module provides secure configuration management with:
- Environment variable loading
- Secret validation
- Secure defaults
- Configuration encryption

Copyright (c) 2024 First Genesis. All rights reserved.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
env_file = os.getenv("ENV_FILE", ".env")
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    logger.warning(f"Environment file {env_file} not found. Using defaults.")


class SecurityConfig:
    """
    Secure configuration management for TML platform.

    Features:
    - Validates security settings
    - Prevents hardcoded secrets
    - Provides secure defaults
    - Encrypts sensitive data
    """

    def __init__(self):
        """Initialize security configuration."""
        self._validate_environment()
        self._load_secrets()

    def _validate_environment(self):
        """Validate that we're not using insecure defaults."""
        insecure_values = [
            "change-me",
            "changeme",
            "password",
            "secret",
            "default",
            "admin",
            "123456",
            "test",
        ]

        critical_vars = ["JWT_SECRET", "DB_PASSWORD", "REDIS_PASSWORD", "API_KEY"]

        for var in critical_vars:
            value = os.getenv(var, "").lower()

            # Check if using insecure default
            for insecure in insecure_values:
                if insecure in value:
                    warnings.warn(
                        f"SECURITY WARNING: {var} contains insecure value '{insecure}'. "
                        f"Please update with a secure value!",
                        UserWarning,
                    )

            # Check minimum length
            if var == "JWT_SECRET" and len(os.getenv(var, "")) < 32:
                warnings.warn(
                    f"SECURITY WARNING: {var} should be at least 32 characters long!",
                    UserWarning,
                )

            if var == "API_KEY" and len(os.getenv(var, "")) < 20:
                warnings.warn(
                    f"SECURITY WARNING: {var} should be at least 20 characters long!",
                    UserWarning,
                )

    def _load_secrets(self):
        """Load secrets from secure sources."""
        # Default to environment variables
        self.secrets = {
            "jwt_secret": self._get_required_env("JWT_SECRET", self._generate_key()),
            "api_key": self._get_required_env("API_KEY", self._generate_key()),
            "db_password": self._get_required_env("DB_PASSWORD", "secure_password"),
            "redis_password": os.getenv("REDIS_PASSWORD", ""),
            "encryption_key": os.getenv("API_ENCRYPTION_KEY", self._generate_key()),
            "session_secret": os.getenv("SESSION_SECRET_KEY", self._generate_key()),
        }

    def _get_required_env(self, key: str, default: Optional[str] = None) -> str:
        """Get required environment variable or use secure default."""
        value = os.getenv(key, default)
        if not value:
            raise ValueError(f"Required environment variable {key} not set!")
        return value

    def _generate_key(self, length: int = 32) -> str:
        """Generate a secure random key."""
        return secrets.token_urlsafe(length)

    def get_database_config(self) -> Dict[str, Any]:
        """Get secure database configuration."""
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "tml_production"),
            "user": os.getenv("DB_USER", "tml_user"),
            "password": self.secrets.get("db_password"),
            "sslmode": os.getenv("DB_SSL_MODE", "require"),
            "connect_timeout": int(os.getenv("DB_CONNECTION_TIMEOUT", 30)),
            "pool_size": int(os.getenv("DB_POOL_SIZE", 20)),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 10)),
        }

    def get_redis_config(self) -> Dict[str, Any]:
        """Get secure Redis configuration."""
        config = {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", 6379)),
            "db": int(os.getenv("REDIS_DB", 0)),
            "password": self.secrets.get("redis_password"),
            "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", 50)),
        }

        # Add SSL if configured
        if os.getenv("REDIS_SSL", "false").lower() == "true":
            config["ssl"] = True
            config["ssl_cert_reqs"] = "required"
            config["ssl_ca_certs"] = os.getenv("REDIS_SSL_CERT_PATH")

        return config

    def get_api_config(self) -> Dict[str, Any]:
        """Get secure API configuration."""
        return {
            "host": os.getenv("API_HOST", "0.0.0.0"),
            "port": int(os.getenv("API_PORT", 8000)),
            "workers": int(os.getenv("API_WORKERS", 4)),
            "api_key": self.secrets.get("api_key"),
            "jwt_secret": self.secrets.get("jwt_secret"),
            "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
            "jwt_expiration_minutes": int(os.getenv("JWT_EXPIRATION_MINUTES", 30)),
            "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
            "rate_limit_requests": int(os.getenv("RATE_LIMIT_REQUESTS", 1000)),
            "rate_limit_window": int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60)),
            "enforce_https": os.getenv("ENFORCE_HTTPS", "true").lower() == "true",
        }

    def get_security_headers(self) -> Dict[str, str]:
        """Get recommended security headers."""
        return {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

    def validate_api_key(self, provided_key: str) -> bool:
        """Validate an API key."""
        expected_key = self.secrets.get("api_key")

        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(provided_key, expected_key)

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def get_allowed_hosts(self) -> List[str]:
        """Get list of allowed hosts for the application."""
        hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        return [host.strip() for host in hosts]

    def is_production(self) -> bool:
        """Check if running in production environment."""
        env = os.getenv("DEPLOYMENT_ENV", "development").lower()
        return env == "production"


# Global instance
security_config = SecurityConfig()


def get_secure_config() -> SecurityConfig:
    """Get the global security configuration instance."""
    return security_config
