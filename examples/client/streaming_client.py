#!/usr/bin/env python3
"""
ARC Protocol - Streaming Client Example

This example demonstrates how to use the ARC client to handle streaming
responses using Server-Sent Events (SSE).
"""

import asyncio
import os
import sys
from typing import Dict, Any, AsyncIterator

from arc import ARCClient
from arc.exceptions import ARCException


# Configuration
TARGET_AGENT = os.getenv("ARC_TARGET_AGENT", "streaming-demo-agent")
REQUEST_AGENT = os.getenv("ARC_REQUEST_AGENT", "streaming-client")
ARC_ENDPOINT = os.getenv("ARC_ENDPOINT", "http://localhost:8000/arc")
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN", "")


async def stream_demo():
    """
    Demonstrate streaming chat responses.
    """
    print("\n🚀 ARC Protocol Streaming Client Example\n")
    print(f"📡 Connecting to: {ARC_ENDPOINT}")
    print(f"🎯 Target agent: {TARGET_AGENT}")
    
    # Create ARC client
    client = ARCClient(
        endpoint=ARC_ENDPOINT,
        token=OAUTH_TOKEN if OAUTH_TOKEN else None,
        request_agent=REQUEST_AGENT,
        timeout=30.0
    )
    
    try:
        # Start conversation with streaming enabled
        print("\n💬 Starting conversation with streaming...")
        
        # Prepare initial message
        initial_message = {
            "role": "user",
            "parts": [
                {
                    "type": "TextPart",
                    "content": "Tell me about the weather today"
                }
            ]
        }
        
        # Start chat with streaming enabled
        stream_response = await client.chat.start(
            target_agent=TARGET_AGENT,
            initial_message=initial_message,
            stream=True  # Enable streaming!
        )
        
        # Process streaming response
        if hasattr(stream_response, "__aiter__"):  # Check if it's an async iterator
            print("\n🤖 Agent is responding (streaming):")
            print("   ", end="", flush=True)
            
            collected_text = ""
            async for event in stream_response:
                if event.get("event") == "stream":
                    # Extract text from the message parts
                    data = event.get("data", {})
                    message = data.get("message", {})
                    
                    for part in message.get("parts", []):
                        if part.get("type") == "TextPart" and "content" in part:
                            content = part["content"]
                            collected_text += content
                            print(content, end="", flush=True)
                
                elif event.get("event") == "done":
                    chat_id = event.get("data", {}).get("chatId")
                    print(f"\n\n✅ Response complete (Chat ID: {chat_id})")
                    break
        
            print("\n📝 Full response:", collected_text)
            
        # Send another message
        print("\n💬 Sending another message...")
        message = {
            "role": "user",
            "parts": [
                {
                    "type": "TextPart",
                    "content": "What time is it?"
                }
            ]
        }
        
        # Use the chat_id from the previous response
        chat_id = "chat-123456"  # In a real app, extract this from the previous response
        
        # Send message with streaming enabled
        stream_response = await client.chat.message(
            target_agent=TARGET_AGENT,
            chat_id=chat_id,
            message=message,
            stream=True
        )
        
        # Process streaming response
        if hasattr(stream_response, "__aiter__"):  # Check if it's an async iterator
            print("\n🤖 Agent is responding (streaming):")
            print("   ", end="", flush=True)
            
            collected_text = ""
            async for event in stream_response:
                if event.get("event") == "stream":
                    # Extract text from the message parts
                    data = event.get("data", {})
                    message = data.get("message", {})
                    
                    for part in message.get("parts", []):
                        if part.get("type") == "TextPart" and "content" in part:
                            content = part["content"]
                            collected_text += content
                            print(content, end="", flush=True)
                
                elif event.get("event") == "done":
                    print(f"\n\n✅ Response complete")
                    break
        
            print("\n📝 Full response:", collected_text)
            
        # End conversation
        print("\n💬 Ending conversation...")
        await client.chat.end(
            target_agent=TARGET_AGENT,
            chat_id=chat_id,
            reason="Demo completed"
        )
        print("✅ Conversation ended")
        
    except ARCException as e:
        print(f"❌ ARC Error: {str(e)}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        # Close the client
        await client.close()
        print("\n🏁 Streaming demo completed\n")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(stream_demo())