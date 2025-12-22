"""Tests for executor and SQL generation."""

import pytest
from app.executor import validate_sql_safety, infer_field_type, infer_schema_from_results


def test_validate_sql_safety():
    """Test SQL safety validation."""
    # Safe queries
    assert validate_sql_safety("SELECT * FROM users WHERE status = ? LIMIT 10")
    assert validate_sql_safety("SELECT COUNT(*) FROM orders WHERE status = ?")

    # Unsafe queries
    assert not validate_sql_safety("DELETE FROM users WHERE id = 1")
    assert not validate_sql_safety("UPDATE users SET status = 'inactive'")
    assert not validate_sql_safety("DROP TABLE users")
    assert not validate_sql_safety("INSERT INTO users VALUES (1, 'test')")


def test_infer_field_type():
    """Test field type inference."""
    assert infer_field_type(None) == "null"
    assert infer_field_type(True) == "boolean"
    assert infer_field_type(42) == "integer"
    assert infer_field_type(3.14) == "number"
    assert infer_field_type("hello") == "string"
    assert infer_field_type([1, 2, 3]) == "array"
    assert infer_field_type({"key": "value"}) == "object"


@pytest.mark.asyncio
async def test_infer_schema_from_results():
    """Test schema inference from query results."""
    # Test with array of objects
    results = [
        {"id": 1, "name": "Alice", "active": True},
        {"id": 2, "name": "Bob", "active": False}
    ]

    schema = await infer_schema_from_results(results)

    assert schema["type"] == "array"
    assert schema["items"]["type"] == "object"
    assert "id" in schema["items"]["properties"]
    assert "name" in schema["items"]["properties"]
    assert "active" in schema["items"]["properties"]

    # Test with empty results
    empty_schema = await infer_schema_from_results([])
    assert empty_schema["type"] == "array"
    assert "description" in empty_schema
