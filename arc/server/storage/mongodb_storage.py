"""
MongoDB-based chat storage implementation.

Uses MongoDB for persistent chat storage with TTL index support.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from .base import ChatStorage

logger = logging.getLogger(__name__)


class MongoChatStorage(ChatStorage):
    """
    MongoDB implementation of ChatStorage.
    
    Features:
    - Document-based storage
    - Native TTL index support for automatic cleanup
    - Flexible schema
    
    Setup:
        Create TTL index on closedAt field:
        db.arc_chats.createIndex(
            { "closedAt": 1 }, 
            { expireAfterSeconds: 86400 }  // 24 hours
        )
    
    Usage:
        from motor.motor_asyncio import AsyncIOMotorClient
        
        mongo_client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = mongo_client['my_database']
        storage = MongoChatStorage(db, collection_name='arc_chats')
        
        # Initialize TTL index
        await storage.initialize_indexes()
        
        chat_manager = ChatManager(agent_id="agent-1", storage=storage)
    """
    
    def __init__(self, database, collection_name: str = "arc_chats"):
        """
        Initialize MongoDB chat storage.
        
        Args:
            database: An initialized motor AsyncIOMotorDatabase instance.
                     Users are responsible for creating and configuring this database.
            collection_name: Name of the collection to store chats (default: "arc_chats")
        """
        self.db = database
        self.collection_name = collection_name
        self.collection = self.db[collection_name]
        logger.info(f"Initialized MongoChatStorage with collection: {collection_name}")
    
    async def initialize_indexes(self) -> None:
        """
        Create necessary indexes including TTL index for automatic cleanup.
        
        This should be called once during application setup.
        """
        # Create TTL index on closedAt field (expires 24 hours after closedAt)
        await self.collection.create_index(
            "closedAt",
            expireAfterSeconds=86400,  # 24 hours
            name="ttl_closedAt"
        )
        
        # Create index on status for faster queries
        await self.collection.create_index("status", name="idx_status")
        
        # Create index on chatId for faster lookups
        await self.collection.create_index("chatId", unique=True, name="idx_chatId")
        
        logger.info(f"MongoDB indexes initialized for collection: {self.collection_name}")
    
    async def save(self, chat_id: str, chat_data: Dict[str, Any]) -> None:
        """
        Save or update a chat session in MongoDB.
        
        Args:
            chat_id: Unique chat identifier
            chat_data: Complete chat data
        """
        # Add chatId to data for indexing
        chat_data["chatId"] = chat_id
        
        # Upsert the document
        await self.collection.update_one(
            {"chatId": chat_id},
            {"$set": chat_data},
            upsert=True
        )
        logger.debug(f"Saved chat {chat_id} to MongoDB")
    
    async def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat session from MongoDB.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            Chat data if found, None otherwise
        """
        doc = await self.collection.find_one({"chatId": chat_id})
        
        if doc is None:
            logger.debug(f"Chat {chat_id} not found in MongoDB")
            return None
        
        # Remove MongoDB's _id field
        if "_id" in doc:
            del doc["_id"]
        
        return doc
    
    async def delete(self, chat_id: str) -> bool:
        """
        Delete a chat session from MongoDB.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one({"chatId": chat_id})
        
        deleted = result.deleted_count > 0
        if deleted:
            logger.info(f"Deleted chat {chat_id} from MongoDB")
        else:
            logger.debug(f"Chat {chat_id} not found for deletion")
        
        return deleted
    
    async def mark_closed(self, chat_id: str, ttl_seconds: int = 86400) -> None:
        """
        Mark a chat as CLOSED and set closedAt timestamp for TTL.
        
        MongoDB's TTL index will automatically delete the document 24 hours after closedAt.
        
        Args:
            chat_id: Unique chat identifier
            ttl_seconds: Time to live in seconds (handled by MongoDB TTL index)
        """
        # Get current chat data
        chat_data = await self.get(chat_id)
        if chat_data is None:
            logger.warning(f"Cannot mark non-existent chat {chat_id} as closed")
            return
        
        # Update status and closedAt
        closed_at = datetime.now(timezone.utc)
        
        await self.collection.update_one(
            {"chatId": chat_id},
            {
                "$set": {
                    "status": "CLOSED",
                    "closedAt": closed_at,
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        logger.info(f"Marked chat {chat_id} as CLOSED (MongoDB TTL will auto-delete in {ttl_seconds}s)")
    
    async def list_active_chats(self) -> List[Dict[str, Any]]:
        """
        List all active (non-CLOSED) chats.
        
        Returns:
            List of chat summaries
        """
        cursor = self.collection.find(
            {"status": {"$ne": "CLOSED"}},
            {"chatId": 1, "status": 1, "targetAgent": 1, "createdAt": 1, "_id": 0}
        )
        
        active_chats = []
        async for doc in cursor:
            active_chats.append({
                "chatId": doc.get("chatId"),
                "status": doc.get("status"),
                "targetAgent": doc.get("targetAgent"),
                "createdAt": doc.get("createdAt")
            })
        
        return active_chats
    
    async def cleanup_expired_chats(self) -> int:
        """
        Clean up expired CLOSED chats.
        
        For MongoDB with TTL index, this is handled automatically.
        This method is provided for compatibility but is a no-op.
        
        Returns:
            Always returns 0 (MongoDB handles cleanup automatically via TTL index)
        """
        logger.debug("MongoDB TTL index handles cleanup automatically, no manual cleanup needed")
        return 0
    
    async def exists(self, chat_id: str) -> bool:
        """
        Check if a chat exists in MongoDB.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if chat exists, False otherwise
        """
        count = await self.collection.count_documents({"chatId": chat_id}, limit=1)
        return count > 0

