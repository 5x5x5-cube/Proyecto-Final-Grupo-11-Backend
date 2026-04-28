# Guía de Despliegue - Proyecto Final

## Arquitectura

```
Internet → NLB → NGINX Ingress → gateway-service → backend services
                                       ↓
                              auth-service (token validation)
                              inventory-service (hotel resolution)
```

Todo el tráfico `/api/v1/*` pasa por el **gateway-service**, que:
- Valida tokens JWT via el auth-service
- Inyecta `X-User-Id` y `X-Hotel-Id` en las requests hacia los servicios internos
- Los clientes solo envían `Authorization: Bearer <token>`

---

## Prerrequisitos

1. **AWS CLI v2** instalado y configurado
2. **Terraform** >= 1.0
3. **kubectl** instalado
4. **Docker Desktop** con soporte para `--platform linux/amd64`
5. **Credenciales AWS** configuradas:
   ```bash
   aws configure --profile maestria
   # AWS Access Key ID: <tu-key>
   # AWS Secret Access Key: <tu-secret>
   # Default region name: us-east-1
   # Default output format: json
   ```

---

## Crear TODO desde cero

### Paso 1: Crear backend de Terraform

El state de Terraform se almacena en S3. El nombre del bucket debe ser globalmente único.

```bash
# Crear bucket S3 para state (usar tu account ID para unicidad)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile maestria --query Account --output text)

aws s3 mb s3://proyecto-final-tf-state-${AWS_ACCOUNT_ID} --region us-east-1 --profile maestria

aws s3api put-bucket-versioning \
  --bucket proyecto-final-tf-state-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled \
  --profile maestria

# Crear tabla DynamoDB para locks
aws dynamodb create-table \
  --table-name proyecto-final-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --profile maestria
```

> **IMPORTANTE**: Actualizar el bucket name en `infrastructure/terraform/main.tf` → backend "s3" → bucket.

### Paso 2: Crear infraestructura con Terraform (~15-20 min)

```bash
cd infrastructure/terraform
AWS_PROFILE=maestria terraform init
AWS_PROFILE=maestria terraform plan -var-file=terraform.tfvars
AWS_PROFILE=maestria terraform apply -var-file=terraform.tfvars
# Escribir "yes" cuando pregunte
```

Terraform crea:
- **VPC** con subnets públicas y privadas, NAT Gateway
- **EKS** cluster con 2 nodos t3.small
- **RDS** PostgreSQL (db.t3.micro)
- **ElastiCache** Redis (cache.t3.micro)
- **SQS** colas (hotel-sync, payment-booking, notification) + DLQs
- **SNS** topic (command-update) con suscripciones a las colas
- **ECR** 11 repositorios Docker (incluye gateway-service)
- **IAM roles** IRSA para inventory, search, payment, booking, notification

> Si falla con error `ResourceInUseException` en EKS Access Entry, importar:
> ```bash
> AWS_PROFILE=maestria terraform import 'module.eks.aws_eks_access_entry.admin' \
>   'proyecto-final-dev:arn:aws:iam::<ACCOUNT_ID>:root'
> ```
> Luego re-ejecutar `terraform apply`.

> Si falla ElastiCache con `InvalidCredentialsException`, es transitorio — re-ejecutar `terraform apply`.

### Paso 3: Configurar kubectl

```bash
AWS_PROFILE=maestria aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
AWS_PROFILE=maestria kubectl get nodes  # debe mostrar 2 nodos Ready
```

### Paso 4: Crear Secrets y ConfigMaps

```bash
cd infrastructure/terraform

# Obtener outputs de Terraform
DB_ENDPOINT=$(AWS_PROFILE=maestria terraform output -raw rds_endpoint)
DB_NAME=$(AWS_PROFILE=maestria terraform output -raw rds_database_name)
REDIS_ENDPOINT=$(AWS_PROFILE=maestria terraform output -raw redis_endpoint)
HOTEL_SYNC_QUEUE_URL=$(AWS_PROFILE=maestria terraform output -raw sqs_hotel_sync_queue_url)
SNS_TOPIC_ARN=$(AWS_PROFILE=maestria terraform output -raw sns_topic_arn)
PAYMENT_BOOKING_QUEUE_URL=$(AWS_PROFILE=maestria terraform output -raw sns_payment_booking_queue_url)
NOTIFICATION_QUEUE_URL=$(AWS_PROFILE=maestria terraform output -raw sns_notification_queue_url)

# Obtener contraseña de DB
DB_PASSWORD=$(AWS_PROFILE=maestria aws secretsmanager get-secret-value \
  --secret-id proyecto-final-dev-db-password --region us-east-1 \
  --query SecretString --output text)

# Construir URLs
DB_HOST=$(echo "$DB_ENDPOINT" | cut -d: -f1)
DB_PORT=$(echo "$DB_ENDPOINT" | cut -d: -f2)
DATABASE_URL="postgresql+asyncpg://dbadmin:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
REDIS_URL="redis://${REDIS_ENDPOINT}:6379"

# Secrets (database-url por servicio)
for SVC in auth-service inventory-service cart-service payment-service booking-service; do
    AWS_PROFILE=maestria kubectl create secret generic ${SVC}-secrets \
      --from-literal=database-url="$DATABASE_URL" \
      --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -
done

# Notification service necesita expo-access-token adicional
AWS_PROFILE=maestria kubectl create secret generic notification-service-secrets \
  --from-literal=database-url="$DATABASE_URL" \
  --from-literal=expo-access-token="<tu-expo-token>" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

# ConfigMaps por servicio
AWS_PROFILE=maestria kubectl create configmap cart-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

AWS_PROFILE=maestria kubectl create configmap notification-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

AWS_PROFILE=maestria kubectl create configmap inventory-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=sqs-queue-url="$HOTEL_SYNC_QUEUE_URL" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

AWS_PROFILE=maestria kubectl create configmap search-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=sqs-queue-url="$HOTEL_SYNC_QUEUE_URL" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

# Shared ConfigMaps (usados por múltiples servicios)
AWS_PROFILE=maestria kubectl create configmap shared-infra-config \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=sqs-queue-url="$HOTEL_SYNC_QUEUE_URL" \
  --from-literal=sns-topic-arn="$SNS_TOPIC_ARN" \
  --from-literal=payment-booking-queue-url="$PAYMENT_BOOKING_QUEUE_URL" \
  --from-literal=notification-queue-url="$NOTIFICATION_QUEUE_URL" \
  --from-literal=aws-region="us-east-1" \
  --from-literal=aws-endpoint-url="" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -

AWS_PROFILE=maestria kubectl create configmap shared-service-discovery \
  --from-literal=inventory-service-url="http://inventory-service:80" \
  --from-literal=booking-service-url="http://booking-service:80" \
  --from-literal=cart-service-url="http://cart-service:80" \
  --from-literal=search-service-url="http://search-service:80" \
  --from-literal=notification-service-url="http://notification-service:80" \
  --from-literal=auth-service-url="http://auth-service:80" \
  --from-literal=payment-service-url="http://payment-service:80" \
  --from-literal=reports-service-url="http://reports-service:80" \
  --from-literal=commercial-service-url="http://commercial-service:80" \
  --dry-run=client -o yaml | AWS_PROFILE=maestria kubectl apply -f -
```

### Paso 5: Construir y subir imágenes Docker

> **Mac ARM (M1/M2)**: Las imágenes deben compilarse con `--platform linux/amd64` para EKS.

```bash
cd ../..  # volver a la raíz del proyecto

AWS_ACCOUNT_ID="<tu-account-id>"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"

# Login a ECR
AWS_PROFILE=maestria aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

# Build y push todos los servicios
SERVICES=("gateway-service" "auth-service" "inventory-service" "search-service" \
  "cart-service" "notification-service" "health-copilot" "payment-service" "booking-service")

for SERVICE in "${SERVICES[@]}"; do
    if [ "$SERVICE" = "health-copilot" ]; then
        SERVICE_DIR="services/health_copilot"
    else
        SERVICE_DIR="services/${SERVICE//-/_}"
    fi

    echo "Building $SERVICE..."
    docker build --platform linux/amd64 \
      -t $ECR_REGISTRY/proyecto-final-dev-${SERVICE}:latest $SERVICE_DIR
    docker push $ECR_REGISTRY/proyecto-final-dev-${SERVICE}:latest
done
```

> Si `notification-service` falla con poetry lock error, regenerar:
> ```bash
> cd services/notification_service && rm poetry.lock && poetry lock --no-update && cd ../..
> ```
> Lo mismo aplica para `auth-service` si falla por `bcrypt` constraint.

### Paso 6: Instalar NGINX Ingress Controller

```bash
AWS_PROFILE=maestria kubectl apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/aws/deploy.yaml

# Esperar a que esté listo (~1-2 min)
AWS_PROFILE=maestria kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

### Paso 7: Desplegar servicios

```bash
# Aplicar todos los deployments
AWS_PROFILE=maestria kubectl apply -f kubernetes/deployments/

# Aplicar ingress
AWS_PROFILE=maestria kubectl apply -f kubernetes/ingress.yaml
```

### Paso 8: Verificar

```bash
AWS_PROFILE=maestria kubectl get pods          # todos deben estar Running
AWS_PROFILE=maestria kubectl get ingress       # ver URL del Load Balancer

# Obtener URL del LB
LB_URL=$(AWS_PROFILE=maestria kubectl get ingress api-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "API: http://$LB_URL"

# Test rápido
curl http://$LB_URL/health
curl http://$LB_URL/api/v1/search/destinations
```

---

## Servicios desplegados

| Servicio | Puerto | Descripción | Secrets/ConfigMaps |
|----------|--------|-------------|-------------------|
| gateway-service | 8000 | API Gateway — auth + proxy | — (env vars para service URLs) |
| auth-service | 8000 | Autenticación JWT | `auth-service-secrets` |
| inventory-service | 8000 | Hoteles, habitaciones, holds | `inventory-service-secrets`, `inventory-service-config`, `shared-infra-config` |
| search-service | 8000 | Búsqueda de hoteles | `search-service-config`, `shared-infra-config` |
| search-worker | — | Worker SQS para sync | `search-service-config`, `shared-infra-config` |
| cart-service | 8000 | Carrito de compras | `cart-service-secrets`, `cart-service-config`, `shared-infra-config` |
| booking-service | 8000 | Reservas | `booking-service-secrets`, `shared-infra-config`, `shared-service-discovery` |
| booking-worker | — | Worker SQS para pagos | `booking-service-secrets`, `shared-infra-config`, `shared-service-discovery` |
| payment-service | 8000 | Procesamiento de pagos | `payment-service-secrets`, `shared-infra-config`, `shared-service-discovery` |
| notification-service | 8000 | Push notifications | `notification-service-secrets`, `notification-service-config`, `shared-infra-config` |
| health-copilot | 8000 | Monitor de salud | — |

### Routing

El **Ingress** enruta todo `/api/v1/*` al `gateway-service`. El gateway resuelve internamente:

| Ruta | Autenticación | Servicio destino |
|------|--------------|-----------------|
| `/api/v1/auth/*` | Pública | auth-service |
| `/api/v1/search/*` | Pública | search-service |
| `/api/v1/inventory/*` | Pública (holds requieren auth) | inventory-service |
| `/api/v1/bookings` | Traveler (Bearer token) | booking-service |
| `/api/v1/bookings/hotel/*` | Hotel Admin (Bearer + hotel resolution) | booking-service |
| `/api/v1/cart/*` | Traveler | cart-service |
| `/api/v1/payments/*` | Mixta (initiate requiere auth) | payment-service |
| `/api/v1/reports/*` | Hotel Admin | reports-service |
| `/api/v1/notifications/*` | Traveler | notification-service |

> **Nota**: `t3.small` tiene ~1.4GB RAM. Con 11 pods usando `requests: 64Mi` y 2 nodos, hay suficiente capacidad.

---

## Actualizar después de cambios en código

```bash
AWS_ACCOUNT_ID="<tu-account-id>"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"

# Login a ECR
AWS_PROFILE=maestria aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

# Build, push y restart un servicio
SERVICE="gateway-service"  # cambiar según necesidad
SERVICE_DIR="services/${SERVICE//-/_}"

docker build --platform linux/amd64 \
  -t $ECR_REGISTRY/proyecto-final-dev-${SERVICE}:latest $SERVICE_DIR
docker push $ECR_REGISTRY/proyecto-final-dev-${SERVICE}:latest
AWS_PROFILE=maestria kubectl rollout restart deployment/${SERVICE}
```

Mapeo de nombres (servicio → directorio):
| Servicio | Directorio |
|----------|-----------|
| gateway-service | `services/gateway_service/` |
| auth-service | `services/auth_service/` |
| booking-service | `services/booking_service/` |
| inventory-service | `services/inventory_service/` |
| search-service | `services/search_service/` |
| cart-service | `services/cart_service/` |
| payment-service | `services/payment_service/` |
| notification-service | `services/notification_service/` |
| health-copilot | `services/health_copilot/` |

---

## Destruir TODO (evitar cargos)

```bash
# 1. Eliminar recursos de Kubernetes (libera el Load Balancer)
AWS_PROFILE=maestria kubectl delete -f kubernetes/ingress.yaml 2>/dev/null
AWS_PROFILE=maestria kubectl delete -f kubernetes/deployments/ 2>/dev/null

# 2. Destruir infraestructura
cd infrastructure/terraform
AWS_PROFILE=maestria terraform destroy -var-file=terraform.tfvars
# Escribir "yes" cuando pregunte
```

> Tarda ~15-20 minutos. **No interrumpir.**
> Si falla por timeout: re-ejecutar `terraform destroy`.
> Si queda un lock: `terraform force-unlock <LOCK-ID>`
> Si el secret queda pendiente:
> `aws secretsmanager delete-secret --secret-id proyecto-final-dev-db-password --region us-east-1 --force-delete-without-recovery --profile maestria`

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `terraform apply` falla en EKS Access Entry (409) | `terraform import 'module.eks.aws_eks_access_entry.admin' 'proyecto-final-dev:arn:aws:iam::<ACCOUNT_ID>:root'` y re-ejecutar |
| ElastiCache `InvalidCredentialsException` | Transitorio — re-ejecutar `terraform apply` |
| `terraform apply/destroy` falla por lock | `terraform force-unlock <LOCK-ID>` |
| Poetry lock incompatible en Docker build | `cd services/<servicio> && rm poetry.lock && poetry lock --no-update` |
| `InvalidImageName` en pods | Verificar que el YAML tiene la URL completa de ECR, no `${ECR_REGISTRY}` |
| `CreateContainerConfigError` | Falta Secret o ConfigMap. Verificar con `kubectl describe pod <pod>` |
| `ImagePullBackOff` | Verificar `docker push` exitoso. Nombre ECR: `proyecto-final-dev-<servicio>` |
| Pods en CrashLoopBackOff | `kubectl logs <pod>`. Puede ser DB migration o dependencia faltante |
| kubectl 401 Unauthorized | `aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1 --profile maestria` |
| Cart/Booking 401 desde cliente | Verificar que el cliente envía `Authorization: Bearer <token>`. Gateway valida el token via auth-service |
| Hotel admin endpoints 403 | Verificar que el usuario tiene `role: hotel_admin` y está asociado a un hotel en inventory (`Hotel.admin_id`) |
| Mac ARM: pods crash en EKS | Asegurar `--platform linux/amd64` en `docker build` |
| Secret "scheduled for deletion" | `aws secretsmanager delete-secret --secret-id <id> --region us-east-1 --force-delete-without-recovery --profile maestria` |
