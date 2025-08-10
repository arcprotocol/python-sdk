"""
ARC Exception Classes

Consolidated exception hierarchy for the ARC Python SDK.
Contains standard exceptions for RPC errors, authentication failures,
network issues, and ARC-specific business logic errors.
"""


class ARCException(Exception):
    """
    Base exception for all ARC-related errors.
    
    Provides common functionality for error tracking and debugging.
    """
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self):
        """Convert exception to dictionary format"""
        return {
            "error": self.__class__.__name__,
            "message": str(self),
            "error_code": self.error_code,
            "details": self.details
        }


# === Core RPC Errors ===

class RpcError(ARCException):
    """
    RPC protocol error.
    
    Represents errors in the RPC protocol itself, not business logic errors.
    These errors have standard codes as defined in the ARC Protocol specification.
    """
    
    def __init__(self, code: int, message: str, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


class ParseError(RpcError):
    """JSON could not be parsed"""
    def __init__(self, message: str = "Parse error", data=None):
        super().__init__(-32700, message, data)


class InvalidRequestError(RpcError):
    """The request object is not a valid ARC request"""
    def __init__(self, message: str = "Invalid request", data=None):
        super().__init__(-32600, message, data)


class MethodNotFoundError(RpcError):
    """The requested method does not exist or is not available"""
    def __init__(self, message: str = "Method not found", data=None):
        super().__init__(-32601, message, data)


class InvalidParamsError(RpcError):
    """Invalid method parameters"""
    def __init__(self, message: str = "Invalid params", data=None):
        super().__init__(-32602, message, data)


class InternalError(RpcError):
    """Internal server error"""
    def __init__(self, message: str = "Internal error", data=None):
        super().__init__(-32603, message, data)


# === ARC-Specific Errors ===

class ARCAgentError(ARCException):
    """Base class for agent-related errors (-41000 to -41099)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


class AgentNotFoundError(ARCAgentError):
    """Agent not found"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41001, message or f"Agent not found: {agent_id}", details)


class AgentNotAvailableError(ARCAgentError):
    """Agent is not available"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41002, message or f"Agent not available: {agent_id}", details)


class AgentUnreachableError(ARCAgentError):
    """Agent is unreachable"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41003, message or f"Agent unreachable: {agent_id}", details)


class InvalidAgentIdError(ARCAgentError):
    """Invalid agent ID format"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41004, message or f"Invalid agent ID: {agent_id}", details)


class AgentAuthenticationError(ARCAgentError):
    """Agent authentication failed"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41005, message or f"Agent authentication failed: {agent_id}", details)


class AgentTimeoutError(ARCAgentError):
    """Agent timed out"""
    def __init__(self, agent_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["agent_id"] = agent_id
        super().__init__(-41006, message or f"Agent timed out: {agent_id}", details)


# === Task Errors ===

class ARCTaskError(ARCException):
    """Base class for task-related errors (-42000 to -42099)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


class TaskNotFoundError(ARCTaskError):
    """Task not found"""
    def __init__(self, task_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(-42001, message or f"Task not found: {task_id}", details)


class TaskAlreadyCompletedError(ARCTaskError):
    """Task already completed"""
    def __init__(self, task_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(-42002, message or f"Task already completed: {task_id}", details)


class TaskAlreadyCanceledError(ARCTaskError):
    """Task already canceled"""
    def __init__(self, task_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(-42003, message or f"Task already canceled: {task_id}", details)


class TaskExecutionError(ARCTaskError):
    """Task execution failed"""
    def __init__(self, task_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(-42004, message or f"Task execution failed: {task_id}", details)


class TaskTimeoutError(ARCTaskError):
    """Task timed out"""
    def __init__(self, task_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["task_id"] = task_id
        super().__init__(-42005, message or f"Task timed out: {task_id}", details)


class InvalidTaskStatusTransitionError(ARCTaskError):
    """Invalid task status transition"""
    def __init__(self, task_id: str, from_status: str, to_status: str, message: str = None, details: dict = None):
        details = details or {}
        details.update({
            "task_id": task_id,
            "from_status": from_status,
            "to_status": to_status
        })
        super().__init__(-42006, message or f"Invalid task status transition: {from_status} -> {to_status}", details)


# === Chat Errors ===

class ARCChatError(ARCException):
    """Base class for chat-related errors (-43000 to -43099)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


# === Stream Errors ===

class ARCStreamError(ARCException):
    """Base class for stream-related errors (-43100 to -43199)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


class StreamNotFoundError(ARCStreamError):
    """Stream not found"""
    def __init__(self, stream_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["stream_id"] = stream_id
        super().__init__(-43101, message or f"Stream not found: {stream_id}", details)


class StreamAlreadyClosedError(ARCStreamError):
    """Stream already closed"""
    def __init__(self, stream_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["stream_id"] = stream_id
        super().__init__(-43102, message or f"Stream already closed: {stream_id}", details)


class InvalidStreamMessageError(ARCStreamError):
    """Invalid stream message"""
    def __init__(self, stream_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["stream_id"] = stream_id
        super().__init__(-43103, message or f"Invalid stream message: {stream_id}", details)


class StreamTimeoutError(ARCStreamError):
    """Stream timed out"""
    def __init__(self, stream_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["stream_id"] = stream_id
        super().__init__(-43104, message or f"Stream timed out: {stream_id}", details)


class ChatNotFoundError(ARCChatError):
    """Chat not found"""
    def __init__(self, chat_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["chat_id"] = chat_id
        super().__init__(-43001, message or f"Chat not found: {chat_id}", details)


class ChatAlreadyClosedError(ARCChatError):
    """Chat already closed"""
    def __init__(self, chat_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["chat_id"] = chat_id
        super().__init__(-43002, message or f"Chat already closed: {chat_id}", details)


class ChatTimeoutError(ARCChatError):
    """Chat timed out"""
    def __init__(self, chat_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["chat_id"] = chat_id
        super().__init__(-43003, message or f"Chat timed out: {chat_id}", details)


class ChatParticipantLimitError(ARCChatError):
    """Chat participant limit exceeded"""
    def __init__(self, chat_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["chat_id"] = chat_id
        super().__init__(-43004, message or f"Chat participant limit exceeded: {chat_id}", details)


class InvalidChatMessageError(ARCChatError):
    """Invalid chat message"""
    def __init__(self, chat_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["chat_id"] = chat_id
        super().__init__(-43005, message or f"Invalid chat message: {chat_id}", details)


# === Security Errors ===

class ARCSecurityError(ARCException):
    """Base class for security-related errors (-44000 to -44099)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


class AuthenticationError(ARCSecurityError):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication failed", details: dict = None):
        super().__init__(-44001, message, details)


class AuthorizationError(ARCSecurityError):
    """Authorization failed"""
    def __init__(self, message: str = "Authorization failed", details: dict = None):
        super().__init__(-44002, message, details)


class InsufficientScopeError(ARCSecurityError):
    """Insufficient OAuth2 scope"""
    def __init__(self, required_scopes: list, provided_scopes: list = None, message: str = None, details: dict = None):
        details = details or {}
        details.update({
            "required_scopes": required_scopes,
            "provided_scopes": provided_scopes or []
        })
        super().__init__(-44003, message or f"Insufficient OAuth2 scope", details)


class TokenExpiredError(ARCSecurityError):
    """Token expired"""
    def __init__(self, message: str = "Token expired", details: dict = None):
        super().__init__(-44004, message, details)


class TokenInvalidError(ARCSecurityError):
    """Token invalid"""
    def __init__(self, message: str = "Token invalid", details: dict = None):
        super().__init__(-44005, message, details)


class PermissionDeniedError(ARCSecurityError):
    """Permission denied"""
    def __init__(self, message: str = "Permission denied", details: dict = None):
        super().__init__(-44006, message, details)


class RateLimitExceededError(ARCSecurityError):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", details: dict = None):
        super().__init__(-44007, message, details)


# === Protocol Errors ===

class ARCProtocolError(ARCException):
    """Base class for protocol-related errors (-45000 to -45099)"""
    def __init__(self, code: int, message: str, details: dict = None):
        super().__init__(message, str(code), details)
        self.code = code


class InvalidARCVersionError(ARCProtocolError):
    """Invalid ARC version"""
    def __init__(self, version: str, message: str = None, details: dict = None):
        details = details or {}
        details["version"] = version
        super().__init__(-45001, message or f"Invalid ARC version: {version}", details)


class MissingRequiredFieldError(ARCProtocolError):
    """Missing required field"""
    def __init__(self, field: str, message: str = None, details: dict = None):
        details = details or {}
        details["field"] = field
        super().__init__(-45002, message or f"Missing required field: {field}", details)


class InvalidFieldFormatError(ARCProtocolError):
    """Invalid field format"""
    def __init__(self, field: str, value: str, message: str = None, details: dict = None):
        details = details or {}
        details.update({
            "field": field,
            "value": value
        })
        super().__init__(-45003, message or f"Invalid format for field {field}: {value}", details)


class MessageTooLargeError(ARCProtocolError):
    """Message too large"""
    def __init__(self, size: int, max_size: int, message: str = None, details: dict = None):
        details = details or {}
        details.update({
            "size": size,
            "max_size": max_size
        })
        super().__init__(-45004, message or f"Message too large: {size} bytes (max {max_size})", details)


class WorkflowTraceInvalidError(ARCProtocolError):
    """Workflow trace invalid"""
    def __init__(self, trace_id: str, message: str = None, details: dict = None):
        details = details or {}
        details["trace_id"] = trace_id
        super().__init__(-45005, message or f"Invalid workflow trace: {trace_id}", details)


# === Network Errors ===

class NetworkError(ARCException):
    """Base class for network-related errors"""
    pass


class ConnectionError(NetworkError):
    """Connection error"""
    pass


class TimeoutError(NetworkError):
    """Network timeout"""
    pass


class SSLError(NetworkError):
    """SSL/TLS error"""
    pass


# === Client Errors ===

class ClientError(ARCException):
    """Base class for client-related errors"""
    pass


class ConfigurationError(ClientError):
    """Client configuration error"""
    pass


class ValidationError(ClientError):
    """Validation error"""
    pass


class SerializationError(ClientError):
    """Serialization error"""
    pass


class DeserializationError(ClientError):
    """Deserialization error"""
    pass