"""
Redis-based chat storage implementation.

Uses Redis for persistent chat storage with built-in TTL support.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .base import ChatStorage

logger = logging.getLogger(__name__)


class RedisChatStorage(ChatStorage):
    """
    Redis implementation of ChatStorage.
    
    Features:
    - Native TTL support for automatic cleanup
    - Fast in-memory storage
    - Suitable for high-performance chat systems
    
    Usage:
        import redis.asyncio as redis
        
        redis_client = redis.Redis(host='localhost', port=6379)
        storage = RedisChatStorage(redis_client)
        
        chat_manager = ChatManager(agent_id="agent-1", storage=storage)
    """
    
    def __init__(self, redis_client):
        """
        Initialize Redis chat storage.
        
        Args:
            redis_client: An initialized redis.asyncio.Redis client instance.
                         Users are responsible for creating and configuring this client.
        """
        self.redis = redis_client
        self.key_prefix = "arc:chat:"
        logger.info("Initialized RedisChatStorage")
    
    def _make_key(self, chat_id: str) -> str:
        """Generate Redis key for a chat."""
        return f"{self.key_prefix}{chat_id}"
    
    async def save(self, chat_id: str, chat_data: Dict[str, Any]) -> None:
        """
        Save or update a chat session in Redis.
        
        Args:
            chat_id: Unique chat identifier
            chat_data: Complete chat data
        """
        key = self._make_key(chat_id)
        serialized = json.dumps(chat_data)
        
        # Save without TTL for active chats
        await self.redis.set(key, serialized)
        logger.debug(f"Saved chat {chat_id} to Redis")
    
    async def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat session from Redis.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            Chat data if found, None otherwise
        """
        key = self._make_key(chat_id)
        data = await self.redis.get(key)
        
        if data is None:
            logger.debug(f"Chat {chat_id} not found in Redis")
            return None
        
        return json.loads(data)
    
    async def delete(self, chat_id: str) -> bool:
        """
        Delete a chat session from Redis.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if deleted, False if not found
        """
        key = self._make_key(chat_id)
        result = await self.redis.delete(key)
        
        deleted = result > 0
        if deleted:
            logger.info(f"Deleted chat {chat_id} from Redis")
        else:
            logger.debug(f"Chat {chat_id} not found for deletion")
        
        return deleted
    
    async def mark_closed(self, chat_id: str, ttl_seconds: int = 86400) -> None:
        """
        Mark a chat as CLOSED and set TTL for automatic deletion.
        
        Redis will automatically delete the chat after ttl_seconds.
        
        Args:
            chat_id: Unique chat identifier
            ttl_seconds: Time to live in seconds (default: 86400 = 24 hours)
        """
        key = self._make_key(chat_id)
        
        # Get current chat data
        chat_data = await self.get(chat_id)
        if chat_data is None:
            logger.warning(f"Cannot mark non-existent chat {chat_id} as closed")
            return
        
        # Update status and closedAt
        chat_data["status"] = "CLOSED"
        chat_data["closedAt"] = datetime.now(timezone.utc).isoformat()
        
        # Save with TTL
        serialized = json.dumps(chat_data)
        await self.redis.setex(key, ttl_seconds, serialized)
        
        logger.info(f"Marked chat {chat_id} as CLOSED with TTL of {ttl_seconds} seconds")
    
    async def list_active_chats(self) -> List[Dict[str, Any]]:
        """
        List all active (non-CLOSED) chats.
        
        Returns:
            List of chat summaries
        """
        pattern = f"{self.key_prefix}*"
        active_chats = []
        
        # Scan for all chat keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    chat = json.loads(data)
                    if chat.get("status") != "CLOSED":
                        active_chats.append({
                            "chatId": chat.get("chatId"),
                            "status": chat.get("status"),
                            "targetAgent": chat.get("targetAgent"),
                            "createdAt": chat.get("createdAt")
                        })
            
            if cursor == 0:
                break
        
        return active_chats
    
    async def cleanup_expired_chats(self) -> int:
        """
        Clean up expired CLOSED chats.
        
        For Redis, TTL handles this automatically, so this is a no-op.
        
        Returns:
            Always returns 0 (Redis handles cleanup automatically)
        """
        logger.debug("Redis handles TTL cleanup automatically, no manual cleanup needed")
        return 0
    
    async def exists(self, chat_id: str) -> bool:
        """
        Check if a chat exists in Redis.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if chat exists, False otherwise
        """
        key = self._make_key(chat_id)
        result = await self.redis.exists(key)
        return result > 0

