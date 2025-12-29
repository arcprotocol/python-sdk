# Platform-Agent Architecture Design

## Overview

This document describes the architecture for a multi-agent platform where users interact with a main platform agent that can dynamically route requests to specialized external agents using the ARC (Agent Remote Communication) Protocol.

---

## Section 1: Architecture Components

### 1.1 System Architecture Diagram

```
┌─────────────────┐
│  User Browser   │
└────────┬────────┘
         │
         │ WebSocket (Persistent Connection)
         │
┌────────▼─────────────────────────────────────┐
│          PLATFORM (Dual Role)                │
│                                              │
│  Role 1: WebSocket Server                   │
│    - Receives connections from users        │
│    - Maintains session per user             │
│    - Hosts main agent per session           │
│                                             │
│  Role 2: ARC Protocol Client                │
│    - Initiates requests to external agents  │
│    - Manages thread mappings per session    │
│    - Handles agent discovery & routing      │
└────────┬─────────────────────────────────────┘
         │
         │ ARC Protocol (HTTPS/RPC - Stateless)
         │ POST /arc
         │
    ┌────┴────┬────────┬────────┐
    │         │        │        │
┌───▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐
│Agent A│ │Agent B│ │Agent C│ │Agent N│
│(FastAPI│ │(FastAPI│ │(FastAPI│ │(FastAPI│
│SERVER)│ │SERVER)│ │SERVER)│ │SERVER)│
│       │ │       │ │       │ │       │
│Receives│ │Receives│ │Receives│ │Receives│
│on /arc │ │on /arc │ │on /arc │ │on /arc │
│HTTP/   │ │HTTP/   │ │HTTP/   │ │HTTP/   │
│HTTPS   │ │HTTPS   │ │HTTPS   │ │HTTPS   │
└───────┘ └──────┘ └──────┘ └──────┘
```

---

### 1.2 Component Details

#### **Platform (CLIENT Role)**

**Primary Function:** Acts as ARC Protocol client, initiating connections to external agents

**Key Characteristics:**
- **Connection Type:** HTTPS/RPC (stateless requests)
- **Initiation:** Platform ALWAYS initiates
- **Protocol:** ARC Protocol for agent-to-agent communication
- **State Management:** In-memory storage (session-scoped)
- **Endpoint:** Makes POST requests to agent's `/arc` endpoint

**Responsibilities:**

1. **Agent Discovery & Routing**
   - Maintains agent registry (list of available agents and capabilities)
   - Determines which external agent to contact based on user query
   - Routes requests to appropriate specialized agents

2. **Thread Management (Client-Side)**
   - For each user session, maintains mapping: `{agent_id: thread_id}`
   - When contacting an agent for first time: calls `chat.start()`, stores returned `chat_id`
   - For subsequent messages to same agent: reuses stored `chat_id` with `chat.message()`
   - Mapping lives in WebSocket session scope (in-memory)

3. **Request Lifecycle**
   - Receives user query via WebSocket
   - Main agent determines if external agent needed
   - Looks up existing thread or creates new one
   - Sends ARC request to external agent
   - Receives response
   - Relays to user via WebSocket

4. **Cleanup on Disconnect**
   - When user WebSocket disconnects
   - Iterates through all agent mappings
   - Sends `chat.end()` to each contacted agent
   - Allows external agents to clean up their persistent storage

**Storage Strategy:**
- ✅ **In-memory storage** (WebSocket session scope)
- ❌ **No persistent storage needed**
- **Rationale:** Mappings are scoped to user's WebSocket session, naturally isolated per user, automatically cleaned up on disconnect

---

#### **External Agents (SERVERS)**

**Primary Function:** Specialized agents that receive and process ARC protocol requests

**Key Characteristics:**
- **Connection Type:** HTTP/HTTPS (stateless, request-response)
- **Framework:** FastAPI as ASGI server
- **Protocol:** ARC Protocol (receives `chat.start`, `chat.message`, `chat.end`)

**Responsibilities:**

1. **Request Processing**
   - Receives ARC protocol requests from Platform
   - Validates request format
   - Processes based on method (`chat.start`, `chat.message`, etc.)

2. **Conversation State Management**
   - Maintains conversation history per `chat_id`
   - Must persist state between stateless HTTP requests
   - Looks up conversation context for each request

3. **Response Generation**
   - Processes user query within conversation context
   - Generates response based on specialization
   - Returns ARC-compliant response

4. **Cleanup Handling**
   - Receives `chat.end()` from Platform on user disconnect
   - Removes conversation data from persistent storage
   - Implements TTL backup cleanup for orphaned conversations

**Storage Strategy:**
- ✅ **Persistent storage REQUIRED** (Redis, PostgreSQL, etc.)
- ❌ **In-memory storage insufficient**
- **Rationale:** 
  - HTTP requests are stateless
  - Each request is a new connection
  - No persistent connection to Platform
  - Must look up conversation state for each request using `chat_id`

**Why Persistent Storage is Necessary:**
1. Each ARC request is independent HTTP call
2. Agent must retrieve conversation history for `chat_id`
3. No way to maintain state between requests otherwise
4. Multiple platform instances may send requests
5. Agent may restart but conversations must persist

---

### 1.3 ARC Protocol Communication

| Aspect | Platform (CLIENT) | External Agents (SERVERS) |
|--------|-------------------|---------------------------|
| **Protocol** | ARC via HTTPS | ARC via HTTPS |
| **Connection** | Stateless (per request) | Stateless (per request) |
| **Endpoint** | Makes POST to `/arc` | Receives POST on `/arc` |
| **Framework** | Any (Python, Node, etc.) | FastAPI (ASGI) |
| **Initiates** | ✅ Always | ❌ Never |
| **State Storage** | In-memory (session scope) | Persistent (DB/Redis) |
| **Isolation** | Session-scoped variables | Must key by chat_id |
| **Cleanup** | Sends chat.end() on session end | Receives chat.end(), removes from DB |

---

### 1.4 Communication Flows

#### **Flow 1: First Contact with External Agent**

```
1. Platform determines need to consult Agent A
2. Platform checks session mapping: Agent A not contacted yet
3. Platform → POST /arc {method: "chat.start"} → Agent A
4. Agent A: Creates conversation, stores in DB, returns chat_id="thread-123"
5. Platform: Stores {agent-A: thread-123} in session mapping
6. Agent A → Response with chat_id → Platform
```

**Storage Changes:**
- Platform: `{agent-A: thread-123}` in session memory
- Agent A: `thread-123` conversation in persistent DB

---

#### **Flow 2: Subsequent Contact with Same Agent**

```
1. Platform needs to consult Agent A again
2. Platform checks mapping: Found {agent-A: thread-123}
3. Platform → POST /arc {method: "chat.message", chat_id: "thread-123"} → Agent A
4. Agent A: Looks up thread-123 in DB, retrieves context
5. Agent A: Processes in context of previous conversation
6. Agent A → Response → Platform
```

**Storage Access:**
- Platform: Reads `thread-123` from session memory
- Agent A: Reads conversation history from DB using `thread-123`

---

#### **Flow 3: Session End - Cleanup**

```
1. Platform session ends (user disconnect, timeout, etc.)
2. Platform: Iterates through session mappings:
   - {agent-A: thread-123}
   - {agent-B: thread-456}
3. Platform → POST /arc {method: "chat.end", chat_id: "thread-123"} → Agent A
4. Agent A: Removes thread-123 from DB
5. Platform → POST /arc {method: "chat.end", chat_id: "thread-456"} → Agent B
6. Agent B: Removes thread-456 from DB
7. Platform: Session scope ends, mappings garbage collected
```

**Storage Changes:**
- Platform: Session destroyed, all mappings gone
- Agent A: `thread-123` removed from DB
- Agent B: `thread-456` removed from DB

**Result:** Clean state everywhere, no orphaned data

---

## Section 2: Design & Architecture Decisions

### 2.1 Core Design Principles

#### **Principle 1: Explicit Context Ownership**

**Decision:** Client (Platform) owns and manages conversation context

**Rationale:**
- Platform initiates all conversations
- Platform knows when user starts/ends session
- Platform has full context of user's interaction flow
- Agents are stateless services focused on processing

**Implementation:**
- Platform stores `{agent_id: chat_id}` mappings per session
- Platform provides `chat_id` in every request to agent
- Agents don't need to track which platform/user initiated

---

#### **Principle 2: Separation of Concerns**

**Client Responsibilities (Platform):**
- User session management
- Agent discovery and routing
- Thread lifecycle (start, reuse, end)
- Mapping storage (session-scoped)

**Server Responsibilities (External Agents):**
- Request processing
- Conversation state persistence
- Specialized task execution
- Response generation

**Not Mixed:**
- Agents don't manage user sessions
- Platform doesn't manage agent internal state
- Clear boundaries via ARC protocol

---

#### **Principle 3: Storage Matches Connection Type**

**WebSocket Connection (Persistent):**
- Storage: In-memory, connection-scoped
- Rationale: Connection stays open, provides natural boundary
- Cleanup: Automatic on disconnect

**HTTP Connection (Stateless):**
- Storage: Persistent (Redis/Database)
- Rationale: Each request is independent, must externalize state
- Cleanup: Explicit via chat.end() + TTL backup

**Why This Matters:**
- Choosing wrong storage for connection type causes issues
- In-memory for stateless = lost state
- Persistent for connection-scoped = unnecessary complexity

---

#### **Principle 4: Graceful Cleanup with Degradation**

**Primary Cleanup Mechanism:**
- WebSocket disconnect triggers `chat.end()` to all contacted agents
- Agents immediately remove conversation data
- Both sides synchronized

**Backup Mechanisms:**
1. **Agent-side TTL:** Conversations expire after inactivity (1-2 hours)
2. **Background cleanup jobs:** Periodically scan for abandoned conversations
3. **Logging:** Track cleanup failures for monitoring

**Rationale:**
- Network failures happen
- Agents may be temporarily down
- Best-effort cleanup + safety nets prevent accumulation

---

### 2.2 Thread Management Strategy

#### **Client-Side (Platform) Mapping**

**Structure:**
```
Per WebSocket Session:
  agent_mappings = {
    "agent-A": "chat-abc123",
    "agent-B": "chat-xyz789",
    "agent-C": "chat-def456"
  }
```

**Lifecycle:**
1. Session starts → Empty mapping
2. First contact with agent → `chat.start()`, store chat_id
3. Subsequent contacts → Look up chat_id, use `chat.message()`
4. Session ends → Send `chat.end()` to all, destroy mapping

**Advantages:**
- Simple dictionary lookup (O(1))
- No database queries needed
- Automatic cleanup on disconnect
- Natural per-user isolation

---

#### **Server-Side (Agent) Storage**

**Structure (Conceptual):**
```
Persistent Storage:
  chat-abc123 → {
    user_context: "...",
    conversation_history: [...],
    created_at: timestamp,
    last_activity: timestamp
  }
```

**Lifecycle:**
1. Receive `chat.start()` → Create entry, return chat_id
2. Receive `chat.message(chat_id)` → Look up entry, process, update
3. Receive `chat.end(chat_id)` → Remove entry
4. TTL cleanup → Remove old entries not explicitly ended

**Storage Options:**
- **Redis:** Fast, TTL built-in, distributed
- **PostgreSQL/MySQL:** Durable, queryable, transactional
- **MongoDB:** Flexible schema, document-based

**Choice Factors:**
- Speed requirements
- Durability needs
- Query complexity
- Infrastructure existing

---

### 2.3 Routing & Agent Discovery

#### **Agent Registry**

**Purpose:** Platform maintains list of available agents and capabilities

**Information Tracked:**
- Agent ID
- Agent endpoint URL
- Capabilities/specializations
- Health status
- Response time metrics

**Discovery Flow:**
1. User query received
2. Main agent analyzes query intent
3. Determines capability needed (e.g., "financial analysis")
4. Queries registry for agents with that capability
5. Selects best agent (based on availability, load, performance)
6. Routes request to selected agent

**Registry Storage:**
- Could be static configuration
- Could be dynamic service discovery
- Could include health checking

---

### 2.4 Multi-Context Support (Future Enhancement)

**Current Design:** Single mapping per agent

**Structure:**
```
agent_mappings = {
  "agent-A": "chat-123"
}
```

**Limitation:** Only one active conversation per agent per user

---

**Enhanced Design:** Context-aware mapping

**Structure:**
```
context_mappings = {
  "workflow-123": {
    "agent-A": "chat-abc",
    "agent-B": "chat-xyz"
  },
  "document-analysis": {
    "agent-A": "chat-def",  # Different thread!
    "agent-C": "chat-ghi"
  }
}
```

**Advantages:**
- User can have multiple concurrent workflows
- Same agent in different contexts = different conversations
- Better context isolation

**Implementation Consideration:**
- Client sends context identifier with each message
- Platform routes based on (context, agent_id) tuple
- More complex cleanup (per-context or all contexts)

---

### 2.5 Error Handling & Resilience

#### **Network Failures**

**Scenario:** Platform can't reach external agent

**Handling:**
1. Timeout on ARC request
2. Retry with exponential backoff (2-3 attempts)
3. If still failing, fallback:
   - Use cached response if available
   - Return error to user
   - Mark agent as unhealthy in registry
4. Log failure for monitoring

---

#### **Agent Unavailability**

**Scenario:** Agent is down or overloaded

**Handling:**
1. Platform detects via timeout or error response
2. Check registry for alternative agents with same capability
3. Route to backup agent if available
4. If no alternatives:
   - Queue request for retry
   - Or return graceful error to user

---

#### **Cleanup Failures**

**Scenario:** chat.end() fails on disconnect

**Handling:**
1. Log failure (which agent, which chat_id)
2. Don't block disconnect
3. Agent's TTL cleanup will eventually remove
4. Monitor for patterns (specific agent always failing?)

---

#### **Partial State**

**Scenario:** Platform crashes mid-session

**Handling:**
1. User's WebSocket disconnects
2. Platform's mappings are lost
3. Agents still have conversation data in DB
4. Agent-side TTL cleanup handles orphaned conversations
5. When user reconnects, new session starts fresh

**Why This is Acceptable:**
- Conversations are naturally bounded (user session)
- TTL cleanup prevents indefinite accumulation
- Fresh start is often desirable anyway

---

### 2.6 Scalability Considerations

#### **Platform Scaling**

**Single Instance:**
- WebSocket sessions managed in-process
- Mappings in process memory
- Simple, works for small scale

**Multiple Instances (Load Balanced):**
- **Issue:** WebSocket connections are sticky to instance
- **Solution:** Load balancer with session affinity
- **Result:** Each user's WebSocket stays with same instance
- **Benefit:** In-memory storage still works

**Horizontal Scaling:**
- Add more Platform instances behind load balancer
- Each handles subset of users
- No shared state needed between instances
- Agent registry could be centralized (Redis/etcd)

---

#### **Agent Scaling**

**Multiple Instances per Agent Type:**
- Multiple instances of "financial-agent"
- Platform routes to any available instance
- Agents use shared persistent storage (Redis cluster)
- Any instance can handle any chat_id

**Load Balancing:**
- Platform tracks agent instance health
- Distributes requests across healthy instances
- Removes unhealthy instances from rotation

---

### 2.7 Security Considerations

#### **Authentication**

**User → Platform:**
- WebSocket authentication on connect
- Token validation
- Session management

**Platform → Agents:**
- OAuth2 bearer tokens in ARC requests
- Agents validate tokens
- Scoped permissions (e.g., `arc.chat.controller`)

---

#### **Authorization**

**User Permissions:**
- What agents can user access?
- Rate limiting per user
- Quota management

**Agent Permissions:**
- What operations can agent perform?
- Which other agents can it call?
- Resource limits

---

#### **Data Privacy**

**Conversation Data:**
- Encrypted in transit (HTTPS/WSS)
- Encrypted at rest (database encryption)
- Retention policies
- GDPR compliance (right to delete)

---

### 2.8 Monitoring & Observability

#### **Key Metrics**

**Platform:**
- Active WebSocket connections
- Agent mappings per session (average, max)
- Request routing decisions
- Cleanup success/failure rates

**Agents:**
- Active conversations (in DB)
- Request processing time
- Error rates
- Storage utilization

**End-to-End:**
- User query to response latency
- Inter-agent call patterns
- Conversation duration distribution

---

#### **Logging**

**Events to Log:**
- User connect/disconnect
- Agent routing decisions
- chat.start/message/end calls
- Cleanup operations
- Errors and retries

**Correlation:**
- User session ID
- Trace ID (across agent calls)
- Chat IDs

---

### 2.9 Testing Strategy

#### **Unit Testing**

**Platform:**
- Agent selection logic
- Mapping management
- Cleanup handlers

**Agents:**
- Request processing
- State persistence/retrieval
- Response generation

---

#### **Integration Testing**

**Scenarios:**
- User session lifecycle
- Multi-agent workflows
- Cleanup on disconnect
- Error handling
- Retry logic

---

#### **Load Testing**

**Test Cases:**
- Concurrent users
- Multiple agents per user
- Long-running sessions
- Disconnect storms
- Agent unavailability

---

## Summary

This architecture provides:

✅ **Clear separation of concerns** between Platform and Agents  
✅ **Appropriate storage strategies** matched to connection types  
✅ **Automatic cleanup** preventing orphaned data  
✅ **Natural isolation** via WebSocket scoping  
✅ **Scalability** through stateless agent design  
✅ **Resilience** via TTL backups and graceful degradation  

The key insight: **Connection type determines storage strategy**
- Persistent connections (WebSocket) → In-memory storage
- Stateless connections (HTTP) → Persistent storage

This creates an elegant, maintainable architecture where each component has clear responsibilities and appropriate state management.

