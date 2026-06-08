"""Configuration management for TML platform."""

import os
from typing import Any, Dict, Optional

from pydantic import Field
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseSettings
    SettingsConfigDict = dict  # Fallback for older versions

from pathlib import Path


class RedisConfig(BaseSettings):
    """Redis configuration for model state storage."""

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None)
    max_connections: int = Field(default=100)

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class KafkaConfig(BaseSettings):
    """Kafka configuration for transaction streaming."""

    bootstrap_servers: str = Field(default="localhost:9092")
    transaction_topic: str = Field(default="transactions")
    model_updates_topic: str = Field(default="model_updates")
    consumer_group: str = Field(default="tml_processors")

    model_config = SettingsConfigDict(env_prefix="KAFKA_")


class CassandraConfig(BaseSettings):
    """Cassandra configuration for model archive storage."""

    hosts: str = Field(default="localhost")
    port: int = Field(default=9042)
    keyspace: str = Field(default="tml_models")
    replication_factor: int = Field(default=3)

    model_config = SettingsConfigDict(env_prefix="CASSANDRA_")


class MLflowConfig(BaseSettings):
    """MLflow configuration for model registry."""

    tracking_uri: str = Field(default="http://localhost:5000")
    experiment_name: str = Field(default="tml_experiments")

    model_config = SettingsConfigDict(env_prefix="MLFLOW_")


class ModelConfig(BaseSettings):
    """Model configuration parameters."""

    base_model_type: str = Field(default="river")  # river, vowpal_wabbit
    max_models_in_memory: int = Field(default=10000)
    model_compression_enabled: bool = Field(default=True)
    ewc_lambda: float = Field(default=0.4)  # Elastic Weight Consolidation
    drift_threshold: float = Field(default=0.1)
    cold_start_samples: int = Field(default=100)

    model_config = SettingsConfigDict(env_prefix="MODEL_")


class ServingConfig(BaseSettings):
    """Model serving configuration."""

    ray_address: Optional[str] = Field(default=None)
    num_replicas: int = Field(default=4)
    max_concurrent_queries: int = Field(default=1000)

    model_config = SettingsConfigDict(env_prefix="SERVING_")


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""

    prometheus_port: int = Field(default=8000)
    grafana_url: str = Field(default="http://localhost:3000")
    drift_check_interval: int = Field(default=300)  # seconds

    model_config = SettingsConfigDict(env_prefix="MONITORING_")


class Config(BaseSettings):
    """Main TML platform configuration."""

    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Component configurations
    redis: RedisConfig = Field(default_factory=RedisConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    cassandra: CassandraConfig = Field(default_factory=CassandraConfig)
    mlflow: MLflowConfig = Field(default_factory=MLflowConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    # Paths
    data_dir: Path = Field(default=Path("./data"))
    model_dir: Path = Field(default=Path("./models"))
    logs_dir: Path = Field(default=Path("./logs"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TML_"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "Config":
        """Load configuration from environment file."""
        return cls(_env_file=env_file)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()


# Global configuration instance
config = Config()
