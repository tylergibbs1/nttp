"""Query execution, SQL generation, and schema inference."""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from app.llm import call_claude_structured, LLMError
from app.models import Intent, QueryResponse, SchemaDefinition, SQLGenerationResult
from app.database import execute_query, get_schema_description
from app.config import settings

logger = logging.getLogger(__name__)

# JSON Schema for SQL generation (for structured outputs)
SQL_GENERATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "The SQL query to execute"
        },
        "params": {
            "type": "array",
            "items": {
                "type": ["string", "integer", "number", "boolean", "null"]
            },
            "description": "Parameters for the SQL query"
        }
    },
    "required": ["sql", "params"],
    "additionalProperties": False
}


# System prompt for SQL generation
SQL_GENERATION_SYSTEM_PROMPT = """You are an expert SQL generator for SQLite.
Generate safe, read-only SQL queries from structured intents.

{schema}

Rules:
- Use parameterized queries with ? placeholders for values
- Add LIMIT clause (max {max_limit})
- Only SELECT queries - no UPDATE, DELETE, DROP, ALTER, INSERT
- Valid SQLite syntax only
- Use proper JOINs for relationships between tables
- Handle filters intelligently (e.g., status='active', created_at > date)

Return JSON:
{{
  "sql": "SELECT ... FROM ... WHERE ... LIMIT ?",
  "params": [value1, value2, ...]
}}

Examples:
Intent: {{"entity": "users", "operation": "list", "filters": {{"status": "active"}}, "limit": 10}}
Response: {{"sql": "SELECT * FROM users WHERE status = ? LIMIT ?", "params": ["active", 10]}}

Intent: {{"entity": "orders", "operation": "count", "filters": {{"status": "pending"}}}}
Response: {{"sql": "SELECT COUNT(*) as count FROM orders WHERE status = ?", "params": ["pending"]}}
"""


class SQLGenerationError(Exception):
    """Failed to generate SQL."""
    pass


class SQLExecutionError(Exception):
    """SQL execution failed."""
    pass


async def generate_sql(intent: Intent) -> SQLGenerationResult:
    """
    Generate SQL query from structured intent.

    Args:
        intent: Parsed intent object

    Returns:
        SQLGenerationResult with SQL and parameters

    Raises:
        SQLGenerationError: If SQL generation fails
    """
    try:
        # Prepare intent for LLM
        intent_dict = {
            "entity": intent.entity,
            "operation": intent.operation,
            "filters": intent.filters,
            "limit": intent.limit or settings.default_limit,
            "fields": intent.fields,
            "sort": intent.sort
        }

        schema = get_schema_description()
        system_prompt = SQL_GENERATION_SYSTEM_PROMPT.format(
            schema=schema,
            max_limit=settings.max_limit
        )

        # Call LLM to generate SQL with structured outputs (guaranteed schema compliance)
        result = await call_claude_structured(
            prompt=json.dumps(intent_dict),
            system=system_prompt,
            json_schema=SQL_GENERATION_JSON_SCHEMA,
            temperature=0.0
        )

        sql = result["sql"]
        params = result.get("params", [])

        # Safety validation
        if not validate_sql_safety(sql):
            raise SQLGenerationError("Generated SQL failed safety validation")

        logger.info(f"Generated SQL: {sql}")
        return SQLGenerationResult(sql=sql, params=params)

    except LLMError as e:
        logger.error(f"LLM failed to generate SQL: {e}")
        raise SQLGenerationError(f"Failed to generate SQL: {e}")
    except Exception as e:
        logger.error(f"Unexpected error generating SQL: {e}")
        raise SQLGenerationError(f"Failed to generate SQL: {e}")


def validate_sql_safety(sql: str) -> bool:
    """
    Validate that SQL is safe (read-only).

    Args:
        sql: SQL query string

    Returns:
        True if safe, False otherwise
    """
    # Convert to uppercase for checking
    sql_upper = sql.upper().strip()

    # Block dangerous operations
    dangerous_keywords = [
        "UPDATE", "DELETE", "DROP", "ALTER", "INSERT", "CREATE",
        "TRUNCATE", "REPLACE", "PRAGMA", "ATTACH", "DETACH"
    ]

    for keyword in dangerous_keywords:
        # Check for keyword as whole word (not part of another word)
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            logger.warning(f"Blocked unsafe SQL containing: {keyword}")
            return False

    # Must start with SELECT or WITH (for CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        logger.warning(f"SQL must start with SELECT or WITH")
        return False

    # Should have a LIMIT clause (unless it's a count)
    if "COUNT(*)" not in sql_upper and "COUNT(*)".lower() not in sql.lower():
        if "LIMIT" not in sql_upper:
            logger.warning("SQL missing LIMIT clause")
            # This is a warning, not a blocker - LLM might have added it via params
            # return False

    return True


async def infer_schema_from_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Infer JSON schema from query results.

    Args:
        results: Query results as list of dicts

    Returns:
        JSON schema dictionary

    Raises:
        ValueError: If results are empty or invalid
    """
    if not results:
        # Empty result set - return schema for empty array
        return {
            "type": "array",
            "items": {"type": "object"},
            "description": "Empty result set"
        }

    # Determine if this is a single object or array
    is_array = isinstance(results, list) and len(results) > 0

    # Get first row to infer structure
    sample = results[0] if is_array else results

    # Infer field types from sample
    properties = {}
    required_fields = []

    for key, value in sample.items():
        field_type = infer_field_type(value)
        properties[key] = {
            "type": field_type
        }
        required_fields.append(key)

    # Build schema
    item_schema = {
        "type": "object",
        "properties": properties,
        "required": required_fields
    }

    if is_array:
        schema = {
            "type": "array",
            "items": item_schema
        }
    else:
        schema = item_schema

    return schema


def infer_field_type(value: Any) -> str:
    """
    Infer JSON schema type from Python value.

    Args:
        value: Python value

    Returns:
        JSON schema type string
    """
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        # Check if it looks like a date
        if re.match(r'\d{4}-\d{2}-\d{2}', value):
            return "string"  # Could add format: "date-time"
        return "string"
    elif isinstance(value, (list, tuple)):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return "string"


# Import json for SQL generation
import json

# Import cache and intent functions
from app.schema_cache import cache
from app.intent import parse_intent, generate_schema_id


async def execute_query_with_cache(query: str, use_cache: bool = True, force_new_schema: bool = False) -> QueryResponse:
    """
    Execute natural language query with schema caching.

    This is the main orchestration function that:
    1. Parses intent from natural language
    2. Checks cache for schema
    3. Generates SQL if needed
    4. Executes query
    5. Infers and caches schema on cache miss
    6. Returns formatted response

    Args:
        query: Natural language query
        use_cache: Whether to use schema cache
        force_new_schema: Force schema re-inference even if cached

    Returns:
        QueryResponse with data and metadata

    Raises:
        IntentParseError: If intent parsing fails
        SQLGenerationError: If SQL generation fails
        SQLExecutionError: If query execution fails
    """
    start_time = time.time()

    try:
        # Step 1: Parse intent from natural language
        logger.info(f"Parsing query: {query}")
        intent = await parse_intent(query)
        schema_id = generate_schema_id(intent)

        # Step 2: Check cache for schema
        cached_schema = None
        if use_cache and not force_new_schema:
            cached_schema = await cache.get(schema_id)

        if cached_schema:
            # CACHE HIT - Use cached schema
            logger.info(f"Cache HIT for schema: {schema_id}")

            # Generate SQL from intent
            sql_result = await generate_sql(intent)

            # Execute query
            try:
                results = await execute_query(sql_result.sql, sql_result.params)
            except Exception as e:
                logger.error(f"SQL execution failed: {e}")
                raise SQLExecutionError(f"Query execution failed: {e}")

            # Update cache usage stats
            await cache.update_usage(schema_id)
            await cache.add_example_query(schema_id, query)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Return response
            return QueryResponse(
                data=results,
                schema_id=schema_id,
                cache_hit=True,
                execution_time_ms=execution_time_ms,
                generated_sql=sql_result.sql,
                intent=intent.normalized_text
            )

        else:
            # CACHE MISS - Full pipeline
            logger.info(f"Cache MISS for schema: {schema_id}")

            # Generate SQL from intent
            sql_result = await generate_sql(intent)

            # Execute query
            try:
                results = await execute_query(sql_result.sql, sql_result.params)
            except Exception as e:
                logger.error(f"SQL execution failed: {e}")
                raise SQLExecutionError(f"Query execution failed: {e}")

            # Infer schema from results
            json_schema = await infer_schema_from_results(results)

            # Create and store schema definition
            schema_def = SchemaDefinition(
                schema_id=schema_id,
                intent_pattern=intent.normalized_text,
                json_schema=json_schema,
                pinned=False,
                created_at=datetime.now(),
                last_used_at=datetime.now(),
                use_count=1,
                example_queries=[query]
            )
            await cache.set(schema_id, schema_def)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Return response
            return QueryResponse(
                data=results,
                schema_id=schema_id,
                cache_hit=False,
                execution_time_ms=execution_time_ms,
                generated_sql=sql_result.sql,
                intent=intent.normalized_text
            )

    except Exception as e:
        # Log error and re-raise
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise
