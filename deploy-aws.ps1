# Script de despliegue completo en AWS
# Ejecutar: .\deploy-aws.ps1

param(
    [switch]$SkipBackend,
    [switch]$SkipDocker,
    [switch]$DestroyAll
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DESPLIEGUE AUTOMÁTICO EN AWS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Función para verificar herramientas
function Test-Tools {
    Write-Host "🔧 Verificando herramientas..." -ForegroundColor Yellow
    
    $tools = @{
        "aws" = "AWS CLI"
        "terraform" = "Terraform"
        "kubectl" = "kubectl"
        "docker" = "Docker"
    }
    
    foreach ($tool in $tools.Keys) {
        try {
            $null = Get-Command $tool -ErrorAction Stop
            Write-Host "  ✅ $($tools[$tool]) instalado" -ForegroundColor Green
        } catch {
            Write-Host "  ❌ $($tools[$tool]) NO instalado" -ForegroundColor Red
            Write-Host "     Instala desde: https://docs.aws.amazon.com/" -ForegroundColor Yellow
            exit 1
        }
    }
    
    # Verificar credenciales AWS
    try {
        aws sts get-caller-identity | Out-Null
        Write-Host "  ✅ AWS CLI configurado correctamente" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ AWS CLI no configurado. Ejecuta: aws configure" -ForegroundColor Red
        exit 1
    }
}

# Función para crear backend
function New-TerraformBackend {
    if ($SkipBackend) {
        Write-Host "⏭️  Saltando creación de backend" -ForegroundColor Yellow
        return
    }
    
    Write-Host ""
    Write-Host "📦 Creando backend de Terraform..." -ForegroundColor Yellow
    
    # Crear bucket S3
    try {
        aws s3 mb s3://proyecto-final-terraform-state --region us-east-1 2>$null
        Write-Host "  ✅ Bucket S3 creado" -ForegroundColor Green
    } catch {
        Write-Host "  ℹ️  Bucket S3 ya existe" -ForegroundColor Gray
    }
    
    # Habilitar versionado
    aws s3api put-bucket-versioning --bucket proyecto-final-terraform-state --versioning-configuration Status=Enabled
    
    # Crear tabla DynamoDB
    try {
        aws dynamodb create-table `
            --table-name proyecto-final-terraform-locks `
            --attribute-definitions AttributeName=LockID,AttributeType=S `
            --key-schema AttributeName=LockID,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST `
            --region us-east-1 2>$null
        Write-Host "  ✅ Tabla DynamoDB creada" -ForegroundColor Green
    } catch {
        Write-Host "  ℹ️  Tabla DynamoDB ya existe" -ForegroundColor Gray
    }
}

# Función para desplegar infraestructura
function Deploy-Infrastructure {
    Write-Host ""
    Write-Host "🚀 Desplegando infraestructura con Terraform..." -ForegroundColor Yellow
    Write-Host "⚠️  Esto tomará 15-20 minutos y costará ~`$100/mes" -ForegroundColor Red
    Write-Host ""
    
    $confirm = Read-Host "¿Continuar? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "❌ Despliegue cancelado" -ForegroundColor Red
        exit 0
    }
    
    Set-Location infrastructure/terraform
    
    # Inicializar Terraform
    Write-Host ""
    Write-Host "🔧 Inicializando Terraform..." -ForegroundColor Yellow
    terraform init
    
    # Aplicar
    Write-Host ""
    Write-Host "📋 Aplicando configuración..." -ForegroundColor Yellow
    terraform apply -auto-approve
    
    # Guardar outputs
    Write-Host ""
    Write-Host "📝 Guardando outputs..." -ForegroundColor Yellow
    terraform output | Out-File -FilePath "..\..\terraform-outputs.txt"
    
    Set-Location ..\..
    
    Write-Host ""
    Write-Host "✅ Infraestructura desplegada exitosamente" -ForegroundColor Green
}

# Función para configurar Kubernetes
function Set-KubernetesConfig {
    Write-Host ""
    Write-Host "⚙️  Configurando kubectl..." -ForegroundColor Yellow
    
    aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
    
    Write-Host "✅ kubectl configurado" -ForegroundColor Green
    
    # Crear secrets y configmaps
    Write-Host ""
    Write-Host "🔑 Creando secrets y configmaps..." -ForegroundColor Yellow
    
    Set-Location infrastructure/terraform
    
    $DB_ENDPOINT = terraform output -raw rds_endpoint
    $DB_NAME = terraform output -raw rds_database_name
    $REDIS_ENDPOINT = terraform output -raw redis_endpoint
    $SQS_QUEUE_URL = terraform output -raw sqs_hotel_sync_queue_url
    $INVENTORY_ROLE_ARN = terraform output -raw inventory_service_role_arn
    $SEARCH_ROLE_ARN = terraform output -raw search_service_role_arn
    
    Set-Location ..\..
    
    # Obtener password de RDS
    $DB_PASSWORD = aws secretsmanager get-secret-value --secret-id proyecto-final-dev-db-password --query SecretString --output text
    
    # Crear secrets
    $services = @("auth-service", "booking-service", "reports-service", "inventory-service", "commercial-service", "payment-service")
    foreach ($service in $services) {
        kubectl create secret generic "$service-secrets" `
            --from-literal=database-url="postgresql://admin:${DB_PASSWORD}@${DB_ENDPOINT}/${DB_NAME}" `
            --dry-run=client -o yaml | kubectl apply -f -
        Write-Host "  ✅ Secret creado para $service" -ForegroundColor Green
    }
    
    # Crear ConfigMaps
    kubectl create configmap inventory-service-config `
        --from-literal=redis-url="redis://${REDIS_ENDPOINT}:6379" `
        --from-literal=sqs-queue-url="${SQS_QUEUE_URL}" `
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap search-service-config `
        --from-literal=redis-url="redis://${REDIS_ENDPOINT}:6379" `
        --from-literal=sqs-queue-url="${SQS_QUEUE_URL}" `
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap cart-service-config `
        --from-literal=redis-url="redis://${REDIS_ENDPOINT}:6379" `
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap notification-service-config `
        --from-literal=redis-url="redis://${REDIS_ENDPOINT}:6379" `
        --dry-run=client -o yaml | kubectl apply -f -
    
    Write-Host "✅ ConfigMaps creados" -ForegroundColor Green
    
    # Actualizar manifests
    Write-Host ""
    Write-Host "📝 Actualizando manifests de Kubernetes..." -ForegroundColor Yellow
    
    $ECR_REGISTRY = (aws ecr describe-repositories --query 'repositories[0].repositoryUri' --output text).Split('/')[0]
    
    Get-ChildItem kubernetes/deployments/*.yaml | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        $content = $content -replace '\$\{ECR_REGISTRY\}', "$ECR_REGISTRY/proyecto-final-dev"
        $content = $content -replace '\$\{IMAGE_TAG\}', 'latest'
        $content = $content -replace '\$\{INVENTORY_SERVICE_ROLE_ARN\}', $INVENTORY_ROLE_ARN
        $content = $content -replace '\$\{SEARCH_SERVICE_ROLE_ARN\}', $SEARCH_ROLE_ARN
        Set-Content $_.FullName -Value $content
        Write-Host "  ✅ Actualizado $($_.Name)" -ForegroundColor Green
    }
}

# Función para build y push de Docker
function Build-DockerImages {
    if ($SkipDocker) {
        Write-Host "⏭️  Saltando build de Docker" -ForegroundColor Yellow
        return
    }
    
    Write-Host ""
    Write-Host "🔨 Construyendo imágenes Docker..." -ForegroundColor Yellow
    
    $ECR_REGISTRY = (aws ecr describe-repositories --query 'repositories[0].repositoryUri' --output text).Split('/')[0]
    
    # Login a ECR
    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY
    
    $services = @("auth_service", "booking_service", "search_service", "cart_service", "reports_service", "inventory_service", "commercial_service", "notification_service", "payment_service", "health_copilot")
    
    foreach ($service in $services) {
        $serviceName = $service -replace '_', '-'
        Write-Host "  🔨 Building $serviceName..." -ForegroundColor Cyan
        
        docker build -t "${ECR_REGISTRY}/proyecto-final-dev-${serviceName}:latest" "services/$service/"
        
        Write-Host "  📤 Pushing $serviceName..." -ForegroundColor Cyan
        docker push "${ECR_REGISTRY}/proyecto-final-dev-${serviceName}:latest"
        
        Write-Host "  ✅ $serviceName completado" -ForegroundColor Green
    }
}

# Función para desplegar en Kubernetes
function Deploy-Kubernetes {
    Write-Host ""
    Write-Host "🚀 Desplegando servicios en Kubernetes..." -ForegroundColor Yellow
    
    kubectl apply -f kubernetes/deployments/
    Start-Sleep -Seconds 10
    kubectl apply -f kubernetes/ingress.yaml
    
    Write-Host "✅ Servicios desplegados" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "📊 Estado de pods:" -ForegroundColor Yellow
    kubectl get pods -o wide
    
    Write-Host ""
    Write-Host "🌐 Load Balancer URL:" -ForegroundColor Yellow
    kubectl get ingress api-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
    Write-Host ""
}

# Función para destruir todo
function Remove-AllInfrastructure {
    Write-Host ""
    Write-Host "🗑️  DESTRUYENDO TODA LA INFRAESTRUCTURA" -ForegroundColor Red
    Write-Host "⚠️  Esto eliminará TODOS los recursos en AWS" -ForegroundColor Red
    Write-Host ""
    
    $confirm = Read-Host "¿Estás SEGURO? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "❌ Destrucción cancelada" -ForegroundColor Yellow
        exit 0
    }
    
    # Eliminar deployments de K8s
    Write-Host ""
    Write-Host "Eliminando deployments de Kubernetes..." -ForegroundColor Yellow
    kubectl delete -f kubernetes/deployments/ 2>$null
    kubectl delete -f kubernetes/ingress.yaml 2>$null
    
    # Destruir infraestructura
    Set-Location infrastructure/terraform
    terraform destroy -auto-approve
    Set-Location ..\..
    
    Write-Host ""
    Write-Host "✅ Infraestructura eliminada" -ForegroundColor Green
}

# MAIN
if ($DestroyAll) {
    Remove-AllInfrastructure
    exit 0
}

Test-Tools
New-TerraformBackend
Deploy-Infrastructure
Set-KubernetesConfig
Build-DockerImages
Deploy-Kubernetes

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ DESPLIEGUE COMPLETO EXITOSO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Para ver el estado: kubectl get pods" -ForegroundColor Cyan
Write-Host "📜 Para ver logs: kubectl logs -l app=inventory-service" -ForegroundColor Cyan
Write-Host "🗑️  Para eliminar todo: .\deploy-aws.ps1 -DestroyAll" -ForegroundColor Cyan
Write-Host ""
