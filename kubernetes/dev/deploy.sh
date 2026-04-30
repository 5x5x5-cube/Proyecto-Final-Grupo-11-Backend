#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==> Apuntando Docker al daemon de minikube..."
eval $(minikube docker-env)

echo "==> Construyendo imagenes..."
cd "$PROJECT_ROOT"
docker-compose build

echo "==> Aplicando infraestructura (postgres, redis, localstack)..."
kubectl apply -f "$SCRIPT_DIR/infrastructure.yaml"

echo "==> Esperando que localstack este listo..."
kubectl wait --for=condition=ready pod -l app=localstack --timeout=120s

echo "==> Aplicando configuracion y secrets..."
kubectl apply -f "$SCRIPT_DIR/shared-config.yaml"
kubectl apply -f "$SCRIPT_DIR/secrets.yaml"

echo "==> Aplicando deployments..."
kubectl apply -f "$SCRIPT_DIR/deployments/"

echo "==> Esperando que los servicios esten listos..."
kubectl wait --for=condition=ready pod -l app=inventory-service --timeout=120s
kubectl wait --for=condition=ready pod -l app=gateway-service --timeout=120s

echo ""
echo "==> Todo listo. Para acceder al gateway:"
minikube service gateway-service --url
