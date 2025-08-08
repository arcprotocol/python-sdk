"""
ARC Testing Utilities

Provides utilities for testing ARC protocol implementations.
Includes mock server, request validation, and helper functions.
"""

import json
import asyncio
import uuid
from typing import Dict, Any, Callable, List, Optional, Union
from datetime import datetime

from ..exceptions import ARCException


class MockARCClient:
    """
    Mock ARC client for testing.
    
    Records requests and returns predefined responses.
    """
    
    def __init__(
        self,
        responses: Optional[Dict[str, Any]] = None,
        default_agent_id: str = "test-agent"
    ):
        """
        Initialize mock client.
        
        Args:
            responses: Dictionary mapping method names to response results
            default_agent_id: Default agent ID for requests
        """
        self.responses = responses or {}
        self.requests: List[Dict[str, Any]] = []
        self.default_agent_id = default_agent_id
        
        # Create task/stream handler objects
        self.task = MockTaskMethods(self)
        self.stream = MockStreamMethods(self)
    
    async def send_request(
        self,
        method: str,
        target_agent: str,
        params: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Record request and return mock response.
        
        Args:
            method: Method name
            target_agent: Target agent ID
            params: Request parameters
            trace_id: Optional trace ID
            timeout: Optional timeout
            
        Returns:
            Mock response
            
        Raises:
            ARCException: If error response is configured
        """
        # Create request object
        request = {
            "arc": "1.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "requestAgent": self.default_agent_id,
            "targetAgent": target_agent,
            "params": params
        }
        
        if trace_id:
            request["traceId"] = trace_id
            
        # Record the request
        self.requests.append(request)
        
        # Get response for this method
        if method in self.responses:
            response_data = self.responses[method]
        else:
            # Default success response
            response_data = {"success": True}
        
        # Check if response is an error
        if isinstance(response_data, Exception):
            raise response_data
        
        # Create response object
        response = {
            "arc": "1.0",
            "id": request["id"],
            "responseAgent": target_agent,
            "targetAgent": self.default_agent_id,
            "result": response_data,
            "error": None
        }
        
        if trace_id:
            response["traceId"] = trace_id
            
        return response
    
    def get_requests(self, method: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recorded requests, optionally filtered by method.
        
        Args:
            method: Optional method name to filter by
            
        Returns:
            List of recorded requests
        """
        if method:
            return [req for req in self.requests if req["method"] == method]
        return self.requests
    
    def reset(self):
        """Clear recorded requests"""
        self.requests = []
    
    def set_response(self, method: str, response: Any):
        """
        Set response for a method.
        
        Args:
            method: Method name
            response: Response data or exception
        """
        self.responses[method] = response


class MockTaskMethods:
    """Mock implementation of task methods"""
    
    def __init__(self, client: MockARCClient):
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
        """Mock task.create method"""
        params = {
            "initialMessage": initial_message
        }
        
        if priority:
            params["priority"] = priority
            
        if metadata:
            params["metadata"] = metadata
            
        return await self.client.send_request(
            method="task.create",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def send(
        self,
        target_agent: str,
        task_id: str,
        message: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock task.send method"""
        params = {
            "taskId": task_id,
            "message": message
        }
        
        return await self.client.send_request(
            method="task.send",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def info(
        self,
        target_agent: str,
        task_id: str,
        include_messages: bool = True,
        include_artifacts: bool = True,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock task.info method"""
        params = {
            "taskId": task_id,
            "includeMessages": include_messages,
            "includeArtifacts": include_artifacts
        }
        
        return await self.client.send_request(
            method="task.info",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def cancel(
        self,
        target_agent: str,
        task_id: str,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock task.cancel method"""
        params = {
            "taskId": task_id
        }
        
        if reason:
            params["reason"] = reason
            
        return await self.client.send_request(
            method="task.cancel",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def subscribe(
        self,
        target_agent: str,
        task_id: str,
        callback_url: str,
        events: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock task.subscribe method"""
        params = {
            "taskId": task_id,
            "callbackUrl": callback_url
        }
        
        if events:
            params["events"] = events
            
        return await self.client.send_request(
            method="task.subscribe",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )


class MockStreamMethods:
    """Mock implementation of stream methods"""
    
    def __init__(self, client: MockARCClient):
        self.client = client
    
    async def start(
        self,
        target_agent: str,
        initial_message: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock stream.start method"""
        params = {
            "initialMessage": initial_message
        }
        
        if metadata:
            params["metadata"] = metadata
            
        return await self.client.send_request(
            method="stream.start",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def message(
        self,
        target_agent: str,
        stream_id: str,
        message: Dict[str, Any],
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock stream.message method"""
        params = {
            "streamId": stream_id,
            "message": message
        }
        
        return await self.client.send_request(
            method="stream.message",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )
    
    async def end(
        self,
        target_agent: str,
        stream_id: str,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock stream.end method"""
        params = {
            "streamId": stream_id
        }
        
        if reason:
            params["reason"] = reason
            
        return await self.client.send_request(
            method="stream.end",
            target_agent=target_agent,
            params=params,
            trace_id=trace_id,
            timeout=timeout
        )


class MockARCServer:
    """
    Mock ARC server for testing.
    
    Records incoming requests and returns predefined responses.
    """
    
    def __init__(self, agent_id: str = "test-server"):
        """
        Initialize mock server.
        
        Args:
            agent_id: Server agent ID
        """
        self.agent_id = agent_id
        self.requests = []
        self.handlers = {}
        self.default_handler = None
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming request.
        
        Args:
            request: ARC request object
            
        Returns:
            ARC response object
        """
        # Record request
        self.requests.append(request)
        
        # Validate request
        if not self._validate_request(request):
            return self._error_response(
                request, 
                -32600, 
                "Invalid request", 
                {"details": "Request does not conform to ARC protocol"}
            )
        
        # Check if request is for this server
        if request["targetAgent"] != self.agent_id:
            return self._error_response(
                request, 
                -41001, 
                f"Agent not found: {request['targetAgent']}", 
                {"requestedAgent": request["targetAgent"], "currentAgent": self.agent_id}
            )
        
        # Get handler for method
        method = request["method"]
        handler = self.handlers.get(method, self.default_handler)
        
        if handler:
            try:
                # Call handler
                context = {
                    "request_id": request["id"],
                    "method": method,
                    "request_agent": request["requestAgent"],
                    "target_agent": request["targetAgent"],
                    "trace_id": request.get("traceId")
                }
                result = await handler(request["params"], context)
                
                # Create success response
                return self._success_response(request, result)
            except Exception as e:
                # Create error response for handler exception
                if isinstance(e, ARCException) and hasattr(e, "code"):
                    return self._error_response(
                        request, e.code, str(e), getattr(e, "details", None)
                    )
                else:
                    return self._error_response(
                        request, -32603, f"Internal error: {str(e)}"
                    )
        else:
            # Method not found
            return self._error_response(
                request, 
                -32601, 
                f"Method not found: {method}", 
                {"supportedMethods": list(self.handlers.keys())}
            )
    
    def _validate_request(self, request: Dict[str, Any]) -> bool:
        """
        Validate ARC request.
        
        Args:
            request: Request object
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ["arc", "id", "method", "requestAgent", "targetAgent", "params"]
        
        # Check required fields
        for field in required_fields:
            if field not in request:
                return False
        
        # Check ARC version
        if request["arc"] != "1.0":
            return False
        
        return True
    
    def _success_response(self, request: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """
        Create success response.
        
        Args:
            request: Request object
            result: Response result
            
        Returns:
            Response object
        """
        response = {
            "arc": "1.0",
            "id": request["id"],
            "responseAgent": self.agent_id,
            "targetAgent": request["requestAgent"],
            "result": result,
            "error": None
        }
        
        if "traceId" in request:
            response["traceId"] = request["traceId"]
            
        return response
    
    def _error_response(
        self, 
        request: Dict[str, Any], 
        code: int, 
        message: str, 
        details: Any = None
    ) -> Dict[str, Any]:
        """
        Create error response.
        
        Args:
            request: Request object
            code: Error code
            message: Error message
            details: Optional error details
            
        Returns:
            Response object
        """
        error = {
            "code": code,
            "message": message
        }
        
        if details is not None:
            error["details"] = details
            
        response = {
            "arc": "1.0",
            "id": request.get("id", "error"),
            "responseAgent": self.agent_id,
            "targetAgent": request.get("requestAgent", "unknown"),
            "result": None,
            "error": error
        }
        
        if "traceId" in request:
            response["traceId"] = request["traceId"]
            
        return response
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register a method handler.
        
        Args:
            method: Method name
            handler: Handler function
        """
        self.handlers[method] = handler
    
    def set_default_handler(self, handler: Callable):
        """
        Set default handler for methods without specific handlers.
        
        Args:
            handler: Handler function
        """
        self.default_handler = handler
    
    def reset(self):
        """Clear recorded requests"""
        self.requests = []
    
    def get_requests(self, method: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recorded requests, optionally filtered by method.
        
        Args:
            method: Optional method name to filter by
            
        Returns:
            List of recorded requests
        """
        if method:
            return [req for req in self.requests if req["method"] == method]
        return self.requests


def create_test_message(content: str, role: str = "user") -> Dict[str, Any]:
    """
    Create a test message object.
    
    Args:
        content: Message content
        role: Message role (user, agent, system)
        
    Returns:
        Message object
    """
    return {
        "role": role,
        "parts": [
            {
                "type": "TextPart",
                "content": content
            }
        ]
    }


def create_test_task_object(
    task_id: Optional[str] = None,
    status: str = "SUBMITTED",
    created_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a test task object.
    
    Args:
        task_id: Optional task ID (auto-generated if None)
        status: Task status
        created_at: Creation timestamp
        
    Returns:
        Task object
    """
    if task_id is None:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        
    if created_at is None:
        created_at = datetime.utcnow().isoformat() + "Z"
        
    return {
        "taskId": task_id,
        "status": status,
        "createdAt": created_at,
        "messages": [],
        "artifacts": []
    }


def create_test_stream_object(
    stream_id: Optional[str] = None,
    status: str = "ACTIVE",
    created_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a test stream object.
    
    Args:
        stream_id: Optional stream ID (auto-generated if None)
        status: Stream status
        created_at: Creation timestamp
        
    Returns:
        Stream object
    """
    if stream_id is None:
        stream_id = f"stream-{uuid.uuid4().hex[:8]}"
        
    if created_at is None:
        created_at = datetime.utcnow().isoformat() + "Z"
        
    return {
        "streamId": stream_id,
        "status": status,
        "createdAt": created_at
    }


def create_test_artifact(
    artifact_id: Optional[str] = None,
    name: str = "Test Artifact",
    mime_type: str = "text/plain",
    content: str = "Test content"
) -> Dict[str, Any]:
    """
    Create a test artifact object.
    
    Args:
        artifact_id: Optional artifact ID (auto-generated if None)
        name: Artifact name
        mime_type: MIME type
        content: Content
        
    Returns:
        Artifact object
    """
    if artifact_id is None:
        artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"
        
    return {
        "artifactId": artifact_id,
        "name": name,
        "mimeType": mime_type,
        "parts": [
            {
                "type": "FilePart",
                "content": content,
                "mimeType": mime_type
            }
        ],
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }