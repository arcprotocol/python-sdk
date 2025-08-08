"""
ARC Client Streaming Utilities

Provides utilities for handling Server-Sent Events (SSE) and streaming responses
in the ARC protocol.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator, List, Union

import httpx

from ..exceptions import ParseError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)


class SSEParser:
    """
    Parser for Server-Sent Events (SSE) format.
    
    Processes raw event stream chunks into structured event data.
    """
    
    def __init__(self):
        """Initialize the SSE parser with an empty buffer."""
        self.buffer = ""
        self.complete_text = ""
    
    def feed(self, chunk: str) -> List[Dict[str, Any]]:
        """
        Process a chunk of SSE data.
        
        Args:
            chunk: Raw SSE data
            
        Returns:
            List of parsed events
        """
        events = []
        
        # Add chunk to buffer
        self.buffer += chunk
        
        # Process complete events (split by double newline)
        parts = self.buffer.split('\n\n')
        if len(parts) > 1:
            # Last part might be incomplete
            self.buffer = parts.pop()
            
            # Process complete parts
            for part in parts:
                event = self._parse_event(part)
                if event:
                    events.append(event)
                    
                    # Track complete content for chat responses
                    if self._is_text_content(event):
                        self.complete_text += self._extract_text_content(event)
        
        return events
    
    def _parse_event(self, event_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single SSE event.
        
        Args:
            event_text: Raw event text
            
        Returns:
            Parsed event or None if invalid
        """
        lines = event_text.strip().split('\n')
        event_type = None
        data = None
        
        for line in lines:
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data_text = line[5:].strip()
                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError:
                    data = data_text
        
        if event_type and data is not None:
            return {
                'event': event_type,
                'data': data
            }
        
        return None
    
    def _is_text_content(self, event: Dict[str, Any]) -> bool:
        """Check if the event contains text content from a chat message."""
        if event.get('event') != 'stream':
            return False
            
        data = event.get('data', {})
        if not isinstance(data, dict):
            return False
            
        message = data.get('message', {})
        if not isinstance(message, dict):
            return False
            
        parts = message.get('parts', [])
        if not parts or not isinstance(parts, list):
            return False
            
        return any(
            isinstance(p, dict) and 
            p.get('type') == 'TextPart' and 
            'content' in p
            for p in parts
        )
    
    def _extract_text_content(self, event: Dict[str, Any]) -> str:
        """Extract text content from a chat message event."""
        try:
            message = event['data']['message']
            for part in message['parts']:
                if part.get('type') == 'TextPart' and 'content' in part:
                    return part['content']
        except (KeyError, TypeError, IndexError):
            pass
            
        return ""


async def stream_response(
    client: httpx.AsyncClient,
    endpoint: str,
    request_data: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float
) -> AsyncIterator[Dict[str, Any]]:
    """
    Handle streaming responses using Server-Sent Events (SSE).
    
    Args:
        client: HTTP client
        endpoint: API endpoint URL
        request_data: The ARC request data
        headers: HTTP headers
        timeout: Request timeout in seconds
        
    Yields:
        Parsed SSE events
    """
    parser = SSEParser()
    
    try:
        async with client.stream(
            'POST',
            endpoint,
            json=request_data,
            headers=headers,
            timeout=timeout
        ) as response:
            # Check response status
            response.raise_for_status()
            
            # Process the stream
            async for chunk in response.aiter_text():
                events = parser.feed(chunk)
                
                # Yield each parsed event
                for event in events:
                    yield event
                    
                    # Check for stream completion
                    if event.get('event') == 'done':
                        return
                    
    except httpx.HTTPStatusError as e:
        raise ConnectionError(f"HTTP error: {e.response.status_code} - {str(e)}")
    except httpx.RequestError as e:
        raise ConnectionError(f"Connection error: {str(e)}")
    except httpx.TimeoutException:
        raise TimeoutError(f"Request timed out after {timeout} seconds")
    except Exception as e:
        raise ParseError(f"Error processing stream: {str(e)}")
        
    # Make sure we process any remaining data in the buffer
    if parser.buffer:
        event = parser._parse_event(parser.buffer)
        if event:
            yield event