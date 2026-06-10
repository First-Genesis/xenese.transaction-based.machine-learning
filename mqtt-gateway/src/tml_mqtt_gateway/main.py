"""
TML MQTT Gateway Main Entry Point
Production-ready MQTT Gateway service
"""

import asyncio
import os
import sys
from pathlib import Path

import structlog
from structlog.stdlib import LoggingFactory

from .config import load_config
from .gateway import TMLMQTTGateway


def setup_logging(log_level: str = "INFO") -> None:
    """Setup structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggingFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set log level
    import logging

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


async def main():
    """Main entry point for TML MQTT Gateway"""

    # Load configuration
    config_path = os.getenv("CONFIG_PATH", "/app/config/gateway.yaml")
    if not os.path.exists(config_path):
        config_path = None

    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(config.gateway.log_level)
    logger = structlog.get_logger("tml_mqtt_gateway")

    logger.info(
        "Starting TML MQTT Gateway",
        version="1.0.0",
        gateway_id=config.gateway.gateway_id,
    )

    # Create and initialize gateway
    gateway = TMLMQTTGateway(config)

    try:
        # Initialize all components
        await gateway.initialize()

        # Start the gateway service
        await gateway.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error("Gateway failed", error=str(e))
        sys.exit(1)
    finally:
        # Ensure clean shutdown
        await gateway.stop()
        logger.info("TML MQTT Gateway stopped")


def cli_main():
    """CLI entry point"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
