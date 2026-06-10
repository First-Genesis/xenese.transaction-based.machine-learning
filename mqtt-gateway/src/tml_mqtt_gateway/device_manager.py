"""
TML Device Manager
Manages IoT device registration, authentication, and status tracking
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import asyncpg
import redis.asyncio as redis
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DatabaseConfig, RedisConfig
from .metrics import DatabaseMetrics


logger = structlog.get_logger(__name__)


class DeviceManager:
    """
    Device management system for IoT devices

    Features:
    - Device registration and authentication
    - Status tracking and health monitoring
    - Connection pooling for database operations
    - Redis caching for performance
    """

    def __init__(
        self,
        db_config: DatabaseConfig,
        redis_config: RedisConfig,
        metrics: DatabaseMetrics,
    ):
        self.db_config = db_config
        self.redis_config = redis_config
        self.metrics = metrics

        # Connection pools
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None

        # Device cache
        self.device_cache = {}
        self.cache_ttl = 300  # 5 minutes

        self.logger = logger.bind(component="device_manager")

    async def initialize(self) -> None:
        """Initialize database and Redis connections"""
        try:
            # Initialize database pool
            await self._initialize_database()

            # Initialize Redis client
            await self._initialize_redis()

            # Create database tables if they don't exist
            await self._create_tables()

            self.logger.info("Device manager initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize device manager", error=str(e))
            raise

    async def _initialize_database(self) -> None:
        """Initialize PostgreSQL connection pool"""
        try:
            self.db_pool = await asyncpg.create_pool(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password,
                min_size=self.db_config.min_connections,
                max_size=self.db_config.max_connections,
                command_timeout=30,
            )

            self.logger.info(
                "Database connection pool created",
                host=self.db_config.host,
                database=self.db_config.database,
            )

        except Exception as e:
            self.logger.error("Failed to create database pool", error=str(e))
            raise

    async def _initialize_redis(self) -> None:
        """Initialize Redis client"""
        try:
            self.redis_client = redis.from_url(
                self.redis_config.connection_string,
                max_connections=self.redis_config.max_connections,
                decode_responses=True,
            )

            # Test connection
            await self.redis_client.ping()

            self.logger.info(
                "Redis client initialized",
                host=self.redis_config.host,
                db=self.redis_config.db,
            )

        except Exception as e:
            self.logger.error("Failed to initialize Redis client", error=str(e))
            raise

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist"""
        try:
            async with self.db_pool.acquire() as conn:
                # Devices table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS devices (
                        device_id VARCHAR(255) PRIMARY KEY,
                        device_type VARCHAR(100) NOT NULL,
                        device_name VARCHAR(255),
                        manufacturer VARCHAR(255),
                        model VARCHAR(255),
                        firmware_version VARCHAR(100),
                        status VARCHAR(50) DEFAULT 'offline',
                        last_seen TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                """
                )

                # Device authentication table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS device_auth (
                        device_id VARCHAR(255) PRIMARY KEY REFERENCES devices(device_id),
                        auth_type VARCHAR(50) NOT NULL,
                        credentials JSONB NOT NULL,
                        enabled BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Device telemetry summary table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS device_telemetry_summary (
                        device_id VARCHAR(255) REFERENCES devices(device_id),
                        date DATE,
                        message_count INTEGER DEFAULT 0,
                        last_message_time TIMESTAMP,
                        avg_message_size INTEGER,
                        error_count INTEGER DEFAULT 0,
                        PRIMARY KEY (device_id, date)
                    )
                """
                )

                # Create indexes
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen)
                """
                )

            self.logger.info("Database tables created/verified")

        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def register_device(self, device_info: Dict[str, Any]) -> bool:
        """Register a new device"""
        try:
            device_id = device_info["device_id"]

            async with self.db_pool.acquire() as conn:
                # Insert or update device
                await conn.execute(
                    """
                    INSERT INTO devices (
                        device_id, device_type, device_name, manufacturer,
                        model, firmware_version, status, last_seen, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (device_id) DO UPDATE SET
                        device_type = EXCLUDED.device_type,
                        device_name = EXCLUDED.device_name,
                        manufacturer = EXCLUDED.manufacturer,
                        model = EXCLUDED.model,
                        firmware_version = EXCLUDED.firmware_version,
                        updated_at = CURRENT_TIMESTAMP,
                        metadata = EXCLUDED.metadata
                """,
                    device_id,
                    device_info.get("device_type", "unknown"),
                    device_info.get("device_name"),
                    device_info.get("manufacturer"),
                    device_info.get("model"),
                    device_info.get("firmware_version"),
                    "online",
                    datetime.now(),
                    json.dumps(device_info.get("metadata", {})),
                )

            # Update cache
            await self._update_device_cache(device_id, device_info)

            self.logger.info("Device registered successfully", device_id=device_id)
            self.metrics.db_queries_total.labels(operation="insert").inc()

            return True

        except Exception as e:
            self.logger.error(
                "Failed to register device",
                device_id=device_info.get("device_id"),
                error=str(e),
            )
            self.metrics.db_query_errors.labels(operation="insert").inc()
            raise

    async def update_device_status(self, device_info: Dict[str, Any]) -> None:
        """Update device status and last seen timestamp"""
        try:
            device_id = device_info["device_id"]

            # Check cache first
            cached_device = await self._get_device_from_cache(device_id)
            if not cached_device:
                # Register device if not exists
                await self.register_device(device_info)
                return

            # Update database
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE devices 
                    SET status = 'online', 
                        last_seen = $2, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = $1
                """,
                    device_id,
                    datetime.now(),
                )

            # Update cache
            await self._update_device_cache(device_id, device_info)

            # Update telemetry summary
            await self._update_telemetry_summary(device_id)

            self.metrics.db_queries_total.labels(operation="update").inc()

        except Exception as e:
            self.logger.error(
                "Failed to update device status",
                device_id=device_info.get("device_id"),
                error=str(e),
            )
            self.metrics.db_query_errors.labels(operation="update").inc()

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device information"""
        try:
            # Check cache first
            cached_device = await self._get_device_from_cache(device_id)
            if cached_device:
                return cached_device

            # Query database
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM devices WHERE device_id = $1
                """,
                    device_id,
                )

                if row:
                    device_info = dict(row)

                    # Parse JSON metadata
                    if device_info.get("metadata"):
                        device_info["metadata"] = json.loads(device_info["metadata"])

                    # Update cache
                    await self._update_device_cache(device_id, device_info)

                    self.metrics.db_queries_total.labels(operation="select").inc()
                    return device_info

            return None

        except Exception as e:
            self.logger.error("Failed to get device", device_id=device_id, error=str(e))
            self.metrics.db_query_errors.labels(operation="select").inc()
            return None

    async def list_devices(
        self,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List devices with optional filtering"""
        try:
            query = "SELECT * FROM devices WHERE 1=1"
            params = []
            param_count = 0

            if device_type:
                param_count += 1
                query += f" AND device_type = ${param_count}"
                params.append(device_type)

            if status:
                param_count += 1
                query += f" AND status = ${param_count}"
                params.append(status)

            param_count += 1
            query += f" ORDER BY last_seen DESC LIMIT ${param_count}"
            params.append(limit)

            param_count += 1
            query += f" OFFSET ${param_count}"
            params.append(offset)

            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

                devices = []
                for row in rows:
                    device_info = dict(row)
                    if device_info.get("metadata"):
                        device_info["metadata"] = json.loads(device_info["metadata"])
                    devices.append(device_info)

                self.metrics.db_queries_total.labels(operation="select").inc()
                return devices

        except Exception as e:
            self.logger.error("Failed to list devices", error=str(e))
            self.metrics.db_query_errors.labels(operation="select").inc()
            return []

    async def mark_devices_offline(self, timeout_minutes: int = 30) -> int:
        """Mark devices as offline if not seen for specified time"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE devices 
                    SET status = 'offline', updated_at = CURRENT_TIMESTAMP
                    WHERE last_seen < $1 AND status = 'online'
                """,
                    cutoff_time,
                )

                # Extract number of updated rows
                updated_count = int(result.split()[-1])

                if updated_count > 0:
                    self.logger.info("Marked devices offline", count=updated_count)

                self.metrics.db_queries_total.labels(operation="update").inc()
                return updated_count

        except Exception as e:
            self.logger.error("Failed to mark devices offline", error=str(e))
            self.metrics.db_query_errors.labels(operation="update").inc()
            return 0

    async def _get_device_from_cache(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device from Redis cache"""
        try:
            if self.redis_client:
                cached_data = await self.redis_client.get(f"device:{device_id}")
                if cached_data:
                    return json.loads(cached_data)

            return None

        except Exception as e:
            self.logger.error(
                "Failed to get device from cache", device_id=device_id, error=str(e)
            )
            return None

    async def _update_device_cache(
        self, device_id: str, device_info: Dict[str, Any]
    ) -> None:
        """Update device in Redis cache"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    f"device:{device_id}",
                    self.cache_ttl,
                    json.dumps(device_info, default=str),
                )

        except Exception as e:
            self.logger.error(
                "Failed to update device cache", device_id=device_id, error=str(e)
            )

    async def _update_telemetry_summary(self, device_id: str) -> None:
        """Update daily telemetry summary for device"""
        try:
            today = datetime.now().date()

            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO device_telemetry_summary (
                        device_id, date, message_count, last_message_time
                    ) VALUES ($1, $2, 1, $3)
                    ON CONFLICT (device_id, date) DO UPDATE SET
                        message_count = device_telemetry_summary.message_count + 1,
                        last_message_time = EXCLUDED.last_message_time
                """,
                    device_id,
                    today,
                    datetime.now(),
                )

        except Exception as e:
            self.logger.error(
                "Failed to update telemetry summary", device_id=device_id, error=str(e)
            )

    async def health_check(self) -> bool:
        """Check health of device manager components"""
        try:
            # Check database connection
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

            # Check Redis connection
            if self.redis_client:
                await self.redis_client.ping()

            return True

        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            return False

    async def close(self) -> None:
        """Close database and Redis connections"""
        try:
            if self.db_pool:
                await self.db_pool.close()

            if self.redis_client:
                await self.redis_client.close()

            self.logger.info("Device manager connections closed")

        except Exception as e:
            self.logger.error("Error closing device manager", error=str(e))

    def get_status(self) -> Dict[str, Any]:
        """Get device manager status"""
        return {
            "database_pool_size": self.db_pool.get_size() if self.db_pool else 0,
            "database_pool_free": self.db_pool.get_idle_size() if self.db_pool else 0,
            "redis_connected": self.redis_client is not None,
            "cache_ttl": self.cache_ttl,
        }
