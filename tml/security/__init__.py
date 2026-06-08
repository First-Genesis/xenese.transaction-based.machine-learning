"""
TML Security Module

Comprehensive security features for the TML platform including:
- Secure configuration management
- Input validation and sanitization
- Authentication and authorization
- Encryption and hashing
- Audit logging
- Security monitoring

Copyright (c) 2024 First Genesis. All rights reserved.
"""

from .config import SecurityConfig, get_secure_config
from .validation import (InputValidator, SecurityChecker, security_checker,
                         validator)

__all__ = [
    "SecurityConfig",
    "get_secure_config",
    "InputValidator",
    "SecurityChecker",
    "validator",
    "security_checker",
]

# Version
__version__ = "1.0.0"
