"""
Device Provisioner
Zero-touch device onboarding and automated provisioning
"""

import asyncio
import json
import secrets
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

import structlog
import qrcode
import io
import base64

from ..config import TMLGatewayConfig
from ..device_manager import DeviceManager
from ..security.certificate_manager import CertificateManager
from ..security.device_authenticator import DeviceAuthenticator
from ..security.encryption_manager import EncryptionManager


logger = structlog.get_logger(__name__)


class ProvisioningMethod(Enum):
    """Device provisioning methods"""
    QR_CODE = "qr_code"
    NFC = "nfc"
    BLUETOOTH = "bluetooth"
    PRE_SHARED_KEY = "pre_shared_key"
    CERTIFICATE = "certificate"
    API = "api"


class ProvisioningStatus(Enum):
    """Provisioning status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class DeviceProvisioner:
    """
    Zero-Touch Device Provisioning System
    
    Features:
    - Multiple provisioning methods (QR, NFC, Bluetooth, PSK)
    - Automatic device registration and authentication setup
    - Certificate generation and distribution
    - Secure credential delivery
    - Bulk provisioning support
    - Template-based configuration
    - Audit trail and compliance
    """
    
    def __init__(
        self,
        config: TMLGatewayConfig,
        device_manager: DeviceManager,
        certificate_manager: CertificateManager,
        authenticator: DeviceAuthenticator,
        encryption_manager: EncryptionManager
    ):
        self.config = config
        self.device_manager = device_manager
        self.certificate_manager = certificate_manager
        self.authenticator = authenticator
        self.encryption_manager = encryption_manager
        
        # Provisioning configuration
        self.provisioning_timeout_minutes = 30
        self.max_provision_attempts = 3
        
        # Provisioning sessions
        self.provisioning_sessions = {}  # session_id -> session_data
        
        # Device templates
        self.device_templates = self._load_device_templates()
        
        # Provisioning statistics
        self.stats = {
            'total_provisioned': 0,
            'successful': 0,
            'failed': 0,
            'in_progress': 0
        }
        
        self.logger = logger.bind(component="device_provisioner")
    
    async def initialize(self) -> None:
        """Initialize device provisioner"""
        try:
            self.logger.info("Device provisioner initialized")
            
            # Start provisioning monitor
            asyncio.create_task(self._provisioning_monitor())
            
        except Exception as e:
            self.logger.error("Failed to initialize provisioner", error=str(e))
            raise
    
    async def create_provisioning_session(
        self,
        device_type: str,
        organization: str = None,
        template_id: str = None,
        method: ProvisioningMethod = ProvisioningMethod.QR_CODE,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create new provisioning session
        
        Args:
            device_type: Type of device to provision
            organization: Organization for multi-tenancy
            template_id: Device template to use
            method: Provisioning method
            metadata: Additional metadata
            
        Returns:
            Provisioning session details
        """
        try:
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Generate provisioning token
            provisioning_token = secrets.token_urlsafe(32)
            
            # Create session data
            session_data = {
                'session_id': session_id,
                'device_type': device_type,
                'organization': organization or 'default',
                'template_id': template_id,
                'method': method.value,
                'status': ProvisioningStatus.PENDING.value,
                'provisioning_token': provisioning_token,
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(minutes=self.provisioning_timeout_minutes),
                'attempts': 0,
                'metadata': metadata or {}
            }
            
            # Apply template if specified
            if template_id:
                template = self.device_templates.get(template_id)
                if template:
                    session_data['configuration'] = template['configuration']
                    session_data['permissions'] = template['permissions']
            
            # Store session
            self.provisioning_sessions[session_id] = session_data
            
            # Generate provisioning payload based on method
            provisioning_payload = await self._generate_provisioning_payload(
                session_data,
                method
            )
            
            self.logger.info("Created provisioning session",
                           session_id=session_id,
                           device_type=device_type,
                           method=method.value)
            
            self.stats['in_progress'] += 1
            
            return {
                'session_id': session_id,
                'provisioning_url': provisioning_payload.get('url'),
                'provisioning_data': provisioning_payload.get('data'),
                'qr_code': provisioning_payload.get('qr_code'),
                'expires_at': session_data['expires_at'].isoformat(),
                'method': method.value
            }
            
        except Exception as e:
            self.logger.error("Failed to create provisioning session", error=str(e))
            raise
    
    async def _generate_provisioning_payload(
        self,
        session_data: Dict[str, Any],
        method: ProvisioningMethod
    ) -> Dict[str, Any]:
        """Generate provisioning payload based on method"""
        base_url = f"https://tml-gateway.local/provision"
        
        provisioning_data = {
            'session_id': session_data['session_id'],
            'token': session_data['provisioning_token'],
            'gateway_url': self.config.gateway.api_host,
            'mqtt_broker': self.config.mqtt.host,
            'mqtt_port': self.config.mqtt.port
        }
        
        if method == ProvisioningMethod.QR_CODE:
            # Generate QR code
            provisioning_url = f"{base_url}?session={session_data['session_id']}&token={session_data['provisioning_token']}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_url)
            qr.make(fit=True)
            
            # Convert QR code to base64 image
            img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return {
                'url': provisioning_url,
                'qr_code': f"data:image/png;base64,{img_base64}",
                'data': provisioning_data
            }
            
        elif method == ProvisioningMethod.PRE_SHARED_KEY:
            # Generate PSK
            psk = secrets.token_hex(32)
            provisioning_data['psk'] = psk
            
            # Store PSK for later verification
            session_data['psk'] = psk
            
            return {
                'data': provisioning_data,
                'psk': psk
            }
            
        elif method == ProvisioningMethod.API:
            # Return raw provisioning data for API-based provisioning
            return {
                'url': f"{base_url}/api",
                'data': provisioning_data
            }
            
        else:
            return {'data': provisioning_data}
    
    async def provision_device(
        self,
        session_id: str,
        device_id: str,
        device_info: Dict[str, Any],
        provisioning_token: str
    ) -> Dict[str, Any]:
        """
        Provision a device using session
        
        Args:
            session_id: Provisioning session ID
            device_id: Unique device identifier
            device_info: Device information
            provisioning_token: Provisioning token for verification
            
        Returns:
            Provisioning result with credentials
        """
        try:
            # Validate session
            session_data = self.provisioning_sessions.get(session_id)
            if not session_data:
                raise ValueError("Invalid provisioning session")
            
            # Check session status
            if session_data['status'] != ProvisioningStatus.PENDING.value:
                raise ValueError(f"Session status is {session_data['status']}")
            
            # Check expiration
            if datetime.utcnow() > session_data['expires_at']:
                session_data['status'] = ProvisioningStatus.EXPIRED.value
                raise ValueError("Provisioning session has expired")
            
            # Verify token
            if provisioning_token != session_data['provisioning_token']:
                session_data['attempts'] += 1
                if session_data['attempts'] >= self.max_provision_attempts:
                    session_data['status'] = ProvisioningStatus.FAILED.value
                raise ValueError("Invalid provisioning token")
            
            # Update session status
            session_data['status'] = ProvisioningStatus.IN_PROGRESS.value
            session_data['device_id'] = device_id
            
            # Merge device info with template configuration
            final_device_info = {
                'device_id': device_id,
                'device_type': session_data['device_type'],
                'device_name': device_info.get('device_name', device_id),
                'manufacturer': device_info.get('manufacturer'),
                'model': device_info.get('model'),
                'firmware_version': device_info.get('firmware_version'),
                'metadata': {
                    **session_data.get('configuration', {}),
                    **device_info.get('metadata', {}),
                    'organization': session_data['organization'],
                    'provisioned_at': datetime.utcnow().isoformat(),
                    'provisioning_session': session_id
                }
            }
            
            # Register device
            await self.device_manager.register_device(final_device_info)
            
            # Generate credentials based on provisioning method
            credentials = await self._generate_device_credentials(
                device_id,
                session_data
            )
            
            # Update session status
            session_data['status'] = ProvisioningStatus.COMPLETED.value
            session_data['completed_at'] = datetime.utcnow()
            
            # Update statistics
            self.stats['total_provisioned'] += 1
            self.stats['successful'] += 1
            self.stats['in_progress'] -= 1
            
            self.logger.info("Device provisioned successfully",
                           session_id=session_id,
                           device_id=device_id,
                           device_type=session_data['device_type'])
            
            return {
                'success': True,
                'device_id': device_id,
                'credentials': credentials,
                'configuration': session_data.get('configuration', {}),
                'mqtt_broker': self.config.mqtt.host,
                'mqtt_port': self.config.mqtt.port,
                'gateway_url': f"http://{self.config.gateway.api_host}:{self.config.gateway.api_port}"
            }
            
        except Exception as e:
            self.logger.error("Failed to provision device",
                            session_id=session_id,
                            device_id=device_id,
                            error=str(e))
            
            # Update statistics
            if session_data and session_data['status'] == ProvisioningStatus.IN_PROGRESS.value:
                session_data['status'] = ProvisioningStatus.FAILED.value
                self.stats['failed'] += 1
                self.stats['in_progress'] -= 1
            
            raise
    
    async def _generate_device_credentials(
        self,
        device_id: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate device credentials"""
        credentials = {
            'device_id': device_id,
            'auth_methods': []
        }
        
        # Generate username/password
        password = secrets.token_urlsafe(16)
        credentials['username'] = device_id
        credentials['password'] = password
        credentials['auth_methods'].append('username_password')
        
        # Store password (in production, hash it)
        device = await self.device_manager.get_device(device_id)
        if device:
            device['metadata']['password'] = password
            await self.device_manager.register_device(device)
        
        # Generate certificate if requested
        if session_data.get('generate_certificate', True):
            cert_pem, key_pem, ca_chain = await self.certificate_manager.generate_device_certificate(
                device_id=device_id,
                device_type=session_data['device_type'],
                organization=session_data['organization']
            )
            
            credentials['certificate'] = cert_pem.decode('utf-8')
            credentials['private_key'] = key_pem.decode('utf-8')
            credentials['ca_chain'] = ca_chain.decode('utf-8')
            credentials['auth_methods'].append('x509_certificate')
        
        # Generate API key
        api_key = await self.authenticator.create_api_key(
            device_id=device_id,
            organization=session_data['organization'],
            permissions=session_data.get('permissions', [])
        )
        
        credentials['api_key'] = api_key
        credentials['auth_methods'].append('api_key')
        
        # Generate encryption key
        encryption_key = self.encryption_manager.generate_device_key(device_id)
        credentials['encryption_key'] = base64.b64encode(encryption_key).decode('utf-8')
        
        # Generate JWT token for initial connection
        jwt_token = await self.authenticator.generate_jwt_token(
            device_id=device_id,
            organization=session_data['organization'],
            permissions=session_data.get('permissions', []),
            expiry_hours=24
        )
        
        credentials['jwt_token'] = jwt_token
        credentials['auth_methods'].append('jwt_token')
        
        return credentials
    
    async def bulk_provision_devices(
        self,
        device_list: List[Dict[str, Any]],
        template_id: str = None,
        organization: str = None
    ) -> List[Dict[str, Any]]:
        """
        Provision multiple devices in bulk
        
        Args:
            device_list: List of device information
            template_id: Template to apply to all devices
            organization: Organization for all devices
            
        Returns:
            List of provisioning results
        """
        results = []
        
        for device_info in device_list:
            try:
                # Create provisioning session for each device
                session = await self.create_provisioning_session(
                    device_type=device_info.get('device_type', 'sensor'),
                    organization=organization,
                    template_id=template_id,
                    method=ProvisioningMethod.API
                )
                
                # Provision device
                result = await self.provision_device(
                    session_id=session['session_id'],
                    device_id=device_info['device_id'],
                    device_info=device_info,
                    provisioning_token=self.provisioning_sessions[session['session_id']]['provisioning_token']
                )
                
                results.append({
                    'device_id': device_info['device_id'],
                    'success': True,
                    'credentials': result['credentials']
                })
                
            except Exception as e:
                results.append({
                    'device_id': device_info.get('device_id', 'unknown'),
                    'success': False,
                    'error': str(e)
                })
        
        successful = sum(1 for r in results if r['success'])
        self.logger.info("Bulk provisioning completed",
                        total=len(device_list),
                        successful=successful)
        
        return results
    
    def _load_device_templates(self) -> Dict[str, Any]:
        """Load device configuration templates"""
        return {
            'temperature_sensor': {
                'device_type': 'sensor',
                'configuration': {
                    'sampling_rate': 60,
                    'data_format': 'json',
                    'topics': ['telemetry', 'status'],
                    'qos': 1
                },
                'permissions': ['telemetry:publish', 'status:publish']
            },
            'smart_camera': {
                'device_type': 'camera',
                'configuration': {
                    'resolution': '1920x1080',
                    'fps': 30,
                    'encoding': 'h264',
                    'topics': ['telemetry', 'status', 'alerts'],
                    'qos': 1
                },
                'permissions': ['telemetry:publish', 'status:publish', 'alerts:publish']
            },
            'actuator': {
                'device_type': 'actuator',
                'configuration': {
                    'control_mode': 'remote',
                    'feedback_enabled': True,
                    'topics': ['telemetry', 'status', 'commands'],
                    'qos': 2
                },
                'permissions': ['telemetry:publish', 'status:publish', 'commands:subscribe']
            },
            'edge_gateway': {
                'device_type': 'gateway',
                'configuration': {
                    'max_devices': 100,
                    'aggregation_enabled': True,
                    'local_storage': True,
                    'topics': ['telemetry', 'status', 'devices', 'system'],
                    'qos': 2
                },
                'permissions': [
                    'telemetry:publish',
                    'status:publish',
                    'devices:manage',
                    'system:monitor'
                ]
            }
        }
    
    async def _provisioning_monitor(self) -> None:
        """Monitor provisioning sessions and clean up expired ones"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                now = datetime.utcnow()
                expired_sessions = []
                
                for session_id, session_data in self.provisioning_sessions.items():
                    if session_data['expires_at'] < now:
                        if session_data['status'] == ProvisioningStatus.PENDING.value:
                            session_data['status'] = ProvisioningStatus.EXPIRED.value
                            expired_sessions.append(session_id)
                            self.stats['in_progress'] -= 1
                
                # Clean up old completed/expired sessions (keep for 24 hours)
                cutoff_time = now - timedelta(hours=24)
                sessions_to_remove = []
                
                for session_id, session_data in self.provisioning_sessions.items():
                    if session_data['created_at'] < cutoff_time:
                        if session_data['status'] in [
                            ProvisioningStatus.COMPLETED.value,
                            ProvisioningStatus.EXPIRED.value,
                            ProvisioningStatus.FAILED.value
                        ]:
                            sessions_to_remove.append(session_id)
                
                for session_id in sessions_to_remove:
                    del self.provisioning_sessions[session_id]
                
                if expired_sessions:
                    self.logger.info("Expired provisioning sessions",
                                   count=len(expired_sessions))
                
                if sessions_to_remove:
                    self.logger.info("Cleaned up old provisioning sessions",
                                   count=len(sessions_to_remove))
                
            except Exception as e:
                self.logger.error("Error in provisioning monitor", error=str(e))
                await asyncio.sleep(60)
    
    def get_status(self) -> Dict[str, Any]:
        """Get provisioner status"""
        active_sessions = sum(
            1 for s in self.provisioning_sessions.values()
            if s['status'] in [ProvisioningStatus.PENDING.value, ProvisioningStatus.IN_PROGRESS.value]
        )
        
        return {
            'total_provisioned': self.stats['total_provisioned'],
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'active_sessions': active_sessions,
            'templates_available': list(self.device_templates.keys())
        }
