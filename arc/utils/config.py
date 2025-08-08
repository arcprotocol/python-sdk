"""
ARC Configuration Utilities

Provides utilities for loading and managing ARC configuration.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load ARC configuration from file.
    
    Looks for configuration in the following order:
    1. Specified config_path
    2. ARCCONFIG environment variable
    3. ~/.arc/config.json
    4. ./.arc.json
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        Dictionary containing configuration
    """
    config = {}
    
    # Check for explicit path
    if config_path and os.path.exists(config_path):
        config = _load_json_file(config_path)
    
    # Check environment variable
    elif "ARCCONFIG" in os.environ and os.path.exists(os.environ["ARCCONFIG"]):
        config = _load_json_file(os.environ["ARCCONFIG"])
    
    # Check user home directory
    elif os.path.exists(os.path.expanduser("~/.arc/config.json")):
        config = _load_json_file(os.path.expanduser("~/.arc/config.json"))
    
    # Check current directory
    elif os.path.exists("./.arc.json"):
        config = _load_json_file("./.arc.json")
    
    return config


def _load_json_file(file_path: str) -> Dict[str, Any]:
    """
    Load JSON from file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary containing file contents
        
    Raises:
        ValueError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse config file: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load config file: {e}")


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Save configuration to file.
    
    Args:
        config: Configuration dictionary
        config_path: Path to save config file
        
    Raises:
        ValueError: If file cannot be saved
    """
    try:
        # Create directory if needed
        directory = os.path.dirname(config_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Save config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        raise ValueError(f"Failed to save config file: {e}")


def get_default_config_path() -> str:
    """
    Get default configuration file path.
    
    Returns:
        Path to default config file
    """
    return os.path.expanduser("~/.arc/config.json")


def load_credentials(credentials_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load ARC API credentials.
    
    Looks for credentials in the following order:
    1. Specified credentials_path
    2. ARCCREDENTIALS environment variable
    3. ~/.arc/credentials.json
    
    Args:
        credentials_path: Optional explicit path to credentials file
        
    Returns:
        Dictionary mapping profile names to credential configurations
    """
    # Check for explicit path
    if credentials_path and os.path.exists(credentials_path):
        return _load_json_file(credentials_path)
    
    # Check environment variable
    if "ARCCREDENTIALS" in os.environ and os.path.exists(os.environ["ARCCREDENTIALS"]):
        return _load_json_file(os.environ["ARCCREDENTIALS"])
    
    # Check user home directory
    creds_path = os.path.expanduser("~/.arc/credentials.json")
    if os.path.exists(creds_path):
        return _load_json_file(creds_path)
    
    return {}


def get_profile_credentials(profile: str = "default") -> Dict[str, Any]:
    """
    Get credentials for a specific profile.
    
    Args:
        profile: Profile name
        
    Returns:
        Credential configuration for the profile
    """
    credentials = load_credentials()
    return credentials.get(profile, {})