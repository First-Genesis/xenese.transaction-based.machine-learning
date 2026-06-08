"""
TML Client Library

Production-grade client library for the TML platform supporting:
- Local processing mode
- Remote API mode
- Hybrid mode
- Distributed processing
- Authentication and security
- Caching and performance optimization

Copyright (c) 2024 First Genesis. All rights reserved.
"""

from .tml_client import (AuthenticationError, ClientError, ProcessingError,
                         ProcessingMode, ProcessingResult, TMLClient,
                         TMLConfig)

__all__ = [
    "TMLClient",
    "TMLConfig",
    "ProcessingMode",
    "ProcessingResult",
    "ClientError",
    "AuthenticationError",
    "ProcessingError",
]

# Version
__version__ = "3.0.0"
