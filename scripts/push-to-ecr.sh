#!/bin/bash

# Script para subir todas las imágenes a ECR

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Debes proporcionar el registry de ECR"
    echo "Uso: ./push-to-ecr.sh <ecr-registry>"
    echo "Ejemplo: ./push-to-ecr.sh 123456789.dkr.ecr.us-east-1.amazonaws.com"
    exit 1
fi

ECR_REGISTRY=$1
AWS_REGION=${2:-us-east-1}

echo "🔐 Autenticando con ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

SERVICES=(
    "auth-service"
    "booking-service"
    "search-service"
    "cart-service"
    "reports-service"
    "inventory-service"
    "commercial-service"
    "notification-service"
    "payment-service"
    "health-copilot"
)

for service in "${SERVICES[@]}"; do
    echo "📤 Subiendo $service..."
    
    # Tag image
    docker tag proyecto-final-$service:latest $ECR_REGISTRY/proyecto-final-dev-$service:latest
    
    # Push image
    docker push $ECR_REGISTRY/proyecto-final-dev-$service:latest
    
    if [ $? -eq 0 ]; then
        echo "✅ $service subido exitosamente"
    else
        echo "❌ Error subiendo $service"
        exit 1
    fi
done

echo ""
echo "✅ Todas las imágenes subidas exitosamente a ECR!"
