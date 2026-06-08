"""
TML Production Client

Enterprise-grade client for the TML platform with support for:
- Multiple processing modes (local, remote, hybrid)
- Authentication and security
- Automatic failover and load balancing
- Request caching and optimization
- Comprehensive error handling

Copyright (c) 2024 First Genesis. All rights reserved.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

# Third-party imports
import httpx
import redis
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

# TML imports
from ..core.production_processor import ProcessingResult
from ..core.production_processor import ProductionConfig
from ..core.production_processor import ProductionTransactionProcessor

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing mode for TML client."""

    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"
    DISTRIBUTED = "distributed"


@dataclass
class TMLConfig:
    """Configuration for TML client."""

    # Processing mode
    processing_mode: ProcessingMode = ProcessingMode.HYBRID

    # API configuration
    api_base_url: str = "https://api.tml.firstgenesis.com"
    api_key: str = ""
    api_timeout: int = 30
    api_retries: int = 3

    # Local processing configuration
    local_config: Optional[ProductionConfig] = None

    # Caching configuration
    enable_caching: bool = True
    cache_ttl: int = 3600  # 1 hour
    cache_max_size: int = 10000

    # Performance configuration
    batch_size: int = 100
    max_concurrent_requests: int = 10

    # Failover configuration
    enable_failover: bool = True
    failover_endpoints: List[str] = field(default_factory=list)

    # Security configuration
    verify_ssl: bool = True
    jwt_token: Optional[str] = None


class ClientError(Exception):
    """Base exception for TML client errors."""

    pass


class AuthenticationError(ClientError):
    """Authentication related errors."""

    pass


class ProcessingError(ClientError):
    """Processing related errors."""

    pass


class RequestCache:
    """Simple in-memory cache for requests."""

    def __init__(self, max_size: int = 10000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, tuple] = {}
        self.access_order: List[str] = []

    def _generate_key(self, data: Dict[str, Any]) -> str:
        """Generate cache key from request data."""
        # Create deterministic hash of request data
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()

    def get(self, data: Dict[str, Any]) -> Optional[ProcessingResult]:
        """Get cached result."""
        key = self._generate_key(data)

        if key not in self.cache:
            return None

        result, timestamp = self.cache[key]

        # Check TTL
        if time.time() - timestamp > self.ttl:
            self.remove(key)
            return None

        # Update access order
        self.access_order.remove(key)
        self.access_order.append(key)

        return result

    def put(self, data: Dict[str, Any], result: ProcessingResult):
        """Cache result."""
        key = self._generate_key(data)

        # Remove if already exists
        if key in self.cache:
            self.access_order.remove(key)

        # Evict LRU if at capacity
        while len(self.cache) >= self.max_size:
            lru_key = self.access_order.pop(0)
            del self.cache[lru_key]

        # Add new result
        self.cache[key] = (result, time.time())
        self.access_order.append(key)

    def remove(self, key: str):
        """Remove from cache."""
        if key in self.cache:
            del self.cache[key]
            self.access_order.remove(key)

    def clear(self):
        """Clear all cached results."""
        self.cache.clear()
        self.access_order.clear()


class TMLClient:
    """
    Production TML client with enterprise features.

    Supports multiple processing modes:
    - LOCAL: Process transactions locally
    - REMOTE: Send to TML API
    - HYBRID: Try local first, fallback to remote
    - DISTRIBUTED: Load balance across multiple endpoints
    """

    def __init__(self, config: TMLConfig):
        self.config = config
        self.cache = (
            RequestCache(max_size=config.cache_max_size, ttl=config.cache_ttl)
            if config.enable_caching
            else None
        )

        # Initialize local processor if needed
        self.local_processor = None
        if config.processing_mode in [ProcessingMode.LOCAL, ProcessingMode.HYBRID]:
            if config.local_config:
                self.local_processor = ProductionTransactionProcessor(
                    config.local_config
                )
            else:
                logger.warning(
                    "Local processing requested but no local_config provided"
                )

        # HTTP client for remote requests
        self.http_client = httpx.AsyncClient(
            timeout=config.api_timeout,
            verify=config.verify_ssl,
            limits=httpx.Limits(max_connections=config.max_concurrent_requests),
        )

        # Statistics
        self.stats = {
            "requests_total": 0,
            "requests_cached": 0,
            "requests_local": 0,
            "requests_remote": 0,
            "requests_failed": 0,
            "start_time": time.time(),
        }

    async def initialize(self):
        """Initialize the client."""
        if self.local_processor:
            await self.local_processor.initialize()

        # Authenticate if API key provided
        if self.config.api_key:
            await self._authenticate()

        logger.info(
            f"TML Client initialized in {self.config.processing_mode.value} mode"
        )

    async def _authenticate(self):
        """Authenticate with the TML API."""
        try:
            auth_url = f"{self.config.api_base_url}/auth/token"
            response = await self.http_client.post(
                auth_url, json={"api_key": self.config.api_key}
            )

            if response.status_code == 200:
                auth_data = response.json()
                self.config.jwt_token = auth_data.get("access_token")
                logger.info("Successfully authenticated with TML API")
            else:
                raise AuthenticationError(f"Authentication failed: {response.text}")

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Failed to authenticate: {e}")

    async def process_transaction(
        self, transaction_data: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Process a single transaction.

        Args:
            transaction_data: Transaction data dictionary

        Returns:
            ProcessingResult object
        """
        self.stats["requests_total"] += 1

        # Check cache first
        if self.cache:
            cached_result = self.cache.get(transaction_data)
            if cached_result:
                self.stats["requests_cached"] += 1
                return cached_result

        # Add transaction ID if not present
        if "transaction_id" not in transaction_data:
            transaction_data["transaction_id"] = str(uuid.uuid4())

        try:
            # Route based on processing mode
            if self.config.processing_mode == ProcessingMode.LOCAL:
                result = await self._process_local(transaction_data)
            elif self.config.processing_mode == ProcessingMode.REMOTE:
                result = await self._process_remote(transaction_data)
            elif self.config.processing_mode == ProcessingMode.HYBRID:
                result = await self._process_hybrid(transaction_data)
            elif self.config.processing_mode == ProcessingMode.DISTRIBUTED:
                result = await self._process_distributed(transaction_data)
            else:
                raise ProcessingError(
                    f"Unsupported processing mode: {self.config.processing_mode}"
                )

            # Cache successful result
            if self.cache and result.status == "success":
                self.cache.put(transaction_data, result)

            return result

        except Exception as e:
            self.stats["requests_failed"] += 1
            logger.error(f"Transaction processing failed: {e}")

            return ProcessingResult(
                transaction_id=transaction_data.get("transaction_id", "unknown"),
                model_id="error",
                status="error",
                error_message=str(e),
            )

    async def _process_local(
        self, transaction_data: Dict[str, Any]
    ) -> ProcessingResult:
        """Process transaction locally."""
        if not self.local_processor:
            raise ProcessingError("Local processor not available")

        self.stats["requests_local"] += 1
        return await self.local_processor.process_transaction_async(transaction_data)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _process_remote(
        self, transaction_data: Dict[str, Any]
    ) -> ProcessingResult:
        """Process transaction via remote API."""
        self.stats["requests_remote"] += 1

        headers = {}
        if self.config.jwt_token:
            headers["Authorization"] = f"Bearer {self.config.jwt_token}"

        try:
            response = await self.http_client.post(
                f"{self.config.api_base_url}/api/v1/process",
                json=transaction_data,
                headers=headers,
            )

            if response.status_code == 200:
                result_data = response.json()
                return ProcessingResult(**result_data)
            elif response.status_code == 401:
                raise AuthenticationError("Authentication required or token expired")
            else:
                raise ProcessingError(
                    f"API request failed: {response.status_code} - {response.text}"
                )

        except httpx.RequestError as e:
            raise ProcessingError(f"Network error: {e}")

    async def _process_hybrid(
        self, transaction_data: Dict[str, Any]
    ) -> ProcessingResult:
        """Process transaction with hybrid approach (local first, remote fallback)."""
        try:
            # Try local processing first
            if self.local_processor:
                return await self._process_local(transaction_data)
        except Exception as e:
            logger.warning(f"Local processing failed, falling back to remote: {e}")

        # Fallback to remote processing
        return await self._process_remote(transaction_data)

    async def _process_distributed(
        self, transaction_data: Dict[str, Any]
    ) -> ProcessingResult:
        """Process transaction with load balancing across endpoints."""
        endpoints = [self.config.api_base_url] + self.config.failover_endpoints

        for endpoint in endpoints:
            try:
                # Temporarily update base URL
                original_url = self.config.api_base_url
                self.config.api_base_url = endpoint

                result = await self._process_remote(transaction_data)

                # Restore original URL
                self.config.api_base_url = original_url

                return result

            except Exception as e:
                logger.warning(f"Endpoint {endpoint} failed: {e}")
                continue

        raise ProcessingError("All endpoints failed")

    async def process_batch(
        self, transactions: List[Dict[str, Any]]
    ) -> List[ProcessingResult]:
        """
        Process multiple transactions in batch.

        Args:
            transactions: List of transaction data dictionaries

        Returns:
            List of ProcessingResult objects
        """
        # Split into batches
        batches = [
            transactions[i : i + self.config.batch_size]
            for i in range(0, len(transactions), self.config.batch_size)
        ]

        results = []
        for batch in batches:
            # Process batch concurrently
            tasks = [self.process_transaction(tx) for tx in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append(
                        ProcessingResult(
                            transaction_id=batch[i].get("transaction_id", f"batch_{i}"),
                            model_id="error",
                            status="error",
                            error_message=str(result),
                        )
                    )
                else:
                    results.append(result)

        return results

    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a specific model."""
        headers = {}
        if self.config.jwt_token:
            headers["Authorization"] = f"Bearer {self.config.jwt_token}"

        try:
            response = await self.http_client.get(
                f"{self.config.api_base_url}/api/v1/models/{model_id}", headers=headers
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise ProcessingError(f"Failed to get model info: {response.text}")

        except httpx.RequestError as e:
            raise ProcessingError(f"Network error: {e}")

    async def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics."""
        uptime = time.time() - self.stats["start_time"]

        stats = {
            "uptime_seconds": uptime,
            "requests_total": self.stats["requests_total"],
            "requests_cached": self.stats["requests_cached"],
            "requests_local": self.stats["requests_local"],
            "requests_remote": self.stats["requests_remote"],
            "requests_failed": self.stats["requests_failed"],
            "cache_hit_rate": (
                self.stats["requests_cached"] / max(1, self.stats["requests_total"])
            ),
            "success_rate": (
                (self.stats["requests_total"] - self.stats["requests_failed"])
                / max(1, self.stats["requests_total"])
            ),
            "requests_per_second": self.stats["requests_total"] / max(1, uptime),
        }

        # Add local processor stats if available
        if self.local_processor:
            stats["local_processor"] = self.local_processor.get_statistics()

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of client and connected services."""
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "statistics": await self.get_statistics(),
        }

        # Check local processor
        if self.local_processor:
            try:
                local_health = self.local_processor.health_check()
                health["components"]["local_processor"] = local_health
            except Exception as e:
                health["components"]["local_processor"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health["status"] = "degraded"

        # Check remote API
        try:
            response = await self.http_client.get(f"{self.config.api_base_url}/health")
            if response.status_code == 200:
                health["components"]["remote_api"] = response.json()
            else:
                health["components"]["remote_api"] = {
                    "status": "unhealthy",
                    "code": response.status_code,
                }
                health["status"] = "degraded"
        except Exception as e:
            health["components"]["remote_api"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health["status"] = "degraded"

        return health

    async def shutdown(self):
        """Gracefully shutdown the client."""
        logger.info("Shutting down TML client...")

        # Clear cache
        if self.cache:
            self.cache.clear()

        # Shutdown local processor
        if self.local_processor:
            await self.local_processor.shutdown()

        # Close HTTP client
        await self.http_client.aclose()

        logger.info("TML client shutdown complete")


# Convenience functions
async def create_client(config: TMLConfig) -> TMLClient:
    """Create and initialize a TML client."""
    client = TMLClient(config)
    await client.initialize()
    return client


async def process_single_transaction(
    transaction_data: Dict[str, Any], config: TMLConfig
) -> ProcessingResult:
    """Process a single transaction with automatic client management."""
    client = await create_client(config)
    try:
        return await client.process_transaction(transaction_data)
    finally:
        await client.shutdown()


# Export main classes
__all__ = [
    "TMLClient",
    "TMLConfig",
    "ProcessingMode",
    "ProcessingResult",
    "ClientError",
    "AuthenticationError",
    "ProcessingError",
    "create_client",
    "process_single_transaction",
]
