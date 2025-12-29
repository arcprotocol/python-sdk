# Agent Remote Communication (ARC) Protocol

[![PyPI version](https://badge.fury.io/py/arc-sdk.svg)](https://badge.fury.io/py/arc-sdk)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/arc-sdk)](https://pepy.tech/project/arc-sdk)
[![GitHub stars](https://img.shields.io/github/stars/arcprotocol/python-sdk.svg?style=social&label=Star)](https://github.com/arcprotocol/python-sdk)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Agent-to-Agent Communication Protocol

**ARC (Agent Remote Communication)** is an agent-to-agent protocol with built-in agent routing, workflow tracing, and SSE streaming. Deploy multiple agent types on a single endpoint.

> [!IMPORTANT]
> **Quantum-Resistant Security**: ARC SDK implements end-to-end encryption using hybrid TLS (X25519 + Kyber-768), combining classical cryptography with post-quantum algorithms (FIPS 203 ML-KEM). Protects against quantum computing attacks.

### Server Architecture

Single package with multiple deployment options:
- **Custom ASGI Server** - Standalone server with built-in middleware (zero dependencies)
- **FastAPI Integration** - Router for existing FastAPI applications (optional: `pip install arc-sdk[fastapi]`)
- **Starlette Integration** - Lightweight ASGI toolkit integration (optional: `pip install arc-sdk[starlette]`)

### Key Features

- **Single Endpoint, Multiple Agents** - Deploy multiple agents behind one endpoint
- **Cross-Agent Workflows** - Agent A → Agent B → Agent C with full traceability via `traceId`
- **Agent Routing** - Built-in routing to target agents
- **End-to-End Tracing** - Track workflows across agent interactions
- **State Management** - Built-in chat session management with persistent storage (Redis, PostgreSQL, MongoDB)

### ARC vs Other Agent-to-Agent Protocols

| Feature | **ARC Protocol** | **A2A (Google)** | **ACP (IBM/Linux Foundation)** |
|---------|------------------|-------------------|--------------------------------|
| **Streaming Model** | ✅ SSE (Server-Sent Events) | ✅ SSE downstream | ⚠️ Chunked HTTP, not duplex |
| **Transport** | ✅ HTTP/1.1 + SSE | ✅ HTTP/1.1 + SSE | ❌ HTTP/1.x only |
| **Message Format** | ✅ JSON with structured parts | ✅ JSON with parts | ✅ JSON with MIME parts |
| **Task Lifecycle** | ✅ Native task methods + webhooks | ⚠️ SSE + webhook registration | ⚠️ Client polling/resume |
| **Multi-Agent Routing** | ✅ Single endpoint, built-in | ✅ Agent Card discovery | ⚠️ Manifest-based, looser |
| **Agent Discovery** | ✅ Built-in agent routing | ✅ Agent Card system | ⚠️ Manifest-based discovery |
| **Error Handling** | ✅ Rich error taxonomy (500+ codes) | ⚠️ JSON-RPC error codes | ⚠️ HTTP status codes |
| **Workflow Tracing** | ✅ Native `traceId` support | ⚠️ Custom implementation | ⚠️ Custom implementation |
| **Learning Curve** | ✅ Simple RPC-style | ✅ Familiar JSON-RPC | ✅ REST-like HTTP |
| **Governance** | ✅ Open Protocol | ⚠️ Google-led | ✅ Linux Foundation |

## Installation

### Core Package

```bash
pip install arc-sdk
```

### With Post-Quantum Cryptography

```bash
pip install arc-sdk[pqc]
```

> [!NOTE]
> Adds quantum-resistant hybrid TLS (X25519 + Kyber-768). See [PQC Documentation](README_QUANTUM_SAFE.md).

### With FastAPI Integration
```bash
pip install arc-sdk[fastapi]
```

### With Starlette Integration

```bash
pip install arc-sdk[starlette]
```

### All Features

```bash
pip install arc-sdk[all,pqc]
```

## Quick Start

### Client

```python
from arc import Client

client = Client("https://company.com/arc", token="your-oauth2-token")

# Create task
task = await client.task.create(
    target_agent="document-analyzer",
    initial_message={"role": "user", "parts": [{"type": "text", "content": "Analyze report"}]}
)

# Start chat
chat = await client.chat.start(
    target_agent="support-agent",
    initial_message={"role": "user", "parts": [{"type": "text", "content": "Help with account"}]}
)
```

### Server

```python
from arc import Server

server = Server(server_id="my-server")

@server.agent_handler("finance-agent", "chat.start")
async def handle_chat(params, context):
    return {"type": "chat", "chat": {...}}

server.run(host="0.0.0.0", port=8000)
```

## Documentation

- [Protocol Specification](https://arc-protocol.org/spec)
- [State Management Guide](docs/STATE_MANAGEMENT_GUIDE.md)
- [Examples](https://github.com/arcprotocol/examples)

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
