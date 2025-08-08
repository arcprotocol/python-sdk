#!/usr/bin/env python3
"""
ARC Protocol - Realtime Chat Example

This example demonstrates how to implement a simple realtime chat application
using the ARC protocol's chat capabilities. It shows:

1. Starting a new chat session
2. Sending messages in real-time
3. Handling streaming responses
4. Properly closing the chat

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
from arc.models.generated import ChatStartParams, ChatMessageParams, ChatEndParams
from arc.models.generated import Message, Part, Role, PartType
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


async def realtime_chat_demo():
    """
    Demonstrates the ARC protocol's realtime chat functionality.
    """
    print("\n🚀 Starting ARC Realtime Chat Demo\n")
    
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
    
    # 2. Create a chat session
    try:
        # Construct initial message
        initial_message = {
            "role": "user",
            "parts": [
                {
                    "type": "TextPart",
                    "content": "Hello! I'd like to start a conversation."
                }
            ]
        }
        
        # Start chat
        print("\n📨 Starting new chat session...")
        chat_response = await client.chat.start(
            target_agent=TARGET_AGENT,
            initial_message=initial_message,
            metadata={
                "user_id": "demo-user",
                "context": "chat-demo"
            }
        )
        
        # Extract chat ID from response
        result = chat_response.get("result", {})
        chat = result.get("chat", {})
        chat_id = chat.get("chatId")
        
        if not chat_id:
            print("❌ Failed to get chat ID from response")
            return
            
        print(f"✅ Chat session started (ID: {chat_id})")
        print(f"   Status: {chat.get('status')}")
        
        # 3. Chat interaction loop
        for i in range(3):
            # Get user input
            if i == 0:
                user_input = "What's the current time?"
            elif i == 1:
                user_input = "Can you tell me a fun fact about programming?"
            else:
                user_input = "Thank you for the conversation!"
                
            print(f"\n👤 USER: {user_input}")
            
            # Send message in the chat
            message = {
                "role": "user",
                "parts": [
                    {
                        "type": "TextPart",
                        "content": user_input
                    }
                ]
            }
            
            print(f"📨 Sending message to chat {chat_id}...")
            message_response = await client.chat.message(
                target_agent=TARGET_AGENT,
                chat_id=chat_id,
                message=message
            )
            
            # For demo purposes, generate a mock response
            agent_response = generate_mock_response(user_input)
            print(f"🤖 AGENT: {agent_response}")
            
            # Pause between messages
            await asyncio.sleep(1)
        
        # 4. End chat session
        print("\n📨 Ending chat session...")
        end_response = await client.chat.end(
            target_agent=TARGET_AGENT,
            chat_id=chat_id,
            reason="Conversation completed"
        )
        
        print(f"✅ Chat session ended")
        if "result" in end_response and "chat" in end_response["result"]:
            chat = end_response["result"]["chat"]
            print(f"   Status: {chat.get('status')}")
            print(f"   Reason: {chat.get('reason')}")
            
    except Exception as e:
        print(f"❌ Error in realtime chat demo: {str(e)}")
    finally:
        # Clean up client
        await client.close()
        print("\n🏁 Realtime chat demo completed\n")
        

def generate_mock_response(user_input: str) -> str:
    """
    Generate a mock agent response for demonstration purposes.
    
    Args:
        user_input: The user's message
        
    Returns:
        A mock response from the agent
    """
    if "time" in user_input.lower():
        current_time = datetime.now().strftime("%H:%M:%S")
        return f"The current time is {current_time}."
    elif "fun fact" in user_input.lower():
        return "Did you know that the first computer bug was an actual insect? In 1947, Grace Hopper found a moth in a relay of the Harvard Mark II computer, which was causing it to malfunction."
    elif "thank" in user_input.lower():
        return "You're welcome! It was nice chatting with you."
    else:
        return "I'm a simple demo agent. I can tell you the time or share a fun fact about programming if you ask!"


if __name__ == "__main__":
    # Run the demo
    asyncio.run(realtime_chat_demo())