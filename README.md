# Prompt Service

FastAPI service for managing LLM prompt configurations and generation parameters.

## Overview

The Prompt Service provides CRUD operations for prompt templates, model configurations, and generation parameters used by the LLM services. It stores configurations in Supabase PostgreSQL and serves them via a REST API.

## Technology Stack

- **Python**: 3.11
- **Framework**: FastAPI 0.115.12
- **Server**: Uvicorn 0.34.0
- **Validation**: Pydantic 2.11.1
- **HTTP Client**: httpx 0.28.1
- **Database**: Supabase PostgreSQL

## API Endpoints

### Health Check
```
GET /health
```

### Prompt Management
```
POST   /api/v1/prompts           - Create new prompt configuration
GET    /api/v1/prompts           - List all prompt configurations
GET    /api/v1/prompts/{id}      - Get specific prompt configuration
PATCH  /api/v1/prompts/{id}      - Update prompt configuration
DELETE /api/v1/prompts/{id}      - Delete prompt configuration
```

## Request/Response Examples

### Create Prompt
```bash
POST /api/v1/prompts
```
```json
{
  "id": "summary-v2.1",
  "name": "Summary Generation v2.1",
  "template": "You are an expert at analyzing club event insights...",
  "modelName": "llama3.2",
  "temperature": 0.2,
  "maxTokens": 1000
}
```

### Response
```json
{
  "id": "summary-v2.1",
  "name": "Summary Generation v2.1",
  "template": "You are an expert at analyzing club event insights...",
  "modelName": "llama3.2",
  "temperature": 0.2,
  "maxTokens": 1000,
  "createdAt": "2026-03-16T10:00:00Z",
  "updatedAt": "2026-03-16T10:00:00Z"
}
```

## Environment Variables

### Required
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase service role key

### Optional
- `PROMPT_TABLE` - Database table name (default: `prompt_configs`)
- `PROMPT_TIMEOUT_MS` - Request timeout in milliseconds (default: `10000`)

## Database Schema

The service expects a `prompt_configs` table in Supabase with the following structure:

```sql
CREATE TABLE prompt_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    template TEXT NOT NULL,
    model_name TEXT NOT NULL,
    temperature REAL NOT NULL CHECK (temperature >= 0.0 AND temperature <= 2.0),
    max_tokens INTEGER NOT NULL CHECK (max_tokens > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Locally
```bash
# Set environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8084 --reload
```

### Docker
```bash
# Build
docker build -t prompt-service .

# Run
docker run -p 8084:8084 \
  -e SUPABASE_URL="your-supabase-url" \
  -e SUPABASE_KEY="your-supabase-key" \
  prompt-service
```

## API Documentation

- **Swagger UI**: http://localhost:8084/docs
- **OpenAPI JSON**: http://localhost:8084/openapi.json

## Health Check

```bash
curl http://localhost:8084/health
```

Response:
```json
{
  "status": "ok",
  "service": "prompt"
}
```

## Error Handling

The service returns appropriate HTTP status codes:
- `200` - Success
- `201` - Created
- `204` - No Content (delete)
- `400` - Bad Request (validation errors)
- `404` - Not Found
- `409` - Conflict (duplicate ID)
- `502` - Bad Gateway (Supabase errors)