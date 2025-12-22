"""Thread-safe in-memory schema cache."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List

from app.models import SchemaDefinition

logger = logging.getLogger(__name__)


class SchemaCache:
    """
    Thread-safe in-memory cache for schema definitions.

    Provides async-safe operations for storing and retrieving schemas.
    """

    def __init__(self):
        """Initialize cache with empty storage and lock."""
        self._cache: Dict[str, SchemaDefinition] = {}
        self._lock = asyncio.Lock()

    async def get(self, schema_id: str) -> Optional[SchemaDefinition]:
        """
        Get schema by ID.

        Args:
            schema_id: Schema identifier

        Returns:
            SchemaDefinition if found, None otherwise
        """
        async with self._lock:
            return self._cache.get(schema_id)

    async def set(self, schema_id: str, schema: SchemaDefinition) -> None:
        """
        Store schema in cache.

        Args:
            schema_id: Schema identifier
            schema: SchemaDefinition to store
        """
        async with self._lock:
            self._cache[schema_id] = schema
            logger.info(f"Cached schema: {schema_id}")

    async def exists(self, schema_id: str) -> bool:
        """
        Check if schema exists in cache.

        Args:
            schema_id: Schema identifier

        Returns:
            True if exists, False otherwise
        """
        async with self._lock:
            return schema_id in self._cache

    async def delete(self, schema_id: str) -> bool:
        """
        Delete schema from cache.

        Args:
            schema_id: Schema identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if schema_id in self._cache:
                del self._cache[schema_id]
                logger.info(f"Deleted schema: {schema_id}")
                return True
            return False

    async def list_all(self) -> List[SchemaDefinition]:
        """
        List all cached schemas.

        Returns:
            List of all SchemaDefinition objects
        """
        async with self._lock:
            return list(self._cache.values())

    async def update_usage(self, schema_id: str) -> None:
        """
        Update usage statistics for a schema.

        Args:
            schema_id: Schema identifier
        """
        async with self._lock:
            if schema_id in self._cache:
                schema = self._cache[schema_id]
                schema.use_count += 1
                schema.last_used_at = datetime.now()
                logger.debug(f"Updated usage for schema {schema_id}: {schema.use_count} uses")

    async def pin(self, schema_id: str) -> bool:
        """
        Pin schema to prevent eviction.

        Args:
            schema_id: Schema identifier

        Returns:
            True if pinned, False if not found
        """
        async with self._lock:
            if schema_id in self._cache:
                self._cache[schema_id].pinned = True
                logger.info(f"Pinned schema: {schema_id}")
                return True
            return False

    async def unpin(self, schema_id: str) -> bool:
        """
        Unpin schema to allow eviction.

        Args:
            schema_id: Schema identifier

        Returns:
            True if unpinned, False if not found
        """
        async with self._lock:
            if schema_id in self._cache:
                self._cache[schema_id].pinned = False
                logger.info(f"Unpinned schema: {schema_id}")
                return True
            return False

    async def add_example_query(self, schema_id: str, query: str) -> None:
        """
        Add an example query to a schema.

        Args:
            schema_id: Schema identifier
            query: Example query string
        """
        async with self._lock:
            if schema_id in self._cache:
                schema = self._cache[schema_id]
                if query not in schema.example_queries:
                    schema.example_queries.append(query)
                    # Keep only last 10 examples
                    schema.example_queries = schema.example_queries[-10:]

    async def clear(self) -> int:
        """
        Clear all non-pinned schemas from cache.

        Returns:
            Number of schemas cleared
        """
        async with self._lock:
            initial_count = len(self._cache)
            self._cache = {
                schema_id: schema
                for schema_id, schema in self._cache.items()
                if schema.pinned
            }
            cleared = initial_count - len(self._cache)
            if cleared > 0:
                logger.info(f"Cleared {cleared} non-pinned schemas")
            return cleared

    async def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        async with self._lock:
            total = len(self._cache)
            pinned = sum(1 for s in self._cache.values() if s.pinned)
            total_uses = sum(s.use_count for s in self._cache.values())

            return {
                "total_schemas": total,
                "pinned_schemas": pinned,
                "total_uses": total_uses,
                "avg_uses": total_uses // total if total > 0 else 0
            }


# Global cache instance
cache = SchemaCache()
