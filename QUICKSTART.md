# NTTP Quick Start Guide

Get started with NTTP in 5 minutes!

## Prerequisites

- Python 3.8+
- Anthropic API key (set as environment variable `ANTHROPIC_API_KEY`)

## Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize database with test data**:
   ```bash
   python3 scripts/seed_db.py
   ```

3. **Start the server**:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Visit the interactive docs**:
   Open http://localhost:8000/docs in your browser

## Try Your First Query

### Using the Web UI

1. Go to http://localhost:8000/docs
2. Find the `POST /query` endpoint
3. Click "Try it out"
4. Enter a query like:
   ```json
   {
     "query": "get all active users"
   }
   ```
5. Click "Execute"

### Using curl

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "get all active users"}'
```

### Using the GET endpoint (for testing)

```bash
curl "http://localhost:8000/query?q=show+me+10+products"
```

## Example Queries

Try these natural language queries:

```bash
# List queries
"get all active users"
"show me 10 products"
"list pending orders"

# Count queries
"count active users"
"how many products are in stock"
"count completed orders"

# Filter queries
"get users who signed up recently"
"show me products in the electronics category"
"find orders with status pending"
```

## Explore the API

### List cached schemas:
```bash
curl http://localhost:8000/schemas
```

### Get intent patterns:
```bash
curl http://localhost:8000/intents
```

### Explain a query (without executing):
```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"query": "get active users"}'
```

### Check health:
```bash
curl http://localhost:8000/health
```

## Understanding the Response

```json
{
  "data": [...],              // Your query results
  "schema_id": "a1b2c3d4",    // Unique schema identifier
  "cache_hit": false,         // Was schema from cache?
  "execution_time_ms": 245.5, // How long it took
  "generated_sql": "SELECT...", // SQL that was generated
  "intent": "entity:users|..."  // Normalized intent
}
```

## Running Tests

```bash
pytest tests/ -v
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the interactive API docs at http://localhost:8000/docs
- Check out the [plan file](~/.claude/plans/zany-watching-sphinx.md) for architecture details
- Try pinning frequently-used schemas with `PUT /schemas/{schema_id}/pin`

## Troubleshooting

**Error: "Field required: anthropic_api_key"**
- Make sure `ANTHROPIC_API_KEY` is set in your environment:
  ```bash
  export ANTHROPIC_API_KEY=your_key_here
  ```

**Database not found**
- Run the seed script: `python3 scripts/seed_db.py`

**Port 8000 already in use**
- Use a different port: `uvicorn app.main:app --port 8001`

## Performance Tips

1. **Cache hits are fast**: Similar queries reuse schemas (< 50ms)
2. **Pin important schemas**: Use `PUT /schemas/{schema_id}/pin`
3. **Monitor cache stats**: Check `GET /health` for cache statistics

Enjoy using NTTP! 🚀
