"""
Server-Sent Events (SSE) support for ARC server.

Provides utilities for sending streaming responses using the SSE protocol.
"""

import json
import asyncio
from typing import Dict, Any, Optional, AsyncIterable, Union

from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.types import Send


class SSEResponse(StreamingResponse):
    """
    Server-Sent Events (SSE) streaming response.
    
    Extends FastAPI's StreamingResponse to implement the SSE protocol
    for streaming chat responses.
    """
    
    def __init__(
        self,
        content: AsyncIterable[Dict[str, Any]],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize SSE response.
        
        Args:
            content: Async iterable yielding message chunks
            status_code: HTTP status code
            headers: Additional HTTP headers
        """
        self.content_iterator = content
        
        # Set SSE-specific headers
        _headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
        
        if headers:
            _headers.update(headers)
            
        super().__init__(
            content=self._sse_content(),
            status_code=status_code,
            media_type="text/event-stream",
            headers=_headers
        )

    async def _sse_content(self):
        """
        Generate SSE content from the content iterator.
        """
        try:
            async for chunk in self.content_iterator:
                # Convert chunk to SSE format
                yield self._format_sse_event(chunk)
                
                # Ensure chunks are sent immediately
                await asyncio.sleep(0)
                
        except Exception as e:
            # If there's an error, send an error event
            error_event = {
                "event": "error",
                "data": {"message": str(e)}
            }
            yield self._format_sse_event(error_event)
            
        # Always send a done event at the end
        done_event = {
            "event": "done",
            "data": {"done": True}
        }
        yield self._format_sse_event(done_event)
        
    def _format_sse_event(self, chunk: Dict[str, Any]) -> str:
        """
        Format a chunk as an SSE event.
        
        Args:
            chunk: Event data to format
            
        Returns:
            Formatted SSE event string
        """
        event_type = chunk.get("event", "stream")
        data = chunk.get("data", {})
        
        # Format as SSE
        formatted = f"event: {event_type}\n"
        
        # Convert data to JSON string
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data)
        else:
            data_str = str(data)
            
        # Split data into multiple data: lines if needed
        formatted += f"data: {data_str}\n\n"
        
        return formatted
        

def create_chat_stream(
    chat_id: str, 
    message_generator: AsyncIterable[Dict[str, Any]]
) -> SSEResponse:
    """
    Create an SSE response for streaming chat messages.
    
    Args:
        chat_id: Chat identifier
        message_generator: Async generator yielding message parts
        
    Returns:
        SSE streaming response
    """
    async def sse_events():
        async for message_part in message_generator:
            # Format as a stream event
            yield {
                "event": "stream",
                "data": {
                    "chatId": chat_id,
                    "message": message_part
                }
            }
    
    return SSEResponse(sse_events())