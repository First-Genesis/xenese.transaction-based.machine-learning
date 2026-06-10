"""
TML SDK Configuration
Configuration management for TML SDK
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import yaml
from .exceptions import TMLConfigError


@dataclass
class TMLConfig:
    """TML SDK Configuration"""
    
    # Core settings
    api_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    api_version: str = "v1"
    
    # Connection settings
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Authentication
    auth_type: str = "api_key"  # api_key, oauth2, jwt
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    jwt_token: Optional[str] = None
    
    # Streaming settings
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_consumer_group: str = "tml-sdk"
    kafka_auto_offset_reset: str = "latest"
    
    # Database settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "tml"
    postgres_user: str = "tml"
    postgres_password: str = "tml123"
    
    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # MLflow settings
    mlflow_tracking_uri: str = "http://localhost:5003"
    mlflow_experiment_name: str = "tml-sdk"
    
    # Monitoring settings
    prometheus_gateway: str = "localhost:9091"
    metrics_enabled: bool = True
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Advanced settings
    enable_spatial_inheritance: bool = True
    enable_federated_learning: bool = True
    enable_drift_detection: bool = True
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, config_path: str) -> "TMLConfig":
        """Load configuration from file"""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise TMLConfigError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() in ['.yml', '.yaml']:
                    data = yaml.safe_load(f)
                elif config_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    raise TMLConfigError(f"Unsupported config file format: {config_path.suffix}")
            
            return cls(**data)
            
        except Exception as e:
            raise TMLConfigError(f"Failed to load configuration: {e}")
    
    @classmethod
    def from_env(cls) -> "TMLConfig":
        """Load configuration from environment variables"""
        config_data = {}
        
        # Map environment variables to config fields
        env_mapping = {
            'TML_API_URL': 'api_url',
            'TML_API_KEY': 'api_key',
            'TML_API_VERSION': 'api_version',
            'TML_TIMEOUT': 'timeout',
            'TML_MAX_RETRIES': 'max_retries',
            'TML_RETRY_DELAY': 'retry_delay',
            'TML_AUTH_TYPE': 'auth_type',
            'TML_OAUTH2_CLIENT_ID': 'oauth2_client_id',
            'TML_OAUTH2_CLIENT_SECRET': 'oauth2_client_secret',
            'TML_JWT_TOKEN': 'jwt_token',
            'TML_KAFKA_BOOTSTRAP_SERVERS': 'kafka_bootstrap_servers',
            'TML_KAFKA_CONSUMER_GROUP': 'kafka_consumer_group',
            'TML_POSTGRES_HOST': 'postgres_host',
            'TML_POSTGRES_PORT': 'postgres_port',
            'TML_POSTGRES_DATABASE': 'postgres_database',
            'TML_POSTGRES_USER': 'postgres_user',
            'TML_POSTGRES_PASSWORD': 'postgres_password',
            'TML_REDIS_HOST': 'redis_host',
            'TML_REDIS_PORT': 'redis_port',
            'TML_REDIS_DB': 'redis_db',
            'TML_REDIS_PASSWORD': 'redis_password',
            'TML_MLFLOW_TRACKING_URI': 'mlflow_tracking_uri',
            'TML_MLFLOW_EXPERIMENT_NAME': 'mlflow_experiment_name',
            'TML_LOG_LEVEL': 'log_level',
        }
        
        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion
                if config_key in ['timeout', 'max_retries', 'postgres_port', 'redis_port', 'redis_db']:
                    config_data[config_key] = int(value)
                elif config_key in ['retry_delay']:
                    config_data[config_key] = float(value)
                elif config_key in ['metrics_enabled', 'enable_spatial_inheritance', 
                                  'enable_federated_learning', 'enable_drift_detection']:
                    config_data[config_key] = value.lower() in ['true', '1', 'yes', 'on']
                else:
                    config_data[config_key] = value
        
        return cls(**config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }
    
    def save_to_file(self, config_path: str, format: str = "yaml"):
        """Save configuration to file"""
        config_path = Path(config_path)
        config_data = self.to_dict()
        
        try:
            with open(config_path, 'w') as f:
                if format.lower() in ['yml', 'yaml']:
                    yaml.dump(config_data, f, default_flow_style=False)
                elif format.lower() == 'json':
                    json.dump(config_data, f, indent=2)
                else:
                    raise TMLConfigError(f"Unsupported format: {format}")
                    
        except Exception as e:
            raise TMLConfigError(f"Failed to save configuration: {e}")
    
    def validate(self) -> None:
        """Validate configuration"""
        errors = []
        
        # Required fields
        if not self.api_url:
            errors.append("api_url is required")
        
        # URL validation
        if self.api_url and not (self.api_url.startswith('http://') or self.api_url.startswith('https://')):
            errors.append("api_url must start with http:// or https://")
        
        # Authentication validation
        if self.auth_type == "api_key" and not self.api_key:
            errors.append("api_key is required when auth_type is 'api_key'")
        elif self.auth_type == "oauth2" and (not self.oauth2_client_id or not self.oauth2_client_secret):
            errors.append("oauth2_client_id and oauth2_client_secret are required when auth_type is 'oauth2'")
        elif self.auth_type == "jwt" and not self.jwt_token:
            errors.append("jwt_token is required when auth_type is 'jwt'")
        
        # Numeric validation
        if self.timeout <= 0:
            errors.append("timeout must be positive")
        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")
        if self.retry_delay < 0:
            errors.append("retry_delay must be non-negative")
        
        if errors:
            raise TMLConfigError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def get_database_url(self) -> str:
        """Get PostgreSQL database URL"""
        return (f"postgresql://{self.postgres_user}:{self.postgres_password}@"
                f"{self.postgres_host}:{self.postgres_port}/{self.postgres_database}")
    
    def get_redis_url(self) -> str:
        """Get Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
