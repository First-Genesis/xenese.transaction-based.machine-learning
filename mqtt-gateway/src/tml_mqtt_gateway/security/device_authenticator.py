"""
Device Authenticator
Advanced authentication system supporting multiple authentication methods
"""

import asyncio
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import structlog

from .certificate_manager import CertificateManager
from ..config import TMLGatewayConfig
from ..device_manager import DeviceManager


logger = structlog.get_logger(__name__)


class AuthMethod(Enum):
    """Authentication methods supported"""
    USERNAME_PASSWORD = "username_password"
    X509_CERTIFICATE = "x509_certificate"
    JWT_TOKEN = "jwt_token"
    API_KEY = "api_key"
    HMAC_SIGNATURE = "hmac_signature"


class AuthResult:
    """Authentication result"""
    
    def __init__(
        self,
        success: bool,
        device_id: str = None,
        auth_method: AuthMethod = None,
        organization: str = None,
        permissions: List[str] = None,
        error_message: str = None,
        metadata: Dict[str, Any] = None
    ):
        self.success = success
        self.device_id = device_id
        self.auth_method = auth_method
        self.organization = organization
        self.permissions = permissions or []
        self.error_message = error_message
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()


class DeviceAuthenticator:
    """
    Advanced Device Authentication System
    
    Features:
    - Multiple authentication methods
    - Certificate-based authentication
    - JWT token validation
    - API key management
    - HMAC signature verification
    - Rate limiting and brute force protection
    - Multi-tenant support
    """
    
    def __init__(
        self,
        config: TMLGatewayConfig,
        certificate_manager: CertificateManager,
        device_manager: DeviceManager
    ):
        self.config = config
        self.certificate_manager = certificate_manager
        self.device_manager = device_manager
        
        # Authentication configuration
        self.jwt_secret = config.gateway.api_key or "default_jwt_secret"
        self.jwt_algorithm = "HS256"
        self.jwt_expiry_hours = 24
        
        # Rate limiting
        self.auth_attempts = {}  # device_id -> [timestamps]
        self.max_attempts_per_hour = 10
        self.lockout_duration_minutes = 30
        self.locked_devices = {}  # device_id -> lockout_until
        
        # API key storage (in production, use database)
        self.api_keys = {}  # api_key -> device_info
        
        # HMAC secrets (in production, use secure key management)
        self.hmac_secrets = {}  # device_id -> secret
        
        self.logger = logger.bind(component="device_authenticator")
    
    async def authenticate_device(
        self,
        auth_method: AuthMethod,
        credentials: Dict[str, Any],
        client_ip: str = None
    ) -> AuthResult:
        """
        Authenticate device using specified method
        
        Args:
            auth_method: Authentication method to use
            credentials: Authentication credentials
            client_ip: Client IP address for rate limiting
            
        Returns:
            AuthResult: Authentication result
        """
        try:
            device_id = credentials.get('device_id') or credentials.get('username')
            
            # Check if device is locked out
            if await self._is_device_locked(device_id):
                return AuthResult(
                    success=False,
                    device_id=device_id,
                    error_message="Device is temporarily locked due to too many failed attempts"
                )
            
            # Record authentication attempt
            await self._record_auth_attempt(device_id, client_ip)
            
            # Perform authentication based on method
            if auth_method == AuthMethod.USERNAME_PASSWORD:
                result = await self._authenticate_username_password(credentials)
            elif auth_method == AuthMethod.X509_CERTIFICATE:
                result = await self._authenticate_x509_certificate(credentials)
            elif auth_method == AuthMethod.JWT_TOKEN:
                result = await self._authenticate_jwt_token(credentials)
            elif auth_method == AuthMethod.API_KEY:
                result = await self._authenticate_api_key(credentials)
            elif auth_method == AuthMethod.HMAC_SIGNATURE:
                result = await self._authenticate_hmac_signature(credentials)
            else:
                return AuthResult(
                    success=False,
                    error_message=f"Unsupported authentication method: {auth_method.value}"
                )
            
            # Handle failed authentication
            if not result.success:
                await self._handle_failed_auth(device_id)
            else:
                await self._handle_successful_auth(device_id)
            
            return result
            
        except Exception as e:
            self.logger.error("Authentication error", error=str(e))
            return AuthResult(
                success=False,
                error_message=f"Authentication error: {str(e)}"
            )
    
    async def _authenticate_username_password(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate using username and password"""
        username = credentials.get('username')
        password = credentials.get('password')
        
        if not username or not password:
            return AuthResult(
                success=False,
                error_message="Username and password are required"
            )
        
        # Get device from database
        device = await self.device_manager.get_device(username)
        if not device:
            return AuthResult(
                success=False,
                device_id=username,
                error_message="Device not found"
            )
        
        # Verify password (in production, use proper password hashing)
        stored_password = device.get('metadata', {}).get('password')
        if not stored_password or not self._verify_password(password, stored_password):
            return AuthResult(
                success=False,
                device_id=username,
                error_message="Invalid credentials"
            )
        
        return AuthResult(
            success=True,
            device_id=username,
            auth_method=AuthMethod.USERNAME_PASSWORD,
            organization=device.get('metadata', {}).get('organization'),
            permissions=self._get_device_permissions(device),
            metadata={'device_type': device.get('device_type')}
        )
    
    async def _authenticate_x509_certificate(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate using X.509 certificate"""
        cert_pem = credentials.get('certificate')
        
        if not cert_pem:
            return AuthResult(
                success=False,
                error_message="Certificate is required"
            )
        
        # Validate certificate
        validation_result = await self.certificate_manager.validate_device_certificate(cert_pem)
        
        if not validation_result['valid']:
            return AuthResult(
                success=False,
                error_message=f"Certificate validation failed: {validation_result['reason']}"
            )
        
        device_id = validation_result['device_id']
        
        # Get device from database
        device = await self.device_manager.get_device(device_id)
        if not device:
            return AuthResult(
                success=False,
                device_id=device_id,
                error_message="Device not registered"
            )
        
        return AuthResult(
            success=True,
            device_id=device_id,
            auth_method=AuthMethod.X509_CERTIFICATE,
            organization=device.get('metadata', {}).get('organization'),
            permissions=self._get_device_permissions(device),
            metadata={
                'certificate_serial': validation_result['serial_number'],
                'certificate_expiry': validation_result['not_valid_after'].isoformat(),
                'device_type': device.get('device_type')
            }
        )
    
    async def _authenticate_jwt_token(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate using JWT token"""
        token = credentials.get('token')
        
        if not token:
            return AuthResult(
                success=False,
                error_message="JWT token is required"
            )
        
        try:
            # Decode and verify JWT token
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            device_id = payload.get('device_id')
            if not device_id:
                return AuthResult(
                    success=False,
                    error_message="Invalid token: missing device_id"
                )
            
            # Check token expiration
            exp = payload.get('exp')
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return AuthResult(
                    success=False,
                    device_id=device_id,
                    error_message="Token has expired"
                )
            
            # Get device from database
            device = await self.device_manager.get_device(device_id)
            if not device:
                return AuthResult(
                    success=False,
                    device_id=device_id,
                    error_message="Device not found"
                )
            
            return AuthResult(
                success=True,
                device_id=device_id,
                auth_method=AuthMethod.JWT_TOKEN,
                organization=payload.get('organization'),
                permissions=payload.get('permissions', []),
                metadata={
                    'token_issued_at': datetime.utcfromtimestamp(payload.get('iat', 0)).isoformat(),
                    'device_type': device.get('device_type')
                }
            )
            
        except jwt.InvalidTokenError as e:
            return AuthResult(
                success=False,
                error_message=f"Invalid JWT token: {str(e)}"
            )
    
    async def _authenticate_api_key(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate using API key"""
        api_key = credentials.get('api_key')
        
        if not api_key:
            return AuthResult(
                success=False,
                error_message="API key is required"
            )
        
        # Validate API key
        device_info = self.api_keys.get(api_key)
        if not device_info:
            return AuthResult(
                success=False,
                error_message="Invalid API key"
            )
        
        device_id = device_info['device_id']
        
        # Check if API key is expired
        if 'expires_at' in device_info:
            if datetime.utcnow() > device_info['expires_at']:
                return AuthResult(
                    success=False,
                    device_id=device_id,
                    error_message="API key has expired"
                )
        
        return AuthResult(
            success=True,
            device_id=device_id,
            auth_method=AuthMethod.API_KEY,
            organization=device_info.get('organization'),
            permissions=device_info.get('permissions', []),
            metadata={'api_key_created': device_info.get('created_at')}
        )
    
    async def _authenticate_hmac_signature(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate using HMAC signature"""
        device_id = credentials.get('device_id')
        timestamp = credentials.get('timestamp')
        signature = credentials.get('signature')
        message = credentials.get('message', '')
        
        if not all([device_id, timestamp, signature]):
            return AuthResult(
                success=False,
                error_message="Device ID, timestamp, and signature are required"
            )
        
        # Check timestamp (prevent replay attacks)
        try:
            request_time = datetime.utcfromtimestamp(int(timestamp))
            if abs((datetime.utcnow() - request_time).total_seconds()) > 300:  # 5 minutes
                return AuthResult(
                    success=False,
                    device_id=device_id,
                    error_message="Request timestamp is too old"
                )
        except (ValueError, TypeError):
            return AuthResult(
                success=False,
                device_id=device_id,
                error_message="Invalid timestamp format"
            )
        
        # Get device secret
        device_secret = self.hmac_secrets.get(device_id)
        if not device_secret:
            return AuthResult(
                success=False,
                device_id=device_id,
                error_message="Device not configured for HMAC authentication"
            )
        
        # Verify HMAC signature
        expected_signature = hmac.new(
            device_secret.encode('utf-8'),
            f"{device_id}{timestamp}{message}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return AuthResult(
                success=False,
                device_id=device_id,
                error_message="Invalid HMAC signature"
            )
        
        # Get device from database
        device = await self.device_manager.get_device(device_id)
        if not device:
            return AuthResult(
                success=False,
                device_id=device_id,
                error_message="Device not found"
            )
        
        return AuthResult(
            success=True,
            device_id=device_id,
            auth_method=AuthMethod.HMAC_SIGNATURE,
            organization=device.get('metadata', {}).get('organization'),
            permissions=self._get_device_permissions(device),
            metadata={
                'request_timestamp': request_time.isoformat(),
                'device_type': device.get('device_type')
            }
        )
    
    async def generate_jwt_token(
        self,
        device_id: str,
        organization: str = None,
        permissions: List[str] = None,
        expiry_hours: int = None
    ) -> str:
        """Generate JWT token for device"""
        expiry_hours = expiry_hours or self.jwt_expiry_hours
        
        payload = {
            'device_id': device_id,
            'organization': organization,
            'permissions': permissions or [],
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours)
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        self.logger.info("Generated JWT token",
                        device_id=device_id,
                        expiry_hours=expiry_hours)
        
        return token
    
    async def create_api_key(
        self,
        device_id: str,
        organization: str = None,
        permissions: List[str] = None,
        expiry_days: int = None
    ) -> str:
        """Create API key for device"""
        import secrets
        
        api_key = f"tml_{secrets.token_urlsafe(32)}"
        
        device_info = {
            'device_id': device_id,
            'organization': organization,
            'permissions': permissions or [],
            'created_at': datetime.utcnow().isoformat()
        }
        
        if expiry_days:
            device_info['expires_at'] = datetime.utcnow() + timedelta(days=expiry_days)
        
        self.api_keys[api_key] = device_info
        
        self.logger.info("Created API key",
                        device_id=device_id,
                        expiry_days=expiry_days)
        
        return api_key
    
    async def set_hmac_secret(self, device_id: str, secret: str) -> None:
        """Set HMAC secret for device"""
        self.hmac_secrets[device_id] = secret
        
        self.logger.info("Set HMAC secret", device_id=device_id)
    
    def _verify_password(self, password: str, stored_password: str) -> bool:
        """Verify password (implement proper hashing in production)"""
        # In production, use bcrypt or similar
        return password == stored_password
    
    def _get_device_permissions(self, device: Dict[str, Any]) -> List[str]:
        """Get device permissions based on device type and metadata"""
        device_type = device.get('device_type', 'unknown')
        
        # Default permissions based on device type
        if device_type == 'sensor':
            return ['telemetry:publish', 'status:publish']
        elif device_type == 'actuator':
            return ['telemetry:publish', 'status:publish', 'commands:subscribe']
        elif device_type == 'gateway':
            return ['telemetry:publish', 'status:publish', 'devices:manage']
        else:
            return ['telemetry:publish']
    
    async def _is_device_locked(self, device_id: str) -> bool:
        """Check if device is locked due to failed attempts"""
        if not device_id:
            return False
        
        lockout_until = self.locked_devices.get(device_id)
        if lockout_until and datetime.utcnow() < lockout_until:
            return True
        
        # Remove expired lockouts
        if lockout_until and datetime.utcnow() >= lockout_until:
            del self.locked_devices[device_id]
        
        return False
    
    async def _record_auth_attempt(self, device_id: str, client_ip: str) -> None:
        """Record authentication attempt for rate limiting"""
        if not device_id:
            return
        
        now = datetime.utcnow()
        
        # Initialize attempts list if not exists
        if device_id not in self.auth_attempts:
            self.auth_attempts[device_id] = []
        
        # Add current attempt
        self.auth_attempts[device_id].append(now)
        
        # Clean old attempts (older than 1 hour)
        cutoff_time = now - timedelta(hours=1)
        self.auth_attempts[device_id] = [
            attempt for attempt in self.auth_attempts[device_id]
            if attempt > cutoff_time
        ]
    
    async def _handle_failed_auth(self, device_id: str) -> None:
        """Handle failed authentication attempt"""
        if not device_id:
            return
        
        attempts = self.auth_attempts.get(device_id, [])
        
        if len(attempts) >= self.max_attempts_per_hour:
            # Lock device
            lockout_until = datetime.utcnow() + timedelta(minutes=self.lockout_duration_minutes)
            self.locked_devices[device_id] = lockout_until
            
            self.logger.warning("Device locked due to failed attempts",
                              device_id=device_id,
                              attempts=len(attempts),
                              lockout_until=lockout_until)
    
    async def _handle_successful_auth(self, device_id: str) -> None:
        """Handle successful authentication"""
        if not device_id:
            return
        
        # Clear failed attempts on successful auth
        if device_id in self.auth_attempts:
            del self.auth_attempts[device_id]
        
        # Remove lockout if exists
        if device_id in self.locked_devices:
            del self.locked_devices[device_id]
    
    def get_status(self) -> Dict[str, Any]:
        """Get authenticator status"""
        return {
            'locked_devices': len(self.locked_devices),
            'active_api_keys': len(self.api_keys),
            'hmac_configured_devices': len(self.hmac_secrets),
            'max_attempts_per_hour': self.max_attempts_per_hour,
            'lockout_duration_minutes': self.lockout_duration_minutes
        }
