"""
Performance Optimizer
Optimizes gateway performance for 100K+ concurrent devices
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import multiprocessing

import structlog
import psutil
import numpy as np

from ..config import TMLGatewayConfig


logger = structlog.get_logger(__name__)


class OptimizationStrategy(Enum):
    """Performance optimization strategies"""
    ADAPTIVE_BATCHING = "adaptive_batching"
    CONNECTION_POOLING = "connection_pooling"
    MESSAGE_COMPRESSION = "message_compression"
    ASYNC_PROCESSING = "async_processing"
    CACHE_OPTIMIZATION = "cache_optimization"
    RESOURCE_SCALING = "resource_scaling"


class PerformanceProfile(Enum):
    """Performance profiles for different scenarios"""
    LOW_LATENCY = "low_latency"       # < 10ms latency priority
    HIGH_THROUGHPUT = "high_throughput"  # > 100K msg/s priority
    BALANCED = "balanced"              # Balance between latency and throughput
    POWER_SAVING = "power_saving"      # Minimize resource usage


class PerformanceOptimizer:
    """
    Performance Optimization System for 100K+ Devices
    
    Features:
    - Adaptive batching and buffering
    - Connection pool optimization
    - Message compression
    - Async I/O optimization
    - Cache management
    - Dynamic resource allocation
    - Load prediction
    - Auto-tuning
    """
    
    def __init__(self, config: TMLGatewayConfig):
        self.config = config
        
        # Performance profile
        self.current_profile = PerformanceProfile.BALANCED
        
        # Optimization parameters
        self.optimization_params = {
            'batch_size': 100,
            'batch_timeout_ms': 10,
            'connection_pool_size': 1000,
            'worker_threads': multiprocessing.cpu_count() * 2,
            'message_compression': True,
            'compression_threshold_bytes': 1024,
            'cache_ttl_seconds': 300,
            'max_concurrent_requests': 10000,
            'buffer_size_mb': 256
        }
        
        # Performance metrics
        self.performance_metrics = {
            'message_throughput': deque(maxlen=1000),
            'processing_latency': deque(maxlen=1000),
            'connection_count': deque(maxlen=1000),
            'memory_usage': deque(maxlen=1000),
            'cpu_usage': deque(maxlen=1000)
        }
        
        # Optimization history
        self.optimization_history = []
        
        # Auto-tuning parameters
        self.auto_tuning_enabled = True
        self.tuning_interval_seconds = 60
        self.target_metrics = {
            'latency_p99_ms': 100,
            'throughput_msg_per_sec': 10000,
            'cpu_usage_percent': 70,
            'memory_usage_percent': 80
        }
        
        # Adaptive batching
        self.batch_buffers = {}  # topic -> message_buffer
        self.batch_timers = {}   # topic -> timer
        
        # Connection pooling
        self.connection_pools = {}  # service -> connection_pool
        
        # Performance predictions
        self.load_predictor = LoadPredictor()
        
        self.logger = logger.bind(component="performance_optimizer")
    
    async def initialize(self) -> None:
        """Initialize performance optimizer"""
        try:
            self.logger.info("Initializing performance optimizer",
                           profile=self.current_profile.value)
            
            # Apply initial optimization profile
            await self._apply_performance_profile(self.current_profile)
            
            # Start optimization tasks
            asyncio.create_task(self._auto_tuning_loop())
            asyncio.create_task(self._performance_monitor())
            asyncio.create_task(self._batch_processor())
            
            self.logger.info("Performance optimizer initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize performance optimizer", error=str(e))
            raise
    
    async def optimize_for_devices(self, device_count: int) -> Dict[str, Any]:
        """
        Optimize settings for specific device count
        
        Args:
            device_count: Expected number of concurrent devices
            
        Returns:
            Optimized configuration parameters
        """
        try:
            self.logger.info("Optimizing for device count", device_count=device_count)
            
            optimized_params = {}
            
            # Connection pool sizing
            # Rule: 1 connection per 100 devices minimum
            optimized_params['connection_pool_size'] = max(
                1000,
                device_count // 100
            )
            
            # Worker threads
            # Rule: 1 worker per 1000 devices, min CPU*2, max CPU*8
            cpu_count = multiprocessing.cpu_count()
            optimized_params['worker_threads'] = min(
                max(cpu_count * 2, device_count // 1000),
                cpu_count * 8
            )
            
            # Batch sizing
            if device_count > 50000:
                # Large scale: bigger batches, longer timeout
                optimized_params['batch_size'] = 500
                optimized_params['batch_timeout_ms'] = 50
            elif device_count > 10000:
                # Medium scale
                optimized_params['batch_size'] = 200
                optimized_params['batch_timeout_ms'] = 20
            else:
                # Small scale: smaller batches, shorter timeout
                optimized_params['batch_size'] = 50
                optimized_params['batch_timeout_ms'] = 10
            
            # Buffer sizing
            # Rule: 1MB per 1000 devices, min 64MB, max 2GB
            optimized_params['buffer_size_mb'] = min(
                max(64, device_count // 1000),
                2048
            )
            
            # Cache TTL
            if device_count > 50000:
                # Longer cache for large deployments
                optimized_params['cache_ttl_seconds'] = 600
            else:
                optimized_params['cache_ttl_seconds'] = 300
            
            # Max concurrent requests
            optimized_params['max_concurrent_requests'] = min(
                device_count * 2,
                100000  # Hard limit
            )
            
            # Enable compression for large deployments
            optimized_params['message_compression'] = device_count > 10000
            
            # Update parameters
            self.optimization_params.update(optimized_params)
            
            self.logger.info("Optimization complete",
                           device_count=device_count,
                           params=optimized_params)
            
            return optimized_params
            
        except Exception as e:
            self.logger.error("Failed to optimize for devices",
                            device_count=device_count,
                            error=str(e))
            raise
    
    async def set_performance_profile(self, profile: PerformanceProfile) -> None:
        """
        Set performance profile
        
        Args:
            profile: Performance profile to apply
        """
        try:
            self.logger.info("Setting performance profile", profile=profile.value)
            
            self.current_profile = profile
            await self._apply_performance_profile(profile)
            
        except Exception as e:
            self.logger.error("Failed to set performance profile",
                            profile=profile.value,
                            error=str(e))
            raise
    
    async def _apply_performance_profile(self, profile: PerformanceProfile) -> None:
        """Apply performance profile settings"""
        if profile == PerformanceProfile.LOW_LATENCY:
            # Optimize for minimum latency
            self.optimization_params.update({
                'batch_size': 1,  # No batching
                'batch_timeout_ms': 0,
                'message_compression': False,  # No compression overhead
                'worker_threads': multiprocessing.cpu_count() * 4,
                'max_concurrent_requests': 50000
            })
            
        elif profile == PerformanceProfile.HIGH_THROUGHPUT:
            # Optimize for maximum throughput
            self.optimization_params.update({
                'batch_size': 1000,  # Large batches
                'batch_timeout_ms': 100,
                'message_compression': True,
                'compression_threshold_bytes': 512,
                'worker_threads': multiprocessing.cpu_count() * 2,
                'max_concurrent_requests': 100000
            })
            
        elif profile == PerformanceProfile.BALANCED:
            # Balance between latency and throughput
            self.optimization_params.update({
                'batch_size': 100,
                'batch_timeout_ms': 10,
                'message_compression': True,
                'compression_threshold_bytes': 1024,
                'worker_threads': multiprocessing.cpu_count() * 2,
                'max_concurrent_requests': 20000
            })
            
        elif profile == PerformanceProfile.POWER_SAVING:
            # Minimize resource usage
            self.optimization_params.update({
                'batch_size': 500,
                'batch_timeout_ms': 100,
                'message_compression': True,
                'compression_threshold_bytes': 256,
                'worker_threads': multiprocessing.cpu_count(),
                'max_concurrent_requests': 5000,
                'buffer_size_mb': 64
            })
    
    async def batch_messages(
        self,
        topic: str,
        message: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Add message to batch and return batch if ready
        
        Args:
            topic: Message topic
            message: Message to batch
            
        Returns:
            Batch of messages if ready, None otherwise
        """
        try:
            # Initialize buffer for topic if not exists
            if topic not in self.batch_buffers:
                self.batch_buffers[topic] = []
            
            # Add message to buffer
            self.batch_buffers[topic].append(message)
            
            # Check if batch is ready
            if len(self.batch_buffers[topic]) >= self.optimization_params['batch_size']:
                # Return batch
                batch = self.batch_buffers[topic]
                self.batch_buffers[topic] = []
                
                # Cancel timer if exists
                if topic in self.batch_timers:
                    self.batch_timers[topic].cancel()
                    del self.batch_timers[topic]
                
                return batch
            
            # Set timer if not exists
            if topic not in self.batch_timers:
                timeout_seconds = self.optimization_params['batch_timeout_ms'] / 1000.0
                
                async def flush_batch():
                    await asyncio.sleep(timeout_seconds)
                    if topic in self.batch_buffers and self.batch_buffers[topic]:
                        # Process partial batch
                        batch = self.batch_buffers[topic]
                        self.batch_buffers[topic] = []
                        await self._process_batch(topic, batch)
                    if topic in self.batch_timers:
                        del self.batch_timers[topic]
                
                self.batch_timers[topic] = asyncio.create_task(flush_batch())
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to batch message",
                            topic=topic,
                            error=str(e))
            return None
    
    async def _process_batch(self, topic: str, batch: List[Dict[str, Any]]) -> None:
        """Process a batch of messages"""
        # This would be called by the actual message processor
        self.logger.debug("Processing batch", topic=topic, size=len(batch))
    
    async def _batch_processor(self) -> None:
        """Process batches periodically"""
        while True:
            try:
                await asyncio.sleep(1)
                
                # Check for stale batches
                for topic, buffer in list(self.batch_buffers.items()):
                    if buffer and topic not in self.batch_timers:
                        # Process stale batch
                        batch = buffer
                        self.batch_buffers[topic] = []
                        await self._process_batch(topic, batch)
                
            except Exception as e:
                self.logger.error("Error in batch processor", error=str(e))
                await asyncio.sleep(5)
    
    async def _auto_tuning_loop(self) -> None:
        """Auto-tune performance parameters"""
        while True:
            try:
                await asyncio.sleep(self.tuning_interval_seconds)
                
                if not self.auto_tuning_enabled:
                    continue
                
                # Collect current metrics
                current_metrics = await self._collect_performance_metrics()
                
                # Compare with targets
                adjustments = self._calculate_adjustments(current_metrics)
                
                # Apply adjustments
                if adjustments:
                    await self._apply_adjustments(adjustments)
                    
                    # Record optimization
                    self.optimization_history.append({
                        'timestamp': datetime.utcnow(),
                        'metrics': current_metrics,
                        'adjustments': adjustments
                    })
                
            except Exception as e:
                self.logger.error("Error in auto-tuning", error=str(e))
                await asyncio.sleep(60)
    
    async def _collect_performance_metrics(self) -> Dict[str, float]:
        """Collect current performance metrics"""
        metrics = {}
        
        # Calculate latency percentiles
        if self.performance_metrics['processing_latency']:
            latencies = [m['latency'] for m in self.performance_metrics['processing_latency']]
            metrics['latency_p99_ms'] = np.percentile(latencies, 99) if latencies else 0
            metrics['latency_p95_ms'] = np.percentile(latencies, 95) if latencies else 0
            metrics['latency_p50_ms'] = np.percentile(latencies, 50) if latencies else 0
        
        # Calculate throughput
        if self.performance_metrics['message_throughput']:
            recent_throughput = self.performance_metrics['message_throughput'][-100:]
            metrics['throughput_msg_per_sec'] = sum(m['count'] for m in recent_throughput) / len(recent_throughput)
        
        # System resources
        metrics['cpu_usage_percent'] = psutil.cpu_percent()
        metrics['memory_usage_percent'] = psutil.virtual_memory().percent
        
        # Connection count
        if self.performance_metrics['connection_count']:
            metrics['active_connections'] = self.performance_metrics['connection_count'][-1]['count']
        
        return metrics
    
    def _calculate_adjustments(self, current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Calculate parameter adjustments based on metrics"""
        adjustments = {}
        
        # Check latency
        if 'latency_p99_ms' in current_metrics:
            if current_metrics['latency_p99_ms'] > self.target_metrics['latency_p99_ms']:
                # Reduce batch size to lower latency
                if self.optimization_params['batch_size'] > 10:
                    adjustments['batch_size'] = max(
                        10,
                        int(self.optimization_params['batch_size'] * 0.8)
                    )
                # Reduce batch timeout
                if self.optimization_params['batch_timeout_ms'] > 5:
                    adjustments['batch_timeout_ms'] = max(
                        5,
                        int(self.optimization_params['batch_timeout_ms'] * 0.8)
                    )
        
        # Check throughput
        if 'throughput_msg_per_sec' in current_metrics:
            if current_metrics['throughput_msg_per_sec'] < self.target_metrics['throughput_msg_per_sec']:
                # Increase batch size to improve throughput
                adjustments['batch_size'] = min(
                    1000,
                    int(self.optimization_params['batch_size'] * 1.2)
                )
                # Increase worker threads
                cpu_count = multiprocessing.cpu_count()
                if self.optimization_params['worker_threads'] < cpu_count * 4:
                    adjustments['worker_threads'] = min(
                        cpu_count * 4,
                        self.optimization_params['worker_threads'] + 2
                    )
        
        # Check CPU usage
        if current_metrics.get('cpu_usage_percent', 0) > self.target_metrics['cpu_usage_percent']:
            # Enable compression to reduce CPU
            if not self.optimization_params['message_compression']:
                adjustments['message_compression'] = True
            # Reduce worker threads
            if self.optimization_params['worker_threads'] > multiprocessing.cpu_count():
                adjustments['worker_threads'] = max(
                    multiprocessing.cpu_count(),
                    self.optimization_params['worker_threads'] - 1
                )
        
        # Check memory usage
        if current_metrics.get('memory_usage_percent', 0) > self.target_metrics['memory_usage_percent']:
            # Reduce buffer size
            if self.optimization_params['buffer_size_mb'] > 64:
                adjustments['buffer_size_mb'] = max(
                    64,
                    int(self.optimization_params['buffer_size_mb'] * 0.8)
                )
            # Reduce cache TTL
            if self.optimization_params['cache_ttl_seconds'] > 60:
                adjustments['cache_ttl_seconds'] = max(
                    60,
                    int(self.optimization_params['cache_ttl_seconds'] * 0.8)
                )
        
        return adjustments
    
    async def _apply_adjustments(self, adjustments: Dict[str, Any]) -> None:
        """Apply parameter adjustments"""
        try:
            self.logger.info("Applying performance adjustments", adjustments=adjustments)
            
            # Update parameters
            self.optimization_params.update(adjustments)
            
            # Apply specific adjustments
            if 'worker_threads' in adjustments:
                # Adjust worker pool size
                # This would trigger actual worker adjustment
                pass
            
            if 'connection_pool_size' in adjustments:
                # Adjust connection pool
                # This would trigger pool resizing
                pass
            
        except Exception as e:
            self.logger.error("Failed to apply adjustments",
                            adjustments=adjustments,
                            error=str(e))
    
    async def _performance_monitor(self) -> None:
        """Monitor performance metrics"""
        while True:
            try:
                await asyncio.sleep(1)
                
                # Collect metrics
                timestamp = datetime.utcnow()
                
                # CPU and memory
                self.performance_metrics['cpu_usage'].append({
                    'timestamp': timestamp,
                    'usage': psutil.cpu_percent()
                })
                
                self.performance_metrics['memory_usage'].append({
                    'timestamp': timestamp,
                    'usage': psutil.virtual_memory().percent
                })
                
            except Exception as e:
                self.logger.error("Error in performance monitor", error=str(e))
                await asyncio.sleep(5)
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get optimization report"""
        return {
            'current_profile': self.current_profile.value,
            'optimization_params': self.optimization_params,
            'auto_tuning_enabled': self.auto_tuning_enabled,
            'target_metrics': self.target_metrics,
            'optimization_history': self.optimization_history[-10:] if self.optimization_history else []
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get optimizer status"""
        return {
            'profile': self.current_profile.value,
            'batch_size': self.optimization_params['batch_size'],
            'worker_threads': self.optimization_params['worker_threads'],
            'connection_pool_size': self.optimization_params['connection_pool_size'],
            'compression_enabled': self.optimization_params['message_compression'],
            'auto_tuning': self.auto_tuning_enabled
        }


class LoadPredictor:
    """Predicts future load for proactive optimization"""
    
    def __init__(self):
        self.history = deque(maxlen=1440)  # 24 hours of minute data
        
    def add_sample(self, timestamp: datetime, load: float):
        """Add load sample"""
        self.history.append((timestamp, load))
    
    def predict_next_hour(self) -> List[float]:
        """Predict load for next hour"""
        if len(self.history) < 60:
            return [0.0] * 60
        
        # Simple moving average prediction
        recent_loads = [load for _, load in list(self.history)[-60:]]
        avg_load = sum(recent_loads) / len(recent_loads)
        
        # Add some variance based on time of day
        predictions = []
        current_hour = datetime.utcnow().hour
        
        for i in range(60):
            # Business hours have higher load
            hour = (current_hour + i // 60) % 24
            if 9 <= hour <= 17:
                multiplier = 1.2
            elif 6 <= hour <= 9 or 17 <= hour <= 20:
                multiplier = 1.0
            else:
                multiplier = 0.7
            
            predictions.append(avg_load * multiplier)
        
        return predictions
