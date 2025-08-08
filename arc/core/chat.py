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
    
    Provides functionality for:
    - Creating and tracking chat sessions
    - Sending messages in chats
    - Closing chats
    - Supporting SSE streaming
    """
    
    def __init__(self, agent_id: str):
        """
        Initialize chat manager.
        
        Args:
            agent_id: ID of this agent
        """
        self.agent_id = agent_id
        self.active_chats: Dict[str, Dict[str, Any]] = {}
    
    def create_chat(self, target_agent: str, metadata: Optional[Dict[str, Any]] = None, 
                   chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        Args:
            target_agent: ID of agent to communicate with
            metadata: Optional chat metadata
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
            "metadata": metadata or {},
            "messages": [],
            "participants": [self.agent_id, target_agent]
        }
        
        self.active_chats[chat_id] = chat
        logger.info(f"Created chat {chat_id} with {target_agent}")
        
        return {
            "chatId": chat_id,
            "status": "ACTIVE",
            "participants": [self.agent_id, target_agent],
            "createdAt": created_at
        }
    
    def get_chat(self, chat_id: str) -> Dict[str, Any]:
        """
        Get chat information.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            Chat object
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
        """
        if chat_id not in self.active_chats:
            raise ChatNotFoundError(chat_id, f"Chat not found: {chat_id}")
        
        chat = self.active_chats[chat_id]
        
        return {
            "chatId": chat["chatId"],
            "status": chat["status"],
            "targetAgent": chat["targetAgent"],
            "participants": chat.get("participants", [self.agent_id, chat["targetAgent"]]),
            "createdAt": chat["createdAt"],
            "updatedAt": chat.get("updatedAt", chat["createdAt"])
        }
    
    def add_message(
        self, 
        chat_id: str, 
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a message to a chat.
        
        Args:
            chat_id: Chat identifier
            message: Message to add
            
        Returns:
            Updated chat object
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
            ChatAlreadyClosedError: If chat is closed
        """
        if chat_id not in self.active_chats:
            raise ChatNotFoundError(chat_id, f"Chat not found: {chat_id}")
            
        chat = self.active_chats[chat_id]
        
        if chat["status"] == "CLOSED":
            raise ChatAlreadyClosedError(chat_id, f"Chat already closed: {chat_id}")
            
        # Add timestamp if not provided
        if "timestamp" not in message:
            message["timestamp"] = self._get_timestamp()
            
        # Store message
        chat["messages"].append(message)
        chat["updatedAt"] = self._get_timestamp()
        
        logger.debug(f"Added message to chat {chat_id}")
        
        return {
            "chatId": chat["chatId"],
            "message": message,
            "status": chat["status"],
            "updatedAt": chat["updatedAt"]
        }
    
    def close_chat(self, chat_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
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
        if chat_id not in self.active_chats:
            raise ChatNotFoundError(chat_id, f"Chat not found: {chat_id}")
            
        chat = self.active_chats[chat_id]
        
        if chat["status"] == "CLOSED":
            raise ChatAlreadyClosedError(chat_id, f"Chat already closed: {chat_id}")
            
        # Update chat state
        chat["status"] = "CLOSED"
        chat["closedAt"] = self._get_timestamp()
        
        if reason:
            chat["reason"] = reason
            
        logger.info(f"Closed chat {chat_id}")
        
        return {
            "chatId": chat["chatId"],
            "status": "CLOSED",
            "closedAt": chat["closedAt"],
            "reason": chat.get("reason")
        }
    
    def get_messages(
        self, 
        chat_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all messages in a chat.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            List of messages
            
        Raises:
            ChatNotFoundError: If chat doesn't exist
        """
        if chat_id not in self.active_chats:
            raise ChatNotFoundError(chat_id, f"Chat not found: {chat_id}")
            
        chat = self.active_chats[chat_id]
        
        return chat.get("messages", [])
    
    def get_active_chats(self) -> List[Dict[str, Any]]:
        """
        Get list of active chats.
        
        Returns:
            List of active chat objects
        """
        active_chats = []
        
        for chat_id, chat in self.active_chats.items():
            if chat["status"] != "CLOSED":
                active_chats.append({
                    "chatId": chat["chatId"],
                    "status": chat["status"],
                    "targetAgent": chat["targetAgent"],
                    "createdAt": chat["createdAt"]
                })
                
        return active_chats
    
    def cleanup_old_chats(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old closed chats.
        
        Args:
            max_age_seconds: Maximum age in seconds for closed chats
            
        Returns:
            Number of chats cleaned up
        """
        import time
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        cleanup_count = 0
        chats_to_remove = []
        
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
                
        # Remove chats
        for chat_id in chats_to_remove:
            del self.active_chats[chat_id]
            
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old chats")
            
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