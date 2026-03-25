.PHONY: help install test lint format docker-up docker-down deploy-local clean

help:
	@echo "Comandos disponibles:"
	@echo "  make install       - Instalar dependencias de todos los servicios"
	@echo "  make test          - Ejecutar tests de todos los servicios"
	@echo "  make lint          - Ejecutar linting en todos los servicios"
	@echo "  make format        - Formatear código de todos los servicios"
	@echo "  make docker-up     - Levantar servicios con Docker Compose"
	@echo "  make docker-down   - Detener servicios Docker Compose"
	@echo "  make deploy-local  - Desplegar localmente con Docker Compose"
	@echo "  make clean         - Limpiar archivos temporales"

install:
	@echo "Instalando dependencias..."
	@for dir in services/*/; do \
		echo "Instalando $$dir..."; \
		cd $$dir && poetry install && cd ../..; \
	done

test:
	@echo "Ejecutando tests..."
	@for dir in services/*/; do \
		echo "Testing $$dir..."; \
		cd $$dir && poetry run pytest && cd ../..; \
	done

lint:
	@echo "Ejecutando linting..."
	@for dir in services/*/; do \
		echo "Linting $$dir..."; \
		cd $$dir && poetry run flake8 app/ tests/ && cd ../..; \
	done

format:
	@echo "Formateando código..."
	@for dir in services/*/; do \
		echo "Formateando $$dir..."; \
		cd $$dir && poetry run black . && poetry run isort . && cd ../..; \
	done

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

deploy-local: docker-up
	@echo "Servicios desplegados localmente"
	@echo "Auth Service: http://localhost:8001"
	@echo "Booking Service: http://localhost:8002"
	@echo "Search Service: http://localhost:8003"
	@echo "Cart Service: http://localhost:8004"
	@echo "Reports Service: http://localhost:8005"
	@echo "Inventory Service: http://localhost:8006"
	@echo "Commercial Service: http://localhost:8007"
	@echo "Notification Service: http://localhost:8008"
	@echo "Payment Service: http://localhost:8009"
	@echo "Health Copilot: http://localhost:8010"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
