#!/bin/bash
set -e

echo "=========================================="
echo "  Despliegue de Aplicaciones en EKS"
echo "=========================================="
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Variables
CLUSTER_NAME="proyecto-final-dev"
REGION="us-east-1"
AWS_ACCOUNT_ID="618246140762"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
ECR_PREFIX="proyecto-final-dev"

echo -e "${YELLOW}Paso 1: Configurar acceso a EKS${NC}"

# Obtener datos del cluster
ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.endpoint" --output text)
CA_DATA=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.certificateAuthority.data" --output text)
CLUSTER_ARN="arn:aws:eks:${REGION}:${AWS_ACCOUNT_ID}:cluster/${CLUSTER_NAME}"

# Determinar comando de autenticación
# En Windows, aws.exe (PyInstaller) crashea como subproceso de kubectl.
# Usar aws-iam-authenticator (binario Go nativo) si está disponible.
IAM_AUTH_PATH=""
if [ -f "$HOME/bin/aws-iam-authenticator.exe" ]; then
    IAM_AUTH_PATH="$(cygpath -w "$HOME/bin/aws-iam-authenticator.exe" 2>/dev/null || echo "C:\\Users\\$USER\\bin\\aws-iam-authenticator.exe")"
elif command -v aws-iam-authenticator &>/dev/null; then
    IAM_AUTH_PATH="$(which aws-iam-authenticator)"
fi

KUBECONFIG_FILE="$HOME/.kube/config"
mkdir -p "$HOME/.kube"

if [ -n "$IAM_AUTH_PATH" ]; then
    echo "Usando aws-iam-authenticator para autenticación"
    cat > "$KUBECONFIG_FILE" <<EOF
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: ${ENDPOINT}
  name: ${CLUSTER_ARN}
contexts:
- context:
    cluster: ${CLUSTER_ARN}
    user: ${CLUSTER_ARN}
  name: ${CLUSTER_ARN}
current-context: ${CLUSTER_ARN}
kind: Config
preferences: {}
users:
- name: ${CLUSTER_ARN}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      args:
      - token
      - -i
      - ${CLUSTER_NAME}
      - --region
      - ${REGION}
      command: ${IAM_AUTH_PATH}
EOF
else
    echo "Usando aws CLI para autenticación"
    aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION
fi

echo ""
echo -e "${YELLOW}Paso 2: Verificar acceso al cluster${NC}"
kubectl get nodes
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: No se puede acceder al cluster.${NC}"
    echo "Verifica que aws-iam-authenticator.exe esté en ~/bin/"
    exit 1
fi

echo ""
echo -e "${GREEN}Acceso al cluster verificado correctamente${NC}"

echo ""
echo -e "${YELLOW}Paso 3: Obtener outputs de Terraform${NC}"
cd infrastructure/terraform

DB_ENDPOINT=$(terraform output -raw rds_endpoint)
DB_NAME=$(terraform output -raw rds_database_name)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)
HOTEL_SYNC_QUEUE_URL=$(terraform output -raw sqs_hotel_sync_queue_url)

echo "DB Endpoint: $DB_ENDPOINT"
echo "Redis Endpoint: $REDIS_ENDPOINT"
echo "SQS Queue: $HOTEL_SYNC_QUEUE_URL"

cd ../..

echo ""
echo -e "${YELLOW}Paso 4: Crear Secrets de Kubernetes${NC}"

# Obtener contraseña de DB desde Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id proyecto-final-dev-db-password \
  --region $REGION \
  --query SecretString \
  --output text)

# Construir DATABASE_URL para cada servicio que lo necesite
# Formato: postgresql+asyncpg://user:pass@host:port/dbname
DB_HOST=$(echo "$DB_ENDPOINT" | cut -d: -f1)
DB_PORT=$(echo "$DB_ENDPOINT" | cut -d: -f2)
DATABASE_URL="postgresql+asyncpg://dbadmin:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

REDIS_URL="redis://${REDIS_ENDPOINT}:6379"

# Secrets con database-url por servicio
for SVC in auth-service inventory-service cart-service payment-service booking-service; do
    kubectl create secret generic ${SVC}-secrets \
      --from-literal=database-url="$DATABASE_URL" \
      --dry-run=client -o yaml | kubectl apply -f -
done

echo -e "${GREEN}Secrets creados${NC}"

echo ""
echo -e "${YELLOW}Paso 5: Crear ConfigMaps${NC}"

# ConfigMaps por servicio según lo que cada deployment espera
kubectl create configmap cart-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap notification-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap inventory-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=sqs-queue-url="$HOTEL_SYNC_QUEUE_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap search-service-config \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=sqs-queue-url="$HOTEL_SYNC_QUEUE_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}ConfigMaps creados${NC}"

echo ""
echo -e "${YELLOW}Paso 6: Login a ECR${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

echo ""
echo -e "${YELLOW}Paso 7: Construir y subir imágenes Docker${NC}"
echo "Esto tomará varios minutos..."

SERVICES=("auth-service" "inventory-service" "search-service" "cart-service" "notification-service" "health-copilot" "payment-service" "booking-service")

for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo -e "${YELLOW}Construyendo $SERVICE...${NC}"
    
    if [ "$SERVICE" = "health-copilot" ]; then
        SERVICE_DIR="services/health_copilot"
    else
        SERVICE_DIR="services/${SERVICE//-/_}"
    fi
    
    docker build -t $ECR_REGISTRY/${ECR_PREFIX}-${SERVICE}:latest $SERVICE_DIR
    docker push $ECR_REGISTRY/${ECR_PREFIX}-${SERVICE}:latest
    
    echo -e "${GREEN}$SERVICE subido a ECR${NC}"
done

echo ""
echo -e "${YELLOW}Paso 8: Instalar NGINX Ingress Controller${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/aws/deploy.yaml

# Esperar a que el controller esté listo
echo "Esperando a que NGINX Ingress Controller esté listo..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=ingress-nginx \
  --timeout=120s

echo -e "${GREEN}NGINX Ingress Controller instalado${NC}"

echo ""
echo -e "${YELLOW}Paso 9: Desplegar servicios en Kubernetes${NC}"

# Solo desplegar los servicios que tienen imagen construida
DEPLOY_YAMLS=(
    "kubernetes/deployments/auth-service.yaml"
    "kubernetes/deployments/inventory-service.yaml"
    "kubernetes/deployments/search-service.yaml"
    "kubernetes/deployments/search-worker.yaml"
    "kubernetes/deployments/cart-service.yaml"
    "kubernetes/deployments/notification-service.yaml"
    "kubernetes/deployments/health-copilot.yaml"
    "kubernetes/deployments/payment-service.yaml"
    "kubernetes/deployments/booking-service.yaml"
)

for YAML in "${DEPLOY_YAMLS[@]}"; do
    echo "Aplicando $YAML..."
    kubectl apply -f "$YAML"
done

echo -e "${GREEN}Servicios desplegados${NC}"

echo ""
echo -e "${YELLOW}Paso 10: Desplegar Ingress${NC}"
kubectl apply -f kubernetes/ingress.yaml

echo ""
echo -e "${GREEN}=========================================="
echo "  Despliegue Completado"
echo "==========================================${NC}"
echo ""
echo "Comandos útiles:"
echo "  Ver pods:        kubectl get pods"
echo "  Ver servicios:   kubectl get svc"
echo "  Ver ingress:     kubectl get ingress"
echo "  Logs de un pod:  kubectl logs -f <pod-name>"
echo ""
echo "Esperando a que el Load Balancer esté listo..."
echo "Esto puede tomar 2-3 minutos..."
echo ""

# Esperar a que el ingress tenga una dirección
for i in {1..60}; do
    LB_URL=$(kubectl get ingress api-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ ! -z "$LB_URL" ]; then
        echo -e "${GREEN}Load Balancer URL: http://$LB_URL${NC}"
        echo ""
        echo "Endpoints disponibles:"
        echo "  - http://$LB_URL/auth/health"
        echo "  - http://$LB_URL/inventory/health"
        echo "  - http://$LB_URL/search/health"
        echo "  - http://$LB_URL/cart/health"
        echo "  - http://$LB_URL/notification/health"
        echo "  - http://$LB_URL/health-copilot/health"
        break
    fi
    echo -n "."
    sleep 3
done

if [ -z "$LB_URL" ]; then
    echo ""
    echo -e "${YELLOW}El Load Balancer aún no está listo. Ejecuta este comando para obtener la URL:${NC}"
    echo "kubectl get ingress api-gateway"
fi

echo ""
echo -e "${GREEN}Despliegue finalizado exitosamente!${NC}"
