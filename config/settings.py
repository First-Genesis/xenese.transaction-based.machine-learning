"""
TML Platform Configuration Management

Centralized configuration for all environments.
"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field
from functools import lru_cache


class RedisSettings(BaseSettings):
    """Redis configuration"""
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default="redis123", env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    
    @property
    def url(self) -> str:
        """Get Redis connection URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class KafkaSettings(BaseSettings):
    """Kafka configuration"""
    bootstrap_servers: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    security_protocol: str = Field(default="PLAINTEXT", env="KAFKA_SECURITY_PROTOCOL")
    sasl_mechanism: Optional[str] = Field(default=None, env="KAFKA_SASL_MECHANISM")
    sasl_username: Optional[str] = Field(default=None, env="KAFKA_SASL_USERNAME")
    sasl_password: Optional[str] = Field(default=None, env="KAFKA_SASL_PASSWORD")
    
    # Topic configurations
    model_events_topic: str = Field(default="tml-model-events", env="KAFKA_MODEL_EVENTS_TOPIC")
    predictions_topic: str = Field(default="tml-predictions", env="KAFKA_PREDICTIONS_TOPIC")
    training_topic: str = Field(default="tml-training", env="KAFKA_TRAINING_TOPIC")


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = Field(default="postgresql://tml:tml123@localhost:5432/tml", env="DATABASE_URL")
    pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=30, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")


class MLflowSettings(BaseSettings):
    """MLflow configuration"""
    tracking_uri: str = Field(default="http://localhost:5000", env="MLFLOW_TRACKING_URI")
    experiment_name: str = Field(default="tml-platform", env="MLFLOW_EXPERIMENT_NAME")
    artifact_location: Optional[str] = Field(default=None, env="MLFLOW_ARTIFACT_LOCATION")


class CassandraSettings(BaseSettings):
    """Cassandra configuration"""
    hosts: str = Field(default="localhost", env="CASSANDRA_HOSTS")
    port: int = Field(default=9042, env="CASSANDRA_PORT")
    keyspace: str = Field(default="tml", env="CASSANDRA_KEYSPACE")
    username: Optional[str] = Field(default=None, env="CASSANDRA_USERNAME")
    password: Optional[str] = Field(default=None, env="CASSANDRA_PASSWORD")
    
    @property
    def host_list(self) -> list:
        """Get list of Cassandra hosts"""
        return [host.strip() for host in self.hosts.split(",")]


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration"""
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    grafana_port: int = Field(default=3000, env="GRAFANA_PORT")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")


class ModelSettings(BaseSettings):
    """Model configuration"""
    default_model_type: str = Field(default="logistic_regression", env="DEFAULT_MODEL_TYPE")
    max_models_in_memory: int = Field(default=10000, env="MAX_MODELS_IN_MEMORY")
    model_cache_ttl: int = Field(default=3600, env="MODEL_CACHE_TTL")  # seconds
    enable_model_compression: bool = Field(default=True, env="ENABLE_MODEL_COMPRESSION")
    inheritance_strategy: str = Field(default="full", env="INHERITANCE_STRATEGY")  # full, partial, selective
    
    # Performance settings
    batch_prediction_size: int = Field(default=1000, env="BATCH_PREDICTION_SIZE")
    async_training: bool = Field(default=True, env="ASYNC_TRAINING")
    model_persistence_interval: int = Field(default=300, env="MODEL_PERSISTENCE_INTERVAL")  # seconds


class APISettings(BaseSettings):
    """API server configuration"""
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    workers: int = Field(default=4, env="API_WORKERS")
    reload: bool = Field(default=False, env="API_RELOAD")
    
    # Security
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")
    rate_limit_per_minute: int = Field(default=1000, env="RATE_LIMIT_PER_MINUTE")
    
    # Request/Response
    max_request_size: int = Field(default=10 * 1024 * 1024, env="MAX_REQUEST_SIZE")  # 10MB
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")  # seconds


class TMLSettings(BaseSettings):
    """Main TML Platform settings"""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    version: str = Field(default="1.0.0", env="TML_VERSION")
    
    # Component settings
    redis: RedisSettings = RedisSettings()
    kafka: KafkaSettings = KafkaSettings()
    database: DatabaseSettings = DatabaseSettings()
    mlflow: MLflowSettings = MLflowSettings()
    cassandra: CassandraSettings = CassandraSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    models: ModelSettings = ModelSettings()
    api: APISettings = APISettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"
    
    def get_component_config(self, component: str) -> Dict[str, Any]:
        """Get configuration for a specific component"""
        component_map = {
            "redis": self.redis,
            "kafka": self.kafka,
            "database": self.database,
            "mlflow": self.mlflow,
            "cassandra": self.cassandra,
            "monitoring": self.monitoring,
            "models": self.models,
            "api": self.api
        }
        
        if component not in component_map:
            raise ValueError(f"Unknown component: {component}")
        
        return component_map[component].dict()


@lru_cache()
def get_settings() -> TMLSettings:
    """Get cached settings instance"""
    return TMLSettings()


# Environment-specific configurations
class DevelopmentSettings(TMLSettings):
    """Development environment settings"""
    environment: str = "development"
    debug: bool = True
    
    class Config:
        env_file = ".env.development"


class StagingSettings(TMLSettings):
    """Staging environment settings"""
    environment: str = "staging"
    debug: bool = False
    
    class Config:
        env_file = ".env.staging"


class ProductionSettings(TMLSettings):
    """Production environment settings"""
    environment: str = "production"
    debug: bool = False
    
    # Production overrides
    redis: RedisSettings = RedisSettings(
        host="redis-cluster.production.local",
        max_connections=500
    )
    
    kafka: KafkaSettings = KafkaSettings(
        bootstrap_servers="kafka-cluster.production.local:9092",
        security_protocol="SASL_SSL"
    )
    
    database: DatabaseSettings = DatabaseSettings(
        pool_size=50,
        max_overflow=100
    )
    
    class Config:
        env_file = ".env.production"


def get_settings_for_environment(env: str) -> TMLSettings:
    """Get settings for specific environment"""
    settings_map = {
        "development": DevelopmentSettings,
        "staging": StagingSettings,
        "production": ProductionSettings
    }
    
    settings_class = settings_map.get(env.lower(), TMLSettings)
    return settings_class()


# Export commonly used settings
settings = get_settings()
