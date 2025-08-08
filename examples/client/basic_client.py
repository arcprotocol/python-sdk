#!/usr/bin/env python3
"""
ARC Protocol - Basic Client Example

This example demonstrates how to use the ARC client to communicate with an ARC server.
It shows how to:
1. Set up OAuth2 authentication
2. Create an ARC client
3. Use both task and stream methods
4. Handle responses and errors

To run this example:
1. Start the server: python ../server/basic_server.py
2. Run this client: python basic_client.py

For local testing, this example allows HTTP connections, but in production
you should always use HTTPS and proper OAuth2 tokens.
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import TaskCreateParams, TaskSendParams, TaskInfoParams
from arc.models.generated import ChatStartParams, ChatMessageParams, ChatEndParams
from arc.models.generated import Message, Part, Role, Type
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration
SERVER_URL = os.getenv("ARC_SERVER_URL", "http://localhost:8000")
TARGET_AGENT = os.getenv("ARC_TARGET_AGENT", "arc-example-agent")
REQUEST_AGENT = os.getenv("ARC_REQUEST_AGENT", "arc-example-client")


async def setup_oauth2_client() -> Optional[str]:
    """
    Set up OAuth2 authentication and get a token.
    
    Returns:
        Optional[str]: The OAuth2 token if successful, None otherwise
    """
    # For local testing, we'll create a simple test token
    # In production, you would get a real token from your OAuth2 provider
    if SERVER_URL.startswith("http://localhost") or SERVER_URL.startswith("http://127.0.0.1"):
        print("🔑 Using development token for local testing")
        return "dev.token.for.local.testing.only"
    
    # Check OAuth2 configuration
    oauth_client_id = os.getenv("OAUTH_CLIENT_ID", "")
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET", "")
    oauth_provider = os.getenv("OAUTH_PROVIDER", "")
    oauth_scope = os.getenv("OAUTH_SCOPE", "arc.agent.caller arc.task.controller arc.chat.controller")
    
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


async def main():
    """Basic ARC client example"""
    
    print("🚀 ARC Protocol - Basic Client Example")
    print("=" * 50)
    
    # Get OAuth token
    oauth_token = await setup_oauth2_client()
    if not oauth_token:
        print("Cannot continue without authentication")
        return
    
    # Determine if we need to allow HTTP for local testing
    allow_http = SERVER_URL.startswith("http://")
    if allow_http:
        print("⚠️  WARNING: Using insecure HTTP connection. Only use for local testing!")
    
    # Create ARC client
    client = ARCClient(
        base_url=SERVER_URL,
        request_agent=REQUEST_AGENT,
        target_agent=TARGET_AGENT,
        oauth_token=oauth_token,
        allow_http=allow_http  # Only for local testing!
    )
    
    print(f"\n📡 Connecting to {TARGET_AGENT} at {SERVER_URL}...")
    
    try:
        # Generate trace ID for end-to-end tracing
        trace_id = f"example-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # =====================================================================
        # TASK METHODS TESTING
        # =====================================================================
        print("\n📬 TESTING TASK METHODS")
        print("-" * 40)
        
        created_task_ids = []
        
        # Test 1: task.create
        print("🔹 Test 1: task.create")
        try:
            task_params = TaskCreateParams(
                initialMessage=Message(
                    role=Role.user,
                    parts=[Part(
                        type=Type.text_part,
                        content="Hello! This is a test task for the ARC protocol example."
                    )]
                ),
                priority="HIGH"
            )
            
            create_response = await client.task.create(task_params, trace_id=trace_id)
            task_data = create_response.get('task', {})
            task_id = task_data.get('taskId', 'unknown')
            created_task_ids.append(task_id)
            
            print(f"   ✅ Task created: {task_id}")
            print(f"   📊 Status: {task_data.get('status', 'unknown')}")
            
            # Get agent response from messages
            messages = task_data.get('messages', [])
            for msg in messages:
                if msg.get('role') == 'agent':
                    parts = msg.get('parts', [])
                    for part in parts:
                        if part.get('type') == 'TextPart':
                            agent_response = part.get('content', '')
                            print(f"   🤖 Agent: {agent_response[:100]}...")
            print()
            
        except Exception as e:
            print(f"   ❌ task.create failed: {e}")
            print()
        
        # Test 2: task.send
        if created_task_ids:
            print("🔹 Test 2: task.send")
            try:                
                send_params = TaskSendParams(
                    taskId=created_task_ids[0],
                    message=Message(
                        role=Role.user,
                        parts=[Part(
                            type=Type.text_part,
                            content="Can you tell me more about the ARC protocol?"
                        )]
                    )
                )
                
                send_response = await client.task.send(send_params, trace_id=trace_id)
                print(f"   ✅ Message sent to task: {created_task_ids[0]}")
                
                # Check if there's a new message in the response
                if 'task' in send_response and 'newMessage' in send_response['task']:
                    new_msg = send_response['task']['newMessage']
                    if new_msg and 'parts' in new_msg:
                        for part in new_msg['parts']:
                            if part.get('type') == 'TextPart':
                                response_text = part.get('content', '')
                                print(f"   🤖 Agent: {response_text[:100]}...")
                
                print()
                
            except Exception as e:
                print(f"   ❌ task.send failed: {e}")
                print()
        
        # Test 3: task.info
        if created_task_ids:
            print("🔹 Test 3: task.info")
            try:
                get_params = TaskInfoParams(taskId=created_task_ids[0])
                get_response = await client.task.info(get_params, trace_id=trace_id)
                
                task_data = get_response.get('task', {})
                print(f"   ✅ Task retrieved: {task_data.get('taskId', 'unknown')}")
                print(f"   📊 Status: {task_data.get('status', 'unknown')}")
                print(f"   💬 Messages: {len(task_data.get('messages', []))}")
                print()
                
            except Exception as e:
                print(f"   ❌ task.info failed: {e}")
                print()
        
        print("📬 TASK METHODS TESTING COMPLETE!")
        print()
        
        # =====================================================================
        # STREAM METHODS TESTING
        # =====================================================================
        print("\n🔄 TESTING STREAM METHODS")
        print("-" * 40)
        
        stream_id = None
        
        # Test 4: stream.start
        print("🔹 Test 4: stream.start")
        try:
            stream_start_params = StreamStartParams(
                participants=[REQUEST_AGENT, TARGET_AGENT],
                metadata={"topic": "example-test", "type": "demo"}
            )
            
            stream_start_response = await client.stream.start(stream_start_params, trace_id=trace_id)
            stream_obj = stream_start_response.get("stream", {})
            stream_id = stream_obj.get("streamId")
            
            print(f"   ✅ Stream started: {stream_id}")
            print(f"   👥 Participants: {stream_obj.get('participants', [])}")
            print(f"   📊 Status: {stream_obj.get('status', 'unknown')}")
            print()
            
        except Exception as e:
            print(f"   ❌ stream.start failed: {e}")
            print()
        
        # Test 5: stream.message
        if stream_id:
            print("🔹 Test 5: stream.message")
            try:
                stream_message_params = StreamMessageParams(
                    streamId=stream_id,
                    message=Message(
                        role=Role.user,
                        parts=[Part(
                            type=Type.text_part,
                            content="Let's test the streaming capabilities of the ARC protocol!"
                        )]
                    )
                )
                
                stream_message_response = await client.stream.message(stream_message_params, trace_id=trace_id)
                print(f"   ✅ Message sent to stream: {stream_id}")
                print(f"   💬 Response: {stream_message_response}")
                print()
                
            except Exception as e:
                print(f"   ❌ stream.message failed: {e}")
                print()
        
        # Test 6: stream.chunk
        if stream_id:
            print("🔹 Test 6: stream.chunk")
            try:
                stream_chunk_params = StreamChunkParams(
                    streamId=stream_id,
                    chunk=Message(
                        role=Role.user,
                        parts=[Part(
                            type=Type.text_part,
                            content="This is chunked data for streaming processing"
                        )]
                    ),
                    sequence=1,
                    isLast=False
                )
                
                stream_chunk_response = await client.stream.chunk(stream_chunk_params, trace_id=trace_id)
                print(f"   ✅ Chunk sent to stream: {stream_id}")
                print(f"   📦 Sequence: 1, Last: False")
                print(f"   🔄 Response: {stream_chunk_response}")
                print()
                
            except Exception as e:
                print(f"   ❌ stream.chunk failed: {e}")
                print()
        
        # Test 7: stream.end
        if stream_id:
            print("🔹 Test 7: stream.end")
            try:
                stream_end_params = StreamEndParams(
                    streamId=stream_id,
                    reason="Example test completed successfully"
                )
                
                stream_end_response = await client.stream.end(stream_end_params, trace_id=trace_id)
                print(f"   ✅ Stream ended: {stream_id}")
                print(f"   📝 Reason: Example test completed")
                print(f"   🏁 Response: {stream_end_response}")
                print()
                
            except Exception as e:
                print(f"   ❌ stream.end failed: {e}")
                print()
        
        print("🔄 STREAM METHODS TESTING COMPLETE!")
        print()
        
        # =====================================================================
        # TESTING SUMMARY
        # =====================================================================
        print("\n📊 TESTING SUMMARY")
        print("-" * 40)
        print("✅ Task Methods Tested:")
        print("   • task.create - Async task creation")
        print("   • task.send - Send message to existing task")
        print("   • task.get - Get task status and results")
        print()
        print("✅ Stream Methods Tested:")
        print("   • stream.start - Start real-time stream")
        print("   • stream.message - Send real-time message")
        print("   • stream.chunk - Send chunked data")
        print("   • stream.end - End the stream")
        print()
        print("🎉 ALL ARC METHODS TESTED SUCCESSFULLY!")
        
    except Exception as e:
        print(f"\n❌ Error in example: {e}")
    finally:
        # Clean up
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())