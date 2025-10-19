#!/usr/bin/env python3
"""
Multi-Agent ARC Server Example

Demonstrates how to create a server with multiple specialized agents:
- Finance Agent: chat.start, chat.message, chat.end (financial queries)
- Support Agent: chat.start, chat.message, chat.end (customer support)  
- Document Agent: task.create, task.info (document processing)
- Analytics Agent: task.create, task.subscribe (data analysis)

Shows how different agents can handle different method sets and specializations.
"""

import asyncio
import uuid
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from arc.server.arc_server import create_server
from arc.server.decorators import validate_params, trace_method, error_handler
from arc.utils.logging import configure_root_logger, create_logger
from arc.server.sse import create_sse_response
from arc.core.streaming import create_chat_stream_generator

# Configure logging
configure_root_logger()
logger = create_logger("multi-agent-server")

# Create multi-agent server with ChatManager
server = create_server(
    server_id="enterprise-server",
    name="Multi-Agent ARC Server",
    version="1.0.0",
    server_description="Enterprise multi-agent server with specialized agents",
    enable_cors=True,
    enable_logging=True,
    enable_chat_manager=True,
    chat_manager_agent_id="enterprise-server"
)

# Finance Agent - Handles financial queries and calculations
@server.agent_handler("finance-agent", "chat.start")
@trace_method
@error_handler
@validate_params()
async def handle_finance_chat_start(params, context):
    """Finance agent chat handler"""
    initial_message = params["initialMessage"]
    chat_id = params.get("chatId", f"finance-chat-{uuid.uuid4().hex[:8]}")
    stream = params.get("stream", False)
    
    # Use ChatManager from context
    chat_manager = context["chat_manager"]
    chat_info = chat_manager.create_chat(
        target_agent=context["request_agent"],
        chat_id=chat_id,
        metadata={"agent_type": "finance", "specialization": "financial_analysis"}
    )
    
    if stream:
        async def finance_content_stream():
            response_parts = [
                "I'm your finance agent. ", "I can help with ", "budgeting, ", 
                "investment analysis, ", "and financial planning. ", 
                "What financial question ", "can I assist you with?"
            ]
            for part in response_parts:
                await asyncio.sleep(0.15)
                yield part
        
        return create_sse_response(create_chat_stream_generator(
            chat_id=chat_id,
            content_generator=finance_content_stream(),
            request_id=context.get("request_id", "unknown")
        ))
    
    # Non-streaming response
    response_text = "I'm your finance agent. I can help with budgeting, investment analysis, and financial planning. What financial question can I assist you with?"
    agent_message = {
        "role": "agent",
        "parts": [{
            "type": "TextPart",
            "content": response_text
        }],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    return {
        "type": "chat",
        "chat": {
            "chatId": chat_id,
            "status": "ACTIVE",
            "createdAt": chat_info["createdAt"],
            "message": agent_message
        }
    }

# Support Agent - Handles customer support queries
@server.agent_handler("support-agent", "chat.start")
@trace_method
@error_handler
@validate_params()
async def handle_support_chat_start(params, context):
    """Support agent chat handler"""
    initial_message = params["initialMessage"]
    chat_id = params.get("chatId", f"support-chat-{uuid.uuid4().hex[:8]}")
    stream = params.get("stream", False)
    
    # Use ChatManager from context
    chat_manager = context["chat_manager"]
    chat_info = chat_manager.create_chat(
        target_agent=context["request_agent"],
        chat_id=chat_id,
        metadata={"agent_type": "support", "specialization": "customer_service"}
    )
    
    if stream:
        async def support_content_stream():
            response_parts = [
                "Hello! I'm your support agent. ", "I'm here to help ", "resolve any issues ", 
                "or answer questions ", "about our services. ", 
                "How can I assist you today?"
            ]
            for part in response_parts:
                await asyncio.sleep(0.12)
                yield part
        
        return create_sse_response(create_chat_stream_generator(
            chat_id=chat_id,
            content_generator=support_content_stream(),
            request_id=context.get("request_id", "unknown")
        ))
    
    # Non-streaming response
    response_text = "Hello! I'm your support agent. I'm here to help resolve any issues or answer questions about our services. How can I assist you today?"
    agent_message = {
        "role": "agent",
        "parts": [{
            "type": "TextPart",
            "content": response_text
        }],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    return {
        "type": "chat",
        "chat": {
            "chatId": chat_id,
            "status": "ACTIVE",
            "createdAt": chat_info["createdAt"],
            "message": agent_message
        }
    }

# Document Agent - Handles document processing tasks
@server.agent_handler("document-agent", "task.create")
@trace_method
@error_handler
@validate_params()
async def handle_document_task_create(params, context):
    """Document agent task creation handler"""
    task_id = f"doc-task-{uuid.uuid4().hex[:8]}"
    initial_message = params["initialMessage"]
    priority = params.get("priority", "NORMAL")
    metadata = params.get("metadata", {})
    
    created_at = datetime.utcnow().isoformat() + "Z"
    
    logger.info(f"Document agent created task {task_id} for document processing")
    
    # Simulate starting background document processing
    asyncio.create_task(process_document_task(task_id))
    
    return {
        "type": "task",
        "task": {
            "taskId": task_id,
            "status": "SUBMITTED",
            "createdAt": created_at,
            "priority": priority,
            "agentType": "document-processing",
            "metadata": metadata
        }
    }

@server.agent_handler("document-agent", "task.info")
@trace_method
@error_handler
@validate_params()
async def handle_document_task_info(params, context):
    """Document agent task info handler"""
    task_id = params["taskId"]
    include_messages = params.get("includeMessages", True)
    include_artifacts = params.get("includeArtifacts", True)
    
    # Mock document processing task info
    mock_task = {
        "taskId": task_id,
        "status": "COMPLETED",
        "createdAt": "2024-01-01T12:00:00Z",
        "updatedAt": "2024-01-01T12:10:00Z",
        "completedAt": "2024-01-01T12:10:00Z",
        "priority": "NORMAL",
        "agentType": "document-processing",
        "messages": [
            {
                "role": "user",
                "parts": [{"type": "TextPart", "content": "Process this PDF document"}],
                "timestamp": "2024-01-01T12:00:00Z"
            },
            {
                "role": "agent",
                "parts": [{"type": "TextPart", "content": "Document processed and analyzed successfully"}],
                "timestamp": "2024-01-01T12:10:00Z"
            }
        ] if include_messages else [],
        "artifacts": [
            {
                "artifactId": f"doc-artifact-{task_id}",
                "name": "Processed Document Analysis",
                "description": "Complete analysis of the processed document",
                "mimeType": "application/json",
                "createdAt": "2024-01-01T12:10:00Z",
                "parts": [{
                    "type": "DataPart",
                    "content": {
                        "wordCount": 1250,
                        "pageCount": 5,
                        "summary": "Document contains financial analysis data",
                        "extractedText": "Sample extracted text..."
                    },
                    "mimeType": "application/json"
                }]
            }
        ] if include_artifacts else [],
        "metadata": {"processingTime": "10s", "confidence": 0.95}
    }
    
    logger.info(f"Document agent retrieved info for task {task_id}")
    
    return {
        "type": "task",
        "task": mock_task
    }

# Analytics Agent - Handles data analysis tasks
@server.agent_handler("analytics-agent", "task.create")
@trace_method
@error_handler
@validate_params()
async def handle_analytics_task_create(params, context):
    """Analytics agent task creation handler"""
    task_id = f"analytics-task-{uuid.uuid4().hex[:8]}"
    initial_message = params["initialMessage"]
    priority = params.get("priority", "HIGH")  # Analytics tasks are high priority
    metadata = params.get("metadata", {})
    
    created_at = datetime.utcnow().isoformat() + "Z"
    
    logger.info(f"Analytics agent created task {task_id} for data analysis")
    
    return {
        "type": "task",
        "task": {
            "taskId": task_id,
            "status": "SUBMITTED",
            "createdAt": created_at,
            "priority": priority,
            "agentType": "data-analytics",
            "metadata": metadata
        }
    }

@server.agent_handler("analytics-agent", "task.subscribe")
@trace_method
@error_handler
@validate_params()
async def handle_analytics_task_subscribe(params, context):
    """Analytics agent task subscription handler"""
    task_id = params["taskId"]
    callback_url = params["callbackUrl"]
    events = params.get("events", ["TASK_COMPLETED", "NEW_ARTIFACT", "ANALYSIS_UPDATE"])
    
    subscription_id = f"analytics-sub-{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat() + "Z"
    
    subscription = {
        "subscriptionId": subscription_id,
        "taskId": task_id,
        "callbackUrl": callback_url,
        "events": events,
        "createdAt": created_at,
        "active": True,
        "agentType": "data-analytics"
    }
    
    logger.info(f"Analytics agent created subscription {subscription_id} for task {task_id}")
    
    return {
        "type": "subscription",
        "subscription": subscription
    }

# Background processing simulation
async def process_document_task(task_id: str):
    """Simulate document processing in background"""
    await asyncio.sleep(2)
    logger.info(f"Document task {task_id} processing started")
    await asyncio.sleep(8)
    logger.info(f"Document task {task_id} processing completed")

# Add chat.message and chat.end handlers for all chat agents
for agent_id in ["finance-agent", "support-agent"]:
    @server.agent_handler(agent_id, "chat.message")
    @trace_method
    @error_handler
    @validate_params()
    async def handle_chat_message(params, context):
        """Generic chat message handler"""
        chat_id = params["chatId"]
        message = params["message"]
        stream = params.get("stream", False)
        
        # Validate chat exists
        chat_manager = context["chat_manager"]
        try:
            chat = chat_manager.get_chat(chat_id)
        except Exception as e:
            raise ValueError(f"Chat not found: {chat_id}")
        
        if stream:
            async def generic_content_stream():
                response_parts = [
                    "I understand ", "your message. ", "Let me help ", 
                    "you with that ", "request."
                ]
                for part in response_parts:
                    await asyncio.sleep(0.1)
                    yield part
            
            return create_sse_response(create_chat_stream_generator(
                chat_id=chat_id,
                content_generator=generic_content_stream(),
                request_id=context.get("request_id", "unknown")
            ))
        
        # Non-streaming response
        response_text = "I understand your message. Let me help you with that request."
        agent_message = {
            "role": "agent",
            "parts": [{
                "type": "TextPart",
                "content": response_text
            }],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return {
            "type": "chat",
            "chat": {
                "chatId": chat_id,
                "status": "ACTIVE",
                "createdAt": chat["createdAt"],
                "message": agent_message
            }
        }
    
    @server.agent_handler(agent_id, "chat.end")
    @trace_method
    @error_handler
    @validate_params()
    async def handle_chat_end(params, context):
        """Generic chat end handler"""
        chat_id = params["chatId"]
        reason = params.get("reason", "Chat ended by user")
        
        # Close chat
        chat_manager = context["chat_manager"]
        try:
            chat_result = chat_manager.close_chat(chat_id, reason)
            logger.info(f"Ended chat {chat_id} with reason: {reason}")
            
            return {
                "type": "chat",
                "chat": chat_result
            }
        except Exception as e:
            raise ValueError(f"Failed to end chat: {e}")

if __name__ == "__main__":
    print(f"Starting Multi-Agent ARC Server")
    print(f"Server ID: enterprise-server")
    print(f"Registered agents:")
    for agent_id, methods in server.agents.items():
        print(f"  - {agent_id}: {', '.join(methods.keys())}")
    print(f"Total agents: {len(server.agents)}")
    print(f"Total methods: {sum(len(methods) for methods in server.agents.values())}")
    print(f"Listening at: http://localhost:8000/arc")
    print(f"Health check: http://localhost:8000/health")
    print(f"Agent info: http://localhost:8000/agent-info")
    print(f"Press Ctrl+C to stop the server")
    server.run(host="0.0.0.0", port=8000)
