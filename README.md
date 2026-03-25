# Proyecto Final - Backend Microservices

Sistema de microservicios backend construido con FastAPI, Poetry, Docker, Kubernetes (EKS) y Terraform.

## Arquitectura

El proyecto consta de 10 microservicios:

1. **auth-service** (Puerto 8001) - Autenticación y autorización
2. **booking-service** (Puerto 8002) - Gestión de reservas
3. **search-service** (Puerto 8003) - Búsqueda
4. **cart-service** (Puerto 8004) - Carrito de compras
5. **reports-service** (Puerto 8005) - Generación de reportes
6. **inventory-service** (Puerto 8006) - Gestión de inventario
7. **commercial-service** (Puerto 8007) - Lógica comercial
8. **notification-service** (Puerto 8008) - Notificaciones
9. **payment-service** (Puerto 8009) - Procesamiento de pagos
10. **health-copilot** (Puerto 8010) - Monitoreo de salud

## Inicio

### Desarrollo Local con Docker Compose

```bash
# Levantar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```


## Estructura del Proyecto

```
Proyecto-Final-Grupo-11-Backend/
├── services/                    # Microservicios
│   ├── auth_service/
│   ├── booking_service/
│   ├── search_service/
│   ├── cart_service/
│   ├── reports_service/
│   ├── inventory_service/
│   ├── commercial_service/
│   ├── notification_service/
│   ├── payment_service/
│   └── health_copilot/
├── infrastructure/              # Infraestructura como código
│   └── terraform/
│       ├── modules/
│       │   ├── vpc/
│       │   ├── eks/
│       │   ├── ecr/
│       │   └── rds/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── kubernetes/                  # Manifiestos de Kubernetes
│   ├── deployments/
│   └── ingress.yaml
├── .github/                     # CI/CD con GitHub Actions
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── build-push.yml
│   │   ├── deploy-eks.yml
│   │   └── terraform.yml
│   └── scripts/
├── docker-compose.yml
└── README.md
```

## Tecnologías

- **Backend**: Python 3.11, FastAPI
- **Gestión de dependencias**: Poetry
- **Containerización**: Docker
- **Orquestación**: Kubernetes (AWS EKS)
- **Infraestructura**: Terraform
- **CI/CD**: GitHub Actions
- **Bases de datos**: PostgreSQL (RDS), Redis
- **Cloud Provider**: AWS

## Despliegue en AWS EKS

### Prerrequisitos

- AWS CLI configurado
- kubectl instalado
- Terraform instalado
- Cuenta de AWS con permisos adecuados

### 1. Crear Infraestructura con Terraform

```bash
cd infrastructure/terraform

# Inicializar Terraform
terraform init

# Crear bucket S3 para state (primera vez)
aws s3 mb s3://proyecto-final-terraform-state --region us-east-1
aws dynamodb create-table \
  --table-name proyecto-final-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Planificar cambios
terraform plan -var-file=terraform.tfvars

# Aplicar cambios
terraform apply -var-file=terraform.tfvars
```

### 2. Configurar kubectl

```bash
aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
```

### 3. Construir y Subir Imágenes a ECR

```bash
# Login a ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Construir y subir cada servicio
cd services/auth_service
docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-auth-service:latest .
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-auth-service:latest
```

### 4. Desplegar en Kubernetes

```bash
# Aplicar deployments
kubectl apply -f kubernetes/deployments/

# Aplicar ingress
kubectl apply -f kubernetes/ingress.yaml

# Verificar deployments
kubectl get deployments
kubectl get pods
kubectl get services
```

## CI/CD con GitHub Actions

### Workflows Disponibles

1. **CI (Continuous Integration)** - `.github/workflows/ci.yml`
   - Ejecuta en cada push y PR
   - Linting (Black, isort, Flake8)
   - Security scan (Bandit)
   - Tests unitarios
   - Coverage

2. **Build & Push** - `.github/workflows/build-push.yml`
   - Construye imágenes Docker
   - Sube a AWS ECR
   - Actualiza manifests de K8s

3. **Deploy to EKS** - `.github/workflows/deploy-eks.yml`
   - Despliega a EKS
   - Health checks
   - Rollback automático

4. **Terraform** - `.github/workflows/terraform.yml`
   - Valida configuración
   - Plan y Apply
   - Gestión de infraestructura

### Secrets Requeridos en GitHub

```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
```

## Testing

```bash
# Ejecutar tests de un servicio
cd services/auth_service
poetry run pytest

# Con coverage
poetry run pytest --cov=app --cov-report=html

# Todos los servicios
for dir in services/*/; do
  cd "$dir"
  poetry run pytest
  cd ../..
done
```


