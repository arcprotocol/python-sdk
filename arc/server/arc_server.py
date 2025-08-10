"""
ARC Server Implementation

FastAPI-based server for handling ARC protocol requests.
Integrates with ARC request processing and provides authentication,
validation, and error handling.
"""

import logging
import json
import uuid
from typing import Dict, Callable, Optional, Any, List, Union
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .sse import SSEResponse, create_chat_stream

from ..exceptions import (
    ARCException, InvalidRequestError, ParseError, MethodNotFoundError, 
    InvalidParamsError, InternalError, AuthenticationError, AuthorizationError
)
from .middleware import extract_auth_context, cors_middleware, logging_middleware, AuthMiddleware
from ..auth.jwt_validator import JWTValidator, MultiProviderJWTValidator


logger = logging.getLogger(__name__)


class ARCServer:
    """
    Server for handling incoming ARC protocol requests using FastAPI.
    
    Features:
    - ARC protocol request/response handling with built-in agent routing
    - OAuth2 authentication with scope validation
    - Request/response validation
    - Error handling with proper HTTP status codes
    - CORS support for web clients
    - Structured logging with trace IDs
    """
    
    def __init__(
        self, 
        agent_id: str,
        name: str = None,
        version: str = "1.0.0",
        agent_description: str = None,
        enable_cors: bool = True,
        enable_validation: bool = True,
        enable_logging: bool = True,
        enable_auth: bool = False
    ):
        """
        Initialize ARC server.
        
        Args:
            agent_id: ID of the agent (used for routing, logging, and identification)
            name: Human-readable name for the agent
            version: Version of the agent
            agent_description: Optional description of the agent
            enable_cors: Enable CORS middleware for web clients
            enable_validation: Enable request validation middleware
            enable_logging: Enable request logging middleware
            enable_auth: Enable OAuth2 authentication middleware
        """
        self.agent_id = agent_id
        self.name = name or agent_id
        self.version = version
        self.agent_description = agent_description or f"ARC agent: {agent_id}"
        
        self.app = FastAPI(
            title=f"{self.name} ARC Server",
            description=self.agent_description,
            version=self.version
        )
        
        # Method handlers
        self.handlers: Dict[str, Callable] = {}
        self.supported_methods: List[str] = []
        
        # Authentication configuration
        self.jwt_validator = None
        self.required_scopes: Dict[str, List[str]] = {
            # Default required scopes for common methods
            "task.create": ["arc.task.controller", "arc.agent.caller"],
            "task.send": ["arc.task.controller", "arc.agent.caller"],
            "task.info": ["arc.task.controller", "arc.agent.caller"],
            "task.cancel": ["arc.task.controller", "arc.agent.caller"],
            "task.subscribe": ["arc.task.controller", "arc.agent.caller"],
            "task.notification": ["arc.task.notify", "arc.agent.receiver"],
            "chat.start": ["arc.chat.controller", "arc.agent.caller"],
            "chat.message": ["arc.chat.controller", "arc.agent.caller"],
            "chat.end": ["arc.chat.controller", "arc.agent.caller"]
        }
        
        # Add middleware in order
        if enable_cors:
            self._add_cors_middleware()
        if enable_logging:
            self._add_logging_middleware()
            
        # Setup routes
        self._setup_routes()
        
        logger.info(f"ARC Server initialized for agent: {agent_id}")
    
    def _add_cors_middleware(self):
        """Add CORS middleware for web client support"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["*"],
        )
    
    def _add_logging_middleware(self):
        """Add logging middleware"""
        self.app.middleware("http")(logging_middleware)
        
    def _add_auth_middleware(self):
        """Add authentication middleware"""
        if self.jwt_validator:
            # Create token validator function
            async def validate_token(token: str):
                try:
                    claims = await self.jwt_validator.validate_token(token)
                    # Extract scopes from claims
                    scopes = []
                    for scope_claim in ["scope", "scp", "permissions"]:
                        if scope_claim in claims:
                            scope_value = claims[scope_claim]
                            if isinstance(scope_value, str):
                                scopes = scope_value.split()
                            elif isinstance(scope_value, list):
                                scopes = scope_value
                            break
                    
                    # Add scopes to claims
                    claims["scopes"] = scopes
                    return claims
                except Exception as e:
                    logger.error(f"Token validation failed: {e}")
                    raise AuthenticationError(f"Invalid token: {str(e)}")
            
            # Add auth middleware
            self.app.add_middleware(
                AuthMiddleware,
                token_validator=validate_token,
                required_scopes=self.required_scopes
            )
            logger.info("Added OAuth2 authentication middleware")
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.post("/arc")
        async def handle_arc_request(request: Request):
            """Handle ARC protocol requests"""
            try:
                # Parse the request body
                body = await request.json()
                
                # Basic validation
                if not isinstance(body, dict):
                    raise InvalidRequestError("Request body must be a JSON object")
                
                # Check required fields
                required_fields = ["arc", "id", "method", "requestAgent", "targetAgent", "params"]
                for field in required_fields:
                    if field not in body:
                        raise InvalidRequestError(f"Missing required field: {field}")
                        
                # Check ARC version
                if body["arc"] != "1.0":
                    error_resp = {
                        "arc": "1.0",
                        "id": body.get("id"),
                        "responseAgent": self.agent_id,
                        "targetAgent": body.get("requestAgent"),
                        "traceId": body.get("traceId"),
                        "result": None,
                        "error": {
                            "code": -45001,
                            "message": f"Invalid ARC version: {body['arc']}",
                            "details": {"supportedVersion": "1.0"}
                        }
                    }
                    return JSONResponse(content=error_resp, status_code=400)
                    
                # Check if this request is for this agent
                if body["targetAgent"] != self.agent_id:
                    error_resp = {
                        "arc": "1.0",
                        "id": body["id"],
                        "responseAgent": self.agent_id,
                        "targetAgent": body["requestAgent"],
                        "traceId": body.get("traceId"),
                        "result": None,
                        "error": {
                            "code": -41001,
                            "message": f"Agent not found: {body['targetAgent']}",
                            "details": {
                                "requestedAgent": body["targetAgent"],
                                "currentAgent": self.agent_id
                            }
                        }
                    }
                    return JSONResponse(content=error_resp, status_code=404)
                
                # Check method
                method = body["method"]
                if method not in self.handlers:
                    error_resp = {
                        "arc": "1.0",
                        "id": body["id"],
                        "responseAgent": self.agent_id,
                        "targetAgent": body["requestAgent"],
                        "traceId": body.get("traceId"),
                        "result": None,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                            "details": {
                                "supportedMethods": self.supported_methods
                            }
                        }
                    }
                    return JSONResponse(content=error_resp, status_code=404)
                
                # Extract authentication information from request
                auth_context = {}
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    auth_context["token"] = auth_header.split(" ")[1]
                    auth_context["authenticated"] = True
                else:
                    auth_context["authenticated"] = False
                
                # Create context
                context = {
                    "request_id": body["id"],
                    "method": method,
                    "request_agent": body["requestAgent"],
                    "target_agent": body["targetAgent"],
                    "trace_id": body.get("traceId"),
                    "raw_request": body,
                    "http_request": request,
                    "auth": auth_context
                }
                
                # Get handler and params
                handler = self.handlers[method]
                params = body["params"]
                
                # Check if streaming is requested for chat methods
                use_streaming = method.startswith('chat.') and params.get('stream', False)
                
                # Execute handler
                result = await handler(params, context)
                
                # Handle streaming response if requested and supported
                if use_streaming and isinstance(result, dict) and 'type' in result and result['type'] == 'chat':
                    # Extract chat data
                    chat_data = result.get('chat', {})
                    chat_id = chat_data.get('chatId')
                    message = chat_data.get('message', {})
                    
                    if chat_id and hasattr(message, 'stream'):
                        # Use SSE for streaming response
                        return create_chat_stream(chat_id, message.stream())
                    
                # Build standard JSON response
                response = {
                    "arc": "1.0",
                    "id": body["id"],
                    "responseAgent": self.agent_id,
                    "targetAgent": body["requestAgent"],
                    "result": result,
                    "error": None
                }
                
                if "traceId" in body:
                    response["traceId"] = body["traceId"]
                
                # Check if the handler returned a Response object directly
                # (e.g., a streaming response)
                if isinstance(result, StreamingResponse):
                    # Return streaming responses directly without wrapping
                    logger.info(f"Returning streaming response for method {method}")
                    return result
                
                # Normal JSON response
                return JSONResponse(content=response)
                
            except ARCException as e:
                # Handle ARC protocol exceptions
                error_resp = {
                    "arc": "1.0",
                    "id": body["id"] if isinstance(body, dict) and "id" in body else str(uuid.uuid4()),
                    "responseAgent": self.agent_id,
                    "targetAgent": body["requestAgent"] if isinstance(body, dict) and "requestAgent" in body else "unknown",
                    "traceId": body.get("traceId") if isinstance(body, dict) else None,
                    "result": None,
                    "error": {
                        "code": getattr(e, "code", -32603),
                        "message": str(e),
                        "details": getattr(e, "details", None)
                    }
                }
                status_code = 400
                return JSONResponse(content=error_resp, status_code=status_code)
                
            except json.JSONDecodeError as e:
                # Handle JSON parse errors
                error_resp = {
                    "arc": "1.0",
                    "id": "error",
                    "responseAgent": self.agent_id,
                    "targetAgent": "unknown",
                    "result": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}",
                        "details": None
                    }
                }
                return JSONResponse(content=error_resp, status_code=400)
                
            except Exception as e:
                # Handle unexpected errors
                logger.exception(f"Unexpected error handling request: {str(e)}")
                error_id = str(uuid.uuid4())
                error_resp = {
                    "arc": "1.0",
                    "id": body["id"] if isinstance(body, dict) and "id" in body else "error",
                    "responseAgent": self.agent_id,
                    "targetAgent": body["requestAgent"] if isinstance(body, dict) and "requestAgent" in body else "unknown",
                    "traceId": body.get("traceId") if isinstance(body, dict) else None,
                    "result": None,
                    "error": {
                        "code": -32603,
                        "message": "Internal server error",
                        "details": {
                            "errorId": error_id
                        }
                    }
                }
                return JSONResponse(content=error_resp, status_code=500)
                
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "ok", "agent": self.agent_id}
            
        @self.app.get("/agent-info")
        async def agent_info():
            """Agent information endpoint"""
            return {
                "agentId": self.agent_id,
                "description": self.agent_description,
                "status": "active",
                "endpoints": {
                    "arc": "/arc"
                },
                "supportedMethods": self.supported_methods
            }
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register a method handler.
        
        Args:
            method: ARC method name (e.g., "task.create")
            handler: Async function that handles the method
                     Expected signature: async def handler(params: dict, context: dict) -> dict
        """
        self.handlers[method] = handler
        if method not in self.supported_methods:
            self.supported_methods.append(method)
        logger.info(f"Registered handler for method: {method}")
            
    def method_handler(self, method: str):
        """
        Decorator for registering method handlers.
        
        Args:
            method: ARC method name (e.g., "task.create")
            
        Example:
            @server.method_handler("task.create")
            async def handle_task_create(params, context):
                # Implementation
                return {"type": "task", "task": {...}}
        """
        def decorator(func: Callable):
            self.register_handler(method, func)
            return func
        return decorator
    
    def task_handler(self, method: str = None):
        """Decorator for task-related method handlers"""
        method_name = method or "task.create"
        return self.method_handler(method_name)
        
    def chat_handler(self, method: str = None):
        """Decorator for chat-related method handlers"""
        method_name = method or "chat.start"
        return self.method_handler(method_name)
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance"""
        return self.app
        
    def use_jwt_validator(self, validator: Union[JWTValidator, MultiProviderJWTValidator]):
        """
        Configure JWT token validation for authentication.
        
        Args:
            validator: JWT validator to use for token validation
        """
        self.jwt_validator = validator
        self._add_auth_middleware()
        logger.info("Configured JWT validation for authentication")
    
    def set_required_scopes(self, method: str, scopes: List[str]):
        """
        Set required OAuth2 scopes for a method.
        
        Args:
            method: ARC method name
            scopes: List of required OAuth2 scopes
        """
        self.required_scopes[method] = scopes
        logger.info(f"Set required scopes for {method}: {scopes}")
    
    def run(
        self, 
        host: str = "0.0.0.0", 
        port: int = 8000, 
        reload: bool = False,
        **kwargs
    ):
        """
        Run the ARC server using Uvicorn.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            reload: Enable auto-reload for development
            **kwargs: Additional arguments passed to uvicorn.run
        """
        import uvicorn
        
        if not self.handlers:
            logger.warning("No method handlers registered. Server will reject all method calls.")
            
        logger.info(f"Starting ARC server for agent {self.agent_id} on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            **kwargs
        )


def create_server(agent_id: str, **kwargs) -> ARCServer:
    """
    Create an ARC server with the given agent ID.
    
    Args:
        agent_id: ID of the agent
        **kwargs: Additional arguments to pass to ARCServer constructor
        
    Returns:
        Initialized ARCServer instance
    """
    return ARCServer(agent_id, **kwargs)