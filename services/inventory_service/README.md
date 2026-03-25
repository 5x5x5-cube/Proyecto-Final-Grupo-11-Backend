# Inventory Service

Inventory management microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8006
poetry run pytest
```
