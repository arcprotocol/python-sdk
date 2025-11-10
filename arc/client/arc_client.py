"""
ARC Client Implementation

Main client class for making requests to ARC-compatible servers.
"""

import asyncio
import json
import logging
import ssl
import uuid
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic, cast, AsyncIterator

from .stream_utils import stream_response

import httpx

from ..exceptions import (
    ARCException, ParseError, InvalidRequestError, MethodNotFoundError,
    InvalidParamsError, InternalError, ARCAgentError, AgentNotFoundError,
    AgentNotAvailableError, ARCTaskError, TaskNotFoundError, ARCChatError,
    ChatNotFoundError, ARCSecurityError, AuthenticationError, AuthorizationError,
    InsufficientScopeError, TokenExpiredError, ARCProtocolError, NetworkError,
    ConnectionError, TimeoutError
)

try:
    from ..crypto import create_quantum_safe_context, HybridTLSConfig
    QUANTUM_SAFE_AVAILABLE = True
except ImportError:
    QUANTUM_SAFE_AVAILABLE = False

# Type definitions
T = TypeVar('T')
ResponseType = Dict[str, Any]
RequestType = Dict[str, Any]

# Setup logging
logger = logging.getLogger("arc.client")


class ARCClient:
    """
    ARC Protocol client for agent communication.
    
    This client provides methods for interacting with ARC-compatible agents
    using the Agent Remote Communication protocol with quantum-safe hybrid TLS by default.
    
    Args:
        endpoint: The ARC endpoint URL
        token: OAuth2 bearer token for authentication
        request_agent: ID of the agent making requests (default: auto-generated)
        timeout: Default request timeout in seconds (default: 60)
        verify_ssl: Whether to verify SSL certificates (default: True)
        ssl_context: Custom SSL context (overrides all other SSL settings if provided)
        use_quantum_safe: Use quantum-safe hybrid TLS (default: True, falls back to standard TLS if unavailable)
        hybrid_tls_config: Configuration for hybrid TLS (optional)
        
    Example:
        >>> # Quantum-safe hybrid TLS (default)
        >>> client = ARCClient("https://api.company.com/arc", token="...")
        >>> task = await client.task.create(target_agent="doc-analyzer", ...)
        
        >>> # Disable quantum-safe TLS (use standard TLS)
        >>> client = ARCClient(
        ...     "https://api.company.com/arc",
        ...     token="...",
        ...     use_quantum_safe=False
        ... )
    """
    
    def __init__(
        self,
        endpoint: str,
        token: Optional[str] = None,
        request_agent: Optional[str] = None,
        timeout: float = 60.0,
        verify_ssl: bool = True,
        ssl_context: Optional[ssl.SSLContext] = None,
        use_quantum_safe: bool = True,
        hybrid_tls_config: Optional['HybridTLSConfig'] = None,
    ):
        self.endpoint = endpoint.rstrip('/')
        self.token = token
        self.request_agent = request_agent or f"arc-python-client-{uuid.uuid4().hex[:8]}"
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Determine SSL configuration
        ssl_config = self._setup_ssl_context(
            ssl_context, 
            use_quantum_safe, 
            hybrid_tls_config, 
            verify_ssl
        )
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            verify=ssl_config,
            follow_redirects=True
        )
        
        # Initialize method handlers
        self.task = TaskMethods(self)
        self.chat = ChatMethods(self)
    
    def _setup_ssl_context(
        self,
        ssl_context: Optional[ssl.SSLContext],
        use_quantum_safe: bool,
        hybrid_tls_config: Optional['HybridTLSConfig'],
        verify_ssl: bool
    ) -> Union[bool, ssl.SSLContext]:
        """
        Setup SSL context for the client.
        
        Priority:
        1. Custom ssl_context if provided
        2. Quantum-safe hybrid TLS (default)
        3. Standard TLS (if quantum-safe disabled or unavailable)
        """
        # If custom SSL context provided, use it
        if ssl_context is not None:
            return ssl_context
        
        # Try to use post-quantum cryptography (PQC) hybrid TLS (default behavior)
        if use_quantum_safe:
            if not QUANTUM_SAFE_AVAILABLE:
                logger.warning(
                    "Post-quantum cryptography (PQC) not available. "
                    "Install with: pip install arc-sdk[pqc] "
                    "Falling back to standard TLS."
                )
                return verify_ssl
            
            try:
                logger.info("Using post-quantum hybrid TLS (X25519 + Kyber-768)")
                return create_quantum_safe_context(
                    verify_ssl=verify_ssl,
                    ca_cert_path=hybrid_tls_config.ca_cert_path if hybrid_tls_config else None,
                    client_cert_path=hybrid_tls_config.client_cert_path if hybrid_tls_config else None,
                    client_key_path=hybrid_tls_config.client_key_path if hybrid_tls_config else None
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create PQC SSL context: {e}. "
                    "Falling back to standard TLS."
                )
                return verify_ssl
        
        # User explicitly disabled PQC
        logger.info("Using standard TLS (post-quantum cryptography disabled)")
        return verify_ssl
        
    async def close(self):
        """Close the HTTP client and release resources."""
        await self.http_client.aclose()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {
            "Content-Type": "application/arc+json",
            "Accept": "application/arc+json, text/event-stream",
            "User-Agent": "arc-sdk-python"
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        return headers
        
    async def send_request(
        self,
        method: str,
        target_agent: str,
        params: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None,
        stream: bool = False
    ) -> Union[ResponseType, AsyncIterator[Dict[str, Any]]]:
        """
        Send an ARC request and return the response.
        
        Args:
            method: ARC method name (e.g., "task.create")
            target_agent: ID of the agent that should handle the request
            params: Method-specific parameters
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds (overrides default)
            
        Returns:
            ARC response object
            
        Raises:
            ARCException: If the request fails or the response is invalid
        """
        # Prepare request
        request_id = str(uuid.uuid4())
        request_data = {
            "arc": "1.0",
            "id": request_id,
            "method": method,
            "requestAgent": self.request_agent,
            "targetAgent": target_agent,
            "params": params
        }
        
        if trace_id:
            request_data["traceId"] = trace_id
            
        # Send request
        try:
            # Check if streaming is requested for chat methods
            if stream and method.startswith('chat.') and params.get('stream', False):
                # For streaming responses, return an async generator
                headers = self._get_headers()
                headers['Accept'] = 'text/event-stream'
                headers['Content-Type'] = 'text/event-stream'
                return stream_response(
                    client=self.http_client,
                    endpoint=self.endpoint,
                    request_data=request_data,
                    headers=headers,
                    timeout=timeout or self.timeout
                )
            
            # Standard JSON response
            response = await self.http_client.post(
                self.endpoint,
                json=request_data,
                headers=self._get_headers(),
                timeout=timeout or self.timeout
            )
            
            # Handle HTTP errors
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Validate response
            self._validate_response(response_data, request_id)
            
            # Check for error
            if "error" in response_data and response_data["error"]:
                self._handle_error(response_data["error"])
                
            return response_data
            
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.RequestError as e:
            raise ConnectionError(f"Connection error: {str(e)}")
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {str(e)}")
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON response: {str(e)}")
            
    def _validate_response(self, response: Dict[str, Any], request_id: str):
        """
        Validate ARC response format.
        
        Args:
            response: ARC response object
            request_id: Expected request ID
            
        Raises:
            InvalidRequestError: If the response is not a valid ARC response
        """
        # Check required fields
        required_fields = ["arc", "id", "responseAgent", "targetAgent"]
        for field in required_fields:
            if field not in response:
                raise InvalidRequestError(f"Missing required field in response: {field}")
                
        # Check protocol version
        if response["arc"] != "1.0":
            raise ARCProtocolError(f"Unsupported ARC version: {response['arc']}")
            
        # Check ID matches
        if response["id"] != request_id:
            raise InvalidRequestError(f"Response ID does not match request ID")
            
        # Check result or error
        if "result" not in response and "error" not in response:
            raise InvalidRequestError("Response must contain either result or error")
            
    def _handle_error(self, error: Dict[str, Any]):
        """
        Handle ARC error response.
        
        Args:
            error: Error object from ARC response
            
        Raises:
            ARCException: Appropriate exception based on error code
        """
        if not error or not isinstance(error, dict):
            raise ARCException("Unknown error")
            
        code = error.get("code")
        message = error.get("message", "Unknown error")
        details = error.get("details")
        
        # Standard JSON-RPC errors
        if code == -32700:
            raise ParseError(message, details)
        elif code == -32600:
            raise InvalidRequestError(message, details)
        elif code == -32601:
            raise MethodNotFoundError(message, details)
        elif code == -32602:
            raise InvalidParamsError(message, details)
        elif code == -32603:
            raise InternalError(message, details)
            
        # ARC-specific errors
        # Agent errors (-41000 to -41099)
        elif -41099 <= code <= -41000:
            if code == -41001:
                raise AgentNotFoundError(details.get("agentId", "unknown"), message, details)
            elif code == -41002:
                raise AgentNotAvailableError(details.get("agentId", "unknown"), message, details)
            else:
                raise ARCAgentError(code, message, details)
                
        # Task errors (-42000 to -42099)
        elif -42099 <= code <= -42000:
            if code == -42001:
                raise TaskNotFoundError(details.get("taskId", "unknown"), message, details)
            else:
                raise ARCTaskError(code, message, details)
                
        # Chat errors (-43000 to -43099)
        elif -43099 <= code <= -43000:
            if code == -43001:
                raise ChatNotFoundError(details.get("chatId", "unknown"), message, details)
            else:
                raise ARCChatError(code, message, details)
                
        # Security errors (-44000 to -44099)
        elif -44099 <= code <= -44000:
            if code == -44001:
                raise AuthenticationError(message, details)
            elif code == -44002:
                raise AuthorizationError(message, details)
            elif code == -44003:
                raise InsufficientScopeError(
                    details.get("required_scopes", []),
                    details.get("provided_scopes", []),
                    message,
                    details
                )
            elif code == -44004:
                raise TokenExpiredError(message, details)
            else:
                raise ARCSecurityError(code, message, details)
                
        # Protocol errors (-45000 to -45099)
        elif -45099 <= code <= -45000:
            raise ARCProtocolError(code, message, details)
            
        # Unknown error
        else:
            raise ARCException(message, str(code), details)
            
    def _handle_http_error(self, error: httpx.HTTPStatusError):
        """
        Handle HTTP errors.
        
        Args:
            error: HTTP error
            
        Raises:
            ARCException: Appropriate exception based on HTTP status code
        """
        status_code = error.response.status_code
        
        try:
            error_data = error.response.json()
            message = error_data.get("message", str(error))
            details = error_data.get("details")
        except (json.JSONDecodeError, AttributeError):
            message = str(error)
            details = None
            
        if status_code == 400:
            raise InvalidRequestError(message, details)
        elif status_code == 401:
            raise AuthenticationError(message, details)
        elif status_code == 403:
            raise AuthorizationError(message, details)
        elif status_code == 404:
            raise MethodNotFoundError(message, details)
        elif status_code == 429:
            raise ARCSecurityError(-44007, f"Rate limit exceeded: {message}", details)
        else:
            raise ARCException(f"HTTP error {status_code}: {message}", details=details)


class TaskMethods:
    """
    Task-related ARC methods.
    
    Provides methods for asynchronous, long-running operations.
    """
    
    def __init__(self, client: ARCClient):
        self.client = client
        
    async def create(
        self,
        target_agent: str,
        initial_message: Dict[str, Any],
        priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new asynchronous task.
        
        Args:
            target_agent: ID of the agent that should handle the task
            initial_message: Initial message to start the task
            priority: Optional task priority (LOW, NORMAL, HIGH, URGENT)
            metadata: Optional custom task metadata
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Task creation response
            
        Example:
            >>> task = await client.task.create(
            ...     target_agent="doc-analyzer-01",
            ...     initial_message={
            ...         "role": "user",
            ...         "parts": [{"type": "TextPart", "content": "Analyze this report"}]
            ...     },
            ...     priority="HIGH"
            ... )
            >>> task_id = task["result"]["task"]["taskId"]
        """
        params = {
            "initialMessage": initial_message
        }
        
        if priority:
            params["priority"] = priority
            
        if metadata:
            params["metadata"] = metadata
            
        response = await self.client.send_request(
            method="task.create",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
        
    async def send(
        self,
        target_agent: str,
        task_id: str,
        message: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send a message to an existing task.
        
        Args:
            target_agent: ID of the agent that handles the task
            task_id: Task identifier
            message: Message object to send
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Task send response
            
        Example:
            >>> response = await client.task.send(
            ...     target_agent="doc-analyzer-01",
            ...     task_id="task-12345",
            ...     message={
            ...         "role": "user",
            ...         "parts": [{"type": "TextPart", "content": "Add financial section"}]
            ...     }
            ... )
            >>> success = response["result"]["success"]
        """
        params = {
            "taskId": task_id,
            "message": message
        }
        
        response = await self.client.send_request(
            method="task.send",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
        
    async def info(
        self,
        target_agent: str,
        task_id: str,
        include_messages: bool = True,
        include_artifacts: bool = True,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Retrieve task status and history.
        
        Args:
            target_agent: ID of the agent that handles the task
            task_id: Task identifier
            include_messages: Whether to include full conversation history
            include_artifacts: Whether to include all artifacts
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Task data response
            
        Example:
            >>> response = await client.task.info(
            ...     target_agent="doc-analyzer-01",
            ...     task_id="task-12345"
            ... )
            >>> status = response["result"]["task"]["status"]
        """
        params = {
            "taskId": task_id,
            "includeMessages": include_messages,
            "includeArtifacts": include_artifacts
        }
        
        response = await self.client.send_request(
            method="task.info",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
        
    async def cancel(
        self,
        target_agent: str,
        task_id: str,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Cancel an existing task.
        
        Args:
            target_agent: ID of the agent that handles the task
            task_id: Task identifier
            reason: Optional reason for cancellation
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Task cancellation response
            
        Example:
            >>> response = await client.task.cancel(
            ...     target_agent="doc-analyzer-01",
            ...     task_id="task-12345",
            ...     reason="Priority changed"
            ... )
            >>> canceled_status = response["result"]["task"]["status"]  # Should be "CANCELED"
        """
        params = {
            "taskId": task_id
        }
        
        if reason:
            params["reason"] = reason
            
        response = await self.client.send_request(
            method="task.cancel",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
        
    async def subscribe(
        self,
        target_agent: str,
        task_id: str,
        callback_url: str,
        events: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Subscribe to task notifications via webhook.
        
        Args:
            target_agent: ID of the agent that handles the task
            task_id: Task identifier
            callback_url: Webhook URL for notifications
            events: Optional list of events to subscribe to
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Subscription response
            
        Example:
            >>> response = await client.task.subscribe(
            ...     target_agent="doc-analyzer-01",
            ...     task_id="task-12345",
            ...     callback_url="https://myapp.com/webhooks/tasks",
            ...     events=["TASK_COMPLETED", "TASK_FAILED"]
            ... )
            >>> subscription_id = response["result"]["subscription"]["subscriptionId"]
        """
        params = {
            "taskId": task_id,
            "callbackUrl": callback_url
        }
        
        if events:
            params["events"] = events
            
        response = await self.client.send_request(
            method="task.subscribe",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
        
    async def notification(
        self,
        target_agent: str,
        task_id: str,
        event: str,
        timestamp: str,
        data: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send task status notification (server-initiated).
        
        Args:
            target_agent: ID of the agent that should receive the notification
            task_id: Task identifier
            event: Event type
            timestamp: Event timestamp
            data: Event-specific notification data
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Notification response
            
        Example:
            >>> response = await client.task.notification(
            ...     target_agent="user-interface-01",
            ...     task_id="task-12345",
            ...     event="TASK_COMPLETED",
            ...     timestamp="2024-01-15T10:35:00Z",
            ...     data={
            ...         "status": "COMPLETED",
            ...         "message": "Task completed successfully",
            ...         "completedAt": "2024-01-15T10:35:00Z"
            ...     }
            ... )
        """
        params = {
            "taskId": task_id,
            "event": event,
            "timestamp": timestamp,
            "data": data
        }
        
        response = await self.client.send_request(
            method="task.notification",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response


class ChatMethods:
    """
    Chat-related ARC methods.
    
    Provides methods for real-time, interactive agent communication.
    """
    
    def __init__(self, client: ARCClient):
        self.client = client
        
    async def start(
        self,
        target_agent: str,
        initial_message: Dict[str, Any],
        chat_id: Optional[str] = None,
        stream: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """
        Start a real-time conversation with an initial message.
        
        Args:
            target_agent: ID of the agent that should handle the chat
            initial_message: Initial message to start the conversation
            chat_id: Optional client-specified chat identifier
            stream: Whether to use Server-Sent Events (SSE) for streaming response
            metadata: Optional custom chat metadata
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Chat start response
            
        Example:
            >>> response = await client.chat.start(
            ...     target_agent="chat-agent-01",
            ...     initial_message={
            ...         "role": "user",
            ...         "parts": [{"type": "TextPart", "content": "Hello, I need help"}]
            ...     }
            ... )
            >>> chat_id = response["result"]["chat"]["chatId"]
        """
        params = {
            "initialMessage": initial_message
        }
        
        if chat_id:
            params["chatId"] = chat_id
            
        if stream:
            params["stream"] = True
        
        if metadata:
            params["metadata"] = metadata
            
        response = await self.client.send_request(
            method="chat.start",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout,
            stream=stream
        )
        
        return response
        
    async def message(
        self,
        target_agent: str,
        chat_id: str,
        message: Dict[str, Any],
        stream: bool = False,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """
        Send a message to an active chat.
        
        Args:
            target_agent: ID of the agent that handles the chat
            chat_id: Chat identifier
            message: Message to send
            stream: Whether to use Server-Sent Events (SSE) for streaming response
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Chat message response
            
        Example:
            >>> response = await client.chat.message(
            ...     target_agent="chat-agent-01",
            ...     chat_id="chat-67890",
            ...     message={
            ...         "role": "user",
            ...         "parts": [{"type": "TextPart", "content": "What's the weather?"}]
            ...     }
            ... )
            >>> agent_response = response["result"]["chat"]["message"]["parts"][0]["content"]
        """
        params = {
            "chatId": chat_id,
            "message": message
        }
        
        if stream:
            params["stream"] = True
            
        response = await self.client.send_request(
            method="chat.message",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout,
            stream=stream
        )
        
        return response
        
    async def end(
        self,
        target_agent: str,
        chat_id: str,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        End an active chat.
        
        Args:
            target_agent: ID of the agent that handles the chat
            chat_id: Chat identifier
            reason: Optional reason for ending the chat
            trace_id: Optional workflow tracking ID
            timeout: Request timeout in seconds
            
        Returns:
            Chat end response
            
        Example:
            >>> response = await client.chat.end(
            ...     target_agent="chat-agent-01",
            ...     chat_id="chat-67890",
            ...     reason="Conversation completed"
            ... )
            >>> status = response["result"]["chat"]["status"]  # Should be "CLOSED"
        """
        params = {
            "chatId": chat_id
        }
        
        if reason:
            params["reason"] = reason
            
        response = await self.client.send_request(
            method="chat.end",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
        
        return response
