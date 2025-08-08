"""
JWT Token Validation for ARC Protocol

Validates JWT tokens from OAuth2 providers using JWKS (JSON Web Key Sets).
Supports standard OAuth2 providers like Auth0, Google, Azure AD, etc.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Set
import httpx
import jwt
from jwt import PyJWKClient
import logging
from datetime import datetime, timedelta

from ..exceptions import (
    AuthenticationError, TokenExpiredError, TokenInvalidError, NetworkError
)


logger = logging.getLogger(__name__)


class JWTValidator:
    """
    JWT token validator using JWKS from OAuth2 providers.
    
    Validates JWT tokens by:
    1. Fetching public keys from JWKS endpoint
    2. Verifying token signature
    3. Checking token expiration
    4. Validating issuer and audience claims
    """
    
    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: Optional[str] = None,
        algorithms: List[str] = None,
        cache_ttl: int = 300  # 5 minutes
    ):
        """
        Initialize JWT validator.
        
        Args:
            jwks_url: JWKS endpoint URL for fetching public keys
            issuer: Expected token issuer
            audience: Expected token audience (optional)
            algorithms: Allowed JWT algorithms (default: ["RS256"])
            cache_ttl: JWKS cache TTL in seconds
        """
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms or ["RS256"]
        self.cache_ttl = cache_ttl
        
        # Initialize JWKS client for fetching public keys
        self.jwks_client = PyJWKClient(
            jwks_url,
            cache_ttl=cache_ttl,
            max_cached_keys=10
        )
        
        logger.info(f"JWT validator initialized for issuer: {issuer}")
        logger.debug(f"JWKS URL: {jwks_url}")
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and return claims.
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary containing token claims
            
        Raises:
            TokenExpiredError: If token is expired
            TokenInvalidError: If token is invalid
            AuthenticationError: For other validation errors
        """
        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate token
            decode_options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "require": ["exp", "iat", "iss"]
            }
            
            # Add audience validation if specified
            if self.audience:
                decode_options["verify_aud"] = True
                decode_options["require"].append("aud")
            
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.algorithms,
                options=decode_options,
                audience=self.audience,
                issuer=self.issuer
            )
            
            logger.debug(f"Token validated successfully for subject: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError(f"Token expired: {str(e)}")
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Token validation error: {str(e)}")
    
    def get_scopes(self, claims: Dict[str, Any]) -> Set[str]:
        """
        Extract OAuth2 scopes from token claims.
        
        Handles different scope formats:
        - "scope" as space-separated string
        - "scope" as list of strings
        - "scp" as space-separated string
        - "scopes" as list of strings
        
        Args:
            claims: Token claims
            
        Returns:
            Set of scope strings
        """
        scopes = set()
        
        # Check common scope claim names
        if "scope" in claims:
            scope_value = claims["scope"]
            if isinstance(scope_value, str):
                scopes.update(scope_value.split())
            elif isinstance(scope_value, list):
                scopes.update(scope_value)
                
        elif "scp" in claims:
            scope_value = claims["scp"]
            if isinstance(scope_value, str):
                scopes.update(scope_value.split())
            elif isinstance(scope_value, list):
                scopes.update(scope_value)
                
        elif "scopes" in claims:
            scope_value = claims["scopes"]
            if isinstance(scope_value, list):
                scopes.update(scope_value)
                
        return scopes
    
    def has_scope(self, claims: Dict[str, Any], required_scope: str) -> bool:
        """
        Check if token has the required scope.
        
        Args:
            claims: Token claims
            required_scope: Required OAuth2 scope
            
        Returns:
            True if token has the required scope
        """
        scopes = self.get_scopes(claims)
        return required_scope in scopes
    
    def has_scopes(self, claims: Dict[str, Any], required_scopes: List[str]) -> bool:
        """
        Check if token has all required scopes.
        
        Args:
            claims: Token claims
            required_scopes: List of required OAuth2 scopes
            
        Returns:
            True if token has all required scopes
        """
        scopes = self.get_scopes(claims)
        return all(scope in scopes for scope in required_scopes)
    
    def check_scopes(self, claims: Dict[str, Any], required_scopes: List[str]) -> bool:
        """
        Check if token has all required scopes and raise exception if not.
        
        Args:
            claims: Token claims
            required_scopes: List of required OAuth2 scopes
            
        Returns:
            True if token has all required scopes
            
        Raises:
            AuthenticationError: If token does not have required scopes
        """
        scopes = self.get_scopes(claims)
        missing_scopes = [scope for scope in required_scopes if scope not in scopes]
        
        if missing_scopes:
            from ..exceptions import InsufficientScopeError
            raise InsufficientScopeError(
                required_scopes=required_scopes,
                provided_scopes=list(scopes),
                message=f"Token missing required scopes: {', '.join(missing_scopes)}"
            )
        
        return True


class OAuth2ProviderValidator:
    """
    Validator factory for common OAuth2 providers.
    
    Provides pre-configured validators for popular OAuth2 providers.
    """
    
    PROVIDER_CONFIGS = {
        "auth0": {
            "jwks_url_template": "https://{tenant_domain}/.well-known/jwks.json",
            "issuer_template": "https://{tenant_domain}/"
        },
        "azure": {
            "jwks_url_template": "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            "issuer_template": "https://sts.windows.net/{tenant_id}/"
        },
        "google": {
            "jwks_url": "https://www.googleapis.com/oauth2/v3/certs",
            "issuer": "https://accounts.google.com"
        },
        "okta": {
            "jwks_url_template": "https://{okta_domain}/oauth2/v1/keys",
            "issuer_template": "https://{okta_domain}"
        },
        "keycloak": {
            "jwks_url_template": "{server_url}/realms/{realm_name}/protocol/openid-connect/certs",
            "issuer_template": "{server_url}/realms/{realm_name}"
        }
    }
    
    @classmethod
    def create_validator(
        cls,
        provider: str,
        audience: Optional[str] = None,
        **provider_config
    ) -> JWTValidator:
        """
        Create JWT validator for a specific provider.
        
        Args:
            provider: Provider name (auth0, azure, google, okta, keycloak, custom)
            audience: Expected audience claim
            **provider_config: Provider-specific configuration
            
        Returns:
            Configured JWTValidator instance
            
        Raises:
            ValueError: If provider is unsupported or required config is missing
        """
        provider = provider.lower()
        
        # Handle custom provider
        if provider == "custom":
            jwks_url = provider_config.get("jwks_url")
            issuer = provider_config.get("issuer")
            
            if not jwks_url or not issuer:
                raise ValueError("custom provider requires jwks_url and issuer")
                
            return JWTValidator(
                jwks_url=jwks_url,
                issuer=issuer,
                audience=audience,
                algorithms=provider_config.get("algorithms")
            )
            
        # Handle known providers
        if provider not in cls.PROVIDER_CONFIGS:
            raise ValueError(f"Unsupported provider: {provider}")
            
        config = cls.PROVIDER_CONFIGS[provider]
        
        # Resolve templates
        if "jwks_url" in config:
            jwks_url = config["jwks_url"]
        elif "jwks_url_template" in config:
            template = config["jwks_url_template"]
            try:
                jwks_url = template.format(**provider_config)
            except KeyError as e:
                raise ValueError(f"Missing required config for {provider}: {e}")
        else:
            raise ValueError(f"Invalid provider configuration for {provider}")
            
        if "issuer" in config:
            issuer = config["issuer"]
        elif "issuer_template" in config:
            template = config["issuer_template"]
            try:
                issuer = template.format(**provider_config)
            except KeyError as e:
                raise ValueError(f"Missing required config for {provider}: {e}")
        else:
            raise ValueError(f"Invalid provider configuration for {provider}")
            
        return JWTValidator(
            jwks_url=jwks_url,
            issuer=issuer,
            audience=audience,
            algorithms=provider_config.get("algorithms")
        )


class MultiProviderJWTValidator:
    """
    JWT validator that tries multiple validators in sequence.
    
    Useful when accepting tokens from multiple OAuth2 providers.
    """
    
    def __init__(self, validators: Dict[str, JWTValidator]):
        """
        Initialize multi-provider validator.
        
        Args:
            validators: Dictionary mapping provider names to JWTValidator instances
        """
        self.validators = validators
        logger.info(f"Multi-provider JWT validator initialized with providers: {', '.join(validators.keys())}")
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token against all providers.
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary containing token claims and provider
            
        Raises:
            AuthenticationError: If token is not valid for any provider
        """
        errors = []
        
        for provider_name, validator in self.validators.items():
            try:
                claims = await validator.validate_token(token)
                claims["_provider"] = provider_name
                return claims
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")
                
        raise AuthenticationError(f"Token validation failed for all providers: {'; '.join(errors)}")


def create_validator_from_config(config: Dict[str, Any]) -> JWTValidator:
    """
    Create JWT validator from configuration.
    
    Args:
        config: Validator configuration
        
    Returns:
        JWTValidator instance
    """
    provider = config.pop("provider", "custom")
    audience = config.pop("audience", None)
    
    return OAuth2ProviderValidator.create_validator(
        provider=provider,
        audience=audience,
        **config
    )