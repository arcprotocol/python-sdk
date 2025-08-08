#!/usr/bin/env python3
"""
ARC Protocol - Streaming Data Example

This example demonstrates how to stream large data sets in chunks using
the ARC protocol's streaming capabilities. It shows:

1. Starting a new stream session
2. Breaking large data into manageable chunks
3. Sending sequential chunks with proper metadata
4. Processing streaming responses in real-time
5. Properly closing the stream

To run this example:
1. Start an ARC compatible server 
2. Configure your OAuth2 environment variables
3. Run this script: python streaming_data.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import StreamStartParams, StreamChunkParams, StreamEndParams
from arc.models.generated import Message, Part, Role, Type
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration
TARGET_AGENT = "data-processor-agent"  # The agent that will process our data
REQUEST_AGENT = "data-sender-client"    # Our client's agent ID
CHUNK_SIZE = 1000  # Characters per chunk for demonstration


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


def generate_sample_data() -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Generate sample data for streaming.
    
    Returns:
        Union[Dict[str, Any], List[Dict[str, Any]]]: Sample data structure
    """
    # Sample dataset - in a real application this could be:
    # - Large JSON datasets
    # - Logs being processed in real-time
    # - Sensor readings
    # - ML model predictions
    # - Video/audio transcription results
    
    # For this example, we'll create a mock dataset of sensor readings
    readings = []
    for i in range(1, 501):  # 500 sample readings
        readings.append({
            "timestamp": f"2023-11-01T{i//60:02d}:{i%60:02d}:00Z",
            "sensorId": f"SENSOR-{(i%5)+1:02d}",
            "temperature": 20 + (i % 10) + ((i % 7) / 10),
            "humidity": 45 + ((i % 15) - 7),
            "pressure": 1010 + ((i % 20) - 10),
            "metadata": {
                "location": f"Zone-{(i%3)+1}",
                "deviceType": "TempSensor-V2",
                "batteryLevel": 100 - (i % 30),
                "signalStrength": "strong" if i % 4 != 0 else "medium"
            }
        })
    
    return {
        "facility": "Manufacturing Plant A",
        "dataType": "environmental",
        "unit": "standard",
        "readings": readings,
        "totalReadings": len(readings)
    }


def chunk_data(data: Union[Dict[str, Any], List[Dict[str, Any]], str], chunk_size: int) -> List[str]:
    """
    Break down large data into manageable chunks.
    
    Args:
        data: The data to chunk
        chunk_size: Maximum characters per chunk
        
    Returns:
        List of string chunks
    """
    # Convert data to JSON string if it's not already a string
    if not isinstance(data, str):
        data_str = json.dumps(data)
    else:
        data_str = data
    
    # Split the JSON string into chunks of approximately chunk_size
    chunks = []
    for i in range(0, len(data_str), chunk_size):
        chunks.append(data_str[i:i+chunk_size])
    
    return chunks


async def streaming_data_demo():
    """
    Demonstrate streaming large data sets in chunks using ARC protocol.
    """
    print("🚀 ARC Protocol - Streaming Data Example")
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
        # 1. Start a new stream session
        stream_start_params = StreamStartParams(
            participants=[REQUEST_AGENT, TARGET_AGENT],
            metadata={
                "dataType": "sensor_readings",
                "format": "json",
                "version": "1.0",
                "timestamp": datetime.now().isoformat()
            }
        )
        
        stream_response = await client.stream.start(stream_start_params)
        stream_id = stream_response.get("stream", {}).get("streamId")
        
        if not stream_id:
            print("❌ Failed to start stream session")
            return
        
        print(f"✅ Stream session started with ID: {stream_id}")
        
        # 2. Generate sample data
        print("\n📊 Generating sample data...")
        data = generate_sample_data()
        
        # 3. Break data into chunks
        print(f"📦 Breaking data into chunks (max {CHUNK_SIZE} chars each)...")
        chunks = chunk_data(data, CHUNK_SIZE)
        print(f"   Total chunks: {len(chunks)}")
        
        # 4. Send data chunks sequentially
        print("\n🔄 Sending data chunks:")
        for i, chunk_data in enumerate(chunks):
            is_last_chunk = i == len(chunks) - 1
            
            # Create chunked message
            chunk_params = StreamChunkParams(
                streamId=stream_id,
                chunk=Message(
                    role=Role.user,
                    parts=[Part(
                        type=Type.data_part,
                        content=chunk_data,
                        mimeType="application/json"
                    )]
                ),
                sequence=i + 1,  # 1-based sequence
                isLast=is_last_chunk
            )
            
            # Send the chunk
            print(f"   Sending chunk {i+1}/{len(chunks)} ({len(chunk_data)} chars)... ", end="", flush=True)
            chunk_response = await client.stream.chunk(chunk_params)
            print("✓")
            
            # In a real application, you might want to:
            # - Check for processing errors
            # - Handle rate limiting
            # - Implement backoff/retry logic
            # Here we just add a small delay to avoid overwhelming the server
            await asyncio.sleep(0.1)
        
        # 5. End the stream session properly
        print("\n🏁 All chunks sent successfully!")
        print("Ending stream session...")
        
        end_params = StreamEndParams(
            streamId=stream_id,
            reason="Data transmission complete"
        )
        await client.stream.end(end_params)
        print("✅ Stream session ended successfully")
        
        # 6. In a real application, you would typically receive processing results
        # from the agent via a webhook or by polling a task endpoint
        print("\n📈 In a production environment, you would now:")
        print("   1. Receive processing confirmation from the agent")
        print("   2. Get results via webhook notification or by polling")
        print("   3. Handle any processing errors")
        
    except Exception as e:
        print(f"\n❌ Error in streaming session: {e}")
    finally:
        # Clean up
        await client.close()


if __name__ == "__main__":
    asyncio.run(streaming_data_demo())
