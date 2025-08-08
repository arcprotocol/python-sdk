#!/usr/bin/env python3
"""
ARC Protocol - Realtime Chat Example

This example demonstrates how to implement a simple realtime chat application
using the ARC protocol's streaming capabilities. It shows:

1. Starting a new stream session
2. Sending messages in real-time
3. Handling streaming responses
4. Properly closing the stream

To run this example:
1. Start an ARC compatible server 
2. Configure your OAuth2 environment variables
3. Run this script: python realtime_chat.py
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import StreamStartParams, StreamMessageParams, StreamEndParams
from arc.models.generated import Message, Part, Role, Type
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration
TARGET_AGENT = "chat-agent"  # The agent ID you want to chat with
REQUEST_AGENT = "chat-client"  # Your client's agent ID


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
    oauth_scope = os.getenv("OAUTH_SCOPE", "arc.agent.caller arc.stream.controller")
    
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
        print(f"❌ Failed to get OAuth2 token: {e}")
        return None


async def realtime_chat_demo():
    """
    Demonstrate a realtime chat session using ARC protocol's streaming capabilities.
    """
    print("🚀 ARC Protocol - Realtime Chat Example")
    print("=" * 50)
    
    # Get OAuth token
    oauth_token = await setup_oauth2_client()
    if not oauth_token:
        print("Cannot continue without authentication")
        return
    
    # Set up ARC client
    server_url = os.getenv("ARC_SERVER_URL", "http://localhost:8000")
    
    # Determine if we need to allow HTTP for local testing
    allow_http = server_url.startswith("http://")
    if allow_http:
        print("⚠️  WARNING: Using insecure HTTP connection. Only use for local testing!")
    
    # Create ARC client
    client = ARCClient(
        base_url=server_url,
        request_agent=REQUEST_AGENT,
        target_agent=TARGET_AGENT,
        oauth_token=oauth_token,
        allow_http=allow_http  # Only for local testing!
    )
    
    print(f"\n📡 Connecting to {TARGET_AGENT} at {server_url}...")
    
    try:
        # Start a new stream session
        stream_start_params = StreamStartParams(
            participants=[REQUEST_AGENT, TARGET_AGENT],
            metadata={
                "clientInfo": "ARC Chat Example",
                "sessionType": "conversation",
                "timestamp": datetime.now().isoformat()
            }
        )
        
        stream_response = await client.stream.start(stream_start_params)
        stream_id = stream_response.get("stream", {}).get("streamId")
        
        if not stream_id:
            print("❌ Failed to start stream session")
            return
        
        print(f"✅ Stream session started with ID: {stream_id}")
        print(f"👥 Participants: {stream_response.get('stream', {}).get('participants', [])}")
        print("\n" + "=" * 50)
        print("🤖 Welcome to the ARC Chat Demo!")
        print("Type your messages and press Enter to send.")
        print("Type 'exit' to end the conversation.")
        print("=" * 50 + "\n")
        
        # Main chat loop
        while True:
            # Get user input
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit", "bye"]:
                break
                
            # Send message to agent
            message_params = StreamMessageParams(
                streamId=stream_id,
                message=Message(
                    role=Role.user,
                    parts=[Part(
                        type=Type.text_part,
                        content=user_input
                    )]
                )
            )
            
            # Send the message and get response
            print("Sending message...")
            message_response = await client.stream.message(message_params)
            
            # In a real application, you would typically receive agent responses 
            # through WebSockets or server-sent events. Here we're simulating with a delay.
            print("Waiting for response...")
            await asyncio.sleep(1)  # Simulate network delay
            
            # Simulate agent response (in real app, this would come via WebSocket/SSE)
            agent_response = generate_mock_response(user_input)
            print(f"\n{TARGET_AGENT}: {agent_response}\n")
        
        # End the stream session properly
        print("\nEnding chat session...")
        end_params = StreamEndParams(
            streamId=stream_id,
            reason="User ended conversation"
        )
        await client.stream.end(end_params)
        print("✅ Chat session ended successfully")
        
    except Exception as e:
        print(f"❌ Error in chat session: {e}")
    finally:
        # Clean up
        await client.close()


def generate_mock_response(user_input: str) -> str:
    """Generate mock agent responses for demonstration purposes"""
    user_input_lower = user_input.lower()
    
    if "hello" in user_input_lower or "hi" in user_input_lower:
        return "Hello! I'm an ARC-powered chat agent. How can I help you today?"
    elif "help" in user_input_lower:
        return "I can assist with questions about ARC protocol, provide examples, or just chat. What would you like to know?"
    elif "arc" in user_input_lower and "protocol" in user_input_lower:
        return "The ARC (Agent Remote Communication) Protocol is a stateless RPC protocol designed for multi-agent deployment with built-in agent routing, load balancing, and workflow tracing."
    elif "how" in user_input_lower and "work" in user_input_lower:
        return "I work by using the ARC protocol's streaming capabilities for real-time communication. Messages are sent and received through secure API endpoints using OAuth2 authentication."
    elif "feature" in user_input_lower:
        return "Key features of ARC protocol include: multi-agent routing, real-time streaming, asynchronous tasks, standardized error handling, and comprehensive security through OAuth2."
    elif "example" in user_input_lower:
        return "This chat is an example of ARC's streaming capabilities! Other examples include file processing pipelines, multi-agent workflows, and task delegation systems."
    else:
        return f"I received your message: '{user_input}'. In a production environment, I would provide a meaningful response based on my capabilities."


if __name__ == "__main__":
    asyncio.run(realtime_chat_demo())
