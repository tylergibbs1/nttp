"""Intent parsing and normalization for cache key generation."""

import hashlib
import json
import logging
import re
from typing import Dict, Any

from app.llm import call_claude_structured, LLMError
from app.models import Intent
from app.database import get_schema_description

logger = logging.getLogger(__name__)

# JSON Schema for intent parsing (for structured outputs)
INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "entity": {
            "type": "string",
            "description": "Target table name (users, products, orders, or order_items)"
        },
        "operation": {
            "type": "string",
            "enum": ["list", "count", "aggregate", "filter"],
            "description": "Operation type"
        },
        "filters": {
            "type": "object",
            "description": "Filter conditions as key-value pairs",
            "properties": {
                "status": {"type": "string"},
                "category": {"type": "string"},
                "in_stock": {"type": "boolean"},
                "created_at": {"type": "string"},
                "user_id": {"type": "integer"},
                "order_id": {"type": "integer"},
                "product_id": {"type": "integer"}
            },
            "additionalProperties": False
        },
        "limit": {
            "type": ["integer", "null"],
            "description": "Result limit, or null for default"
        },
        "fields": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Specific fields to return, or null for all fields"
        },
        "sort": {
            "type": ["string", "null"],
            "description": "Sort specification (e.g., 'created_at:desc'), or null"
        }
    },
    "required": ["entity", "operation"],
    "additionalProperties": False
}


# System prompt for intent parsing
INTENT_PARSE_SYSTEM_PROMPT = """You are an expert at parsing natural language database queries.
Extract structured intent from user queries about an e-commerce database.

{schema}

Return JSON with this exact structure:
{{
  "entity": "<table_name>",
  "operation": "<list|count|aggregate|filter>",
  "filters": {{"<field>": "<value>"}},
  "limit": <number or null>,
  "fields": [<field names>] or null,
  "sort": "<field:asc|desc>" or null
}}

Rules:
- entity must be one of: users, products, orders, order_items
- operation: "list" for SELECT, "count" for COUNT, "aggregate" for SUM/AVG/etc
- filters: extract conditions (e.g., "active users" -> {{"status": "active"}})
- limit: extract limit if specified, otherwise null
- fields: specific fields requested, or null for all fields
- sort: sorting specification if mentioned

Examples:
- "get all active users" -> {{"entity": "users", "operation": "list", "filters": {{"status": "active"}}, "limit": null}}
- "show me 10 products" -> {{"entity": "products", "operation": "list", "filters": {{}}, "limit": 10}}
- "count pending orders" -> {{"entity": "orders", "operation": "count", "filters": {{"status": "pending"}}, "limit": null}}
"""


class IntentParseError(Exception):
    """Failed to parse user intent."""
    pass


async def parse_intent(query: str) -> Intent:
    """
    Parse natural language query into structured intent.

    Args:
        query: Natural language query

    Returns:
        Structured Intent object

    Raises:
        IntentParseError: If parsing fails
    """
    try:
        # Get schema description
        schema = get_schema_description()
        system_prompt = INTENT_PARSE_SYSTEM_PROMPT.format(schema=schema)

        # Call LLM to parse intent with structured outputs (guaranteed schema compliance)
        result = await call_claude_structured(
            prompt=query,
            system=system_prompt,
            json_schema=INTENT_JSON_SCHEMA,
            temperature=0.0
        )

        # Ensure filters is a dict (guaranteed by schema, but defensive programming)
        if "filters" not in result:
            result["filters"] = {}

        # Generate normalized text for cache key
        normalized = normalize_intent_dict(result)

        # Create Intent object
        intent = Intent(
            entity=result["entity"],
            operation=result["operation"],
            filters=result.get("filters", {}),
            limit=result.get("limit"),
            fields=result.get("fields"),
            sort=result.get("sort"),
            normalized_text=normalized
        )

        logger.info(f"Parsed intent: {intent.entity}.{intent.operation} with {len(intent.filters)} filters")
        return intent

    except LLMError as e:
        logger.error(f"LLM failed to parse intent: {e}")
        raise IntentParseError(f"Failed to understand query: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing intent: {e}")
        raise IntentParseError(f"Failed to parse query: {e}")


def normalize_intent_dict(intent_data: Dict[str, Any]) -> str:
    """
    Normalize intent dictionary to canonical form for cache key generation.

    Args:
        intent_data: Intent dictionary from LLM

    Returns:
        Normalized string representation
    """
    # Extract key components
    entity = intent_data.get("entity", "").lower().strip()
    operation = intent_data.get("operation", "").lower().strip()
    filters = intent_data.get("filters", {})
    limit = intent_data.get("limit")
    fields = intent_data.get("fields", [])
    sort = intent_data.get("sort")

    # Normalize filters: sort keys and convert values to lowercase strings
    normalized_filters = {}
    for key, value in filters.items():
        key_clean = key.lower().strip()
        if isinstance(value, str):
            value_clean = value.lower().strip()
        else:
            value_clean = str(value)
        normalized_filters[key_clean] = value_clean

    # Sort filter keys for consistency
    sorted_filters = dict(sorted(normalized_filters.items()))

    # Build normalized representation
    parts = [
        f"entity:{entity}",
        f"operation:{operation}",
    ]

    if sorted_filters:
        filters_str = ",".join(f"{k}={v}" for k, v in sorted_filters.items())
        parts.append(f"filters:{filters_str}")

    if limit:
        parts.append(f"limit:{limit}")

    if fields:
        fields_str = ",".join(sorted(str(f).lower() for f in fields))
        parts.append(f"fields:{fields_str}")

    if sort:
        parts.append(f"sort:{sort.lower()}")

    return "|".join(parts)


def normalize_intent(intent: Intent) -> str:
    """
    Normalize Intent object to canonical form.

    Args:
        intent: Intent object

    Returns:
        Normalized string representation
    """
    return intent.normalized_text


def generate_schema_id(intent: Intent) -> str:
    """
    Generate unique schema ID from normalized intent.

    Args:
        intent: Intent object

    Returns:
        Schema ID (16-char hash)
    """
    normalized = normalize_intent(intent)
    hash_obj = hashlib.sha256(normalized.encode())
    return hash_obj.hexdigest()[:16]


def remove_articles(text: str) -> str:
    """
    Remove common articles from text for normalization.

    Args:
        text: Input text

    Returns:
        Text with articles removed
    """
    # Remove common articles (a, an, the)
    text = re.sub(r'\b(a|an|the)\b', '', text, flags=re.IGNORECASE)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_keywords(text: str) -> list[str]:
    """
    Extract keywords from query text.

    Args:
        text: Query text

    Returns:
        List of keywords
    """
    # Remove articles
    text = remove_articles(text)

    # Split into words
    words = text.lower().split()

    # Filter out common words
    stop_words = {"get", "show", "list", "all", "me", "my", "the", "a", "an", "of", "for", "to", "in", "on"}
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return keywords
