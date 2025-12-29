"""
ARC Chat Module

Provides support for real-time chat communication in the ARC protocol.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, Union, List, Callable, AsyncGenerator

from ..exceptions import (
    ChatNotFoundError, ChatAlreadyClosedError, InvalidChatMessageError,
    ChatTimeoutError
)


logger = logging.getLogger(__name__)


class ChatManager:
    """
    Manages active chat sessions for ARC real-time communication.
    
    This manager creates and tracks chat session mappings between ARC chat_id 
    and framework-specific thread identifiers. It does NOT store messages or
    conversation state - frameworks handle that internally.
    
    Primary responsibilities:
    - Creating chat_id ↔ framework_thread_id mappings
    - Storing chat metadata (framework info, thread references)
    - Managing chat lifecycle (ACTIVE/CLOSED status)
    - Optional persistent storage (Redis, PostgreSQL, MongoDB)
    - 24-hour retention for closed chats (for debugging/analytics)
    
    The framework (LangChain, LlamaIndex, etc.) stores actual messages and 
    state using its own storage system, referenced by the thread_id.
    """
    
    def __init__(self, agent_id: str, storage: Optional[Any] = None):
        """
        Initialize chat manager.
        
        Args:
            agent_id: ID of this agent
            storage: Optional ChatStorage implementation for persistent storage.
                    If None, uses in-memory storage only (current behavior).
                    If provided, uses dual-write: RAM (fast) + persistent storage.
        """
        self.agent_id = agent_id
        self.active_chats: Dict[str, Dict[str, Any]] = {}
        self.storage = storage
        
        if storage:
            logger.info(f"ChatManager initialized with persistent storage: {type(storage).__name__}")
        else:
            logger.info("ChatManager initialized with in-memory storage only")
    
    async def create_chat(self, target_agent: str, metadata: Optional[Dict[str, Any]] = None, 
                   chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        This creates a mapping between ARC chat_id and framework-specific thread_id.
        The framework stores actual messages and state internally.
        
        Args:
            target_agent: ID of agent to communicate with
            metadata: Optional chat metadata (typically includes framework_thread_id)
            chat_id: Optional client-specified chat identifier
            
        Returns:
            Chat object with chat ID
        """
        # Use provided chat_id or generate one
        chat_id = chat_id or f"chat-{uuid.uuid4().hex[:8]}"
        created_at = self._get_timestamp()
        
        chat = {
            "chatId": chat_id,
            "status": "ACTIVE",
            "targetAgent": target_agent,
            "createdAt": created_at,
            "updatedAt": created_at,
            "metadata": metadata or {}
        }
        
        # Store in RAM (fast access)
        self.active_chats[chat_id] = chat
        
        # Store in persistent storage if configured
        if self.storage:
            await self.storage.save(chat_id, chat)
        
        logger.info(f"Created chat {chat_id} with {target_agent}")
        
        return {
            "chatId": chat_id,
            "status": "ACTIVE",
            "targetAgent": target_agent,
            "createdAt": created_at
        }
    
    async def get_chat(self, chat_id: str) -> Dict[str, Any]:
        """
        Get chat information including metadata.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            Chat object with metadata (includes framework_thread_id)
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
        """
        # Check RAM first (fast)
        if chat_id in self.active_chats:
            chat = self.active_chats[chat_id]
            return {
                "chatId": chat["chatId"],
                "status": chat["status"],
                "targetAgent": chat["targetAgent"],
                "metadata": chat.get("metadata", {}),
                "createdAt": chat["createdAt"],
                "updatedAt": chat.get("updatedAt", chat["createdAt"])
            }
        
        # Check persistent storage if configured
        if self.storage:
            chat = await self.storage.get(chat_id)
            if chat:
                # Cache in RAM for future access
                self.active_chats[chat_id] = chat
                return {
                    "chatId": chat["chatId"],
                    "status": chat["status"],
                    "targetAgent": chat["targetAgent"],
                    "metadata": chat.get("metadata", {}),
                    "createdAt": chat["createdAt"],
                    "updatedAt": chat.get("updatedAt", chat["createdAt"])
                }
        
        # Not found in RAM or storage
        raise ChatNotFoundError(chat_id, f"Chat not found: {chat_id}")
    
    async def update_metadata(
        self, 
        chat_id: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update chat metadata (e.g., framework_thread_id or other info).
        
        Args:
            chat_id: Chat identifier
            metadata: Metadata to merge with existing metadata
            
        Returns:
            Updated chat object
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
            ChatAlreadyClosedError: If chat is closed
        """
        # Ensure chat is loaded (checks RAM, then storage)
        await self.get_chat(chat_id)
        
        chat = self.active_chats[chat_id]
        
        if chat["status"] == "CLOSED":
            raise ChatAlreadyClosedError(chat_id, f"Chat already closed: {chat_id}")
            
        # Merge metadata
        chat["metadata"].update(metadata)
        chat["updatedAt"] = self._get_timestamp()
        
        # Update persistent storage if configured
        if self.storage:
            await self.storage.save(chat_id, chat)
        
        logger.debug(f"Updated metadata for chat {chat_id}")
        
        return {
            "chatId": chat["chatId"],
            "metadata": chat["metadata"],
            "status": chat["status"],
            "updatedAt": chat["updatedAt"]
        }
    
    async def close_chat(self, chat_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Close a chat.
        
        Args:
            chat_id: Chat identifier
            reason: Optional reason for closing
            
        Returns:
            Closed chat object
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
            ChatAlreadyClosedError: If chat already closed
        """
        # Ensure chat is loaded (checks RAM, then storage)
        await self.get_chat(chat_id)
        
        chat = self.active_chats[chat_id]
        
        if chat["status"] == "CLOSED":
            raise ChatAlreadyClosedError(chat_id, f"Chat already closed: {chat_id}")
            
        # Update chat state
        chat["status"] = "CLOSED"
        chat["closedAt"] = self._get_timestamp()
        
        if reason:
            chat["reason"] = reason
        
        # Mark as closed in persistent storage with 24-hour TTL
        if self.storage:
            await self.storage.mark_closed(chat_id, ttl_seconds=86400)
        
        logger.info(f"Closed chat {chat_id}")
        
        return {
            "chatId": chat["chatId"],
            "status": "CLOSED",
            "closedAt": chat["closedAt"],
            "reason": chat.get("reason")
        }
    
    
    async def get_active_chats(self) -> List[Dict[str, Any]]:
        """
        Get list of active chats.
        
        Returns:
            List of active chat objects
        """
        active_chats = []
        
        # Get from RAM
        for chat_id, chat in self.active_chats.items():
            if chat["status"] != "CLOSED":
                active_chats.append({
                    "chatId": chat["chatId"],
                    "status": chat["status"],
                    "targetAgent": chat["targetAgent"],
                    "createdAt": chat["createdAt"]
                })
        
        # If storage is configured, also get from storage (in case of chats not in RAM)
        if self.storage:
            storage_chats = await self.storage.list_active_chats()
            # Add any chats from storage that aren't already in the list
            ram_chat_ids = {chat["chatId"] for chat in active_chats}
            for chat in storage_chats:
                if chat["chatId"] not in ram_chat_ids:
                    active_chats.append(chat)
                
        return active_chats
    
    async def cleanup_old_chats(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up old closed chats from RAM and trigger storage cleanup.
        
        Args:
            max_age_seconds: Maximum age in seconds for closed chats (default: 86400 = 24 hours)
            
        Returns:
            Number of chats cleaned up from RAM
        """
        import time
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        cleanup_count = 0
        chats_to_remove = []
        
        # Clean up from RAM
        for chat_id, chat in self.active_chats.items():
            if chat["status"] != "CLOSED":
                continue
                
            # Parse closed_at timestamp
            closed_at = None
            try:
                if "closedAt" in chat:
                    if isinstance(chat["closedAt"], str):
                        closed_at = datetime.fromisoformat(chat["closedAt"].replace("Z", "+00:00"))
                    else:
                        closed_at = chat["closedAt"]
            except (ValueError, TypeError):
                # If we can't parse, assume it's too old
                chats_to_remove.append(chat_id)
                cleanup_count += 1
                continue
                
            if closed_at and (now - closed_at).total_seconds() > max_age_seconds:
                chats_to_remove.append(chat_id)
                cleanup_count += 1
                
        # Remove chats from RAM
        for chat_id in chats_to_remove:
            del self.active_chats[chat_id]
        
        # Trigger storage cleanup if configured
        # (For Redis/MongoDB this is no-op, for PostgreSQL it deletes expired chats)
        if self.storage:
            storage_cleanup_count = await self.storage.cleanup_expired_chats()
            logger.info(f"Storage cleanup removed {storage_cleanup_count} expired chats")
            
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old chats from RAM")
            
        return cleanup_count
    
    def _get_timestamp(self) -> str:
        """Get current ISO timestamp"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


class ChatConsumer:
    """
    Client-side consumer for receiving messages from a chat session.
    
    Provides an asynchronous iterator interface for consuming chat messages,
    with support for SSE streaming.
    """
    
    def __init__(
        self,
        client: Any,
        target_agent: str,
        chat_id: str,
        timeout: float = 30.0
    ):
        """
        Initialize chat consumer.
        
        Args:
            client: ARC client instance
            target_agent: ID of agent to communicate with
            chat_id: Chat identifier
            timeout: Maximum time to wait for messages
        """
        self.client = client
        self.target_agent = target_agent
        self.chat_id = chat_id
        self.timeout = timeout
        self.last_sequence = 0
        self.closed = False
        
    async def __aiter__(self):
        return self
        
    async def __anext__(self) -> Dict[str, Any]:
        """Get next message in chat"""
        if self.closed:
            raise StopAsyncIteration
            
        try:
            # Wait for new messages with timeout
            messages = await asyncio.wait_for(
                self._fetch_messages(), 
                timeout=self.timeout
            )
            
            if not messages or self.closed:
                raise StopAsyncIteration
                
            return messages[0]
            
        except asyncio.TimeoutError:
            raise ChatTimeoutError(self.chat_id, f"Timed out waiting for messages in chat {self.chat_id}")
            
        except Exception as e:
            logger.error(f"Error in chat consumer: {str(e)}")
            raise
    
    async def close(self):
        """Close the chat consumer"""
        if not self.closed:
            self.closed = True
            logger.debug(f"Closed chat consumer for chat {self.chat_id}")


class ChatProducer:
    """
    Server-side producer for sending messages to a chat session.
    
    Provides methods for sending messages and ending the chat.
    """
    
    def __init__(
        self,
        processor: Any,
        request_agent: str,
        chat_id: str,
        trace_id: Optional[str] = None
    ):
        """
        Initialize chat producer.
        
        Args:
            processor: ARC request processor
            request_agent: ID of requesting agent
            chat_id: Chat identifier
            trace_id: Optional workflow trace ID
        """
        self.processor = processor
        self.request_agent = request_agent
        self.chat_id = chat_id
        self.trace_id = trace_id
        self.closed = False
        
    async def send_message(
        self,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send a message in the chat.
        
        Args:
            message: Message to send
            
        Returns:
            Response from target agent
            
        Raises:
            ChatAlreadyClosedError: If chat is closed
        """
        if self.closed:
            raise ChatAlreadyClosedError(self.chat_id, f"Chat already closed: {self.chat_id}")
            
        # Prepare request
        request = {
            "method": "chat.message",
            "params": {
                "chatId": self.chat_id,
                "message": message
            },
            "requestAgent": self.processor.agent_id,
            "targetAgent": self.request_agent
        }
        
        if self.trace_id:
            request["traceId"] = self.trace_id
            
        # Send message
        response = await self.processor.process_request(request)
        
        return response.get("result")
        
    async def close(
        self, 
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End the chat.
        
        Args:
            reason: Optional reason for closing
            
        Returns:
            Response from target agent
        """
        if self.closed:
            return {"chatId": self.chat_id, "status": "CLOSED"}
            
        # Prepare request
        request = {
            "method": "chat.end",
            "params": {
                "chatId": self.chat_id
            },
            "requestAgent": self.processor.agent_id,
            "targetAgent": self.request_agent
        }
        
        if reason:
            request["params"]["reason"] = reason
            
        if self.trace_id:
            request["traceId"] = self.trace_id
            
        # Send end request
        response = await self.processor.process_request(request)
        
        self.closed = True
        logger.debug(f"Closed chat producer for chat {self.chat_id}")
        
        return response.get("result")