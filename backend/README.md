# OpenProxyAI Backend

Zero Trust AI Gateway — FastAPI backend service.

## Quick Start

```bash
cp .env.example .env
# edit .env with your LLM provider API keys

# From repo root:
docker compose up -d

# Run migrations:
cd backend
alembic upgrade head

# Start dev server (with hot reload):
uvicorn app.main:app --reload --port 8000
```
