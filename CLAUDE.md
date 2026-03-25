# TravelHub Backend

## Project Overview

Python monorepo with 10 FastAPI microservices, each managed independently with Poetry. Stack: Python 3.11, FastAPI, PostgreSQL (via asyncpg + SQLAlchemy), Redis, Docker, Kubernetes (AWS EKS), Terraform.

## Project Structure

```
services/                    # One directory per microservice
│   ├── auth_service/        # Port 8001
│   ├── booking_service/     # Port 8002
│   ├── search_service/      # Port 8003
│   ├── cart_service/        # Port 8004
│   ├── reports_service/     # Port 8005
│   ├── inventory_service/   # Port 8006
│   ├── commercial_service/  # Port 8007
│   ├── notification_service/# Port 8008
│   ├── payment_service/     # Port 8009
│   └── health_copilot/      # Port 8010
infrastructure/terraform/    # VPC, EKS, ECR, RDS modules
kubernetes/deployments/      # K8s manifests per service
.github/workflows/           # ci.yml, build-push.yml, deploy-eks.yml, terraform.yml
```

Each service follows this internal layout:

```
services/<name>/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI app, /health and / endpoints required
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── Dockerfile
├── pyproject.toml       # Poetry config, Black/isort/pytest settings
└── README.md
```

## Key Commands

Run from the repo root — these iterate over all services:

```bash
make install       # poetry install in every service
make test          # poetry run pytest in every service
make lint          # poetry run flake8 app/ tests/ in every service
make format        # poetry run black . && poetry run isort . in every service
make docker-up     # docker-compose up -d
make docker-down   # docker-compose down
make clean         # remove __pycache__, .pyc, .pytest_cache, htmlcov
```

Run against a single service:

```bash
cd services/<name>
poetry install
poetry run pytest
poetry run pytest --cov=app --cov-report=html
poetry run black .
poetry run isort .
poetry run flake8 app/ tests/
poetry run bandit -r app/
```

## Code Style

All settings are defined in each service's `pyproject.toml`:

- **Black** — line length 100, target Python 3.11
- **isort** — profile `black`, line length 100 (ensures import order is compatible with Black)
- **Flake8** — runs on `app/` and `tests/` only
- **Bandit** — security linting on `app/` (runs in CI)
- **mypy** is installed as a dev dependency but not enforced in CI yet

Always run `make format` before committing. CI will fail on Black or isort violations.

## Testing Conventions

- Test files live in `services/<name>/tests/`, prefixed with `test_`.
- `asyncio_mode = "auto"` is set globally — async test functions work without the `@pytest.mark.asyncio` decorator.
- `testpaths = ["tests"]` — pytest only looks in the `tests/` directory.
- Use `httpx` (already a dev dependency) with FastAPI's `TestClient` or `AsyncClient` for endpoint tests.
- Coverage is collected with `--cov=app` in CI and uploaded to Codecov per service.

## Pre-commit Hooks

The repo does not have a `.pre-commit-config.yaml` at the root. Linting and tests are enforced exclusively through CI on push/PR. Run `make lint` and `make format` manually before opening a PR.

## CI Pipeline

Defined in `.github/workflows/ci.yml`. Triggers on push to `main`, `develop`, `feature/**` and on PRs to `main`/`develop`.

- Uses `dorny/paths-filter` to detect which services changed — only affected services are tested.
- Per changed service, runs in order:
  1. `poetry install`
  2. `black --check .` (format check)
  3. `isort --check-only .` (import order check)
  4. `flake8 app/ tests/` (lint)
  5. `bandit -r app/` (security scan)
  6. `pytest --cov=app --cov-report=xml` (tests + coverage)
  7. Coverage uploaded to Codecov
- A final `all-tests-passed` job acts as a required status gate.

Other workflows: `build-push.yml` (Docker → ECR), `deploy-eks.yml` (EKS deploy + rollback), `terraform.yml` (infra plan/apply).

## Adding or Modifying a Service

1. Copy an existing service directory as a template (e.g., `cp -r services/auth_service services/my_service`).
2. Update `pyproject.toml`: change `name`, `description`, and port references.
3. Implement the FastAPI app in `app/main.py`. Always include `/health` and `/` endpoints.
4. Add tests under `tests/`.
5. Update `docker-compose.yml` with the new service and its port.
6. Add a Kubernetes manifest under `kubernetes/deployments/`.
7. Register the service in `.github/workflows/ci.yml` under `detect-changes.filters` and `build-push.yml`.
8. Run `make lint` and `make test` to verify everything passes before pushing.

## Pull Requests

- All PRs must follow the template in `.github/PULL_REQUEST_TEMPLATE.md`
- Every PR must include:
  - **Ticket**: link to the related ticket/issue
  - **Descripción**: brief description of the changes
  - **Cambios realizados**: bullet list of specific changes made
- Write PR descriptions in Spanish
- Use conventional commit format for PR titles in English: `type(scope): description`
