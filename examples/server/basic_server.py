#!/usr/bin/env python3
"""
ARC Protocol - Basic Server Example

This example demonstrates how to create a simple ARC server that handles
both task and stream methods. It provides handlers for:

- Task methods: task.create, task.send, task.info
- Stream methods: stream.start, stream.message, stream.chunk, stream.end

To run this example:
1. Configure environment variables (optional)
2. Start this server: python basic_server.py
3. In another terminal, run one of the clients: python ../client/basic_client.py

The server implements OAuth2 authentication but will accept a dev token
for local testing purposes.
"""

import asyncio
import datetime
import json
import logging
import os
import uuid
from typing import Dict, Any, List, Optional

# Import ARC SDK
from arc import ARCServer, RpcContext
from arc.server import method_handler, task_handler, stream_handler
from arc.models.generated import Message, Part, Role, Type
from arc.auth.jwt_validator import JWTValidator, MultiProviderJWTValidator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("arc-example-server")


# Server configuration
SERVER_NAME = "ARC Example Server"
SERVER_VERSION = "1.0.0"
SERVER_AGENT_ID = "arc-example-agent"
SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "False").lower() in ("true", "1", "yes")


# Mock database for storing tasks and streams
mock_db = {
    "tasks": {},
    "streams": {}
}


def generate_mock_response(user_content: str) -> str:
    """Generate a mock AI response based on user input"""
    content_lower = user_content.lower()
    
    if "hello" in content_lower or "hi" in content_lower:
        return "Hello! I'm the ARC Example Server. How can I help you today?"
    elif "database" in content_lower:
        return "I found 3 recent database issues: Connection timeouts (resolved), Index optimization needed, and Backup job failing. Would you like details on any specific issue?"
    elif "search" in content_lower:
        return "I've searched the knowledge base and found several relevant articles. Here are the top 3 results with solutions to similar problems."
    elif "ticket" in content_lower or "issue" in content_lower:
        return "I've created a new ticket #TK-2024-001 and assigned it to the appropriate team. You'll receive updates via email."
    elif "help" in content_lower:
        return "I'm here to help! I can assist with database issues, ticket management, knowledge searches, and general support tasks."
    elif "test" in content_lower:
        return "✅ Test successful! This is a mock response from the ARC Example Server. Everything is working correctly!"
    elif "arc" in content_lower and "protocol" in content_lower:
        return "The ARC (Agent Remote Communication) Protocol is a stateless RPC protocol for multi-agent deployment with built-in agent routing, load balancing, and workflow tracing."
    else:
        return f"I received your message: '{user_content}'. This is a mock response from the ARC Example Server. In a real implementation, I would process your request and provide a meaningful response."


def create_server() -> ARCServer:
    """Create and configure the ARC server"""
    
    # Create server instance with our agent ID
    server = ARCServer(
        agent_id=SERVER_AGENT_ID,
        name=SERVER_NAME,
        version=SERVER_VERSION,
        enable_cors=True,
        enable_logging=True
    )
    
    # Configure JWT validation if enabled
    if ENABLE_AUTH:
        # Try to load JWT validators from environment
        try:
            jwks_urls = os.getenv("JWT_JWKS_URLS", "").split(",")
            issuers = os.getenv("JWT_ISSUERS", "").split(",")
            
            if jwks_urls and issuers and len(jwks_urls) == len(issuers):
                validators = []
                for i, jwks_url in enumerate(jwks_urls):
                    validators.append(
                        JWTValidator(
                            jwks_url=jwks_url.strip(),
                            issuer=issuers[i].strip(),
                            audience=os.getenv("JWT_AUDIENCE", "arc-api")
                        )
                    )
                
                if validators:
                    jwt_validator = MultiProviderJWTValidator(validators)
                    server.use_jwt_validator(jwt_validator)
                    logger.info(f"Configured JWT validation with {len(validators)} providers")
                    
                    # Define required scopes for each method
                    # Each method requires specific scopes
                    server.set_required_scopes("task.create", ["arc.task.controller"])
                    server.set_required_scopes("task.send", ["arc.task.controller"])
                    server.set_required_scopes("task.info", ["arc.task.reader"])
                    server.set_required_scopes("stream.start", ["arc.stream.controller"])
                    server.set_required_scopes("stream.message", ["arc.stream.controller"])
                    server.set_required_scopes("stream.chunk", ["arc.stream.controller"])
                    server.set_required_scopes("stream.end", ["arc.stream.controller"])
                    
                    logger.info("Configured required scopes for all methods")
            else:
                logger.warning("Incomplete JWT configuration, proceeding without authentication")
                
        except Exception as e:
            logger.error(f"Failed to configure JWT validation: {e}")
            logger.warning("Proceeding without authentication")
    else:
        logger.info("Authentication disabled for local testing")
    
    return server


#############################################################
# Task Method Handlers
#############################################################

@task_handler("task.create")
async def handle_task_create(params, context: RpcContext):
    """
    Handle task.create method
    
    This creates a new asynchronous task and returns the initial task object.
    """
    try:
        logger.info(f"Received task creation request from {context.request_agent}")
        
        # Extract the initial message
        initial_message = params.initialMessage
        user_content = ""
        
        # Process text parts from the message
        if initial_message and initial_message.parts:
            for part in initial_message.parts:
                if part.type == Type.text_part:
                    user_content = part.content or ""
                    break
        
        logger.info(f"User message: {user_content[:100]}")
        
        # Generate timestamp and task ID
        now_dt = datetime.datetime.now()
        task_id = f"task-{now_dt.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        # Generate mock response based on content
        ai_response = generate_mock_response(user_content)
        
        # Create agent response message
        agent_message = Message(
            role=Role.agent,
            parts=[Part(
                type=Type.text_part,
                content=ai_response
            )],
            timestamp=now_dt,
            agentId=SERVER_AGENT_ID
        )
        
        # Create task object
        task_obj = {
            "taskId": task_id,
            "status": "completed",
            "createdAt": now_dt,
            "updatedAt": now_dt,
            "assignedAgent": SERVER_AGENT_ID,
            "messages": [initial_message, agent_message],
            "artifacts": [],
            "metadata": {
                "priority": getattr(params, "priority", "normal"),
                "source": "arc_example_server",
                "processed_at": now_dt.isoformat() + "Z",
                **(getattr(params, "metadata", {}) or {})
            }
        }
        
        # Store task in our mock database
        mock_db["tasks"][task_id] = task_obj
        
        logger.info(f"Task {task_id} created successfully")
        
        # Return the task object according to ARC protocol
        return {
            "type": "task",
            "task": task_obj
        }
        
    except Exception as e:
        logger.error(f"Error in task.create handler: {e}", exc_info=True)
        raise


@task_handler("task.send")
async def handle_task_send(params, context: RpcContext):
    """
    Handle task.send method
    
    This adds a message to an existing task and returns the updated task.
    """
    try:
        task_id = params.taskId
        message = params.message
        
        logger.info(f"Sending message to task: {task_id}")
        
        # Check if task exists
        if task_id not in mock_db["tasks"]:
            raise ValueError(f"Task {task_id} not found")
        
        task = mock_db["tasks"][task_id]
        
        # Extract message content
        user_content = ""
        if message and message.parts:
            for part in message.parts:
                if part.type == Type.text_part:
                    user_content = part.content or ""
                    break
        
        logger.info(f"Additional message: {user_content[:100]}")
        
        # Generate response to the additional message
        ai_response = generate_mock_response(user_content)
        
        now_dt = datetime.datetime.now()
        
        # Create agent response to the new message
        agent_message = Message(
            role=Role.agent,
            parts=[Part(
                type=Type.text_part,
                content=f"Received additional message for task {task_id}. {ai_response}"
            )],
            timestamp=now_dt,
            agentId=SERVER_AGENT_ID
        )
        
        # Add messages to the task
        task["messages"].append(message)
        task["messages"].append(agent_message)
        task["updatedAt"] = now_dt
        
        # Return task update response
        return {
            "type": "task",
            "task": {
                "taskId": task_id,
                "status": "completed",
                "updatedAt": now_dt,
                "newMessage": agent_message
            }
        }
        
    except Exception as e:
        logger.error(f"Error in task.send handler: {e}", exc_info=True)
        raise


@task_handler("task.info")
async def handle_task_info(params, context: RpcContext):
    """
    Handle task.info method
    
    This retrieves the current state of a task.
    """
    try:
        task_id = params.taskId
        logger.info(f"Getting status for task: {task_id}")
        
        # Check if task exists
        if task_id not in mock_db["tasks"]:
            raise ValueError(f"Task {task_id} not found")
        
        task = mock_db["tasks"][task_id]
        
        # Return the task object
        return {
            "type": "task",
            "task": task
        }
        
    except Exception as e:
        logger.error(f"Error in task.info handler: {e}", exc_info=True)
        raise


#############################################################
# Stream Method Handlers
#############################################################

@stream_handler("stream.start")
async def handle_stream_start(params, context: RpcContext):
    """
    Handle stream.start method
    
    This creates a new real-time stream session.
    """
    try:
        # Generate a new stream ID
        stream_id = f"stream-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        now_dt = datetime.datetime.now()
        
        # Get participants list or default to requester and this agent
        participants = getattr(params, "participants", [context.request_agent, SERVER_AGENT_ID])
        
        # Create stream object
        stream_obj = {
            "streamId": stream_id,
            "status": "active",
            "participants": participants,
            "createdAt": now_dt,
            "metadata": getattr(params, "metadata", {}) or {}
        }
        
        # Store stream in our mock database
        mock_db["streams"][stream_id] = stream_obj
        
        logger.info(f"Stream started: {stream_id} by {context.request_agent}")
        
        # Return stream object according to ARC protocol
        return {
            "type": "stream",
            "stream": stream_obj
        }
        
    except Exception as e:
        logger.error(f"Error in stream.start handler: {e}", exc_info=True)
        raise


@stream_handler("stream.message")
async def handle_stream_message(params, context: RpcContext):
    """
    Handle stream.message method
    
    This processes a message in a real-time stream.
    """
    try:
        stream_id = params.streamId
        message = params.message
        
        # Check if stream exists
        if stream_id not in mock_db["streams"]:
            raise ValueError(f"Stream {stream_id} not found")
        
        stream = mock_db["streams"][stream_id]
        
        # Extract message content
        content = ""
        if message and message.parts:
            for part in message.parts:
                if part.type == Type.text_part:
                    content = part.content or ""
                    break
        
        logger.info(f"Stream message for {stream_id}: {content[:100]}")
        
        # In a real implementation, this would typically:
        # 1. Process the message
        # 2. Send response through WebSocket/SSE
        # 3. Store message history
        
        # For this example, we'll just acknowledge receipt
        # In a real server, agent responses would be sent via WebSocket/SSE
        
        # Add message to stream
        if "messages" not in stream:
            stream["messages"] = []
        stream["messages"].append(message)
        
        return {
            "type": "stream_message_ack",
            "streamId": stream_id
        }
        
    except Exception as e:
        logger.error(f"Error in stream.message handler: {e}", exc_info=True)
        raise


@stream_handler("stream.chunk")
async def handle_stream_chunk(params, context: RpcContext):
    """
    Handle stream.chunk method
    
    This processes a chunk of data in a real-time stream.
    """
    try:
        stream_id = params.streamId
        chunk = params.chunk
        sequence = params.sequence
        is_last = params.isLast
        
        # Check if stream exists
        if stream_id not in mock_db["streams"]:
            raise ValueError(f"Stream {stream_id} not found")
        
        # Extract chunk content if it's a message
        chunk_content = "Unknown chunk"
        if chunk and hasattr(chunk, 'parts'):
            for part in chunk.parts:
                if part.type == Type.text_part or part.type == Type.data_part:
                    chunk_content = part.content or ""
                    break
        
        logger.info(f"Stream chunk for {stream_id}: seq={sequence}, last={is_last}")
        logger.debug(f"Chunk content: {chunk_content[:50]}...")
        
        # In a real implementation, this would:
        # 1. Process the chunk
        # 2. Buffer or stream to processor
        # 3. Possibly send incremental results via WebSocket/SSE
        
        # For this example, we'll just acknowledge receipt
        return {
            "type": "stream_chunk_ack",
            "streamId": stream_id,
            "sequence": sequence,
            "isLast": is_last,
            "processed": True
        }
        
    except Exception as e:
        logger.error(f"Error in stream.chunk handler: {e}", exc_info=True)
        raise


@stream_handler("stream.end")
async def handle_stream_end(params, context: RpcContext):
    """
    Handle stream.end method
    
    This ends a real-time stream session.
    """
    try:
        stream_id = params.streamId
        reason = params.reason
        
        # Check if stream exists
        if stream_id not in mock_db["streams"]:
            raise ValueError(f"Stream {stream_id} not found")
        
        stream = mock_db["streams"][stream_id]
        
        # Update stream status
        stream["status"] = "ended"
        stream["endedAt"] = datetime.datetime.now()
        stream["endReason"] = reason
        
        logger.info(f"Stream ended: {stream_id} by {context.request_agent} (Reason: {reason})")
        
        return {
            "type": "stream_end_ack",
            "streamId": stream_id,
            "reason": reason
        }
        
    except Exception as e:
        logger.error(f"Error in stream.end handler: {e}", exc_info=True)
        raise


def main():
    """Start the ARC server"""
    
    print("🚀 Starting ARC Example Server...")
    print(f"🤖 Agent ID: {SERVER_AGENT_ID}")
    print(f"🔐 Authentication: {'Enabled' if ENABLE_AUTH else 'Disabled (local testing)'}")
    print()
    
    # Create and start the server
    server = create_server()
    
    # Print server information
    print("🌐 Server URLs:")
    print(f"  • ARC endpoint: http://{SERVER_HOST}:{SERVER_PORT}/arc")
    print(f"  • Health check: http://{SERVER_HOST}:{SERVER_PORT}/health")
    print(f"  • Agent card: http://{SERVER_HOST}:{SERVER_PORT}/.well-known/agent-card.json")
    print()
    print("🎯 SUPPORTED ARC METHODS:")
    print("   📬 Task Methods:")
    print("     • task.create - Create async tasks")
    print("     • task.send - Send messages to existing tasks")
    print("     • task.info - Get task status and results")
    print("   🔄 Stream Methods:")
    print("     • stream.start - Start real-time streams")
    print("     • stream.message - Send real-time messages")
    print("     • stream.chunk - Send chunked data")
    print("     • stream.end - End streams")
    print()
    print("🧪 Test with: python ../client/basic_client.py")
    print("⏹️  Press Ctrl+C to stop")
    print()
    
    # Start the server
    server.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == "__main__":
    main()