"""Helper utilities for TML platform."""

import time
import hashlib
import json
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
from contextlib import asynccontextmanager

import numpy as np
from loguru import logger


def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate a unique ID with optional prefix."""
    timestamp = str(int(time.time() * 1000))
    hash_obj = hashlib.md5(timestamp.encode())
    unique_id = hash_obj.hexdigest()[:length]
    
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize object to JSON, handling numpy types."""
    def json_serializer(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    return json.dumps(obj, default=json_serializer)


def safe_json_deserialize(json_str: str, default: Any = None) -> Any:
    """Safely deserialize JSON string."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to deserialize JSON: {e}")
        return default


def normalize_features(features: Dict[str, Any]) -> Dict[str, float]:
    """Normalize feature dictionary to numeric values."""
    normalized = {}
    
    for key, value in features.items():
        if isinstance(value, (int, float)):
            normalized[key] = float(value)
        elif isinstance(value, bool):
            normalized[key] = float(value)
        elif isinstance(value, str):
            # Hash string values to numeric
            normalized[key] = float(hash(value) % 1000) / 1000.0
        elif value is None:
            normalized[key] = 0.0
        else:
            # Convert other types to string then hash
            normalized[key] = float(hash(str(value)) % 1000) / 1000.0
    
    return normalized


def calculate_feature_similarity(features1: Dict[str, Any], 
                                features2: Dict[str, Any]) -> float:
    """Calculate cosine similarity between two feature dictionaries."""
    # Normalize features
    norm1 = normalize_features(features1)
    norm2 = normalize_features(features2)
    
    # Get common keys
    common_keys = set(norm1.keys()) & set(norm2.keys())
    
    if not common_keys:
        return 0.0
    
    # Calculate cosine similarity
    dot_product = sum(norm1[key] * norm2[key] for key in common_keys)
    magnitude1 = sum(norm1[key] ** 2 for key in common_keys) ** 0.5
    magnitude2 = sum(norm2[key] ** 2 for key in common_keys) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def retry_with_backoff(max_retries: int = 3, 
                      base_delay: float = 1.0,
                      max_delay: float = 60.0,
                      exponential_base: float = 2.0):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}), "
                                 f"retrying in {delay:.2f}s: {e}")
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def async_retry_with_backoff(max_retries: int = 3,
                           base_delay: float = 1.0,
                           max_delay: float = 60.0,
                           exponential_base: float = 2.0):
    """Decorator for retrying async functions with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Async function {func.__name__} failed after {max_retries} retries")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"Async function {func.__name__} failed (attempt {attempt + 1}), "
                                 f"retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, failure_threshold: int = 5, 
                 recovery_timeout: float = 60.0,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker for {func.__name__} is now HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _on_success(self):
        """Handle successful execution."""
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info("Circuit breaker is now CLOSED")
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker is now OPEN (failures: {self.failure_count})")


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: float, capacity: int = None):
        self.rate = rate  # tokens per second
        self.capacity = capacity or int(rate * 2)  # bucket capacity
        self.tokens = self.capacity
        self.last_update = time.time()
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens from the bucket."""
        now = time.time()
        
        # Add tokens based on elapsed time
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time for tokens to be available."""
        if self.tokens >= tokens:
            return 0.0
        
        needed_tokens = tokens - self.tokens
        return needed_tokens / self.rate


@asynccontextmanager
async def async_timeout(seconds: float):
    """Async context manager for timeouts."""
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {seconds} seconds")
        raise


def batch_iterator(items: List[Any], batch_size: int):
    """Iterate over items in batches."""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


async def async_batch_processor(items: List[Any], 
                              processor: Callable,
                              batch_size: int = 10,
                              max_concurrency: int = 5) -> List[Any]:
    """Process items in batches with concurrency control."""
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process_batch(batch):
        async with semaphore:
            return await processor(batch)
    
    tasks = []
    for batch in batch_iterator(items, batch_size):
        task = asyncio.create_task(process_batch(batch))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten results and handle exceptions
    flattened_results = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch processing error: {result}")
            continue
        
        if isinstance(result, list):
            flattened_results.extend(result)
        else:
            flattened_results.append(result)
    
    return flattened_results


class PerformanceTimer:
    """Context manager for measuring performance."""
    
    def __init__(self, name: str, log_result: bool = True):
        self.name = name
        self.log_result = log_result
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        
        if self.log_result:
            duration = (self.end_time - self.start_time) * 1000
            if exc_type is None:
                logger.debug(f"Performance: {self.name} completed in {duration:.2f}ms")
            else:
                logger.error(f"Performance: {self.name} failed after {duration:.2f}ms")
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


def validate_features(features: Dict[str, Any], 
                     required_features: List[str] = None,
                     allowed_types: Dict[str, type] = None) -> bool:
    """Validate feature dictionary."""
    if not isinstance(features, dict):
        logger.error("Features must be a dictionary")
        return False
    
    if not features:
        logger.error("Features dictionary is empty")
        return False
    
    # Check required features
    if required_features:
        missing = set(required_features) - set(features.keys())
        if missing:
            logger.error(f"Missing required features: {missing}")
            return False
    
    # Check feature types
    if allowed_types:
        for feature, expected_type in allowed_types.items():
            if feature in features:
                if not isinstance(features[feature], expected_type):
                    logger.error(f"Feature {feature} has wrong type: "
                               f"expected {expected_type}, got {type(features[feature])}")
                    return False
    
    return True


def memory_usage_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        logger.warning("psutil not available, cannot measure memory usage")
        return 0.0
