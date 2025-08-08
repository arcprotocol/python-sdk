"""
ARC Authentication Module

Provides OAuth2 authentication components for ARC SDK:
- OAuth2 client credentials flow
- JWT token validation with JWKS
- Support for major OAuth2 providers (Auth0, Google, Azure, Okta)
"""

from .oauth2_client import (
    OAuth2Token, OAuth2ClientCredentials, OAuth2Config, 
    create_oauth2_client, OAuth2Handler
)
from .jwt_validator import (
    JWTValidator, OAuth2ProviderValidator, MultiProviderJWTValidator,
    create_validator_from_config
)

__all__ = [
    # OAuth2 Client
    "OAuth2Token",
    "OAuth2ClientCredentials",
    "OAuth2Config",
    "create_oauth2_client",
    "OAuth2Handler",
    
    # JWT Validation
    "JWTValidator",
    "OAuth2ProviderValidator",
    "MultiProviderJWTValidator",
    "create_validator_from_config"
]
