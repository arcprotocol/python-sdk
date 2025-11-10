"""
Tests for Post-Quantum Cryptography (PQC) support in ARC SDK.

These tests verify that:
1. PQC libraries can be detected
2. SSL contexts are created correctly with/without PQC
3. Graceful fallback to standard TLS works
4. Client and server can use PQC
"""

import pytest
import ssl
from unittest.mock import patch, MagicMock

from arc.crypto import (
    verify_kyber_support,
    create_quantum_safe_context,
    create_hybrid_ssl_context,
    get_supported_kyber_groups,
    get_oqs_openssl_path,
    HybridTLSConfig,
    HYBRID_KEX_GROUPS
)


class TestPQCDetection:
    """Test PQC library detection and availability."""
    
    def test_verify_kyber_support_returns_dict(self):
        """Test that verify_kyber_support returns a dictionary with expected keys."""
        result = verify_kyber_support()
        
        assert isinstance(result, dict)
        assert "available" in result
        assert "oqs_path" in result
        assert "supported_groups" in result
        assert "openssl_version" in result
        assert "error" in result
    
    def test_get_oqs_path(self):
        """Test getting OQS library path."""
        path = get_oqs_openssl_path()
        # Path may be None if PQC not installed, which is valid
        assert path is None or path.exists()
    
    def test_supported_groups(self):
        """Test getting supported Kyber groups."""
        groups = get_supported_kyber_groups()
        
        assert isinstance(groups, list)
        assert len(groups) > 0
        # Should include hybrid groups
        assert any("kyber" in group for group in groups)


class TestHybridTLSConfig:
    """Test HybridTLSConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = HybridTLSConfig()
        
        assert config.kyber_variant == 768
        assert config.classical_curve == "x25519"
        assert config.min_tls_version == ssl.TLSVersion.TLSv1_3
        assert config.verify_mode == ssl.CERT_REQUIRED
        assert config.check_hostname is True
        assert config.ca_cert_path is None
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = HybridTLSConfig(
            kyber_variant=1024,
            classical_curve="x25519",
            verify_mode=ssl.CERT_NONE,
            check_hostname=False
        )
        
        assert config.kyber_variant == 1024
        assert config.classical_curve == "x25519"
        assert config.verify_mode == ssl.CERT_NONE
        assert config.check_hostname is False


class TestSSLContextCreation:
    """Test SSL context creation with PQC."""
    
    def test_create_quantum_safe_context_basic(self):
        """Test creating a quantum-safe SSL context."""
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        context = create_quantum_safe_context()
        
        assert isinstance(context, ssl.SSLContext)
        assert context.minimum_version == ssl.TLSVersion.TLSv1_3
    
    def test_create_quantum_safe_context_no_verify(self):
        """Test creating context without SSL verification."""
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        context = create_quantum_safe_context(verify_ssl=False)
        
        assert isinstance(context, ssl.SSLContext)
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE
    
    def test_create_hybrid_ssl_context_default(self):
        """Test creating hybrid SSL context with defaults."""
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        context = create_hybrid_ssl_context()
        
        assert isinstance(context, ssl.SSLContext)
        assert context.minimum_version == ssl.TLSVersion.TLSv1_3
    
    def test_create_hybrid_ssl_context_custom_config(self):
        """Test creating hybrid SSL context with custom config."""
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        config = HybridTLSConfig(
            kyber_variant=512,
            classical_curve="x25519"
        )
        context = create_hybrid_ssl_context(config)
        
        assert isinstance(context, ssl.SSLContext)


class TestClientPQC:
    """Test PQC integration with ARCClient."""
    
    @pytest.mark.asyncio
    async def test_client_with_pqc_available(self):
        """Test client uses PQC when available."""
        from arc import Client
        
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        client = Client(
            endpoint="https://example.com",
            token="test-token",
            use_quantum_safe=True
        )
        
        # Should have SSL context configured
        assert client.http_client is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_client_without_pqc(self):
        """Test client falls back gracefully when PQC not available."""
        from arc import Client
        
        # Mock PQC as unavailable
        with patch('arc.client.arc_client.QUANTUM_SAFE_AVAILABLE', False):
            client = Client(
                endpoint="https://example.com",
                token="test-token",
                use_quantum_safe=True
            )
            
            # Should still work with standard TLS
            assert client.http_client is not None
            
            await client.close()
    
    @pytest.mark.asyncio
    async def test_client_pqc_disabled(self):
        """Test client with PQC explicitly disabled."""
        from arc import Client
        
        client = Client(
            endpoint="https://example.com",
            token="test-token",
            use_quantum_safe=False
        )
        
        # Should work with standard TLS
        assert client.http_client is not None
        
        await client.close()


class TestServerPQC:
    """Test PQC integration with ARCServer."""
    
    def test_server_ssl_setup_with_pqc(self):
        """Test server SSL setup with PQC available."""
        from arc import Server
        
        result = verify_kyber_support()
        
        if not result["available"]:
            pytest.skip("PQC libraries not available")
        
        server = Server(server_id="test-server")
        
        # Mock SSL files
        ssl_config = server._setup_ssl_for_server(
            ssl_context=None,
            use_quantum_safe=True,
            hybrid_tls_config=None,
            ssl_keyfile="/fake/key.pem",
            ssl_certfile="/fake/cert.pem",
            ssl_ca_certs=None
        )
        
        # Should return SSL context or config dict
        assert ssl_config is not None
    
    def test_server_ssl_setup_without_pqc(self):
        """Test server SSL setup without PQC."""
        from arc import Server
        
        server = Server(server_id="test-server")
        
        # Mock PQC as unavailable
        with patch('arc.server.arc_server.QUANTUM_SAFE_AVAILABLE', False):
            ssl_config = server._setup_ssl_for_server(
                ssl_context=None,
                use_quantum_safe=True,
                hybrid_tls_config=None,
                ssl_keyfile="/fake/key.pem",
                ssl_certfile="/fake/cert.pem",
                ssl_ca_certs=None
            )
            
            # Should fall back to standard SSL config
            assert ssl_config is not None


class TestHybridKEXGroups:
    """Test hybrid key exchange group definitions."""
    
    def test_hybrid_kex_groups_defined(self):
        """Test that hybrid KEX groups are properly defined."""
        assert isinstance(HYBRID_KEX_GROUPS, dict)
        assert len(HYBRID_KEX_GROUPS) > 0
        
        # Check for expected groups
        expected_groups = [
            "p256_kyber512",
            "p256_kyber768",
            "p256_kyber1024",
            "x25519_kyber512",
            "x25519_kyber768",
            "x25519_kyber1024"
        ]
        
        for group in expected_groups:
            assert group in HYBRID_KEX_GROUPS


class TestPQCFallback:
    """Test graceful fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_client_fallback_on_error(self):
        """Test client falls back when PQC context creation fails."""
        from arc import Client
        
        # Mock create_quantum_safe_context to raise an error
        with patch('arc.client.arc_client.create_quantum_safe_context', side_effect=Exception("Test error")):
            with patch('arc.client.arc_client.QUANTUM_SAFE_AVAILABLE', True):
                client = Client(
                    endpoint="https://example.com",
                    token="test-token",
                    use_quantum_safe=True
                )
                
                # Should still work with fallback
                assert client.http_client is not None
                
                await client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

