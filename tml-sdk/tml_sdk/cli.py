#!/usr/bin/env python3
"""
TML SDK Command Line Interface
"""

import click
import json
from typing import Dict, Any

from .client.tml_client import TMLClient
from .client.config import TMLConfig
from .transactions.transaction import create_transaction


@click.group()
@click.option("--config", "-c", help="Configuration file path")
@click.option("--api-url", help="TML Platform API URL")
@click.option("--api-key", help="API key for authentication")
@click.pass_context
def cli(ctx, config, api_url, api_key):
    """TML SDK Command Line Interface"""
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        tml_config = TMLConfig.from_file(config)
    else:
        tml_config = TMLConfig()
        if api_url:
            tml_config.api_url = api_url
        if api_key:
            tml_config.api_key = api_key
        else:
            # Set a dummy API key for offline mode
            tml_config.api_key = "offline-mode"

    # Initialize client
    ctx.obj["client"] = TMLClient(config=tml_config)


@cli.group()
def models():
    """Model management commands"""
    pass


@models.command()
@click.option("--name", "-n", required=True, help="Model name")
@click.option(
    "--type", "-t", "model_type", default="river_classifier", help="Model type"
)
@click.option("--algorithm", "-a", default="logistic_regression", help="Algorithm")
@click.option("--features", "-f", help="Comma-separated feature names")
@click.pass_context
def create(ctx, name, model_type, algorithm, features):
    """Create a new model"""
    client = ctx.obj["client"]

    feature_list = features.split(",") if features else []

    try:
        model = client.models.create(
            name=name, model_type=model_type, algorithm=algorithm, features=feature_list
        )

        click.echo(f"✅ Model created successfully!")
        click.echo(f"   Name: {model.name}")
        click.echo(f"   ID: {model.model_id}")
        click.echo(f"   Type: {model.model_type}")
        click.echo(f"   Algorithm: {model.algorithm}")

    except Exception as e:
        click.echo(f"❌ Failed to create model: {e}", err=True)


@models.command()
@click.pass_context
def list(ctx):
    """List all models"""
    client = ctx.obj["client"]

    try:
        models_list = client.models.list()

        if not models_list:
            click.echo("No models found.")
            return

        click.echo(f"Found {len(models_list)} models:")
        click.echo()

        for model_info in models_list:
            click.echo(f"📊 {model_info['name']}")
            click.echo(f"   ID: {model_info['model_id']}")
            click.echo(f"   Type: {model_info['model_type']}")
            click.echo(f"   Status: {model_info['status']}")
            click.echo(f"   Created: {model_info['created_at']}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Failed to list models: {e}", err=True)


@models.command()
@click.argument("model_id")
@click.pass_context
def info(ctx, model_id):
    """Get model information"""
    client = ctx.obj["client"]

    try:
        model = client.models.get(model_id)
        model_info = model.get_info()

        click.echo(f"📊 Model Information")
        click.echo(f"   Name: {model_info['name']}")
        click.echo(f"   ID: {model_info['model_id']}")
        click.echo(f"   Type: {model_info['model_type']}")
        click.echo(f"   Status: {model_info['status']}")
        click.echo(f"   Features: {len(model_info['features'])}")
        click.echo(f"   Created: {model_info['created_at']}")
        click.echo(f"   Updated: {model_info['updated_at']}")

        if model_info.get("metrics"):
            click.echo(f"   Metrics: {model_info['metrics']}")

    except Exception as e:
        click.echo(f"❌ Failed to get model info: {e}", err=True)


@cli.group()
def transactions():
    """Transaction management commands"""
    pass


@transactions.command()
@click.option("--features", "-f", required=True, help="Features as JSON string")
@click.option("--label", "-l", help="Transaction label")
@click.option("--source", "-s", help="Data source")
def create(features, label, source):
    """Create a transaction"""
    try:
        features_dict = json.loads(features)

        transaction = create_transaction(
            features=features_dict, label=label, source=source
        )

        click.echo(f"✅ Transaction created successfully!")
        click.echo(f"   ID: {transaction.transaction_id}")
        click.echo(f"   Features: {len(transaction.features)}")
        click.echo(f"   Label: {transaction.label}")
        click.echo(f"   Source: {transaction.source}")

    except json.JSONDecodeError:
        click.echo("❌ Invalid JSON format for features", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to create transaction: {e}", err=True)


@cli.command()
@click.pass_context
def status(ctx):
    """Check TML Platform status"""
    client = ctx.obj["client"]

    try:
        if client.is_connected():
            platform_status = client.get_status()
            platform_info = client.get_info()

            click.echo("🟢 TML Platform Status: Connected")
            click.echo(f"   URL: {client.config.api_url}")
            click.echo(f"   Status: {platform_status.get('status', 'unknown')}")
            click.echo(f"   Version: {platform_info.get('version', 'unknown')}")
        else:
            click.echo("🔴 TML Platform Status: Disconnected")
            click.echo(f"   URL: {client.config.api_url}")
            click.echo("   Running in offline mode")

    except Exception as e:
        click.echo(f"❌ Failed to check status: {e}", err=True)


@cli.command()
def version():
    """Show SDK version"""
    from . import __version__

    click.echo(f"TML SDK version: {__version__}")


def main():
    """Main CLI entry point"""
    cli()


if __name__ == "__main__":
    main()
