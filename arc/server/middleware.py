"""
ARC Server Middleware

Middleware components for ARC server:
- Authentication middleware for OAuth2 token validation
- CORS middleware for web clients
- Logging middleware for request/response logging
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from ..exceptions import (
    AuthenticationError, AuthorizationError, InsufficientScopeError, 
    TokenExpiredError, TokenInvalidError
)


logger = logging.getLogger(__name__)
security = HTTPBearer()


async def extract_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Extract authentication context from request.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        Authentication context with token information
        
    Raises:
        AuthenticationError: If authentication fails
    """
    if not credentials:
        raise AuthenticationError("Authentication required")
        
    token = credentials.credentials
    
    # Token validation should be implemented here
    # This is a simplified example - in production, validate JWT tokens
    # and extract claims like scopes, user ID, etc.
    
    # For now, just return the token
    return {
        "token": token,
        "scopes": [],  # Should be extracted from token
        "authenticated": True
    }


async def cors_middleware(request: Request, call_next: Callable) -> Response:
    """
    CORS middleware for handling preflight requests and adding CORS headers.
    
    Args:
        request: FastAPI request
        call_next: Next middleware in chain
        
    Returns:
        Response with CORS headers
    """
    # Handle OPTIONS preflight requests
    if request.method == "OPTIONS":
        response = Response(
            content="",
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Max-Age": "86400",  # 24 hours
            }
        )
        return response
        
    # Process request
    response = await call_next(request)
    
    # Add CORS headers to response
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    
    return response


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Logging middleware for tracking request/response information.
    
    Args:
        request: FastAPI request
        call_next: Next middleware in chain
        
    Returns:
        Processed response
    """
    start_time = time.time()
    
    # Extract trace ID for correlation logging
    trace_id = None
    request_id = None
    
    try:
        # Try to read request body if it's ARC
        if request.url.path == "/arc" and request.method == "POST":
            # Save original body for later
            body_bytes = await request.body()
            
            # Parse request to get IDs for logging
            try:
                body = json.loads(body_bytes.decode())
                trace_id = body.get("traceId")
                request_id = body.get("id")
            except json.JSONDecodeError:
                pass
            
            # Restore body
            async def get_body():
                return body_bytes
            request._body = body_bytes
    except Exception:
        # If we can't read the body, just continue
        pass
        
    # Log the request
    logger.info(
        f"Request: {request.method} {request.url.path} - "
        f"TraceID: {trace_id or 'none'}, RequestID: {request_id or 'none'}"
    )
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = round((time.time() - start_time) * 1000)
    
    # Log the response
    logger.info(
        f"Response: {response.status_code} - {duration_ms}ms - "
        f"TraceID: {trace_id or 'none'}, RequestID: {request_id or 'none'}"
    )
    
    return response


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware that validates OAuth2 tokens and 
    enforces scope requirements for different ARC methods.
    """
    
    def __init__(
        self, 
        app,
        token_validator: Optional[Callable] = None,
        required_scopes: Dict[str, list] = None
    ):
        """
        Initialize auth middleware.
        
        Args:
            app: FastAPI app
            token_validator: Function to validate tokens and extract claims
            required_scopes: Mapping of ARC methods to required OAuth2 scopes
        """
        super().__init__(app)
        self.token_validator = token_validator
        self.required_scopes = required_scopes or {}
        
    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request through the middleware"""
        # Only process ARC requests
        if request.url.path != "/arc" or request.method != "POST":
            return await call_next(request)
            
        # Read request body
        body_bytes = await request.body()
        
        try:
            # Parse request to get method for scope validation
            body = json.loads(body_bytes.decode())
            method = body.get("method")
            
            # Validate token if we have a validator
            if self.token_validator and method:
                # Get authorization header
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    raise AuthenticationError("Bearer token required")
                    
                token = auth_header.split(" ")[1]
                claims = await self.token_validator(token)
                
                # Validate scopes if required for this method
                if method in self.required_scopes:
                    required = self.required_scopes[method]
                    provided = claims.get("scopes", [])
                    
                    if not set(required).issubset(set(provided)):
                        raise InsufficientScopeError(
                            required_scopes=required,
                            provided_scopes=provided,
                            message=f"Insufficient scope for {method}"
                        )
            
            # Restore body
            async def get_body():
                return body_bytes
            request._body = body_bytes
            
        except json.JSONDecodeError:
            # If we can't parse the body, let the main handler deal with it
            # Restore body
            async def get_body():
                return body_bytes
            request._body = body_bytes
        except AuthenticationError as e:
            # Return auth error response
            error_resp = {
                "arc": "1.0",
                "id": body.get("id", "error"),
                "responseAgent": "auth-middleware",  # The server will replace this
                "targetAgent": body.get("requestAgent", "unknown"),
                "result": None,
                "error": {
                    "code": -44001,
                    "message": str(e),
                    "details": getattr(e, "details", None)
                }
            }
            return Response(
                content=json.dumps(error_resp),
                media_type="application/json",
                status_code=401
            )
        except InsufficientScopeError as e:
            # Return scope error response
            error_resp = {
                "arc": "1.0",
                "id": body.get("id", "error"),
                "responseAgent": "auth-middleware",  # The server will replace this
                "targetAgent": body.get("requestAgent", "unknown"),
                "result": None,
                "error": {
                    "code": -44003,
                    "message": str(e),
                    "details": {
                        "required_scopes": e.required_scopes,
                        "provided_scopes": e.provided_scopes
                    }
                }
            }
            return Response(
                content=json.dumps(error_resp),
                media_type="application/json",
                status_code=403
            )
            
        # Continue with the request
        return await call_next(request)