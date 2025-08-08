# Agent Remote Communication (ARC) Protocol - Multi-Agent Communication Revolution

[![PyPI version](https://badge.fury.io/py/arc-sdk.svg)](https://badge.fury.io/py/arc-sdk)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/arc-sdk)](https://pepy.tech/project/arc-sdk)
[![GitHub stars](https://img.shields.io/github/stars/arcprotocol/python-sdk.svg?style=social&label=Star)](https://github.com/arcprotocol/python-sdk)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🚀 **World's First Multi-Agent RPC Protocol**

> **ARC (Agent Remote Communication)** is the first RPC protocol that solves multi-agent deployment complexity with built-in agent routing, load balancing, and workflow tracing. Deploy hundreds of different agent types on a single endpoint with zero infrastructure overhead.

### **🎯 Revolutionary Multi-Agent Features:**
- **🏗️ Single Endpoint, Multiple Agents** - Deploy 10s or 100s of agents behind `https://company.com/arc`
- **⚖️ Built-in Load Balancing** - Route to `finance-agent-01`, `finance-agent-02`, `finance-agent-03` automatically  
- **🔄 Cross-Agent Workflows** - Agent A → Agent B → Agent C with full traceability via `traceId`
- **📡 Unified Agent Management** - No service discovery, no API gateways, no orchestration engines required
- **🔍 End-to-End Tracing** - Track complex workflows across multiple agent interactions
- **⚡ Zero Infrastructure Overhead** - Single deployment handles all agent types

### **🆚 Why ARC vs Others:**

| Feature | ARC | JSON-RPC 2.0 | gRPC | REST |
|---------|-----|---------------|------|------|
| **Agent Routing** | ✅ Built-in | ❌ Manual | ❌ Manual | ❌ Manual |
| **Workflow Tracing** | ✅ Native | ❌ Custom | ⚠️ External | ❌ Custom |
| **Multi-Agent Ready** | ✅ First-class | ❌ DIY | ❌ DIY | ❌ DIY |
| **Load Balancing** | ✅ Protocol-level | ❌ External | ❌ External | ❌ External |
| **Learning Curve** | ✅ Simple | ✅ Simple | ❌ Complex | ✅ Simple |

## 📦 **Quick Start**

### Installation

```bash
pip install arc-sdk
```

### 🔥 **30-Second Multi-Agent Demo**

```python
from arc import ARCClient

# Create ARC client
client = ARCClient("https://company.com/arc", token="your-oauth2-token")

# Step 1: User requests document analysis
task_response = await client.task.create(
    target_agent="document-analyzer-01",
    initial_message={"role": "user", "parts": [{"type": "TextPart", "content": "Analyze quarterly report"}]},
    trace_id="workflow_quarterly_report_789"  # 🔍 Workflow tracking
)

# Step 2: Document agent automatically calls chart generator
chart_response = await client.task.create(
    target_agent="chart-generator-01", 
    initial_message={"role": "agent", "parts": [{"type": "DataPart", "content": "{\"revenue\": 1000000}"}]},
    trace_id="workflow_quarterly_report_789"  # 🔍 Same workflow ID!
)

# Step 3: Real-time chat with customer support agent
chat = await client.chat.start(
    target_agent="support-agent-01",
    initial_message={"role": "user", "parts": [{"type": "TextPart", "content": "Help with account"}]}
)
```

### 🏗️ **Architecture: Single Endpoint, Infinite Agents**

```
https://company.com/arc  ← Single endpoint for everything
├── finance-analyzer-01, finance-analyzer-02    (Load balanced)
├── document-processor-03, document-processor-04
├── chart-generator-05
├── customer-support-06
└── report-writer-07
```

## 🎯 **Core Methods - Simple but Powerful**

### **📋 Task Methods (Asynchronous)**
Perfect for long-running operations like document analysis, report generation:

```python
# Create task
task = await client.task.create(target_agent="doc-analyzer", initial_message=msg)

# Send additional input (when agent needs more info)
await client.task.send(task_id="task-123", message=additional_msg)

# Get results
result = await client.task.get(task_id="task-123")

# Cancel if needed
await client.task.cancel(task_id="task-123")

# Subscribe to notifications
await client.task.subscribe(task_id="task-123", webhook_url="https://myapp.com/hooks")
```

### **💬 Chat Methods (Real-time)**
Perfect for interactive chat, live assistance, collaborative editing:

```python
# Start real-time conversation
chat = await client.chat.start(target_agent="chat-agent", initial_message=msg)

# Continue conversation
await client.chat.message(chat_id="chat-456", message=followup_msg)

# End when done
await client.chat.end(chat_id="chat-456")
```

### **🔔 Notification Methods (Server-initiated)**
Agents push updates back automatically:

```python
# Agents send task progress notifications
await client.task.notification(task_id="task-123", event="TASK_COMPLETED", data={...})

# Agents can stream real-time responses
await client.chat.message(chat_id="chat-456", message=response_msg, stream=True)
```

## 🔐 **Enterprise Security & OAuth2**

ARC uses industry-standard OAuth2 with agent-specific scopes:

```python
# Requesting agents (initiate work)
scopes = ["arc.task.controller", "arc.chat.controller", "arc.agent.caller"]

# Processing agents (receive work, send notifications)  
scopes = ["arc.task.notify", "arc.chat.receiver", "arc.agent.receiver"]

# Full-service agents (can do both)
scopes = ["arc.task.controller", "arc.task.notify", "arc.chat.controller", "arc.chat.receiver", "arc.agent.caller", "arc.agent.receiver"]
```

## 🌟 **Real-World Examples**

### **📊 Multi-Agent Financial Analysis**
```python
# Router agent orchestrates entire workflow
trace_id = "financial_analysis_Q4_2024"

# 1. Extract data from documents
doc_task = await client.task.create(
    target_agent="document-extractor-01",
    initial_message={"role": "user", "parts": [{"type": "FilePart", "content": "base64pdf..."}]},
    trace_id=trace_id
)

# 2. Generate charts from extracted data  
chart_task = await client.task.create(
    target_agent="chart-generator-01",
    initial_message={"role": "agent", "parts": [{"type": "DataPart", "content": extracted_data}]},
    trace_id=trace_id  # Same workflow!
)

# 3. Write executive summary
summary_task = await client.task.create(
    target_agent="report-writer-01", 
    initial_message={"role": "agent", "parts": [{"type": "TextPart", "content": "Create summary"}]},
    trace_id=trace_id  # All connected!
)
```

### **🎧 Real-time Customer Support**
```python
# Start customer conversation
support_chat = await client.chat.start(
    target_agent="tier1-support-agent",
    initial_message={"role": "user", "parts": [{"type": "TextPart", "content": "My account is locked"}]}
)

# Agent can escalate to specialist
if needs_escalation:
    specialist_chat = await client.chat.start(
        target_agent="account-security-specialist", 
        initial_message={"role": "agent", "parts": [{"type": "TextPart", "content": "Escalated case: account lockout"}]}
    )
```

## 🏢 **Production Deployment**

### **Docker Deployment**
```yaml
# docker-compose.yml
version: '3.8'
services:
  arc-gateway:
    image: arc-protocol/gateway:latest
    ports:
      - "443:443"
    environment:
      - ARC_OAUTH2_PROVIDER=https://auth.company.com
      - ARC_AGENT_REGISTRY=https://registry.company.com
      
  document-analyzer:
    image: company/document-analyzer:latest
    environment:
      - ARC_ENDPOINT=https://gateway/arc
      - ARC_AGENT_ID=document-analyzer-01
```

### **Load Balancing**
```python
# Multiple instances automatically load balanced
agents = [
    "finance-analyzer-01",
    "finance-analyzer-02", 
    "finance-analyzer-03"
]

# ARC automatically routes to available instance
task = await client.task.create(
    target_agent="finance-analyzer-01",  # ARC handles routing
    initial_message=analysis_request
)
```

## 📚 **Documentation**

- 📖 **[Full Documentation](https://docs.arc-protocol.org)**
- 🔧 **[API Reference](https://docs.arc-protocol.org/api)**
- 📋 **[Protocol Specification](https://arc-protocol.org/spec)**
- 🎯 **[Examples Repository](https://github.com/arcprotocol/examples)**

## 🤝 **Contributing**

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 **License**

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

---

**🚀 Ready to revolutionize your multi-agent architecture?**

```bash
pip install arc-sdk
```

**Join the ARC Protocol community:** [https://arc-protocol.org](https://arc-protocol.org)
