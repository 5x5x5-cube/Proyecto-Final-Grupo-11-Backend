.PHONY: help install setup test lint format format-check docker-up docker-down deploy-local clean \
        aws-setup aws-backend aws-init aws-plan aws-deploy aws-destroy \
        k8s-setup k8s-deploy k8s-status k8s-logs k8s-delete \
        docker-build docker-push deploy-all

help:
	@echo "=========================================="
	@echo "  COMANDOS DE DESARROLLO LOCAL"
	@echo "=========================================="
	@echo "  make setup         - Instalar dependencias + configurar git hooks"
	@echo "  make install       - Instalar dependencias de todos los servicios"
	@echo "  make test          - Ejecutar tests de todos los servicios"
	@echo "  make lint          - Ejecutar linting en todos los servicios"
	@echo "  make format        - Formatear código de todos los servicios"
	@echo "  make format-check  - Verificar formato sin modificar archivos"
	@echo "  make docker-up     - Levantar servicios con Docker Compose"
	@echo "  make docker-down   - Detener servicios Docker Compose"
	@echo "  make deploy-local  - Desplegar localmente con Docker Compose"
	@echo "  make clean         - Limpiar archivos temporales"
	@echo ""
	@echo "=========================================="
	@echo "  COMANDOS DE DESPLIEGUE AWS"
	@echo "=========================================="
	@echo "  make aws-setup     - Configurar AWS CLI y verificar credenciales"
	@echo "  make aws-backend   - Crear S3 bucket y DynamoDB para Terraform"
	@echo "  make aws-init      - Inicializar Terraform"
	@echo "  make aws-plan      - Ver plan de infraestructura Terraform"
	@echo "  make aws-deploy    - Desplegar infraestructura completa en AWS"
	@echo "  make aws-destroy   - Destruir toda la infraestructura AWS"
	@echo ""
	@echo "  make k8s-setup     - Configurar kubectl y crear secrets/configmaps"
	@echo "  make k8s-deploy    - Desplegar servicios en Kubernetes"
	@echo "  make k8s-status    - Ver estado de pods y servicios"
	@echo "  make k8s-logs      - Ver logs de servicios"
	@echo "  make k8s-delete    - Eliminar deployments de Kubernetes"
	@echo ""
	@echo "  make docker-build  - Construir todas las imágenes Docker"
	@echo "  make docker-push   - Subir imágenes a ECR"
	@echo "  make deploy-all    - Despliegue completo (infra + k8s + docker)"
	@echo ""

setup: install
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg
	cp scripts/pre-push-tests.sh .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	@echo "Git hooks configured!"

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

format-check:
	@echo "Verificando formato..."
	@for dir in services/*/; do \
		echo "Verificando $$dir..."; \
		cd $$dir && poetry run black --check . && poetry run isort --check-only . && cd ../..; \
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

# ==========================================
# AWS DEPLOYMENT COMMANDS
# ==========================================

aws-setup:
	@echo "🔧 Verificando configuración de AWS CLI..."
	@aws --version || (echo "❌ AWS CLI no instalado. Instala desde: https://aws.amazon.com/cli/" && exit 1)
	@aws sts get-caller-identity && echo "✅ AWS CLI configurado correctamente" || (echo "❌ Ejecuta: aws configure" && exit 1)
	@terraform --version || (echo "❌ Terraform no instalado. Instala desde: https://terraform.io" && exit 1)
	@kubectl version --client || (echo "❌ kubectl no instalado. Instala desde: https://kubernetes.io/docs/tasks/tools/" && exit 1)
	@echo "✅ Todas las herramientas están instaladas"

aws-backend:
	@echo "📦 Creando backend de Terraform (S3 + DynamoDB)..."
	@aws s3 mb s3://proyecto-final-terraform-state --region us-east-1 2>/dev/null || echo "Bucket ya existe"
	@aws s3api put-bucket-versioning --bucket proyecto-final-terraform-state --versioning-configuration Status=Enabled
	@aws dynamodb create-table \
		--table-name proyecto-final-terraform-locks \
		--attribute-definitions AttributeName=LockID,AttributeType=S \
		--key-schema AttributeName=LockID,KeyType=HASH \
		--billing-mode PAY_PER_REQUEST \
		--region us-east-1 2>/dev/null || echo "Tabla DynamoDB ya existe"
	@echo "✅ Backend de Terraform listo"

aws-init: aws-backend
	@echo "🔧 Inicializando Terraform..."
	cd infrastructure/terraform && terraform init
	@echo "✅ Terraform inicializado"

aws-plan: aws-init
	@echo "📋 Generando plan de Terraform..."
	cd infrastructure/terraform && terraform plan
	@echo "✅ Plan generado"

aws-deploy: aws-init
	@echo "🚀 Desplegando infraestructura en AWS..."
	@echo "⚠️  Esto tomará 15-20 minutos y costará ~$$100/mes"
	@read -p "¿Continuar? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	cd infrastructure/terraform && terraform apply -auto-approve
	@echo "✅ Infraestructura desplegada"
	@echo ""
	@echo "📝 Guardando outputs..."
	cd infrastructure/terraform && terraform output > ../../terraform-outputs.txt
	@cat terraform-outputs.txt
	@echo ""
	@echo "✅ Siguiente paso: make k8s-setup"

aws-destroy:
	@echo "🗑️  Destruyendo infraestructura AWS..."
	@echo "⚠️  Esto eliminará TODOS los recursos en AWS"
	@read -p "¿Estás seguro? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	cd infrastructure/terraform && terraform destroy -auto-approve
	@echo "✅ Infraestructura eliminada"

# ==========================================
# KUBERNETES COMMANDS
# ==========================================

k8s-setup:
	@echo "⚙️  Configurando kubectl para EKS..."
	aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
	@echo "✅ kubectl configurado"
	@echo ""
	@echo "🔑 Creando secrets y configmaps..."
	bash scripts/setup-k8s.sh
	@echo "✅ Secrets y ConfigMaps creados"

k8s-deploy: k8s-setup
	@echo "🚀 Desplegando servicios en Kubernetes..."
	kubectl apply -f kubernetes/deployments/
	@echo "⏳ Esperando 10 segundos..."
	@sleep 10
	kubectl apply -f kubernetes/ingress.yaml
	@echo "✅ Servicios desplegados"
	@echo ""
	@echo "📊 Estado actual:"
	@make k8s-status

k8s-status:
	@echo "📊 Estado de Kubernetes:"
	@echo ""
	@echo "=== PODS ==="
	kubectl get pods -o wide
	@echo ""
	@echo "=== SERVICES ==="
	kubectl get services
	@echo ""
	@echo "=== INGRESS ==="
	kubectl get ingress
	@echo ""
	@echo "=== LOAD BALANCER URL ==="
	@kubectl get ingress api-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "Esperando ALB..."

k8s-logs:
	@echo "📜 Logs de servicios principales:"
	@echo ""
	@echo "=== INVENTORY SERVICE ==="
	kubectl logs -l app=inventory-service --tail=50
	@echo ""
	@echo "=== SEARCH SERVICE ==="
	kubectl logs -l app=search-service --tail=50
	@echo ""
	@echo "=== SEARCH WORKER ==="
	kubectl logs -l app=search-worker --tail=50

k8s-delete:
	@echo "🗑️  Eliminando deployments de Kubernetes..."
	kubectl delete -f kubernetes/deployments/ || true
	kubectl delete -f kubernetes/ingress.yaml || true
	@echo "✅ Deployments eliminados"

# ==========================================
# DOCKER BUILD & PUSH
# ==========================================

docker-build:
	@echo "🔨 Construyendo imágenes Docker..."
	@ECR_REGISTRY=$$(aws ecr describe-repositories --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1); \
	for service in auth_service booking_service search_service cart_service reports_service inventory_service commercial_service notification_service payment_service health_copilot; do \
		SERVICE_NAME=$$(echo $$service | sed 's/_/-/g'); \
		echo "Building $$SERVICE_NAME..."; \
		docker build -t $$ECR_REGISTRY/proyecto-final-dev-$$SERVICE_NAME:latest services/$$service/ || exit 1; \
	done
	@echo "✅ Todas las imágenes construidas"

docker-push:
	@echo "📤 Subiendo imágenes a ECR..."
	@ECR_REGISTRY=$$(aws ecr describe-repositories --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $$ECR_REGISTRY; \
	for service in auth_service booking_service search_service cart_service reports_service inventory_service commercial_service notification_service payment_service health_copilot; do \
		SERVICE_NAME=$$(echo $$service | sed 's/_/-/g'); \
		echo "Pushing $$SERVICE_NAME..."; \
		docker push $$ECR_REGISTRY/proyecto-final-dev-$$SERVICE_NAME:latest || exit 1; \
	done
	@echo "✅ Todas las imágenes subidas a ECR"

# ==========================================
# FULL DEPLOYMENT
# ==========================================

deploy-all: aws-setup aws-deploy docker-build docker-push k8s-deploy
	@echo ""
	@echo "=========================================="
	@echo "  ✅ DESPLIEGUE COMPLETO EXITOSO"
	@echo "=========================================="
	@echo ""
	@echo "🌐 URL del Load Balancer:"
	@kubectl get ingress api-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
	@echo ""
	@echo ""
	@echo "📊 Para ver el estado: make k8s-status"
	@echo "📜 Para ver logs: make k8s-logs"
	@echo "🗑️  Para eliminar todo: make aws-destroy"
	@echo ""
