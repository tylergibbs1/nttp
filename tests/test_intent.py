"""Tests for intent parsing and normalization."""

import pytest
from app.intent import (
    normalize_intent_dict, generate_schema_id,
    remove_articles, extract_keywords
)
from app.models import Intent


def test_normalize_intent_dict():
    """Test intent normalization produces consistent output."""
    intent1 = {
        "entity": "users",
        "operation": "list",
        "filters": {"status": "active"},
        "limit": None
    }

    intent2 = {
        "entity": "USERS",
        "operation": "LIST",
        "filters": {"STATUS": "ACTIVE"},
        "limit": None
    }

    # Should normalize to same string
    norm1 = normalize_intent_dict(intent1)
    norm2 = normalize_intent_dict(intent2)

    assert norm1 == norm2
    assert "entity:users" in norm1
    assert "operation:list" in norm1
    assert "filters:status=active" in norm1


def test_generate_schema_id_consistency():
    """Test that same intent generates same schema ID."""
    intent1 = Intent(
        entity="users",
        operation="list",
        filters={"status": "active"},
        limit=None,
        normalized_text="entity:users|operation:list|filters:status=active"
    )

    intent2 = Intent(
        entity="users",
        operation="list",
        filters={"status": "active"},
        limit=None,
        normalized_text="entity:users|operation:list|filters:status=active"
    )

    schema_id1 = generate_schema_id(intent1)
    schema_id2 = generate_schema_id(intent2)

    assert schema_id1 == schema_id2
    assert len(schema_id1) == 16  # 16-char hash


def test_remove_articles():
    """Test article removal."""
    assert remove_articles("get the users") == "get users"
    assert remove_articles("show me a product") == "show me product"
    assert remove_articles("list an order") == "list order"


def test_extract_keywords():
    """Test keyword extraction."""
    keywords = extract_keywords("get all the active users")
    assert "active" in keywords
    assert "users" in keywords
    assert "get" not in keywords  # stop word
    assert "all" not in keywords  # stop word
    assert "the" not in keywords  # stop word
