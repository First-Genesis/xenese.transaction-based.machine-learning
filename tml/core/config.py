"""Configuration management for TML platform."""

import os
from typing import Any, Dict, Optional

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings, Field

from pathlib import Path


class RedisConfig(BaseSettings):
    """Redis configuration for model state storage."""

    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")

    class Config:
        env_prefix = "REDIS_"


class KafkaConfig(BaseSettings):
    """Kafka configuration for transaction streaming."""

    bootstrap_servers: str = Field(
        default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS"
    )
    transaction_topic: str = Field(
        default="transactions", env="KAFKA_TRANSACTION_TOPIC"
    )
    model_updates_topic: str = Field(
        default="model_updates", env="KAFKA_MODEL_UPDATES_TOPIC"
    )
    consumer_group: str = Field(default="tml_processors", env="KAFKA_CONSUMER_GROUP")

    class Config:
        env_prefix = "KAFKA_"


class CassandraConfig(BaseSettings):
    """Cassandra configuration for model archive storage."""

    hosts: str = Field(default="localhost", env="CASSANDRA_HOSTS")
    port: int = Field(default=9042, env="CASSANDRA_PORT")
    keyspace: str = Field(default="tml_models", env="CASSANDRA_KEYSPACE")
    replication_factor: int = Field(default=3, env="CASSANDRA_REPLICATION_FACTOR")

    class Config:
        env_prefix = "CASSANDRA_"


class MLflowConfig(BaseSettings):
    """MLflow configuration for model registry."""

    tracking_uri: str = Field(
        default="http://localhost:5000", env="MLFLOW_TRACKING_URI"
    )
    experiment_name: str = Field(
        default="tml_experiments", env="MLFLOW_EXPERIMENT_NAME"
    )

    class Config:
        env_prefix = "MLFLOW_"


class ModelConfig(BaseSettings):
    """Model configuration parameters."""

    base_model_type: str = Field(
        default="river", env="MODEL_BASE_TYPE"
    )  # river, vowpal_wabbit
    max_models_in_memory: int = Field(default=10000, env="MODEL_MAX_IN_MEMORY")
    model_compression_enabled: bool = Field(
        default=True, env="MODEL_COMPRESSION_ENABLED"
    )
    ewc_lambda: float = Field(
        default=0.4, env="MODEL_EWC_LAMBDA"
    )  # Elastic Weight Consolidation
    drift_threshold: float = Field(default=0.1, env="MODEL_DRIFT_THRESHOLD")
    cold_start_samples: int = Field(default=100, env="MODEL_COLD_START_SAMPLES")

    class Config:
        env_prefix = "MODEL_"


class ServingConfig(BaseSettings):
    """Model serving configuration."""

    ray_address: Optional[str] = Field(default=None, env="RAY_ADDRESS")
    num_replicas: int = Field(default=4, env="SERVING_NUM_REPLICAS")
    max_concurrent_queries: int = Field(
        default=1000, env="SERVING_MAX_CONCURRENT_QUERIES"
    )

    class Config:
        env_prefix = "SERVING_"


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""

    prometheus_port: int = Field(default=8000, env="PROMETHEUS_PORT")
    grafana_url: str = Field(default="http://localhost:3000", env="GRAFANA_URL")
    drift_check_interval: int = Field(
        default=300, env="MONITORING_DRIFT_CHECK_INTERVAL"
    )  # seconds

    class Config:
        env_prefix = "MONITORING_"


class Config(BaseSettings):
    """Main TML platform configuration."""

    # Environment
    environment: str = Field(default="development", env="TML_ENVIRONMENT")
    debug: bool = Field(default=False, env="TML_DEBUG")
    log_level: str = Field(default="INFO", env="TML_LOG_LEVEL")

    # Component configurations
    redis: RedisConfig = Field(default_factory=RedisConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    cassandra: CassandraConfig = Field(default_factory=CassandraConfig)
    mlflow: MLflowConfig = Field(default_factory=MLflowConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    # Paths
    data_dir: Path = Field(default=Path("./data"), env="TML_DATA_DIR")
    model_dir: Path = Field(default=Path("./models"), env="TML_MODEL_DIR")
    logs_dir: Path = Field(default=Path("./logs"), env="TML_LOGS_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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
