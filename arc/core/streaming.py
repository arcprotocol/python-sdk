"""
ARC Streaming Module

Provides support for real-time streaming communication in the ARC protocol.
Includes utilities for handling streaming responses, content generators, and
standardized streaming patterns.
"""

import asyncio
import json
import logging
import uuid
import time
from typing import Dict, Any, Optional, Union, List, Callable, AsyncGenerator, AsyncIterable

from ..exceptions import (
    StreamNotFoundError, StreamAlreadyClosedError, InvalidStreamMessageError,
    StreamTimeoutError
)
from ..server.sse import stream_event


logger = logging.getLogger(__name__)


# --- Core SSE Protocol Utilities ---


async def generate_sse_events(
    chat_id: str,
    content_generator: AsyncIterable[str],
    role: str = "agent",
    request_id: Optional[str] = None,
    content_type: str = "TextPart"
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events (SSE) for streaming chat content.
    
    This helper transforms a content generator into properly formatted
    SSE events following the ARC protocol streaming format.
    
    Args:
        chat_id: Chat identifier
        content_generator: Async generator yielding content strings
        role: Message role (default: "agent")
        request_id: Original request ID for the done event
        content_type: Content part type (default: "TextPart")
        
    Yields:
        Properly formatted SSE event strings ready for streaming
    """
    # Stream each content update - no initial empty event needed
    async for content in content_generator:
        chat_data = {
            "chatId": chat_id,
            "message": {
                "role": role,
                "parts": [{
                    "type": content_type,
                    "content": content
                }]
            }
        }
        # Use stream_event to format SSE event
        yield stream_event("stream", chat_data)
    
    # Final done event
    done_data = {"chatId": chat_id, "status": "ACTIVE", "done": True}
    if request_id:
        done_data["requestId"] = request_id
    yield stream_event("done", done_data)




async def create_chat_stream_generator(
    chat_id: str,
    content_generator: AsyncGenerator[str, None],
    request_id: Optional[str] = None,
    role: str = "agent"
) -> AsyncGenerator[str, None]:
    """
    Create a generator for streaming a chat message using the ARC protocol format.
    
    This utility takes a content generator from the agent and formats it as
    proper SSE events following the ARC protocol streaming specification.
    
    Args:
        chat_id: Chat identifier
        content_generator: Agent's content generator (true streaming source)
        request_id: Request ID for the done event
        role: Message role (default: "agent")
        
    Returns:
        Async generator yielding SSE event strings
        
    Raises:
        ValueError: If chat_id is empty or invalid
    """
    if not chat_id or not isinstance(chat_id, str):
        raise ValueError("chat_id must be a non-empty string")
    
    if not content_generator:
        raise ValueError("content_generator is required for streaming")
    
    try:
        # Create SSE event generator from the agent's content stream
        async for event in generate_sse_events(chat_id, content_generator, role, request_id):
            yield event
            
    except Exception as e:
        # Send error event and close gracefully
        error_data = {
            "chatId": chat_id,
            "error": {
                "code": -43005,  # ARC chat error code
                "message": f"Stream error: {str(e)}"
            }
        }
        yield stream_event("error", error_data)
        
        # Send done event to close stream
        done_data = {"chatId": chat_id, "status": "ERROR", "done": True}
        if request_id:
            done_data["requestId"] = request_id
        yield stream_event("done", done_data)


# --- Client-side Streaming Parser ---

class SSEParser:
    """
    Parser for Server-Sent Events (SSE) received from an ARC server.
    
    This utility helps client applications parse and process SSE
    events according to the ARC protocol format.
    """
    
    @staticmethod
    def parse_chunk(chunk: Union[str, Dict[str, Any]]) -> tuple:
        """
        Parse an SSE chunk into event type and data.
        
        Handles both dictionary objects and string SSE formats.
        
        Args:
            chunk: Raw chunk from SSE stream (string or dict)
            
        Returns:
            Tuple of (event_type, event_data)
        """
        event_type = None
        event_data = {}
        
        # If it's already a dictionary (e.g., from httpx parsing)
        if isinstance(chunk, dict):
            event_type = chunk.get('event')
            event_data = chunk.get('data', {})
            return event_type, event_data
            
        # If it's a string in SSE format: "event: type\ndata: {...}"
        elif isinstance(chunk, str) and chunk.startswith('event: '):
            lines = chunk.strip().split('\n')
            
            for line in lines:
                if line.startswith('event: '):
                    event_type = line[7:].strip()
                elif line.startswith('data: '):
                    try:
                        data_str = line[6:].strip()
                        event_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        # If not valid JSON, treat as raw string
                        event_data = {'raw': data_str}
        
        return event_type, event_data
    
    @staticmethod
    def extract_content(event_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract text content from an ARC protocol SSE message.
        
        Args:
            event_data: Parsed event data
            
        Returns:
            Extracted text content or None if not found
        """
        if "message" in event_data and "parts" in event_data["message"]:
            for part in event_data["message"]["parts"]:
                if part.get("type") == "TextPart" and "content" in part:
                    return part["content"]
        return None


class StreamManager:
    """
    Manages active stream sessions for ARC real-time communication.
    
    Provides functionality for:
    - Creating and tracking stream sessions
    - Sending messages in streams
    - Handling stream chunks
    - Closing streams
    """
    
    def __init__(self, agent_id: str):
        """
        Initialize stream manager.
        
        Args:
            agent_id: ID of this agent
        """
        self.agent_id = agent_id
        self.active_streams: Dict[str, Dict[str, Any]] = {}
    
    def create_stream(self, target_agent: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new stream session.
        
        Args:
            target_agent: ID of agent to communicate with
            metadata: Optional stream metadata
            
        Returns:
            Stream object with stream ID
        """
        stream_id = f"stream-{uuid.uuid4().hex[:8]}"
        created_at = self._get_timestamp()
        
        stream = {
            "streamId": stream_id,
            "status": "ACTIVE",
            "targetAgent": target_agent,
            "createdAt": created_at,
            "metadata": metadata or {},
            "chunks": [],
            "sequence": 0
        }
        
        self.active_streams[stream_id] = stream
        logger.info(f"Created stream {stream_id} with {target_agent}")
        
        return {
            "streamId": stream_id,
            "status": "ACTIVE",
            "createdAt": created_at
        }
    
    def get_stream(self, stream_id: str) -> Dict[str, Any]:
        """
        Get stream information.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            Stream object
            
        Raises:
            StreamNotFoundError: If stream doesn't exist
        """
        if stream_id not in self.active_streams:
            raise StreamNotFoundError(stream_id, f"Stream not found: {stream_id}")
        
        stream = self.active_streams[stream_id]
        
        return {
            "streamId": stream["streamId"],
            "status": stream["status"],
            "targetAgent": stream["targetAgent"],
            "createdAt": stream["createdAt"]
        }
    
    def end_stream(self, stream_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        End an active stream.
        
        Args:
            stream_id: Stream identifier
            reason: Optional reason for ending the stream
            
        Returns:
            Updated stream object
            
        Raises:
            StreamNotFoundError: If stream doesn't exist
            StreamAlreadyClosedError: If stream is already closed
        """
        if stream_id not in self.active_streams:
            raise StreamNotFoundError(stream_id, f"Stream not found: {stream_id}")
        
        stream = self.active_streams[stream_id]
        
        if stream["status"] == "CLOSED":
            raise StreamAlreadyClosedError(stream_id, f"Stream already closed: {stream_id}")
        
        # Update stream
        stream["status"] = "CLOSED"
        stream["closedAt"] = self._get_timestamp()
        if reason:
            stream["reason"] = reason
        
        logger.info(f"Ended stream {stream_id}")
        
        return {
            "streamId": stream["streamId"],
            "status": "CLOSED",
            "closedAt": stream["closedAt"],
            "reason": reason
        }
    
    def add_chunk(
        self, 
        stream_id: str, 
        chunk: Dict[str, Any], 
        is_last: bool = False
    ) -> Dict[str, Any]:
        """
        Add a message chunk to a stream.
        
        Args:
            stream_id: Stream identifier
            chunk: Message chunk to add
            is_last: Whether this is the final chunk
            
        Returns:
            Chunk metadata with sequence number
            
        Raises:
            StreamNotFoundError: If stream doesn't exist
            StreamAlreadyClosedError: If stream is closed
        """
        if stream_id not in self.active_streams:
            raise StreamNotFoundError(stream_id, f"Stream not found: {stream_id}")
        
        stream = self.active_streams[stream_id]
        
        if stream["status"] == "CLOSED":
            raise StreamAlreadyClosedError(stream_id, f"Cannot add chunk to closed stream: {stream_id}")
        
        # Get next sequence number
        sequence = stream["sequence"] + 1
        stream["sequence"] = sequence
        
        # Add timestamp
        chunk_with_meta = chunk.copy()
        chunk_with_meta["timestamp"] = self._get_timestamp()
        chunk_with_meta["sequence"] = sequence
        chunk_with_meta["isLast"] = is_last
        
        # Store chunk
        stream["chunks"].append(chunk_with_meta)
        
        # If this is the last chunk, close the stream
        if is_last:
            stream["status"] = "COMPLETED"
            stream["completedAt"] = chunk_with_meta["timestamp"]
        
        return {
            "sequence": sequence,
            "isLast": is_last,
            "timestamp": chunk_with_meta["timestamp"]
        }
    
    def get_chunks(
        self, 
        stream_id: str, 
        since_sequence: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get chunks from a stream.
        
        Args:
            stream_id: Stream identifier
            since_sequence: Get chunks after this sequence number
            
        Returns:
            List of chunks
            
        Raises:
            StreamNotFoundError: If stream doesn't exist
        """
        if stream_id not in self.active_streams:
            raise StreamNotFoundError(stream_id, f"Stream not found: {stream_id}")
        
        stream = self.active_streams[stream_id]
        
        # Filter chunks by sequence
        chunks = [
            chunk for chunk in stream["chunks"]
            if chunk["sequence"] > since_sequence
        ]
        
        return chunks
    
    def get_active_streams(self) -> List[Dict[str, Any]]:
        """Get list of all active streams"""
        return [
            {
                "streamId": stream["streamId"],
                "status": stream["status"],
                "targetAgent": stream["targetAgent"],
                "createdAt": stream["createdAt"]
            }
            for stream in self.active_streams.values()
            if stream["status"] == "ACTIVE"
        ]
    
    def cleanup_old_streams(self, max_age_seconds: int = 3600) -> int:
        """
        Remove old completed/closed streams.
        
        Args:
            max_age_seconds: Maximum age of completed streams to keep
            
        Returns:
            Number of streams removed
        """
        import time
        current_time = time.time()
        streams_to_remove = []
        
        for stream_id, stream in self.active_streams.items():
            if stream["status"] in ["CLOSED", "COMPLETED"]:
                # Check if the stream is old enough to remove
                closed_at = stream.get("closedAt") or stream.get("completedAt")
                if closed_at:
                    try:
                        # Convert ISO timestamp to seconds
                        from datetime import datetime
                        closed_time = datetime.fromisoformat(closed_at.replace("Z", "+00:00")).timestamp()
                        age = current_time - closed_time
                        
                        if age > max_age_seconds:
                            streams_to_remove.append(stream_id)
                    except (ValueError, TypeError):
                        # If we can't parse the timestamp, keep the stream
                        pass
        
        # Remove streams
        for stream_id in streams_to_remove:
            del self.active_streams[stream_id]
        
        return len(streams_to_remove)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


class StreamConsumer:
    """
    Client for consuming ARC protocol stream chunks.
    
    Provides:
    - Asynchronous stream consumption with async iterators
    - Timeout handling
    - Automatic message reassembly
    """
    
    def __init__(
        self,
        client: Any,
        target_agent: str,
        stream_id: str,
        timeout: float = 30.0
    ):
        """
        Initialize stream consumer.
        
        Args:
            client: ARC client instance
            target_agent: ID of agent providing the stream
            stream_id: Stream identifier
            timeout: Timeout in seconds for stream operations
        """
        self.client = client
        self.target_agent = target_agent
        self.stream_id = stream_id
        self.timeout = timeout
        self.last_sequence = 0
        self.buffer = []
        self.complete = False
        self.trace_id = None
    
    async def __aiter__(self):
        return self
    
    async def __anext__(self) -> Dict[str, Any]:
        """
        Get next message chunk from stream.
        
        Returns:
            Message chunk
            
        Raises:
            StopAsyncIteration: When stream is complete
            StreamTimeoutError: If stream times out
        """
        if self.complete and not self.buffer:
            raise StopAsyncIteration
        
        # If we have buffered chunks, return the next one
        if self.buffer:
            return self.buffer.pop(0)
        
        # Fetch more chunks
        chunks = await self._fetch_chunks()
        
        if not chunks:
            if self.complete:
                raise StopAsyncIteration
            
            # No chunks yet, wait and try again
            await asyncio.sleep(0.1)
            return await self.__anext__()
        
        # Process chunks
        for chunk in chunks:
            self.buffer.append(chunk)
            self.last_sequence = chunk["sequence"]
            if chunk.get("isLast", False):
                self.complete = True
        
        return self.buffer.pop(0)
    
    async def _fetch_chunks(self) -> List[Dict[str, Any]]:
        """
        Fetch new chunks from the stream.
        
        Returns:
            List of new chunks
            
        Raises:
            StreamTimeoutError: If request times out
        """
        try:
            response = await self.client.stream.get_chunks(
                target_agent=self.target_agent,
                stream_id=self.stream_id,
                since_sequence=self.last_sequence,
                trace_id=self.trace_id,
                timeout=self.timeout
            )
            
            # Extract chunks from response
            if response.get("result", {}).get("chunks"):
                return response["result"]["chunks"]
            
            return []
        except asyncio.TimeoutError:
            raise StreamTimeoutError(
                self.stream_id,
                f"Stream operation timed out after {self.timeout} seconds"
            )
        except Exception as e:
            # Pass through ARC exceptions
            if hasattr(e, "code"):
                raise
            
            # Wrap other exceptions
            raise StreamTimeoutError(
                self.stream_id,
                f"Error fetching stream chunks: {str(e)}"
            )
    
    async def close(self):
        """Close the stream explicitly"""
        if not self.complete:
            try:
                await self.client.stream.end(
                    target_agent=self.target_agent,
                    stream_id=self.stream_id,
                    trace_id=self.trace_id,
                    timeout=self.timeout
                )
                self.complete = True
            except Exception as e:
                logger.warning(f"Error closing stream {self.stream_id}: {str(e)}")


class StreamProducer:
    """
    Utility for producing ARC protocol stream chunks.
    
    Provides:
    - Simplified streaming response generation
    - Automatic sequence numbering
    - Proper chunk formatting
    """
    
    def __init__(
        self,
        processor: Any,
        request_agent: str,
        stream_id: str,
        trace_id: Optional[str] = None
    ):
        """
        Initialize stream producer.
        
        Args:
            processor: ARC processor instance
            request_agent: ID of agent receiving the stream
            stream_id: Stream identifier
            trace_id: Optional workflow trace ID
        """
        self.processor = processor
        self.request_agent = request_agent
        self.stream_id = stream_id
        self.trace_id = trace_id
        self.sequence = 0
        self.is_complete = False
    
    async def send_chunk(
        self,
        chunk: Dict[str, Any],
        is_last: bool = False
    ) -> Dict[str, Any]:
        """
        Send a chunk to the stream.
        
        Args:
            chunk: Message chunk to send
            is_last: Whether this is the final chunk
            
        Returns:
            ARC response object
        """
        if self.is_complete:
            raise StreamAlreadyClosedError(
                self.stream_id, 
                "Cannot send chunks to a completed stream"
            )
        
        # Increment sequence
        self.sequence += 1
        
        # Mark as complete if this is the last chunk
        if is_last:
            self.is_complete = True
        
        # Create request
        params = {
            "streamId": self.stream_id,
            "chunk": chunk,
            "sequence": self.sequence,
            "isLast": is_last
        }
        
        request = self.processor.create_request(
            method="stream.chunk",
            target_agent=self.request_agent,
            params=params,
            trace_id=self.trace_id
        )
        
        return request
    
    async def complete(
        self, 
        final_chunk: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete the stream with optional final chunk.
        
        Args:
            final_chunk: Optional final chunk to send
            
        Returns:
            ARC response object if final_chunk is provided, None otherwise
        """
        if final_chunk:
            return await self.send_chunk(final_chunk, is_last=True)
        
        self.is_complete = True
        return None