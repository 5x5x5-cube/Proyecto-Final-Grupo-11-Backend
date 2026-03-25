# Reports Service

Reports generation microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8005
poetry run pytest
```
