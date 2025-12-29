"""
Abstract base class for chat storage backends.

Defines the interface that all storage implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class ChatStorage(ABC):
    """
    Abstract base class for persistent chat storage.
    
    All storage implementations (Redis, PostgreSQL, MongoDB, etc.) must implement
    this interface to ensure compatibility with ChatManager.
    """
    
    @abstractmethod
    async def save(self, chat_id: str, chat_data: Dict[str, Any]) -> None:
        """
        Save or update a chat session.
        
        Args:
            chat_id: Unique chat identifier
            chat_data: Complete chat data including status, messages, metadata, etc.
        """
        pass
    
    @abstractmethod
    async def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat session by ID.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            Chat data if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, chat_id: str) -> bool:
        """
        Delete a chat session.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def mark_closed(self, chat_id: str, ttl_seconds: int = 86400) -> None:
        """
        Mark a chat as CLOSED and set TTL for automatic deletion.
        
        For storage backends with native TTL support (Redis), this sets expiration.
        For others (PostgreSQL, MongoDB), this updates the status and closedAt timestamp.
        
        Args:
            chat_id: Unique chat identifier
            ttl_seconds: Time to live in seconds (default: 86400 = 24 hours)
        """
        pass
    
    @abstractmethod
    async def list_active_chats(self) -> List[Dict[str, Any]]:
        """
        List all active (non-CLOSED) chats.
        
        Returns:
            List of chat summaries (chatId, status, targetAgent, createdAt)
        """
        pass
    
    @abstractmethod
    async def cleanup_expired_chats(self) -> int:
        """
        Clean up expired CLOSED chats based on TTL.
        
        For Redis, this is handled automatically.
        For PostgreSQL/MongoDB, this must be called periodically.
        
        Returns:
            Number of chats cleaned up
        """
        pass
    
    @abstractmethod
    async def exists(self, chat_id: str) -> bool:
        """
        Check if a chat exists.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if chat exists, False otherwise
        """
        pass

