# ARC Protocol SDK Examples

This directory contains examples and test scripts for the ARC Protocol Python SDK.

## Quick Start

### 1. Start the Test Server

```bash
cd examples/server
python arc_test_server.py
```

This will start a test server on `http://localhost:8000/arc`.

### 2. Make Test Scripts Executable (One-Time Setup)

```bash
cd examples/client
chmod +x test_*.py
```

### 3. Run Individual Tests

Once executable, you can run tests directly:

```bash
# Start a chat
./test_chat_start.py --message "Hello!"

# Send a message (use the chat_id from previous command)
./test_chat_message.py <chat_id> --message "Follow-up message"

# End the chat
./test_chat_end.py <chat_id> --reason "Done"

# Create a task
./test_task_create.py --message "Task description"

# Get task info
./test_task_info.py <task_id>

# Send to task
./test_task_send.py <task_id> --message "Additional info"

# Cancel task
./test_task_cancel.py <task_id> --reason "No longer needed"
```

## Server Examples

The `server` directory contains an example server implementation that can be used to test the SDK locally.

## Client Examples

The `client` directory contains test scripts for each method in the ARC Protocol.

### Running the Full Test Suite

To run all tests against the local server:

```bash
cd examples/client
python arc_client_test.py
```

You can also run specific test suites:

```bash
# Run only task-related tests
python arc_client_test.py --tests task

# Run only chat-related tests
python arc_client_test.py --tests chat
```

### Testing Individual Methods

Each method of the ARC Protocol has a dedicated test script:

#### Task Methods

1. **task.create** - Create a new task
   ```bash
   python test_task_create.py
   ```

2. **task.info** - Get information about a task
   ```bash
   python test_task_info.py <task_id>
   ```

3. **task.send** - Send a message to a task
   ```bash
   python test_task_send.py <task_id> --message "Additional information"
   ```

4. **task.cancel** - Cancel a task
   ```bash
   python test_task_cancel.py <task_id> --reason "No longer needed"
   ```

5. **task.subscribe** - Subscribe to task events
   ```bash
   python test_task_subscribe.py <task_id> --callback "https://example.com/webhook"
   ```

#### Chat Methods

1. **chat.start** - Start a new chat session
   ```bash
   python test_chat_start.py
   ```

2. **chat.message** - Send a message to an existing chat
   ```bash
   python test_chat_message.py <chat_id> --message "Hello there"
   ```

3. **chat.end** - End a chat session
   ```bash
   python test_chat_end.py <chat_id> --reason "Conversation complete"
   ```

### Testing with Streaming

Some methods support streaming responses. To test streaming:

```bash
python test_chat_start.py --stream
python test_chat_message.py <chat_id> --stream
```

Note: The test server doesn't implement true streaming but provides compatible responses.

## Example Workflow

Here's a typical workflow for testing the complete API:

```bash
# Start the server (in one terminal)
cd examples/server
python arc_test_server.py

# In another terminal, run tests
cd examples/client

# Create a task
task_id=$(python test_task_create.py | grep "Task ID:" | awk '{print $3}')

# Get task info
python test_task_info.py $task_id

# Send a message to the task
python test_task_send.py $task_id

# Subscribe to task updates
python test_task_subscribe.py $task_id

# Cancel the task
python test_task_cancel.py $task_id

# Start a chat
chat_id=$(python test_chat_start.py | grep "Chat ID:" | awk '{print $3}')

# Send a message to the chat
python test_chat_message.py $chat_id

# End the chat
python test_chat_end.py $chat_id
```

## Advanced Options

All test scripts support additional options:

- `--url` - ARC server endpoint URL (default: http://localhost:8000/arc)
- `--agent` - Target agent ID (default: test-arc-server)
- `--client-id` - Client agent ID (default: test-arc-client)
- `--verbose` or `-v` - Enable verbose output with full responses