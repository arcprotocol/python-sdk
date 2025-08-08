"""
ARC Server Module

Provides components for building ARC-compatible servers.
"""

from .arc_server import ARCServer, create_server
from .middleware import (
    extract_auth_context, cors_middleware, logging_middleware,
    AuthMiddleware
)
from .decorators import (
    validate_params, require_scopes, task_method,
    chat_method, error_handler, trace_method
)
from .sse import SSEResponse, create_chat_stream

__all__ = [
    # Server
    "ARCServer",
    "create_server",
    
    # Middleware
    "extract_auth_context",
    "cors_middleware",
    "logging_middleware",
    "AuthMiddleware",
    
    # Decorators
    "validate_params",
    "require_scopes",
    "task_method",
    "chat_method",
    "error_handler",
    "trace_method",
    
    # SSE Support
    "SSEResponse",
    "create_chat_stream"
]
