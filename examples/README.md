# ARC Protocol Python SDK Examples

This directory contains example applications demonstrating how to use the ARC (Agent Remote Communication) Protocol Python SDK. These examples are organized to show both server and client implementations, as well as specialized use cases.

## Directory Structure

- **`server/`**: Server implementations
  - `basic_server.py` - A complete server that handles both task and stream methods

- **`client/`**: Client implementations
  - `basic_client.py` - A simple client that demonstrates connecting to an ARC server

- **`task_examples/`**: Task-based communication examples (client-side)
  - `create_task.py` - Shows basic task creation and management
  - `multi_agent_workflow.py` - Orchestrates a complex workflow with multiple agents

- **`chat_examples/`**: Chat communication examples (client-side)
  - `realtime_chat.py` - Implements a simple chat application using real-time communication
  - `streaming_response.py` - Shows how to handle streaming responses using SSE

## Getting Started

The simplest way to start using these examples is to run the basic server and client:

1. Start the server:
   ```bash
   cd server
   python basic_server.py
   ```

2. In a new terminal, run the client:
   ```bash
   cd client
   python basic_client.py
   ```

## Prerequisites

Before running these examples, you'll need:

1. Python 3.7+
2. For real-world usage: An OAuth2 provider (for authentication)
3. For the use-case examples: ARC-compatible agents to communicate with

## Configuration

Most examples use environment variables for configuration:

```bash
# Server Configuration
export SERVER_PORT=8000          # Port for the server to listen on
export ENABLE_AUTH=False         # Enable/disable auth for local testing

# Client Configuration
export ARC_SERVER_URL=http://localhost:8000    # URL of the ARC server
export ARC_TARGET_AGENT=arc-example-agent      # Agent ID of the target
export ARC_REQUEST_AGENT=arc-example-client    # Your client's agent ID

# OAuth2 Configuration (for production use)
export OAUTH_CLIENT_ID=your-client-id
export OAUTH_CLIENT_SECRET=your-client-secret
export OAUTH_PROVIDER=auth0|google|azure|okta  # or 'custom' for custom provider
export OAUTH_SCOPE="arc.agent.caller arc.task.controller"  # Adjust scopes as needed

# For custom OAuth provider
export OAUTH_TOKEN_URL=https://your-provider.com/oauth/token
```

For local testing, you can use HTTP URLs and dev tokens, but the examples will warn about insecure connections.

## How the Examples Work

### Server-Client Pattern

The ARC protocol follows a server-client pattern:

1. **Server**: Implements handlers for the ARC methods (task.create, chat.start, etc.)
2. **Client**: Connects to the server and calls these methods

To test, you always need to run a server first, then connect with a client.

### Available Examples

#### Basic Server and Client

- **`server/basic_server.py`**: A complete server implementation supporting all ARC methods
  - Handles both task and chat methods
  - Includes mock implementations for testing
  - Can be extended with real business logic

- **`client/basic_client.py`**: A simple client that tests all available methods
  - Shows how to create the client and authenticate
  - Demonstrates calling all supported methods
  - Handles responses and errors

#### Task Examples

- **`task_examples/create_task.py`**: Shows basic task creation and management
  - Demonstrates: task.create, task.send, task.get

- **`task_examples/multi_agent_workflow.py`**: Orchestrates a complex workflow with multiple agents
  - Demonstrates: Coordinating multiple agents, parallel processing, result aggregation

#### Chat Examples

- **`chat_examples/realtime_chat.py`**: Implements a simple chat application using real-time communication
  - Demonstrates: chat.start, chat.message, chat.end

- **`chat_examples/streaming_response.py`**: Shows how to handle streaming responses using SSE
  - Demonstrates: chat.start with streaming, chat.message with streaming, chat.end

## Key Concepts

- **Authentication**: OAuth2 client credentials flow
- **Task Operations**: Creating, updating, and retrieving asynchronous tasks
- **Chat Operations**: Real-time interactive communication with streaming support
- **Multi-Agent Workflows**: Coordinating multiple specialized agents
- **Error Handling**: Proper error detection and recovery
- **Tracing**: Using trace IDs for end-to-end request tracking

## Additional Resources

- [ARC Protocol Official Specification](https://github.com/arc-protocol/arc-protocol)
- [Python SDK Documentation](https://docs.arc-protocol.org/python-sdk/)
- [API Reference](https://docs.arc-protocol.org/python-sdk/api-reference)