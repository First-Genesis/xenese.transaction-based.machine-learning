"""Model registry for managing millions of transaction models."""

import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod

import redis
import mlflow
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from loguru import logger

from tml.core.config import config
from tml.core.model import TransactionModel, TransactionContext


@dataclass
class ModelMetadata:
    """Metadata for a transaction model."""
    model_id: str
    parent_model_id: Optional[str]
    transaction_id: str
    user_id: Optional[str]
    creation_time: float
    last_updated: float
    total_predictions: int
    total_updates: int
    accuracy: float
    drift_score: float
    status: str  # active, archived, deprecated
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        return cls(**data)


class ModelStorage(ABC):
    """Abstract base class for model storage backends."""
    
    @abstractmethod
    async def store_model(self, model: TransactionModel) -> bool:
        """Store a model."""
        pass
    
    @abstractmethod
    async def load_model(self, model_id: str) -> Optional[TransactionModel]:
        """Load a model by ID."""
        pass
    
    @abstractmethod
    async def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        pass
    
    @abstractmethod
    async def list_models(self, filters: Dict[str, Any] = None) -> List[str]:
        """List model IDs with optional filters."""
        pass


class RedisModelStorage(ModelStorage):
    """Redis-based hot storage for active models."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=False,  # We need bytes for pickle
            max_connections=config.redis.max_connections
        )
        self.metadata_client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db + 1,  # Separate DB for metadata
            password=config.redis.password,
            decode_responses=True,
            max_connections=config.redis.max_connections
        )
    
    async def store_model(self, model: TransactionModel) -> bool:
        """Store model in Redis."""
        try:
            # Serialize model state
            model_state = model.get_state()
            model_bytes = json.dumps(model_state).encode('utf-8')
            
            # Store model data
            key = f"model:{model.model_id}"
            self.redis_client.set(key, model_bytes, ex=3600)  # 1 hour TTL
            
            # Store metadata
            metadata = ModelMetadata(
                model_id=model.model_id,
                parent_model_id=model.parent_model_id,
                transaction_id=model.context.transaction_id,
                user_id=model.context.user_id,
                creation_time=model.model.metrics.creation_time,
                last_updated=model.model.metrics.last_updated,
                total_predictions=model.model.metrics.total_predictions,
                total_updates=model.model.metrics.total_updates,
                accuracy=model.model.metrics.accuracy,
                drift_score=model.model.metrics.drift_score,
                status="active",
                tags={}
            )
            
            metadata_key = f"metadata:{model.model_id}"
            self.metadata_client.hset(metadata_key, mapping=metadata.to_dict())
            
            # Add to active models set
            self.metadata_client.sadd("active_models", model.model_id)
            
            logger.debug(f"Stored model {model.model_id} in Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store model {model.model_id} in Redis: {e}")
            return False
    
    async def load_model(self, model_id: str) -> Optional[TransactionModel]:
        """Load model from Redis."""
        try:
            key = f"model:{model_id}"
            model_bytes = self.redis_client.get(key)
            
            if not model_bytes:
                return None
            
            # Deserialize model state
            model_state = json.loads(model_bytes.decode('utf-8'))
            
            # Create model instance
            context = TransactionContext(**model_state["context"])
            model = TransactionModel(context)
            model.set_state(model_state)
            
            logger.debug(f"Loaded model {model_id} from Redis")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model {model_id} from Redis: {e}")
            return None
    
    async def delete_model(self, model_id: str) -> bool:
        """Delete model from Redis."""
        try:
            # Delete model data
            model_key = f"model:{model_id}"
            metadata_key = f"metadata:{model_id}"
            
            pipe = self.redis_client.pipeline()
            pipe.delete(model_key)
            pipe.execute()
            
            # Delete metadata
            meta_pipe = self.metadata_client.pipeline()
            meta_pipe.delete(metadata_key)
            meta_pipe.srem("active_models", model_id)
            meta_pipe.execute()
            
            logger.debug(f"Deleted model {model_id} from Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model {model_id} from Redis: {e}")
            return False
    
    async def list_models(self, filters: Dict[str, Any] = None) -> List[str]:
        """List active model IDs."""
        try:
            return list(self.metadata_client.smembers("active_models"))
        except Exception as e:
            logger.error(f"Failed to list models from Redis: {e}")
            return []
    
    def get_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Get model metadata."""
        try:
            metadata_key = f"metadata:{model_id}"
            data = self.metadata_client.hgetall(metadata_key)
            if data:
                # Convert string values back to appropriate types
                data['creation_time'] = float(data['creation_time'])
                data['last_updated'] = float(data['last_updated'])
                data['total_predictions'] = int(data['total_predictions'])
                data['total_updates'] = int(data['total_updates'])
                data['accuracy'] = float(data['accuracy'])
                data['drift_score'] = float(data['drift_score'])
                return ModelMetadata.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata for model {model_id}: {e}")
            return None


class CassandraModelStorage(ModelStorage):
    """Cassandra-based cold storage for archived models."""
    
    def __init__(self):
        auth_provider = PlainTextAuthProvider(username='cassandra', password='cassandra')
        self.cluster = Cluster(
            config.cassandra.hosts.split(','),
            port=config.cassandra.port,
            auth_provider=auth_provider
        )
        self.session = self.cluster.connect()
        self._setup_keyspace()
    
    def _setup_keyspace(self):
        """Setup Cassandra keyspace and tables."""
        try:
            # Create keyspace
            self.session.execute(f"""
                CREATE KEYSPACE IF NOT EXISTS {config.cassandra.keyspace}
                WITH replication = {{
                    'class': 'SimpleStrategy',
                    'replication_factor': {config.cassandra.replication_factor}
                }}
            """)
            
            self.session.set_keyspace(config.cassandra.keyspace)
            
            # Create models table
            self.session.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    model_id text PRIMARY KEY,
                    parent_model_id text,
                    transaction_id text,
                    user_id text,
                    model_data blob,
                    creation_time timestamp,
                    last_updated timestamp,
                    total_predictions int,
                    total_updates int,
                    accuracy double,
                    drift_score double,
                    status text,
                    tags map<text, text>
                )
            """)
            
            # Create index on transaction_id
            self.session.execute("""
                CREATE INDEX IF NOT EXISTS ON models (transaction_id)
            """)
            
            # Create index on user_id
            self.session.execute("""
                CREATE INDEX IF NOT EXISTS ON models (user_id)
            """)
            
        except Exception as e:
            logger.error(f"Failed to setup Cassandra keyspace: {e}")
    
    async def store_model(self, model: TransactionModel) -> bool:
        """Store model in Cassandra."""
        try:
            model_state = model.get_state()
            model_data = json.dumps(model_state).encode('utf-8')
            
            query = """
                INSERT INTO models (
                    model_id, parent_model_id, transaction_id, user_id,
                    model_data, creation_time, last_updated,
                    total_predictions, total_updates, accuracy, drift_score,
                    status, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.session.execute(query, [
                model.model_id,
                model.parent_model_id,
                model.context.transaction_id,
                model.context.user_id,
                model_data,
                model.model.metrics.creation_time,
                model.model.metrics.last_updated,
                model.model.metrics.total_predictions,
                model.model.metrics.total_updates,
                model.model.metrics.accuracy,
                model.model.metrics.drift_score,
                "archived",
                {}
            ])
            
            logger.debug(f"Stored model {model.model_id} in Cassandra")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store model {model.model_id} in Cassandra: {e}")
            return False
    
    async def load_model(self, model_id: str) -> Optional[TransactionModel]:
        """Load model from Cassandra."""
        try:
            query = "SELECT model_data FROM models WHERE model_id = ?"
            result = self.session.execute(query, [model_id])
            row = result.one()
            
            if not row:
                return None
            
            model_state = json.loads(row.model_data.decode('utf-8'))
            context = TransactionContext(**model_state["context"])
            model = TransactionModel(context)
            model.set_state(model_state)
            
            logger.debug(f"Loaded model {model_id} from Cassandra")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model {model_id} from Cassandra: {e}")
            return None
    
    async def delete_model(self, model_id: str) -> bool:
        """Delete model from Cassandra."""
        try:
            query = "DELETE FROM models WHERE model_id = ?"
            self.session.execute(query, [model_id])
            
            logger.debug(f"Deleted model {model_id} from Cassandra")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model {model_id} from Cassandra: {e}")
            return False
    
    async def list_models(self, filters: Dict[str, Any] = None) -> List[str]:
        """List model IDs with optional filters."""
        try:
            if filters and 'user_id' in filters:
                query = "SELECT model_id FROM models WHERE user_id = ?"
                result = self.session.execute(query, [filters['user_id']])
            else:
                query = "SELECT model_id FROM models"
                result = self.session.execute(query)
            
            return [row.model_id for row in result]
            
        except Exception as e:
            logger.error(f"Failed to list models from Cassandra: {e}")
            return []


class ModelRegistry:
    """Central registry for managing transaction models."""
    
    def __init__(self):
        self.hot_storage = RedisModelStorage()
        self.cold_storage = CassandraModelStorage()
        self.active_models: Dict[str, TransactionModel] = {}
        self.model_cache_size = config.model.max_models_in_memory
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # MLflow setup
        mlflow.set_tracking_uri(config.mlflow.tracking_uri)
        try:
            mlflow.create_experiment(config.mlflow.experiment_name)
        except:
            pass  # Experiment already exists
        mlflow.set_experiment(config.mlflow.experiment_name)
    
    async def register_model(self, model: TransactionModel) -> bool:
        """Register a new model in the registry."""
        try:
            # Store in hot storage
            await self.hot_storage.store_model(model)
            
            # Add to in-memory cache if space available
            if len(self.active_models) < self.model_cache_size:
                self.active_models[model.model_id] = model
            else:
                # Evict least recently used model
                await self._evict_lru_model()
                self.active_models[model.model_id] = model
            
            # Log to MLflow
            with mlflow.start_run(run_name=f"model_{model.model_id}"):
                mlflow.log_param("model_id", model.model_id)
                mlflow.log_param("parent_model_id", model.parent_model_id)
                mlflow.log_param("transaction_id", model.context.transaction_id)
                mlflow.log_metric("creation_time", model.model.metrics.creation_time)
            
            logger.info(f"Registered model {model.model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register model {model.model_id}: {e}")
            return False
    
    async def get_model(self, model_id: str) -> Optional[TransactionModel]:
        """Get a model by ID."""
        # Check in-memory cache first
        if model_id in self.active_models:
            return self.active_models[model_id]
        
        # Try hot storage
        model = await self.hot_storage.load_model(model_id)
        if model:
            # Add to cache if space available
            if len(self.active_models) < self.model_cache_size:
                self.active_models[model_id] = model
            return model
        
        # Try cold storage
        model = await self.cold_storage.load_model(model_id)
        if model:
            # Promote to hot storage
            await self.hot_storage.store_model(model)
            if len(self.active_models) < self.model_cache_size:
                self.active_models[model_id] = model
        
        return model
    
    async def update_model(self, model: TransactionModel) -> bool:
        """Update an existing model."""
        try:
            # Update in hot storage
            await self.hot_storage.store_model(model)
            
            # Update in-memory cache
            if model.model_id in self.active_models:
                self.active_models[model.model_id] = model
            
            # Log metrics to MLflow
            with mlflow.start_run(run_name=f"model_{model.model_id}_update"):
                mlflow.log_metric("total_predictions", model.model.metrics.total_predictions)
                mlflow.log_metric("total_updates", model.model.metrics.total_updates)
                mlflow.log_metric("accuracy", model.model.metrics.accuracy)
                mlflow.log_metric("drift_score", model.model.metrics.drift_score)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update model {model.model_id}: {e}")
            return False
    
    async def archive_model(self, model_id: str) -> bool:
        """Archive a model to cold storage."""
        try:
            model = await self.get_model(model_id)
            if not model:
                return False
            
            # Store in cold storage
            await self.cold_storage.store_model(model)
            
            # Remove from hot storage and cache
            await self.hot_storage.delete_model(model_id)
            if model_id in self.active_models:
                del self.active_models[model_id]
            
            logger.info(f"Archived model {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive model {model_id}: {e}")
            return False
    
    async def delete_model(self, model_id: str) -> bool:
        """Delete a model completely."""
        try:
            # Remove from all storages
            await self.hot_storage.delete_model(model_id)
            await self.cold_storage.delete_model(model_id)
            
            # Remove from cache
            if model_id in self.active_models:
                del self.active_models[model_id]
            
            logger.info(f"Deleted model {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model {model_id}: {e}")
            return False
    
    async def list_models(self, filters: Dict[str, Any] = None) -> List[str]:
        """List all model IDs."""
        hot_models = await self.hot_storage.list_models(filters)
        cold_models = await self.cold_storage.list_models(filters)
        return list(set(hot_models + cold_models))
    
    async def get_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Get model metadata."""
        return self.hot_storage.get_model_metadata(model_id)
    
    async def _evict_lru_model(self):
        """Evict least recently used model from cache."""
        if not self.active_models:
            return
        
        # Find model with oldest last_updated time
        lru_model_id = min(
            self.active_models.keys(),
            key=lambda mid: self.active_models[mid].model.metrics.last_updated
        )
        
        # Archive the model
        await self.archive_model(lru_model_id)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "active_models_count": len(self.active_models),
            "cache_size_limit": self.model_cache_size,
            "cache_utilization": len(self.active_models) / self.model_cache_size
        }
