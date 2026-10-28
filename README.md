# NTTP (Natural Text Transfer Protocol)

Replace traditional API development with natural language requests that return structured, schema-consistent data.

NTTP accepts plain text queries and returns structured data with automatically inferred and cached schemas for consistency. Built with **Anthropic's Structured Outputs** for guaranteed schema compliance and zero JSON parsing errors.

```bash
# Example query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "get all active users who signed up this month"}'
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (DATABASE_PATH and LOG_LEVEL are optional)
```

### 3. Initialize database

```bash
python scripts/seed_db.py
```

### 4. Run server

```bash
uvicorn app.main:app --reload
```

### 5. Try it out

Visit `http://localhost:8000/docs` for interactive API documentation, or see [QUICKSTART.md](QUICKSTART.md) for example queries.

## How it works

![NTTP Architecture](public/figure1.jpeg)

### Flow

```
HTTP Request → Intent Parser (LLM) → Cache Lookup → [hit: format] / [miss: SQL Gen → Execute → Infer Schema → Cache]
```

## Features

### Core Capabilities
- **Natural Language Queries**: No need to write SQL or API calls
- **Schema Inference**: Response structure automatically determined on first request
- **Schema Caching**: Consistent responses for similar queries (sub-50ms cache hits)
- **Type Safety**: Pydantic models throughout
- **Read-Only**: Safe, SELECT-only queries

### Reliability & Performance
- **🎯 Structured Outputs**: Uses Anthropic's beta feature for guaranteed schema compliance
  - **Zero JSON parsing errors**: Responses always match schema
  - **Type-safe guarantees**: No more missing fields or wrong types
  - **Automatic validation**: No retries needed for schema violations
- **⚡ Grammar Caching**: First-query compilation, then sub-50ms cache hits
- **🔒 Production-Ready**: Comprehensive error handling and logging

## API endpoints

- `POST /query` - Execute natural language query
- `GET /query?q=...` - Same, as a GET request (handy for testing)
- `POST /explain` - Explain query without executing
- `GET /schemas` - List cached schemas
- `GET /schemas/{schema_id}` - Get specific schema
- `PUT /schemas/{schema_id}/pin` / `PUT /schemas/{schema_id}/unpin` - Pin or unpin a cached schema
- `DELETE /schemas/{schema_id}` - Delete a cached schema
- `GET /intents` - List known intent patterns
- `GET /health` - Health check

## Tech stack

- **FastAPI**: Async web framework
- **SQLite + aiosqlite**: Embedded database
- **Claude API (Sonnet 4.5)**: Intent parsing and SQL generation with structured outputs
- **Pydantic**: Data validation
- **Structured Outputs Beta**: Guaranteed schema compliance (no JSON parsing errors)

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)**: 5-minute getting started guide
- **/docs**: Interactive API documentation (http://localhost:8000/docs when server running)

## Development

```bash
pytest
```

Tests live in [tests/](tests).

## Success criteria

- [x] Natural language query interface
- [x] Automatic schema inference and caching
- [x] Sub-50ms cache hit latency
- [x] Schema management endpoints
- [x] Comprehensive test coverage

## License

MIT
