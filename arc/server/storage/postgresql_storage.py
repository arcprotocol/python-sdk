"""
PostgreSQL-based chat storage implementation.

Uses PostgreSQL for persistent chat storage with manual TTL cleanup.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from .base import ChatStorage

logger = logging.getLogger(__name__)


class PostgreSQLChatStorage(ChatStorage):
    """
    PostgreSQL implementation of ChatStorage.
    
    Features:
    - Relational database storage
    - SQL query capabilities
    - Manual TTL cleanup (requires periodic calls to cleanup_expired_chats)
    
    Schema:
        CREATE TABLE arc_chats (
            chat_id VARCHAR(255) PRIMARY KEY,
            chat_data JSONB NOT NULL,
            status VARCHAR(50) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            target_agent VARCHAR(255)
        );
        CREATE INDEX idx_status ON arc_chats(status);
        CREATE INDEX idx_closed_at ON arc_chats(closed_at);
    
    Usage:
        import asyncpg
        
        db_pool = await asyncpg.create_pool('postgresql://user:pass@localhost/dbname')
        storage = PostgreSQLChatStorage(db_pool)
        
        # Initialize schema
        await storage.initialize_schema()
        
        chat_manager = ChatManager(agent_id="agent-1", storage=storage)
    """
    
    def __init__(self, db_pool, table_name: str = "arc_chats"):
        """
        Initialize PostgreSQL chat storage.
        
        Args:
            db_pool: An initialized asyncpg connection pool.
                    Users are responsible for creating and configuring this pool.
            table_name: Name of the table to store chats (default: "arc_chats")
        """
        self.pool = db_pool
        self.table_name = table_name
        logger.info(f"Initialized PostgreSQLChatStorage with table: {table_name}")
    
    async def initialize_schema(self) -> None:
        """
        Create the necessary database schema if it doesn't exist.
        
        This should be called once during application setup.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    chat_id VARCHAR(255) PRIMARY KEY,
                    chat_data JSONB NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    closed_at TIMESTAMP,
                    target_agent VARCHAR(255)
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_status 
                ON {self.table_name}(status)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_closed_at 
                ON {self.table_name}(closed_at)
            """)
        logger.info(f"PostgreSQL schema initialized for table: {self.table_name}")
    
    async def save(self, chat_id: str, chat_data: Dict[str, Any]) -> None:
        """
        Save or update a chat session in PostgreSQL.
        
        Args:
            chat_id: Unique chat identifier
            chat_data: Complete chat data
        """
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.table_name} 
                (chat_id, chat_data, status, created_at, updated_at, target_agent)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (chat_id) 
                DO UPDATE SET 
                    chat_data = $2,
                    status = $3,
                    updated_at = $5,
                    target_agent = $6
            """,
                chat_id,
                json.dumps(chat_data),
                chat_data.get("status", "ACTIVE"),
                datetime.fromisoformat(chat_data.get("createdAt").replace("Z", "+00:00")) 
                    if chat_data.get("createdAt") else datetime.now(timezone.utc),
                datetime.fromisoformat(chat_data.get("updatedAt").replace("Z", "+00:00"))
                    if chat_data.get("updatedAt") else datetime.now(timezone.utc),
                chat_data.get("targetAgent")
            )
        logger.debug(f"Saved chat {chat_id} to PostgreSQL")
    
    async def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chat session from PostgreSQL.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            Chat data if found, None otherwise
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT chat_data FROM {self.table_name} WHERE chat_id = $1",
                chat_id
            )
        
        if row is None:
            logger.debug(f"Chat {chat_id} not found in PostgreSQL")
            return None
        
        return json.loads(row['chat_data'])
    
    async def delete(self, chat_id: str) -> bool:
        """
        Delete a chat session from PostgreSQL.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if deleted, False if not found
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table_name} WHERE chat_id = $1",
                chat_id
            )
        
        deleted = result != "DELETE 0"
        if deleted:
            logger.info(f"Deleted chat {chat_id} from PostgreSQL")
        else:
            logger.debug(f"Chat {chat_id} not found for deletion")
        
        return deleted
    
    async def mark_closed(self, chat_id: str, ttl_seconds: int = 86400) -> None:
        """
        Mark a chat as CLOSED and update closedAt timestamp.
        
        PostgreSQL doesn't have native TTL, so cleanup_expired_chats() must be called
        periodically to remove old CLOSED chats.
        
        Args:
            chat_id: Unique chat identifier
            ttl_seconds: Time to live in seconds (stored for reference, cleanup is manual)
        """
        # Get current chat data
        chat_data = await self.get(chat_id)
        if chat_data is None:
            logger.warning(f"Cannot mark non-existent chat {chat_id} as closed")
            return
        
        # Update status and closedAt
        closed_at = datetime.now(timezone.utc)
        chat_data["status"] = "CLOSED"
        chat_data["closedAt"] = closed_at.isoformat()
        
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE {self.table_name}
                SET chat_data = $1, status = $2, closed_at = $3, updated_at = $4
                WHERE chat_id = $5
            """,
                json.dumps(chat_data),
                "CLOSED",
                closed_at,
                datetime.now(timezone.utc),
                chat_id
            )
        
        logger.info(f"Marked chat {chat_id} as CLOSED (TTL: {ttl_seconds}s, requires manual cleanup)")
    
    async def list_active_chats(self) -> List[Dict[str, Any]]:
        """
        List all active (non-CLOSED) chats.
        
        Returns:
            List of chat summaries
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT chat_data FROM {self.table_name}
                WHERE status != 'CLOSED'
            """)
        
        active_chats = []
        for row in rows:
            chat = json.loads(row['chat_data'])
            active_chats.append({
                "chatId": chat.get("chatId"),
                "status": chat.get("status"),
                "targetAgent": chat.get("targetAgent"),
                "createdAt": chat.get("createdAt")
            })
        
        return active_chats
    
    async def cleanup_expired_chats(self) -> int:
        """
        Clean up expired CLOSED chats based on TTL (24 hours by default).
        
        This should be called periodically (e.g., via cron job or scheduled task).
        
        Returns:
            Number of chats cleaned up
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=86400)  # 24 hours
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(f"""
                DELETE FROM {self.table_name}
                WHERE status = 'CLOSED' AND closed_at < $1
            """, cutoff_time)
        
        # Parse "DELETE N" result
        count = int(result.split()[-1]) if result.startswith("DELETE") else 0
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired chats from PostgreSQL")
        
        return count
    
    async def exists(self, chat_id: str) -> bool:
        """
        Check if a chat exists in PostgreSQL.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            True if chat exists, False otherwise
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                f"SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE chat_id = $1)",
                chat_id
            )
        return result

