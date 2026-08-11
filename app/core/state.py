"""Abstract state store and in-memory implementation.

The ``BaseStateStore`` defines a pluggable interface for ephemeral state
(approval token caching, rate-limit locks, etc.).  The ``InMemoryStateStore``
fulfils the contract for local/dev usage.  A Redis-backed implementation can
be swapped in later without touching any service or API code.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any


class BaseStateStore(ABC):
    """Abstract interface for ephemeral key-value state operations."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Retrieve a value by key, or ``None`` if not found / expired."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a value, optionally with a TTL in seconds."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key.  Returns ``True`` if the key existed."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether a key exists and has not expired."""


class InMemoryStateStore(BaseStateStore):
    """Thread-safe async in-memory key-value store with optional TTL.

    Suitable for single-process deployments and testing.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, expires_at: float | None) -> bool:
        """Return ``True`` if the entry has a TTL and it has elapsed."""
        if expires_at is None:
            return False
        return time.monotonic() > expires_at

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._is_expired(expires_at):
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = (time.monotonic() + ttl_seconds) if ttl_seconds else None
        async with self._lock:
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return (await self.get(key)) is not None
