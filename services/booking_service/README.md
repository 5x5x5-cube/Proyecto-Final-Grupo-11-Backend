# Booking Service

Booking management microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
# Install dependencies
poetry install

# Run service
poetry run uvicorn app.main:app --reload --port 8002

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run isort .

# Lint
poetry run flake8 .
```
