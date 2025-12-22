"""Tests for schema cache."""

import pytest
from datetime import datetime
from app.schema_cache import SchemaCache
from app.models import SchemaDefinition


@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test setting and getting schemas from cache."""
    cache = SchemaCache()

    schema = SchemaDefinition(
        schema_id="test123",
        intent_pattern="entity:users|operation:list",
        json_schema={"type": "array"},
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        use_count=0
    )

    await cache.set("test123", schema)
    retrieved = await cache.get("test123")

    assert retrieved is not None
    assert retrieved.schema_id == "test123"
    assert retrieved.intent_pattern == "entity:users|operation:list"


@pytest.mark.asyncio
async def test_cache_delete():
    """Test deleting schemas from cache."""
    cache = SchemaCache()

    schema = SchemaDefinition(
        schema_id="test456",
        intent_pattern="entity:products|operation:list",
        json_schema={"type": "array"},
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        use_count=0
    )

    await cache.set("test456", schema)
    assert await cache.exists("test456")

    await cache.delete("test456")
    assert not await cache.exists("test456")


@pytest.mark.asyncio
async def test_cache_pin_unpin():
    """Test pinning and unpinning schemas."""
    cache = SchemaCache()

    schema = SchemaDefinition(
        schema_id="test789",
        intent_pattern="entity:orders|operation:count",
        json_schema={"type": "object"},
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        use_count=0
    )

    await cache.set("test789", schema)
    await cache.pin("test789")

    retrieved = await cache.get("test789")
    assert retrieved.pinned is True

    await cache.unpin("test789")
    retrieved = await cache.get("test789")
    assert retrieved.pinned is False


@pytest.mark.asyncio
async def test_cache_usage_stats():
    """Test usage statistics updates."""
    cache = SchemaCache()

    schema = SchemaDefinition(
        schema_id="test_usage",
        intent_pattern="entity:users|operation:list",
        json_schema={"type": "array"},
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        use_count=0
    )

    await cache.set("test_usage", schema)

    # Update usage
    await cache.update_usage("test_usage")
    await cache.update_usage("test_usage")

    retrieved = await cache.get("test_usage")
    assert retrieved.use_count == 2
