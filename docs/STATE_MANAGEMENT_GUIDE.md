# ARC Protocol - State Management Guide

## Table of Contents
- [Overview](#overview)
- [Architecture Principles](#architecture-principles)
- [Client-Side State Management](#client-side-state-management-platform)
- [Server-Side State Management](#server-side-state-management-agents)
- [Storage Options](#storage-options)
- [Framework Integration](#framework-integration)
- [Best Practices](#best-practices)

---

## Overview

The ARC protocol uses a **dual-sided state management** architecture where both the client (Platform) and server (Agent) maintain their own conversation state independently.

### Key Principles

1. **Client and Server maintain separate state**
   - Platform stores user conversation context
   - Agents store framework-specific processing state

2. **Standard communication, flexible storage**
   - ARC protocol is the communication standard
   - Each side chooses its own storage solution

3. **Reference-based linking**
   - Platform tracks `agent_id → chat_id` mappings
   - Agent tracks `chat_id → framework_thread_id` mappings
   - Frameworks handle actual message/state storage

---

## Architecture Principles

### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER CONVERSATION                        │
│                                                                   │
│  User ←→ Platform (WebSocket) ←→ Platform Storage                │
│           ↓                                                       │
│           ↓ ARC Protocol (HTTP/HTTPS)                            │
│           ↓                                                       │
│           ↓                                                       │
│  Platform ←→ Agent Server ←→ Framework Storage                   │
│                    ↓                                              │
│              Framework Agent                                      │
│          (LangChain, LlamaIndex, etc.)                           │
└─────────────────────────────────────────────────────────────────┘
```

### What Gets Stored Where

| Storage Location | What's Stored | Purpose |
|-----------------|---------------|---------|
| **Platform Storage** | `agent_id → chat_id` mappings, User context | Track which agents user talked to |
| **Agent Storage (ChatManager)** | `chat_id → framework_thread_id` mappings | Link ARC protocol to framework |
| **Framework Storage** | Messages, state, checkpoints | Actual conversation data |

---

## Client-Side State Management (Platform)

### What the Platform Manages

The Platform acts as an **ARC Client** and needs to:

1. **Track conversations with multiple agents**
   - User might talk to Agent A, then Agent B, then back to Agent A
   - Need to remember which `chat_id` belongs to which agent

2. **Maintain user context**
   - Which agents are active in current session
   - Workflow/trace IDs for debugging

3. **Handle session lifecycle**
   - Start conversations on user request
   - Resume conversations automatically
   - Clean up on disconnect

---

### Client Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Platform (ARC Client)                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         WebSocket Session (Per User)                │    │
│  │                                                      │    │
│  │  User Message                                       │    │
│  │       ↓                                             │    │
│  │  ThreadManager (in-memory)                         │    │
│  │  {                                                  │    │
│  │    "agent-A": "chat-123",                          │    │
│  │    "agent-B": "chat-456"                           │    │
│  │  }                                                  │    │
│  │       ↓                                             │    │
│  │  ARCClient.chat.start() or .message()             │    │
│  │       ↓                                             │    │
│  └──────────────────────────────────────────────────────┘    │
│                      ↓                                        │
│              ARC Protocol (HTTP/HTTPS)                        │
│                      ↓                                        │
└──────────────────────────────────────────────────────────────┘
```

---

### What We Provide: ThreadManager

**Purpose:** Automatic thread ID management for client sessions

**Key Features:**
- ✅ Per-session in-memory storage (WebSocket scope)
- ✅ Automatic `chat.start` vs `chat.message` selection
- ✅ Automatic cleanup on disconnect
- ✅ Thread reuse across multiple messages

**Developer Usage:**

```python
# Initialize once per WebSocket connection
arc_client = Client(endpoint="...", token="...")
thread_manager = ThreadManager(arc_client)

# Send message - ThreadManager handles everything
response = await thread_manager.send_message(
    target_agent="agent-A",
    message=user_message
)
# First time: calls chat.start, stores chat_id
# Next time: calls chat.message, reuses chat_id

# On disconnect
await thread_manager.end_all_chats()
```

---

### What Developers Must Do

#### 1. WebSocket Handler Integration

**You provide:**
- WebSocket connection handling
- User authentication/authorization
- Connection lifecycle management

**Pattern:**

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Create per-connection instances
    arc_client = Client(...)
    thread_manager = ThreadManager(arc_client)
    
    try:
        while True:
            data = await websocket.receive_json()
            response = await thread_manager.send_message(...)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        # Cleanup automatically
        await thread_manager.end_all_chats()
```

---

## Server-Side State Management (Agents)

### What the Agent Server Manages

The Agent acts as an **ARC Server** and needs to:

1. **Map ARC chat_id to framework thread_id**
   - ARC protocol uses `chat_id`
   - Framework (LangChain, etc.) uses its own `thread_id`
   - Need mapping to link them

2. **Track conversation status**
   - Which chats are ACTIVE vs CLOSED
   - When to clean up old conversations

3. **Store metadata (flexible, no enforced structure)**
   - Common: Framework type, thread references
   - Optional: model info, timestamps, user IDs, session data
   - Store whatever your framework/application needs

---

### Server Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    Agent (ARC Server)                          │
│                                                                 │
│  ARC Request (chat_id)                                         │
│        ↓                                                        │
│  ┌──────────────────────────────────────────────────┐         │
│  │            ChatManager                            │         │
│  │                                                   │         │
│  │  chat_id → metadata {                            │         │
│  │    "framework": "langchain",                     │         │
│  │    "framework_thread_id": "thread-xyz"           │         │
│  │  }                                                │         │
│  └──────────────────────────────────────────────────┘         │
│        ↓                                                        │
│  Extract thread_id                                             │
│        ↓                                                        │
│  ┌──────────────────────────────────────────────────┐         │
│  │         Framework Storage                        │         │
│  │                                                   │         │
│  │  LangChain Checkpointer                          │         │
│  │  thread_id → {state, messages, ...}              │         │
│  │                                                   │         │
│  │         OR                                        │         │
│  │                                                   │         │
│  │  LlamaIndex Memory                               │         │
│  │  thread_id → ChatMemoryBuffer                    │         │
│  └──────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────┘
```

---

### What We Provide: ChatManager + Storage

**Purpose:** Manage chat_id ↔ framework_thread_id mappings

**Key Features:**
- ✅ Dual-write: RAM (fast) + Persistent storage
- ✅ Multiple storage backends (Redis, PostgreSQL, MongoDB)
- ✅ 24-hour retention for closed chats
- ✅ Automatic/manual cleanup (depends on storage)

**What ChatManager Stores:**

```python
{
    "chatId": "chat-abc123",          # ARC identifier
    "status": "ACTIVE",                # ACTIVE or CLOSED
    "targetAgent": "requesting-agent", # Who initiated
    "metadata": {                      # ✅ Open structure - store anything you need!
        "framework": "langchain",      # Example: framework type
        "framework_thread_id": "thread-xyz789",  # Example: thread reference
        # Add any fields your application needs:
        # "user_id": "user-123", "model": "gpt-4", etc.
    },
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-01-01T00:00:05Z"
}
```

**What ChatManager Does NOT Store:**
- ❌ Messages (framework handles this)
- ❌ Conversation state (framework handles this)
- ❌ User data (not needed on server side)

---

### What Developers Must Do

#### 1. Initialize ChatManager with Storage

**Choose storage backend:**

```python
# Option A: Redis (automatic TTL)
redis_client = redis.Redis(host="...", password="...")
storage = RedisChatStorage(redis_client)

# Option B: PostgreSQL (manual cleanup)
db_pool = await asyncpg.create_pool(...)
storage = PostgreSQLChatStorage(db_pool)
await storage.initialize_schema()

# Option C: MongoDB (TTL index)
mongo_db = AsyncIOMotorClient(...).my_database
storage = MongoChatStorage(mongo_db)
await storage.initialize_indexes()

# Create ChatManager
chat_manager = ChatManager(agent_id="my-agent", storage=storage)
```

#### 2. Handle chat.start - Create Mapping

**Pattern:**

```python
@server.agent_handler("my-agent")
async def handle_chat_start(params, context):
    # Step 1: Extract chat_id (client may provide, or generate)
    chat_id = params.get("chatId") or f"chat-{uuid.uuid4().hex[:8]}"
    
    # Step 2: Create framework thread_id
    framework_thread_id = str(uuid.uuid4())
    
    # Step 3: Store mapping in ChatManager
    chat_manager = context["chat_manager"]
    await chat_manager.create_chat(
        target_agent=context["request_agent"],
        chat_id=chat_id,
        metadata={"framework_thread_id": framework_thread_id}
    )
    
    # Step 4: Use thread_id with your framework
    config = {"configurable": {"thread_id": framework_thread_id}}
    result = my_agent.invoke(params["initialMessage"], config=config)
    
    return arc_response
```

#### 3. Handle chat.message - Retrieve Mapping

**Pattern:**

```python
@server.agent_handler("my-agent")
async def handle_chat_message(params, context):
    # Step 1: Get mapping from ChatManager
    chat_manager = context["chat_manager"]
    chat = await chat_manager.get_chat(params["chatId"])
    framework_thread_id = chat["metadata"]["framework_thread_id"]
    
    # Step 2: Framework automatically loads state using thread_id
    config = {"configurable": {"thread_id": framework_thread_id}}
    result = my_agent.invoke(params["message"], config=config)
    
    return arc_response
```

#### 4. Handle chat.end - Mark as Closed

**Pattern:**

```python
@server.agent_handler("my-agent")
async def handle_chat_end(params, context):
    # Mark as closed (sets 24h TTL)
    chat_manager = context["chat_manager"]
    await chat_manager.close_chat(params["chatId"], reason=params.get("reason"))
    
    # Optional: Clean up framework storage
    # (depends on your framework's cleanup strategy)
    
    return arc_response
```

#### 5. Optional: Periodic Cleanup

**For PostgreSQL only (Redis/MongoDB auto-cleanup):**

```python
# Run as cron job or scheduled task
async def cleanup_job():
    await chat_manager.cleanup_old_chats(max_age_seconds=86400)
```

---

## Storage Options

### Client-Side (Platform)

| Option | Use Case | Pros | Cons |
|--------|----------|------|------|
| **In-Memory (WebSocket scope)** | Most platforms (recommended) | ✅ Simple<br>✅ Fast<br>✅ Auto-cleanup on disconnect | ❌ Lost on disconnect<br>❌ No cross-session history |

**Recommendation:** Use in-memory (ThreadManager default) - it's simple and matches WebSocket session lifecycle.

---

### Server-Side (Agent)

| Storage | TTL Handling | Best For |
|---------|--------------|----------|
| **Redis** | ✅ Automatic | High-performance, stateless agents |
| **PostgreSQL** | ⚠️ Manual cleanup needed | Relational queries, structured data |
| **MongoDB** | ✅ Automatic (TTL index) | Flexible schema, document-based |

**Recommendation:**
- **Redis:** If you want automatic cleanup and high performance
- **PostgreSQL:** If you need complex queries or existing PostgreSQL infrastructure
- **MongoDB:** If you prefer document storage and automatic TTL

---

## Framework Integration

### How Different Frameworks Store State

#### LangChain (Checkpointer)

**Framework handles:**
- State graphs
- Message history
- Intermediate steps
- Checkpoints

**Your integration:**

```python
from langgraph.checkpoint.memory import MemorySaver

# Framework's checkpointer
checkpointer = MemorySaver()
agent = create_react_agent(model, tools, checkpointer=checkpointer)

# Use ARC chat_id as thread_id OR create separate thread_id
framework_thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": framework_thread_id}}

# LangChain stores/loads state automatically
result = agent.invoke(input, config=config)
```

---

#### LlamaIndex (Memory)

**Framework handles:**
- Chat memory buffer
- Message history
- Token limits

**Your integration:**

```python
from llama_index.core.memory import ChatMemoryBuffer

# Store memory per thread_id
memories = {}  # {framework_thread_id: ChatMemoryBuffer}

# On chat.start
framework_thread_id = str(uuid.uuid4())
memories[framework_thread_id] = ChatMemoryBuffer.from_defaults()

# On chat.message
memory = memories[framework_thread_id]
agent = OpenAIAgent.from_tools(tools, memory=memory)
result = agent.chat(message)
```

---

#### Custom Framework

**If you build your own:**

```python
# Store whatever state your framework needs
framework_storage = {
    framework_thread_id: {
        "messages": [...],
        "context": {...},
        "custom_state": {...}
    }
}

# On each message, load and save state
state = framework_storage[framework_thread_id]
new_state = process_message(message, state)
framework_storage[framework_thread_id] = new_state
```

---

## Best Practices

### Client-Side (Platform)

#### ✅ DO

1. **Create ThreadManager per WebSocket connection**
   ```python
   # Good: Isolated per user
   @app.websocket("/ws")
   async def handler(websocket):
       thread_manager = ThreadManager(arc_client)
   ```

2. **Always call `end_all_chats()` on disconnect**
   ```python
   except WebSocketDisconnect:
       await thread_manager.end_all_chats()
   ```

3. **Use trace IDs for debugging**
   ```python
   await thread_manager.send_message(
       target_agent="...",
       message=...,
       trace_id=workflow_id  # Track conversations
   )
   ```

#### ❌ DON'T

1. **Don't share ThreadManager across users**
   ```python
   # Bad: Global ThreadManager
   global_thread_manager = ThreadManager(...)  # ❌
   ```

2. **Don't forget cleanup**
   ```python
   # Bad: No cleanup on disconnect
   except WebSocketDisconnect:
       pass  # ❌ Leaves open chats
   ```

---

### Server-Side (Agent)

#### ✅ DO

1. **Use persistent storage in production**
   ```python
   # Good: Survives server restart
   storage = RedisChatStorage(redis_client)
   chat_manager = ChatManager(agent_id="...", storage=storage)
   ```

2. **Store framework_thread_id in metadata**
   ```python
   # Good: Clear reference
   metadata = {
       "framework": "langchain",
       "framework_thread_id": thread_id,
       "model": "gpt-4"  # Optional metadata
   }
   ```

3. **Handle chat.end properly**
   ```python
   # Good: Mark as closed
   await chat_manager.close_chat(chat_id, reason=reason)
   ```

4. **Use try/except for framework errors**
   ```python
   try:
       result = agent.invoke(...)
   except FrameworkError as e:
       # Handle framework-specific errors
       await chat_manager.close_chat(chat_id, reason=str(e))
       raise
   ```

#### ❌ DON'T

1. **Don't store messages in ChatManager**
   ```python
   # Bad: ChatManager is not for messages
   await chat_manager.add_message(...)  # ❌ Method removed
   ```

2. **Don't forget to map thread_id**
   ```python
   # Bad: No mapping stored
   thread_id = uuid.uuid4()
   result = agent.invoke(...)  # ❌ Can't retrieve thread_id later
   ```

3. **Don't use in-memory storage in production**
   ```python
   # Bad: Lost on restart
   chat_manager = ChatManager(agent_id="...", storage=None)  # ❌
   ```

---

## Complete Flow Example

### End-to-End Conversation

```
1. User sends message to Platform
   ↓
2. Platform: ThreadManager.send_message("agent-A", message)
   ↓
3. ThreadManager: No chat_id for agent-A → call chat.start
   ↓
4. ARC Protocol: HTTP POST /arc with chat.start
   ↓
5. Agent Server receives chat.start
   ↓
6. Agent: Creates framework_thread_id = "thread-xyz"
   ↓
7. Agent: ChatManager stores mapping: chat-123 → thread-xyz
   ↓
8. Agent: LangChain loads/creates state for thread-xyz
   ↓
9. Agent: Processes message, LangChain saves state to thread-xyz
   ↓
10. Agent: Returns ARC response with chat_id=chat-123
    ↓
11. Platform: ThreadManager stores agent-A → chat-123
    ↓
12. Platform: Returns response to user

--- User sends another message ---

13. Platform: ThreadManager.send_message("agent-A", message)
    ↓
14. ThreadManager: Has chat_id for agent-A → call chat.message
    ↓
15. ARC Protocol: HTTP POST /arc with chat.message(chat-123)
    ↓
16. Agent: ChatManager retrieves thread-xyz for chat-123
    ↓
17. Agent: LangChain loads state from thread-xyz
    ↓
18. Agent: Processes with context, saves updated state
    ↓
19. Agent: Returns response
    ↓
20. Platform: Returns to user
```

---

## Summary

### Client-Side (Platform)
- **Use:** `ThreadManager` for automatic thread management
- **Storage:** In-memory (WebSocket scope) for most cases
- **Your job:** WebSocket handling, user auth, cleanup on disconnect

### Server-Side (Agent)
- **Use:** `ChatManager` + Storage for chat_id ↔ thread_id mapping
- **Storage:** Redis (auto-cleanup) or PostgreSQL/MongoDB (your choice)
- **Your job:** Framework integration, handle chat.start/message/end, cleanup

### Framework Storage
- **LangChain:** Uses checkpointer, automatically handles state
- **LlamaIndex:** Uses memory objects, you manage per thread_id
- **Custom:** You decide how to store/load state

### Key Principle
**Two separate systems, linked by references:**
- Platform ↔ Agents: Linked by `chat_id`
- Agents ↔ Frameworks: Linked by `thread_id`
- Each system stores what it needs, nothing more

---

## Need Help?

- **Client examples:** `examples/client/thread_manager_example.py`
- **Server examples:** `examples/server/chat_*_example.py`
- **API Reference:** See SDK documentation
- **Issues:** GitHub issues for bug reports/questions

