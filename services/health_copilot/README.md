# Health Copilot

Health monitoring and copilot microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8010
poetry run pytest
```
