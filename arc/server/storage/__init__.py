"""
Chat storage module for persistent storage backends.

Provides abstract base class and implementations for Redis, PostgreSQL, and MongoDB.
"""

from .base import ChatStorage
from .redis_storage import RedisChatStorage
from .postgresql_storage import PostgreSQLChatStorage
from .mongodb_storage import MongoChatStorage

__all__ = [
    "ChatStorage",
    "RedisChatStorage",
    "PostgreSQLChatStorage",
    "MongoChatStorage",
]

