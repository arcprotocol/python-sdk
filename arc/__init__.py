"""
Agent Remote Communication (ARC) Protocol - Python Implementation

The first RPC protocol that solves multi-agent deployment complexity with built-in agent routing,
load balancing, and workflow tracing. Deploy hundreds of different agent types on a single endpoint
with zero infrastructure overhead.

Homepage: https://arc-protocol.org
Documentation: https://docs.arc-protocol.org
"""

__version__ = "1.3.1"
__author__ = "Moein Roghani"
__email__ = "moein.roghani@proton.me"
__license__ = "Apache-2.0"

# Clean, simple API - the main classes developers use
from .client.arc_client import ARCClient as Client
from .client.thread_manager import ThreadManager
from .server.arc_server import ARCServer as Server

# Storage backends for persistent chat sessions
from .server.storage import (
    ChatStorage,
    RedisChatStorage,
    PostgreSQLChatStorage,
    MongoChatStorage
)

# Core exceptions
from .exceptions import (
    ARCException, RpcError, ParseError, InvalidRequestError,
    MethodNotFoundError, InvalidParamsError, InternalError,
    
    # Agent errors
    ARCAgentError, AgentNotFoundError, AgentNotAvailableError,
    AgentUnreachableError, InvalidAgentIdError, AgentAuthenticationError,
    AgentTimeoutError,
    
    # Task errors
    ARCTaskError, TaskNotFoundError, TaskAlreadyCompletedError,
    TaskAlreadyCanceledError, TaskExecutionError, TaskTimeoutError,
    InvalidTaskStatusTransitionError,
    
    # Chat errors
    ARCChatError, ChatNotFoundError, ChatAlreadyClosedError,
    ChatTimeoutError, ChatParticipantLimitError, InvalidChatMessageError,
    
    # Security errors
    ARCSecurityError, AuthenticationError, AuthorizationError,
    InsufficientScopeError, TokenExpiredError, TokenInvalidError,
    PermissionDeniedError, RateLimitExceededError,
    
    # Protocol errors
    ARCProtocolError, InvalidARCVersionError, MissingRequiredFieldError,
    InvalidFieldFormatError, MessageTooLargeError, WorkflowTraceInvalidError,
    
    # Network errors
    NetworkError, ConnectionError, TimeoutError, SSLError,
    
    # Client errors
    ClientError, ConfigurationError, ValidationError,
    SerializationError, DeserializationError
)

# Models from schema 
from .models import (
    # Enum Types
    Role, PartType, Encoding, TaskStatus, ChatStatus,
    Priority, EventType, ResultType,
    
    # Base Models
    Part, Message, Artifact, TaskObject, ChatObject,
    SubscriptionObject, ErrorObject,
    
    # Method Parameters
    TaskCreateParams, TaskSendParams, TaskInfoParams, TaskCancelParams,
    TaskSubscribeParams, TaskNotificationParams, ChatStartParams,
    ChatMessageParams, ChatEndParams,
    
    # Result Types
    TaskResult, ChatResult, SubscriptionResult, SuccessResult,
    MethodResult,
    
    # Request/Response
    ARCRequest, ARCResponse
)

# Core processing
from .core import (
    ValidationResult, validate_arc_request, validate_arc_response,
    validate_method_params, validate_message, validate_request,
    validate_response, RequestValidator, ARCProcessor,
    ChatManager, ChatConsumer, ChatProducer,
    Subscription, WebhookManager
)

# Authentication
from .auth import (
    OAuth2Token, OAuth2ClientCredentials, OAuth2Config, 
    create_oauth2_client, OAuth2Handler, JWTValidator,
    OAuth2ProviderValidator, MultiProviderJWTValidator,
    create_validator_from_config
)

# Schema utilities
from .schemas import ARCSchema, get_schema

# Server components
from .server import (
    ARCServer, create_server, extract_auth_context,
    validate_params, require_scopes, task_method,
    chat_method, error_handler, trace_method
)

# Framework integrations (optional imports)
try:
    from . import fastapi
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

try:
    from . import starlette
    _HAS_STARLETTE = True
except ImportError:
    _HAS_STARLETTE = False

# Version information
def get_version():
    """Return the current version of the ARC SDK."""
    return __version__

# Convenience functions
def create_client(endpoint: str, token: str = None, **kwargs):
    """
    Create an ARC client with the given endpoint and token.
    
    Args:
        endpoint: The ARC endpoint URL
        token: OAuth2 bearer token for authentication
        **kwargs: Additional client configuration options
        
    Returns:
        An initialized ARCClient instance
    """
    from .client.arc_client import ARCClient
    return ARCClient(endpoint=endpoint, token=token, **kwargs)

def create_server_app(agent_id: str, **kwargs):
    """
    Create an ARC server with the given agent ID.
    
    Args:
        agent_id: ID of the agent
        **kwargs: Additional server configuration options
        
    Returns:
        Initialized ARCServer instance
    """
    return Server(agent_id=agent_id, **kwargs)

# Essential exports
__all__ = [
    # Main API - what most developers need
    "Client",           # arc.Client (clean name)
    "Server",           # arc.Server (clean name)
    "ThreadManager",    # arc.ThreadManager (client-side thread mapping)
    "create_client",    # Convenience function
    "create_server_app", # Convenience function
    "get_version",      # Version info
    
    # Storage backends for ChatManager
    "ChatStorage",      # Abstract base class
    "RedisChatStorage", # Redis implementation
    "PostgreSQLChatStorage", # PostgreSQL implementation
    "MongoChatStorage", # MongoDB implementation
    
    # Core exceptions
    "ARCException", "RpcError", "ParseError", "InvalidRequestError",
    "MethodNotFoundError", "InvalidParamsError", "InternalError",
    
    # Agent errors
    "ARCAgentError", "AgentNotFoundError", "AgentNotAvailableError",
    "AgentUnreachableError", "InvalidAgentIdError", "AgentAuthenticationError",
    "AgentTimeoutError",
    
    # Task errors
    "ARCTaskError", "TaskNotFoundError", "TaskAlreadyCompletedError",
    "TaskAlreadyCanceledError", "TaskExecutionError", "TaskTimeoutError",
    "InvalidTaskStatusTransitionError",
    
    # Chat errors
    "ARCChatError", "ChatNotFoundError", "ChatAlreadyClosedError",
    "ChatTimeoutError", "ChatParticipantLimitError", "InvalidChatMessageError",
    
    # Security errors
    "ARCSecurityError", "AuthenticationError", "AuthorizationError",
    "InsufficientScopeError", "TokenExpiredError", "TokenInvalidError",
    "PermissionDeniedError", "RateLimitExceededError",
    
    # Protocol errors
    "ARCProtocolError", "InvalidARCVersionError", "MissingRequiredFieldError",
    "InvalidFieldFormatError", "MessageTooLargeError", "WorkflowTraceInvalidError",
    
    # Network errors
    "NetworkError", "ConnectionError", "TimeoutError", "SSLError",
    
    # Client errors
    "ClientError", "ConfigurationError", "ValidationError",
    "SerializationError", "DeserializationError",
    
    # Core Models (most commonly used)
    "Role", "PartType", "TaskStatus", "ChatStatus", "Priority",
    "Part", "Message", "Artifact", "TaskObject", "ChatObject",
    "TaskResult", "ChatResult", "SuccessResult",
    "ARCRequest", "ARCResponse",
    
    # Core Processing
    "validate_request", "validate_response", "ARCProcessor",
    "ChatManager", "WebhookManager"
]