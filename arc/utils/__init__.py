"""
ARC Utilities Module

Provides utility functions and helpers for ARC protocol implementation.
"""

from .schema import (
    load_arc_schema, get_schema_version, get_schema_info,
    get_available_methods, get_method_documentation
)

from .logging import (
    create_logger, get_logger, configure_root_logger,
    log_request, log_response, create_correlation_id, create_trace_id,
    ContextAdapter, JsonFormatter
)

from .config import (
    load_config, save_config, get_default_config_path,
    load_credentials, get_profile_credentials
)

from .agent_card import (
    load_agent_card_schema, validate_agent_card, create_agent_card,
    load_agent_card, save_agent_card, get_agent_capabilities,
    get_agent_methods, supports_method, has_capability,
    get_agent_info_as_dict, AgentCardRegistry
)

from .testing import (
    MockARCClient, MockARCServer, MockTaskMethods, MockStreamMethods,
    create_test_message, create_test_task_object, 
    create_test_stream_object, create_test_artifact
)

__all__ = [
    # Schema utilities
    "load_arc_schema",
    "get_schema_version",
    "get_schema_info",
    "get_available_methods",
    "get_method_documentation",
    
    # Logging utilities
    "create_logger",
    "get_logger",
    "configure_root_logger",
    "log_request",
    "log_response",
    "create_correlation_id",
    "create_trace_id",
    "ContextAdapter",
    "JsonFormatter",
    
    # Config utilities
    "load_config",
    "save_config",
    "get_default_config_path",
    "load_credentials",
    "get_profile_credentials",
    
    # Agent card utilities
    "load_agent_card_schema",
    "validate_agent_card",
    "create_agent_card",
    "load_agent_card",
    "save_agent_card",
    "get_agent_capabilities",
    "get_agent_methods",
    "supports_method",
    "has_capability",
    "get_agent_info_as_dict",
    "AgentCardRegistry",
    
    # Testing utilities
    "MockARCClient",
    "MockARCServer", 
    "MockTaskMethods",
    "MockStreamMethods",
    "create_test_message",
    "create_test_task_object",
    "create_test_stream_object",
    "create_test_artifact"
]
