#!/usr/bin/env python3
"""
ARC Protocol - Multi-Agent Workflow Example

This example demonstrates how to use the ARC protocol to orchestrate a workflow
involving multiple specialized agents working together. It shows:

1. Task creation and delegation between multiple agents
2. Task chaining (using output from one agent as input to another)
3. Parallel processing with multiple agents
4. Result aggregation
5. Using trace ID for end-to-end workflow tracking

Multi-agent workflows allow for complex business processes to be broken down into
steps handled by specialized agents, combining their capabilities for comprehensive solutions.

To run this example:
1. Start ARC compatible servers for each agent (or simulate with a single server)
2. Configure your OAuth2 environment variables
3. Run this script: python multi_agent_workflow.py
"""

import asyncio
import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Set

# Import ARC SDK
from arc import ARCClient
from arc.models.generated import TaskCreateParams, TaskInfoParams
from arc.models.generated import Message, Part, Role, Type
from arc.auth.oauth2_client import OAuth2ClientCredentials, create_oauth2_client


# Configuration for our workflow
COORDINATOR_AGENT = "workflow-coordinator"   # Our client acting as workflow coordinator
AGENTS = {
    "data-extraction": {
        "id": "data-extraction-agent",
        "url": os.getenv("DATA_EXTRACTION_AGENT_URL", "http://localhost:8001")
    },
    "data-analysis": {
        "id": "data-analysis-agent",
        "url": os.getenv("DATA_ANALYSIS_AGENT_URL", "http://localhost:8002")
    },
    "report-generation": {
        "id": "report-generation-agent", 
        "url": os.getenv("REPORT_AGENT_URL", "http://localhost:8003")
    }
}


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
        
        # Clean up OAuth client
        await oauth_client.close()
        return oauth_token
        
    except Exception as e:
        print(f"❌ Failed to get OAuth2 token: {e}")
        return None


def generate_workflow_input() -> Dict[str, Any]:
    """
    Generate the initial input for our workflow.
    """
    # This would typically come from user input or external systems
    # For this demo, we'll create a sample request for analyzing sales data
    return {
        "request_type": "quarterly_sales_report",
        "data_source": {
            "type": "database",
            "connection": "sales_db",
            "table": "quarterly_transactions",
            "time_range": {
                "start": "2023-01-01",
                "end": "2023-12-31"
            }
        },
        "analysis_requirements": [
            "revenue_by_region",
            "top_products",
            "growth_trends",
            "customer_segments"
        ],
        "report_format": "executive_summary",
        "visualization_required": True
    }


async def poll_task_until_complete(client: ARCClient, task_id: str, trace_id: str, 
                                 max_attempts: int = 10, delay_seconds: int = 2) -> Dict[str, Any]:
    """
    Poll a task until it's complete or failed.
    
    Args:
        client: The ARC client to use
        task_id: The ID of the task to poll
        trace_id: Trace ID for tracking the request
        max_attempts: Maximum number of polling attempts
        delay_seconds: Delay between polling attempts
        
    Returns:
        The completed task data or empty dict if failed
    """
    get_params = TaskInfoParams(taskId=task_id)
    
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.task.info(get_params, trace_id=trace_id)
            task_data = response.get('task', {})
            status = task_data.get('status', 'unknown')
            
            print(f"   [{attempt}/{max_attempts}] Task {task_id}: {status}")
            
            if status in ['completed', 'failed', 'cancelled']:
                return task_data
                
            await asyncio.sleep(delay_seconds)
            
        except Exception as e:
            print(f"   ❌ Error polling task {task_id}: {e}")
            await asyncio.sleep(delay_seconds)
    
    print(f"   ⚠️ Reached maximum polling attempts for task {task_id}")
    return {}


def extract_result_content(task_data: Dict[str, Any], content_type: str = 'text') -> Optional[str]:
    """
    Extract content from a completed task.
    
    Args:
        task_data: The task data response
        content_type: The type of content to extract ('text' or 'data')
        
    Returns:
        The extracted content or None if not found
    """
    if not task_data:
        return None
        
    messages = task_data.get('messages', [])
    agent_messages = [msg for msg in messages if msg.get('role') == 'agent']
    
    if not agent_messages:
        return None
        
    # Get the last agent message
    last_message = agent_messages[-1]
    
    for part in last_message.get('parts', []):
        part_type = part.get('type')
        
        if (content_type == 'text' and part_type == 'TextPart') or \
           (content_type == 'data' and part_type == 'DataPart'):
            return part.get('content')
            
    return None


async def multi_agent_workflow_demo():
    """
    Demonstrate a multi-agent workflow using ARC protocol.
    """
    print("🚀 ARC Protocol - Multi-Agent Workflow Example")
    print("=" * 60)
    
    # Get OAuth token
    oauth_token = await setup_oauth2_client()
    if not oauth_token:
        print("Cannot continue without authentication")
        return
    
    # Create shared trace ID for the entire workflow
    workflow_trace_id = f"workflow-{str(uuid.uuid4())[:8]}"
    print(f"📝 Workflow Trace ID: {workflow_trace_id}")
    
    # Initialize clients for each agent
    clients = {}
    for role, agent_info in AGENTS.items():
        try:
            # Determine if we need to allow HTTP for local testing
            allow_http = agent_info["url"].startswith("http://")
            
            clients[role] = ARCClient(
                base_url=agent_info["url"],
                request_agent=COORDINATOR_AGENT,
                target_agent=agent_info["id"],
                oauth_token=oauth_token,
                allow_http=allow_http
            )
            print(f"✅ Connected to {role} agent: {agent_info['id']}")
        except Exception as e:
            print(f"❌ Failed to initialize client for {role} agent: {e}")
            return
    
    try:
        # =====================================================================
        # STEP 1: Data Extraction Task - Get data from the source
        # =====================================================================
        print("\n📊 STEP 1: Initiating Data Extraction")
        print("-" * 60)
        
        # Generate the initial workflow input
        workflow_input = generate_workflow_input()
        
        # Create task for data extraction agent
        extraction_params = TaskCreateParams(
            initialMessage=Message(
                role=Role.user,
                parts=[
                    Part(
                        type=Type.text_part,
                        content="Extract quarterly sales data according to the provided specifications"
                    ),
                    Part(
                        type=Type.data_part,
                        content=json.dumps(workflow_input),
                        mimeType="application/json"
                    )
                ]
            ),
            metadata={
                "workflow_id": workflow_trace_id,
                "step": "data_extraction"
            }
        )
        
        # Send task to data extraction agent
        extraction_client = clients["data-extraction"]
        extraction_response = await extraction_client.task.create(
            extraction_params, trace_id=workflow_trace_id
        )
        
        extraction_task_id = extraction_response.get("task", {}).get("taskId")
        if not extraction_task_id:
            print("❌ Data extraction task creation failed")
            return
            
        print(f"✅ Data extraction task created: {extraction_task_id}")
        
        # Wait for extraction task to complete
        print("⏳ Waiting for data extraction to complete...")
        extraction_result = await poll_task_until_complete(
            extraction_client, extraction_task_id, workflow_trace_id
        )
        
        # Extract data content from the extraction task result
        extracted_data_json = extract_result_content(extraction_result, "data")
        if not extracted_data_json:
            print("❌ Failed to get extracted data from task")
            return
            
        # Parse the extracted data
        try:
            extracted_data = json.loads(extracted_data_json)
            print("✅ Data successfully extracted")
            record_count = len(extracted_data.get("records", []))
            print(f"📊 Extracted {record_count} records")
        except json.JSONDecodeError:
            print("❌ Failed to parse extracted data")
            return
        
        # =====================================================================
        # STEP 2: Parallel Data Analysis - Process data with multiple specialized analyses
        # =====================================================================
        print("\n📈 STEP 2: Performing Parallel Data Analysis")
        print("-" * 60)
        
        # For demonstration, we'll launch two different analyses in parallel
        analysis_types = ["revenue_trends", "product_performance"]
        analysis_tasks = {}
        analysis_client = clients["data-analysis"]
        
        # Create and launch analysis tasks in parallel
        async def launch_analysis(analysis_type):
            analysis_params = TaskCreateParams(
                initialMessage=Message(
                    role=Role.user,
                    parts=[
                        Part(
                            type=Type.text_part,
                            content=f"Perform {analysis_type} analysis on the provided data"
                        ),
                        Part(
                            type=Type.data_part,
                            content=extracted_data_json,
                            mimeType="application/json"
                        )
                    ]
                ),
                metadata={
                    "workflow_id": workflow_trace_id,
                    "step": f"analysis_{analysis_type}",
                    "analysis_type": analysis_type
                }
            )
            
            response = await analysis_client.task.create(
                analysis_params, trace_id=workflow_trace_id
            )
            
            task_id = response.get("task", {}).get("taskId")
            if task_id:
                print(f"✅ {analysis_type.title()} analysis task created: {task_id}")
                return task_id
            else:
                print(f"❌ {analysis_type.title()} analysis task creation failed")
                return None
        
        # Launch all analysis tasks in parallel
        analysis_tasks_futures = [launch_analysis(analysis_type) for analysis_type in analysis_types]
        analysis_task_ids = await asyncio.gather(*analysis_tasks_futures)
        
        # Filter out failed tasks
        analysis_task_ids = [task_id for task_id in analysis_task_ids if task_id]
        
        if not analysis_task_ids:
            print("❌ All analysis tasks failed to start")
            return
        
        # Wait for all analysis tasks to complete
        print("⏳ Waiting for all analysis tasks to complete...")
        
        async def wait_for_analysis(task_id):
            result = await poll_task_until_complete(
                analysis_client, task_id, workflow_trace_id
            )
            return task_id, result
        
        analysis_results_futures = [wait_for_analysis(task_id) for task_id in analysis_task_ids]
        analysis_results = await asyncio.gather(*analysis_results_futures)
        
        # Build a map of task IDs to results
        analysis_data = {}
        for task_id, result in analysis_results:
            # Extract result content (both text and data)
            text_content = extract_result_content(result, "text")
            data_content_json = extract_result_content(result, "data")
            
            try:
                if data_content_json:
                    data_content = json.loads(data_content_json)
                else:
                    data_content = {}
                    
                analysis_data[task_id] = {
                    "text": text_content,
                    "data": data_content,
                    "task_id": task_id
                }
                print(f"✅ Analysis results received for task: {task_id}")
            except json.JSONDecodeError:
                print(f"❌ Failed to parse analysis results for task: {task_id}")
        
        if not analysis_data:
            print("❌ No analysis results available")
            return
            
        # Combine all analysis results
        combined_analysis = {
            "timestamp": datetime.now().isoformat(),
            "source": "multi-agent-workflow",
            "workflow_id": workflow_trace_id,
            "analyses": list(analysis_data.values())
        }
        
        # =====================================================================
        # STEP 3: Report Generation - Create final output based on analyses
        # =====================================================================
        print("\n📝 STEP 3: Generating Final Report")
        print("-" * 60)
        
        # Create task for report generation
        report_params = TaskCreateParams(
            initialMessage=Message(
                role=Role.user,
                parts=[
                    Part(
                        type=Type.text_part,
                        content="Generate a comprehensive report based on the provided analyses"
                    ),
                    Part(
                        type=Type.data_part,
                        content=json.dumps(combined_analysis),
                        mimeType="application/json"
                    )
                ]
            ),
            metadata={
                "workflow_id": workflow_trace_id,
                "step": "report_generation",
                "format": workflow_input.get("report_format", "executive_summary")
            }
        )
        
        # Send task to report generation agent
        report_client = clients["report-generation"]
        report_response = await report_client.task.create(
            report_params, trace_id=workflow_trace_id
        )
        
        report_task_id = report_response.get("task", {}).get("taskId")
        if not report_task_id:
            print("❌ Report generation task creation failed")
            return
            
        print(f"✅ Report generation task created: {report_task_id}")
        
        # Wait for report generation to complete
        print("⏳ Waiting for report generation to complete...")
        report_result = await poll_task_until_complete(
            report_client, report_task_id, workflow_trace_id
        )
        
        # Extract report content
        final_report = extract_result_content(report_result, "text")
        
        # =====================================================================
        # WORKFLOW SUMMARY
        # =====================================================================
        print("\n🎉 WORKFLOW COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Workflow ID: {workflow_trace_id}")
        print(f"Total agents involved: {len(AGENTS)}")
        print("Completed steps:")
        print(f"  1. Data Extraction (Task: {extraction_task_id})")
        print(f"  2. Parallel Analysis ({len(analysis_task_ids)} tasks)")
        for i, task_id in enumerate(analysis_task_ids):
            print(f"     {i+1}. {analysis_types[i]} (Task: {task_id})")
        print(f"  3. Report Generation (Task: {report_task_id})")
        
        print("\n📄 FINAL REPORT SUMMARY:")
        if final_report:
            # Show first few lines of the report
            report_lines = final_report.split("\n")
            preview_lines = min(10, len(report_lines))
            print("\n".join(report_lines[:preview_lines]))
            if len(report_lines) > preview_lines:
                print("... [report truncated] ...")
        else:
            print("Report content not available")
        
    except Exception as e:
        print(f"\n❌ Error in workflow: {e}")
    finally:
        # Clean up clients
        for client in clients.values():
            await client.close()


if __name__ == "__main__":
    asyncio.run(multi_agent_workflow_demo())
