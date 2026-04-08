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
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/proyecto-final-dev"

echo -e "${YELLOW}Paso 1: Configurar acceso a EKS${NC}"

# Obtener datos del cluster
ENDPOINT=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.endpoint" --output text)
CA_DATA=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.certificateAuthority.data" --output text)
CLUSTER_ARN="arn:aws:eks:${REGION}:${AWS_ACCOUNT_ID}:cluster/${CLUSTER_NAME}"

# Determinar comando de autenticación
# En Windows, aws.exe (PyInstaller) crashea como subproceso de kubectl.
# Usar aws-iam-authenticator (binario Go nativo) si está disponible.
IAM_AUTH_PATH=""
if command -v aws-iam-authenticator &>/dev/null; then
    IAM_AUTH_PATH="aws-iam-authenticator"
elif [ -f "$HOME/bin/aws-iam-authenticator.exe" ]; then
    IAM_AUTH_PATH="$(cygpath -w "$HOME/bin/aws-iam-authenticator.exe" 2>/dev/null || echo "$HOME/bin/aws-iam-authenticator.exe")"
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
HOTEL_SYNC_QUEUE_URL=$(terraform output -raw hotel_sync_queue_url)

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

# Crear secret de base de datos
kubectl create secret generic db-credentials \
  --from-literal=username=dbadmin \
  --from-literal=password="$DB_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}Secrets creados${NC}"

echo ""
echo -e "${YELLOW}Paso 5: Crear ConfigMaps${NC}"

kubectl create configmap app-config \
  --from-literal=DB_HOST="$DB_ENDPOINT" \
  --from-literal=DB_NAME="$DB_NAME" \
  --from-literal=REDIS_URL="redis://$REDIS_ENDPOINT:6379" \
  --from-literal=HOTEL_SYNC_QUEUE_URL="$HOTEL_SYNC_QUEUE_URL" \
  --from-literal=AWS_REGION="$REGION" \
  --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}ConfigMaps creados${NC}"

echo ""
echo -e "${YELLOW}Paso 6: Login a ECR${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

echo ""
echo -e "${YELLOW}Paso 7: Construir y subir imágenes Docker${NC}"
echo "Esto tomará varios minutos..."

SERVICES=("auth-service" "inventory-service" "search-service" "cart-service" "notification-service" "health-copilot")

for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo -e "${YELLOW}Construyendo $SERVICE...${NC}"
    
    if [ "$SERVICE" = "health-copilot" ]; then
        SERVICE_DIR="services/health_copilot"
    else
        SERVICE_DIR="services/${SERVICE//-/_}"
    fi
    
    docker build -t $ECR_REGISTRY/$SERVICE:latest $SERVICE_DIR
    docker push $ECR_REGISTRY/$SERVICE:latest
    
    echo -e "${GREEN}$SERVICE subido a ECR${NC}"
done

echo ""
echo -e "${YELLOW}Paso 8: Desplegar servicios en Kubernetes${NC}"

# Desplegar en orden
kubectl apply -f kubernetes/deployments/auth-service.yaml
kubectl apply -f kubernetes/deployments/inventory-service.yaml
kubectl apply -f kubernetes/deployments/search-service.yaml
kubectl apply -f kubernetes/deployments/search-worker.yaml
kubectl apply -f kubernetes/deployments/cart-service.yaml
kubectl apply -f kubernetes/deployments/notification-service.yaml
kubectl apply -f kubernetes/deployments/health-copilot.yaml

echo -e "${GREEN}Servicios desplegados${NC}"

echo ""
echo -e "${YELLOW}Paso 9: Desplegar Ingress${NC}"
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
    LB_URL=$(kubectl get ingress hotel-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ ! -z "$LB_URL" ]; then
        echo -e "${GREEN}Load Balancer URL: http://$LB_URL${NC}"
        echo ""
        echo "Endpoints disponibles:"
        echo "  - http://$LB_URL/auth/health"
        echo "  - http://$LB_URL/inventory/health"
        echo "  - http://$LB_URL/search/health"
        echo "  - http://$LB_URL/cart/health"
        echo "  - http://$LB_URL/notifications/health"
        echo "  - http://$LB_URL/copilot/health"
        break
    fi
    echo -n "."
    sleep 3
done

if [ -z "$LB_URL" ]; then
    echo ""
    echo -e "${YELLOW}El Load Balancer aún no está listo. Ejecuta este comando para obtener la URL:${NC}"
    echo "kubectl get ingress hotel-ingress"
fi

echo ""
echo -e "${GREEN}Despliegue finalizado exitosamente!${NC}"
