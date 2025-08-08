"""
ARC Request Processing Module

Provides core functionality for processing ARC protocol requests and responses.
"""

import uuid
import json
import logging
from typing import Dict, Callable, Any, Optional, Union, List

from ..exceptions import (
    ARCException, ParseError, InvalidRequestError, MethodNotFoundError, 
    InvalidParamsError, InternalError, AuthenticationError, AuthorizationError
)
from .validation import validate_arc_request, validate_method_params


logger = logging.getLogger(__name__)


class ARCProcessor:
    """
    Process ARC protocol requests and responses.
    
    Handles:
    - Request parsing and validation
    - Method routing to handlers
    - Response formatting
    - Error handling with proper ARC error codes
    """
    
    # Standard JSON-RPC 2.0 error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # ARC-specific error codes from protocol spec
    # Agent Errors (-41000 to -41099)
    AGENT_NOT_FOUND = -41001
    AGENT_NOT_AVAILABLE = -41002
    AGENT_UNREACHABLE = -41003
    INVALID_AGENT_ID = -41004
    AGENT_AUTHENTICATION_FAILED = -41005
    AGENT_TIMEOUT = -41006
    
    # Task Errors (-42000 to -42099)
    TASK_NOT_FOUND = -42001
    TASK_ALREADY_COMPLETED = -42002
    TASK_ALREADY_CANCELED = -42003
    TASK_EXECUTION_FAILED = -42004
    TASK_TIMEOUT = -42005
    INVALID_TASK_STATUS_TRANSITION = -42006
    
    # Stream Errors (-43000 to -43099)
    STREAM_NOT_FOUND = -43001
    STREAM_ALREADY_CLOSED = -43002
    STREAM_TIMEOUT = -43003
    STREAM_PARTICIPANT_LIMIT = -43004
    INVALID_STREAM_MESSAGE = -43005
    
    # Security Errors (-44000 to -44099)
    AUTHENTICATION_FAILED = -44001
    AUTHORIZATION_FAILED = -44002
    INSUFFICIENT_SCOPE = -44003
    TOKEN_EXPIRED = -44004
    TOKEN_INVALID = -44005
    PERMISSION_DENIED = -44006
    RATE_LIMIT_EXCEEDED = -44007
    
    # Protocol Errors (-45000 to -45099)
    INVALID_ARC_VERSION = -45001
    MISSING_REQUIRED_FIELD = -45002
    INVALID_FIELD_FORMAT = -45003
    MESSAGE_TOO_LARGE = -45004
    WORKFLOW_TRACE_INVALID = -45005
    
    def __init__(self, agent_id: str):
        """
        Initialize ARC processor.
        
        Args:
            agent_id: ID of this agent (used in responses)
        """
        self.agent_id = agent_id
        self.handlers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
    
    def add_middleware(self, middleware: Callable):
        """
        Add middleware for request processing.
        
        Args:
            middleware: Async callable with signature (request, context) -> None
                       Should raise exceptions for validation failures
        """
        self.middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__class__.__name__}")
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register a method handler.
        
        Args:
            method: ARC method name (e.g., "task.create")
            handler: Async function with signature (params, context) -> result
        """
        self.handlers[method] = handler
        logger.info(f"Registered handler for method: {method}")
    
    async def process_request(
        self, 
        request_data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process an ARC protocol request.
        
        Args:
            request_data: Raw request data
            context: Request context with authentication info
            
        Returns:
            ARC response object
            
        Raises:
            ARCException: If request processing fails
        """
        try:
            # Parse and validate request
            validation_result = validate_arc_request(request_data)
            if not validation_result:
                raise InvalidRequestError(validation_result.error_message)
            
            request = validation_result.data
            
            # Get key fields
            request_id = request["id"]
            method = request["method"]
            request_agent = request["requestAgent"]
            target_agent = request["targetAgent"]
            params = request["params"]
            trace_id = request.get("traceId")
            
            # Update context with request data
            context.update({
                "request_id": request_id,
                "method": method,
                "request_agent": request_agent,
                "target_agent": target_agent,
                "trace_id": trace_id
            })
            
            # Check if this request is for this agent
            if target_agent != self.agent_id:
                return self._create_error_response(
                    request_id,
                    self.AGENT_NOT_FOUND,
                    f"Agent not found: {target_agent}",
                    {"requestedAgent": target_agent, "currentAgent": self.agent_id},
                    request_agent,
                    trace_id
                )
            
            # Check if method exists
            if method not in self.handlers:
                return self._create_error_response(
                    request_id,
                    self.METHOD_NOT_FOUND,
                    f"Method not found: {method}",
                    {"supportedMethods": list(self.handlers.keys())},
                    request_agent,
                    trace_id
                )
            
            # Validate method params
            params_result = validate_method_params(method, params)
            if not params_result:
                return self._create_error_response(
                    request_id,
                    self.INVALID_PARAMS,
                    f"Invalid parameters for {method}",
                    {"errors": params_result.errors},
                    request_agent,
                    trace_id
                )
            
            # Run middleware
            try:
                for middleware in self.middleware:
                    await middleware(request, context)
            except ARCException as e:
                # Handle middleware exceptions
                return self._create_error_response(
                    request_id,
                    getattr(e, "code", self.INTERNAL_ERROR),
                    str(e),
                    getattr(e, "details", None),
                    request_agent,
                    trace_id
                )
            
            # Get and call handler
            handler = self.handlers[method]
            result = await handler(params, context)
            
            # Create success response
            return self._create_success_response(
                request_id,
                result,
                request_agent,
                trace_id
            )
            
        except InvalidRequestError as e:
            return self._create_error_response(
                request_data.get("id", "error"),
                self.INVALID_REQUEST,
                str(e),
                getattr(e, "data", None),
                request_data.get("requestAgent", "unknown"),
                request_data.get("traceId")
            )
        except MethodNotFoundError as e:
            return self._create_error_response(
                request_data.get("id", "error"),
                self.METHOD_NOT_FOUND,
                str(e),
                getattr(e, "data", None),
                request_data.get("requestAgent", "unknown"),
                request_data.get("traceId")
            )
        except InvalidParamsError as e:
            return self._create_error_response(
                request_data.get("id", "error"),
                self.INVALID_PARAMS,
                str(e),
                getattr(e, "data", None),
                request_data.get("requestAgent", "unknown"),
                request_data.get("traceId")
            )
        except ParseError as e:
            return self._create_error_response(
                "error",
                self.PARSE_ERROR,
                str(e),
                getattr(e, "data", None),
                "unknown",
                None
            )
        except ARCException as e:
            # Handle known ARC exceptions
            return self._create_error_response(
                request_data.get("id", "error"),
                getattr(e, "code", self.INTERNAL_ERROR),
                str(e),
                getattr(e, "details", None),
                request_data.get("requestAgent", "unknown"),
                request_data.get("traceId")
            )
        except Exception as e:
            # Handle unknown exceptions
            logger.exception(f"Unexpected error processing request: {str(e)}")
            return self._create_error_response(
                request_data.get("id", "error"),
                self.INTERNAL_ERROR,
                "Internal server error",
                {"errorId": str(uuid.uuid4())},
                request_data.get("requestAgent", "unknown"),
                request_data.get("traceId")
            )
    
    def _create_success_response(
        self, 
        request_id: Union[str, int], 
        result: Any,
        target_agent: str,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a success response for an ARC request.
        
        Args:
            request_id: Original request ID
            result: Result data
            target_agent: ID of agent to receive response
            trace_id: Optional workflow tracing ID
            
        Returns:
            ARC response object
        """
        response = {
            "arc": "1.0",
            "id": request_id,
            "responseAgent": self.agent_id,
            "targetAgent": target_agent,
            "result": result,
            "error": None
        }
        
        if trace_id:
            response["traceId"] = trace_id
        
        return response
    
    def _create_error_response(
        self,
        request_id: Union[str, int],
        code: int,
        message: str,
        details: Any = None,
        target_agent: str = "unknown",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an error response for an ARC request.
        
        Args:
            request_id: Original request ID
            code: Error code
            message: Error message
            details: Optional error details
            target_agent: ID of agent to receive response
            trace_id: Optional workflow tracing ID
            
        Returns:
            ARC response object
        """
        response = {
            "arc": "1.0",
            "id": request_id,
            "responseAgent": self.agent_id,
            "targetAgent": target_agent,
            "result": None,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        if details is not None:
            response["error"]["details"] = details
            
        if trace_id:
            response["traceId"] = trace_id
        
        return response
    
    def create_request(
        self,
        method: str,
        target_agent: str,
        params: Any = None,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an ARC request object.
        
        Args:
            method: Method name
            target_agent: ID of target agent
            params: Method parameters (must be serializable)
            trace_id: Optional workflow trace ID
            request_id: Optional request ID (auto-generated if None)
            
        Returns:
            ARC request object
        """
        request = {
            "arc": "1.0",
            "id": request_id or str(uuid.uuid4()),
            "method": method,
            "requestAgent": self.agent_id,
            "targetAgent": target_agent,
            "params": params or {}
        }
        
        if trace_id:
            request["traceId"] = trace_id
        
        return request