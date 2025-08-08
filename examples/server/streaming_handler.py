#!/usr/bin/env python3
"""
ARC Protocol - Streaming Chat Example Server

This example demonstrates how to implement a server that supports
streaming responses using Server-Sent Events (SSE) for chat methods.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, AsyncIterator

from fastapi import FastAPI
import uvicorn

from arc.server import ARCServer
from arc.models.generated import Message, Part, Role, PartType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streaming-server")

# Create ARC server
app = ARCServer(
    agent_id="streaming-demo-agent",
    name="Streaming Demo Agent",
    agent_description="Demonstrates streaming responses with SSE"
)

# FastAPI instance (if needed for other routes)
fastapi_app = app.get_app()


class StreamingMessage:
    """A message that can be streamed chunk by chunk."""

    def __init__(self, content: str, chunk_size: int = 10, delay: float = 0.1):
        """
        Initialize with the full content.
        
        Args:
            content: The full message text
            chunk_size: Characters per chunk
            delay: Seconds between chunks
        """
        self.content = content
        self.chunk_size = chunk_size
        self.delay = delay
        
    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream the message in chunks.
        
        Yields:
            Message parts with progressively more content
        """
        text = self.content
        pos = 0
        
        while pos < len(text):
            # Get next chunk
            chunk = text[pos:pos + self.chunk_size]
            pos += self.chunk_size
            
            # Create message with this chunk
            yield {
                "role": "agent",
                "parts": [{"type": "TextPart", "content": chunk}]
            }
            
            # Delay to simulate thinking/typing
            await asyncio.sleep(self.delay)


@app.chat_handler("chat.start")
async def handle_chat_start(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle chat.start method with streaming support.
    
    Args:
        params: Method parameters
        context: Request context
        
    Returns:
        Chat result with streaming response if requested
    """
    # Extract parameters
    initial_message = params.get("initialMessage", {})
    chat_id = params.get("chatId") or f"chat-{uuid.uuid4().hex[:8]}"
    stream_mode = params.get("stream", False)
    metadata = params.get("metadata", {})
    
    # Log the incoming message
    logger.info(f"Chat started: {chat_id}")
    if initial_message.get("parts"):
        content = []
        for part in initial_message.get("parts", []):
            if part.get("type") == "TextPart":
                content.append(part.get("content", ""))
        logger.info(f"User message: {' '.join(content)}")
    
    # Generate a response based on the user's message
    response_text = generate_response(initial_message)
    
    # If streaming is requested, return a streamable message
    if stream_mode:
        response_message = StreamingMessage(response_text, chunk_size=10, delay=0.1)
    else:
        # Otherwise, return the full message
        response_message = {
            "role": "agent",
            "parts": [{"type": "TextPart", "content": response_text}]
        }
    
    # Return chat result
    return {
        "type": "chat",
        "chat": {
            "chatId": chat_id,
            "status": "ACTIVE",
            "message": response_message,
            "createdAt": datetime.now().isoformat(),
            "participants": ["streaming-demo-agent"]
        }
    }


@app.chat_handler("chat.message")
async def handle_chat_message(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle chat.message method with streaming support.
    
    Args:
        params: Method parameters
        context: Request context
        
    Returns:
        Chat result with streaming response if requested
    """
    # Extract parameters
    chat_id = params.get("chatId")
    message = params.get("message", {})
    stream_mode = params.get("stream", False)
    
    # Log the incoming message
    logger.info(f"Message received in chat: {chat_id}")
    if message.get("parts"):
        content = []
        for part in message.get("parts", []):
            if part.get("type") == "TextPart":
                content.append(part.get("content", ""))
        logger.info(f"User message: {' '.join(content)}")
    
    # Generate a response based on the user's message
    response_text = generate_response(message)
    
    # If streaming is requested, return a streamable message
    if stream_mode:
        response_message = StreamingMessage(response_text, chunk_size=10, delay=0.1)
    else:
        # Otherwise, return the full message
        response_message = {
            "role": "agent",
            "parts": [{"type": "TextPart", "content": response_text}]
        }
    
    # Return chat result
    return {
        "type": "chat",
        "chat": {
            "chatId": chat_id,
            "status": "ACTIVE",
            "message": response_message,
            "updatedAt": datetime.now().isoformat()
        }
    }


@app.chat_handler("chat.end")
async def handle_chat_end(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle chat.end method.
    
    Args:
        params: Method parameters
        context: Request context
        
    Returns:
        Chat end result
    """
    chat_id = params.get("chatId")
    reason = params.get("reason", "Chat ended by user")
    
    logger.info(f"Chat ended: {chat_id} - Reason: {reason}")
    
    return {
        "type": "chat",
        "chat": {
            "chatId": chat_id,
            "status": "CLOSED",
            "closedAt": datetime.now().isoformat(),
            "reason": reason
        }
    }


def generate_response(message: Dict[str, Any]) -> str:
    """
    Generate a response based on the user's message.
    
    Args:
        message: User message
        
    Returns:
        Response text
    """
    # Extract text from message parts
    user_text = ""
    for part in message.get("parts", []):
        if part.get("type") == "TextPart":
            user_text += part.get("content", "")
    
    # Simple keyword-based responses
    user_text = user_text.lower()
    
    if "hello" in user_text or "hi" in user_text or "hey" in user_text:
        return "Hello! I'm a streaming demo agent. I'll send my response chunk by chunk so you can see how SSE streaming works."
        
    elif "help" in user_text:
        return "I'm a demo agent showing how streaming works in the ARC protocol. My responses are sent chunk by chunk using Server-Sent Events (SSE). Try sending me a message and watch my response appear gradually!"
        
    elif "weather" in user_text:
        return "Today's weather is sunny with a high of 75°F (24°C) and a low of 62°F (16°C). There's a 10% chance of precipitation and winds are from the northwest at 5-10 mph."
        
    elif "time" in user_text:
        return f"The current time is {datetime.now().strftime('%H:%M:%S')}. This is being streamed to you character by character using SSE!"
        
    elif "bye" in user_text or "goodbye" in user_text:
        return "Goodbye! Thanks for trying out the streaming demo. Feel free to come back anytime to see how ARC protocol streaming works!"
        
    else:
        return "I'm demonstrating streaming responses with the ARC protocol. Each character of this message is being sent individually through Server-Sent Events. This approach allows for real-time, incremental responses that appear to the user as if they're being typed out progressively."


if __name__ == "__main__":
    uvicorn.run(
        app.get_app(),
        host="0.0.0.0",
        port=8000
    )