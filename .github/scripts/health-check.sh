#!/bin/bash

# Health check script for deployed services

set -e

SERVICES=$1
MAX_RETRIES=30
RETRY_DELAY=10

IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"

for service in "${SERVICE_ARRAY[@]}"; do
    service=$(echo $service | xargs)
    echo "Checking health of $service..."
    
    retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        POD=$(kubectl get pod -l app=$service -o jsonpath="{.items[0].metadata.name}" 2>/dev/null || echo "")
        
        if [ -z "$POD" ]; then
            echo "No pod found for $service, retrying..."
            retries=$((retries + 1))
            sleep $RETRY_DELAY
            continue
        fi
        
        if kubectl exec $POD -- curl -f http://localhost:8000/health 2>/dev/null; then
            echo "✅ $service is healthy"
            break
        else
            echo "Health check failed for $service, retrying..."
            retries=$((retries + 1))
            sleep $RETRY_DELAY
        fi
    done
    
    if [ $retries -eq $MAX_RETRIES ]; then
        echo "❌ Health check failed for $service after $MAX_RETRIES attempts"
        exit 1
    fi
done

echo "✅ All services are healthy"
