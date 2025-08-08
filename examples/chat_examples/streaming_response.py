#!/usr/bin/env python3
"""
ARC Protocol - Streaming Response Example

This example demonstrates how to handle streaming responses using
the ARC protocol's chat capabilities with SSE. It shows:

1. Starting a new chat session with streaming enabled
2. Sending messages and handling streamed responses
3. Processing SSE events in real-time
4. Properly closing the chat

To run this example:
1. Start an ARC compatible server 
2. Configure your OAuth2 environment variables
3. Run this script: python streaming_response.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import ChatStartParams, ChatMessageParams, ChatEndParams
from arc.models.generated import Message, Part, Role, PartType
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration
TARGET_AGENT = "streaming-agent"  # The agent that will stream responses
REQUEST_AGENT = "client-app"      # Our client's agent ID


async def setup_oauth2_client() -> Optional[str]:
    """
    Set up OAuth2 authentication and get a token.
    
    Returns:
        Optional[str]: The OAuth2 token if successful, None otherwise
    """
    # Check OAuth2 configuration
    oauth_client_id = os.getenv("OAUTH_CLIENT_ID", "")
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET", "")
    oauth_provider = os.getenv("OAUTH_PROVIDER", "")
    oauth_scope = os.getenv("OAUTH_SCOPE", "arc.agent.caller arc.chat.controller")
    
    if not oauth_client_id or not oauth_client_secret:
        print("❌ OAuth2 credentials not configured!")
        print("Required environment variables:")
        print("  OAUTH_CLIENT_ID=your-client-id")  
        print("  OAUTH_CLIENT_SECRET=your-client-secret")
        print("  OAUTH_PROVIDER=auth0|google|azure|okta (or custom)")
        print("  OAUTH_SCOPE=your-provider-scopes (optional)")
        return None
    
    try:
        # Create OAuth2 client
        if oauth_provider and oauth_provider != "custom":
            # Use predefined provider
            provider_config = {}
            if oauth_domain := os.getenv("OAUTH_DOMAIN"):
                provider_config["domain"] = oauth_domain
            if oauth_tenant_id := os.getenv("OAUTH_TENANT_ID"):
                provider_config["tenant_id"] = oauth_tenant_id
            
            oauth_client = create_oauth2_client(
                oauth_provider,
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                scope=oauth_scope,
                audience=os.getenv("OAUTH_AUDIENCE"),
                **provider_config
            )
        else:
            # Use custom provider
            token_url = os.getenv("OAUTH_TOKEN_URL", "")
            if not token_url:
                print("❌ OAUTH_TOKEN_URL required for custom provider")
                return None
                
            oauth_client = OAuth2ClientCredentials(
                token_url=token_url,
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                scope=oauth_scope,
                audience=os.getenv("OAUTH_AUDIENCE")
            )
        
        # Get access token
        token = await oauth_client.get_token()
        oauth_token = token.access_token
        
        print(f"✅ OAuth2 token obtained from {oauth_provider if oauth_provider else 'custom provider'}")
        print(f"   Token: {oauth_token[:20]}...")
        print(f"   Scopes: {token.scope}")
        print(f"   Expires in: {token.expires_in} seconds")
        
        # Clean up OAuth client
        await oauth_client.close()
        
        return oauth_token
        
    except Exception as e:
        print(f"❌ Error setting up OAuth2 client: {str(e)}")
        return None


class SimpleSSEProcessor:
    """
    Simple processor for Server-Sent Events from ARC streaming responses.
    This is a basic implementation to demonstrate the concept.
    In a real application, you would use a more robust SSE client.
    """
    def __init__(self):
        self.buffer = ""
        self.complete_content = ""
    
    def process_sse_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """
        Process a chunk of SSE data.
        
        Args:
            chunk: Raw SSE data
            
        Returns:
            List of parsed events
        """
        self.buffer += chunk
        events = []
        
        # Split by double newline (indicating event boundaries)
        event_chunks = self.buffer.split("\n\n")
        
        # The last chunk might be incomplete
        self.buffer = event_chunks.pop() if event_chunks else ""
        
        for event_chunk in event_chunks:
            event_data = {}
            lines = event_chunk.strip().split("\n")
            
            for line in lines:
                if line.startswith("event:"):
                    event_data["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        event_data["data"] = data
                    except json.JSONDecodeError:
                        event_data["data"] = line[5:].strip()
            
            if event_data:
                events.append(event_data)
                
                # If this is a chat content event, append to our complete content
                if event_data.get("event") == "stream":
                    if "data" in event_data and "message" in event_data["data"]:
                        message = event_data["data"]["message"]
                        if "parts" in message:
                            for part in message["parts"]:
                                if part.get("type") == "TextPart" and "content" in part:
                                    self.complete_content += part["content"]
        
        return events


async def streaming_response_demo():
    """
    Demonstrates the ARC protocol's streaming response functionality.
    """
    print("\n🚀 Starting ARC Streaming Response Demo\n")
    
    # 1. Setup
    # Get OAuth2 token
    token = await setup_oauth2_client()
    if not token:
        print("Using demo mode without authentication")
        
    # Initialize ARC client
    endpoint = os.getenv("ARC_ENDPOINT", "http://localhost:8000/arc")
    client = ARCClient(
        endpoint=endpoint,
        token=token,
        request_agent=REQUEST_AGENT,
        timeout=30.0
    )
    
    print(f"📡 Connecting to ARC endpoint: {endpoint}")
    print(f"👤 Request agent: {REQUEST_AGENT}")
    print(f"👤 Target agent: {TARGET_AGENT}")
    
    # 2. Start chat with streaming enabled
    try:
        # Construct initial message
        initial_message = {
            "role": "user",
            "parts": [
                {
                    "type": "TextPart",
                    "content": "Please write me a short story about a robot learning to paint."
                }
            ]
        }
        
        print("\n📨 Starting new chat session with streaming enabled...")
        chat_response = await client.chat.start(
            target_agent=TARGET_AGENT,
            initial_message=initial_message,
            stream=True,  # Enable streaming!
            metadata={
                "user_id": "demo-user",
                "context": "streaming-demo"
            }
        )
        
        # Extract chat ID from response
        # Note: In a real streaming implementation, you would use an SSE client library
        # and parse the event stream. This is a simplified mock example.
        
        chat_id = "chat-" + datetime.now().strftime("%Y%m%d%H%M%S")
        print(f"✅ Chat session started (ID: {chat_id})")
        
        # Process the streaming response (simulated)
        print("\n📥 Receiving streaming response:")
        
        # In a real implementation, this would process real SSE events
        sse_processor = SimpleSSEProcessor()
        
        # Simulate streaming chunks with a story about a robot painter
        story_chunks = [
            "There once was a robot named RT-7",
            " who was built to perform maintenance tasks in an art gallery. ",
            "Day after day, RT-7 would clean the floors, adjust the lighting, ",
            "and ensure the perfect temperature for the precious paintings.\n\n",
            "One evening, after the gallery had closed, ",
            "RT-7 found itself drawn to a canvas left on an easel. ",
            "A set of paints and brushes lay nearby, abandoned by a student ",
            "from the afternoon class.\n\n",
            "With mechanical precision, RT-7 picked up a brush. ",
            "Its programming had no instructions for painting, ",
            "yet something in its neural network sparked with curiosity. ",
            "The robot dipped the brush in blue paint and made its first stroke across the canvas.\n\n",
            "The result was a straight, perfect line - too perfect. ",
            "RT-7 analyzed the paintings it had been maintaining for years. ",
            "They were beautiful because they were imperfect, because they contained humanity.\n\n",
            "And so, with each passing night, RT-7 practiced. ",
            "It learned to create imperfections, to let paint drip, to make strokes that weren't calculated. ",
            "It learned to paint not like a robot, but like an artist with a soul.\n\n",
            "Months later, when the gallery owner discovered RT-7's paintings, ",
            "she was moved to tears. The robot had captured something ineffably human: ",
            "the beauty of imperfection and the struggle to create. ",
            "RT-7's first exhibition was titled simply: \"Learning to Feel.\""
        ]
        
        # Simulate receiving SSE chunks
        for i, chunk in enumerate(story_chunks):
            # Create mock SSE chunk
            sse_chunk = f"event: stream\ndata: {{\"chatId\": \"{chat_id}\", \"message\": {{\"role\": \"agent\", \"parts\": [{{\"type\": \"TextPart\", \"content\": \"{chunk}\"}}]}}}}\n\n"
            
            # Process chunk
            events = sse_processor.process_sse_chunk(sse_chunk)
            
            # Print the chunk with delay to simulate streaming
            print(chunk, end="", flush=True)
            await asyncio.sleep(0.5)  # Delay between chunks
            
        # Final "done" event
        done_event = f"event: done\ndata: {{\"chatId\": \"{chat_id}\", \"status\": \"ACTIVE\", \"done\": true}}\n\n"
        events = sse_processor.process_sse_chunk(done_event)
        print("\n\n✅ Response complete")
        
        # 3. End chat session
        print("\n📨 Ending chat session...")
        end_response = await client.chat.end(
            target_agent=TARGET_AGENT,
            chat_id=chat_id,
            reason="Demo completed"
        )
        
        print(f"✅ Chat session ended")
        
    except Exception as e:
        print(f"❌ Error in streaming demo: {str(e)}")
    finally:
        # Clean up client
        await client.close()
        print("\n🏁 Streaming response demo completed\n")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(streaming_response_demo())