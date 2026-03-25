#!/bin/bash

# Script para construir todas las imágenes Docker

set -e

echo "🐳 Construyendo todas las imágenes Docker..."

SERVICES=(
    "auth_service"
    "booking_service"
    "search_service"
    "cart_service"
    "reports_service"
    "inventory_service"
    "commercial_service"
    "notification_service"
    "payment_service"
    "health_copilot"
)

for service in "${SERVICES[@]}"; do
    service_name=$(echo $service | sed 's/_/-/g')
    echo "📦 Construyendo $service_name..."
    
    docker build -t proyecto-final-$service_name:latest services/$service
    
    if [ $? -eq 0 ]; then
        echo "✅ $service_name construido exitosamente"
    else
        echo "❌ Error construyendo $service_name"
        exit 1
    fi
done

echo ""
echo "✅ Todas las imágenes construidas exitosamente!"
echo ""
echo "Imágenes disponibles:"
docker images | grep proyecto-final
