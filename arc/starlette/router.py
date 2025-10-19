"""
Starlette Router for ARC Protocol.

This module implements the router pattern for integrating ARC protocol
with Starlette applications, providing a lightweight alternative to FastAPI.
"""

import json
import uuid
import asyncio
from typing import Optional, Dict, Any, Callable, List, Union
import logging

try:
    from starlette.routing import Router, Route
    from starlette.requests import Request
    from starlette.responses import Response, JSONResponse, StreamingResponse
except ImportError:
    raise ImportError(
        "Starlette is required for arc.starlette module. "
        "Install with: pip install arc-sdk[starlette]"
    )

from ..core.chat import ChatManager
from ..server.sse import SSEResponse
from ..utils.logging import create_logger
from ..exceptions import (
    ARCException, InvalidRequestError, ParseError, MethodNotFoundError,
    InvalidParamsError, InternalError
)

logger = create_logger("arc.starlette.router")


class ARCRouter(Router):
    """
    Starlette Router for ARC Protocol.
    
    Single endpoint multi-agent router that handles ARC protocol requests
    and routes them internally based on targetAgent field.
    
    Example:
        ```python
        from starlette.applications import Starlette
        from arc.starlette import ARCRouter
        
        app = Starlette()
        arc_router = ARCRouter()
        
        # Register agents and their handlers
        @arc_router.agent_handler("finance-agent", "chat.start")
        async def handle_finance_chat(params, context):
            return {"type": "chat", "chat": {...}}
            
        app.mount("/arc", arc_router)
        ```
    """
    
    def __init__(
        self, 
        enable_chat_manager: bool = False, 
        chat_manager_agent_id: Optional[str] = None,
        **router_kwargs
    ):
        """
        Initialize ARC Starlette Router.
        
        Args:
            enable_chat_manager: Enable ChatManager for chat lifecycle management
            chat_manager_agent_id: Agent ID for ChatManager (required if enable_chat_manager=True)
            **router_kwargs: Additional arguments passed to Router
        """
        # Agent registry: {agent_id: {method: handler}}
        self.agents: Dict[str, Dict[str, Callable]] = {}
        self.supported_agents: List[str] = []
        
        # Optional ChatManager for chat lifecycle management
        self.chat_manager = None
        if enable_chat_manager:
            if not chat_manager_agent_id:
                raise ValueError("chat_manager_agent_id is required when enable_chat_manager=True")
            self.chat_manager = ChatManager(chat_manager_agent_id)
            logger.info(f"Enabled ChatManager with agent ID: {chat_manager_agent_id}")
        
        # Set up routes
        routes = [
            Route("/", self.arc_endpoint, methods=["POST"]),
            Route("/info", self.agent_info, methods=["GET"]),
        ]
        
        super().__init__(routes, **router_kwargs)
        
        logger.info("Initialized ARC Starlette Router for multi-agent routing")
    
    async def arc_endpoint(self, request: Request) -> Union[Response, StreamingResponse]:
        """
        Main ARC protocol endpoint.
        
        Handles all ARC protocol requests and routes them to appropriate
        method handlers based on the request method field.
        """
        try:
            # Parse request body
            body = await request.body()
            
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError as e:
                return self._create_error_response(
                    "error", -32700, f"Parse error: {str(e)}", "unknown"
                )
            
            # Basic validation
            if not isinstance(request_data, dict):
                return self._create_error_response(
                    "error", -32600, "Request body must be a JSON object", "unknown"
                )
            
            # Check required fields
            required_fields = ["arc", "id", "method", "requestAgent", "targetAgent", "params"]
            for field in required_fields:
                if field not in request_data:
                    return self._create_error_response(
                        request_data.get("id", "error"), 
                        -32600, 
                        f"Missing required field: {field}",
                        request_data.get("requestAgent", "unknown")
                    )
            
            # Check ARC version
            if request_data["arc"] != "1.0":
                return self._create_error_response(
                    request_data["id"],
                    -45001,
                    f"Invalid ARC version: {request_data['arc']}",
                    request_data["requestAgent"],
                    {"supportedVersion": "1.0"}
                )
            
            # Check if target agent is registered
            target_agent = request_data["targetAgent"]
            if target_agent not in self.agents:
                return self._create_error_response(
                    request_data["id"],
                    -41001,
                    f"Agent not found: {target_agent}",
                    request_data["requestAgent"],
                    {
                        "requestedAgent": target_agent,
                        "availableAgents": self.supported_agents
                    }
                )
            
            # Check if method exists for this agent
            method = request_data["method"]
            agent_methods = self.agents[target_agent]
            if method not in agent_methods:
                return self._create_error_response(
                    request_data["id"],
                    -32601,
                    f"Method {method} not found for agent {target_agent}",
                    request_data["requestAgent"],
                    {"supportedMethods": list(agent_methods.keys())}
                )
            
            # Create context
            context = {
                "request_id": request_data["id"],
                "method": method,
                "request_agent": request_data["requestAgent"],
                "target_agent": target_agent,
                "trace_id": request_data.get("traceId"),
                "raw_request": request_data,
                "http_request": request,
                "chat_manager": self.chat_manager  # Provide ChatManager in context
            }
            
            # Get handler and params
            handler = agent_methods[method]
            params = request_data["params"]
            
            # Execute handler
            result = await handler(params, context)
            
            # Handle streaming response if returned
            if isinstance(result, (StreamingResponse, SSEResponse)):
                return result
            
            # Build standard JSON response
            response = {
                "arc": "1.0",
                "id": request_data["id"],
                "responseAgent": target_agent,
                "targetAgent": request_data["requestAgent"],
                "result": result,
                "error": None
            }
            
            if "traceId" in request_data:
                response["traceId"] = request_data["traceId"]
            
            return JSONResponse(content=response, media_type="application/arc+json")
            
        except ARCException as e:
            # Handle ARC protocol exceptions
            return self._create_error_response(
                request_data.get("id", "error") if isinstance(request_data, dict) else "error",
                getattr(e, "code", -32603),
                str(e),
                request_data.get("requestAgent", "unknown") if isinstance(request_data, dict) else "unknown",
                getattr(e, "details", None)
            )
            
        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"Unexpected error handling request: {str(e)}")
            error_id = str(uuid.uuid4())
            return self._create_error_response(
                request_data.get("id", "error") if isinstance(request_data, dict) else "error",
                -32603,
                "Internal server error",
                request_data.get("requestAgent", "unknown") if isinstance(request_data, dict) else "unknown",
                {"errorId": error_id}
            )
    
    async def agent_info(self, request: Request) -> JSONResponse:
        """
        ARC router information endpoint.
        
        Returns information about registered agents and their capabilities.
        This is separate from the ARC protocol and used for discovery.
        """
        agents_info = {}
        for agent_id, methods in self.agents.items():
            agents_info[agent_id] = {
                "supportedMethods": list(methods.keys()),
                "status": "active"
            }
        
        return JSONResponse({
            "router": "ARC Multi-Agent Router",
            "status": "active",
            "endpoints": {
                "arc": "/"
            },
            "registeredAgents": agents_info,
            "totalAgents": len(self.agents)
        })
    
    def agent_handler(self, agent_id: str, method: str):
        """
        Decorator for registering agent method handlers.
        
        Args:
            agent_id: ID of the agent that handles this method
            method: ARC method name (e.g., "chat.start")
            
        Example:
            @router.agent_handler("finance-agent", "chat.start")
            async def handle_finance_chat_start(params, context):
                return {"type": "chat", "chat": {...}}
        """
        def decorator(func: Callable):
            self.register_agent_handler(agent_id, method, func)
            return func
        return decorator
    
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
    
    def _create_error_response(
        self,
        request_id: str,
        code: int,
        message: str,
        target_agent: str,
        details: Any = None
    ) -> JSONResponse:
        """Create an ARC error response."""
        error_resp = {
            "arc": "1.0",
            "id": request_id,
            "responseAgent": "arc-router",
            "targetAgent": target_agent,
            "result": None,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        if details is not None:
            error_resp["error"]["details"] = details
        
        # Determine HTTP status code based on ARC error code
        if code == -32700:  # Parse error
            status_code = 400
        elif code == -32600:  # Invalid request
            status_code = 400
        elif code == -32601:  # Method not found
            status_code = 404
        elif code == -32602:  # Invalid params
            status_code = 400
        elif code == -41001:  # Agent not found
            status_code = 404
        elif code == -44001:  # Authentication failed
            status_code = 401
        elif code == -44002:  # Authorization failed
            status_code = 403
        else:
            status_code = 500
        
        return JSONResponse(
            content=error_resp,
            status_code=status_code,
            media_type="application/arc+json"
        )
