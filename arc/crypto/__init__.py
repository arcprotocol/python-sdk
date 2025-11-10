"""
Quantum-resistant cryptography support for ARC Protocol
Uses OQS Provider for OpenSSL 3 with Kyber for hybrid TLS

The OQS libraries are automatically loaded when this module is imported.
No manual configuration required.
"""

from .hybrid_tls import (
    create_hybrid_ssl_context,
    create_quantum_safe_context,
    get_supported_kyber_groups,
    get_oqs_openssl_path,
    verify_kyber_support,
    HybridTLSConfig,
    HYBRID_KEX_GROUPS
)

__all__ = [
    'create_hybrid_ssl_context',
    'create_quantum_safe_context',
    'get_supported_kyber_groups',
    'get_oqs_openssl_path',
    'verify_kyber_support',
    'HybridTLSConfig',
    'HYBRID_KEX_GROUPS'
]

