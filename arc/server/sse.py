"""
Server-Sent Events (SSE) support for ARC server.

Provides utilities for sending streaming responses using the SSE protocol.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, AsyncIterable, Union, Callable, TypeVar, Generator

from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.types import Send

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SSEResponse(StreamingResponse):
    # Make sure it's recognized as a StreamingResponse by the server
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
                formatted_event = self._format_sse_event(chunk)
                yield formatted_event.encode('utf-8')
                
                # Yield control to allow immediate sending (no artificial delay)
                await asyncio.sleep(0)
                
        except Exception as e:
            # If there's an error, send an error event
            logger.error(f"SSE streaming error: {str(e)}")
            error_event = {
                "event": "error",
                "data": {"message": str(e), "code": -43005}
            }
            yield self._format_sse_event(error_event).encode('utf-8')
            
        # Note: Don't send automatic done event here - let the generator handle it
        
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
        
        # Convert data to JSON string (compact, single-line)
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, separators=(',', ':'))
        else:
            data_str = str(data)
        
        # Single data line (our JSON is always single-line)
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


def create_sse_response(content_generator: AsyncIterable[str]) -> SSEResponse:
    """
    Create a Server-Sent Events (SSE) response from a content generator.
    
    This is a general-purpose function to create an SSE response from any
    content generator that yields formatted SSE event strings.
    
    Args:
        content_generator: Async generator yielding formatted SSE event strings
        
    Returns:
        SSE streaming response
    """
    async def sse_stream():
        async for event_str in content_generator:
            # The generator should already provide properly formatted SSE event strings
            # We just pass them through as is
            yield {
                "raw": True,  # Flag to indicate pre-formatted event
                "content": event_str
            }
    
    # Create a custom wrapper to handle pre-formatted events
    class FormattedSSEResponse(SSEResponse):
        def _format_sse_event(self, chunk: Dict[str, Any]) -> str:
            # If this is a pre-formatted event string, return it directly
            if chunk.get("raw"):
                return chunk.get("content", "")
            # Otherwise, format normally
            return super()._format_sse_event(chunk)
    
    return FormattedSSEResponse(sse_stream())


def stream_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Format an event and data as a SSE event string.
    
    Args:
        event_type: Type of event (e.g., 'stream', 'done')
        data: Event data to send
        
    Returns:
        Formatted SSE event string
    """
    # Format as SSE
    formatted = f"event: {event_type}\n"
    
    # Convert data to JSON string (compact, single-line)
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, separators=(',', ':'))
    else:
        data_str = str(data)
    
    # Single data line (our JSON is always single-line)
    formatted += f"data: {data_str}\n\n"
    
    return formatted