"""
ARC Agent Card Utilities

Utilities for working with ARC agent cards - metadata about agents
including their capabilities, methods, and documentation.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


logger = logging.getLogger(__name__)


def get_agent_card_schema_path() -> Path:
    """Get the path to the agent card schema file"""
    return Path(__file__).parent.parent / "schemas" / "agent-card.schema.json"


def load_agent_card_schema() -> Dict[str, Any]:
    """
    Load the agent card JSON schema.
    
    Returns:
        Agent card schema
        
    Raises:
        FileNotFoundError: If schema file not found
        ValueError: If schema cannot be parsed
    """
    schema_path = get_agent_card_schema_path()
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Agent card schema not found at: {schema_path}")
    
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        logger.debug(f"Loaded agent card schema from: {schema_path}")
        return schema
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse agent card schema: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load agent card schema: {e}")


def validate_agent_card(card: Dict[str, Any]) -> bool:
    """
    Validate an agent card against the schema.
    
    Args:
        card: Agent card to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ImportError: If jsonschema package is not available
    """
    if not JSONSCHEMA_AVAILABLE:
        raise ImportError(
            "jsonschema package is required for validation. "
            "Install it with: pip install jsonschema"
        )
    
    try:
        schema = load_agent_card_schema()
        jsonschema.validate(instance=card, schema=schema)
        return True
    except jsonschema.exceptions.ValidationError as e:
        logger.warning(f"Agent card validation failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Agent card validation error: {e}")
        return False


def create_agent_card(
    agent_id: str,
    name: str,
    description: str,
    version: str = "1.0.0",
    contact: Optional[Dict[str, str]] = None,
    capabilities: Optional[List[str]] = None,
    methods: Optional[List[str]] = None,
    api_url: Optional[str] = None,
    docs_url: Optional[str] = None,
    logo_url: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an agent card object.
    
    Args:
        agent_id: Unique ID of the agent
        name: Display name of the agent
        description: Detailed description of the agent
        version: Agent version
        contact: Optional contact information
        capabilities: Optional list of agent capabilities
        methods: Optional list of supported ARC methods
        api_url: Optional ARC endpoint URL
        docs_url: Optional documentation URL
        logo_url: Optional logo URL
        model: Optional underlying model information
        
    Returns:
        Agent card object
    """
    card = {
        "schema": "https://arc-protocol.org/schemas/agent-card/v1.0.0",
        "agentId": agent_id,
        "name": name,
        "description": description,
        "version": version
    }
    
    # Add optional fields if provided
    if contact:
        card["contact"] = contact
    
    if capabilities:
        card["capabilities"] = capabilities
    
    if methods:
        card["methods"] = methods
    
    if api_url:
        card["apiUrl"] = api_url
    
    if docs_url:
        card["docsUrl"] = docs_url
    
    if logo_url:
        card["logoUrl"] = logo_url
    
    if model:
        card["model"] = model
    
    return card


def load_agent_card(file_path: str) -> Dict[str, Any]:
    """
    Load agent card from file.
    
    Args:
        file_path: Path to agent card JSON file
        
    Returns:
        Agent card object
        
    Raises:
        FileNotFoundError: If file not found
        ValueError: If file cannot be parsed
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Agent card file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            card = json.load(f)
        
        logger.debug(f"Loaded agent card from: {file_path}")
        return card
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse agent card: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load agent card: {e}")


def save_agent_card(card: Dict[str, Any], file_path: str, validate: bool = True) -> None:
    """
    Save agent card to file.
    
    Args:
        card: Agent card object
        file_path: Path to save card to
        validate: Whether to validate card before saving
        
    Raises:
        ValueError: If validation fails or file cannot be saved
    """
    if validate and JSONSCHEMA_AVAILABLE:
        if not validate_agent_card(card):
            raise ValueError("Agent card validation failed")
    
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(card, f, indent=2)
            
        logger.debug(f"Saved agent card to: {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to save agent card: {e}")


def get_agent_capabilities(card: Dict[str, Any]) -> List[str]:
    """
    Get capabilities from agent card.
    
    Args:
        card: Agent card object
        
    Returns:
        List of capability strings
    """
    return card.get("capabilities", [])


def get_agent_methods(card: Dict[str, Any]) -> List[str]:
    """
    Get supported methods from agent card.
    
    Args:
        card: Agent card object
        
    Returns:
        List of method names
    """
    return card.get("methods", [])


def supports_method(card: Dict[str, Any], method: str) -> bool:
    """
    Check if agent supports a specific method.
    
    Args:
        card: Agent card object
        method: Method name to check
        
    Returns:
        True if method is supported
    """
    methods = get_agent_methods(card)
    return method in methods


def has_capability(card: Dict[str, Any], capability: str) -> bool:
    """
    Check if agent has a specific capability.
    
    Args:
        card: Agent card object
        capability: Capability to check
        
    Returns:
        True if agent has capability
    """
    capabilities = get_agent_capabilities(card)
    return capability in capabilities


def get_agent_info_as_dict(
    agent_id: str,
    name: str,
    description: str,
    methods: List[str],
    status: str = "active",
    endpoints: Optional[Dict[str, str]] = None,
    capabilities: Optional[List[str]] = None,
    version: str = "1.0.0"
) -> Dict[str, Any]:
    """
    Generate agent information dictionary for agent-info endpoint.
    
    Args:
        agent_id: Agent ID
        name: Agent name
        description: Agent description
        methods: Supported methods
        status: Agent status
        endpoints: API endpoints
        capabilities: Agent capabilities
        version: Agent version
        
    Returns:
        Agent information dictionary
    """
    info = {
        "agentId": agent_id,
        "name": name,
        "description": description,
        "supportedMethods": methods,
        "status": status,
        "version": version
    }
    
    if endpoints:
        info["endpoints"] = endpoints
    else:
        info["endpoints"] = {"arc": "/arc"}
    
    if capabilities:
        info["capabilities"] = capabilities
    
    return info


def get_agent_prompt(card: Dict[str, Any]) -> Optional[str]:
    """
    Extract agent prompt from agent card.
    
    Args:
        card: Agent card object
        
    Returns:
        Agent prompt string if available, None otherwise
    """
    return card.get("prompt")


class AgentCardRegistry:
    """
    Registry for managing multiple agent cards.
    
    Provides lookup by agent ID and capability matching.
    """
    
    def __init__(self):
        """Initialize empty registry"""
        self.cards: Dict[str, Dict[str, Any]] = {}
    
    def register(self, card: Dict[str, Any]) -> None:
        """
        Register an agent card.
        
        Args:
            card: Agent card object
            
        Raises:
            ValueError: If card is invalid or missing agentId
        """
        if "agentId" not in card:
            raise ValueError("Agent card missing agentId")
        
        agent_id = card["agentId"]
        self.cards[agent_id] = card
    
    def unregister(self, agent_id: str) -> None:
        """
        Remove agent card from registry.
        
        Args:
            agent_id: Agent ID to remove
        """
        if agent_id in self.cards:
            del self.cards[agent_id]
    
    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent card by ID.
        
        Args:
            agent_id: Agent ID to look up
            
        Returns:
            Agent card if found, None otherwise
        """
        return self.cards.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """
        Get list of registered agent IDs.
        
        Returns:
            List of agent IDs
        """
        return list(self.cards.keys())
    
    def find_by_capability(self, capability: str) -> List[str]:
        """
        Find agents with a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of matching agent IDs
        """
        return [
            agent_id for agent_id, card in self.cards.items()
            if has_capability(card, capability)
        ]
    
    def find_by_method(self, method: str) -> List[str]:
        """
        Find agents supporting a specific method.
        
        Args:
            method: Method name to search for
            
        Returns:
            List of matching agent IDs
        """
        return [
            agent_id for agent_id, card in self.cards.items()
            if supports_method(card, method)
        ]
    
    def load_from_directory(self, directory_path: str) -> int:
        """
        Load agent cards from a directory.
        
        Args:
            directory_path: Path to directory containing agent card JSON files
            
        Returns:
            Number of cards loaded
        """
        if not os.path.isdir(directory_path):
            raise ValueError(f"Not a directory: {directory_path}")
        
        count = 0
        for filename in os.listdir(directory_path):
            if filename.endswith(".json"):
                try:
                    file_path = os.path.join(directory_path, filename)
                    card = load_agent_card(file_path)
                    self.register(card)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to load agent card from {filename}: {e}")
        
        return count