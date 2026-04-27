#!/bin/bash
set -e

echo "=========================================="
echo "  Setup Kubernetes Resources for AWS EKS"
echo "=========================================="

# Check if terraform outputs are available
cd infrastructure/terraform

echo ""
echo "📦 Fetching Terraform outputs..."
DB_ENDPOINT=$(terraform output -raw rds_endpoint)
DB_NAME=$(terraform output -raw rds_database_name)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)
SQS_QUEUE_URL=$(terraform output -raw sqs_hotel_sync_queue_url)
SNS_TOPIC_ARN=$(terraform output -raw sns_topic_arn)
PAYMENT_BOOKING_QUEUE_URL=$(terraform output -raw payment_booking_queue_url)
NOTIFICATION_QUEUE_URL=$(terraform output -raw notification_queue_url)
INVENTORY_ROLE_ARN=$(terraform output -raw inventory_service_role_arn)
SEARCH_ROLE_ARN=$(terraform output -raw search_service_role_arn)
ECR_URLS=$(terraform output -json ecr_repository_urls)

cd ../..

echo "  RDS Endpoint:    $DB_ENDPOINT"
echo "  Redis Endpoint:  $REDIS_ENDPOINT"
echo "  SQS Queue URL:   $SQS_QUEUE_URL"

# Get RDS password from Secrets Manager
echo ""
echo "🔐 Fetching RDS password from Secrets Manager..."
DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id proyecto-final-dev-db-password \
  --query SecretString --output text)

# Create secrets for services that use database
echo ""
echo "🔑 Creating Kubernetes Secrets..."

for service in auth-service booking-service reports-service inventory-service commercial-service payment-service; do
  kubectl create secret generic ${service}-secrets \
    --from-literal=database-url="postgresql://admin:${DB_PASSWORD}@${DB_ENDPOINT}/${DB_NAME}" \
    --dry-run=client -o yaml | kubectl apply -f -
  echo "  ✅ Created secret for ${service}"
done

# Create shared ConfigMaps
echo ""
echo "📋 Creating shared ConfigMaps..."

kubectl create configmap shared-infra-config \
  --from-literal=redis-url="redis://${REDIS_ENDPOINT}:6379" \
  --from-literal=sqs-queue-url="${SQS_QUEUE_URL}" \
  --from-literal=sns-topic-arn="${SNS_TOPIC_ARN}" \
  --from-literal=payment-booking-queue-url="${PAYMENT_BOOKING_QUEUE_URL}" \
  --from-literal=notification-queue-url="${NOTIFICATION_QUEUE_URL}" \
  --from-literal=aws-region="us-east-1" \
  --from-literal=aws-endpoint-url="" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "  ✅ Created shared-infra-config (Redis, SQS, SNS, AWS)"

kubectl create configmap shared-service-discovery \
  --from-literal=inventory-service-url="http://inventory-service:80" \
  --from-literal=booking-service-url="http://booking-service:80" \
  --from-literal=cart-service-url="http://cart-service:80" \
  --from-literal=search-service-url="http://search-service:80" \
  --from-literal=notification-service-url="http://notification-service:80" \
  --from-literal=auth-service-url="http://auth-service:80" \
  --from-literal=payment-service-url="http://payment-service:80" \
  --from-literal=reports-service-url="http://reports-service:80" \
  --from-literal=commercial-service-url="http://commercial-service:80" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "  ✅ Created shared-service-discovery (internal service URLs)"

# Replace variables in K8s manifests
echo ""
echo "📝 Replacing variables in Kubernetes manifests..."

ECR_REGISTRY=$(echo $ECR_URLS | python3 -c "import sys,json; urls=json.load(sys.stdin); print(list(urls.values())[0].rsplit('/',1)[0])")

for file in kubernetes/deployments/*.yaml; do
  sed -i "s|\${ECR_REGISTRY}|${ECR_REGISTRY}|g" $file
  sed -i "s|\${IMAGE_TAG}|latest|g" $file
  sed -i "s|\${INVENTORY_SERVICE_ROLE_ARN}|${INVENTORY_ROLE_ARN}|g" $file
  sed -i "s|\${SEARCH_SERVICE_ROLE_ARN}|${SEARCH_ROLE_ARN}|g" $file
  echo "  ✅ Updated $(basename $file)"
done

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. kubectl apply -f kubernetes/deployments/"
echo "  2. kubectl apply -f kubernetes/ingress.yaml"
echo "  3. kubectl get pods"
echo ""
