FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry==1.7.1

COPY services/inventory_service/pyproject.toml services/inventory_service/poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

COPY services/inventory_service/app ./app
COPY services/inventory_service/alembic.ini ./
COPY services/inventory_service/alembic/ ./alembic/
COPY services/inventory_service/scripts/ ./scripts/
COPY services/inventory_service/entrypoint.sh ./

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
