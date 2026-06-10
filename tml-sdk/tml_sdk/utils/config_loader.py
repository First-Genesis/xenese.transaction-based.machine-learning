"""
Configuration Loading Utilities
Helper functions for loading and saving configuration files
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any

from ..client.exceptions import TMLConfigError


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dict: Configuration data
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise TMLConfigError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yml', '.yaml']:
                return yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                return json.load(f)
            else:
                raise TMLConfigError(f"Unsupported config format: {config_path.suffix}")
    except Exception as e:
        raise TMLConfigError(f"Failed to load config: {e}")


def save_config(config_data: Dict[str, Any], config_path: str, format: str = "yaml"):
    """
    Save configuration to file
    
    Args:
        config_data: Configuration data
        config_path: Path to save configuration
        format: File format (yaml or json)
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(config_path, 'w') as f:
            if format.lower() in ['yml', 'yaml']:
                yaml.dump(config_data, f, default_flow_style=False)
            elif format.lower() == 'json':
                json.dump(config_data, f, indent=2)
            else:
                raise TMLConfigError(f"Unsupported format: {format}")
    except Exception as e:
        raise TMLConfigError(f"Failed to save config: {e}")
