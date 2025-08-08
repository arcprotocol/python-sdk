"""
OAuth2 Client Implementation for ARC Protocol

Implements OAuth2 client credentials flow for machine-to-machine authentication.
Supports standard OAuth2 providers like Auth0, Google, Azure AD, etc.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Set
import httpx
import logging
from datetime import datetime, timedelta

from ..exceptions import (
    AuthenticationError, TokenExpiredError, TokenInvalidError, NetworkError
)


logger = logging.getLogger(__name__)


class OAuth2Token:
    """OAuth2 access token with metadata"""
    
    def __init__(
        self, 
        access_token: str, 
        token_type: str = "Bearer", 
        expires_in: int = 3600, 
        scope: str = "", 
        **kwargs
    ):
        """
        Initialize token.
        
        Args:
            access_token: OAuth2 access token
            token_type: Token type (usually "Bearer")
            expires_in: Token lifetime in seconds
            scope: Space-separated list of granted scopes
            **kwargs: Additional token properties
        """
        self.access_token = access_token
        self.token_type = token_type
        self.expires_in = expires_in
        self.scope = scope
        self.issued_at = datetime.utcnow()
        self.expires_at = self.issued_at + timedelta(seconds=expires_in)
        self.extra = kwargs
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 30 second buffer)"""
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=30))
    
    @property
    def authorization_header(self) -> str:
        """Get Authorization header value"""
        return f"{self.token_type} {self.access_token}"
    
    @property
    def scopes(self) -> Set[str]:
        """Get token scopes as a set"""
        return set(self.scope.split() if self.scope else [])


class OAuth2ClientCredentials:
    """
    OAuth2 Client Credentials Flow Implementation
    
    Handles getting and refreshing OAuth2 tokens using client credentials grant.
    """
    
    def __init__(
        self, 
        token_url: str,
        client_id: str, 
        client_secret: str,
        scope: Optional[str] = None,
        audience: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize OAuth2 client credentials flow.
        
        Args:
            token_url: OAuth2 token endpoint URL
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            scope: Space-separated list of scopes to request (e.g., "arc.task.controller arc.agent.caller")
            audience: OAuth2 audience (for some providers like Auth0)
            timeout: Request timeout in seconds
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.audience = audience
        self.timeout = timeout
        self._current_token: Optional[OAuth2Token] = None
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self._lock = asyncio.Lock()  # Lock for thread safety during token refresh
    
    async def get_token(self, force_refresh: bool = False) -> OAuth2Token:
        """
        Get a valid OAuth2 access token.
        
        Args:
            force_refresh: Force getting a new token even if current one is valid
            
        Returns:
            Valid OAuth2 token
            
        Raises:
            AuthenticationError: If token request fails
            NetworkError: If there's a network error
        """
        # Use lock to prevent multiple concurrent token requests
        async with self._lock:
            # Return current token if still valid
            if not force_refresh and self._current_token and not self._current_token.is_expired:
                return self._current_token
            
            logger.debug(f"Requesting new OAuth2 token from {self.token_url}")
            
            # Prepare token request
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            # Add optional parameters
            if self.scope:
                token_data["scope"] = self.scope
            
            if self.audience:
                token_data["audience"] = self.audience
            
            try:
                # Make token request
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "arc-sdk-python/1.0.0"
                }
                
                response = await self._http_client.post(
                    self.token_url,
                    data=token_data,
                    headers=headers
                )
                
                # Check for errors
                response.raise_for_status()
                
                # Parse token response
                token_json = response.json()
                
                if "access_token" not in token_json:
                    raise AuthenticationError(
                        "Invalid token response: missing access_token",
                        details={"token_url": self.token_url}
                    )
                
                # Create token object
                self._current_token = OAuth2Token(**token_json)
                
                logger.debug(
                    f"Token obtained successfully. Expires in {self._current_token.expires_in} seconds. "
                    f"Scopes: {self._current_token.scope}"
                )
                
                return self._current_token
                
            except httpx.HTTPStatusError as e:
                # Handle HTTP errors
                error_info = {}
                try:
                    error_info = e.response.json()
                except Exception:
                    error_info = {"status": e.response.status_code, "text": e.response.text}
                
                raise AuthenticationError(
                    f"OAuth2 token request failed: {str(e)}",
                    details={"error": error_info, "token_url": self.token_url}
                )
                
            except httpx.RequestError as e:
                # Handle connection errors
                raise NetworkError(f"OAuth2 token request failed: {str(e)}")
    
    async def get_authorization_header(self, force_refresh: bool = False) -> str:
        """
        Get Authorization header value.
        
        Args:
            force_refresh: Force getting a new token
            
        Returns:
            Authorization header value
        """
        token = await self.get_token(force_refresh)
        return token.authorization_header
    
    async def close(self):
        """Close HTTP client"""
        await self._http_client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class OAuth2Config:
    """Configuration for OAuth2 client credentials flow"""
    
    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        audience: Optional[str] = None
    ):
        """
        Initialize OAuth2 configuration.
        
        Args:
            token_url: OAuth2 token endpoint URL
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            scope: Space-separated list of scopes to request
            audience: OAuth2 audience (for some providers like Auth0)
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.audience = audience
    
    def create_client(self, timeout: float = 30.0) -> OAuth2ClientCredentials:
        """
        Create OAuth2 client from config.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Configured OAuth2 client
        """
        return OAuth2ClientCredentials(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
            audience=self.audience,
            timeout=timeout
        )


def create_oauth2_client(
    provider: str,
    client_id: str,
    client_secret: str,
    scope: Optional[str] = None,
    **provider_config
) -> OAuth2ClientCredentials:
    """
    Create OAuth2 client for common providers.
    
    Args:
        provider: OAuth2 provider name (auth0, azure, google, okta, etc.)
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        scope: Space-separated list of scopes to request
        **provider_config: Provider-specific configuration
        
    Returns:
        Configured OAuth2ClientCredentials instance
        
    Supported providers:
        - auth0: needs tenant_domain
        - azure: needs tenant_id
        - google
        - okta: needs okta_domain
        - keycloak: needs realm_name and server_url
        - custom: needs token_url
    """
    # Provider-specific configurations
    provider = provider.lower()
    
    if provider == "auth0":
        tenant_domain = provider_config.get("tenant_domain")
        if not tenant_domain:
            raise ValueError("auth0 provider requires tenant_domain")
        
        token_url = f"https://{tenant_domain}/oauth/token"
        audience = provider_config.get("audience")
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            audience=audience
        )
        
    elif provider == "azure":
        tenant_id = provider_config.get("tenant_id", "common")
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope
        )
        
    elif provider == "google":
        token_url = "https://oauth2.googleapis.com/token"
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope
        )
        
    elif provider == "okta":
        okta_domain = provider_config.get("okta_domain")
        if not okta_domain:
            raise ValueError("okta provider requires okta_domain")
        
        token_url = f"https://{okta_domain}/oauth2/v1/token"
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope
        )
        
    elif provider == "keycloak":
        realm_name = provider_config.get("realm_name")
        server_url = provider_config.get("server_url")
        
        if not realm_name or not server_url:
            raise ValueError("keycloak provider requires realm_name and server_url")
        
        token_url = f"{server_url}/realms/{realm_name}/protocol/openid-connect/token"
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope
        )
        
    elif provider == "custom":
        token_url = provider_config.get("token_url")
        if not token_url:
            raise ValueError("custom provider requires token_url")
        
        audience = provider_config.get("audience")
        
        return OAuth2ClientCredentials(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            audience=audience
        )
        
    else:
        raise ValueError(f"Unsupported OAuth2 provider: {provider}")


class OAuth2Handler:
    """
    OAuth2 handler for ARC client.
    
    Manages OAuth2 authentication for ARC clients, supporting both
    direct token usage and client credentials flow for token acquisition.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        oauth_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize OAuth2 handler.
        
        Args:
            token: Static OAuth2 token
            oauth_config: OAuth2 client credentials configuration
        """
        self.token = token
        self.oauth_client = None
        
        # Initialize OAuth2 client if config provided
        if oauth_config:
            provider = oauth_config.pop("provider", "custom")
            client_id = oauth_config.pop("client_id", None)
            client_secret = oauth_config.pop("client_secret", None)
            scope = oauth_config.pop("scope", None)
            
            if not client_id or not client_secret:
                raise ValueError("OAuth2 config must include client_id and client_secret")
            
            self.oauth_client = create_oauth2_client(
                provider=provider,
                client_id=client_id,
                client_secret=client_secret,
                scope=scope,
                **oauth_config
            )
    
    async def get_token(self) -> str:
        """
        Get current access token.
        
        Returns:
            Access token string
            
        Raises:
            AuthenticationError: If no token is available
        """
        if self.token:
            return self.token
        
        if self.oauth_client:
            token = await self.oauth_client.get_token()
            return token.access_token
        
        raise AuthenticationError("No token or OAuth2 configuration provided")
    
    async def get_authorization_header(self) -> str:
        """
        Get Authorization header value.
        
        Returns:
            Authorization header value
        """
        if self.token:
            return f"Bearer {self.token}"
        
        if self.oauth_client:
            return await self.oauth_client.get_authorization_header()
        
        raise AuthenticationError("No token or OAuth2 configuration provided")
    
    async def close(self):
        """Close resources"""
        if self.oauth_client:
            await self.oauth_client.close()