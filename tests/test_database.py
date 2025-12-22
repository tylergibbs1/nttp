"""Tests for database layer."""

import pytest
from app.database import init_db, execute_query, get_all_tables


@pytest.mark.asyncio
async def test_init_db():
    """Test database initialization."""
    await init_db()
    tables = await get_all_tables()
    assert "users" in tables
    assert "products" in tables
    assert "orders" in tables
    assert "order_items" in tables


@pytest.mark.asyncio
async def test_execute_query():
    """Test query execution."""
    await init_db()
    results = await execute_query("SELECT * FROM users LIMIT 5")
    assert isinstance(results, list)
    if results:  # May be empty if not seeded
        assert isinstance(results[0], dict)
