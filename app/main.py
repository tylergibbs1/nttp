"""FastAPI application with NTTP endpoints."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.models import (
    QueryRequest, QueryResponse, SchemaListResponse,
    IntentListResponse, ExplainResponse, ErrorResponse
)
from app.executor import (
    execute_query_with_cache, generate_sql,
    SQLGenerationError, SQLExecutionError
)
from app.intent import parse_intent, generate_schema_id, IntentParseError
from app.schema_cache import cache
from app.llm import LLMError
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting NTTP API server...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down NTTP API server...")


# Create FastAPI app
app = FastAPI(
    title="NTTP API",
    description="Natural Text Transfer Protocol - Query databases with natural language",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(IntentParseError)
async def intent_parse_error_handler(request, exc):
    """Handle intent parsing errors."""
    return JSONResponse(
        status_code=400,
        content={
            "error": "IntentParseError",
            "message": str(exc),
            "suggestion": "Try rephrasing your query or being more specific about what you want."
        }
    )


@app.exception_handler(SQLGenerationError)
async def sql_generation_error_handler(request, exc):
    """Handle SQL generation errors."""
    return JSONResponse(
        status_code=400,
        content={
            "error": "SQLGenerationError",
            "message": str(exc),
            "suggestion": "The query could not be converted to SQL. Try simplifying your request."
        }
    )


@app.exception_handler(SQLExecutionError)
async def sql_execution_error_handler(request, exc):
    """Handle SQL execution errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "SQLExecutionError",
            "message": str(exc),
            "suggestion": "There was an error executing the database query. Please try again."
        }
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request, exc):
    """Handle LLM API errors."""
    return JSONResponse(
        status_code=502,
        content={
            "error": "LLMError",
            "message": "AI service temporarily unavailable",
            "suggestion": "Please try again in a moment."
        }
    )


# Core query endpoints
@app.post("/query", response_model=QueryResponse)
async def query_post(request: QueryRequest):
    """
    Execute natural language query.

    This is the main endpoint for NTTP queries. It accepts a natural language
    query and returns structured data with an inferred or cached schema.

    Args:
        request: QueryRequest with query string and options

    Returns:
        QueryResponse with data, schema_id, and metadata

    Example:
        ```
        POST /query
        {
          "query": "get all active users",
          "use_cache": true
        }
        ```
    """
    try:
        return await execute_query_with_cache(
            query=request.query,
            use_cache=request.use_cache,
            force_new_schema=request.force_new_schema
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query", response_model=QueryResponse)
async def query_get(
    q: str = Query(..., description="Natural language query"),
    use_cache: bool = Query(True, description="Use schema cache"),
    force_new_schema: bool = Query(False, description="Force schema re-inference")
):
    """
    Execute natural language query (GET convenience endpoint).

    Same as POST /query but accepts query parameters for easy testing.

    Example:
        ```
        GET /query?q=show+me+active+users
        ```
    """
    try:
        return await execute_query_with_cache(
            query=q,
            use_cache=use_cache,
            force_new_schema=force_new_schema
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Schema management endpoints
@app.get("/schemas", response_model=SchemaListResponse)
async def list_schemas():
    """
    List all cached schemas.

    Returns metadata for all schemas in the cache including usage statistics.

    Example response:
        ```json
        {
          "schemas": [
            {
              "schema_id": "a1b2c3d4e5f6g7h8",
              "intent_pattern": "entity:users|operation:list|filters:status=active",
              "use_count": 42,
              "pinned": false,
              "created_at": "2024-01-15T10:30:00",
              "last_used_at": "2024-01-15T14:20:00"
            }
          ],
          "total": 1
        }
        ```
    """
    schemas = await cache.list_all()
    schema_list = [
        {
            "schema_id": s.schema_id,
            "intent_pattern": s.intent_pattern,
            "use_count": s.use_count,
            "pinned": s.pinned,
            "created_at": s.created_at.isoformat(),
            "last_used_at": s.last_used_at.isoformat(),
            "example_queries": s.example_queries
        }
        for s in schemas
    ]
    return SchemaListResponse(schemas=schema_list, total=len(schema_list))


@app.get("/schemas/{schema_id}")
async def get_schema(schema_id: str):
    """
    Get specific schema details.

    Returns complete schema definition including JSON schema structure.

    Args:
        schema_id: Schema identifier

    Returns:
        Full schema definition with JSON schema
    """
    schema = await cache.get(schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    return {
        "schema_id": schema.schema_id,
        "intent_pattern": schema.intent_pattern,
        "json_schema": schema.json_schema,
        "pinned": schema.pinned,
        "created_at": schema.created_at.isoformat(),
        "last_used_at": schema.last_used_at.isoformat(),
        "use_count": schema.use_count,
        "example_queries": schema.example_queries
    }


@app.put("/schemas/{schema_id}/pin")
async def pin_schema(schema_id: str):
    """
    Pin schema to prevent eviction.

    Pinned schemas are never removed from the cache automatically.

    Args:
        schema_id: Schema identifier
    """
    success = await cache.pin(schema_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"status": "pinned", "schema_id": schema_id}


@app.put("/schemas/{schema_id}/unpin")
async def unpin_schema(schema_id: str):
    """
    Unpin schema to allow eviction.

    Args:
        schema_id: Schema identifier
    """
    success = await cache.unpin(schema_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"status": "unpinned", "schema_id": schema_id}


@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: str):
    """
    Delete schema from cache.

    Pinned schemas cannot be deleted and will return an error.

    Args:
        schema_id: Schema identifier
    """
    schema = await cache.get(schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    if schema.pinned:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete pinned schema. Unpin first."
        )

    await cache.delete(schema_id)
    return {"status": "deleted", "schema_id": schema_id}


# Utility endpoints
@app.get("/intents", response_model=IntentListResponse)
async def list_intents():
    """
    List known intent patterns.

    Returns all cached intent patterns sorted by usage frequency.
    This helps understand what queries the system has learned.

    Example response:
        ```json
        {
          "intents": [
            {
              "pattern": "entity:users|operation:list|filters:status=active",
              "schema_id": "a1b2c3d4e5f6g7h8",
              "use_count": 42,
              "example_queries": ["get active users", "show me active users"]
            }
          ],
          "total": 1
        }
        ```
    """
    schemas = await cache.list_all()
    intents = [
        {
            "pattern": s.intent_pattern,
            "schema_id": s.schema_id,
            "use_count": s.use_count,
            "example_queries": s.example_queries
        }
        for s in sorted(schemas, key=lambda x: x.use_count, reverse=True)
    ]
    return IntentListResponse(intents=intents, total=len(intents))


@app.post("/explain", response_model=ExplainResponse)
async def explain_query(request: QueryRequest):
    """
    Explain query without executing.

    Shows how the query would be parsed, what SQL would be generated,
    and what schema would be used - all without actually running the query.

    Useful for debugging and understanding the system's interpretation.

    Args:
        request: QueryRequest with query string

    Returns:
        ExplainResponse with intent, SQL, and schema information

    Example:
        ```
        POST /explain
        {
          "query": "get all active users"
        }
        ```
    """
    try:
        # Parse intent
        intent = await parse_intent(request.query)
        schema_id = generate_schema_id(intent)

        # Generate SQL
        sql_result = await generate_sql(intent)

        # Check if schema exists
        cached_schema = await cache.get(schema_id)
        cached_schema_dict = None
        if cached_schema:
            cached_schema_dict = {
                "json_schema": cached_schema.json_schema,
                "use_count": cached_schema.use_count,
                "created_at": cached_schema.created_at.isoformat()
            }

        return ExplainResponse(
            query=request.query,
            intent=intent.dict(),
            sql=sql_result.sql,
            params=sql_result.params,
            schema_id=schema_id,
            cached_schema=cached_schema_dict
        )
    except Exception as e:
        logger.error(f"Query explanation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    cache_stats = await cache.get_stats()
    return {
        "status": "healthy",
        "cache_stats": cache_stats
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "NTTP API",
        "version": "1.0.0",
        "description": "Natural Text Transfer Protocol - Query databases with natural language",
        "docs": "/docs",
        "endpoints": {
            "query": "POST /query or GET /query?q=your+query",
            "schemas": "GET /schemas",
            "intents": "GET /intents",
            "explain": "POST /explain",
            "health": "GET /health"
        }
    }
