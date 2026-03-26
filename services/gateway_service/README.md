# Gateway Service

API Gateway for TravelHub — single entry point for all client requests.

## Endpoints

- `GET /health` — Health check
- `GET /api/v1/{service}/*` — Proxies to the appropriate backend microservice

## Development

```bash
poetry install
poetry run pytest
poetry run uvicorn app.main:app --reload --port 8080
```
