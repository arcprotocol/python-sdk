# Post-Quantum Cryptography (PQC)

The ARC Python SDK includes optional post-quantum cryptography support using hybrid TLS with Kyber.

> [!IMPORTANT]
> **Installation**: `pip install arc-sdk[pqc]` builds quantum-resistant cryptography libraries automatically.

## Installation

```bash
pip install arc-sdk[pqc]
```

## Prerequisites

You need these build tools installed:

### macOS
```bash
brew install cmake ninja
xcode-select --install
```

### Linux (Debian/Ubuntu)
```bash
sudo apt-get install cmake ninja-build build-essential
```

### Linux (RedHat/CentOS/Fedora)
```bash
sudo yum install cmake ninja-build
sudo yum groupinstall 'Development Tools'
```

### Windows
```bash
choco install cmake ninja visualstudio2022buildtools
```

Or download manually:
- CMake: https://cmake.org/download/
- Ninja: https://github.com/ninja-build/ninja/releases
- Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/

> [!NOTE]
> These are standard cross-platform build tools used by many projects.

## Usage

### Client

```python
from arc import Client

# PQC is enabled by default - uses x25519_kyber768 automatically
client = Client(
    endpoint="https://api.example.com/arc",
    token="your-token"
)
```

> [!TIP]
> To disable PQC (if installed but you don't want to use it), set `use_quantum_safe=False`:
> ```python
> client = Client(endpoint="...", token="...", use_quantum_safe=False)
> ```

### Server

```python
from arc import Server

server = Server(server_id="my-server")

# PQC is enabled by default
server.run(
    host="0.0.0.0",
    port=443,
    ssl_keyfile="/path/to/server.key",
    ssl_certfile="/path/to/server.crt"
)
```

> [!TIP]
> To disable PQC on the server, set `use_quantum_safe=False` in `server.run()`.

## What is Hybrid TLS?

Combines classical and post-quantum cryptography:
- **Classical**: X25519 (Curve25519 elliptic curve)
- **Post-Quantum**: Kyber-768 (NIST FIPS 203 ML-KEM)

**Result**: Secure against both current and future quantum attacks.

**Default**: `x25519_kyber768` (X25519 + Kyber-768)

**Industry Implementations**:
- **Zoom**: Uses Kyber-768 for E2EE (May 2024)
- **Chrome**: Uses X25519Kyber768 hybrid for TLS (Aug 2023)
- **Cloudflare**: Uses X25519MLKEM768 hybrid for TLS (2022)

## Verification

Check if PQC is available:

```python
from arc.crypto import verify_kyber_support
import json

result = verify_kyber_support()
print(json.dumps(result, indent=2))
```

Expected output:
```json
{
  "available": true,
  "supported_groups": ["x25519_kyber768", "x25519_kyber512", ...],
  "openssl_version": "OpenSSL 3.x.x"
}
```

## How It Works

> [!NOTE]
> **Requirements**: Both client and server must install `arc-sdk[pqc]` for post-quantum cryptography.

**TLS Handshake**:
- Both sides have PQC → Negotiates `x25519_kyber768` hybrid key exchange
- One side missing PQC → OpenSSL falls back to classical X25519

> [!TIP]
> **Process**: Install → Import → Connect. Libraries load automatically, hybrid TLS is negotiated during handshake.

## References

> [!NOTE]
> **Official NIST Documentation**:
> - [FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf)
> - [NIST Post-Quantum Cryptography Project](https://csrc.nist.gov/projects/post-quantum-cryptography)
> - [NIST IR 8413: Status Report on the Third Round of the NIST PQC Standardization Process](https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8413.pdf)

**Implementation**:
- [Open Quantum Safe (OQS) Project](https://openquantumsafe.org/)
- [liboqs: C library for quantum-resistant cryptography](https://github.com/open-quantum-safe/liboqs)
- [OQS Provider for OpenSSL 3](https://github.com/open-quantum-safe/oqs-provider)
- [CRYSTALS-Kyber Official Website](https://pq-crystals.org/kyber/)

## License

Apache 2.0 (same as ARC SDK)
