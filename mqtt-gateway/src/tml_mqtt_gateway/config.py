"""
TML MQTT Gateway Configuration
Centralized configuration management with environment variable support
"""

import os
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
import yaml


class MQTTConfig(BaseSettings):
    """MQTT Broker Configuration"""
    
    host: str = Field(default="localhost", env="MQTT_BROKER_HOST")
    port: int = Field(default=1883, env="MQTT_BROKER_PORT")
    username: Optional[str] = Field(default=None, env="MQTT_USERNAME")
    password: Optional[str] = Field(default=None, env="MQTT_PASSWORD")
    client_id: str = Field(default="tml-gateway", env="MQTT_CLIENT_ID")
    keepalive: int = Field(default=60, env="MQTT_KEEPALIVE")
    qos: int = Field(default=1, env="MQTT_QOS")
    
    # TLS Configuration
    use_tls: bool = Field(default=False, env="MQTT_USE_TLS")
    ca_cert_path: Optional[str] = Field(default=None, env="MQTT_CA_CERT")
    cert_path: Optional[str] = Field(default=None, env="MQTT_CERT")
    key_path: Optional[str] = Field(default=None, env="MQTT_KEY")
    
    # Topic Configuration
    base_topic: str = Field(default="tml", env="MQTT_BASE_TOPIC")
    subscribe_topics: List[str] = Field(
        default=["tml/devices/+/+/telemetry", "tml/devices/+/+/status"],
        env="MQTT_SUBSCRIBE_TOPICS"
    )
    
    @validator('subscribe_topics', pre=True)
    def parse_topics(cls, v):
        if isinstance(v, str):
            return [topic.strip() for topic in v.split(',')]
        return v


class KafkaConfig(BaseSettings):
    """Kafka Configuration"""
    
    bootstrap_servers: str = Field(default="localhost:29092", env="KAFKA_BOOTSTRAP_SERVERS")
    topic_prefix: str = Field(default="tml.iot", env="KAFKA_TOPIC_PREFIX")
    
    # Producer Configuration
    acks: str = Field(default="all", env="KAFKA_ACKS")
    retries: int = Field(default=3, env="KAFKA_RETRIES")
    batch_size: int = Field(default=16384, env="KAFKA_BATCH_SIZE")
    linger_ms: int = Field(default=10, env="KAFKA_LINGER_MS")
    compression_type: str = Field(default="gzip", env="KAFKA_COMPRESSION")
    
    # Topic Mapping
    telemetry_topic: str = Field(default="tml.iot.telemetry", env="KAFKA_TELEMETRY_TOPIC")
    status_topic: str = Field(default="tml.iot.device_status", env="KAFKA_STATUS_TOPIC")
    alerts_topic: str = Field(default="tml.iot.alerts", env="KAFKA_ALERTS_TOPIC")
    dead_letter_topic: str = Field(default="tml.iot.dead_letter", env="KAFKA_DEAD_LETTER_TOPIC")


class DatabaseConfig(BaseSettings):
    """Database Configuration"""
    
    host: str = Field(default="localhost", env="POSTGRES_HOST")
    port: int = Field(default=5432, env="POSTGRES_PORT")
    database: str = Field(default="tml", env="POSTGRES_DB")
    username: str = Field(default="tml", env="POSTGRES_USER")
    password: str = Field(default="tml123", env="POSTGRES_PASSWORD")
    
    # Connection Pool
    min_connections: int = Field(default=5, env="DB_MIN_CONNECTIONS")
    max_connections: int = Field(default=20, env="DB_MAX_CONNECTIONS")
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseSettings):
    """Redis Configuration"""
    
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    
    # Connection Pool
    max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    
    @property
    def connection_string(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class GatewayConfig(BaseSettings):
    """Gateway Configuration"""
    
    gateway_id: str = Field(default="tml-gateway-001", env="GATEWAY_ID")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8080, env="API_PORT")
    
    # Metrics Configuration
    metrics_host: str = Field(default="0.0.0.0", env="METRICS_HOST")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # Processing Configuration
    max_workers: int = Field(default=10, env="MAX_WORKERS")
    batch_size: int = Field(default=100, env="BATCH_SIZE")
    flush_interval: float = Field(default=1.0, env="FLUSH_INTERVAL")
    
    # Health Check
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    # Security
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    enable_auth: bool = Field(default=False, env="ENABLE_AUTH")


class TMLGatewayConfig(BaseSettings):
    """Main Gateway Configuration"""
    
    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @classmethod
    def from_file(cls, config_path: str) -> "TMLGatewayConfig":
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return cls(**config_data)
    
    def to_file(self, config_path: str) -> None:
        """Save configuration to YAML file"""
        with open(config_path, 'w') as f:
            yaml.dump(self.dict(), f, default_flow_style=False)
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # MQTT validation
        if not self.mqtt.host:
            errors.append("MQTT host is required")
        
        # Kafka validation
        if not self.kafka.bootstrap_servers:
            errors.append("Kafka bootstrap servers are required")
        
        # Database validation
        if not all([self.database.host, self.database.username, self.database.password]):
            errors.append("Database connection parameters are incomplete")
        
        return errors


# Global configuration instance
config = TMLGatewayConfig()


def get_config() -> TMLGatewayConfig:
    """Get global configuration instance"""
    return config


def load_config(config_path: Optional[str] = None) -> TMLGatewayConfig:
    """Load configuration from file or environment"""
    global config
    
    if config_path and os.path.exists(config_path):
        config = TMLGatewayConfig.from_file(config_path)
    else:
        config = TMLGatewayConfig()
    
    # Validate configuration
    errors = config.validate_config()
    if errors:
        raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    return config
