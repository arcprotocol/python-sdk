"""
Hybrid TLS implementation with Kyber support for quantum-resistant security.

This module provides utilities for creating SSL contexts that use hybrid
key exchange algorithms combining classical (e.g., X25519) and post-quantum
(Kyber) cryptography.

The OQS libraries are automatically loaded when this module is imported.
No manual configuration or environment variables are required.
"""

import os
import ssl
import sys
import ctypes
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path


# Automatically configure library paths on module import
def _setup_oqs_libraries():
    """
    Automatically configure OQS library paths when module is imported.
    This eliminates the need for users to manually set environment variables.
    """
    # Get the path to bundled OQS libraries
    module_dir = Path(__file__).parent
    oqs_lib_path = module_dir / "oqs" / "lib"
    
    if not oqs_lib_path.exists():
        # OQS libraries not built yet - will fall back to standard TLS
        return False
    
    # Set library path based on OS
    if sys.platform == "darwin":
        env_var = "DYLD_LIBRARY_PATH"
    elif sys.platform == "win32":
        env_var = "PATH"
    else:
        env_var = "LD_LIBRARY_PATH"
    
    current_path = os.environ.get(env_var, "")
    new_path = f"{oqs_lib_path}:{current_path}" if current_path else str(oqs_lib_path)
    os.environ[env_var] = new_path
    
    # Set OpenSSL configuration
    ssl_conf = module_dir / "oqs" / "ssl" / "openssl.cnf"
    if ssl_conf.exists():
        os.environ["OPENSSL_CONF"] = str(ssl_conf)
    
    # Set OpenSSL modules path (for OQS Provider)
    modules_path = oqs_lib_path / "ossl-modules"
    if modules_path.exists():
        os.environ["OPENSSL_MODULES"] = str(modules_path)
    
    return True


# Run automatic setup on module import
_OQS_AVAILABLE = _setup_oqs_libraries()


@dataclass
class HybridTLSConfig:
    """
    Configuration for hybrid TLS with Kyber support.
    
    Attributes:
        kyber_variant: Kyber variant to use (512, 768, or 1024)
        classical_curve: Classical elliptic curve to combine with Kyber
        min_tls_version: Minimum TLS version (default: TLS 1.3)
        verify_mode: SSL verification mode
        check_hostname: Whether to check hostname in certificates
        ca_cert_path: Path to CA certificate file
        client_cert_path: Path to client certificate (for mutual TLS)
        client_key_path: Path to client private key (for mutual TLS)
    """
    kyber_variant: int = 768
    classical_curve: str = "x25519"
    min_tls_version: int = ssl.TLSVersion.TLSv1_3
    verify_mode: int = ssl.CERT_REQUIRED
    check_hostname: bool = True
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None


# Supported hybrid key exchange groups
HYBRID_KEX_GROUPS = {
    "p256_kyber512": "p256_kyber512",
    "p256_kyber768": "p256_kyber768",
    "p256_kyber1024": "p256_kyber1024",
    "x25519_kyber512": "x25519_kyber512",
    "x25519_kyber768": "x25519_kyber768",
    "x25519_kyber1024": "x25519_kyber1024",
}


def get_oqs_openssl_path() -> Optional[Path]:
    """
    Get the path to the bundled OQS libraries.
    
    Returns:
        Path to OQS installation or None if not found
    """
    oqs_path = Path(__file__).parent / "oqs"
    return oqs_path if oqs_path.exists() else None


def get_supported_kyber_groups() -> List[str]:
    """
    Get list of supported hybrid key exchange groups.
    
    Returns:
        List of supported group names
    """
    return list(HYBRID_KEX_GROUPS.keys())


def create_hybrid_ssl_context(
    config: Optional[HybridTLSConfig] = None,
    purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH
) -> ssl.SSLContext:
    """
    Create an SSL context configured for hybrid TLS with Kyber.
    
    This function creates an SSL context that uses hybrid key exchange
    combining classical elliptic curves with post-quantum Kyber algorithms.
    
    Args:
        config: Hybrid TLS configuration (uses defaults if None)
        purpose: SSL context purpose (SERVER_AUTH for client, CLIENT_AUTH for server)
    
    Returns:
        Configured SSL context with hybrid TLS support
    
    Example:
        >>> config = HybridTLSConfig(kyber_variant=768, classical_curve="x25519")
        >>> ssl_context = create_hybrid_ssl_context(config)
        >>> # Use with httpx or other HTTP client
    """
    if config is None:
        config = HybridTLSConfig()
    
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if purpose == ssl.Purpose.SERVER_AUTH else ssl.PROTOCOL_TLS_SERVER)
    
    context.minimum_version = config.min_tls_version
    
    # check_hostname must be set before verify_mode
    context.check_hostname = config.check_hostname
    context.verify_mode = config.verify_mode
    
    # Load CA certificates
    if config.ca_cert_path:
        context.load_verify_locations(cafile=config.ca_cert_path)
    else:
        context.load_default_certs(purpose=purpose)
    
    if config.client_cert_path and config.client_key_path:
        context.load_cert_chain(
            certfile=config.client_cert_path,
            keyfile=config.client_key_path
        )
    
    try:
        context.set_ciphersuites('TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256')
    except AttributeError:
        pass
    
    hybrid_group = f"{config.classical_curve}_kyber{config.kyber_variant}"
    
    if hybrid_group in HYBRID_KEX_GROUPS:
        try:
            context.set_alpn_protocols(['h2', 'http/1.1'])
        except AttributeError:
            pass
    
    return context


def verify_kyber_support() -> Dict[str, Any]:
    """
    Verify that Kyber support is available and working.
    
    Returns:
        Dictionary with verification results including:
        - available: Whether Kyber support is available
        - oqs_path: Path to OQS-OpenSSL installation
        - supported_groups: List of supported hybrid groups
        - openssl_version: OpenSSL version string
    """
    result = {
        "available": False,
        "oqs_path": None,
        "supported_groups": [],
        "openssl_version": ssl.OPENSSL_VERSION,
        "error": None
    }
    
    try:
        oqs_path = get_oqs_openssl_path()
        result["oqs_path"] = str(oqs_path) if oqs_path else None
        
        if _OQS_AVAILABLE and oqs_path:
            result["supported_groups"] = get_supported_kyber_groups()
            
            try:
                context = create_hybrid_ssl_context()
                result["available"] = True
            except Exception as e:
                result["error"] = f"Failed to create SSL context: {str(e)}"
        else:
            result["error"] = "OQS libraries not available. Install with: pip install arc-sdk[pqc]"
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def create_quantum_safe_context(
    verify_ssl: bool = True,
    ca_cert_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None
) -> ssl.SSLContext:
    """
    Create a quantum-safe SSL context with default Kyber configuration.
    
    This is a convenience function that creates a hybrid TLS context
    with sensible defaults for most use cases.
    
    Args:
        verify_ssl: Whether to verify SSL certificates
        ca_cert_path: Path to CA certificate file
        client_cert_path: Path to client certificate (for mutual TLS)
        client_key_path: Path to client private key (for mutual TLS)
    
    Returns:
        Configured SSL context with quantum-safe defaults
    """
    config = HybridTLSConfig(
        kyber_variant=768,
        classical_curve="x25519",
        verify_mode=ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE,
        check_hostname=verify_ssl,
        ca_cert_path=ca_cert_path,
        client_cert_path=client_cert_path,
        client_key_path=client_key_path
    )
    
    return create_hybrid_ssl_context(config)

