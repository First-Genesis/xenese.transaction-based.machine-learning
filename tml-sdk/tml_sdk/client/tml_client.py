"""
TML Client - Main SDK Client
Core client for interacting with the TML Platform
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
import requests
import aiohttp
from datetime import datetime, timedelta

from .config import TMLConfig
from .exceptions import (
    TMLException, TMLConnectionError, TMLAuthenticationError,
    TMLValidationError, TMLTimeoutError, TMLRateLimitError
)
from ..models.model_manager import ModelManager
from ..transactions.transaction_manager import TransactionManager
from ..spatial.spatial_manager import SpatialManager
from ..federated.federated_manager import FederatedManager
from ..monitoring.monitoring_manager import MonitoringManager
from ..utils.logger import get_logger


class TMLClient:
    """
    Main TML SDK Client
    
    Provides access to all TML Platform functionality including:
    - Model management and training
    - Transaction streaming and processing
    - Spatial inheritance
    - Federated learning
    - Monitoring and drift detection
    
    Example:
        client = TMLClient(api_url="http://localhost:8000", api_key="your-key")
        
        # Create a model
        model = client.models.create("fraud_detection", model_type="river_classifier")
        
        # Stream transactions
        for transaction in client.transactions.stream("live-transactions"):
            prediction = model.predict(transaction.features)
            model.learn(transaction.features, transaction.label)
    """
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        config: TMLConfig = None,
        **kwargs
    ):
        """
        Initialize TML Client
        
        Args:
            api_url: TML Platform API URL
            api_key: API key for authentication
            config: TMLConfig instance (optional)
            **kwargs: Additional configuration options
        """
        # Initialize configuration
        if config:
            self.config = config
        else:
            # Create config from parameters
            config_data = {}
            if api_url:
                config_data['api_url'] = api_url
            if api_key:
                config_data['api_key'] = api_key
            config_data.update(kwargs)
            
            self.config = TMLConfig(**config_data)
        
        # Validate configuration
        self.config.validate()
        
        # Initialize logger
        self.logger = get_logger(__name__, level=self.config.log_level)
        
        # Initialize session
        self.session = requests.Session()
        self.async_session: Optional[aiohttp.ClientSession] = None
        
        # Authentication
        self._setup_authentication()
        
        # Initialize managers
        self.models = ModelManager(self)
        self.transactions = TransactionManager(self)
        self.spatial = SpatialManager(self)
        self.federated = FederatedManager(self)
        self.monitoring = MonitoringManager(self)
        
        # Connection state
        self._connected = False
        self._last_health_check = None
        
        self.logger.info(f"TML Client initialized for {self.config.api_url}")
    
    def _setup_authentication(self):
        """Setup authentication headers"""
        if self.config.auth_type == "api_key" and self.config.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.api_key}",
                "X-API-Key": self.config.api_key
            })
        elif self.config.auth_type == "jwt" and self.config.jwt_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.jwt_token}"
            })
        
        # Common headers
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": f"TML-SDK/1.0.0",
            "Accept": "application/json"
        })
    
    def connect(self) -> bool:
        """
        Connect to TML Platform and verify authentication
        
        Returns:
            bool: True if connection successful
            
        Raises:
            TMLConnectionError: If connection fails
            TMLAuthenticationError: If authentication fails
        """
        try:
            response = self.get("/health")
            if response.status_code == 200:
                self._connected = True
                self._last_health_check = datetime.now()
                self.logger.info("Successfully connected to TML Platform")
                return True
            else:
                raise TMLConnectionError(f"Health check failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError as e:
            raise TMLConnectionError(f"Failed to connect to {self.config.api_url}: {e}")
        except requests.exceptions.Timeout as e:
            raise TMLTimeoutError(f"Connection timeout: {e}")
        except Exception as e:
            raise TMLConnectionError(f"Unexpected connection error: {e}")
    
    def disconnect(self):
        """Disconnect from TML Platform"""
        if self.session:
            self.session.close()
        if self.async_session:
            asyncio.create_task(self.async_session.close())
        
        self._connected = False
        self.logger.info("Disconnected from TML Platform")
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        if not self._connected:
            return False
        
        # Check if health check is recent (within 5 minutes)
        if self._last_health_check:
            if datetime.now() - self._last_health_check > timedelta(minutes=5):
                try:
                    return self.connect()
                except:
                    self._connected = False
                    return False
        
        return True
    
    def get(self, endpoint: str, params: Dict = None, **kwargs) -> requests.Response:
        """Make GET request to TML Platform"""
        return self._request("GET", endpoint, params=params, **kwargs)
    
    def post(self, endpoint: str, data: Dict = None, json: Dict = None, **kwargs) -> requests.Response:
        """Make POST request to TML Platform"""
        return self._request("POST", endpoint, data=data, json=json, **kwargs)
    
    def put(self, endpoint: str, data: Dict = None, json: Dict = None, **kwargs) -> requests.Response:
        """Make PUT request to TML Platform"""
        return self._request("PUT", endpoint, data=data, json=json, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Make DELETE request to TML Platform"""
        return self._request("DELETE", endpoint, **kwargs)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic and error handling
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            requests.Response: HTTP response
            
        Raises:
            TMLConnectionError: If request fails
            TMLAuthenticationError: If authentication fails
            TMLRateLimitError: If rate limited
        """
        url = f"{self.config.api_url.rstrip('/')}/api/{self.config.api_version}/{endpoint.lstrip('/')}"
        
        # Set timeout
        kwargs.setdefault('timeout', self.config.timeout)
        
        # Retry logic
        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"{method} {url} (attempt {attempt + 1})")
                
                response = self.session.request(method, url, **kwargs)
                
                # Handle different response codes
                if response.status_code == 200:
                    return response
                elif response.status_code == 401:
                    raise TMLAuthenticationError("Authentication failed")
                elif response.status_code == 403:
                    raise TMLAuthenticationError("Access forbidden")
                elif response.status_code == 404:
                    raise TMLException(f"Resource not found: {endpoint}")
                elif response.status_code == 429:
                    raise TMLRateLimitError("Rate limit exceeded")
                elif response.status_code >= 500:
                    if attempt < self.config.max_retries:
                        self.logger.warning(f"Server error {response.status_code}, retrying...")
                        continue
                    raise TMLConnectionError(f"Server error: {response.status_code}")
                else:
                    raise TMLException(f"Request failed: {response.status_code} - {response.text}")
                    
            except requests.exceptions.Timeout:
                if attempt < self.config.max_retries:
                    self.logger.warning("Request timeout, retrying...")
                    continue
                raise TMLTimeoutError("Request timeout")
            except requests.exceptions.ConnectionError as e:
                if attempt < self.config.max_retries:
                    self.logger.warning(f"Connection error, retrying: {e}")
                    continue
                raise TMLConnectionError(f"Connection failed: {e}")
            except Exception as e:
                if attempt < self.config.max_retries:
                    self.logger.warning(f"Request failed, retrying: {e}")
                    continue
                raise TMLException(f"Request failed: {e}")
    
    async def async_get(self, endpoint: str, params: Dict = None, **kwargs) -> aiohttp.ClientResponse:
        """Make async GET request"""
        return await self._async_request("GET", endpoint, params=params, **kwargs)
    
    async def async_post(self, endpoint: str, data: Dict = None, json: Dict = None, **kwargs) -> aiohttp.ClientResponse:
        """Make async POST request"""
        return await self._async_request("POST", endpoint, data=data, json=json, **kwargs)
    
    async def _async_request(self, method: str, endpoint: str, **kwargs) -> aiohttp.ClientResponse:
        """Make async HTTP request"""
        if not self.async_session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.async_session = aiohttp.ClientSession(
                headers=self.session.headers,
                timeout=timeout
            )
        
        url = f"{self.config.api_url.rstrip('/')}/api/{self.config.api_version}/{endpoint.lstrip('/')}"
        
        async with self.async_session.request(method, url, **kwargs) as response:
            if response.status == 401:
                raise TMLAuthenticationError("Authentication failed")
            elif response.status == 429:
                raise TMLRateLimitError("Rate limit exceeded")
            elif response.status >= 400:
                text = await response.text()
                raise TMLException(f"Request failed: {response.status} - {text}")
            
            return response
    
    def get_info(self) -> Dict[str, Any]:
        """Get TML Platform information"""
        try:
            response = self.get("/info")
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get platform info: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get TML Platform status"""
        try:
            response = self.get("/status")
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get platform status: {e}")
            return {"status": "unknown", "error": str(e)}
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.disconnect()
        except:
            pass
