"""
Starlette integration for ARC Protocol.

This module provides Starlette router integration for the ARC protocol,
offering a lightweight alternative to FastAPI for ASGI applications.
"""

from .router import ARCRouter

__all__ = ["ARCRouter"]
