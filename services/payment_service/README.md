# Payment Service

Payment processing microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8009
poetry run pytest
```
