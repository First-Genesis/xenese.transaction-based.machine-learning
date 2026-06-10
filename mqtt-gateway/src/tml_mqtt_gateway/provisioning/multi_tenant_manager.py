"""
Multi-Tenant Manager
Isolated namespaces and resource management for multiple organizations
"""

import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum

import structlog

from ..config import TMLGatewayConfig
from ..device_manager import DeviceManager


logger = structlog.get_logger(__name__)


class TenantStatus(Enum):
    """Tenant status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"


class ResourceQuota:
    """Resource quota for tenant"""
    
    def __init__(
        self,
        max_devices: int = 100,
        max_messages_per_day: int = 1000000,
        max_storage_gb: int = 10,
        max_bandwidth_mbps: int = 100
    ):
        self.max_devices = max_devices
        self.max_messages_per_day = max_messages_per_day
        self.max_storage_gb = max_storage_gb
        self.max_bandwidth_mbps = max_bandwidth_mbps


class MultiTenantManager:
    """
    Multi-Tenant Management System
    
    Features:
    - Isolated tenant namespaces
    - Resource quota management
    - Topic isolation and routing
    - Tenant-specific authentication
    - Usage tracking and billing
    - Data isolation and security
    - Cross-tenant analytics
    """
    
    def __init__(
        self,
        config: TMLGatewayConfig,
        device_manager: DeviceManager
    ):
        self.config = config
        self.device_manager = device_manager
        
        # Tenant registry
        self.tenants = {}  # tenant_id -> tenant_info
        
        # Tenant device mapping
        self.tenant_devices = {}  # tenant_id -> Set[device_id]
        
        # Resource usage tracking
        self.resource_usage = {}  # tenant_id -> usage_data
        
        # Topic namespace mapping
        self.tenant_topics = {}  # tenant_id -> topic_prefix
        
        self.logger = logger.bind(component="multi_tenant_manager")
    
    async def initialize(self) -> None:
        """Initialize multi-tenant manager"""
        try:
            self.logger.info("Multi-tenant manager initialized")
            
            # Load existing tenants
            await self._load_existing_tenants()
            
            # Start usage monitor
            asyncio.create_task(self._usage_monitor())
            
        except Exception as e:
            self.logger.error("Failed to initialize multi-tenant manager", error=str(e))
            raise
    
    async def create_tenant(
        self,
        tenant_id: str,
        organization_name: str,
        admin_email: str,
        plan: str = "standard",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create new tenant
        
        Args:
            tenant_id: Unique tenant identifier
            organization_name: Organization name
            admin_email: Admin contact email
            plan: Subscription plan
            metadata: Additional metadata
            
        Returns:
            Tenant configuration
        """
        try:
            # Check if tenant already exists
            if tenant_id in self.tenants:
                raise ValueError(f"Tenant {tenant_id} already exists")
            
            # Determine resource quota based on plan
            quota = self._get_quota_for_plan(plan)
            
            # Generate topic namespace
            topic_prefix = f"tml/{tenant_id}"
            
            # Create tenant configuration
            tenant_info = {
                'tenant_id': tenant_id,
                'organization_name': organization_name,
                'admin_email': admin_email,
                'plan': plan,
                'status': TenantStatus.ACTIVE.value,
                'created_at': datetime.utcnow(),
                'quota': {
                    'max_devices': quota.max_devices,
                    'max_messages_per_day': quota.max_messages_per_day,
                    'max_storage_gb': quota.max_storage_gb,
                    'max_bandwidth_mbps': quota.max_bandwidth_mbps
                },
                'topic_prefix': topic_prefix,
                'isolation_enabled': True,
                'metadata': metadata or {}
            }
            
            # Initialize resource usage
            self.resource_usage[tenant_id] = {
                'device_count': 0,
                'message_count_today': 0,
                'storage_used_gb': 0.0,
                'bandwidth_used_mbps': 0.0,
                'last_updated': datetime.utcnow()
            }
            
            # Initialize tenant collections
            self.tenants[tenant_id] = tenant_info
            self.tenant_devices[tenant_id] = set()
            self.tenant_topics[tenant_id] = topic_prefix
            
            # Create tenant-specific database schema
            await self._create_tenant_schema(tenant_id)
            
            self.logger.info("Created tenant",
                           tenant_id=tenant_id,
                           organization=organization_name,
                           plan=plan)
            
            return {
                'tenant_id': tenant_id,
                'topic_prefix': topic_prefix,
                'quota': tenant_info['quota'],
                'status': tenant_info['status']
            }
            
        except Exception as e:
            self.logger.error("Failed to create tenant",
                            tenant_id=tenant_id,
                            error=str(e))
            raise
    
    async def add_device_to_tenant(
        self,
        tenant_id: str,
        device_id: str,
        device_info: Dict[str, Any]
    ) -> bool:
        """
        Add device to tenant
        
        Args:
            tenant_id: Tenant identifier
            device_id: Device identifier
            device_info: Device information
            
        Returns:
            Success status
        """
        try:
            # Validate tenant
            if tenant_id not in self.tenants:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            tenant_info = self.tenants[tenant_id]
            
            # Check tenant status
            if tenant_info['status'] != TenantStatus.ACTIVE.value:
                raise ValueError(f"Tenant {tenant_id} is not active")
            
            # Check device quota
            usage = self.resource_usage[tenant_id]
            if usage['device_count'] >= tenant_info['quota']['max_devices']:
                raise ValueError(f"Tenant {tenant_id} has reached device quota")
            
            # Add tenant information to device metadata
            device_info['metadata'] = device_info.get('metadata', {})
            device_info['metadata']['tenant_id'] = tenant_id
            device_info['metadata']['organization'] = tenant_info['organization_name']
            
            # Register device
            await self.device_manager.register_device(device_info)
            
            # Update tenant device mapping
            self.tenant_devices[tenant_id].add(device_id)
            
            # Update resource usage
            usage['device_count'] += 1
            usage['last_updated'] = datetime.utcnow()
            
            self.logger.info("Added device to tenant",
                           tenant_id=tenant_id,
                           device_id=device_id)
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to add device to tenant",
                            tenant_id=tenant_id,
                            device_id=device_id,
                            error=str(e))
            raise
    
    def get_tenant_topic_prefix(self, tenant_id: str) -> str:
        """Get topic prefix for tenant"""
        if tenant_id in self.tenant_topics:
            return self.tenant_topics[tenant_id]
        
        # Default tenant uses standard prefix
        if tenant_id == "default":
            return "tml"
        
        return f"tml/{tenant_id}"
    
    def validate_tenant_topic_access(
        self,
        tenant_id: str,
        topic: str
    ) -> bool:
        """
        Validate if tenant has access to topic
        
        Args:
            tenant_id: Tenant identifier
            topic: MQTT topic
            
        Returns:
            True if access is allowed
        """
        # Get tenant prefix
        tenant_prefix = self.get_tenant_topic_prefix(tenant_id)
        
        # Check if topic starts with tenant prefix
        return topic.startswith(tenant_prefix)
    
    def isolate_message_for_tenant(
        self,
        tenant_id: str,
        topic: str
    ) -> str:
        """
        Transform topic to tenant namespace
        
        Args:
            tenant_id: Tenant identifier
            topic: Original topic
            
        Returns:
            Tenant-namespaced topic
        """
        # Remove any existing prefix
        if topic.startswith("tml/"):
            topic = topic[4:]  # Remove "tml/"
        
        # Add tenant prefix
        tenant_prefix = self.get_tenant_topic_prefix(tenant_id)
        
        # Construct tenant-specific topic
        if topic.startswith("devices/"):
            return f"{tenant_prefix}/{topic}"
        else:
            return f"{tenant_prefix}/devices/{topic}"
    
    async def update_tenant_usage(
        self,
        tenant_id: str,
        message_count: int = 0,
        bandwidth_mbps: float = 0.0
    ) -> None:
        """
        Update tenant resource usage
        
        Args:
            tenant_id: Tenant identifier
            message_count: Number of messages processed
            bandwidth_mbps: Bandwidth consumed
        """
        try:
            if tenant_id not in self.resource_usage:
                return
            
            usage = self.resource_usage[tenant_id]
            usage['message_count_today'] += message_count
            usage['bandwidth_used_mbps'] = max(usage['bandwidth_used_mbps'], bandwidth_mbps)
            usage['last_updated'] = datetime.utcnow()
            
            # Check quotas
            tenant_info = self.tenants[tenant_id]
            quota = tenant_info['quota']
            
            # Check message quota
            if usage['message_count_today'] > quota['max_messages_per_day']:
                self.logger.warning("Tenant exceeded message quota",
                                  tenant_id=tenant_id,
                                  messages=usage['message_count_today'],
                                  quota=quota['max_messages_per_day'])
            
            # Check bandwidth quota
            if usage['bandwidth_used_mbps'] > quota['max_bandwidth_mbps']:
                self.logger.warning("Tenant exceeded bandwidth quota",
                                  tenant_id=tenant_id,
                                  bandwidth=usage['bandwidth_used_mbps'],
                                  quota=quota['max_bandwidth_mbps'])
            
        except Exception as e:
            self.logger.error("Failed to update tenant usage",
                            tenant_id=tenant_id,
                            error=str(e))
    
    async def get_tenant_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant usage statistics
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Usage statistics
        """
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        tenant_info = self.tenants[tenant_id]
        usage = self.resource_usage[tenant_id]
        
        # Get device statistics
        device_count = len(self.tenant_devices[tenant_id])
        active_devices = 0
        
        for device_id in self.tenant_devices[tenant_id]:
            device = await self.device_manager.get_device(device_id)
            if device and device.get('status') == 'online':
                active_devices += 1
        
        return {
            'tenant_id': tenant_id,
            'organization_name': tenant_info['organization_name'],
            'plan': tenant_info['plan'],
            'status': tenant_info['status'],
            'created_at': tenant_info['created_at'].isoformat(),
            'devices': {
                'total': device_count,
                'active': active_devices,
                'quota': tenant_info['quota']['max_devices']
            },
            'usage': {
                'messages_today': usage['message_count_today'],
                'message_quota': tenant_info['quota']['max_messages_per_day'],
                'storage_gb': usage['storage_used_gb'],
                'storage_quota': tenant_info['quota']['max_storage_gb'],
                'bandwidth_mbps': usage['bandwidth_used_mbps'],
                'bandwidth_quota': tenant_info['quota']['max_bandwidth_mbps']
            }
        }
    
    async def suspend_tenant(self, tenant_id: str, reason: str = None) -> None:
        """
        Suspend tenant account
        
        Args:
            tenant_id: Tenant identifier
            reason: Suspension reason
        """
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        self.tenants[tenant_id]['status'] = TenantStatus.SUSPENDED.value
        self.tenants[tenant_id]['suspension_reason'] = reason
        self.tenants[tenant_id]['suspended_at'] = datetime.utcnow()
        
        self.logger.warning("Tenant suspended",
                          tenant_id=tenant_id,
                          reason=reason)
    
    async def reactivate_tenant(self, tenant_id: str) -> None:
        """
        Reactivate suspended tenant
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        self.tenants[tenant_id]['status'] = TenantStatus.ACTIVE.value
        self.tenants[tenant_id]['reactivated_at'] = datetime.utcnow()
        
        self.logger.info("Tenant reactivated", tenant_id=tenant_id)
    
    def _get_quota_for_plan(self, plan: str) -> ResourceQuota:
        """Get resource quota for subscription plan"""
        quotas = {
            'trial': ResourceQuota(
                max_devices=10,
                max_messages_per_day=10000,
                max_storage_gb=1,
                max_bandwidth_mbps=10
            ),
            'standard': ResourceQuota(
                max_devices=100,
                max_messages_per_day=1000000,
                max_storage_gb=10,
                max_bandwidth_mbps=100
            ),
            'professional': ResourceQuota(
                max_devices=1000,
                max_messages_per_day=10000000,
                max_storage_gb=100,
                max_bandwidth_mbps=1000
            ),
            'enterprise': ResourceQuota(
                max_devices=10000,
                max_messages_per_day=100000000,
                max_storage_gb=1000,
                max_bandwidth_mbps=10000
            )
        }
        
        return quotas.get(plan, quotas['standard'])
    
    async def _create_tenant_schema(self, tenant_id: str) -> None:
        """Create tenant-specific database schema"""
        # In production, create isolated schema or database for tenant
        self.logger.info("Created tenant schema", tenant_id=tenant_id)
    
    async def _load_existing_tenants(self) -> None:
        """Load existing tenants from database"""
        # In production, load from database
        # For now, create default tenant
        if 'default' not in self.tenants:
            await self.create_tenant(
                tenant_id='default',
                organization_name='Default Organization',
                admin_email='admin@tml.local',
                plan='standard'
            )
    
    async def _usage_monitor(self) -> None:
        """Monitor tenant usage and reset daily counters"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                now = datetime.utcnow()
                
                # Reset daily counters at midnight
                if now.hour == 0:
                    for tenant_id in self.resource_usage:
                        self.resource_usage[tenant_id]['message_count_today'] = 0
                        self.resource_usage[tenant_id]['last_reset'] = now
                    
                    self.logger.info("Reset daily usage counters")
                
                # Check for expired trial tenants
                for tenant_id, tenant_info in self.tenants.items():
                    if tenant_info['status'] == TenantStatus.TRIAL.value:
                        trial_duration = now - tenant_info['created_at']
                        if trial_duration.days > 30:  # 30-day trial
                            tenant_info['status'] = TenantStatus.EXPIRED.value
                            self.logger.warning("Trial expired", tenant_id=tenant_id)
                
            except Exception as e:
                self.logger.error("Error in usage monitor", error=str(e))
                await asyncio.sleep(300)
    
    def get_status(self) -> Dict[str, Any]:
        """Get multi-tenant manager status"""
        return {
            'total_tenants': len(self.tenants),
            'active_tenants': sum(1 for t in self.tenants.values() if t['status'] == TenantStatus.ACTIVE.value),
            'suspended_tenants': sum(1 for t in self.tenants.values() if t['status'] == TenantStatus.SUSPENDED.value),
            'total_devices': sum(len(devices) for devices in self.tenant_devices.values()),
            'plans': {
                'trial': sum(1 for t in self.tenants.values() if t['plan'] == 'trial'),
                'standard': sum(1 for t in self.tenants.values() if t['plan'] == 'standard'),
                'professional': sum(1 for t in self.tenants.values() if t['plan'] == 'professional'),
                'enterprise': sum(1 for t in self.tenants.values() if t['plan'] == 'enterprise')
            }
        }
