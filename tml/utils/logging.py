"""Logging configuration and utilities for TML platform."""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from tml.core.config import config


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to loguru."""

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    json_logs: bool = False,
    intercept_stdlib: bool = True,
):
    """Setup logging configuration for TML platform."""

    # Remove default loguru handler
    logger.remove()

    # Determine log level
    if log_level is None:
        log_level = config.log_level

    # Console handler
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    if json_logs:
        console_format = (
            '{"time": "{time:YYYY-MM-DD HH:mm:ss}", '
            '"level": "{level}", '
            '"module": "{name}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"message": "{message}"}'
        )

    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=not json_logs,
        backtrace=True,
        diagnose=True,
    )

    # File handler
    if log_file or config.logs_dir:
        if not log_file:
            log_file = config.logs_dir / "tml.log"

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

        logger.add(
            log_file,
            format=file_format,
            level=log_level,
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            backtrace=True,
            diagnose=True,
        )

    # Intercept standard library logging
    if intercept_stdlib:
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        # Intercept specific loggers
        for logger_name in [
            "uvicorn",
            "uvicorn.access",
            "fastapi",
            "kafka",
            "cassandra",
            "redis",
            "mlflow",
        ]:
            logging.getLogger(logger_name).handlers = [InterceptHandler()]

    logger.info(f"Logging configured with level: {log_level}")


def get_logger(name: str):
    """Get a logger instance for a specific module."""
    return logger.bind(name=name)


# Performance logging decorator
def log_performance(func_name: Optional[str] = None):
    """Decorator to log function performance."""

    def decorator(func):
        import time
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                logger.debug(f"Performance: {name} executed in {execution_time:.2f}ms")
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Performance: {name} failed after {execution_time:.2f}ms: {e}"
                )
                raise

        return wrapper

    return decorator


# Async performance logging decorator
def log_async_performance(func_name: Optional[str] = None):
    """Decorator to log async function performance."""

    def decorator(func):
        import asyncio
        import time
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                logger.debug(f"Performance: {name} executed in {execution_time:.2f}ms")
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Performance: {name} failed after {execution_time:.2f}ms: {e}"
                )
                raise

        return wrapper

    return decorator


# Context manager for logging blocks
class LoggingContext:
    """Context manager for logging code blocks."""

    def __init__(self, name: str, level: str = "INFO"):
        self.name = name
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.log(self.level, f"Starting: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = (time.time() - self.start_time) * 1000

        if exc_type is None:
            logger.log(self.level, f"Completed: {self.name} in {execution_time:.2f}ms")
        else:
            logger.error(f"Failed: {self.name} after {execution_time:.2f}ms: {exc_val}")


# Initialize logging on import
setup_logging()
