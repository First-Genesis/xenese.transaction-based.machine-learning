"""
TML SDK Exceptions
Custom exception classes for TML SDK operations
"""

class TMLException(Exception):
    """Base exception for all TML SDK errors"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class TMLConnectionError(TMLException):
    """Raised when connection to TML platform fails"""
    pass


class TMLAuthenticationError(TMLException):
    """Raised when authentication fails"""
    pass


class TMLValidationError(TMLException):
    """Raised when input validation fails"""
    pass


class TMLModelError(TMLException):
    """Raised when model operations fail"""
    pass


class TMLTransactionError(TMLException):
    """Raised when transaction processing fails"""
    pass


class TMLSpatialError(TMLException):
    """Raised when spatial inheritance operations fail"""
    pass


class TMLFederatedError(TMLException):
    """Raised when federated learning operations fail"""
    pass


class TMLMonitoringError(TMLException):
    """Raised when monitoring operations fail"""
    pass


class TMLConfigError(TMLException):
    """Raised when configuration is invalid"""
    pass


class TMLTimeoutError(TMLException):
    """Raised when operations timeout"""
    pass


class TMLRateLimitError(TMLException):
    """Raised when rate limits are exceeded"""
    pass


class TMLResourceNotFoundError(TMLException):
    """Raised when requested resource is not found"""
    pass


class TMLPermissionError(TMLException):
    """Raised when user lacks required permissions"""
    pass
