"""
ARC Server Implementation

FastAPI-based server for handling ARC protocol requests.
Integrates with ARC request processing and provides authentication,
validation, and error handling with optional quantum-safe TLS.
"""

import logging
import json
import ssl
import uuid
from typing import Dict, Callable, Optional, Any, List, Union
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .sse import SSEResponse, create_chat_stream
from ..core.chat import ChatManager

from ..exceptions import (
    ARCException, InvalidRequestError, ParseError, MethodNotFoundError, 
    InvalidParamsError, InternalError, AuthenticationError, AuthorizationError
)
from .middleware import extract_auth_context, cors_middleware, logging_middleware, AuthMiddleware
try:
    from ..auth.jwt_validator import JWTValidator, MultiProviderJWTValidator
except ImportError:
    # JWT validators are optional dependencies
    JWTValidator = None
    MultiProviderJWTValidator = None

try:
    from ..crypto import create_quantum_safe_context, HybridTLSConfig, verify_kyber_support
    QUANTUM_SAFE_AVAILABLE = True
except ImportError:
    QUANTUM_SAFE_AVAILABLE = False


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
        server_id: str = "arc-server",
        name: str = None,
        version: str = "1.0.0",
        server_description: str = None,
        enable_cors: bool = True,
        enable_validation: bool = True,
        enable_logging: bool = True,
        enable_auth: bool = False,
        enable_chat_manager: bool = False,
        chat_manager_agent_id: Optional[str] = None
    ):
        """
        Initialize ARC server with multi-agent support.
        
        Args:
            server_id: ID of the server (for identification and logging)
            name: Human-readable name for the server
            version: Version of the server
            server_description: Optional description of the server
            enable_cors: Enable CORS middleware for web clients
            enable_validation: Enable request validation middleware
            enable_logging: Enable request logging middleware
            enable_auth: Enable OAuth2 authentication middleware
            enable_chat_manager: Enable ChatManager for chat lifecycle management
            chat_manager_agent_id: Agent ID for ChatManager (required if enable_chat_manager=True)
        """
        self.server_id = server_id
        self.name = name or server_id
        self.version = version
        self.server_description = server_description or f"ARC multi-agent server: {server_id}"
        
        self.app = FastAPI(
            title=f"{self.name} ARC Server",
            description=self.server_description,
            version=self.version
        )
        
        # Multi-agent registry: {agent_id: {method: handler}}
        self.agents: Dict[str, Dict[str, Callable]] = {}
        self.supported_agents: List[str] = []
        
        # Optional ChatManager for chat lifecycle management
        self.chat_manager = None
        if enable_chat_manager:
            if not chat_manager_agent_id:
                raise ValueError("chat_manager_agent_id is required when enable_chat_manager=True")
            self.chat_manager = ChatManager(chat_manager_agent_id)
            logger.info(f"Enabled ChatManager with agent ID: {chat_manager_agent_id}")
        
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
        
        logger.info(f"ARC Server initialized with server ID: {self.server_id}")
    
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
                        "responseAgent": "arc-server",
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
                    
                # Check if target agent is registered
                target_agent = body["targetAgent"]
                if target_agent not in self.agents:
                    error_resp = {
                        "arc": "1.0",
                        "id": body["id"],
                        "responseAgent": "arc-server",
                        "targetAgent": body["requestAgent"],
                        "traceId": body.get("traceId"),
                        "result": None,
                        "error": {
                            "code": -41001,
                            "message": f"Agent not found: {target_agent}",
                            "details": {
                                "requestedAgent": target_agent,
                                "availableAgents": self.supported_agents
                            }
                        }
                    }
                    return JSONResponse(content=error_resp, status_code=404)
                
                # Check if method exists for this agent
                method = body["method"]
                agent_methods = self.agents[target_agent]
                if method not in agent_methods:
                    error_resp = {
                        "arc": "1.0",
                        "id": body["id"],
                        "responseAgent": target_agent,
                        "targetAgent": body["requestAgent"],
                        "traceId": body.get("traceId"),
                        "result": None,
                        "error": {
                            "code": -32601,
                            "message": f"Method {method} not found for agent {target_agent}",
                            "details": {
                                "supportedMethods": list(agent_methods.keys())
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
                    "target_agent": target_agent,
                    "trace_id": body.get("traceId"),
                    "raw_request": body,
                    "http_request": request,
                    "auth": auth_context,
                    "chat_manager": self.chat_manager  # Provide ChatManager in context
                }
                
                # Get handler and params
                handler = agent_methods[method]
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
                    "responseAgent": target_agent,
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
                    "responseAgent": "arc-server",
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
                    "responseAgent": "arc-server",
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
                    "responseAgent": "arc-server",
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
            return {"status": "ok", "server": self.server_id, "agents": len(self.agents)}
            
        @self.app.get("/agent-info")
        async def agent_info():
            """Multi-agent server information endpoint"""
            agents_info = {}
            for agent_id, methods in self.agents.items():
                agents_info[agent_id] = {
                    "supportedMethods": list(methods.keys()),
                    "status": "active"
                }
            
            return {
                "server": self.server_id,
                "description": self.server_description,
                "status": "active",
                "endpoints": {
                    "arc": "/arc"
                },
                "registeredAgents": agents_info,
                "totalAgents": len(self.agents)
            }
    
    def register_agent_handler(self, agent_id: str, method: str, handler: Callable):
        """
        Register a method handler for a specific agent.
        
        Args:
            agent_id: ID of the agent
            method: ARC method name (e.g., "chat.start")
            handler: Async function that handles the method
                     Expected signature: async def handler(params: dict, context: dict) -> dict
        """
        if agent_id not in self.agents:
            self.agents[agent_id] = {}
            self.supported_agents.append(agent_id)
        
        self.agents[agent_id][method] = handler
        logger.info(f"Registered handler for agent {agent_id}, method {method}")
            
    def agent_handler(self, agent_id: str, method: str):
        """
        Decorator for registering agent method handlers.
        
        Args:
            agent_id: ID of the agent that handles this method
            method: ARC method name (e.g., "chat.start")
            
        Example:
            @server.agent_handler("finance-agent", "chat.start")
            async def handle_finance_chat_start(params, context):
                return {"type": "chat", "chat": {...}}
        """
        def decorator(func: Callable):
            self.register_agent_handler(agent_id, method, func)
            return func
        return decorator
    
    def register_agent(self, agent_id: str):
        """
        Register an agent (without methods).
        
        Args:
            agent_id: ID of the agent to register
        """
        if agent_id not in self.agents:
            self.agents[agent_id] = {}
            self.supported_agents.append(agent_id)
            logger.info(f"Registered agent: {agent_id}")
    
    # Backward compatibility methods
    def register_handler(self, method: str, handler: Callable):
        """
        DEPRECATED: Register a method handler (backward compatibility).
        Use agent_handler() for multi-agent support.
        """
        logger.warning("register_handler() is deprecated. Use agent_handler() for multi-agent support.")
        # For backward compatibility, register under a default agent
        default_agent = "default-agent"
        self.register_agent_handler(default_agent, method, handler)
            
    def method_handler(self, method: str):
        """
        DEPRECATED: Decorator for registering method handlers (backward compatibility).
        Use agent_handler() for multi-agent support.
        """
        logger.warning("method_handler() is deprecated. Use agent_handler() for multi-agent support.")
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
        
    def use_jwt_validator(self, validator):
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
        ssl_context: Optional[ssl.SSLContext] = None,
        use_quantum_safe: bool = True,
        hybrid_tls_config: Optional['HybridTLSConfig'] = None,
        ssl_keyfile: Optional[str] = None,
        ssl_certfile: Optional[str] = None,
        ssl_ca_certs: Optional[str] = None,
        **kwargs
    ):
        """
        Run the ARC server using Uvicorn with quantum-safe hybrid TLS by default.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            reload: Enable auto-reload for development
            ssl_context: Custom SSL context for TLS (overrides all other SSL settings)
            use_quantum_safe: Use quantum-safe hybrid TLS (default: True, falls back to standard TLS if unavailable)
            hybrid_tls_config: Configuration for hybrid TLS (optional)
            ssl_keyfile: Path to SSL private key file
            ssl_certfile: Path to SSL certificate file
            ssl_ca_certs: Path to CA certificates file (for mutual TLS)
            **kwargs: Additional arguments passed to uvicorn.run
            
        Example:
            >>> # Quantum-safe hybrid TLS (default)
            >>> server.run(
            ...     host="0.0.0.0",
            ...     port=443,
            ...     ssl_keyfile="/path/to/key.pem",
            ...     ssl_certfile="/path/to/cert.pem"
            ... )
            
            >>> # Disable quantum-safe TLS (use standard TLS)
            >>> server.run(
            ...     host="0.0.0.0",
            ...     port=443,
            ...     use_quantum_safe=False,
            ...     ssl_keyfile="/path/to/key.pem",
            ...     ssl_certfile="/path/to/cert.pem"
            ... )
        """
        import uvicorn
        
        if not self.agents:
            logger.warning("No agents registered. Server will reject all method calls.")
            
        # Setup SSL configuration
        ssl_config = self._setup_ssl_for_server(
            ssl_context,
            use_quantum_safe,
            hybrid_tls_config,
            ssl_keyfile,
            ssl_certfile,
            ssl_ca_certs
        )
        
        # Log server startup
        protocol = "https" if ssl_config else "http"
        logger.info(f"Starting ARC server {self.server_id} on {protocol}://{host}:{port}")
        
        if use_quantum_safe and QUANTUM_SAFE_AVAILABLE:
            logger.info("Using post-quantum hybrid TLS (X25519 + Kyber-768)")
        elif use_quantum_safe and not QUANTUM_SAFE_AVAILABLE:
            logger.warning(
                "Post-quantum cryptography (PQC) not available. "
                "Install with: pip install arc-sdk[pqc] "
                "Using standard TLS."
            )
        
        # Prepare uvicorn arguments
        uvicorn_args = {
            "host": host,
            "port": port,
            "reload": reload,
        }
        
        # Add SSL configuration if available
        if ssl_config:
            if isinstance(ssl_config, ssl.SSLContext):
                uvicorn_args["ssl_context"] = ssl_config
            else:
                # Standard SSL with key/cert files
                if ssl_keyfile:
                    uvicorn_args["ssl_keyfile"] = ssl_keyfile
                if ssl_certfile:
                    uvicorn_args["ssl_certfile"] = ssl_certfile
                if ssl_ca_certs:
                    uvicorn_args["ssl_ca_certs"] = ssl_ca_certs
        
        # Merge with additional kwargs
        uvicorn_args.update(kwargs)
        
        uvicorn.run(self.app, **uvicorn_args)
    
    def _setup_ssl_for_server(
        self,
        ssl_context: Optional[ssl.SSLContext],
        use_quantum_safe: bool,
        hybrid_tls_config: Optional['HybridTLSConfig'],
        ssl_keyfile: Optional[str],
        ssl_certfile: Optional[str],
        ssl_ca_certs: Optional[str]
    ) -> Optional[Union[ssl.SSLContext, Dict[str, str]]]:
        """
        Setup SSL configuration for the server.
        
        Priority:
        1. Custom ssl_context if provided
        2. Quantum-safe hybrid TLS (default if SSL files provided)
        3. Standard SSL with keyfile/certfile
        4. None (no SSL)
        """
        # If custom SSL context provided, use it
        if ssl_context is not None:
            return ssl_context
        
        # Try to use post-quantum cryptography (PQC) hybrid TLS (default if SSL files provided)
        if use_quantum_safe and ssl_keyfile and ssl_certfile:
            if not QUANTUM_SAFE_AVAILABLE:
                logger.warning(
                    "Post-quantum cryptography (PQC) not available. "
                    "Install with: pip install arc-sdk[pqc] "
                    "Using standard TLS."
                )
                # Fall through to standard SSL
            else:
                try:
                    # Create PQC context for server
                    from ..crypto import create_hybrid_ssl_context
                    
                    if hybrid_tls_config is None:
                        hybrid_tls_config = HybridTLSConfig()
                    
                    context = create_hybrid_ssl_context(
                        config=hybrid_tls_config,
                        purpose=ssl.Purpose.CLIENT_AUTH  # Server purpose
                    )
                    
                    # Load server certificate and key
                    context.load_cert_chain(
                        certfile=ssl_certfile,
                        keyfile=ssl_keyfile
                    )
                    
                    # Load CA certificates for client verification (mutual TLS)
                    if ssl_ca_certs:
                        context.load_verify_locations(cafile=ssl_ca_certs)
                        context.verify_mode = ssl.CERT_REQUIRED
                    
                    logger.info("Server configured with post-quantum hybrid TLS")
                    return context
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to create PQC SSL context: {e}. "
                        "Falling back to standard TLS."
                    )
                    # Fall through to standard SSL
        
        # Standard SSL with keyfile/certfile
        if ssl_keyfile and ssl_certfile:
            logger.info("Server configured with standard TLS")
            return {
                "ssl_keyfile": ssl_keyfile,
                "ssl_certfile": ssl_certfile,
                "ssl_ca_certs": ssl_ca_certs
            }
        
        # No SSL (HTTP only)
        return None


def create_server(server_id: str = "arc-server", **kwargs) -> ARCServer:
    """
    Create an ARC multi-agent server.
    
    Args:
        server_id: ID of the server (for identification and logging)
        **kwargs: Additional arguments to pass to ARCServer constructor
        
    Returns:
        Initialized ARCServer instance with multi-agent support
    """
    return ARCServer(server_id=server_id, **kwargs)