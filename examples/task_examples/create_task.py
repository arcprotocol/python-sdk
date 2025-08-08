#!/usr/bin/env python3
"""
ARC Protocol - Task Creation Example

This example demonstrates how to use the ARC protocol's task methods to:
1. Create a new asynchronous task
2. Send additional information to an existing task
3. Check the status and results of a task

Tasks in ARC protocol allow for asynchronous processing of requests that
may take longer to complete, don't require real-time interaction, or need
to be persisted across sessions.

To run this example:
1. Start an ARC compatible server 
2. Configure your OAuth2 environment variables
3. Run this script: python create_task.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import TaskCreateParams, TaskSendParams, TaskInfoParams
from arc.models.generated import Message, Part, Role, Type
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration
TARGET_AGENT = "data-analysis-agent"  # The agent ID to handle our task
REQUEST_AGENT = "task-client"         # Our client's agent ID


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
    oauth_scope = os.getenv("OAUTH_SCOPE", "arc.agent.caller arc.task.controller")
    
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


def generate_sales_data() -> Dict[str, Any]:
    """Generate sample sales data for analysis"""
    return {
        "quarterly_sales": [
            {
                "quarter": "Q1",
                "revenue": 1250000,
                "growth": 0.05,
                "top_product": "Product A",
                "regions": {
                    "north": 450000,
                    "south": 320000,
                    "east": 280000,
                    "west": 200000
                }
            },
            {
                "quarter": "Q2",
                "revenue": 1340000,
                "growth": 0.07,
                "top_product": "Product B",
                "regions": {
                    "north": 410000,
                    "south": 350000,
                    "east": 310000,
                    "west": 270000
                }
            },
            {
                "quarter": "Q3",
                "revenue": 1420000,
                "growth": 0.06,
                "top_product": "Product A",
                "regions": {
                    "north": 430000,
                    "south": 380000,
                    "east": 320000,
                    "west": 290000
                }
            },
            {
                "quarter": "Q4",
                "revenue": 1560000,
                "growth": 0.09,
                "top_product": "Product C",
                "regions": {
                    "north": 460000,
                    "south": 410000,
                    "east": 350000,
                    "west": 340000
                }
            }
        ],
        "year": 2023,
        "currency": "USD",
        "department": "Electronics"
    }


async def task_creation_demo():
    """
    Demonstrate asynchronous task creation and management using ARC protocol.
    """
    print("🚀 ARC Protocol - Task Creation Example")
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
        # Generate trace ID for end-to-end tracing
        trace_id = f"task-demo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # 1. Create a new task with initial instructions
        print("\n📬 Step 1: Creating a new asynchronous task...")
        
        # Generate the sales data to analyze
        sales_data = generate_sales_data()
        sales_json = json.dumps(sales_data)
        
        # Create task with initial message containing both text instructions and data
        create_params = TaskCreateParams(
            initialMessage=Message(
                role=Role.user,
                parts=[
                    Part(
                        type=Type.text_part,
                        content="Please analyze the quarterly sales data and provide insights"
                    ),
                    Part(
                        type=Type.data_part,
                        content=sales_json,
                        mimeType="application/json"
                    )
                ]
            ),
            priority="HIGH",
            metadata={
                "category": "sales-analysis",
                "importance": "high",
                "deadline": (datetime.now().isoformat() + "Z")
            }
        )
        
        # Send the task creation request
        create_response = await client.task.create(create_params, trace_id=trace_id)
        task_data = create_response.get('task', {})
        task_id = task_data.get('taskId', 'unknown')
        
        if not task_id or task_id == 'unknown':
            print("❌ Failed to create task")
            return
            
        print(f"✅ Task created with ID: {task_id}")
        print(f"📊 Status: {task_data.get('status', 'unknown')}")
        print(f"📝 Trace ID: {trace_id}")
        
        # Get agent response from messages
        messages = task_data.get('messages', [])
        if messages:
            for msg in messages:
                if msg.get('role') == 'agent':
                    parts = msg.get('parts', [])
                    for part in parts:
                        if part.get('type') == 'TextPart':
                            agent_response = part.get('content', '')
                            print(f"\n🤖 Initial agent response: {agent_response}")
        
        # 2. Send additional information to the task
        print("\n📬 Step 2: Sending additional information to the task...")
        
        # Send additional context or requirements to the task
        send_params = TaskSendParams(
            taskId=task_id,
            message=Message(
                role=Role.user,
                parts=[Part(
                    type=Type.text_part,
                    content="Please also include trend analysis for the last 3 quarters and forecast for next quarter"
                )]
            )
        )
        
        # Send the additional message
        send_response = await client.task.send(send_params, trace_id=trace_id)
        print(f"✅ Additional information sent to task {task_id}")
        
        # 3. Check task status and results (polling)
        print("\n📬 Step 3: Checking task status (polling)...")
        
        # In a real application, you would typically either:
        # a) Subscribe to task updates via webhook (task.subscribe)
        # b) Poll for task status at reasonable intervals
        # Here we'll demonstrate polling
        
        for attempt in range(1, 4):
            print(f"Polling attempt {attempt}... ", end="", flush=True)
            
            get_params = TaskInfoParams(taskId=task_id)
            get_response = await client.task.info(get_params, trace_id=trace_id)
            
            updated_task = get_response.get('task', {})
            status = updated_task.get('status', 'unknown')
            
            print(f"Status: {status}")
            
            if status in ['completed', 'failed', 'cancelled']:
                # Task is in a terminal state
                break
                
            # In real application, use appropriate backoff strategy
            await asyncio.sleep(1)  # Simple delay for demo
        
        # Get final results
        print("\n📊 Final task status:")
        get_params = TaskInfoParams(taskId=task_id)
        final_response = await client.task.info(get_params, trace_id=trace_id)
        
        final_task = final_response.get('task', {})
        final_status = final_task.get('status', 'unknown')
        print(f"Status: {final_status}")
        
        # Extract results from the final messages
        print("\n📝 Task Results:")
        messages = final_task.get('messages', [])
        message_count = len(messages)
        print(f"Total messages: {message_count}")
        
        if message_count > 0:
            # Show the last agent message as the result
            agent_messages = [msg for msg in messages if msg.get('role') == 'agent']
            if agent_messages:
                latest_msg = agent_messages[-1]
                for part in latest_msg.get('parts', []):
                    if part.get('type') == 'TextPart':
                        content = part.get('content', '')
                        print(f"\n🤖 Agent result:\n{content}")
        
        # Show artifacts if any
        artifacts = final_task.get('artifacts', [])
        if artifacts:
            print(f"\n📎 Task produced {len(artifacts)} artifacts:")
            for artifact in artifacts:
                print(f"  - {artifact.get('name', 'unnamed')}: {artifact.get('mimeType', 'unknown type')}")
        
    except Exception as e:
        print(f"\n❌ Error in task demo: {e}")
    finally:
        # Clean up
        await client.close()


if __name__ == "__main__":
    asyncio.run(task_creation_demo())
