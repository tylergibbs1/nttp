"""Pydantic models for type-safe data validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Intent(BaseModel):
    """Structured representation of parsed user intent."""

    entity: str = Field(..., description="Target table (users, products, orders, order_items)")
    operation: str = Field(..., description="Operation type (list, count, aggregate, filter)")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filter conditions")
    limit: Optional[int] = Field(None, description="Result limit")
    fields: Optional[List[str]] = Field(None, description="Specific fields to return")
    sort: Optional[str] = Field(None, description="Sort specification (e.g., 'created_at:desc')")
    normalized_text: str = Field(..., description="Normalized intent for cache key generation")


class QueryRequest(BaseModel):
    """Request model for natural language queries."""

    query: str = Field(..., min_length=1, max_length=500, description="Natural language query")
    use_cache: bool = Field(True, description="Whether to use schema cache")
    force_new_schema: bool = Field(False, description="Force schema re-inference")


class QueryResponse(BaseModel):
    """Response model for query results."""

    data: Any = Field(..., description="Query results")
    schema_id: str = Field(..., description="Schema identifier")
    cache_hit: bool = Field(..., description="Whether schema was from cache")
    execution_time_ms: float = Field(..., description="Total execution time in milliseconds")
    generated_sql: Optional[str] = Field(None, description="Generated SQL query (for debugging)")
    intent: Optional[str] = Field(None, description="Normalized intent (for debugging)")


class SchemaDefinition(BaseModel):
    """Cached schema definition."""

    schema_id: str = Field(..., description="Unique schema identifier")
    intent_pattern: str = Field(..., description="Normalized intent pattern")
    json_schema: Dict[str, Any] = Field(..., description="JSON schema for response structure")
    pinned: bool = Field(False, description="Whether schema is pinned (prevent eviction)")
    created_at: datetime = Field(default_factory=datetime.now, description="Schema creation time")
    last_used_at: datetime = Field(default_factory=datetime.now, description="Last usage time")
    use_count: int = Field(0, description="Number of times schema has been used")
    example_queries: List[str] = Field(default_factory=list, description="Example queries using this schema")


class SchemaListResponse(BaseModel):
    """Response model for listing schemas."""

    schemas: List[Dict[str, Any]] = Field(..., description="List of schema metadata")
    total: int = Field(..., description="Total number of schemas")


class IntentListResponse(BaseModel):
    """Response model for listing intents."""

    intents: List[Dict[str, Any]] = Field(..., description="List of intent patterns")
    total: int = Field(..., description="Total number of intents")


class ExplainResponse(BaseModel):
    """Response model for query explanation."""

    query: str = Field(..., description="Original query")
    intent: Dict[str, Any] = Field(..., description="Parsed intent")
    sql: str = Field(..., description="Generated SQL")
    params: List[Any] = Field(..., description="SQL parameters")
    schema_id: str = Field(..., description="Schema ID that would be used")
    cached_schema: Optional[Dict[str, Any]] = Field(None, description="Existing cached schema if available")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    suggestion: Optional[str] = Field(None, description="Suggestion for fixing the error")


class SQLGenerationResult(BaseModel):
    """Result from SQL generation."""

    sql: str = Field(..., description="Generated SQL query")
    params: List[Any] = Field(..., description="Query parameters")


class SchemaInferenceResult(BaseModel):
    """Result from schema inference."""

    json_schema: Dict[str, Any] = Field(..., description="Inferred JSON schema")
    sample_data: Optional[Any] = Field(None, description="Sample data used for inference")
