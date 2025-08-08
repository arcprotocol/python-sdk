# Contributing to ARC Python SDK

Thank you for your interest in contributing to the Agent Remote Communication (ARC) Protocol Python implementation! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [moein.roghani@proton.me](mailto:moein.roghani@proton.me).

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Virtual environment tool (venv, conda, or poetry)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/python-sdk.git
   cd python-sdk
   ```

## Development Setup

### 1. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Using conda
conda create -n arc-sdk python=3.11
conda activate arc-sdk
```

### 2. Install Development Dependencies

```bash
# Install in development mode with all extras
pip install -e ".[dev,test,docs,validation]"

# Or using poetry
poetry install --with dev,test,docs
```

### 3. Install Pre-commit Hooks

```bash
pre-commit install
```

### 4. Verify Installation

```bash
# Run tests
pytest

# Check code style
black --check .
flake8 .
mypy arc/

# Validate package
python -m arc.utils.schema info
```

## Contributing Guidelines

### Types of Contributions

We welcome the following types of contributions:

- **🐛 Bug fixes** - Fix issues in existing code
- **✨ New features** - Add new functionality to ARC
- **📚 Documentation** - Improve docs, examples, or guides
- **🧪 Tests** - Add or improve test coverage
- **🎨 Code quality** - Refactoring, performance improvements
- **🔧 Tooling** - CI/CD, development tools, automation

### Before You Start

1. **Search existing issues** - Check if your bug/feature is already reported
2. **Open an issue** - Discuss significant changes before implementing
3. **Check roadmap** - Ensure your contribution aligns with project goals

### ARC Protocol Compliance

When contributing, ensure your changes maintain compliance with the ARC Protocol specification:

- **Protocol Version**: All implementations must support ARC 1.0
- **Method Support**: Implement all 10 standard methods (task.*, chat.*, notification methods)
- **Schema Validation**: Validate request/response structures against ARC schema
- **OAuth2 Scopes**: Properly handle agent-specific OAuth2 scopes
- **Agent Routing**: Maintain `requestAgent`/`targetAgent` semantics
- **Workflow Tracing**: Preserve `traceId` for multi-agent workflows

## Pull Request Process

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number
```

### 2. Make Changes

- Follow [Code Style](#code-style) guidelines
- Add/update tests for your changes
- Update documentation if needed
- Ensure all tests pass

### 3. Commit Changes

Use conventional commits format:
```bash
git commit -m "feat: add stream.chunk method implementation"
git commit -m "fix: handle OAuth2 token refresh in ARCClient"
git commit -m "docs: update multi-agent workflow examples"
```

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title and description
- Link to related issues
- Description of changes made
- Testing performed

## Code Style

### Python Style

We use the following tools for code quality:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type checking
mypy arc/
```

### Code Guidelines

- **Type hints**: Use type hints for all public APIs
- **Docstrings**: Use Google-style docstrings
- **Error handling**: Provide meaningful error messages
- **Logging**: Use structured logging with appropriate levels

### Example Code Style

```python
from typing import Optional, Dict, Any
from arc.schemas import ARCRequest, ARCResponse

class ARCClient:
    """ARC Protocol client for agent communication.
    
    This client provides methods for interacting with ARC-compatible agents
    using the Agent Remote Communication protocol.
    
    Args:
        endpoint: The ARC endpoint URL
        token: OAuth2 bearer token for authentication
        
    Example:
        >>> client = ARCClient("https://api.company.com/arc", token="...")
        >>> task = await client.task.create(target_agent="doc-analyzer", ...)
    """
    
    def __init__(self, endpoint: str, token: str) -> None:
        self.endpoint = endpoint
        self.token = token
        
    async def send_request(
        self, 
        request: ARCRequest,
        timeout: Optional[float] = None
    ) -> ARCResponse:
        """Send ARC request and return response.
        
        Args:
            request: The ARC request object
            timeout: Request timeout in seconds
            
        Returns:
            ARC response object
            
        Raises:
            ARCError: If request fails or response is invalid
        """
        # Implementation here...
```

## Testing

### Test Structure

```
tests/
├── unit/              # Unit tests for individual components
│   ├── test_client.py
│   ├── test_schemas.py
│   └── test_utils.py
├── integration/       # Integration tests with real services
│   ├── test_task_flow.py
│   └── test_stream_flow.py
└── fixtures/          # Test data and fixtures
    ├── requests.json
    └── responses.json
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_client.py

# Run with coverage
pytest --cov=arc --cov-report=html

# Run integration tests (requires test server)
pytest tests/integration/ --integration
```

### Writing Tests

- Use `pytest` framework
- Mock external dependencies
- Test both success and error cases
- Include ARC protocol compliance tests

```python
import pytest
from arc import ARCClient
from arc.schemas import ARCRequest

@pytest.mark.asyncio
async def test_task_create_success():
    """Test successful task creation."""
    client = ARCClient("https://test.arc", token="test-token")
    
    # Mock the HTTP client
    with patch.object(client, '_send_http_request') as mock_send:
        mock_send.return_value = {
            "arc": "1.0",
            "id": "req_001",
            "result": {"type": "task", "task": {"taskId": "task-123"}},
            "error": None
        }
        
        response = await client.task.create(
            target_agent="test-agent",
            initial_message={"role": "user", "parts": [{"type": "TextPart", "content": "test"}]}
        )
        
        assert response.result.task.taskId == "task-123"
```

## Documentation

### Types of Documentation

- **API Reference** - Auto-generated from docstrings
- **User Guide** - Step-by-step tutorials and examples
- **Protocol Guide** - ARC protocol implementation details
- **Examples** - Real-world usage patterns

### Writing Documentation

- Use clear, concise language
- Include code examples
- Update docstrings for new/changed APIs
- Add examples to `examples/` directory

### Building Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Build documentation
cd docs/
make html

# Serve locally
python -m http.server 8000 -d _build/html/
```

## Issue Reporting

### Bug Reports

Please include:

- **Environment**: Python version, OS, ARC SDK version
- **Steps to reproduce**: Minimal code example
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs/errors**: Full error messages and stack traces

### Feature Requests

Please include:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other ways to solve the problem
- **ARC compliance**: How does it fit with ARC protocol?

## Release Process

### Version Numbering

We follow semantic versioning (SemVer):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml` and `setup.py`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create release PR
5. Tag release: `git tag v1.2.3`
6. Build and publish to PyPI
7. Create GitHub release

### Publishing to PyPI

```bash
# Test on TestPyPI first
./release.sh

# Manual process
python -m build
twine upload --repository testpypi dist/*
twine upload dist/*
```

## Community

- **GitHub Discussions**: For questions and community discussions
- **Issues**: For bug reports and feature requests
- **Discord**: Join our community server (link in README)
- **Protocol Updates**: Follow [@arcprotocol](https://twitter.com/arcprotocol)

## License

By contributing to ARC Python SDK, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to the ARC Protocol ecosystem! 🚀
